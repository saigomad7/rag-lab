# -*- coding: utf-8 -*-
"""
nb06 · 검색 평가 · 단계별 비교(ablation) — 체크리스트 S15 · S09-4 · S11 (RRF · MMR) · S12 (리랭크)
골든셋(문서 ID + 정답 문장)으로 BM25 / Dense / Sparse / Hybrid(RRF) / +Rerank / +MMR 을 같은 기준으로 잰다.
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
import lab_io, lab_text, lab_search, lab_eval
for _m in (lab_io, lab_text, lab_search, lab_eval):
    importlib.reload(_m)
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 60)

# %% [1] 골든셋 — golden/golden_v1.csv (qid, question, q_type, source, gold_doc_ids, gold_text)
if C.IS_SAMPLE:
    golden = lab_io.sample_mod().golden()
else:
    golden = lab_io.read_table(os.path.join(C.GOLDEN_DIR, 'golden_v1.csv'))
golden = golden.fillna('')
print(len(golden), '문항 ·', golden.q_type.value_counts().to_dict())

# %% [2] 검색기 구성 — PARTS 로 켤 검색기 선택, BM25_TOK 로 토크나이저 선택
PARTS = ('bm25', 'dense', 'sparse')     # live 에서 sparse 필드가 없으면 ('bm25', 'dense')
BM25_TOK = 'kiwi'                       # space | josa | kiwi
CORPUS_N = 50000
corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else CORPUS_N)
if not C.IS_SAMPLE:                      # 정답 문서 청크는 반드시 포함
    _gold_ids = sorted({x for s in golden.gold_doc_ids for x in str(s).split(';') if x})
    corpus = pd.concat([corpus, lab_io.load_chunks(doc_ids=_gold_ids)]).drop_duplicates('chunk_id')
corpus = corpus.dropna(subset=['text']).reset_index(drop=True)
ret = lab_search.Retriever(corpus, bm25_tokenizer=BM25_TOK, parts=PARTS)
print('코퍼스', len(corpus), '청크 · 검색기', PARTS, '· BM25 토크나이저', BM25_TOK)

# %% [3] 단계별 비교 — 같은 골든셋, 같은 지표
MODES = ['bm25', 'dense', 'sparse', 'hybrid', 'hybrid+rerank', 'hybrid+rerank+mmr']
MODES = [m for m in MODES if m not in ('bm25', 'dense', 'sparse') or m in PARTS]
search_fn = lambda q, mode, k: ret.search(q, mode, k=k, cand=50, lam=0.7)
detail, summary = lab_eval.evaluate(search_fn, golden, MODES, k=10)
print(summary.to_string())

# %% [4] 어디서 약한가 — 질문 유형별 · 소스별 Hit@5
by_type = lab_eval.breakdown(detail, 'q_type', 'hit@5')
by_source = lab_eval.breakdown(detail, 'source', 'hit@5')
print(by_type.to_string()); print(); print(by_source.to_string())

# %% [5] RRF k · MMR λ 스윕 (S11-2 · S11-3)
sweep_rows = []
for rrf_k in (20, 60):
    for lam in (0.5, 0.7, 1.0):
        fn = lambda q, mode, k, _r=rrf_k, _l=lam: ret.search(q, 'hybrid+rerank+mmr', k=k, lam=_l, rrf_k=_r)
        _, s = lab_eval.evaluate(fn, golden, ['hybrid+rerank+mmr'], k=10, verbose=False)
        sweep_rows.append(dict(rrf_k=rrf_k, mmr_lambda=lam, **s.iloc[0].to_dict()))
sweep = pd.DataFrame(sweep_rows)
print(sweep[['rrf_k', 'mmr_lambda', 'hit@1', 'hit@5', 'mrr', 'ndcg@10']].to_string(index=False))

# %% [6] 틀린 문항 보기 — MODE 만 바꿔서
MODE = 'hybrid+rerank+mmr'
failures = detail[(detail['mode'] == MODE) & (~detail.no_answer_q) & (detail['hit@5'] == 0)][['qid', 'q_type', 'source', 'question', 'top1_doc', 'top1_text']]
failures = failures.merge(golden[['qid', 'gold_doc_ids', 'gold_text']], on='qid')
print(failures.to_string(index=False))

# %% [7] 질문 하나 드릴다운 — 단계별 상위 5개 나란히
QID = golden.qid.iloc[0]
_q = golden.set_index('qid').loc[QID, 'question']
drill = pd.concat({m: ret.search(_q, m, k=5)[['doc_id', 'text']] for m in MODES}, axis=1)
print(_q); print(drill.to_string())

# %% [8] 저장 (실험 기록 — 날짜 · 설정과 함께)
summary_out = summary.reset_index().assign(parts='+'.join(PARTS), bm25_tok=BM25_TOK, corpus=len(corpus), golden=len(golden), mode_env=C.LAB_MODE)
lab_io.save(summary_out, 'nb06_summary'); lab_io.save(detail, 'nb06_detail'); lab_io.save(sweep, 'nb06_sweep')
