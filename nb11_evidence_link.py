# -*- coding: utf-8 -*-
"""
nb11 · 질문 ↔ 근거 문서 연결 — 질문 은행을 골든셋으로 바꾸는 단계
  질문만 있는 상태에서는 "검색 실패"와 "문서 부재"가 구분되지 않는다.
  [1] 질문 은행 적재 → [2] 코퍼스에서 근거 후보 검색 → [3] 사람이 근거 확정(엑셀)
  [4] 확정분 → 골든셋 생성 · 근거 확보율 산출 → [5] 미확보 = 수집 공백 목록
"""
# %% [0] 준비 — 가장 먼저 실행
import os, sys, importlib
try:
    LAB = os.path.dirname(os.path.abspath(__file__))
except NameError:
    LAB = r'C:\work\rag_lab'
if LAB not in sys.path:
    sys.path.insert(0, LAB)
os.chdir(LAB)
import pandas as pd
import lab_config as C
importlib.reload(C)
import lab_io, lab_search, lab_eval, lab_autoeval
for _m in (lab_io, lab_search, lab_eval, lab_autoeval):
    importlib.reload(_m)
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 50)
print('LAB_MODE =', C.LAB_MODE)

# %% [1] 질문 은행 — 사외 정보 기반 60문항 (근거 문서 미연결 상태)
bank = lab_io.read_table(os.path.join(C.GOLDEN_DIR, 'answer_golden_v1.csv')).fillna('')
print(len(bank), '문항 · 근거 문서 연결 전')
print(bank.head(3)[['qid', 'question', 'q_type']].to_string(index=False))

# %% [2] 코퍼스에서 근거 후보 검색 — 질문당 상위 K 후보
K = 5
corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000).dropna(subset=['text']).reset_index(drop=True)
meta = lab_io.load_raw().set_index('doc_id')
ret = lab_search.Retriever(corpus, bm25_tokenizer='kiwi')
search_fn = lambda q, k=K: ret.search(q, 'hybrid+rerank+mmr', k=k, cand=50)
linked = lab_autoeval.link_evidence(bank.head(60), search_fn, k=K, meta=meta)
link_path = lab_io.save(linked, 'nb11_evidence_link')
print(linked.head(8)[['qid', 'cand_rank', 'cand_doc_id', 'cand_doc_type', 'score', 'cand_text']].to_string(index=False))
print('\n→ 저장 파일의 "근거 판정" 열 기입: 근거 확보 / 문서 없음 / 보류')
print('   근거 확보 시 확정 doc_id · 확정 정답 문장 입력 (후보 텍스트에서 복사)')

# %% [3] 확정 파일 읽기 → 골든셋 · 근거 확보율
LINKED = link_path.replace('.csv', '.xlsx')       # ← 판정 완료 파일 경로
if os.path.exists(LINKED):
    done = lab_io.read_table(LINKED)
    golden, coverage = lab_autoeval.apply_evidence(done, bank)
    rep = lab_autoeval.coverage_report(coverage)
    print(rep.to_string(index=False))
    print(coverage.groupby(['q_type', '근거 상태']).size().unstack(fill_value=0).to_string())
    if len(golden):
        golden.to_csv(os.path.join(C.GOLDEN_DIR, 'golden_from_bank.csv'), index=False, encoding='utf-8-sig')
        print('골든셋', len(golden), '문항 → golden/golden_from_bank.csv')
else:
    print('판정 파일 없음:', LINKED)
    golden, coverage, rep = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# %% [4] 수집 공백 목록 — 문서 없음 문항 (검색 성능과 무관)
if len(coverage):
    gap = coverage[coverage['근거 상태'] == '문서 없음'].merge(bank[['qid', 'question', 'source_hint']], on='qid', how='left')
    lab_io.save(gap, 'nb11_source_gap')
    print('수집 공백', len(gap), '문항 — 해당 소스 수집 범위 확대 검토')
    print(gap.head(10)[['qid', 'q_type', 'source_hint', 'question']].to_string(index=False))

# %% [5] 평가 — 근거 확보 문항만 대상
if len(golden):
    detail, summary = lab_eval.evaluate(lambda q, mode, k: ret.search(q, mode, k=k, cand=50),
                                        golden.fillna(''), ['hybrid+rerank+mmr'], k=10)
    print(summary.to_string())
    print('\n해석: 근거 확보 문항만 측정 · 문서 없음 문항은 수집 과제로 분리 (검색 점수에 포함 금지)')
    lab_io.save(detail, 'nb11_detail')
