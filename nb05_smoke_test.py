# -*- coding: utf-8 -*-
"""
nb05 · 스모크 테스트 20문항
1) 질문 20개를 '지금 시스템'에 넣고 상위 10개 청크 + 답변을 엑셀로 뽑는다
2) 사람이 엑셀의 판정 칸(검색판정 · 답변판정 · 실패유형)을 채운다
3) 채운 파일을 읽어 실패 유형을 집계한다

체크리스트: docs/rag_checklist_rev10.xlsx → [P1_검색] S07 질의 입력 · [스모크20] 시트
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

# %% [1] 질문 20개
smoke_q = lab_io.read_table(os.path.join(C.GOLDEN_DIR, 'smoke20.csv'))
print(smoke_q[['no', 'q_type', 'question']].to_string(index=False))

# %% [2] 검색 방법 선택 — 'api' = 기존 사내 검색 API 그대로(권장) / 'lab' = 이 랩의 검색기
HOW = 'api' if (C.SEARCH_API_URL and not C.IS_SAMPLE) else 'lab'
if HOW == 'api':
    _answers = {}
    def search_fn(q, k=10):
        res, ans = lab_search.api_search(q, k)
        _answers[q] = ans
        return res
    def answer_fn(q, res):
        return _answers.get(q) or lab_search.llm_answer(q, res)
else:
    corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000)
    ret = lab_search.Retriever(corpus)
    _meta = lab_io.load_raw().set_index('doc_id') if C.IS_SAMPLE else None
    def search_fn(q, k=10):
        return ret.search(q, 'hybrid+rerank+mmr', k=k)
    def answer_fn(q, res):
        return lab_search.llm_answer(q, res, _meta)
print('검색 방법:', HOW)

# %% [3] 실행 → 판정용 엑셀 생성 (질문당 10행, 1행에 답변과 판정 칸)
smoke_tbl = lab_eval.smoke_template(smoke_q, search_fn, answer_fn, k=10)
smoke_path = lab_io.save(smoke_tbl, 'nb05_smoke_to_judge')
print(smoke_tbl[smoke_tbl['rank'] == 1][['no', 'question', 'doc_id', 'answer']].to_string(index=False))
print('\n→ 저장된 xlsx 를 열어 rank=1 행의 검색판정 · 답변판정 · 실패유형 칸을 채운다')
print('   검색판정: 적중 / 순위 낮음 / 누락   답변판정: 정답 / 부분 / 오답 / 자료 없음')
print('   실패유형: 정상 / ①검색 누락 / ②엉뚱한 청크 / ③파싱 깨짐 / ④답변 환각 / ⑤권한 노출')

# %% [4] 판정한 파일 읽어서 집계 — JUDGED 경로만 바꾼다
JUDGED = smoke_path.replace('.csv', '.xlsx')          # ← 판정을 채운 파일 경로
smoke_judged = lab_io.read_table(JUDGED)
smoke_result = lab_eval.smoke_summary(smoke_judged)
fail_counts, search_counts, answer_counts = smoke_result['실패유형'], smoke_result['검색판정'], smoke_result['답변판정']
print(fail_counts.to_string(index=False)); print(search_counts.to_string(index=False)); print(answer_counts.to_string(index=False))
print('\n가장 많은 실패 유형 → 체크리스트에서 먼저 볼 단계:  ①→S08·S09·S03  ②→S05·S11·S12  ③→S02·S03  ④→S13·S14  ⑤→S05·S10')
