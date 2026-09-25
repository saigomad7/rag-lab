# -*- coding: utf-8 -*-
"""
nb01 · 소스 인벤토리
Spyder: 셀마다 Ctrl+Enter (다음 셀로 이동은 Shift+Enter). 결과는 Variable Explorer 에서 확인.

체크리스트: docs/rag_checklist_rev10.xlsx → [P1_적재공통] S01 수집 · S05 메타데이터
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
cfg = pd.Series(C.summary(), name='설정')
print(cfg.to_string())

# %% [1] 소스 유형별 문서 수 · 청크 수 · 작성일 누락 (전체 테이블 집계)
docs_by_type = lab_io.count_by_type()
chunks_by_type = lab_io.count_chunks_by_type()
inv = docs_by_type.merge(chunks_by_type[['doc_type', 'chunks']], on='doc_type', how='left')
inv['유형'] = inv['doc_type'].map(C.DOC_TYPE_KO)
inv['청크/문서'] = (inv['chunks'] / inv['docs']).round(1)
inv['작성일 누락%'] = (inv['no_pub_date'] / inv['docs'] * 100).round(1)
inv = inv[['doc_type', '유형', 'docs', 'chunks', '청크/문서', 'no_pub_date', '작성일 누락%']].sort_values('docs', ascending=False)
print(inv.to_string(index=False))
print('\n미등록 DOC_TYPE(표준 9종 매핑 안 됨):', sorted(set(inv.doc_type) - set(C.DOC_TYPE_KO)))

# %% [2] 표본 원문 로드 — 유형별 N건 (이후 셀은 이 표본으로 점검)
N_PER_TYPE = 50
raw_s = lab_io.sample_per_type(N_PER_TYPE)
print('표본', len(raw_s), '건 /', raw_s.doc_type.nunique(), '개 유형')

# %% [3] 메타데이터 채움률 (S05-1) — 유형별로 값이 들어 있는 비율 %
META_COLS = [c for c in ('title', 'published_at', 'org_name', 'author', 'security_level', 'src_url', 'file_path') if c in raw_s]
meta_fill = raw_s.groupby('doc_type')[META_COLS].apply(lambda g: (g.notna() & (g.astype(str).apply(lambda s: s.str.strip()) != '')).mean() * 100).round(0)
meta_fill.insert(0, '유형', meta_fill.index.map(C.DOC_TYPE_KO))
print(meta_fill.to_string())

# %% [4] 원문 저장 형태 선확인 — 텍스트만인가, 구조가 남아 있나
def _store(g):
    b = g['body'].fillna('')
    return pd.Series({
        '본문 길이 중앙값': int(b.str.len().median()),
        '빈 본문%': round((b.str.len() == 0).mean() * 100, 1),
        'HTML 태그%': round(b.str.contains(r'<(?:p|div|br|table|span)\b', regex=True).mean() * 100, 1),
        'Markdown 표(|)%': round(b.str.contains(r'(?m)^\s*\|.*\|\s*$').mean() * 100, 1),
        '구분자 없는 표 의심%': round(b.map(lab_text.table_suspect).mean() * 100, 1),
        '줄바꿈 보존%': round((b.str.count('\n') >= 3).mean() * 100, 1),
        '원본 파일 경로%': round(g['file_path'].notna().mean() * 100, 1) if 'file_path' in g else None,
    })
store_check = raw_s.groupby('doc_type').apply(_store)
store_check.insert(0, '유형', store_check.index.map(C.DOC_TYPE_KO))
print(store_check.to_string())
print('\n읽는 법: 줄바꿈 보존%가 낮고 구분자 없는 표 의심%가 높으면 → 원본 재파싱 검토 (처리흐름 0번)')

# %% [5] 중복 — 완전 중복(본문 해시) · 근사 중복(MinHash, 재송고 · 인용)
import hashlib
raw_s['body_hash'] = raw_s['body'].fillna('').map(lambda t: hashlib.sha256(t.strip().encode()).hexdigest())
dup_exact = raw_s[raw_s.duplicated('body_hash', keep=False)].sort_values('body_hash')[['doc_id', 'doc_type', 'title', 'body_hash']]
raw_s['clean'] = [lab_text.clean(b, d) for b, d in zip(raw_s['body'], raw_s['doc_type'])]   # 끝부분 저작권 · 서명 문구 차이를 없애고 비교
dup_near = lab_text.near_duplicates(raw_s, 'clean', 'doc_id', threshold=0.8)
if len(dup_near):
    t = raw_s.set_index('doc_id')
    dup_near['type_a'] = dup_near.id_a.map(t.doc_type); dup_near['title_a'] = dup_near.id_a.map(t.title)
    dup_near['type_b'] = dup_near.id_b.map(t.doc_type); dup_near['title_b'] = dup_near.id_b.map(t.title)
print('완전 중복', len(dup_exact), '행 / 근사 중복 쌍', len(dup_near))
print(dup_near.head(10).to_string(index=False))

# %% [6] 저장 + 체크리스트에 옮겨 적을 요약
for _df, _n in ((inv, 'nb01_inventory'), (meta_fill.reset_index(), 'nb01_meta_fill'),
                (store_check.reset_index(), 'nb01_store_check'), (dup_near, 'nb01_dup_near')):
    lab_io.save(_df, _n)
print('\n[체크리스트 기입용]')
for _, r in inv.iterrows():
    print(f"  {r['유형']:<8} 문서 {r['docs']:>8,} · 청크 {(r['chunks'] if pd.notna(r['chunks']) else 0):>9,.0f} · 작성일 누락 {r['작성일 누락%']}%")
