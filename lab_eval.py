# -*- coding: utf-8 -*-
"""
평가 — 골든셋(문서 ID + 정답 문장)으로 검색 지표 계산
  적중 판정: 청크의 doc_id 가 정답 문서이고, 정답 문장이 있으면 그 문장과 글자 3-gram 겹침 ≥ 기준
  지표: Hit@k · Recall@k(정답 문서 기준) · MRR · nDCG@k — 모드별 · 질문 유형별 · 소스별
"""
import re
import math
import numpy as np
import pandas as pd


def _grams(t, n=3):
    t = re.sub(r'\s+', '', t or '')
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def overlap(gold_text, chunk_text):
    """정답 문장 3-gram 중 청크에 들어 있는 비율 (0~1)."""
    g = _grams(gold_text)
    return len(g & _grams(chunk_text)) / len(g) if g else 1.0


def judge(results, gold_doc_ids, gold_text='', th=0.5):
    """결과 각 행의 적중 여부(0/1) 목록."""
    gold = {x.strip() for x in str(gold_doc_ids or '').split(';') if x.strip()}
    rel = []
    for r in results.itertuples():
        ok = str(r.doc_id) in gold and (not gold_text or overlap(gold_text, r.text) >= th)
        rel.append(int(ok))
    return rel


def metrics(rel, results, gold_doc_ids, ks=(1, 3, 5, 10)):
    gold = {x.strip() for x in str(gold_doc_ids or '').split(';') if x.strip()}
    out = {}
    first = next((i for i, v in enumerate(rel) if v), None)
    out['mrr'] = 1 / (first + 1) if first is not None else 0.0
    for k in ks:
        top = rel[:k]
        out[f'hit@{k}'] = int(any(top))
        ids = results['doc_id'].head(k) if 'doc_id' in getattr(results, 'columns', []) else []
        found = {str(d) for d, v in zip(ids, top) if v}
        out[f'recall@{k}'] = len(found) / len(gold) if gold else np.nan
        dcg = sum(v / math.log2(i + 2) for i, v in enumerate(top))
        ideal = sum(1 / math.log2(i + 2) for i in range(min(k, max(1, len(gold)))))
        out[f'ndcg@{k}'] = dcg / ideal if ideal else 0.0
    out['first_hit_rank'] = first + 1 if first is not None else None
    return out


def evaluate(search_fn, golden, modes, k=10, th=0.5, verbose=True):
    """
    search_fn(question, mode, k) → 결과 DataFrame(rank, chunk_id, doc_id, text ...)
    반환: (질문별 상세 df, 모드별 요약 df)
    '답없음' 문항(gold_doc_ids 비어 있음)은 검색 지표에서 제외하고 상위 점수만 기록.
    """
    rows = []
    for mode in modes:
        for g in golden.itertuples():
            res = search_fn(g.question, mode, k)
            base = dict(mode=mode, qid=g.qid, q_type=g.q_type, source=g.source, question=g.question,
                        top1_doc=res['doc_id'].iloc[0] if len(res) else None,
                        top1_text=(res['text'].iloc[0][:80] if len(res) else ''))
            if not str(g.gold_doc_ids or '').strip():
                rows.append({**base, 'no_answer_q': True})
                continue
            rel = judge(res, g.gold_doc_ids, g.gold_text, th)
            rows.append({**base, 'no_answer_q': False, **metrics(rel, res, g.gold_doc_ids)})
        if verbose:
            print(f'  {mode:<20} 완료')
    detail = pd.DataFrame(rows)
    scored = detail[~detail.no_answer_q]
    cols = [c for c in scored.columns if c.startswith(('hit@', 'recall@', 'ndcg@')) or c == 'mrr']
    summary = scored.groupby('mode', sort=False)[cols].mean().round(3)
    return detail, summary


def breakdown(detail, by='q_type', metric='hit@5'):
    """모드 × 질문 유형(또는 source) 표."""
    d = detail[~detail.no_answer_q]
    return d.pivot_table(index=by, columns='mode', values=metric, aggfunc='mean').round(3)


def smoke_template(questions, search_fn, answer_fn=None, k=10):
    """스모크 테스트: 질문마다 상위 k 청크와 답변을 한 표로 → 사람이 판정 칸을 채운다."""
    rows = []
    for q in questions.itertuples():
        res = search_fn(q.question, k)
        ans = answer_fn(q.question, res) if answer_fn else ''
        for r in res.itertuples():
            rows.append(dict(no=q.no, q_type=q.q_type, question=q.question if r.rank == 1 else '',
                             rank=r.rank, doc_id=r.doc_id, text=str(r.text)[:300],
                             answer=ans if r.rank == 1 else '', 검색판정='' if r.rank == 1 else None,
                             답변판정='' if r.rank == 1 else None, 실패유형='' if r.rank == 1 else None, 메모=''))
    return pd.DataFrame(rows)


def smoke_summary(judged):
    """판정 칸을 채운 스모크 표 → 실패 유형 · 검색 판정 · 답변 판정 집계."""
    j = judged[judged['rank'] == 1]
    out = {}
    for col in ('실패유형', '검색판정', '답변판정'):
        out[col] = j[col].fillna('(미기입)').replace('', '(미기입)').value_counts().rename_axis(col).reset_index(name='건수')
    return out
