# -*- coding: utf-8 -*-
"""
nb03 · BM25 한국어 토크나이저 점검 — 체크리스트 S09-2 · S09-4
"하이닉스의 / 하이닉스는" 이 같은 토큰으로 색인되는지, 토크나이저를 바꾸면 검색이 얼마나 달라지는지.
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
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 80)
S = lab_search

# %% [1] 토크나이저 비교 — 같은 단어가 같은 토큰이 되는가
SENTENCES = ['하이닉스의 HBM 점유율은 55%다', '하이닉스는 HBM4 12단을 양산한다', 'SK하이닉스가 eSSD 수요를 전망했다',
             'DRAM 계약가격이 3분기에 8% 상승했다']
TOKENIZERS = ['space', 'josa', 'kiwi']
tok_cmp = pd.DataFrame({name: [' / '.join(S.get_tokenizer(name)(s)) for s in SENTENCES] for name in TOKENIZERS}, index=SENTENCES)
print(tok_cmp.to_string())
print('\n"하이닉스의"·"하이닉스는"이 space 에서는 서로 다른 토큰 → 현행 BM25가 공백 분리라면 S09-2 = 개선 필요')

# %% [2] 코퍼스 + 골든셋 — live 에서는 청크 표본으로 (전체 BM25 는 기존 시스템에서)
CORPUS_N = 50000                       # live: 불러올 청크 수 (메모리에 맞게)
corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else CORPUS_N).dropna(subset=['text']).reset_index(drop=True)
golden = lab_io.read_table(os.path.join(C.GOLDEN_DIR, 'golden_v1.csv')) if not C.IS_SAMPLE else lab_io.sample_mod().golden()
golden = golden.fillna('')
print('코퍼스', len(corpus), '청크 · 골든셋', len(golden), '문항')
if not C.IS_SAMPLE:
    print('주의: 표본 코퍼스에 정답 문서가 없으면 적중이 0 → 골든셋 정답 문서의 청크를 코퍼스에 포함시킬 것 (아래 셀)')

# %% [2-1] (live) 골든셋 정답 문서의 청크를 코퍼스에 합치기
if not C.IS_SAMPLE:
    _gold_ids = sorted({x for s in golden.gold_doc_ids for x in str(s).split(';') if x})
    corpus = pd.concat([corpus, lab_io.load_chunks(doc_ids=_gold_ids)]).drop_duplicates('chunk_id').reset_index(drop=True)
    print('정답 문서 청크 포함 후', len(corpus))

# %% [3] 토크나이저별 BM25 적중률 — Hit@1 · Hit@5 · MRR
bm25_models = {name: S.BM25(S.get_tokenizer(name)).fit(corpus['text'].tolist()) for name in TOKENIZERS}
rows = []
for name, bm in bm25_models.items():
    for g in golden[golden.gold_doc_ids != ''].itertuples():
        res = S.Retriever._rank(corpus.iloc[[i for i, _ in bm.search(g.question, 10)]][['chunk_id', 'doc_id', 'text']])
        rel = lab_eval.judge(res, g.gold_doc_ids, g.gold_text)
        m = lab_eval.metrics(rel, res, g.gold_doc_ids)
        rows.append(dict(tokenizer=name, qid=g.qid, q_type=g.q_type, **{k: m[k] for k in ('hit@1', 'hit@5', 'mrr')}))
bm25_detail = pd.DataFrame(rows)
bm25_cmp = bm25_detail.groupby('tokenizer', sort=False)[['hit@1', 'hit@5', 'mrr']].mean().round(3)
print(bm25_cmp.to_string())

# %% [4] 질의 하나 드릴다운 — QUERY 만 바꿔서 반복
QUERY = '하이닉스의 HBM 점유율 추정치는?'
drill = pd.concat({name: corpus.iloc[[i for i, _ in bm.search(QUERY, 5)]][['doc_id', 'text']].reset_index(drop=True)
                   for name, bm in bm25_models.items()}, axis=1)
print(drill.to_string())

# %% [5] 저장
lab_io.save(tok_cmp.reset_index().rename(columns={'index': 'sentence'}), 'nb03_tokenizer_cmp')
lab_io.save(bm25_cmp.reset_index(), 'nb03_bm25_cmp')
