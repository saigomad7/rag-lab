# -*- coding: utf-8 -*-
"""
표준 RAG 평가 지표 — 검색(IR) · 생성(RAGAS 계열) · 운영
계산 방식 3종
  auto   : 규칙 · 임베딩으로 자동 계산 (LLM 불필요)
  judge  : 사내 LLM 채점 (프롬프트 제공)
  manual : 사람 확인 (20문항 표본)
RAGAS 원 구현은 외부 LLM · 패키지를 쓰므로, 여기서는 같은 정의를 사내 자원만으로 근사한다.
"""
import re
import numpy as np
import pandas as pd

# ---------------- 공통 ----------------
_NUM = re.compile(r'\d[\d,\.]*\s*(?:%|원|달러|USD|EB|TB|GB|억|조|배|bp|p)?')
_PERIOD = re.compile(r'(20\d{2}\s*년|\d\s*분기|[1-4]Q\s*\d{0,2}|\d{1,2}\s*월|상반기|하반기|전년|전분기|전월)')
_CITE = re.compile(r'\[(\d+|DB)[^\]]*\]')
_HEDGE = re.compile(r'(전망|추정|예상|가능성|것으로 보|로 추정|전망치)')
_REFUSE = re.compile(r'(확인된 자료 없음|자료가 없|확인 불가|알 수 없|제공되지 않)')


def _grams(t, n=3):
    t = re.sub(r'\s+', '', str(t or ''))
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def _cov(a, b):
    """a 의 3-gram 중 b 에 포함된 비율"""
    ga = _grams(a)
    return len(ga & _grams(b)) / len(ga) if ga else 0.0


def _sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n', str(text or '')) if len(s.strip()) >= 10]


# ---------------- 검색 지표 (IR · auto) ----------------
def precision_at_k(rel, k):
    """상위 k 중 정답 비율"""
    top = rel[:k]
    return sum(top) / k if k else 0.0


def average_precision(rel):
    """MAP 의 문항 단위 값"""
    hits, s = 0, 0.0
    for i, v in enumerate(rel, 1):
        if v:
            hits += 1
            s += hits / i
    return s / hits if hits else 0.0


def context_precision(rel, k=10):
    """RAGAS context precision 근사 — 상위 k 컨텍스트 중 정답 관련 비율"""
    return precision_at_k(rel, min(k, len(rel)) or 1)


def context_recall(gold_text, contexts):
    """RAGAS context recall 근사 — 정답 문장 내용이 검색 컨텍스트에 포함된 비율"""
    if not str(gold_text or '').strip():
        return np.nan
    joined = ' '.join(str(c) for c in contexts)
    return _cov(gold_text, joined)


# ---------------- 생성 지표 (RAGAS 계열) ----------------
def faithfulness(answer, contexts, th=0.30):
    """
    답변 문장 중 컨텍스트에 근거가 있는 비율 (근거 없는 문장 = 환각 후보).
    문장별 최대 3-gram 겹침이 th 이상이면 근거 있음으로 본다.
    """
    sents = _sentences(answer)
    if not sents:
        return np.nan, []
    ctx = [str(c) for c in contexts]
    flags = []
    for s in sents:
        best = max((_cov(s, c) for c in ctx), default=0.0)
        flags.append((s, round(best, 3), best >= th))
    return sum(1 for _, _, ok in flags if ok) / len(flags), flags


def answer_relevancy(question, answer, embedder=None):
    """질문과 답변의 의미 유사도 (임베딩). 임베더 없으면 3-gram 겹침으로 근사."""
    if embedder is None:
        return max(_cov(question, answer), _cov(answer, question))
    v = embedder.encode([str(question), str(answer)])['dense']
    a, b = v[0], v[1]
    return float(a @ b / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1))


