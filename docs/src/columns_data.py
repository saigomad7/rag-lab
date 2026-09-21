# -*- coding: utf-8 -*-
"""
소스별 컬럼 정의서 — 소스 유형마다 어떤 컬럼이 있어야 하는가 (권장안)
행 = (컬럼명, 논리명, 타입, 필수, 어디서 오나, 쓰이는 곳(단계), 샘플값)
  필수: M=반드시 / R=권장 / O=선택
"""
M, R, O = 'M', 'R', 'O'

# ---------- 모든 소스 공통 (문서 단위 = RAG_DOC) ----------
COMMON_DOC = [
 ('DOC_ID', '문서 고유 ID', 'VARCHAR2(64)', M, '적재 시 생성 (소스코드+일자+일련)', 'S01 · 전 단계 키', 'NEWS_20260915_000123'),
 ('SRC_SYSTEM', '원천 시스템', 'VARCHAR2(32)', M, '수집 모듈', 'S01 증분 · 재수집', 'NEWS_CRAWL'),
 ('SRC_KEY', '원천 키', 'VARCHAR2(200)', M, '원천 시스템의 PK · URL · Message-ID', 'S01 중복 · 갱신 판정', 'hankyung:2026091500123'),
 ('DATA_SOURCE', '사외/사내', 'VARCHAR2(16)', M, '수집 경로', 'S10 필터 · S28 권한', 'EXTERNAL'),
 ('DOC_TYPE', '문서 유형', 'VARCHAR2(32)', M, '수집 경로 · 분류', 'S03 청킹 규칙 · S10 필터', 'NEWS'),
 ('TITLE', '제목', 'VARCHAR2(1000 CHAR)', M, '원문', 'S03 헤더 · S14 인용', '마이크론, 히로시마 HBM 라인 증설'),
 ('PUBLISHED_AT', '작성 · 발행일시', 'DATE', M, '원문 (없으면 NULL)', 'S08 기간필터 · S12 최신성 · S19 센싱', '2026-09-15 08:12'),
 ('DATE_QUALITY', '날짜 품질', 'VARCHAR2(10)', R, 'EXACT / ESTIMATED / MISSING', 'S08 필터 신뢰도', 'EXACT'),
 ('COLLECTED_AT', '수집일시', 'DATE', M, '수집 모듈', 'S01 운영 · 지연 점검', '2026-09-15 09:00'),
 ('ORG_NAME', '기관 · 부서', 'VARCHAR2(200 CHAR)', M, '언론사 · 증권사 · 기관 · 작성 부서', 'S03 헤더 · S14 인용 · 필터', '한국경제'),
 ('AUTHOR', '작성자', 'VARCHAR2(200 CHAR)', R, '기자 · 애널리스트 · 작성자', 'S14 인용', '김기술'),
 ('SRC_URL', '원문 링크 · 경로', 'VARCHAR2(2000)', R, 'URL 또는 파일 경로', 'UI 원문 이동 · 재파싱', 'https://…/2026/09/15/123'),
 ('FILE_PATH', '원본 파일 경로', 'VARCHAR2(1000)', R, '파일 서버 · 그룹웨어', '처리흐름 0번(재파싱 가능 여부)', '\\\\fs01\\reports\\2026\\R-0912.pptx'),
 ('LANG', '언어', 'VARCHAR2(8)', R, '판별 또는 소스 고정', 'S08 질의 확장', 'ko'),
 ('SECURITY_LEVEL', '보안 등급', 'NUMBER(1)', M, '0 공개 1 사내 2 대외비 3 임원', 'S10 필터 · S28 권한', '0'),
 ('CONTENT_HASH', '본문 해시', 'VARCHAR2(64)', M, 'SHA-256(정제 본문)', 'S01 중복 · 변경 감지', 'a3f9…'),
 ('TAGS', '태그(JSON)', 'CLOB(JSON)', R, 'LLM 추출 + 사전', 'S05 · S19 센싱 · S24 라우팅', '{"company":["마이크론"],"product":["HBM"]}'),
 ('META_EXTRA', '가변 메타(JSON)', 'CLOB(JSON)', M, '소스별 고유 항목 (아래 표)', 'S05 표시 · 보조 필터', '{"category":"IT/테크"}'),
 ('IS_DELETED', '삭제 여부', 'CHAR(1)', M, '원천 삭제 · 폐기 반영', 'S06 동기화', 'N'),
 ('UPD_DATE', '갱신일시', 'DATE', M, '적재 시각', 'S06 증분 동기화', '2026-09-15 09:00'),
]

