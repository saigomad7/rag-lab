# -*- coding: utf-8 -*-
"""
소스별 컬럼 정의서 — 소스 유형마다 어떤 항목이 있어야 하고, 그 항목을 **어디에 저장하는가**
행 = (이름, 논리명, 타입, 필수, 저장 위치, 어디서 오나, 쓰이는 곳(단계), 샘플값)
  필수: M=반드시 / R=권장 / O=선택
  저장 위치: COL=공통 컬럼 · JSON=META_EXTRA 키 · TAGS=TAGS 키 · ACL=RAG_DOC_ACL 행 · CHUNK=청크 컬럼
"""
M, R, O = 'M', 'R', 'O'
COL, JSON, TAGS, ACL, CHUNK = 'COL', 'JSON', 'TAGS', 'ACL', 'CHUNK'

STORE_KO = {
    COL:   ('공통 컬럼', '필터 · 권한 · 정렬 · 인용에 쓰이므로 전용 컬럼'),
    JSON:  ('META_EXTRA', '소스별로만 쓰는 값 → JSON 키'),
    TAGS:  ('TAGS', '센싱 · 라우팅용 엔티티 → JSON 배열'),
    ACL:   ('ACL 테이블', '권한 판단에 쓰이므로 행으로 분리'),
    CHUNK: ('청크 컬럼', 'RAG_CHUNK 의 컬럼'),
}

# ---------- 모든 소스 공통 (문서 단위 = RAG_DOC) ----------
COMMON_DOC = [
 ('DOC_ID', '문서 고유 ID', 'VARCHAR2(64)', M, COL, '적재 시 생성 (소스코드+일자+일련)', 'S01 · 전 단계 키', 'NEWS_20260915_000123'),
 ('SRC_SYSTEM', '원천 시스템', 'VARCHAR2(32)', M, COL, '수집 모듈', 'S01 증분 · 재수집', 'NEWS_CRAWL'),
 ('SRC_KEY', '원천 키', 'VARCHAR2(200)', M, COL, '원천 테이블 PK · URL · Message-ID', 'S01 중복 · 갱신 판정', 'hankyung:2026091500123'),
 ('DATA_SOURCE', '사외/사내', 'VARCHAR2(16)', M, COL, '수집 경로', 'S10 필터 · S28 권한', 'EXTERNAL'),
 ('DOC_TYPE', '문서 유형', 'VARCHAR2(32)', M, COL, '수집 경로 · 분류', 'S03 청킹 규칙 · S10 필터', 'NEWS'),
 ('TITLE', '제목', 'VARCHAR2(1000 CHAR)', M, COL, '원문', 'S03 헤더 · S14 인용', '마이크론, 히로시마 HBM 라인 증설'),
 ('PUBLISHED_AT', '작성 · 발행일시', 'DATE', M, COL, '원문 (없으면 NULL)', 'S08 기간필터 · S12 최신성 · S19 센싱', '2026-09-15 08:12'),
 ('DATE_QUALITY', '날짜 품질', 'VARCHAR2(10)', R, COL, 'EXACT / ESTIMATED / MISSING', 'S08 필터 신뢰도', 'EXACT'),
 ('COLLECTED_AT', '수집일시', 'DATE', M, COL, '수집 모듈', 'S01 운영 · 지연 점검', '2026-09-15 09:00'),
 ('ORG_NAME', '기관 · 부서', 'VARCHAR2(200 CHAR)', M, COL, '언론사 · 증권사 · 기관 · 작성 부서', 'S03 헤더 · S14 인용 · 필터', '한국경제'),
 ('AUTHOR', '작성자', 'VARCHAR2(200 CHAR)', R, COL, '기자 · 애널리스트 · 작성자', 'S14 인용', '김기술'),
 ('SRC_URL', '원문 링크 · 경로', 'VARCHAR2(2000)', R, COL, 'URL 또는 파일 경로', 'UI 원문 이동 · 재파싱', 'https://…/2026/09/15/123'),
 ('FILE_PATH', '원본 파일 경로', 'VARCHAR2(1000)', R, COL, '파일 서버 · 그룹웨어', '처리흐름 0번(재파싱 가능 여부)', '\\\\fs01\\reports\\2026\\R-0912.pptx'),
 ('LANG', '언어', 'VARCHAR2(8)', R, COL, '판별 또는 소스 고정', 'S08 질의 확장', 'ko'),
 ('SECURITY_LEVEL', '보안 등급', 'NUMBER(1)', M, COL, '0 공개 1 사내 2 대외비 3 임원', 'S10 필터 · S28 권한', '0'),
 ('CONTENT_HASH', '본문 해시', 'VARCHAR2(64)', M, COL, 'SHA-256(정제 본문)', 'S01 중복 · 변경 감지', 'a3f9…'),
 ('TAGS', '태그 묶음', 'CLOB CHECK(IS JSON)', R, COL, 'LLM 추출 + 사전 (아래 TAGS 스키마)', 'S05 · S19 센싱 · S24 라우팅', '{"company":["마이크론"],…}'),
 ('META_EXTRA', '가변 메타 묶음', 'CLOB CHECK(IS JSON)', M, COL, '소스별 고유 항목 (아래 소스별 표의 JSON 행)', 'S05 표시 · 보조 필터', '{"category":"IT/테크",…}'),
 ('IS_DELETED', '삭제 여부', 'CHAR(1)', M, COL, '원천 삭제 · 폐기 반영', 'S06 동기화', 'N'),
 ('UPD_DATE', '갱신일시', 'DATE', M, COL, '적재 시각', 'S06 증분 동기화', '2026-09-15 09:00'),
]

