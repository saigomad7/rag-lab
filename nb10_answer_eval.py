# -*- coding: utf-8 -*-
"""
nb10 · 답변 품질 정량 평가 — 표준 지표(RAGAS 계열) + 검색 지표
  [1] 질의·답변 골든셋 60문항 적재  [2] 검색 → 컨텍스트 → 답변 생성  [3] auto 지표 계산
  [4] LLM 채점(judge)  [5] 지표 요약 · 합격 판정  [6] 저장 (골든_평가_팩 붙여넣기용)
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
import lab_io, lab_search, lab_eval, lab_ragas
for _m in (lab_io, lab_search, lab_eval, lab_ragas):
    importlib.reload(_m)
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 50)
print('LAB_MODE =', C.LAB_MODE, '| LLM =', '설정됨' if C.LLM_URL else '없음(구조 지표만)')

# %% [1] 질의 · 답변 골든셋 (60문항 · 사외 정보 기반)
# 선행 조건: 질문의 근거 문서가 코퍼스에 적재 · 파싱 · 청킹된 상태여야 측정 성립
#   근거 미연결 상태의 60문항 = 질문 은행 → nb11_evidence_link 로 근거 확정 후 golden_from_bank.csv 사용 권장
_linked = os.path.join(C.GOLDEN_DIR, 'golden_from_bank.csv')
SRC = _linked if os.path.exists(_linked) else os.path.join(C.GOLDEN_DIR, 'answer_golden_v1.csv')
gold = lab_io.read_table(SRC).fillna('')
print('골든셋 소스 =', os.path.basename(SRC), '(질문 은행 상태면 근거 미확보 문항이 섞여 점수 과소평가)')
print(len(gold), '문항 ·', gold.q_type.value_counts().to_dict())
print(gold.head(3)[['qid', 'question', 'must_include']].to_string(index=False))

# %% [2] 지표 카탈로그 — 무엇을 어떻게 재는가
catalog = lab_ragas.catalog()
print(catalog.to_string(index=False))

# %% [3] 검색 → 컨텍스트 → 답변 생성
N_EVAL, K = 20, 6                       # live: 60 전체 권장
corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000).dropna(subset=['text']).reset_index(drop=True)
ret = lab_search.Retriever(corpus, bm25_tokenizer='kiwi')
meta = lab_io.load_raw().set_index('doc_id')
rows = []
for g in gold.head(N_EVAL).itertuples():
    res = ret.search(g.question, 'hybrid+rerank+mmr', k=K, cand=50)
    ctx = res['text'].astype(str).tolist()
    ans = lab_search.llm_answer(g.question, res, meta, n=K)
    rows.append(dict(qid=g.qid, question=g.question, q_type=g.q_type, answer=ans, contexts=ctx,
                     must_include=g.must_include, gold_text='', is_no_answer=(g.q_type == '답없음'),
                     top_docs=';'.join(res['doc_id'].astype(str).head(3))))
print('평가 대상', len(rows), '문항 · 컨텍스트', K, '개씩')
print(pd.DataFrame(rows)[['qid', 'q_type', 'top_docs']].head(8).to_string(index=False))

# %% [4] auto 지표 — 규칙 · 임베딩 (LLM 없이 계산)
emb = lab_search.Embedder()
auto = lab_ragas.evaluate_answers(rows, embedder=emb)
num = ['faithfulness', 'answer_relevancy', 'answer_correctness', 'citation_accuracy', 'context_recall', 'refusal_ok']
print(auto[['qid', 'q_type'] + num].round(3).to_string(index=False))

# %% [5] LLM 채점(judge) — live + LLM_URL 일 때만
if C.USE_LLM:
    jr = []
    for r in rows:
        p = lab_ragas.judge_prompt(r['question'], r['answer'], r['contexts'], r['must_include'])
        jr.append(dict(qid=r['qid'], **lab_ragas.parse_judge(lab_search.llm_answer(p, pd.DataFrame(columns=['text', 'doc_id'])))))
    judge = pd.DataFrame(jr)
    print(judge.mean(numeric_only=True).round(3).to_string())
else:
    judge = pd.DataFrame()
    print('(샘플 모드 · LLM 미설정 → judge 생략. live 에서 실행)')

# %% [6] 요약 · 합격 판정
summary = pd.DataFrame([{
 'Faithfulness': auto.faithfulness.mean(), 'Answer Relevancy': auto.answer_relevancy.mean(),
 'Answer Correctness': auto.answer_correctness.mean(), 'Citation Accuracy': auto.citation_accuracy.mean(),
 'Context Recall': auto.context_recall.mean(),
 'Refusal Accuracy': auto[auto.q_type == '답없음'].refusal_ok.mean() if (auto.q_type == '답없음').any() else float('nan'),
 '수치 표기율': auto.has_number.mean(), '시점 표기율': auto.has_period.mean(), '인용 표기율': auto.has_citation.mean(),
}]).T.rename(columns={0: '측정'}).round(3)
THRESH = {'Faithfulness': 0.85, 'Answer Relevancy': 0.70, 'Answer Correctness': 0.75,
          'Citation Accuracy': 0.90, 'Context Recall': 0.75, 'Refusal Accuracy': 0.80}
summary['기준'] = [THRESH.get(i, '') for i in summary.index]
summary['판정'] = [('-' if not isinstance(t, float) or pd.isna(v) else ('충족' if v >= t else '미달'))
                 for v, t in zip(summary['측정'], summary['기준'])]
print(summary.to_string())
print('\n주의: 샘플 모드 답변은 LLM 미호출 stub → 생성 지표 수치는 의미 없음. live 에서 판단')

# %% [7] 저장 — 골든_평가_팩 7_답변평가 · 8_표준지표 에 붙여넣기
lab_io.save(auto, 'nb10_auto_metrics')
lab_io.save(summary.reset_index().rename(columns={'index': '지표'}), 'nb10_summary')
lab_io.save(catalog, 'nb10_metric_catalog')
if len(judge):
    lab_io.save(judge, 'nb10_judge')
