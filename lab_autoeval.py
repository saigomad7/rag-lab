# -*- coding: utf-8 -*-
"""
골든셋 없이 정량 평가 — 사내 DB 만으로 평가셋을 자동 생성한다.
  L1 known-item  : 문서에서 고유 문장 1개를 뽑아 질의로 사용 → 그 문서가 정답 (라벨 작업 0)
  L1b 제목 질의  : 제목을 질의로 사용 → 그 문서가 정답
  L1c 중복쌍     : 근사 중복 문서쌍 → 한쪽 문장으로 질의 시 다른 쪽도 회수되는지 (의미 검색 확인)
  L2 합성 QA     : 사내 LLM 이 청크에서 질문 생성 → 자동 검증(유일성 · 난이도) 통과분만 채택
  공통 판정      : 정답 문서 ID 일치 + 정답 문장 3-gram 겹침
난이도: easy(고유 코드 · 숫자 포함) / mid(일반 문장) / hard(문장 변형 · 다문서)
"""
import re
import random
import numpy as np
import pandas as pd
import lab_config as C
import lab_text

_STOP = re.compile(r'^[\s\W]*$')
_UNIQ = re.compile(r'([A-Z]{2,}[-_]?\d+|\d[\d,\.]{2,}\s*(?:%|억|조|EB|TB|GB|달러|원)?|[A-Z]{3,})')


def _sentences(text, min_len=25, max_len=160):
    """문장 후보 추출 — 너무 짧거나 긴 것, 표 · 목차 줄은 제외."""
    out = []
    for raw in re.split(r'(?<=[.!?])\s+|\n', str(text or '')):
        s = raw.strip()
        if not (min_len <= len(s) <= max_len) or _STOP.match(s):
            continue
        if s.startswith(('>', '-----', '#', '[')) or '이전 메일' in s:
            continue                                  # 인용 · 머리말 줄 제외
        if '|' in s or re.match(r'^\s*[\d.]+\s', s) or s.count('.') > 6:
            continue                                  # 표 · 머리글 · 목차 줄 제외
        if not re.search(r'(다|요|음|함|임|됨|것|정|표)[.!?]?$', s):
            continue                                  # 문장 종결 아님(제목 · 라벨 줄) 제외
        if len(re.findall(r'[가-힣]{2,}', s)) < 3:
            continue                                  # 한글 어절 3개 미만(수치 나열 등) 제외
        out.append(s)
    return out


def difficulty(sent):
    """easy: 고유 코드 · 수치 포함 / mid: 일반 문장"""
    return 'easy' if _UNIQ.search(sent) else 'mid'


def uniqueness(sent, corpus_index, top=5):
    """이 문장이 코퍼스에서 얼마나 유일한가 — BM25 상위 결과가 한 문서에 몰리면 유일."""
    hits = corpus_index(sent, top)
    if not hits:
        return 0.0
    first = hits[0][0]
    return sum(1 for d, _ in hits if d == first) / len(hits)


def make_known_item(chunks, n=200, per_doc=1, seed=7, min_chunk_len=80):
    """
    L1 known-item 평가셋 — 라벨 작업 없이 생성.
      chunks: chunk_id · doc_id · text
    질의 = 청크에서 뽑은 문장 1개(원문 그대로), 정답 = 그 문장이 속한 문서.
    """
    rng = random.Random(seed)
    pool = chunks[chunks.text.astype(str).str.len() >= min_chunk_len]
    rows, used = [], {}
    for r in pool.sample(frac=1, random_state=seed).itertuples():
        if used.get(r.doc_id, 0) >= per_doc:
            continue
        cands = _sentences(r.text)
        if not cands:
            continue
        sent = rng.choice(cands)
        used[r.doc_id] = used.get(r.doc_id, 0) + 1
        rows.append(dict(qid=f'K{len(rows) + 1:04d}', question=sent, q_type='known-item',
                         level=difficulty(sent), gold_doc_ids=r.doc_id, gold_text=sent,
                         src_chunk=r.chunk_id))
        if len(rows) >= n:
            break
    return pd.DataFrame(rows)


def make_title_query(docs, n=200, seed=7, min_title_len=8):
    """L1b 제목 질의 — 제목만으로 해당 문서를 찾는지. 제목이 본문에 없으면 난이도 상승."""
    d = docs[docs.title.astype(str).str.len() >= min_title_len].sample(frac=1, random_state=seed)
    rows = []
    for r in d.itertuples():
        rows.append(dict(qid=f'T{len(rows) + 1:04d}', question=str(r.title), q_type='title',
                         level='easy', gold_doc_ids=r.doc_id, gold_text='', src_chunk=''))
        if len(rows) >= n:
            break
    return pd.DataFrame(rows)


def make_dup_pair(docs, text_col='body', threshold=0.8, n=100, seed=7):
    """L1c 중복쌍 — 근사 중복 문서 A·B 중 A 문장으로 질의 시 B 도 상위에 오는지(의미 회수)."""
    pairs = lab_text.near_duplicates(docs, text_col, 'doc_id', threshold=threshold)
    rng = random.Random(seed)
    idx = docs.set_index('doc_id')
    rows = []
    for p in pairs.itertuples():
        cands = _sentences(idx.loc[p.id_a, text_col])
        if not cands:
            continue
        sent = rng.choice(cands)
        rows.append(dict(qid=f'D{len(rows) + 1:04d}', question=sent, q_type='dup-pair', level='hard',
                         gold_doc_ids=f'{p.id_a};{p.id_b}', gold_text='', src_chunk='',
                         note=f'유사도 {p.similarity:.2f}'))
        if len(rows) >= n:
            break
    return pd.DataFrame(rows)