# ---------- 청크 단위 (RAG_CHUNK) ----------
COMMON_CHUNK = [
 ('CHUNK_ID', '청크 ID', 'VARCHAR2(100)', M, CHUNK, 'DOC_ID + 순번', 'S06 Milvus PK', 'NEWS_20260915_000123_0001'),
 ('DOC_ID', '문서 ID', 'VARCHAR2(64)', M, CHUNK, 'RAG_DOC 참조', '인용 · 문서당 상한', 'NEWS_20260915_000123'),
 ('CHUNK_SEQ', '순번', 'NUMBER(6)', M, CHUNK, '분할 순서', '인접 확장', '1'),
 ('PARENT_ID', '부모 청크', 'VARCHAR2(100)', O, CHUNK, 'Parent-Child 구조', 'S03-4 · S13 확장', ''),
 ('CHUNK_KIND', '청크 종류', 'VARCHAR2(10)', R, CHUNK, 'TEXT / TABLE / SUMMARY', 'S03 표 분리 · 수치 질문', 'TEXT'),
 ('SECTION_PATH', '섹션 경로', 'VARCHAR2(1000 CHAR)', R, CHUNK, '헤딩 · 안건 · 슬라이드 번호', 'S03 헤더 · 인용', '3. 공급 > 3.2 DRAM 증설'),
 ('HEADER_TEXT', '문맥 헤더', 'VARCHAR2(1000 CHAR)', M, CHUNK, '[유형|날짜|기관|제목|섹션] 생성', 'S03-3 · S04 dense 입력', '[뉴스 | 2026-09-15 | 한국경제 | …]'),
 ('CHUNK_TEXT', '청크 본문', 'CLOB', M, CHUNK, '정제 후 분할', 'S04 임베딩 · S12 리랭크', '마이크론이 일본 히로시마 공장에…'),
 ('TOKEN_CNT', '토큰 수', 'NUMBER(6)', R, CHUNK, '임베딩 토크나이저', 'S04-1 잘림 점검', '412'),
 ('CHUNKER_VER', '청커 버전', 'VARCHAR2(16)', R, CHUNK, '분할 규칙 버전', '재청킹 비교', 'v2'),
]

