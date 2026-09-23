# -*- coding: utf-8 -*-
"""
데이터 파이프라인 적재 검증 — 수집 → 통합 → 메타 → 청킹 → 임베딩 → 인덱싱
각 함수는 DataFrame 을 돌려준다 (Variable Explorer 에서 바로 확인).
판정 기준은 CRITERIA 한 곳에서 관리.
"""
import numpy as np
import pandas as pd

import lab_config as C

# 단계별 합격 기준 — 사내 실정에 맞게 조정
CRITERIA = {
    'doc_id_unique': 1.00,         # 문서 ID 유일성
    'body_present': 0.98,          # 본문 존재율
    'date_present': 0.95,          # 발행일 존재율
    'meta_required': 0.95,         # 유형별 필수 메타 충족률
    'chunk_coverage': 0.98,        # 청킹된 문서 비율
    'orphan_chunk': 0.00,          # 고아 청크 비율 (doc_id 미존재)
    'seq_integrity': 1.00,         # 청크 순번 결손 · 중복 없음
    'empty_chunk': 0.01,           # 빈 · 초단문 청크 비율 상한
    'index_match': 0.99,           # 인덱싱 건수 / 청크 건수
    'dup_body': 0.05,              # 본문 중복 비율 상한
}

# 소스 유형별 필수 메타 — 없는 항목은 수집 단계 보완 과제
REQUIRED_META = {
    'NEWS': ['title', 'published_at', 'org_name'],
    'BROKER': ['title', 'published_at', 'org_name', 'author'],
    'INSTITUTION': ['title', 'published_at', 'org_name'],
    'EMAIL': ['title', 'published_at', 'author'],
    'MEETING': ['title', 'published_at', 'org_name'],
    'REPORT': ['title', 'published_at', 'org_name', 'author'],
    'EXEC_REPORT': ['title', 'published_at', 'org_name'],
}

_OK = lambda v, th, upper=False: ('합격' if (v <= th if upper else v >= th) else '미달')


def _rate(n, d):
    return float(n) / d if d else np.nan


# ---------------- 1단계 · 수집 → 통합 테이블 ----------------
def doc_integrity(raw):
    """통합 문서 테이블 무결성 — ID · 본문 · 날짜 · 중복"""
    n = len(raw)
    dup_id = int(raw['doc_id'].duplicated().sum())
    body = raw['body'].astype(str).str.strip() if 'body' in raw else pd.Series([], dtype=str)
    body_ok = int((body.str.len() > 0).sum()) if n else 0
    date_ok = int(raw['published_at'].notna().sum()) if 'published_at' in raw else 0
    coll_ok = int(raw['collected_at'].notna().sum()) if 'collected_at' in raw else 0
    dup_body = int(body.duplicated().sum()) if n else 0
    fut = 0
    if 'published_at' in raw:
        d = pd.to_datetime(raw['published_at'], errors='coerce')
        fut = int((d > pd.Timestamp.now()).sum() + (d < pd.Timestamp('2000-01-01')).sum())
    rows = [
        ('문서 건수', n, '', '', ''),
        ('doc_id 유일성', _rate(n - dup_id, n), CRITERIA['doc_id_unique'], _OK(_rate(n - dup_id, n), CRITERIA['doc_id_unique']),
         f'중복 {dup_id} 건' if dup_id else ''),
        ('본문 존재율', _rate(body_ok, n), CRITERIA['body_present'], _OK(_rate(body_ok, n), CRITERIA['body_present']),
         f'결측 {n - body_ok} 건'),
        ('발행일 존재율', _rate(date_ok, n), CRITERIA['date_present'], _OK(_rate(date_ok, n), CRITERIA['date_present']),
         f'결측 {n - date_ok} 건'),
        ('수집일 존재율', _rate(coll_ok, n), CRITERIA['date_present'], _OK(_rate(coll_ok, n), CRITERIA['date_present']),
         '발행일 · 수집일 분리 여부 확인'),
        ('본문 중복률', _rate(dup_body, n), CRITERIA['dup_body'], _OK(_rate(dup_body, n), CRITERIA['dup_body'], upper=True),
         f'완전 동일 본문 {dup_body} 건 · 전재 기사 의심'),
        ('날짜 이상치', fut, 0, ('합격' if fut == 0 else '미달'), '미래 일자 · 2000년 이전'),
    ]
    return pd.DataFrame(rows, columns=['점검 항목', '값', '기준', '판정', '비고'])