# ---------- 청크 단위 (RAG_CHUNK) ----------
COMMON_CHUNK = [
 ('CHUNK_ID', '청크 ID', 'VARCHAR2(100)', M, 'DOC_ID + 순번', 'S06 Milvus PK', 'NEWS_20260915_000123_0001'),
 ('DOC_ID', '문서 ID', 'VARCHAR2(64)', M, 'RAG_DOC 참조', '인용 · 문서당 상한', 'NEWS_20260915_000123'),
 ('CHUNK_SEQ', '순번', 'NUMBER(6)', M, '분할 순서', '인접 확장', '1'),
 ('PARENT_ID', '부모 청크', 'VARCHAR2(100)', O, 'Parent-Child 구조', 'S03-4 · S13 확장', ''),
 ('CHUNK_KIND', '청크 종류', 'VARCHAR2(10)', R, 'TEXT / TABLE / SUMMARY', 'S03 표 분리 · 수치 질문', 'TEXT'),
 ('SECTION_PATH', '섹션 경로', 'VARCHAR2(1000 CHAR)', R, '헤딩 · 안건 · 슬라이드 번호', 'S03 헤더 · 인용', '3. 공급 > 3.2 DRAM 증설'),
 ('HEADER_TEXT', '문맥 헤더', 'VARCHAR2(1000 CHAR)', M, '[유형|날짜|기관|제목|섹션] 생성', 'S03-3 · S04 dense 입력', '[뉴스 | 2026-09-15 | 한국경제 | 마이크론…]'),
 ('CHUNK_TEXT', '청크 본문', 'CLOB', M, '정제 후 분할', 'S04 임베딩 · S12 리랭크', '마이크론이 일본 히로시마 공장에…'),
 ('TOKEN_CNT', '토큰 수', 'NUMBER(6)', R, '임베딩 토크나이저', 'S04-1 잘림 점검', '412'),
 ('CHUNKER_VER', '청커 버전', 'VARCHAR2(16)', R, '분할 규칙 버전', '재청킹 비교', 'v2'),
]