# ---------- 소스별 ----------
PER_SOURCE = {
 'NEWS': ('뉴스', [
   ('ORG_NAME ← publisher', '언론사', 'VARCHAR2(200 CHAR)', M, COL, '수집 메타 → 공통 컬럼에 적재', '필터 · 인용', '한국경제'),
   ('AUTHOR ← reporter', '기자', 'VARCHAR2(200 CHAR)', R, COL, '기사 바이라인 → 공통 컬럼', '인용', '김기술'),
   ('category', '분야', 'string', R, JSON, '언론사 분류', '표시 · 센싱 축 매핑', '"IT/테크"'),
   ('cluster_id', '사건 묶음 ID', 'string', R, JSON, '근사 중복(MinHash) 묶음 대표', 'S01 재송고 · S18 센싱', '"EVT_20260915_HBM_MU"'),
   ('is_primary', '대표 기사', 'string(Y/N)', R, JSON, '묶음 중 가장 이른 기사', '중복 접기', '"Y"'),
   ('press_type', '매체 유형', 'string', O, JSON, '종합지 · 산업지 · 통신사', '가중치', '"종합지"'),
   ('company / product / topic', '엔티티 태그', 'array', R, TAGS, '사내 LLM 추출 + 코드 사전', 'S19 센싱 · S24 라우팅', '["마이크론"] / ["HBM"]'),
 ]),
 'BROKER': ('증권사 리포트', [
   ('ORG_NAME ← firm_name', '증권사', 'VARCHAR2(200 CHAR)', M, COL, '리포트 표지 → 공통 컬럼', '필터 · 인용', '○○증권'),
   ('AUTHOR ← analyst', '애널리스트', 'VARCHAR2(200 CHAR)', R, COL, '표지 · 말미 → 공통 컬럼', '인용', '이분석'),
   ('period_covered', '대상 기간', 'string', R, JSON, '제목 · 본문', 'S08 기간 필터 보조', '"3Q26"'),
   ('report_type', '리포트 종류', 'string', R, JSON, '산업 · 기업 · 프리뷰 · 리뷰', '표시 · 필터', '"산업"'),
   ('target_stock', '대상 종목 · 산업', 'string', R, JSON, '표지', '표시 · 센싱', '"메모리 반도체"'),
   ('opinion', '투자의견', 'string', O, JSON, '표지', '센싱(논조)', '"BUY"'),
   ('target_price', '목표가', 'number', O, JSON, '표지', '센싱', '260000'),
   ('has_table', '표 포함', 'string(Y/N)', R, JSON, '파싱 결과', 'S03 표 청크 분리', '"Y"'),
   ('company / product', '엔티티 태그', 'array', R, TAGS, 'LLM 추출', '센싱 · 라우팅', '["SK하이닉스","삼성전자"]'),
 ]),
 'INSTITUTION': ('기관 보고서', [
   ('ORG_NAME ← institution_name', '기관명', 'VARCHAR2(200 CHAR)', M, COL, '표지 → 공통 컬럼', '필터 · 인용', '○○리서치'),
   ('data_asof', '데이터 기준 시점', 'string', M, JSON, '본문 "as of" · 표 머리말', 'S08 기간 · S27 정합성', '"2Q26"'),
   ('research_type', '자료 유형', 'string', R, JSON, '시장전망 · 통계 · 백서', '표시 · 필터', '"시장전망"'),
   ('license_scope', '라이선스 범위', 'string', R, JSON, '계약 정보', 'S28 권한 판단 근거', '"사내 열람"'),
   ('region_scope', '지역 범위', 'string', O, JSON, '표지 · 목차', '표시', '"Global"'),
   ('keywords', '키워드', 'array', O, JSON, '표지 · 목차', '센싱 보조', '["HBM","CapEx"]'),
 ]),
 'EMAIL': ('메일', [
   ('SRC_KEY ← message_id', 'Message-ID', 'VARCHAR2(200)', M, COL, '메일 헤더 → 원천 키', '중복 · 갱신', '<a1b2@mail>'),
   ('ORG_NAME ← sender_dept', '발신 부서', 'VARCHAR2(200 CHAR)', R, COL, '조직도 매핑 → 공통 컬럼', '필터 · 표시', '영업전략팀'),
   ('thread_id', '스레드 ID', 'string', M, JSON, 'In-Reply-To 추적', 'S03 스레드 청킹', '"TH_9901"'),
   ('has_attachment', '첨부 유무', 'string(Y/N)', M, JSON, '메일 파싱', '첨부 분리 처리', '"Y"'),
   ('attach_doc_ids', '첨부 문서 ID', 'array', R, JSON, '첨부를 별도 문서로 적재', '처리흐름(첨부 분기)', '["RPT_20260910_0007"]'),
   ('quote_removed', '인용 제거 여부', 'string(Y/N)', R, JSON, '정제 단계 기록', 'S02 품질 점검', '"Y"'),
   ('sender / recipients', '발신자 · 수신자', 'ACL 행', M, ACL, '메일 헤더 To · Cc', 'S28 권한 필터', 'USER lee@… / USER pm@…'),
 ]),
 'MEETING': ('회의록', [
   ('PUBLISHED_AT ← meeting_date', '회의일', 'DATE', M, COL, '양식 → 공통 컬럼', '기간 필터', '2026-09-17'),
   ('ORG_NAME ← department', '주관 부서', 'VARCHAR2(200 CHAR)', M, COL, '양식 → 공통 컬럼', '필터 · 권한', '시장분석팀'),
   ('project_code', '과제 코드', 'string', R, JSON, '양식', '표시 · 권한 보조', '"PRJ-MIS-2026"'),
   ('agenda_no', '안건 번호', 'number', R, JSON, '분할 시 부여', 'S03 안건 단위 청킹', '2'),
   ('decisions', '결정 사항', 'array', R, JSON, '본문 추출', '질문 응답(무엇을 정했나)', '["4Q 전망 유지"]'),
   ('action_items', '액션 아이템', 'array of object', R, JSON, '본문 추출', '질문 응답 · 추적', '[{"task":"…","owner":"박기록","due":"2026-09-24"}]'),
   ('attendees', '참석자', 'ACL 행', M, ACL, '양식', 'S28 권한 필터', 'USER 박기록 / GROUP 시장분석팀'),
 ]),
 'REPORT': ('사내 보고서', [
   ('ORG_NAME ← department', '작성 부서', 'VARCHAR2(200 CHAR)', M, COL, '문서 속성 · 결재 정보', '권한 · 필터', '시장분석팀'),
   ('SECURITY_LEVEL', '보안 등급', 'NUMBER(1)', M, COL, '표지 표기 · 그룹웨어', 'S10 · S28', '1'),
   ('version', '버전', 'string', M, JSON, '파일명 · 표지', 'S01 최종본 판정', '"v1.0"'),
   ('approval_status', '결재 상태', 'string', M, JSON, '그룹웨어', '최종본만 적재', '"APPROVED"'),
   ('report_kind', '보고서 종류', 'string', R, JSON, '표지', '표시 · 필터', '"시장동향"'),
   ('period_covered', '대상 기간', 'string', R, JSON, '제목 · 본문', '기간 필터 보조', '"3Q26"'),
   ('file_format', '원본 형식', 'string', R, JSON, '파일 확장자', 'S02 파서 분기', '"PPTX"'),
   ('SECTION_PATH ← slide_no', '슬라이드 번호', 'VARCHAR2(1000 CHAR)', R, CHUNK, '청크 생성 시', '인용 위치', '슬라이드 7'),
 ]),
 'KNOWLEDGE': ('지식문서', [
   ('PUBLISHED_AT ← last_updated_at', '최종 수정일', 'DATE', M, COL, 'KMS → 공통 컬럼(작성일 대신)', 'S08 최신성', '2026-08-30'),
   ('AUTHOR ← last_updated_by', '최종 수정자', 'VARCHAR2(200 CHAR)', R, COL, 'KMS → 공통 컬럼', '인용 · 문의처', '관리자'),
   ('category', '분류', 'string', M, JSON, 'KMS 분류 체계', '표시 · 필터', '"용어 정의"'),
   ('system_name', '대상 시스템 · 업무', 'string', R, JSON, 'KMS 속성', '표시 · 필터', '"MIS"'),
   ('doc_status', '문서 상태', 'string', M, JSON, '현행 / 개정중 / 폐기', '폐기본 제외 (또는 IS_DELETED)', '"CURRENT"'),
   ('related_docs', '관련 문서', 'array', O, JSON, 'KMS 링크', '추가 탐색', '["KB_0102"]'),
 ]),
 'ENG_REPORT': ('엔지니어 보고서', [
   ('ORG_NAME ← department', '작성 부서', 'VARCHAR2(200 CHAR)', M, COL, '문서 속성', '권한 · 필터', '○○개발팀'),
   ('process', '공정', 'string', M, JSON, '문서 속성 · 본문', '표시 · 필터', '"TSV"'),
   ('fab', 'Fab · 라인', 'string', R, JSON, '문서 속성', '표시 · 필터', '"M16"'),
   ('test_item', '평가 항목', 'string', R, JSON, '본문 · 표 제목', '수치 질문', '"온도별 신뢰성"'),
   ('spec_version', '규격 버전', 'string', O, JSON, '본문', '버전 구분', '"REL-2.3"'),
   ('has_measure_table', '측정 표 포함', 'string(Y/N)', R, JSON, '파싱 결과', '표 청크 분리', '"Y"'),
   ('product', '제품 태그', 'array', M, TAGS, '문서 속성 → 코드 사전', 'S24 라우팅 · 정형 연계', '["HBM4-12H"]'),
   ('project_code', '과제 그룹', 'ACL 행', M, ACL, '문서 속성', 'S28 과제 그룹 권한', 'GROUP PRJ-HBM4-REL'),
 ]),
 'EXEC_REPORT': ('임원 보고서', [
   ('SECURITY_LEVEL', '보안 등급', 'NUMBER(1)', M, COL, '표지 표기 (등급 3 고정)', 'S10 · S28', '3'),
   ('ORG_NAME ← department', '보고 부서', 'VARCHAR2(200 CHAR)', M, COL, '표지', '필터 · 인용', '전략기획'),
   ('report_to', '보고 대상', 'string', M, JSON, '표지 · 결재선', '표시', '"CEO"'),
   ('meeting_body', '보고 회의체', 'string', R, JSON, '표지', '표시 · 필터', '"경영회의"'),
   ('confidentiality', '대외 등급', 'string', M, JSON, '표지 표기', '표시 · 감사', '"CONFIDENTIAL"'),
   ('decision_items', '결정 · 지시 사항', 'array', R, JSON, '본문 추출', '질문 응답 · 추적', '["고객 다변화 추진"]'),
   ('summary_slide', '요약 슬라이드 번호', 'number', R, JSON, '파싱', '리랭크 가중', '2'),
   ('approval_line', '결재선', 'ACL 행', M, ACL, '그룹웨어', 'S28 권한 필터', 'USER A상무 / USER B전무'),
 ]),
}

