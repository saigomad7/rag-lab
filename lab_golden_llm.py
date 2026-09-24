# -*- coding: utf-8 -*-
"""
LLM 기반 골든셋 생성 — 적재된 코퍼스에서 질의 · 응답 · 근거를 함께 만든다.

절차
  1) 표본 추출   : 소스 유형별 균형 표본 (편중 방지)
  2) 생성        : 청크 1개 → 질문 · 정답 · 근거 문장 · 유형 · 난이도 (JSON)
  3) 자가 검증   : 근거 문장이 원문에 실재 · 질문 복붙 아님 · 정답 회수 가능
  4) 답없음 문항 : 코퍼스에 없는 전제 → 거절 정확도 측정용
  5) 검수 시트   : 사람이 채택 / 수정 / 폐기 (이력 엑셀 `2_골든셋_검수`)

LLM 이 없으면(샘플 모드) 규칙 기반으로 같은 형식을 만들어 흐름을 확인할 수 있다.
"""
import json
import re

import numpy as np
import pandas as pd

import lab_config as C

Q_TYPES = ['사실', '수치', '기간', '비교', '종합']
LEVELS = ['easy', 'mid', 'hard']

GEN_PROMPT = """아래 [문서 조각]만 근거로 하여 평가용 질의 · 응답 1건을 만들어라.

규칙
- 질문: 조각의 구체 정보(수치 · 고유명사 · 날짜)를 묻는다. 조각 문장을 그대로 베끼지 않는다.
- 질문에 "이 문서", "위 자료" 같은 지시어를 쓰지 않는다. 문서를 몰라도 뜻이 통해야 한다.
- 정답: 조각에 적힌 내용만으로 작성한다. 추측 · 일반 상식 금지.
- 근거: 정답의 출처가 되는 조각 원문 문장을 그대로 1개 옮긴다.
- 유형: {types} 중 하나. 난이도: easy · mid · hard 중 하나.

출력: JSON 한 줄만. 설명 금지.
{{"question":"...","answer":"...","evidence":"...","q_type":"수치","level":"mid"}}

[문서 유형] {doc_type}
[문서 제목] {title}
[문서 조각]
{chunk}
"""

NOANS_PROMPT = """아래 [보유 주제 목록]을 보고, 이 자료들로는 **답할 수 없는** 질문 1개를 만들어라.
조건: 같은 업계 용어를 쓰되, 목록에 없는 대상 · 기간 · 지표를 묻는다. 질문 한 줄만 출력한다.

[보유 주제 목록]
{topics}
"""

_NUM = re.compile(r'\d[\d,\.]*\s*(?:%|원|달러|억|조|배|EB|TB|GB|bp|나노|단)')
_SENT = re.compile(r'(?<=[.!?])\s+|\n')


def _llm(prompt):
    import lab_search
    return lab_search.llm_answer(prompt, pd.DataFrame(columns=['text', 'doc_id']))


def _grams(t, n=3):
    t = re.sub(r'\s+', '', str(t or ''))
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def _cov(a, b):
    ga = _grams(a)
    return len(ga & _grams(b)) / len(ga) if ga else 0.0


# ---------------- 1) 표본 추출 ----------------
def sample_chunks(chunks, raw, per_type=10, min_len=150, seed=7):
    """소스 유형별 균형 표본 — 정보량 있는 청크 우선(수치 포함 · 길이)"""
    df = chunks.merge(raw[['doc_id', 'doc_type', 'title', 'published_at']], on='doc_id', how='left')
    df = df[df['text'].astype(str).str.len() >= min_len].copy()
    df['has_num'] = df['text'].astype(str).str.contains(_NUM)
    out = []
    for t, g in df.groupby('doc_type'):
        g = g.sort_values('has_num', ascending=False)
        take = min(per_type, len(g))
        out.append(pd.concat([g[g.has_num].head(take), g[~g.has_num].head(max(0, take - int(g.has_num.sum())))])
                   .head(take))
    return pd.concat(out).sample(frac=1, random_state=seed).reset_index(drop=True) if out else df.head(0)


