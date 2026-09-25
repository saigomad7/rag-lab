# -*- coding: utf-8 -*-
"""
nb08 · 골든셋 없이 정량 평가 — 사내 DB 만으로 평가셋 자동 생성 · 기준 대비 판정
  [1] L1 known-item (원문 문장 → 그 문서가 정답)   [2] L1b 제목 질의   [3] L1c 중복쌍
  [4] L2 합성 QA (사내 LLM 질문 생성 + 자동 필터)   [5] 측정   [6] 기준 대비 판정   [7] 저장
사람 라벨 0건으로 시작 → 실패 문항만 눈으로 확인 → 그 문항이 곧 수동 골든셋 후보

체크리스트: docs/rag_checklist_rev10.xlsx → [P1_검색] S15 평가
"""
# %% [0] 준비 — 가장 먼저 실행
import os, sys, importlib
try:
    LAB = os.path.dirname(os.path.abspath(__file__))
except NameError:
    LAB = r'C:\work\rag_lab'          # ← __file__ 이 없다고 나오면 이 폴더 경로를 직접 적는다
if LAB not in sys.path:
    sys.path.insert(0, LAB)
os.chdir(LAB)
import pandas as pd
import lab_config as C
importlib.reload(C)
import lab_io, lab_text, lab_search, lab_eval, lab_autoeval
for _m in (lab_io, lab_text, lab_search, lab_eval, lab_autoeval):
    importlib.reload(_m)
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 60)
print('LAB_MODE =', C.LAB_MODE)

# %% [1] 코퍼스 적재 + 검색기 구성
N_DOC, N_CHUNK = 2000, 50000            # live: 표본 크기 (메모리 · 시간에 맞게)
docs = lab_io.load_raw(n=None if C.IS_SAMPLE else N_DOC)
chunks = lab_io.load_chunks(n=None if C.IS_SAMPLE else N_CHUNK).dropna(subset=['text']).reset_index(drop=True)
ret = lab_search.Retriever(chunks, bm25_tokenizer='kiwi')
search_fn = lambda q, k=10: ret.search(q, 'hybrid+rerank+mmr', k=k, cand=50)
print('문서', len(docs), '· 청크', len(chunks))

# %% [2] L1 known-item — 원문 문장을 질의로 (라벨 작업 0건)
N_KNOWN = 200
eval_known = lab_autoeval.make_known_item(chunks, n=N_KNOWN)
print(eval_known[['qid', 'level', 'gold_doc_ids', 'question']].head(8).to_string(index=False))
print('생성', len(eval_known), '문항 ·', lab_autoeval.sample_size_note(len(eval_known)))

# %% [3] L1b 제목 질의 + L1c 중복쌍
eval_title = lab_autoeval.make_title_query(docs, n=100)
eval_dup = lab_autoeval.make_dup_pair(docs, 'body', threshold=0.8, n=50)
print('제목 질의', len(eval_title), '· 중복쌍', len(eval_dup))
print(eval_dup.head(3).to_string(index=False) if len(eval_dup) else '(중복쌍 없음 — 재송고 · 인용 중복이 적다는 뜻)')

# %% [4] L2 합성 QA — 사내 LLM 이 질문 생성 (live 에서 LLM_URL 필요)
N_SYN = 50
if not C.USE_LLM:
    _mock = lambda p: '이 문서에서 제시한 핵심 수치는?'
    eval_syn = lab_autoeval.make_synthetic(chunks, n=min(N_SYN, 20), llm=_mock)
    print('(샘플 모드: 고정 문구로 대체 — live 에서 사내 LLM 사용)')
else:
    eval_syn = lab_autoeval.make_synthetic(chunks, n=N_SYN)
print('합성', len(eval_syn), '문항')
print(eval_syn[['qid', 'gold_doc_ids', 'question']].head(5).to_string(index=False))

# %% [5] 측정 — 세트별 Recall@k · MRR
def run(eval_df, name, k=10):
    rows = []
    for g in eval_df.itertuples():
        res = search_fn(g.question, k)
        rel = lab_eval.judge(res, g.gold_doc_ids, getattr(g, 'gold_text', '') or '', th=0.5)
        m = lab_eval.metrics(rel, res, g.gold_doc_ids)
        rows.append(dict(set=name, qid=g.qid, level=getattr(g, 'level', ''), q_type=g.q_type,
                         gold=g.gold_doc_ids, question=g.question[:60], **m))
    return pd.DataFrame(rows)

parts = [run(eval_known, 'L1 known-item'), run(eval_title, 'L1b 제목')]
if len(eval_dup):
    parts.append(run(eval_dup, 'L1c 중복쌍'))
if len(eval_syn):
    parts.append(run(eval_syn, 'L2 합성'))
detail = pd.concat(parts, ignore_index=True)
by_set = detail.groupby('set')[['recall@1', 'recall@5', 'recall@10', 'mrr']].mean().round(3)
by_level = detail.groupby(['set', 'level'])[['recall@5']].mean().round(3)
print(by_set.to_string()); print(); print(by_level.to_string())

# %% [6] 기준 대비 판정 — CRITERIA 와 비교
crit = pd.DataFrame(lab_autoeval.CRITERIA, columns=['세트', '지표', '기준', '해석'])
got = {
 ('L1 known-item', 'Recall@5'): by_set.loc['L1 known-item', 'recall@5'] if 'L1 known-item' in by_set.index else None,
 ('L1 known-item', 'Recall@1'): by_set.loc['L1 known-item', 'recall@1'] if 'L1 known-item' in by_set.index else None,
 ('L1b 제목 질의', 'Recall@5'): by_set.loc['L1b 제목', 'recall@5'] if 'L1b 제목' in by_set.index else None,
 ('L1c 중복쌍', 'Recall@10(양쪽)'): by_set.loc['L1c 중복쌍', 'recall@10'] if 'L1c 중복쌍' in by_set.index else None,
 ('L2 합성 QA', 'Recall@5'): by_set.loc['L2 합성', 'recall@5'] if 'L2 합성' in by_set.index else None,
 ('L2 합성 QA', 'MRR'): by_set.loc['L2 합성', 'mrr'] if 'L2 합성' in by_set.index else None,
}
crit['측정'] = [got.get((r.세트, r.지표)) for r in crit.itertuples()]
def _judge(row):
    if row['측정'] is None or pd.isna(row['측정']):
        return '-'
    thr = row['기준'].replace('≥', '').replace('≤', '').strip()
    try:
        v = float(thr)
    except ValueError:
        return '-'
    return '충족' if row['측정'] >= v else '미달'
crit['판정'] = crit.apply(_judge, axis=1)
print(crit[['세트', '지표', '기준', '측정', '판정', '해석']].to_string(index=False))

# %% [7] 실패 문항 — 눈으로 볼 대상 (수동 골든셋 후보)
fails = detail[detail['recall@5'] == 0][['set', 'qid', 'level', 'gold', 'question']]
print('실패', len(fails), '문항 (상위 15)')
print(fails.head(15).to_string(index=False))

# %% [8] 저장 — 평가셋 · 결과 (평가셋은 골든셋 v1 의 씨앗으로 재사용)
for _df, _n in ((eval_known, 'nb08_set_known'), (eval_title, 'nb08_set_title'), (eval_dup, 'nb08_set_dup'),
                (eval_syn, 'nb08_set_syn'), (detail, 'nb08_detail'), (by_set.reset_index(), 'nb08_by_set'),
                (crit, 'nb08_criteria'), (fails, 'nb08_fails')):
    if len(_df):
        lab_io.save(_df, _n)