# ---------- 소스별 META_EXTRA JSON 스키마 (그대로 복사해 쓰는 형태) ----------
JSON_SCHEMA = {
 'NEWS': """{
  "category":    "IT/테크",
  "cluster_id":  "EVT_20260915_HBM_MU",
  "is_primary":  "Y",
  "press_type":  "종합지"
}""",
 'BROKER': """{
  "period_covered": "3Q26",
  "report_type":    "산업",
  "target_stock":   "메모리 반도체",
  "opinion":        "BUY",
  "target_price":   260000,
  "has_table":      "Y"
}""",
 'INSTITUTION': """{
  "data_asof":     "2Q26",
  "research_type": "시장전망",
  "license_scope": "사내 열람",
  "region_scope":  "Global",
  "keywords":      ["HBM", "DRAM", "CapEx"]
}""",
 'EMAIL': """{
  "thread_id":      "TH_9901",
  "has_attachment": "Y",
  "attach_doc_ids": ["RPT_20260910_0007"],
  "quote_removed":  "Y",
  "recipients_cnt": 3
}""",
 'MEETING': """{
  "project_code": "PRJ-MIS-2026",
  "agenda_no":    2,
  "decisions":    ["4Q 전망 유지"],
  "action_items": [
    {"task": "고객별 발주 재확인", "owner": "박기록", "due": "2026-09-24"}
  ]
}""",
 'REPORT': """{
  "version":         "v1.0",
  "approval_status": "APPROVED",
  "report_kind":     "시장동향",
  "period_covered":  "3Q26",
  "file_format":     "PPTX"
}""",
 'KNOWLEDGE': """{
  "category":     "용어 정의",
  "system_name":  "MIS",
  "doc_status":   "CURRENT",
  "related_docs": ["KB_0102"]
}""",
 'ENG_REPORT': """{
  "process":           "TSV",
  "fab":               "M16",
  "test_item":         "온도별 신뢰성",
  "spec_version":      "REL-2.3",
  "has_measure_table": "Y"
}""",
 'EXEC_REPORT': """{
  "report_to":       "CEO",
  "meeting_body":    "경영회의",
  "confidentiality": "CONFIDENTIAL",
  "decision_items":  ["고객 다변화 추진"],
  "summary_slide":   2
}""",
}

