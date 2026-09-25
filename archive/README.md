# archive — 지금 당장은 안 보는 것

돌리는 데 필요한 파일은 `../docs/` 에 3개만 두었습니다. 여기는 필요할 때만 꺼내 씁니다.

## 기입용 엑셀 (평가 단계에서 필요)

| 파일 | 쓰는 노트북 |
|---|---|
| `golden_eval_pack_rev4.xlsx` | nb09 · nb10 · nb11 · nb12 |
| `rag_project_log_rev1.xlsx` | nb13 · 회차 기록 전반 |
| `metric_catalog_template_rev1.xlsx` | nb07 (채워서 `catalog/metric_catalog.xlsx` 로 저장) |
| `golden_set_example_rev2.xlsx` | 기입용 아님 — 골든셋 실물 예시 |

## 참고 문서

| 파일 | 내용 |
|---|---|
| `rag_runbook_rev1.html` | 실행 안내서 원본 (docs 의 T2 판과 내용 동일) |
| `rag_design_guide_rev4.html` | 설계 원본 — 아키텍처 · 결정 사항 |
| `rag_quest_board_rev4.html` | 항목별 옵션 · 장단점 사전 |
| `rag_stage_checklist_rev3.html` | 단계별 체크리스트 상세판 (S01~S21) |
| `rag_checklist_sheet_rev9.html` | 체크리스트 HTML 판 (엑셀 rev10 의 이전 버전) |
| `query_flow_example_rev2.html` | 혼합 질의 흐름 · 지표 정의서 작성 예시 |
| `smoke_test_20_rev1.html` | 스모크 20문항 · 실패 유형 |

## src/

문서 · 엑셀을 만든 생성 스크립트. 내용을 고쳐 다시 만들 때만 씁니다.
```
python make_run_guide.py          → docs/rag_run_guide_rev1.xlsx
python make_checklist_xlsx_rev10.py → docs/rag_checklist_rev10.xlsx
python make_project_log.py        → archive/rag_project_log_rev1.xlsx
```