# ---------- 소스별 고유 (META_EXTRA 키 또는 전용 컬럼) ----------
PER_SOURCE = {
 'NEWS': ('뉴스', [
   ('publisher', '언론사', 'VARCHAR2(100)', M, '수집 메타 (= ORG_NAME)', '필터 · 인용', '한국경제'),
   ('reporter', '기자', 'VARCHAR2(100)', R, '기사 바이라인', '인용', '김기술'),
   ('category', '분야', 'VARCHAR2(50)', R, '언론사 분류', '필터 · 센싱 축 매핑', 'IT/테크'),
   ('cluster_id', '사건 묶음 ID', 'VARCHAR2(64)', R, '근사 중복(MinHash) 묶음 대표', 'S01 재송고 · S18 센싱', 'EVT_20260915_HBM_MU'),
   ('is_primary', '대표 기사', 'CHAR(1)', R, '묶음 중 가장 이른 기사', '중복 접기', 'Y'),
   ('press_type', '매체 유형', 'VARCHAR2(20)', O, '종합지 · 산업지 · 통신사', '가중치', '종합지'),
 ]),
 'BROKER': ('증권사 리포트', [
   ('firm_name', '증권사', 'VARCHAR2(100)', M, '리포트 표지 (= ORG_NAME)', '필터 · 인용', '○○증권'),
   ('analyst', '애널리스트', 'VARCHAR2(100)', R, '표지 · 말미', '인용', '이분석'),
   ('report_type', '리포트 종류', 'VARCHAR2(30)', R, '산업 · 기업 · 프리뷰 · 리뷰', '필터', '산업'),
   ('target_stock', '대상 종목 · 산업', 'VARCHAR2(200)', R, '표지', '필터 · 센싱', '메모리 반도체'),
   ('opinion', '투자의견', 'VARCHAR2(20)', O, '표지', '센싱(논조)', 'BUY'),
   ('target_price', '목표가', 'NUMBER', O, '표지', '센싱', '260000'),
   ('period_covered', '대상 기간', 'VARCHAR2(20)', R, '제목 · 본문', 'S08 기간 필터', '3Q26'),
   ('has_table', '표 포함', 'CHAR(1)', R, '파싱 결과', 'S03 표 청크 분리', 'Y'),
 ]),
 'INSTITUTION': ('기관 보고서', [
   ('institution_name', '기관명', 'VARCHAR2(100)', M, '표지 (= ORG_NAME)', '필터 · 인용', '○○리서치'),
   ('research_type', '자료 유형', 'VARCHAR2(30)', R, '시장전망 · 통계 · 백서', '필터', '시장전망'),
   ('data_asof', '데이터 기준 시점', 'VARCHAR2(20)', M, '본문 "as of" · 표 머리말', 'S08 기간 · S27 정합성', '2Q26'),
   ('license_scope', '라이선스 범위', 'VARCHAR2(50)', R, '계약 정보', 'S28 권한', '사내 열람'),
   ('region_scope', '지역 범위', 'VARCHAR2(50)', O, '표지 · 목차', '필터', 'Global'),
   ('keywords', '키워드', 'VARCHAR2(500)', O, '표지 · 목차', '센싱 태그', 'HBM;DRAM;CapEx'),
 ]),
 'EMAIL': ('메일', [
   ('message_id', 'Message-ID', 'VARCHAR2(200)', M, '메일 헤더 (= SRC_KEY)', '중복 · 스레드', '<a1b2@mail>'),
   ('thread_id', '스레드 ID', 'VARCHAR2(100)', M, 'In-Reply-To 추적', 'S03 스레드 청킹', 'TH_9901'),
   ('sender', '발신자', 'VARCHAR2(200)', M, '메일 헤더', 'S28 ACL · 인용', 'lead@company.example'),
   ('recipients', '수신자 목록', 'CLOB(JSON)', M, 'To + Cc', 'S28 ACL(행 권한)', '["pm@…","cto@…"]'),
   ('sender_dept', '발신 부서', 'VARCHAR2(100)', R, '조직도 매핑', '필터 · 권한', '영업전략팀'),
   ('has_attachment', '첨부 유무', 'CHAR(1)', M, '메일 파싱', '첨부 분리 처리', 'Y'),
   ('attach_doc_ids', '첨부 문서 ID', 'CLOB(JSON)', R, '첨부를 별도 문서로 적재', '처리흐름(첨부 분기)', '["RPT_20260910_0007"]'),
   ('quote_removed', '인용 제거 여부', 'CHAR(1)', R, '정제 단계 기록', 'S02 품질 점검', 'Y'),
 ]),
 'MEETING': ('회의록', [
   ('meeting_date', '회의일', 'DATE', M, '양식 (= PUBLISHED_AT)', '기간 필터', '2026-09-17'),
   ('department', '주관 부서', 'VARCHAR2(100)', M, '양식', '권한 · 필터', '시장분석팀'),
   ('attendees', '참석자', 'CLOB(JSON)', M, '양식', 'S28 ACL · 인용', '["박기록","최분석"]'),
   ('project_code', '과제 코드', 'VARCHAR2(50)', R, '양식', '필터 · 권한', 'PRJ-MIS-2026'),
   ('agenda_no', '안건 번호', 'NUMBER(3)', R, '분할 시 부여', 'S03 안건 단위 청킹', '2'),
   ('decisions', '결정 사항', 'CLOB(JSON)', R, '본문 추출', '질문 응답(무엇을 정했나)', '["4Q 전망 유지"]'),
   ('action_items', '액션 아이템', 'CLOB(JSON)', R, '본문 추출 (담당 · 기한)', '질문 응답 · 추적', '[{"task":"발주 재확인","owner":"박기록","due":"2026-09-24"}]'),
 ]),
 'REPORT': ('사내 보고서', [
   ('department', '작성 부서', 'VARCHAR2(100)', M, '문서 속성 · 결재 정보', '권한 · 필터', '시장분석팀'),
   ('version', '버전', 'VARCHAR2(20)', M, '파일명 · 표지', 'S01 최종본 판정', 'v1.0'),
   ('approval_status', '결재 상태', 'VARCHAR2(20)', M, '그룹웨어', '최종본만 적재', 'APPROVED'),
   ('report_kind', '보고서 종류', 'VARCHAR2(30)', R, '표지', '필터', '시장동향'),
   ('period_covered', '대상 기간', 'VARCHAR2(20)', R, '제목 · 본문', '기간 필터', '3Q26'),
   ('file_format', '원본 형식', 'VARCHAR2(10)', R, '파일 확장자', 'S02 파서 분기', 'PPTX'),
   ('slide_no', '슬라이드 번호', 'NUMBER(4)', R, '청크 생성 시', '인용 위치', '7'),
 ]),
 'KNOWLEDGE': ('지식문서', [
   ('category', '분류', 'VARCHAR2(100)', M, 'KMS 분류 체계', '필터', '용어 정의'),
   ('system_name', '대상 시스템 · 업무', 'VARCHAR2(100)', R, 'KMS 속성', '필터', 'MIS'),
   ('last_updated_at', '최종 수정일', 'DATE', M, 'KMS (= PUBLISHED_AT 로 사용)', 'S08 최신성', '2026-08-30'),
   ('last_updated_by', '최종 수정자', 'VARCHAR2(100)', R, 'KMS', '인용 · 문의처', '관리자'),
   ('doc_status', '문서 상태', 'VARCHAR2(20)', M, '현행 / 개정중 / 폐기', '폐기본 제외', 'CURRENT'),
   ('related_docs', '관련 문서', 'CLOB(JSON)', O, 'KMS 링크', '추가 탐색', '["KB_0102"]'),
 ]),
 'ENG_REPORT': ('엔지니어 보고서', [
   ('process', '공정', 'VARCHAR2(50)', M, '문서 속성 · 본문', '필터 · 권한', 'TSV'),
   ('product', '제품', 'VARCHAR2(50)', M, '문서 속성', '필터 · 코드값 사전 연결', 'HBM4-12H'),
   ('fab', 'Fab · 라인', 'VARCHAR2(30)', R, '문서 속성', '필터 · 권한', 'M16'),
   ('test_item', '평가 항목', 'VARCHAR2(100)', R, '본문 · 표 제목', '수치 질문', '온도별 신뢰성'),
   ('spec_version', '규격 버전', 'VARCHAR2(30)', O, '본문', '버전 구분', 'REL-2.3'),
   ('project_code', '과제 코드', 'VARCHAR2(50)', R, '문서 속성', 'S28 과제 그룹 권한', 'PRJ-HBM4-REL'),
   ('has_measure_table', '측정 표 포함', 'CHAR(1)', R, '파싱 결과', '표 청크 분리', 'Y'),
 ]),
 'EXEC_REPORT': ('임원 보고서', [
   ('report_to', '보고 대상', 'VARCHAR2(100)', M, '표지 · 결재선', 'S28 ACL', 'CEO'),
   ('meeting_body', '보고 회의체', 'VARCHAR2(100)', R, '표지', '필터', '경영회의'),
   ('approval_line', '결재선', 'CLOB(JSON)', M, '그룹웨어', 'S28 ACL(열람 가능자)', '["A상무","B전무"]'),
   ('decision_items', '결정 · 지시 사항', 'CLOB(JSON)', R, '본문 추출', '질문 응답 · 추적', '["고객 다변화 추진"]'),
   ('confidentiality', '대외 등급', 'VARCHAR2(20)', M, '표지 표기', 'S28 (등급 3 고정)', 'CONFIDENTIAL'),
   ('summary_slide', '요약 슬라이드 번호', 'NUMBER(4)', R, '파싱', '리랭크 가중', '2'),
 ]),
}