TAGS_SCHEMA = """TAGS (모든 소스 공통 · 센싱과 라우팅의 근거)
{
  "company": ["마이크론", "SK하이닉스"],     // 코드 사전의 표준명으로 정규화
  "product": ["HBM", "eSSD"],
  "topic":   ["증설", "가격"],               // 센싱 축 · 하위 신호와 같은 어휘
  "region":  ["일본"],
  "event":   "CAPACITY_EXPANSION"            // 선택: 이벤트 유형 코드
}"""

ACL_SCHEMA = """RAG_DOC_ACL (권한은 JSON 이 아니라 행으로)
DOC_ID              PRINCIPAL_TYPE  PRINCIPAL_ID
EML_20260910_004412  USER            lee@company.example      ← 발신자
EML_20260910_004412  USER            pm@company.example       ← 수신자
EXE_20260911_000009  GROUP           STRATEGY_PLANNING        ← 결재선 부서
NEWS_20260915_000123 ALL             *                        ← 사외 공개

→ Milvus 에는 acl = ["lee@…","pm@…"] 처럼 배열 필드로 복제해 검색 시 필터"""

# ---------- JSON 을 쓸 때의 규칙 ----------
JSON_RULES = [
 ('승격 기준', '필터 · 권한 · 정렬 · 인용에 쓰면 공통 컬럼, 화면 표시와 참고면 JSON',
  '기간 필터에 쓰는 PUBLISHED_AT 은 컬럼. "리포트 종류"는 표시용이므로 JSON'),
 ('JSON 안의 값으로 필터하면', 'Milvus 벡터 검색과 동시에 걸기 어렵고, Oracle 에서도 함수 기반 인덱스가 필요',
  'JSON_VALUE(META_EXTRA, \'$.period_covered\') 조회는 되지만 대량 필터에는 느림'),
 ('Oracle 저장', '19c: CLOB + CHECK(IS JSON) · 21c 이상: JSON 타입. 자주 쓰는 키는 가상 컬럼 + 인덱스',
  "ALTER TABLE RAG_DOC ADD (PERIOD_COVERED AS (JSON_VALUE(META_EXTRA,'$.period_covered')))"),
 ('Milvus 복제', '필터에 쓰는 값만 스칼라 필드로. 나머지는 JSON 필드 하나로 보내 표시용으로만',
  'doc_type · published_at · security_level · acl 은 스칼라, meta 는 JSON'),
 ('키 이름 고정', '같은 뜻의 키를 소스마다 다르게 쓰지 않기. 사전을 만들어 관리',
  '대상 기간은 모든 소스에서 period_covered 로 통일'),
 ('빈 값 처리', '없는 키는 넣지 않음(null 넣지 않기). 코드에서 get(key, 기본값)으로 처리',
  '{"opinion": null} 대신 키 자체를 생략'),
]

