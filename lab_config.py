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
    """
    python-dotenv 없이 .env 를 읽는다.
    첫 실행: 이미 있는 환경변수를 존중(setdefault) — 셸에서 준 값이 우선.
    [0] 셀 재실행(reload): .env 값으로 덮어쓴다 — 파일을 고치고 다시 돌리면 반영되게.
      (덮어쓰기가 없으면 Spyder 커널이 살아 있는 동안 옛 값이 계속 남는다)
    """
    if not os.path.exists(path):
        return
    import sys as _sys
    reloaded = getattr(_sys, '_lab_env_loaded', False)      # sys 는 reload 돼도 유지됨
    with open(path, encoding='utf-8-sig') as f:             # 메모장 저장 시 붙는 BOM 제거
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            v = re.split(r'\s+#', v, 1)[0]                  # 줄 끝 주석 제거:  KEY=값   # 설명
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if reloaded:
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)
    _sys._lab_env_loaded = True


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

def _endpoint(url, tail):
    """
    엔드포인트 끝 경로를 맞춘다 — 베이스 URL 만 적어도 동작하게.
      https://api.openai.com/v1                     → .../v1/embeddings
      https://generativelanguage.googleapis.com/v1beta/openai/  → .../openai/embeddings
    """
    if not url:
        return url
    u = url.rstrip('/')
    return u if u.endswith(tail) else f'{u}/{tail}'


EMBED_URL = _endpoint(EMBED_URL, 'embeddings')
EMBED_API_KEY = env('EMBED_API_KEY', '')       # 비우면 LLM_API_KEY 를 쓴다
# 무료 키 대응 — 한 번에 몰아치지 않게
EMBED_BATCH = int(env('EMBED_BATCH', '16'))    # 한 요청에 보낼 문장 수
EMBED_RPM = int(env('EMBED_RPM', '0'))         # 분당 요청 수 제한 (0 = 제한 없음 · 무료 키는 5~15 권장)
EMBED_CACHE = env('EMBED_CACHE', 'true').lower() == 'true'   # 같은 문장은 다시 호출하지 않는다

LLM_URL = env('LLM_URL', '')                   # .../v1/chat/completions (OpenAI 호환)
LLM_MODEL = env('LLM_MODEL', '')
LLM_API_KEY = env('LLM_API_KEY', 'none')
LLM_RPM = int(env('LLM_RPM', '0'))             # 분당 호출 수 제한 (0 = 제한 없음 · 무료 키는 10 권장)
LLM_RETRY = int(env('LLM_RETRY', '3'))         # 429 · 5xx 재시도 횟수
LLM_URL = _endpoint(LLM_URL, 'chat/completions')
if not EMBED_API_KEY:
    EMBED_API_KEY = LLM_API_KEY
RERANK_API_KEY = env('RERANK_API_KEY', '') or LLM_API_KEY

# 기존 사내 검색 API (스모크 테스트 · 평가를 "지금 시스템 그대로" 돌릴 때)
SEARCH_API_URL = env('SEARCH_API_URL', '')
SEARCH_API_TOKEN = env('SEARCH_API_TOKEN', '')

# 샘플 데이터로 연습하되 모델은 진짜로 쓰고 싶을 때 (개인 노트북 학습용) → SAMPLE_MODELS=true
#   DB · Milvus 없이 샘플 문서 16건을 쓰면서 임베딩 · 리랭커 · LLM 은 실제 호출한다.
#   사내 데이터는 들어가지 않으므로 외부 API(OpenAI 등)를 써도 무방하다. 사내에서는 쓰지 않는다.
SAMPLE_MODELS = env('SAMPLE_MODELS', 'false').lower() == 'true'
# 샘플 데이터 규모 — 16(기본, lab_sample) | 100(lab_sample100, 지표가 의미를 갖는 규모)
SAMPLE_SET = env('SAMPLE_SET', '16')
if IS_SAMPLE and not SAMPLE_MODELS:                      # 샘플 모드 기본값은 모델 없이
    EMBED_MODE, RERANK_MODE = 'sample', 'sample'

# LLM 을 실제로 호출할 수 있는 상태인가 (live 이거나, 샘플 + SAMPLE_MODELS)
USE_LLM = bool(LLM_URL) and (not IS_SAMPLE or SAMPLE_MODELS)

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
# 왼쪽 = 랩이 쓰는 표준 이름(고정) · 오른쪽 = 사내 실제 이름(교체)
#   · 없는 컬럼은 None  → SELECT 에서 빠진다
#   · 사내에만 있는 컬럼은 줄을 추가하면 된다 (예: approval_status='APRV_STS')
#     추가한 컬럼은 raw 데이터프레임에 그대로 실려 오고,
#     lab_sources 의 required 에 넣으면 nb00 메타 점검 대상이 된다
#   · 이름은 영문 소문자 · 밑줄 권장. 끝이 _at · _dt · _date 면 날짜로 자동 변환
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

# ---------------------------------------------------------------------
# 소스 유형은 lab_sources.py 한 곳에서 정의한다 (추가 · 제거 · 이름 변경).
# 여기서는 그 정의를 읽어 쓰기만 한다 — 고칠 것 없음.
# ---------------------------------------------------------------------
import lab_sources                       # noqa: E402
DOC_TYPE_MAP = lab_sources.type_map()    # 사내 코드 → 유형 코드
DOC_TYPE_KO = lab_sources.ko_map()       # 유형 코드 → 표기 이름

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
        'LAB_MODE': LAB_MODE + (' + 실제 모델' if (IS_SAMPLE and SAMPLE_MODELS) else ''), 'SAMPLE_SET': SAMPLE_SET, 'ORA_DSN': ORA_DSN or '비어 있음', 'ORA_USER': mask(ORA_USER),
        'MILVUS_URI': MILVUS_URI, 'MILVUS_COLLECTION': MILVUS_COLLECTION,
        'EMBED_MODE': EMBED_MODE, 'EMBED_MAX_LENGTH': EMBED_MAX_LENGTH, 'RERANK_MODE': RERANK_MODE,
        'EMBED_URL': EMBED_URL or '비어 있음', 'LLM_URL': LLM_URL or '비어 있음', 'USE_LLM': USE_LLM, 'SEARCH_API_URL': mask(SEARCH_API_URL),
        'RAW_TABLE': RAW['table'], 'CHUNK_TABLE': CHUNK['table'], 'OUT_DIR': OUT_DIR,
    }