SYN_PROMPT = """아래 [문서 조각]만 보고, 이 조각이 정답이 되는 **한국어 질문 1개**를 만들어라.
조건:
- 조각에 있는 구체 정보(수치 · 고유명사 · 날짜)를 묻는다
- 조각 문장을 그대로 베끼지 않는다 (다른 표현으로)
- "이 문서", "위 자료" 같은 지시어를 쓰지 않는다
- 질문 한 줄만 출력한다

[문서 조각]
{chunk}

질문:"""


def make_synthetic(chunks, n=100, seed=7, min_chunk_len=120, llm=None):
    """
    L2 합성 QA — 사내 LLM 으로 질문 생성. llm(prompt) -> str 을 주입(테스트 용이).
    생성 실패 · 조각 복붙(겹침 과다)은 버린다.
    """
    if llm is None:
        def llm(prompt):
            import lab_search
            return lab_search.llm_answer(prompt, pd.DataFrame(columns=['text', 'doc_id']))
    pool = chunks[chunks.text.astype(str).str.len() >= min_chunk_len].sample(frac=1, random_state=seed)
    rows = []
    for r in pool.itertuples():
        try:
            q = str(llm(SYN_PROMPT.format(chunk=str(r.text)[:1200]))).strip().split('\n')[0]
        except Exception:
            continue
        q = re.sub(r'^[-*\d.\s]+', '', q)
        if len(q) < 8 or len(q) > 120:
            continue
        if _overlap(q, str(r.text)) > 0.6:          # 조각을 그대로 베낀 질문 제외
            continue
        rows.append(dict(qid=f'S{len(rows) + 1:04d}', question=q, q_type='synthetic',
                         level='mid', gold_doc_ids=r.doc_id, gold_text=str(r.text)[:200], src_chunk=r.chunk_id))
        if len(rows) >= n:
            break
    return pd.DataFrame(rows)


def _grams(t, n=3):
    t = re.sub(r'\s+', '', str(t or ''))
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def _overlap(a, b):
    ga = _grams(a)
    return len(ga & _grams(b)) / len(ga) if ga else 0.0


def screen(eval_df, search_fn, k=10, min_level_ok=('easy', 'mid')):
    """
    평가셋 사전 검증 — 질의가 애초에 답이 나올 수 없는 것(코퍼스 밖 · 중복 문서 과다)을 걸러낸다.
    같은 검색기로 한 번 돌려 정답 문서가 top-k 에 전혀 없으면 '검증 실패'로 표시(제외 판단은 사용자 몫).
    """
    rows = []
    for g in eval_df.itertuples():
        res = search_fn(g.question, k)
        gold = {x for x in str(g.gold_doc_ids).split(';') if x}
        got = set(res['doc_id'].astype(str).head(k))
        rows.append(dict(qid=g.qid, found=bool(gold & got), rank=_first_rank(res, gold)))
    s = pd.DataFrame(rows)
    return eval_df.merge(s, on='qid')


def _first_rank(res, gold):
    for i, d in enumerate(res['doc_id'].astype(str), 1):
        if d in gold:
            return i
    return None


# ---------------- 기준(Threshold) ----------------
CRITERIA = [
 ('L1 known-item', 'Recall@5', '≥ 0.95', '원문 문장을 그대로 질의 → 못 찾으면 색인 · 토크나이저 · 청킹 결함'),
 ('L1 known-item', 'Recall@1', '≥ 0.80', '1순위 정확도. 0.6 미만이면 결합 가중 · 리랭크 재조정'),
 ('L1b 제목 질의', 'Recall@5', '≥ 0.90', '제목 = 대표 표현. 미달 시 헤더 부착(S03-3) 효과 확인'),
 ('L1c 중복쌍', 'Recall@10(양쪽)', '≥ 0.70', '표현이 다른 같은 내용 회수 = 의미 검색 동작 확인'),
 ('L2 합성 QA', 'Recall@5', '≥ 0.80', '표현 변형 질의. L1 대비 하락 폭이 크면 dense · sparse 균형 문제'),
 ('L2 합성 QA', 'MRR', '≥ 0.60', '상위 노출 안정성'),
 ('공통', '소스별 편차', '최저 소스 ≥ 전체 −0.15', '특정 소스만 낮으면 그 소스 파싱 · 청킹 문제'),
 ('공통', '난이도 easy − mid 차이', '≤ 0.15', '차이가 크면 고유명사에만 의존(어휘 검색 편중)'),
]


def summarize(detail, by=None):
    """평가 결과 요약 — 전체 · 그룹별 Recall@k · MRR."""
    cols = [c for c in detail.columns if c.startswith(('hit@', 'recall@', 'ndcg@')) or c == 'mrr']
    if by:
        return detail.groupby(by)[cols].mean().round(3)
    return detail[cols].mean().round(3)


def sample_size_note(n):
    """표본 수에 따른 오차 범위(95% 신뢰) — 해석 시 참고."""
    if n <= 0:
        return ''
    half = 1.96 * (0.25 / n) ** 0.5
    return f'n={n} → 95% 신뢰구간 ±{half * 100:.1f}%p'
