# -*- coding: utf-8 -*-
"""
nb04 · Milvus 점검 — 체크리스트 S06 (버전 · 필터 필드 · 인덱스 · Oracle 과 건수 정합성) · S10-2 필터 동시 적용
live 모드 전용. sample 모드에서는 어떤 표가 나오는지 모양만 보여 준다.
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
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 80)
LIVE = not C.IS_SAMPLE
print('LAB_MODE =', C.LAB_MODE, '| 컬렉션 =', C.MILVUS_COLLECTION)

# %% [1] 서버 버전 · 스키마 · 인덱스 · 건수 (S06-1 · S06-4)
if LIVE:
    import pymilvus
    mv = lab_search.MilvusSearcher()
    try:
        from pymilvus import utility, connections
        connections.connect(uri=C.MILVUS_URI, token=C.MILVUS_TOKEN or None)
        server_version = utility.get_server_version()
    except Exception as ex:
        server_version = f'확인 실패: {type(ex).__name__}'
    mv_fields, mv_indexes, mv_count = mv.describe()
else:
    server_version = '(sample) 2.4.x'
    mv_fields = pd.DataFrame([dict(name='chunk_id', type='VARCHAR', params='{"max_length": 100}', is_primary=True),
                              dict(name='dense', type='FLOAT_VECTOR', params='{"dim": 1024}', is_primary=False),
                              dict(name='chunk_text', type='VARCHAR', params='{"max_length": 8000}', is_primary=False)])
    mv_indexes = pd.DataFrame([dict(index_name='dense', index_type='HNSW', metric_type='IP', params='{"M": 16, "efConstruction": 200}')])
    mv_count = 32
print('Milvus 서버:', server_version, '| pymilvus:', getattr(__import__('pymilvus'), '__version__', '?'), '| 엔티티 수:', mv_count)
print(mv_fields.to_string(index=False)); print(mv_indexes.to_string(index=False))
print('\n기준: sparse · hybrid_search · array 필터 = 2.4 이상, BM25 내장 = 2.5 이상')

# %% [2] 필요한 필드가 있는가 (S06-2 필터 필드 · S06-3 본문 사본 · S04-2 sparse)
NEED = {'dense (벡터)': 'FLOAT_VECTOR', 'sparse (키워드)': 'SPARSE_FLOAT_VECTOR', 'doc_id': None, 'chunk_text (리랭커용 본문)': None,
        'doc_type (유형 필터)': None, 'published_at (기간 필터)': None, 'security_level (권한)': None, 'acl (권한 그룹)': None}
_names = set(mv_fields['name']); _types = set(mv_fields['type'].str.upper())
field_check = pd.DataFrame([{'필요 필드': k,
                             '있음': (v and any(v in t for t in _types)) or k.split(' ')[0] in _names} for k, v in NEED.items()])
print(field_check.to_string(index=False))

# %% [3] Oracle 청크 수 vs Milvus 엔티티 수 (S06-5 동기화)
if LIVE:
    oracle_chunks = int(lab_io.read_sql(f"SELECT COUNT(*) AS n FROM {C.CHUNK['table']}").n[0])
else:
    oracle_chunks = len(lab_io.load_chunks())
sync_check = pd.DataFrame([dict(oracle_chunks=oracle_chunks, milvus_entities=mv_count, 차이=oracle_chunks - (mv_count or 0))])
print(sync_check.to_string(index=False))
print('차이가 0이 아니면 → 누락 · 삭제 미반영 확인 (S06-5)')

# %% [4] 테스트 검색 — 필터 없이 / 필터 걸고 (S10-2: 필터가 검색과 동시에 적용되는가)
QUERY = '3분기 DRAM 계약가격 전망'
FILTER = f"{C.MV['doc_type']} == 'BROKER'" if C.MV['doc_type'] else ''     # 사내 필드 · 값에 맞게
if LIVE:
    emb = lab_search.Embedder()
    v = emb.encode([QUERY])['dense'][0]
    mv_test = mv.dense(v, 10)
    mv_test_filtered = mv.dense(v, 10, FILTER) if FILTER else pd.DataFrame()
else:
    ret = lab_search.Retriever(lab_io.load_chunks(), parts=('dense',))
    mv_test = ret.dense(QUERY, 10); mv_test_filtered = pd.DataFrame()
print(mv_test[['chunk_id', 'doc_id', 'score', 'text']].head(10).to_string(index=False))
if len(mv_test_filtered):
    print('\n[필터 적용]', FILTER); print(mv_test_filtered[['chunk_id', 'doc_id', 'score', 'text']].to_string(index=False))

# %% [5] 저장
for _df, _n in ((mv_fields, 'nb04_fields'), (mv_indexes, 'nb04_indexes'), (field_check, 'nb04_field_check'), (sync_check, 'nb04_sync')):
    lab_io.save(_df, _n)