# ---------- 사내 테이블과 매핑하는 4가지 경우 ----------
MAPPING_CASES = [
 ('① 같은 뜻의 컬럼이 이미 있다', '컬럼명만 맞춰 매핑. 값 형식(날짜 · 코드)만 통일',
  '사내 NEWS_ARTICLE.PUB_DT → PUBLISHED_AT (형식 변환)', '사내 컬럼명 칸에 그대로 적기'),
 ('② 다른 테이블에 흩어져 있다', '적재 시 조인해서 한 행으로 합치거나, 분석용 뷰를 만들어 그 뷰를 읽기',
  '기사 본문 = ARTICLE, 언론사 = PRESS_MASTER → 조인 후 ORG_NAME', '뷰 이름을 사내 컬럼명 칸에'),
 ('③ 본문에서 만들 수 있다 (파생)', '추출 규칙을 정하고 적재 파이프라인에서 생성. 규칙을 문서에 남김',
  '기관 보고서 data_asof ← 본문 "as of 2Q26" 정규식', '사내 보유 = "파생 가능"'),
 ('④ 아예 없다', '수집 단계에서 받아올 수 있는지 확인 → 불가하면 그 항목에 의존하는 기능을 접기',
  'cluster_id 가 없으면 재송고 접기 · 센싱 정확도 하락을 감수', '사내 보유 = "없음" + 비고에 영향'),
]

