# -*- coding: utf-8 -*-
"""
RAG 점검 랩 — 설정
------------------------------------------------------------
사내에서 고칠 곳은 두 군데뿐이다.
  1) .env            : 접속 정보 · 엔드포인트 (비밀값)      ← .env.example 복사
  2) 이 파일 [사내 맞춤] 블록 : 테이블 · 컬럼 이름, 문서 유형 코드
LAB_MODE=sample 이면 DB · Milvus · 모델 없이 샘플 데이터로 모든 셀이 돈다.
"""
import os
import re

LAB_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(LAB_DIR, 'out')
GOLDEN_DIR = os.path.join(LAB_DIR, 'golden')
os.makedirs(OUT_DIR, exist_ok=True)


def _load_env(path):
    """python-dotenv 없이도 .env 를 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8-sig') as f:        # 메모장 저장 시 붙는 BOM 제거
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            v = re.split(r'\s+#', v, 1)[0]             # 줄 끝 주석 제거:  KEY=값   # 설명
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env(os.path.join(LAB_DIR, '.env'))
env = lambda k, d=None: os.environ.get(k, d)

# ---------------- 실행 모드 ----------------
LAB_MODE = env('LAB_MODE', 'sample')          # sample | live
IS_SAMPLE = LAB_MODE == 'sample'

# ---------------- Oracle ----------------
ORA_USER = env('ORA_USER')
ORA_PASSWORD = env('ORA_PASSWORD')
ORA_DSN = env('ORA_DSN')                       # 예: host:1521/SERVICE
ORA_THICK_LIB = env('ORA_THICK_LIB')           # thick 모드가 필요할 때만 Instant Client 경로

# ---------------- Milvus ----------------
MILVUS_URI = env('MILVUS_URI', 'http://localhost:19530')
MILVUS_TOKEN = env('MILVUS_TOKEN', '')
MILVUS_COLLECTION = env('MILVUS_COLLECTION', 'rag_chunks')

# ---------------- 모델 ----------------
EMBED_MODE = env('EMBED_MODE', 'sample')       # local(FlagEmbedding) | api(OpenAI 호환) | sample
BGE_M3_PATH = env('BGE_M3_PATH', '')           # local 모드: 모델 폴더
EMBED_URL = env('EMBED_URL', '')               # api 모드: .../v1/embeddings
EMBED_MODEL = env('EMBED_MODEL', 'bge-m3')
EMBED_MAX_LENGTH = int(env('EMBED_MAX_LENGTH', '8192'))  # 현재 설정값을 그대로 적는다 (S04-1 점검용)

RERANK_MODE = env('RERANK_MODE', 'sample')     # local | api | none | sample
RERANK_PATH = env('RERANK_PATH', '')
RERANK_URL = env('RERANK_URL', '')

LLM_URL = env('LLM_URL', '')                   # .../v1/chat/completions (OpenAI 호환)
LLM_MODEL = env('LLM_MODEL', '')
LLM_API_KEY = env('LLM_API_KEY', 'none')

# 기존 사내 검색 API (스모크 테스트 · 평가를 "지금 시스템 그대로" 돌릴 때)
SEARCH_API_URL = env('SEARCH_API_URL', '')
SEARCH_API_TOKEN = env('SEARCH_API_TOKEN', '')

if IS_SAMPLE:                                            # 샘플 모드는 모델 없이 — .env 의 local/api 설정 무시
    EMBED_MODE, RERANK_MODE = 'sample', 'sample'

HTTP_TIMEOUT = int(env('HTTP_TIMEOUT', '60'))
VERIFY_SSL = env('VERIFY_SSL', 'false').lower() == 'true'
if not VERIFY_SSL:                                      # 사내 인증서 환경: 경고 대량 출력 방지
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

# =====================================================================
# [사내 맞춤] 테이블 · 컬럼 이름 — 오른쪽 값만 사내 이름으로 바꾼다. 없으면 None
# =====================================================================
RAW = dict(
    table='RAG_RAW_DOC',
    doc_id='DOC_ID',
    doc_type='DOC_TYPE',
    title='TITLE',
    body='BODY_TEXT',          # CLOB 본문
    published_at='PUBLISHED_AT',
    collected_at='COLLECTED_AT',
    org_name='ORG_NAME',       # 언론사 · 증권사 · 기관 · 부서
    author='AUTHOR',
    security_level=None,       # 없으면 None
    src_url=None,
    file_path=None,            # 원본 파일 경로 · BLOB 존재 여부 확인용 (없으면 None)
)
CHUNK = dict(
    table='RAG_CHUNK',
    chunk_id='CHUNK_ID',
    doc_id='DOC_ID',
    seq='CHUNK_SEQ',
    text='CHUNK_TEXT',
)
# Milvus 컬렉션 필드 이름
MV = dict(
    pk='chunk_id',
    doc_id='doc_id',
    text='chunk_text',
    dense='dense',
    sparse='sparse',           # 없으면 None
    doc_type='doc_type',       # 스칼라 필터 필드 (없으면 None)
    published_at='published_at',
)

# 사내 DOC_TYPE 코드 → 표준 9종. 왼쪽을 사내 코드로 바꾼다.
DOC_TYPE_MAP = {
    'NEWS': 'NEWS', 'BROKER': 'BROKER', 'INSTITUTION': 'INSTITUTION',
    'EMAIL': 'EMAIL', 'MEETING': 'MEETING', 'REPORT': 'REPORT', 'EXEC_REPORT': 'EXEC_REPORT',
}
DOC_TYPE_KO = {
    'NEWS': '뉴스', 'BROKER': '증권사', 'INSTITUTION': '기관', 'EMAIL': '메일', 'MEETING': '회의록',
    'REPORT': '사내 보고서', 'EXEC_REPORT': '임원',
}

# 기존 검색 API 요청 · 응답 모양 — 사내 API에 맞춰 바꾼다
SEARCH_API = dict(
    request=lambda q, k: {'query': q, 'top_k': k},     # 요청 본문
    results_key='results',                              # 응답 JSON에서 결과 목록 키 (점으로 중첩: 'data.items')
    fields=dict(chunk_id='chunk_id', doc_id='doc_id', text='text', score='score', doc_type='doc_type'),
    answer_key='answer',                                # 답변까지 주는 API면 그 키, 없으면 None
)


def summary():
    """현재 설정을 한눈에 (비밀값은 가림)."""
    mask = lambda v: ('설정됨' if v else '비어 있음')
    return {
        'LAB_MODE': LAB_MODE, 'ORA_DSN': ORA_DSN or '비어 있음', 'ORA_USER': mask(ORA_USER),
        'MILVUS_URI': MILVUS_URI, 'MILVUS_COLLECTION': MILVUS_COLLECTION,
        'EMBED_MODE': EMBED_MODE, 'EMBED_MAX_LENGTH': EMBED_MAX_LENGTH, 'RERANK_MODE': RERANK_MODE,
        'LLM_URL': mask(LLM_URL), 'SEARCH_API_URL': mask(SEARCH_API_URL),
        'RAW_TABLE': RAW['table'], 'CHUNK_TABLE': CHUNK['table'], 'OUT_DIR': OUT_DIR,
    }
