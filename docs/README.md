# docs — 점검 · 설계 문서

HTML 파일은 **더블클릭하면 브라우저에서 바로 열립니다**(스크립트·외부 연결 없음, 휴대폰에서도 열림).
xlsx 는 엑셀에서 열어 직접 고치며 씁니다.

## 먼저 볼 것

| 파일 | 무엇 |
|---|---|
| `rag_checklist_sheet_rev4.html` | **★ 진행 기준** — 스프레드시트 형식 체크리스트. 요약 · 소스별 매트릭스 · 소스별 상세 · 소스별 처리 흐름 · P1 적재/검색 · P2 센싱 · **P3 정형연계** · 정형연계 흐름 · 스모크 20 |
| `rag_checklist_rev4.xlsx` | 위 체크리스트의 **엑셀판** — 상태 드롭다운, 요약 자동 계산(수식). 사내에서 채워 가며 쓰는 용도 |
| `metric_catalog_template_rev1.xlsx` | **지표 정의서 양식**(S22) — 채워서 `catalog/metric_catalog.xlsx` 로 저장하면 `nb07_sql_router.py` 가 읽음 |

## 이해용

| 파일 | 무엇 |
|---|---|
| `query_flow_example_rev2.html` | 질의 1건이 **비정형(문서) + 정형(DB)** 을 함께 도는 과정 + 부록 "지표 정의서는 이렇게 만든다" |
| `smoke_test_20_rev1.html` | 스모크 테스트 20문항과 실패 유형 5종 · 집계표 (S07-1) |
| `rag_design_guide_rev4.html` | 설계 원본 — 아키텍처, 결정 D1~D6, Oracle · Milvus 스키마, Phase 2 센싱 설계 |
| `rag_quest_board_rev4.html` | 항목별 **옵션 · 장단점 · 완료 조건** 사전 (Q00~Q40) |
| `rag_stage_checklist_rev3.html` | 단계별 체크리스트 상세판 (S01~S21, 103항목) |

## src/

문서를 만든 파이썬 스크립트입니다. 내용을 고칠 때는 데이터 파일(`sources_data.py`, `flows_data.py`, `phase3_data.py`)만 고치고 `make_*.py` 를 다시 실행하면 같은 모양으로 다시 만들어집니다. (pandas · openpyxl 필요)

## 단계 번호

- **S01~S06** 적재(수집 · 파싱 · 청킹 · 임베딩 · 메타 · 벡터DB) · **S07~S15** 검색(질의 · BM25 · 시맨틱 · 결합 · 리랭크 · 컨텍스트 · 답변 · 평가)
- **S16~S21** 마켓 센싱(Phase 2) · **S22~S29** 정형 데이터 연계(Phase 3)
- 코드(`nb01`~`nb07`)가 각 단계의 현 수준을 실제 값으로 채웁니다.

> 문서 안의 수치 · 회사명 · 문서 예시는 모두 **설명용으로 지어낸 값**입니다.
