# -*- coding: utf-8 -*-
"""
LangGraph 기반 RAG 검색 로직 — 노드 단위로 켜고 끄며 지표 변화를 본다.

노드 구성
  route → decompose → retrieve → fuse → rerank → diversify → grade
        → (근거 부족 시) rewrite → retrieve … (최대 MAX_RETRY)
        → generate → verify → (환각 의심 시) regenerate 1회 → end

langgraph 가 설치돼 있으면 StateGraph 로 실행하고, 없으면 동일한 노드 함수를
내장 실행기로 순차 실행한다 (결과 동일 · 사내 폐쇄망에서 추가 설치 불필요).

프리셋(PRESETS) 을 바꿔가며 같은 골든셋으로 측정하면 개선 폭이 수치로 남는다.
"""
import re
import time

import numpy as np
import pandas as pd

import lab_config as C
import lab_search
import lab_ragas

MAX_RETRY = 1

# ---------------- 프리셋 — 이 표가 실험 설계서 ----------------
PRESETS = {
 'v0_baseline':  dict(decompose=False, mode='bm25',               grade=False, rewrite=False, verify=False, k=6, cand=50),
 'v1_hybrid':    dict(decompose=False, mode='hybrid',             grade=False, rewrite=False, verify=False, k=6, cand=50),
 'v2_rerank':    dict(decompose=False, mode='hybrid+rerank',      grade=False, rewrite=False, verify=False, k=6, cand=50),
 'v3_mmr':       dict(decompose=False, mode='hybrid+rerank+mmr',  grade=False, rewrite=False, verify=False, k=6, cand=50),
 'v4_decompose': dict(decompose=True,  mode='hybrid+rerank+mmr',  grade=False, rewrite=False, verify=False, k=6, cand=50),
 'v5_grade':     dict(decompose=True,  mode='hybrid+rerank+mmr',  grade=True,  rewrite=True,  verify=False, k=6, cand=50),
 'v6_verify':    dict(decompose=True,  mode='hybrid+rerank+mmr',  grade=True,  rewrite=True,  verify=True,  k=6, cand=50),
}
DEFAULT = 'v6_verify'


def cfg(name=DEFAULT, **over):
    c = dict(PRESETS[name])
    c.update(over)
    c['preset'] = name
    return c


# ---------------- 노드 ----------------
_CMP = re.compile(r'(대비|비교|차이|vs\.?|와 |과 |각각)')
_MULTI = re.compile(r'(그리고|및|또한|이유|배경|영향|전망|요약)')
_SQL_HINT = re.compile(r'(매출|출하|재고|가격|ASP|수량|추이|합계|평균|월별|분기별|전월|전년)')

DECOMP_PROMPT = """아래 질문을 검색에 쓸 하위 질의 2~3개로 나눠라.
규칙: 한 줄에 하나 · 번호 · 설명 없이 질의문만 · 원 질문의 고유명사와 기간은 유지.
질문: {q}"""

GRADE_PROMPT = """질문에 답하는 데 이 문단이 쓸모 있는가? 예 또는 아니오 한 단어로만 답하라.
[질문] {q}
[문단] {t}"""


def n_route(st, c):
    """질의 경로 판정 — 정형(SQL) · 비정형(RAG) · 혼합"""
    q = st['question']
    has_num = bool(_SQL_HINT.search(q))
    st['route'] = 'hybrid' if (has_num and len(q) > 25) else ('sql' if has_num else 'rag')
    st['trace'].append(('route', st['route']))
    return st


def n_decompose(st, c):
    """복합 질의 분해 — 비교 · 다단 질문만 (단순 질의는 그대로)"""
    q = st['question']
    subs = [q]
    if c.get('decompose'):
        if C.USE_LLM:
            try:
                txt = lab_search.llm_answer(DECOMP_PROMPT.format(q=q), pd.DataFrame(columns=['text', 'doc_id']))
                subs = [s.strip(' -·0123456789.') for s in str(txt).splitlines() if len(s.strip()) > 6][:3] or [q]
            except Exception:
                subs = [q]
        elif _CMP.search(q) or _MULTI.search(q):
            parts = [p.strip() for p in re.split(r'(?:와|과|,|그리고|및)\s+', q) if len(p.strip()) > 5]
            subs = ([q] + parts[:2]) if len(parts) > 1 else [q]
    st['subqueries'] = subs
    st['trace'].append(('decompose', len(subs)))
    return st


