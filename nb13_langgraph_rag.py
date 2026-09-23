# -*- coding: utf-8 -*-
"""
nb13 · LangGraph 기반 RAG — 노드 구성 → 실행 추적 → 프리셋별 지표 비교
  [1] 그래프 구성 확인  [2] 질문 1건 노드별 추적  [3] 프리셋 비교  [4] 증감(개선 정량화)
  [5] 최적 프리셋 고정 → 운영 설정으로
  Variable Explorer 확인 대상: st(상태) · tr(노드 추적) · summ(비교표) · dlt(증감) · detail
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
import lab_io, lab_search, lab_eval, lab_ragas, lab_graph
for _m in (lab_io, lab_search, lab_eval, lab_ragas, lab_graph):
    importlib.reload(_m)
pd.set_option('display.width', 240); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 46)
try:
    import langgraph; LG = True
except Exception:
    LG = False
print('LAB_MODE =', C.LAB_MODE, '| langgraph =', '설치됨' if LG else '미설치(내장 실행기 사용 · 결과 동일)')

# %% [1] 프리셋 — 실험 설계서 (노드를 하나씩 켜며 측정)
print(pd.DataFrame(lab_graph.PRESETS).T.to_string())

# %% [2] 검색기 · 그래프 준비
corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else 50000).dropna(subset=['text']).reset_index(drop=True)
meta = lab_io.load_raw().set_index('doc_id')
ret = lab_search.Retriever(corpus, bm25_tokenizer='kiwi')
conf = lab_graph.cfg('v6_verify')
app = lab_graph.build_langgraph(ret, meta, conf)
print('그래프:', 'langgraph StateGraph' if app else '내장 실행기')
print('노드 순서: route → decompose → retrieve → grade →(근거 없으면) rewrite → generate → verify')

# %% [3] 질문 1건 — 노드별 실행 추적
Q = 'HBM 증설 계획과 그에 따른 공급 영향은?'
st = lab_graph.run_graph(Q, ret, meta, conf, app)
tr = lab_graph.trace_table(st)
print(tr.to_string(index=False))
print('\n하위 질의:', st['subqueries'])
print('컨텍스트', len(st['contexts']), '개 · 재검색', st['retry'], '회 · 재생성', st['regen'], '회 · 충실도', st['faith'])
print('\n[답변]\n', st['answer'][:600])

# %% [4] 평가 질문 적재 — 골든셋(근거 확보분) 우선
_g = os.path.join(C.GOLDEN_DIR, 'golden_from_bank.csv')
GSRC = _g if os.path.exists(_g) else os.path.join(C.GOLDEN_DIR, 'answer_golden_v1.csv')
gold = lab_io.read_table(GSRC).fillna('')
qs = list(zip(gold.qid.astype(str), gold.question.astype(str)))[:20]      # live: 전체 권장
print('골든셋 =', os.path.basename(GSRC), '· 평가 문항', len(qs))

# %% [5] 프리셋 비교 — 노드를 켤 때마다 지표가 어떻게 변하는가
emb = lab_search.Embedder()
PRESETS = ['v0_baseline', 'v1_hybrid', 'v2_rerank', 'v3_mmr', 'v5_grade', 'v6_verify']
summ, detail = lab_graph.compare(PRESETS, qs, ret, meta, golden=gold, embedder=emb, use_langgraph=LG)
print(summ.to_string(index=False))

# %% [6] 증감 — 개선 정량화 (기준 = v0_baseline)
dlt = lab_graph.delta(summ, base='v0_baseline')
print(dlt.to_string(index=False))
print('\n해석: 값이 오르면 개선 · 평균_초 는 낮을수록 좋음 · 표본이 작으면 오차 범위 확인(nb08 sample_size_note)')

# %% [7] 프리셋별 문항 결과 — 퇴행 문항 추적
M = 'answer_correctness'          # faithfulness · answer_relevancy · answer_correctness 중 선택
piv = detail.pivot_table(index='qid', columns='preset', values=M, aggfunc='first')
piv = piv[[p for p in PRESETS if p in piv.columns]]
piv['증감'] = (piv.iloc[:, -1] - piv.iloc[:, 0]).round(3)
print(f'[{M}] 프리셋별 문항 점수 · 증감 < 0 = 퇴행 문항')
print(piv.round(3).to_string())
print('\n퇴행 문항:', list(piv[piv['증감'] < 0].index) or '(없음)')

# %% [8] 저장 — 이력 엑셀 `5_실험이력` · `6_프리셋비교` 에 붙여넣기
lab_io.save(summ, 'nb13_preset_summary')
lab_io.save(dlt, 'nb13_preset_delta')
lab_io.save(detail.drop(columns=['contexts', 'chunk_ids'], errors='ignore'), 'nb13_detail')
print('\n운영 적용: 최고 프리셋을 lab_graph.DEFAULT 에 지정 → 이후 모든 실행에 반영')