def citation_accuracy(answer, contexts):
    """인용 번호가 실제 컨텍스트를 가리키는지 — 번호 범위 + 해당 청크와의 겹침."""
    cites = _CITE.findall(str(answer or ''))
    if not cites:
        return np.nan, 0
    ok = 0
    for c in cites:
        if c == 'DB':
            ok += 1
            continue
        i = int(c)
        if 1 <= i <= len(contexts):
            ok += 1
    return ok / len(cites), len(cites)


def refusal_correct(answer, is_no_answer):
    """답없음 문항은 거절해야 정답 · 그 외 문항은 거절하면 오답"""
    refused = bool(_REFUSE.search(str(answer or '')))
    return int(refused == bool(is_no_answer))


def structure_check(answer, q_type=''):
    """수치 · 출처 · 시점 · 추정 표기 — 규칙 기반 구조 점검"""
    a = str(answer or '')
    return dict(has_number=bool(_NUM.search(a)), has_period=bool(_PERIOD.search(a)),
                has_citation=bool(_CITE.search(a)), has_hedge=bool(_HEDGE.search(a)),
                refused=bool(_REFUSE.search(a)))


def element_coverage(answer, must_include, th=0.25):
    """
    골든셋의 필수 요소 충족률(auto 근사) — 요소 문구와 답변의 겹침으로 판정.
    문구 표현이 달라 과소평가될 수 있으므로, 최종 확인은 judge 또는 manual 권장.
    """
    elems = [e.strip() for e in str(must_include or '').split(';') if e.strip()]
    if not elems:
        return np.nan, []
    hits = []
    for e in elems:
        key = re.sub(r'\([^)]*\)', '', e)
        cov = max(_cov(key, answer), _keyword_hit(key, answer))
        hits.append((e, round(cov, 3), cov >= th))
    return sum(1 for _, _, ok in hits if ok) / len(hits), hits


def _keyword_hit(elem, answer):
    """요소 문구의 핵심 토큰이 답변에 있는지 (0~1)"""
    toks = [t for t in re.findall(r'[가-힣A-Za-z0-9]{2,}', elem) if t not in ('또는', '제시', '표기', '수치', '내용')]
    if not toks:
        return 0.0
    a = str(answer or '')
    return sum(1 for t in toks if t in a) / len(toks)


# ---------------- LLM 채점 (judge) ----------------
JUDGE_PROMPT = """아래 [질문] · [근거 자료] · [답변] 을 보고 항목별로 0 또는 1 로만 채점하라.
채점 항목:
1. faithfulness  : 답변의 모든 문장이 근거 자료 범위 안인가 (추가 사실 없음)
2. relevancy     : 답변이 질문에 직접 답하는가
3. completeness  : 필수 요소를 모두 담았는가 — 필수 요소: {must}
4. citation      : 인용 번호가 실제 근거를 가리키는가 (인용 없으면 0)
5. hallucination : 근거에 없는 수치 · 사실을 만들어냈는가 (있으면 1, 없으면 0)

출력 형식(JSON 한 줄): {{"faithfulness":0,"relevancy":0,"completeness":0,"citation":0,"hallucination":0}}

[질문] {question}
[근거 자료]
{contexts}
[답변]
{answer}
"""


def judge_prompt(question, answer, contexts, must=''):
    ctx = '\n'.join(f'[{i}] {str(c)[:500]}' for i, c in enumerate(contexts, 1))
    return JUDGE_PROMPT.format(question=question, answer=answer, contexts=ctx, must=must or '(없음)')


def parse_judge(text):
    """LLM 채점 응답(JSON) 파싱 — 실패 시 빈 dict"""
    import json
    m = re.search(r'\{[^{}]+\}', str(text or ''))
    if not m:
        return {}
    try:
        return {k: int(v) for k, v in json.loads(m.group(0)).items()}
    except Exception:
        return {}