# ---------- 소스별 샘플 레코드 (핵심 컬럼만) ----------
SAMPLES = {
 'NEWS': """DOC_ID        : NEWS_20260915_000123
DATA_SOURCE   : EXTERNAL      DOC_TYPE : NEWS      SECURITY_LEVEL : 0
TITLE         : 마이크론, 히로시마 HBM 라인 증설
PUBLISHED_AT  : 2026-09-15 08:12   DATE_QUALITY : EXACT   COLLECTED_AT : 2026-09-15 09:00
ORG_NAME      : 한국경제      AUTHOR : 김기술      SRC_URL : https://…/2026/09/15/123
TAGS          : {"company":["마이크론"],"product":["HBM"],"topic":["증설"]}
META_EXTRA    : {"category":"IT/테크","cluster_id":"EVT_20260915_HBM_MU","is_primary":"Y","press_type":"종합지"}""",
 'BROKER': """DOC_ID        : BRK_20260912_000031
DATA_SOURCE   : EXTERNAL      DOC_TYPE : BROKER    SECURITY_LEVEL : 1
TITLE         : 메모리 3Q 프리뷰 — 가격 상승 지속
PUBLISHED_AT  : 2026-09-12        ORG_NAME : ○○증권      AUTHOR : 이분석
META_EXTRA    : {"report_type":"산업","target_stock":"메모리 반도체","opinion":"BUY",
                 "period_covered":"3Q26","has_table":"Y"}
※ 표는 CHUNK_KIND=TABLE 로 분리, SECTION_PATH = "표 2. 가격 전망\"""",
 'INSTITUTION': """DOC_ID        : INS_20260901_000008
TITLE         : 글로벌 HBM 시장 전망      ORG_NAME : ○○리서치
PUBLISHED_AT  : 2026-09-01   ← 발행일
META_EXTRA    : {"data_asof":"2Q26","research_type":"시장전망","license_scope":"사내 열람"}
※ 발행일과 데이터 기준 시점(data_asof)이 다르다. 둘 다 없으면 "최신 자료"가 틀린다.""",
 'EMAIL': """DOC_ID        : EML_20260910_004412
DATA_SOURCE   : INTERNAL      DOC_TYPE : EMAIL     SECURITY_LEVEL : 2
TITLE         : RE: 4Q 발주 조정 건        PUBLISHED_AT : 2026-09-10 14:22
ORG_NAME      : 영업전략팀    AUTHOR : 이영업
META_EXTRA    : {"thread_id":"TH_9901","sender":"lead@…","recipients":["pm@…","cto@…"],
                 "has_attachment":"Y","attach_doc_ids":["RPT_20260910_0007"],"quote_removed":"Y"}
ACL(별도 테이블): USER lead@… / USER pm@… / USER cto@…""",
 'MEETING': """DOC_ID        : MTG_20260917_000045
TITLE         : 시장분석팀 주간회의       PUBLISHED_AT : 2026-09-17
ORG_NAME      : 시장분석팀
META_EXTRA    : {"attendees":["박기록","최분석","정수요"],"project_code":"PRJ-MIS-2026",
                 "agenda_no":2,"decisions":["4Q 전망 유지"],
                 "action_items":[{"task":"고객별 발주 재확인","owner":"박기록","due":"2026-09-24"}]}
※ 청크는 안건 단위. SECTION_PATH = "안건 2. HBM 수요 점검\"""",
 'REPORT': """DOC_ID        : RPT_20260905_000112
TITLE         : 3Q 메모리 수요 점검 v1.0   PUBLISHED_AT : 2026-09-05   SECURITY_LEVEL : 1
ORG_NAME      : 시장분석팀    AUTHOR : 최분석    FILE_PATH : \\\\fs01\\reports\\2026\\R-0905.pptx
META_EXTRA    : {"version":"v1.0","approval_status":"APPROVED","report_kind":"시장동향",
                 "period_covered":"3Q26","file_format":"PPTX","slide_no":7}
※ v0.9 초안은 approval_status 로 걸러 적재하지 않는다.""",
 'KNOWLEDGE': """DOC_ID        : KNW_000317
TITLE         : 용어 정의 — Sufficiency Ratio
PUBLISHED_AT  : 2026-08-30   ← 최종 수정일을 작성일로 사용
ORG_NAME      : MIS          META_EXTRA : {"category":"용어 정의","system_name":"MIS",
                 "doc_status":"CURRENT","last_updated_by":"관리자"}
※ doc_status=OBSOLETE 는 적재 제외 또는 IS_DELETED=Y""",
 'ENG_REPORT': """DOC_ID        : ENG_20260902_000076
TITLE         : HBM4 12단 신뢰성 평가      SECURITY_LEVEL : 2
ORG_NAME      : ○○개발팀     PUBLISHED_AT : 2026-09-02
META_EXTRA    : {"process":"TSV","product":"HBM4-12H","fab":"M16","test_item":"온도별 신뢰성",
                 "project_code":"PRJ-HBM4-REL","has_measure_table":"Y"}
ACL: GROUP 개발팀 / GROUP PRJ-HBM4-REL""",
 'EXEC_REPORT': """DOC_ID        : EXE_20260911_000009
TITLE         : 3Q 경영 현안              SECURITY_LEVEL : 3
ORG_NAME      : 전략기획     PUBLISHED_AT : 2026-09-11
META_EXTRA    : {"report_to":"CEO","meeting_body":"경영회의","confidentiality":"CONFIDENTIAL",
                 "approval_line":["A상무","B전무"],"summary_slide":2}
ACL: GROUP 전략기획 / USER A상무 / USER B전무   ← 그 외 검색 결과에서 제외""",
}