# ---------------- 2) 생성 ----------------
def _parse(txt):
    m = re.search(r'\{.*\}', str(txt or ''), re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    return d if {'question', 'answer', 'evidence'} <= set(d) else None


def _rule_item(row):
    """LLM 없을 때 — 수치 문장을 골라 질문 형태로 변환 (형식 확인용)"""
    sents = [s.strip() for s in _SENT.split(str(row.text)) if len(s.strip()) > 25]
    ev = next((s for s in sents if _NUM.search(s)), sents[0] if sents else '')
    if not ev:
        return None
    subj = str(row.title or '')[:40] or C.DOC_TYPE_KO.get(row.doc_type, '')
    key = re.sub(r'[는은이가을를]\s*$', '', ' '.join(re.findall(r'[가-힣A-Za-z0-9]{2,}', ev)[:4]))
    return dict(question=f'{subj} 자료에서 {key} 관련 수치는?', answer=ev[:160], evidence=ev[:200],
                q_type='수치' if _NUM.search(ev) else '사실', level='mid')


def generate(sampled, n=60, llm=None, use_llm=None):
    """청크 표본 → 질의 · 응답 · 근거 생성"""
    use_llm = C.USE_LLM if use_llm is None else use_llm
    llm = llm or _llm
    rows, i = [], 0
    for r in sampled.itertuples():
        if len(rows) >= n:
            break
        i += 1
        d = None
        if use_llm:
            try:
                d = _parse(llm(GEN_PROMPT.format(types=' · '.join(Q_TYPES), doc_type=C.DOC_TYPE_KO.get(r.doc_type, r.doc_type),
                                                 title=str(r.title or '')[:80], chunk=str(r.text)[:1500])))
            except Exception:
                d = None
        if d is None:
            d = _rule_item(r)
        if d is None:
            continue
        rows.append(dict(qid=f'G{len(rows) + 1:04d}', question=str(d['question']).strip()[:200],
                         gold_answer=str(d['answer']).strip()[:400], gold_text=str(d['evidence']).strip()[:300],
                         q_type=d.get('q_type', '사실'), level=d.get('level', 'mid'),
                         gold_doc_ids=r.doc_id, src_chunk=r.chunk_id,
                         doc_type=C.DOC_TYPE_KO.get(r.doc_type, r.doc_type),
                         published_at=str(getattr(r, 'published_at', ''))[:10],
                         생성=('LLM' if use_llm else '규칙')))
    return pd.DataFrame(rows)


def make_unanswerable(raw, n=6, llm=None, use_llm=None, seed=7):
    """답없음 문항 — 코퍼스에 없는 전제 (거절 정확도 측정용)"""
    use_llm = C.USE_LLM if use_llm is None else use_llm
    llm = llm or _llm
    topics = '\n'.join('- ' + str(t)[:60] for t in raw['title'].dropna().sample(min(20, len(raw)), random_state=seed))
    rows = []
    if use_llm:
        for i in range(n):
            try:
                q = str(llm(NOANS_PROMPT.format(topics=topics))).strip().splitlines()[0]
            except Exception:
                continue
            if 8 <= len(q) <= 150:
                rows.append(q)
    base = ['보유 자료에 없는 기간의 월별 수치를 묻는 질문', '보유 자료에 없는 업체의 실적을 묻는 질문',
            '보유 자료에 없는 지표의 전망을 묻는 질문']
    while len(rows) < n:
        rows.append(f'{base[len(rows) % 3]} (변형 {len(rows) + 1})')
    return pd.DataFrame([dict(qid=f'N{i + 1:04d}', question=q, gold_answer='확인된 자료 없음', gold_text='',
                              q_type='답없음', level='mid', gold_doc_ids='', src_chunk='', doc_type='-',
                              published_at='', 생성=('LLM' if use_llm else '규칙'))
                         for i, q in enumerate(rows[:n])])


# ---------------- 3) 자가 검증 ----------------
CHECKS = ['근거 실재', '복붙 아님', '지시어 없음', '길이 적정', '중복 아님', '회수 가능']
_DEICTIC = re.compile(r'(이 문서|위 자료|본 자료|해당 문서|아래 표|위 표)')


def self_check(golden, chunks, retriever=None, k=5):
    """생성 결과 자가 검증 — 불합격 항목이 있으면 검수 우선 대상"""
    cmap = chunks.set_index('chunk_id')['text'].astype(str).to_dict() if 'chunk_id' in chunks else {}
    seen, out = set(), []
    for r in golden.itertuples():
        src = cmap.get(r.src_chunk, '')
        ev_ok = (_cov(r.gold_text, src) >= 0.8) if (r.gold_text and src) else (r.q_type == '답없음')
        copy_ok = _cov(r.question, src) <= 0.6
        deic_ok = not bool(_DEICTIC.search(str(r.question)))
        len_ok = 8 <= len(str(r.question)) <= 150
        key = re.sub(r'\W', '', str(r.question))[:40]
        dup_ok = key not in seen
        seen.add(key)
        rec_ok = np.nan
        if retriever is not None and r.q_type != '답없음':
            try:
                res = retriever.search(r.question, 'hybrid+rerank', k=k, cand=30)
                rec_ok = int(str(r.gold_doc_ids) in set(res['doc_id'].astype(str)))
            except Exception:
                rec_ok = np.nan
        flags = [ev_ok, copy_ok, deic_ok, len_ok, dup_ok]
        out.append(dict(qid=r.qid, 근거_실재=ev_ok, 복붙_아님=copy_ok, 지시어_없음=deic_ok,
                        길이_적정=len_ok, 중복_아님=dup_ok, 회수_가능=rec_ok,
                        자가검증=('통과' if all(flags) and (rec_ok != 0) else '보류'),
                        사유=' · '.join(n for n, f in zip(CHECKS[:5], flags) if not f) or
                            ('정답 문서 미회수' if rec_ok == 0 else '')))
    return pd.DataFrame(out)


def apply_check(golden, checked):
    """자가 검증 결과 결합 — 통과분이 검수 1순위"""
    g = golden.merge(checked[['qid', '자가검증', '사유', '회수_가능']], on='qid', how='left')
    return g.sort_values(['자가검증', 'q_type']).reset_index(drop=True)


# ---------------- 4) 배분 · 검수 시트 ----------------
TARGET_MIX = {'사실': 0.30, '수치': 0.25, '종합': 0.15, '기간': 0.10, '비교': 0.10, '답없음': 0.10}


def mix_report(golden, target=None):
    """유형 배분 점검 — 한쪽으로 몰리면 지표가 왜곡된다"""
    target = target or TARGET_MIX
    n = len(golden)
    cnt = golden['q_type'].value_counts()
    rows = []
    for t in list(target):
        tgt, act = target.get(t, 0) * n, int(cnt.get(t, 0))
        rows.append(dict(유형=t, 목표=round(tgt), 실제=act, 비중=round(act / n, 3) if n else 0,
                         판정=('부족' if act < tgt * 0.6 else ('과다' if act > tgt * 1.5 else '적정'))))
    return pd.DataFrame(rows)


REVIEW_COLS = ['qid', 'q_type', 'level', '소스', '문서일자', '질문', '정답(생성)', '근거 문장', 'gold_doc_ids',
               '자가검증', '사유', '검수 결과', '수정 질문', '수정 정답', '폐기 사유', '검수자']


def to_review(golden):
    """검수 시트 형태로 — 이력 엑셀 `2_골든셋_검수` 에 붙여넣기"""
    d = pd.DataFrame(columns=REVIEW_COLS)
    d['qid'] = golden['qid']
    for a, b in [('q_type', 'q_type'), ('level', 'level'), ('소스', 'doc_type'), ('문서일자', 'published_at'),
                 ('질문', 'question'), ('정답(생성)', 'gold_answer'), ('근거 문장', 'gold_text'),
                 ('gold_doc_ids', 'gold_doc_ids'), ('자가검증', '자가검증'), ('사유', '사유')]:
        if b in golden:
            d[a] = golden[b].values
    return d


def finalize(reviewed):
    """검수 완료 → 골든셋 확정 (채택 · 수정 후 채택만)"""
    d = reviewed.fillna('')
    ok = d[d['검수 결과'].isin(['채택', '수정 후 채택'])].copy()
    q = np.where(ok['수정 질문'].astype(str).str.strip() != '', ok['수정 질문'], ok['질문'])
    a = np.where(ok['수정 정답'].astype(str).str.strip() != '', ok['수정 정답'], ok['정답(생성)'])
    return pd.DataFrame(dict(qid=ok['qid'], question=q, q_type=ok['q_type'], level=ok['level'],
                             gold_doc_ids=ok['gold_doc_ids'], gold_text=ok['근거 문장'], gold_answer=a,
                             must_include='', source_hint=ok['소스'])).reset_index(drop=True)