def meta_completeness(raw, required=None):
    """소스 유형별 필수 메타 충족률 — 부족 항목이 수집 · 파싱 보완 과제"""
    required = required or REQUIRED_META
    out = []
    for t, g in raw.groupby('doc_type'):
        cols = required.get(t, ['title', 'published_at'])
        for c in cols:
            if c not in g:
                out.append(dict(소스=C.DOC_TYPE_KO.get(t, t), 항목=c, 건수=len(g), 충족=0, 충족률=0.0,
                                판정='미달', 비고='컬럼 자체가 없음'))
                continue
            v = g[c]
            ok = int((v.notna() & (v.astype(str).str.strip() != '')).sum())
            r = _rate(ok, len(g))
            out.append(dict(소스=C.DOC_TYPE_KO.get(t, t), 항목=c, 건수=len(g), 충족=ok, 충족률=round(r, 3),
                            판정=_OK(r, CRITERIA['meta_required']), 비고=''))
    return pd.DataFrame(out)


def type_distribution(raw, chunks=None):
    """소스 유형별 문서 · 청크 · 기간 분포 — 수집 편중 확인"""
    out = []
    for t, g in raw.groupby('doc_type'):
        d = pd.to_datetime(g['published_at'], errors='coerce')
        nc = int(chunks[chunks.doc_id.isin(g.doc_id)].shape[0]) if chunks is not None else np.nan
        out.append(dict(소스=C.DOC_TYPE_KO.get(t, t), 코드=t, 문서수=len(g),
                        비중=round(_rate(len(g), len(raw)), 3), 청크수=nc,
                        문서당_청크=round(_rate(nc, len(g)), 1) if chunks is not None else np.nan,
                        최초=str(d.min())[:10], 최신=str(d.max())[:10],
                        평균_본문길이=int(g['body'].astype(str).str.len().mean()) if 'body' in g else 0))
    return pd.DataFrame(out).sort_values('문서수', ascending=False).reset_index(drop=True)


# ---------------- 2단계 · 청킹 테이블 ----------------
def chunk_integrity(raw, chunks, min_len=30):
    """문서 ↔ 청크 연결 무결성 · 청크 품질"""
    nd, nc = len(raw), len(chunks)
    doc_ids = set(raw['doc_id'])
    chunked = set(chunks['doc_id'])
    orphan = int((~chunks['doc_id'].isin(doc_ids)).sum())
    missing = len(doc_ids - chunked)
    tx = chunks['text'].astype(str)
    empty = int((tx.str.strip().str.len() < min_len).sum())
    dup_cid = int(chunks['chunk_id'].duplicated().sum()) if 'chunk_id' in chunks else 0
    seq_bad = 0
    if 'seq' in chunks:
        for _, g in chunks.groupby('doc_id'):
            s = sorted(pd.to_numeric(g['seq'], errors='coerce').dropna().astype(int).tolist())
            if len(s) != len(set(s)) or (s and s != list(range(s[0], s[0] + len(s)))):
                seq_bad += 1
    rows = [
        ('청크 건수', nc, '', '', ''),
        ('청킹 문서 비율', _rate(len(chunked & doc_ids), nd), CRITERIA['chunk_coverage'],
         _OK(_rate(len(chunked & doc_ids), nd), CRITERIA['chunk_coverage']), f'청킹 누락 문서 {missing} 건'),
        ('고아 청크 비율', _rate(orphan, nc), CRITERIA['orphan_chunk'],
         _OK(_rate(orphan, nc), CRITERIA['orphan_chunk'], upper=True), f'원문 없는 청크 {orphan} 건'),
        ('chunk_id 유일성', _rate(nc - dup_cid, nc), 1.0, _OK(_rate(nc - dup_cid, nc), 1.0), f'중복 {dup_cid} 건'),
        ('순번 정합 문서 비율', _rate(len(chunked) - seq_bad, len(chunked)), CRITERIA['seq_integrity'],
         _OK(_rate(len(chunked) - seq_bad, len(chunked)), CRITERIA['seq_integrity']), f'결손 · 중복 {seq_bad} 문서'),
        (f'초단문 청크 비율(<{min_len}자)', _rate(empty, nc), CRITERIA['empty_chunk'],
         _OK(_rate(empty, nc), CRITERIA['empty_chunk'], upper=True), f'{empty} 건'),
    ]
    return pd.DataFrame(rows, columns=['점검 항목', '값', '기준', '판정', '비고'])