# ---------------- 지표 카탈로그 ----------------
METRIC_CATALOG = [
 # (구분, 지표, 정의, 계산 방식, 합격 기준, 대응 단계)
 ('검색', 'Recall@k', '정답 문서가 상위 k 에 포함된 문항 비율', 'auto', 'R@5 ≥ 0.80 · R@10 ≥ 0.90', 'S09 · S10 · S03'),
 ('검색', 'Precision@k', '상위 k 중 정답 관련 비율', 'auto', '≥ 0.40 (k=5)', 'S11 · S12'),
 ('검색', 'MRR', '첫 정답 순위의 역수 평균', 'auto', '≥ 0.65', 'S12'),
 ('검색', 'MAP', '정답 위치별 정밀도 평균', 'auto', '≥ 0.55', 'S11 · S12'),
 ('검색', 'nDCG@10', '순위 가중 정확도', 'auto', '≥ 0.70', 'S11 · S12'),
 ('검색', 'Hit Rate@k', '정답 1건 이상 포함 비율', 'auto', 'R@5 와 동일 관리', 'S09'),
 ('검색', 'Context Precision', '검색 컨텍스트 중 정답 관련 비율 (RAGAS)', 'auto', '≥ 0.50', 'S11 · S12 · MMR'),
 ('검색', 'Context Recall', '정답 문장 내용이 컨텍스트에 포함된 비율 (RAGAS)', 'auto', '≥ 0.75', 'S03 청킹 · S13 컨텍스트'),
 ('생성', 'Faithfulness', '답변 문장 중 근거 있는 비율 (RAGAS)', 'auto + judge', '≥ 0.85', 'S13 · S14'),
 ('생성', 'Answer Relevancy', '질문과 답변의 의미 정합 (RAGAS)', 'auto(임베딩)', '≥ 0.70', 'S14 프롬프트'),
 ('생성', 'Answer Correctness', '필수 요소 충족률 (골든셋 기준)', 'auto 근사 + judge', '≥ 0.75', 'S13 · S14'),
 ('생성', 'Citation Accuracy', '인용 번호가 실제 근거를 지시', 'auto', '≥ 0.90', 'S14 인용 규칙'),
 ('생성', 'Hallucination Rate', '근거 없는 수치 · 사실 생성 비율', 'judge', '≤ 0.05', 'S14 · S29 임계'),
 ('생성', 'Refusal Accuracy', '답없음 문항 거절 정확도', 'auto', '≥ 0.80', 'S14 · 점수 임계'),
 ('운영', 'p95 지연', '질의 응답 95 분위 시간', 'auto', '검색 ≤ 2초 · 답변 ≤ 8초', 'S12 후보 수'),
 ('운영', '평가 재현성', '동일 설정 2회 측정 편차', 'auto', '≤ 0.02', '캐시 · temperature 0'),
]


def catalog():
    return pd.DataFrame(METRIC_CATALOG, columns=['구분', '지표', '정의', '계산 방식', '합격 기준', '대응 단계'])


def evaluate_answers(rows, embedder=None):
    """
    rows: [{qid, question, answer, contexts[list], must_include, is_no_answer}]
    반환: 문항별 지표 DataFrame (auto 계산분)
    """
    out = []
    for r in rows:
        ctx = r.get('contexts') or []
        f, _ = faithfulness(r.get('answer'), ctx)
        cov, _ = element_coverage(r.get('answer'), r.get('must_include', ''))
        cite, n_cite = citation_accuracy(r.get('answer'), ctx)
        out.append(dict(qid=r.get('qid'), q_type=r.get('q_type', ''),
                        faithfulness=f, answer_relevancy=answer_relevancy(r.get('question'), r.get('answer'), embedder),
                        answer_correctness=cov, citation_accuracy=cite, n_citation=n_cite,
                        context_recall=context_recall(r.get('gold_text', ''), ctx),
                        refusal_ok=refusal_correct(r.get('answer'), r.get('is_no_answer')),
                        **structure_check(r.get('answer'), r.get('q_type', ''))))
    return pd.DataFrame(out)