def n_retrieve(st, c):
    """하위 질의별 검색 → RRF 결합 (단일 질의면 그대로)"""
    ret = st['_ret']
    lists, frames = [], []
    for sq in st['subqueries']:
        r = ret.search(sq, c['mode'], k=c['k'] * 2, cand=c['cand'])
        if not len(r):
            continue
        frames.append(r)
        lists.append(list(r['chunk_id'].astype(str)))
    if not frames:
        st['docs'] = pd.DataFrame(columns=['chunk_id', 'doc_id', 'text', 'score'])
        st['trace'].append(('retrieve', 0))
        return st
    all_df = pd.concat(frames, ignore_index=True).drop_duplicates('chunk_id')
    if len(lists) > 1:
        fused = dict(lab_search.rrf(lists))
        all_df['score'] = all_df['chunk_id'].astype(str).map(fused).fillna(0)
        all_df = all_df.sort_values('score', ascending=False)
    st['docs'] = all_df.head(c['k'] * 2).reset_index(drop=True)
    st['trace'].append(('retrieve', len(st['docs'])))
    return st


def n_grade(st, c):
    """문단 적합성 판정 — 무관 문단 제거 (컨텍스트 오염 차단)"""
    if not c.get('grade') or not len(st['docs']):
        st['graded'] = st['docs']
        return st
    q, keep = st['question'], []
    for r in st['docs'].itertuples():
        t = str(r.text)
        if C.USE_LLM:
            try:
                v = lab_search.llm_answer(GRADE_PROMPT.format(q=q, t=t[:800]), pd.DataFrame(columns=['text', 'doc_id']))
                ok = '예' in str(v)[:10]
            except Exception:
                ok = True
        else:                                    # LLM 없을 때: 어휘 겹침 규칙
            ok = lab_ragas._cov(q, t) >= 0.06 or _kw_overlap(q, t) >= 0.25
        if ok:
            keep.append(r.Index)
    st['graded'] = st['docs'].loc[keep] if keep else st['docs'].head(0)
    st['trace'].append(('grade', f'{len(st["graded"])}/{len(st["docs"])}'))
    return st


def _kw_overlap(q, t):
    ks = {w for w in re.findall(r'[가-힣A-Za-z0-9]{2,}', q)}
    return (len(ks & {w for w in re.findall(r'[가-힣A-Za-z0-9]{2,}', t)}) / len(ks)) if ks else 0.0


def n_rewrite(st, c):
    """근거 부족 시 질의 재작성 후 재검색 (최대 MAX_RETRY)"""
    if st['retry'] >= MAX_RETRY:
        return st
    st['retry'] += 1
    q = st['question']
    core = ' '.join(re.findall(r'[가-힣A-Za-z0-9]{2,}', q)[:8])   # 조사 · 수식어 제거형 축약
    st['subqueries'] = [core, q]
    st['trace'].append(('rewrite', core))
    return st


def n_generate(st, c):
    """답변 생성 — 근거 없으면 '확인된 자료 없음'"""
    docs = st.get('graded', st['docs'])
    st['contexts'] = docs['text'].astype(str).tolist()[:c['k']]
    if not len(docs):
        st['answer'] = '확인된 자료 없음'
    else:
        try:
            st['answer'] = lab_search.llm_answer(st['question'], docs.head(c['k']), st.get('_meta'), n=c['k'])
        except Exception as ex:                      # LLM 호출 실패 — 실행은 계속, 원인을 답변 자리에 남긴다
            st['answer'] = f'(LLM 호출 실패: {type(ex).__name__}) 상위 근거 → ' + str(docs.iloc[0]['text'])[:80]
    st['top_docs'] = ';'.join(docs['doc_id'].astype(str).head(3)) if len(docs) else ''
    st['trace'].append(('generate', len(st['contexts'])))
    return st


