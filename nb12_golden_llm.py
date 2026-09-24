# -*- coding: utf-8 -*-
"""
nb12 · LLM 기반 골든셋 생성 — 적재된 코퍼스에서 질의 · 응답 · 근거를 함께 만든다
  [1] 유형별 균형 표본  [2] 생성  [3] 자가 검증  [4] 답없음 문항  [5] 배분 점검
  [6] 검수 시트 저장 → 사람 검수 → [7] 확정 골든셋
  Variable Explorer 확인 대상: sampled · gen · chk · gold · review · mix
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
import lab_io, lab_search, lab_golden_llm
for _m in (lab_io, lab_search, lab_golden_llm):
    importlib.reload(_m)
pd.set_option('display.width', 240); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 44)
USE_LLM = C.USE_LLM
print('LAB_MODE =', C.LAB_MODE, '| 생성 방식 =', 'LLM' if USE_LLM else '규칙(샘플 · 형식 확인용)')
print('선행 조건: nb00 파이프라인 점검 통과 — 적재 · 청킹된 문서에서만 골든셋 생성 가능')

# %% [1] 표본 추출 — 소스 유형별 균형 (수치 포함 청크 우선)
raw = lab_io.load_raw()
chunks = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000).dropna(subset=['text'])
sampled = lab_golden_llm.sample_chunks(chunks, raw, per_type=10, min_len=120)
print(f'표본 {len(sampled)} 청크')
print(sampled.groupby('doc_type').size().to_string())

# %% [2] 생성 — 청크 → 질문 · 정답 · 근거 문장 (JSON)
N = 60
gen = lab_golden_llm.generate(sampled, n=N, use_llm=USE_LLM)
print(f'생성 {len(gen)} 건')
print(gen.head(5)[['qid', 'doc_type', 'q_type', 'question', 'gold_text']].to_string(index=False))

# %% [3] 자가 검증 — 근거 실재 · 복붙 · 지시어 · 회수 가능 여부
ret = lab_search.Retriever(chunks.reset_index(drop=True), bm25_tokenizer='kiwi')
chk = lab_golden_llm.self_check(gen, chunks, retriever=ret)
print(chk.groupby('자가검증').size().to_string())
print('\n보류 사유:')
print(chk[chk.자가검증 == '보류'][['qid', '사유']].head(10).to_string(index=False) or '(없음)')
gen = lab_golden_llm.apply_check(gen, chk)

# %% [4] 답없음 문항 추가 — 거절 정확도 측정용
noans = lab_golden_llm.make_unanswerable(raw, n=max(4, N // 10), use_llm=USE_LLM)
gold = pd.concat([gen, noans], ignore_index=True)
print(f'총 {len(gold)} 문항 (답없음 {len(noans)} 포함)')

# %% [5] 유형 배분 점검 — 한쪽 쏠림이면 지표가 왜곡된다
mix = lab_golden_llm.mix_report(gold)
print(mix.to_string(index=False))

# %% [6] 검수 시트 저장 → 이력 엑셀 `2_골든셋_검수` 에 붙여넣기
review = lab_golden_llm.to_review(gold)
lab_io.save(review, 'nb12_golden_review')
print('검수 규칙: 자가검증 "통과" 부터 확인 · 질문만 보고 답할 수 있는지 · 정답이 근거 문장에서 나오는지')
print('검수 결과 열: 채택 / 수정 후 채택 / 폐기')

# %% [7] 검수 완료 파일 → 확정 골든셋
REVIEWED = ''                     # 예: r'C:\work\rag_lab\out\nb12_golden_review_260924_101500.xlsx'
if REVIEWED and os.path.exists(REVIEWED):
    final = lab_golden_llm.finalize(lab_io.read_table(REVIEWED))
    final.to_csv(os.path.join(C.GOLDEN_DIR, 'golden_llm_v1.csv'), index=False, encoding='utf-8-sig')
    print(f'확정 {len(final)} 문항 → golden/golden_llm_v1.csv')
    print(final.groupby('q_type').size().to_string())
else:
    print('검수 파일 경로(REVIEWED)를 채우고 이 셀만 다시 실행')
    final = pd.DataFrame()

# %% [8] 다음 단계
print('nb06 검색 지표 · nb10 답변 지표 · nb13 프리셋 비교에서 golden_llm_v1.csv 사용')