NOTES = [
 ('필수(M) 판단 기준', '이 값이 없으면 검색 · 권한 · 인용 중 하나가 깨지는 것만 M 으로 뒀습니다. 나머지는 R(권장) · O(선택)입니다.'),
 ('저장 위치가 핵심', '같은 항목이라도 <b>공통 컬럼 / META_EXTRA(JSON) / TAGS / ACL 행</b> 중 어디에 두느냐에 따라 검색 · 권한에서 쓸 수 있는지가 달라집니다.'),
 ('← 표기', '"ORG_NAME ← publisher" 는 소스의 그 항목을 공통 컬럼에 채우라는 뜻입니다. 소스마다 이름이 달라도 저장 위치는 하나로 모읍니다.'),
 ('권한은 행으로', '메일 수신자 · 회의 참석자 · 결재선을 JSON 배열에 두면 권한 필터로 쓸 수 없습니다. ACL 테이블 행으로 풀고 Milvus 에 배열로 복제합니다.'),
 ('날짜가 둘인 소스', '기관 보고서(발행일 vs data_asof), 지식문서(작성일 vs 최종 수정일)는 둘을 나눠 두고, 검색 기준으로 쓸 쪽을 PUBLISHED_AT 에 넣습니다.'),
 ('사내 보유 채우기', '오른쪽 두 칸을 채우면 매핑표가 됩니다. "파생 가능"은 본문이나 다른 컬럼에서 만들 수 있다는 뜻입니다(위 ③).'),
]