NOTES = [
 ('필수(M) 판단 기준', '이 컬럼이 없으면 검색 · 권한 · 인용 중 하나가 깨지는 것만 M 으로 뒀습니다. 나머지는 R(권장) · O(선택)입니다.'),
 ('공통 컬럼 우선', '필터 · 권한 · 정렬 · 인용에 쓰는 값은 META_EXTRA(JSON)가 아니라 공통 컬럼으로 올립니다. JSON 안의 값으로는 벡터 검색과 동시에 필터를 걸기 어렵습니다.'),
 ('권한은 별도 테이블', '메일 수신자 · 결재선은 JSON 에 두면 권한 필터로 쓸 수 없습니다. RAG_DOC_ACL 행으로 풀어 넣고, Milvus 에는 acl 배열로 복제합니다.'),
 ('날짜가 둘인 소스', '기관 보고서(발행일 vs 데이터 기준 시점), 지식문서(작성일 vs 최종 수정일)는 반드시 둘을 나눠 두고, 검색 기준으로 쓸 쪽을 PUBLISHED_AT 에 넣습니다.'),
 ('사내 보유 여부 채우기', '오른쪽 두 칸(사내 보유 · 사내 컬럼명)을 채우면 그대로 매핑표가 됩니다. "파생 가능"은 다른 컬럼이나 본문에서 만들 수 있다는 뜻입니다.'),
]