def n_verify(st, c):
    """환각 점검 — 근거 없는 문장 비율이 높으면 1회 재생성 후 보류 처리"""
    if not c.get('verify') or not st['contexts']:
        st['faith'] = np.nan
        return st
    f, _ = lab_ragas.faithfulness(st['answer'], st['contexts'])
    st['faith'] = f
    if (f is not None) and (not np.isnan(f)) and f < 0.6 and st['regen'] < 1:
        st['regen'] += 1
        st['trace'].append(('verify', f'재생성 f={f:.2f}'))
        st = n_generate(st, c)
        f2, _ = lab_ragas.faithfulness(st['answer'], st['contexts'])
        st['faith'] = f2
        if f2 < 0.6:
            st['answer'] = '확인된 자료 없음 (근거 불충분)'
    st['trace'].append(('verify', round(float(st['faith']), 3) if st['faith'] == st['faith'] else ''))
    return st


# ---------------- 실행기 ----------------
def _need_rewrite(st, c):
    return c.get('rewrite') and len(st.get('graded', st['docs'])) == 0 and st['retry'] < MAX_RETRY


def _new_state(q, ret, meta):
    return dict(question=q, route='', subqueries=[q], docs=pd.DataFrame(), graded=None, contexts=[],
                answer='', top_docs='', faith=np.nan, retry=0, regen=0, trace=[], _ret=ret, _meta=meta)


def run_once(question, ret, meta=None, c=None):
    """질문 1건 실행 → 상태 dict (trace 로 어느 노드가 무엇을 했는지 확인)"""
    c = c or cfg()
    t0 = time.time()
    st = _new_state(question, ret, meta)
    st = n_route(st, c)
    st = n_decompose(st, c)
    st = n_retrieve(st, c)
    st = n_grade(st, c)
    while _need_rewrite(st, c):
        st = n_rewrite(st, c)
        st = n_retrieve(st, c)
        st = n_grade(st, c)
    st = n_generate(st, c)
    st = n_verify(st, c)
    st['elapsed'] = round(time.time() - t0, 3)
    st['preset'] = c.get('preset', '')
    return st


def build_langgraph(ret, meta=None, c=None):
    """langgraph 설치 시 StateGraph 로 동일 노드를 구성 (없으면 None)"""
    c = c or cfg()
    try:
        from langgraph.graph import StateGraph, END
    except Exception:
        return None
    g = StateGraph(dict)
    g.add_node('route', lambda s: n_route(s, c))
    g.add_node('decompose', lambda s: n_decompose(s, c))
    g.add_node('retrieve', lambda s: n_retrieve(s, c))
    g.add_node('grade', lambda s: n_grade(s, c))
    g.add_node('rewrite', lambda s: n_rewrite(s, c))
    g.add_node('generate', lambda s: n_generate(s, c))
    g.add_node('verify', lambda s: n_verify(s, c))
    g.set_entry_point('route')
    g.add_edge('route', 'decompose')
    g.add_edge('decompose', 'retrieve')
    g.add_edge('retrieve', 'grade')
    g.add_conditional_edges('grade', lambda s: 'rewrite' if _need_rewrite(s, c) else 'generate',
                            {'rewrite': 'rewrite', 'generate': 'generate'})
    g.add_edge('rewrite', 'retrieve')
    g.add_edge('generate', 'verify')
    g.add_edge('verify', END)
    return g.compile()


def run_graph(question, ret, meta=None, c=None, app=None):
    """langgraph 앱이 있으면 그래프로, 없으면 내장 실행기로 (결과 동일)"""
    if app is None:
        return run_once(question, ret, meta, c)
    st = _new_state(question, ret, meta)
    t0 = time.time()
    out = app.invoke(st)
    out['elapsed'] = round(time.time() - t0, 3)
    out['preset'] = (c or cfg()).get('preset', '')
    return out


def trace_table(st):
    """노드 실행 흔적 → DataFrame"""
    return pd.DataFrame(st['trace'], columns=['노드', '결과'])