# ---------- 소스별 샘플 레코드 (한 건 전체) ----------
SAMPLES = {
 'NEWS': """-- RAG_DOC 한 행
DOC_ID         : NEWS_20260915_000123        SRC_SYSTEM : NEWS_CRAWL
SRC_KEY        : hankyung:2026091500123
DATA_SOURCE    : EXTERNAL   DOC_TYPE : NEWS   SECURITY_LEVEL : 0   LANG : ko
TITLE          : 마이크론, 히로시마 HBM 라인 증설
PUBLISHED_AT   : 2026-09-15 08:12   DATE_QUALITY : EXACT   COLLECTED_AT : 2026-09-15 09:00
ORG_NAME       : 한국경제    AUTHOR : 김기술    SRC_URL : https://…/2026/09/15/123
CONTENT_HASH   : a3f9…       IS_DELETED : N
TAGS           : {"company":["마이크론"],"product":["HBM"],"topic":["증설"],"region":["일본"]}
META_EXTRA     : {"category":"IT/테크","cluster_id":"EVT_20260915_HBM_MU","is_primary":"Y","press_type":"종합지"}
-- RAG_DOC_ACL : (ALL, *)""",
 'BROKER': """DOC_ID         : BRK_20260912_000031        SRC_SYSTEM : BROKER_FEED
DATA_SOURCE    : EXTERNAL   DOC_TYPE : BROKER   SECURITY_LEVEL : 1
TITLE          : 메모리 3Q 프리뷰 — 가격 상승 지속
PUBLISHED_AT   : 2026-09-12        ORG_NAME : ○○증권      AUTHOR : 이분석
TAGS           : {"company":["SK하이닉스","삼성전자"],"product":["DRAM","NAND"],"topic":["가격"]}
META_EXTRA     : {"period_covered":"3Q26","report_type":"산업","target_stock":"메모리 반도체",
                  "opinion":"BUY","target_price":260000,"has_table":"Y"}
-- 표는 CHUNK_KIND=TABLE, SECTION_PATH="표 2. 가격 전망" 으로 별도 청크""",
 'INSTITUTION': """DOC_ID         : INS_20260901_000008
TITLE          : 글로벌 HBM 시장 전망        ORG_NAME : ○○리서치
PUBLISHED_AT   : 2026-09-01   ← 발행일 (검색 기준)
META_EXTRA     : {"data_asof":"2Q26","research_type":"시장전망","license_scope":"사내 열람",
                  "region_scope":"Global","keywords":["HBM","CapEx"]}
-- 발행일과 데이터 기준 시점이 다르다. 답변에는 둘 다 표기""",
 'EMAIL': """DOC_ID         : EML_20260910_004412        SRC_KEY : <a1b2@mail>
DATA_SOURCE    : INTERNAL   DOC_TYPE : EMAIL   SECURITY_LEVEL : 2
TITLE          : RE: 4Q 발주 조정 건          PUBLISHED_AT : 2026-09-10 14:22
ORG_NAME       : 영업전략팀   AUTHOR : 이영업
META_EXTRA     : {"thread_id":"TH_9901","has_attachment":"Y",
                  "attach_doc_ids":["RPT_20260910_0007"],"quote_removed":"Y","recipients_cnt":3}
-- RAG_DOC_ACL : (USER, lee@…) (USER, pm@…) (USER, cto@…)   ← 이 세 사람만 검색됨""",
 'MEETING': """DOC_ID         : MTG_20260917_000045
TITLE          : 시장분석팀 주간회의         PUBLISHED_AT : 2026-09-17   ORG_NAME : 시장분석팀
META_EXTRA     : {"project_code":"PRJ-MIS-2026","agenda_no":2,"decisions":["4Q 전망 유지"],
                  "action_items":[{"task":"고객별 발주 재확인","owner":"박기록","due":"2026-09-24"}]}
-- RAG_DOC_ACL : (GROUP, 시장분석팀) (USER, 박기록) (USER, 최분석) (USER, 정수요)
-- 청크는 안건 단위, SECTION_PATH = "안건 2. HBM 수요 점검\"""",
 'REPORT': """DOC_ID         : RPT_20260905_000112        SECURITY_LEVEL : 1
TITLE          : 3Q 메모리 수요 점검 v1.0     PUBLISHED_AT : 2026-09-05
ORG_NAME       : 시장분석팀   AUTHOR : 최분석   FILE_PATH : \\\\fs01\\reports\\2026\\R-0905.pptx
META_EXTRA     : {"version":"v1.0","approval_status":"APPROVED","report_kind":"시장동향",
                  "period_covered":"3Q26","file_format":"PPTX"}
-- v0.9 초안은 approval_status 로 걸러 적재하지 않음 / SECTION_PATH = "슬라이드 7\"""",
 'KNOWLEDGE': """DOC_ID         : KNW_000317
TITLE          : 용어 정의 — Sufficiency Ratio
PUBLISHED_AT   : 2026-08-30   ← 최종 수정일을 넣는다   AUTHOR : 관리자(최종 수정자)
META_EXTRA     : {"category":"용어 정의","system_name":"MIS","doc_status":"CURRENT",
                  "related_docs":["KB_0102"]}
-- doc_status=OBSOLETE 는 IS_DELETED=Y 로 동기화""",
 'ENG_REPORT': """DOC_ID         : ENG_20260902_000076        SECURITY_LEVEL : 2
TITLE          : HBM4 12단 신뢰성 평가        ORG_NAME : ○○개발팀   PUBLISHED_AT : 2026-09-02
TAGS           : {"product":["HBM4-12H"],"topic":["신뢰성"]}
META_EXTRA     : {"process":"TSV","fab":"M16","test_item":"온도별 신뢰성",
                  "spec_version":"REL-2.3","has_measure_table":"Y"}
-- RAG_DOC_ACL : (GROUP, 개발팀) (GROUP, PRJ-HBM4-REL)""",
 'EXEC_REPORT': """DOC_ID         : EXE_20260911_000009        SECURITY_LEVEL : 3
TITLE          : 3Q 경영 현안                ORG_NAME : 전략기획   PUBLISHED_AT : 2026-09-11
META_EXTRA     : {"report_to":"CEO","meeting_body":"경영회의","confidentiality":"CONFIDENTIAL",
                  "decision_items":["고객 다변화 추진"],"summary_slide":2}
-- RAG_DOC_ACL : (GROUP, STRATEGY_PLANNING) (USER, A상무) (USER, B전무)
-- 그 외 계정의 검색 결과에서는 이 문서가 아예 나오지 않아야 함 (누출 테스트 대상)""",
}
