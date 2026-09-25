# -*- coding: utf-8 -*-
"""
nb10 · 답변 품질 지표 — 충실도 · 적합도 · 정확도 · 인용 · 거절
  LLM 이 없어도 돈다. 답변을 만드는 방식을 바꿔 가며 지표가 어떻게 달라지는지 본다.
    모범답변 : 정답 문장을 그대로 답변으로 (지표의 상한선 · 계산이 맞는지 확인)
    추출식   : 상위 청크에서 질문과 겹치는 문장을 뽑아 인용 (LLM 없이 · 사외 연습용)
    LLM      : 사내 LLM 이 생성 (.env 에 LLM_URL 이 있을 때만)

기입 엑셀: archive/inside/golden_eval_pack_rev4.xlsx → [7_답변평가] [8_표준지표]
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
print('LAB_MODE =', C.LAB_MODE, '| LLM =', '사용' if C.USE_LLM else '없음(모범답변 · 추출식으로 진행)')

# %% [1] 정답지 — golden/golden_sample100.csv (사내: golden_v1.csv)
gold = lab_io.load_golden()
print(len(gold), '문항 ·', gold.q_type.value_counts().to_dict())
print(gold.head(3)[['qid', 'question', 'gold_doc_ids']].to_string(index=False))

# %% [2] 지표 카탈로그 — 생성 쪽 지표가 여기서 계산된다
catalog = lab_ragas.catalog()
print(catalog[catalog.구분 == '생성'].to_string(index=False))

# %% [3] 검색 → 답변 만들기 (방식 3가지)
N_EVAL, K, MODE = 30, 6, 'hybrid+rerank+mmr'        # 문항 수 · 컨텍스트 수 · 검색 방식
corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000).dropna(subset=['text']).reset_index(drop=True)
ret = lab_search.Retriever(corpus, bm25_tokenizer='kiwi')
meta = lab_io.load_raw().set_index('doc_id')

rows = []
for g in gold.head(N_EVAL).itertuples():
    res = ret.search(g.question, MODE, k=K, cand=50)
    ctx = res['text'].astype(str).tolist()
    no_ans = (getattr(g, 'q_type', '') == '답없음')
    base = dict(qid=g.qid, question=g.question, q_type=getattr(g, 'q_type', ''), contexts=ctx,
                gold_text=g.gold_text, must_include=(getattr(g, 'must_include', '') or g.gold_text),
                is_no_answer=no_ans, top_docs=';'.join(res['doc_id'].astype(str).head(3)))
    rows.append(dict(base, 방식='모범답변', answer=('확인된 자료 없음' if no_ans else f'{g.gold_text} [1]')))
    rows.append(dict(base, 방식='추출식', answer=lab_search.extractive_answer(g.question, res, meta, n=K)))
    if C.USE_LLM:
        try:
            rows.append(dict(base, 방식='LLM', answer=lab_search.llm_answer(g.question, res, meta, n=K)))
        except Exception as ex:
            print(f'  {g.qid} LLM 건너뜀 — {str(ex).splitlines()[0][:70]}')
print(f'{min(N_EVAL, len(gold))} 문항 × 방식 {len(set(r["방식"] for r in rows))}종 = {len(rows)} 건')
print(pd.DataFrame(rows)[['qid', '방식', 'answer']].head(4).to_string(index=False))

# %% [4] 지표 계산 — 방식별 비교
emb = lab_search.Embedder()
auto = lab_ragas.evaluate_answers(rows, embedder=emb)
auto['방식'] = [r['방식'] for r in rows]
num = ['faithfulness', 'answer_relevancy', 'answer_correctness', 'citation_accuracy', 'refusal_ok']
by_mode = auto.groupby('방식', sort=False)[num].mean().round(3)
print(by_mode.to_string())
print('\n모범답변 = 정답 문장을 그대로 답변으로 쓴 경우 → 지표의 상한선.')
print('추출식이 여기에 얼마나 근접하는가 = 지금 검색이 답변 재료를 얼마나 잘 골라 오는가')

# %% [5] 합격 판정 — 기준 대비
THRESH = {'faithfulness': 0.85, 'answer_relevancy': 0.70, 'answer_correctness': 0.75,
          'citation_accuracy': 0.90, 'refusal_ok': 0.80}
KO = {'faithfulness': '충실도 (근거 안에서 말했나)', 'answer_relevancy': '적합도 (질문에 답했나)',
      'answer_correctness': '정확도 (정답 내용을 담았나)', 'citation_accuracy': '인용 (출처가 맞나)',
      'refusal_ok': '거절 (없으면 없다고 했나)'}
TARGET = 'LLM' if ('LLM' in by_mode.index) else '추출식'
judge = pd.DataFrame({'지표': [KO[k] for k in num],
                      '모범답변(상한)': [by_mode.loc['모범답변', k] for k in num],
                      TARGET: [by_mode.loc[TARGET, k] for k in num],
                      '기준': [THRESH[k] for k in num]})
judge['판정'] = ['충족' if (v == v and v >= t) else '미달' for v, t in zip(judge[TARGET], judge['기준'])]
print(judge.to_string(index=False))

# %% [6] 유형별 · 약한 문항 보기
print('■ 질문 유형별 (', TARGET, ')')
print(auto[auto.방식 == TARGET].groupby('q_type')[num].mean().round(3).to_string())
print('\n■ 정확도가 낮은 문항 5개')
low = auto[auto.방식 == TARGET].nsmallest(5, 'answer_correctness')[['qid', 'q_type'] + num]
print(low.round(3).to_string(index=False))
d = pd.DataFrame(rows)
print('\n해당 문항의 질문 · 답변:')
print(d[(d.방식 == TARGET) & (d.qid.isin(low.qid))][['qid', 'question', 'answer']].to_string(index=False))

# %% [7] 저장
lab_io.save(auto, 'nb10_metrics')
lab_io.save(by_mode.reset_index(), 'nb10_by_mode')
lab_io.save(judge, 'nb10_judge')
lab_io.save(pd.DataFrame(rows).drop(columns=['contexts']), 'nb10_answers')