# ---------------- 프리셋 비교 ----------------
def run_batch(questions, ret, meta=None, c=None, app=None):
    """질문 목록 실행 → 문항별 결과 DataFrame"""
    rows = []
    for q in questions:
        qid, text = (q if isinstance(q, (tuple, list)) else ('', q))
        st = run_graph(text, ret, meta, c, app)
        rows.append(dict(qid=qid, question=text, preset=st['preset'], route=st['route'],
                         n_sub=len(st['subqueries']), n_ctx=len(st['contexts']), retry=st['retry'],
                         regen=st['regen'], faith=st['faith'], elapsed=st['elapsed'],
                         top_docs=st['top_docs'], answer=st['answer'],
                         contexts=st['contexts'], chunk_ids=list(st['docs']['chunk_id'].astype(str))
                         if len(st['docs']) else []))
    return pd.DataFrame(rows)


def compare(presets, questions, ret, meta=None, golden=None, embedder=None, use_langgraph=True):
    """
    프리셋별 실행 → 지표 비교표. golden(qid · gold_doc_ids · must_include) 있으면 검색 · 정확도까지.
    반환: (요약 비교표, 문항별 원본)
    """
    import lab_eval
    allr, summ = [], []
    gmap = {}
    if golden is not None and len(golden):
        gmap = {str(r.qid): r for r in golden.itertuples()}
    for name in presets:
        c = cfg(name)
        app = build_langgraph(ret, meta, c) if use_langgraph else None
        r = run_batch(questions, ret, meta, c, app)
        r['preset'] = name
        rows = []
        for x in r.itertuples():
            g = gmap.get(str(x.qid))
            rec = dict(qid=x.qid, question=x.question, answer=x.answer, contexts=x.contexts,
                       q_type=(getattr(g, 'q_type', '') if g is not None else ''),
                       must_include=(getattr(g, 'must_include', '') if g is not None else ''),
                       gold_text=(getattr(g, 'gold_text', '') if g is not None else ''),
                       is_no_answer=(getattr(g, 'q_type', '') == '답없음' if g is not None else False))
            rows.append(rec)
            if g is not None and getattr(g, 'gold_doc_ids', ''):
                res = pd.DataFrame(dict(doc_id=[d.split('#')[0] for d in x.chunk_ids],
                                        text=x.contexts + [''] * (len(x.chunk_ids) - len(x.contexts))))
                rel = lab_eval.judge(res, str(g.gold_doc_ids), getattr(g, 'gold_text', ''))
                m = lab_eval.metrics(rel, res, str(g.gold_doc_ids))
                r.loc[x.Index, ['hit@5', 'recall@5', 'mrr']] = [m.get('hit@5'), m.get('recall@5'), m.get('mrr')]
        auto = lab_ragas.evaluate_answers(rows, embedder=embedder)
        acols = ['faithfulness', 'answer_relevancy', 'answer_correctness', 'citation_accuracy', 'refusal_ok']
        r = r.merge(auto[['qid'] + acols], on='qid', how='left')
        s = dict(preset=name,
                 검색_hit5=round(r['hit@5'].mean(), 3) if 'hit@5' in r else np.nan,
                 Faithfulness=round(auto.faithfulness.mean(skipna=True), 3),
                 Answer_Relevancy=round(auto.answer_relevancy.mean(skipna=True), 3),
                 Answer_Correctness=round(auto.answer_correctness.mean(skipna=True), 3),
                 Citation=round(auto.citation_accuracy.mean(skipna=True), 3),
                 거절_정확도=round(auto[auto.q_type == '답없음'].refusal_ok.mean(), 3)
                 if (auto.q_type == '답없음').any() else np.nan,
                 재검색=int(r.retry.sum()), 재생성=int(r.regen.sum()),
                 평균_초=round(r.elapsed.mean(), 3))
        summ.append(s)
        allr.append(r)
    return pd.DataFrame(summ), pd.concat(allr, ignore_index=True)


def delta(summary, base=None):
    """기준 프리셋 대비 증감 — 개선 정량화"""
    d = summary.set_index('preset')
    base = base or d.index[0]
    num = d.select_dtypes('number')
    out = (num - num.loc[base]).round(3)
    out.insert(0, '기준 대비', [('기준' if i == base else '') for i in out.index])
    return out.reset_index()
