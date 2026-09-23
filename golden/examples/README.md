# golden/examples — 골든셋 실물 예시 (샘플 데이터 생성분)

| 파일 | 내용 | 생성 방법 |
|---|---|---|
| `manual_golden_example.csv` | 수동 골든셋 (질문 · 유형 · 정답 문서 · 정답 문장) | 사람 작성 |
| `auto_known_item_example.csv` | 문서 문장 = 질의 · 정답 = 그 문서 | `nb08` L1 · 라벨 0건 |
| `auto_title_example.csv` | 제목 = 질의 | `nb08` L1b |
| `auto_synthetic_example.csv` | 사내 LLM 생성 질문 | `nb08` L2 |
| `sql_golden_example.csv` | 질문 → 정답 SQL (채점: 실행 결과 값 일치) | 수동 · `nb07` |

- 실제 사용 파일: `golden/golden_v1.csv`(수동) · `golden/sql_golden_v1.csv`(정형) · `nb08` 실행 시 `out/` 자동 생성분
- 정답 표기: `gold_doc_ids` 복수 시 `;` 구분 · `gold_text` = 문서 내 정답 문장 (청크 ID 금지)
- 판정: doc_id 일치 + 정답 문장 3-gram 겹침 ≥ 0.5