def chunk_size_profile(chunks, raw=None, token=True):
    """청크 길이 분포 — 소스 유형별 (임베딩 최대 길이 초과 여부 확인)"""
    import lab_text
    df = chunks.copy()
    df['chars'] = df['text'].astype(str).str.len()
    if token:
        df['tokens'] = df['text'].astype(str).map(lab_text.count_tokens)
    if raw is not None:
        df = df.merge(raw[['doc_id', 'doc_type']], on='doc_id', how='left')
    key = 'doc_type' if 'doc_type' in df else None
    g = df.groupby(key) if key else [('전체', df)]
    out = []
    for t, x in g:
        row = dict(소스=C.DOC_TYPE_KO.get(t, t), 청크수=len(x),
                   글자_중앙=int(x['chars'].median()), 글자_p95=int(x['chars'].quantile(.95)),
                   글자_최대=int(x['chars'].max()))
        if token:
            row.update(토큰_중앙=int(x['tokens'].median()), 토큰_p95=int(x['tokens'].quantile(.95)),
                       토큰_최대=int(x['tokens'].max()),
                       초과율=round(_rate(int((x['tokens'] > C.EMBED_MAX_LENGTH).sum()), len(x)), 4))
        out.append(row)
    return pd.DataFrame(out)


# ---------------- 3단계 · 임베딩 · 인덱싱 ----------------
def index_integrity(chunks, sample=20):
    """Milvus 인덱싱 정합성 — 건수 일치 · 샘플 왕복 · 필드 구성"""
    rows = []
    nc = len(chunks)
    if C.IS_SAMPLE:
        return pd.DataFrame([('인덱싱 점검', np.nan, '', '생략', '샘플 모드 — live 에서 실행')],
                            columns=['점검 항목', '값', '기준', '판정', '비고'])
    try:
        import lab_search
        ms = lab_search.MilvusSearcher()
        info = ms.describe()
        n_idx = int(info.get('num_entities', 0))
        rows.append(('인덱싱 건수', n_idx, '', '', info.get('collection', '')))
        rows.append(('청크 대비 비율', _rate(n_idx, nc), CRITERIA['index_match'],
                     _OK(_rate(n_idx, nc), CRITERIA['index_match']), f'Oracle 청크 {nc} 건'))
        fields = info.get('fields', [])
        for f in ('dense', 'sparse', 'doc_type', 'published_at'):
            name = C.MV.get(f)
            rows.append((f'필드 {f}', (name in fields) if name else False, True,
                         ('합격' if (name and name in fields) else '미달'),
                         '스칼라 필터 · 하이브리드용' if f in ('doc_type', 'sparse') else ''))
        # 샘플 왕복 — 청크 텍스트로 검색해 자기 자신이 1위인지
        hit = 0
        s = chunks.sample(min(sample, nc), random_state=1)
        ret = lab_search.Retriever(parts=('dense',))
        for r in s.itertuples():
            res = ret.search(str(r.text)[:200], 'dense', k=3, cand=5)
            if len(res) and str(res.iloc[0]['chunk_id']) == str(r.chunk_id):
                hit += 1
        rows.append(('자기 검색 적중률', _rate(hit, len(s)), 0.9, _OK(_rate(hit, len(s)), 0.9),
                     f'{len(s)} 건 표본 · 미달 시 임베딩 · 인덱스 불일치'))
    except Exception as ex:
        rows.append(('인덱싱 점검', np.nan, '', '오류', f'{type(ex).__name__}: {ex}'))
    return pd.DataFrame(rows, columns=['점검 항목', '값', '기준', '판정', '비고'])


# ---------------- 종합 ----------------
def pipeline_report(*tables):
    """단계별 점검표를 하나로 — 미달 항목만 빠르게 보기"""
    names = ['1_통합문서', '2_메타', '3_청킹', '4_인덱싱']
    out = []
    for nm, t in zip(names, tables):
        if t is None or not len(t):
            continue
        d = t.copy()
        col = '점검 항목' if '점검 항목' in d else '항목'
        d = d.rename(columns={col: '점검 항목'})
        if '충족률' in d:
            d['값'] = d['충족률']
            d['점검 항목'] = d['소스'].astype(str) + ' · ' + d['점검 항목'].astype(str)
        d['단계'] = nm
        out.append(d[['단계', '점검 항목', '값', '판정'] + (['비고'] if '비고' in d else [])])
    if not out:
        return pd.DataFrame()
    r = pd.concat(out, ignore_index=True)
    r['값'] = pd.to_numeric(r['값'], errors='coerce').round(4)
    return r


def failed_only(report):
    """미달 항목 → 개선 과제 목록"""
    return report[report['판정'] == '미달'].reset_index(drop=True)
