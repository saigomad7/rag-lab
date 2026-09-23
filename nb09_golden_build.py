# -*- coding: utf-8 -*-
"""
nb09 · 골든셋 구성 → 정량 평가 (골든_평가_팩 엑셀과 연계)
  [1] 자동 평가셋 생성 → [2] 검수 시트 내보내기 → (엑셀에서 검수) → [3] 골든셋 확정
  [4] 골든셋으로 측정 → [5] 실행 기록 행 생성 → [6] 문항별 결과 내보내기
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
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 60)
print('LAB_MODE =', C.LAB_MODE)

# %% [1] 자동 평가셋 생성 (nb08 과 동일 · 규모만 조정)
N_KNOWN, N_TITLE, N_SYN = 200, 100, 50
docs = lab_io.load_raw(n=None if C.IS_SAMPLE else 2000)
chunks = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000).dropna(subset=['text']).reset_index(drop=True)
sets = {'known-item': lab_autoeval.make_known_item(chunks, n=N_KNOWN),
        '제목': lab_autoeval.make_title_query(docs, n=N_TITLE)}
if not C.IS_SAMPLE and C.LLM_URL:
    sets['합성'] = lab_autoeval.make_synthetic(chunks, n=N_SYN)
print({k: len(v) for k, v in sets.items()})

# %% [2] 검수 시트 내보내기 → 엑셀 `1_골든셋_검수` 에 붙여넣기
review = lab_autoeval.to_review(sets)
review_path = lab_io.save(review, 'nb09_review_sheet')
print(review.head(5).to_string(index=False))
print('\n→ 위 파일을 열어 골든_평가_팩의 1_골든셋_검수 A5 부터 붙여넣기 → G~L 열 기입')

# %% [3] 검수 완료분 → 골든셋 확정 (golden/golden_v1.csv)
REVIEWED = review_path.replace('.csv', '.xlsx')      # ← 검수 완료 파일 경로로 교체
if os.path.exists(REVIEWED):
    reviewed = lab_io.read_table(REVIEWED)
    golden = lab_autoeval.from_review(reviewed)
    if len(golden):
        golden.to_csv(os.path.join(C.GOLDEN_DIR, 'golden_v1.csv'), index=False, encoding='utf-8-sig')
        print('골든셋 확정', len(golden), '문항 → golden/golden_v1.csv')
    else:
        print('채택 문항 없음 — 검수 결과 열을 채운 뒤 다시 실행')
else:
    print('검수 파일 없음:', REVIEWED)

# %% [4] 골든셋으로 측정
RUN_ID, SETTING = 'RUN-001', '기준선(현행)'
golden = lab_io.read_table(os.path.join(C.GOLDEN_DIR, 'golden_v1.csv')) if os.path.exists(os.path.join(C.GOLDEN_DIR, 'golden_v1.csv')) else None
if golden is None or not len(golden):
    import lab_sample
    golden = lab_sample.golden() if C.IS_SAMPLE else pd.DataFrame()
    print('(골든셋 파일 없음 → 샘플 골든셋 사용)')
golden = golden.fillna('')
ret = lab_search.Retriever(chunks, bm25_tokenizer='kiwi')
search_fn = lambda q, mode, k: ret.search(q, mode, k=k, cand=50)
detail, summary = lab_eval.evaluate(search_fn, golden, ['hybrid+rerank+mmr'], k=10)
print(summary.to_string())

# %% [5] 실행 기록 한 행 → 엑셀 `3_평가_실행기록` 에 붙여넣기
rec = lab_autoeval.run_record(RUN_ID, summary.iloc[0].to_dict(), len(golden), SETTING,
                              chunk='고정 500', header='없음', tok='kiwi', rerank='bge-reranker-v2-m3', cand=50)
lab_io.save(rec, 'nb09_run_record')
print(rec.T.to_string())

# %% [6] 문항별 결과 → 엑셀 `6_문항별_결과` 에 붙여넣기
per_q = detail[~detail.no_answer_q][['qid', 'q_type', 'source', 'question', 'hit@5', 'first_hit_rank']].copy()
per_q.columns = ['qid', 'set', 'source', '질문', 'A hit@5', 'A 순위']
lab_io.save(per_q, 'nb09_per_question')
print(per_q.head(8).to_string(index=False))
print('\n→ 설정 변경 후 [4]~[6] 재실행 → B 회차 열에 붙여넣기 → 5_전후비교 · 6_문항별_결과 자동 판정')
