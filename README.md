# rag-lab — 사내 RAG 점검 랩

Oracle(원문·청크) → BGE-M3 → Milvus → 하이브리드 검색(BM25 + Dense/Sparse, RRF) → 리랭크 → MMR → 사내 LLM 구성의
**현재 상태를 측정하고 단계별로 비교**하기 위한 점검 코드입니다.

- **Windows + Spyder** 에서 Jupyter처럼 `# %%` 셀 단위로 실행하고, 결과는 변수 탐색기(Variable Explorer)의 DataFrame으로 봅니다.
- `LAB_MODE=sample` 이면 DB · Milvus · 모델 없이 가짜 샘플 데이터로 모든 셀이 돕니다. `SAMPLE_SET=100` 으로 100건 규모 전환. 샘플 데이터와 수치는 모두 지어낸 예시입니다.
- 사내에서는 `.env`와 `lab_config.py`의 **[사내 맞춤]** 블록만 고쳐 `LAB_MODE=live`로 씁니다. DB에는 SELECT만 합니다.

| 노트북 | 점검 내용 |
|---|---|
| `nb00_pipeline_check.py` | **적재 검증** — 문서 · 메타 · 청킹 · 인덱싱 무결성. 평가 이전에 통과해야 하는 단계 |
| `nb01_inventory.py` | 소스별 문서·청크 수, 작성일 누락, 메타 채움률, 원문 저장 형태, 중복 |
| `nb02_parse_chunk.py` | 청크 길이·max_length 초과, 문장 잘림·표 깨짐·노이즈·헤더, 소스별 정제 전후 |
| `nb03_bm25_tokenizer.py` | 공백 / 조사 제거 / Kiwi 토크나이저 비교, BM25 적중률 |
| `nb04_milvus.py` | Milvus 스키마·인덱스·필수 필드, Oracle과 건수 정합성, 필터 검색 |
| `nb05_smoke_test.py` | 스모크 20문항 실행 → 판정용 엑셀 → 실패 유형 집계 |
| `nb06_retrieval_eval.py` | 골든셋으로 BM25 / Dense / Sparse / Hybrid / +Rerank / +MMR 비교 |
| `nb08`~`nb12` | 자동 평가셋 · 골든셋 구성 · 답변 평가 · 근거 문서 연결 · **LLM 골든셋 생성** |
| `nb13_langgraph_rag.py` | **LangGraph RAG** — 노드 구성(프리셋)별 지표 비교로 개선 폭 정량화 |
| `nb07_sql_router.py` | **정형 데이터 연계(Phase 3)** — 지표 카탈로그 · 질의 라우팅 · SQL 생성/정적검증/실행 · 결합 · 실행결과 정확도 |

정형 연계(nb07)는 `catalog/metric_catalog.xlsx`(지표 정의서)를 채운 뒤 씁니다. 예시 파일이 함께 들어 있고, 샘플 모드에서는 SQLite 샘플 DB로 SQL 이 실제로 돕니다.

설치 · 설정 · 셀별 설명은 **[USAGE.md](USAGE.md)** 를 봅니다.

먼저 읽을 문서: **[docs/rag_runbook_t2_rev1.html](docs/rag_runbook_t2_rev1.html)** — 전체 그림 · 준비 · 실행 순서 · 지표 읽는 법 · 고도화 방법.
실행 순서는 **[docs/rag_run_guide_rev1.xlsx](docs/rag_run_guide_rev1.xlsx)**, 점검 항목은 **[docs/rag_checklist_rev10.xlsx](docs/rag_checklist_rev10.xlsx)** 를 봅니다.

돌리는 데 필요한 문서는 **[docs/](docs/)** 에 3개만 두었고, 나머지(기입용 엑셀 · 설계 문서 · 생성 스크립트)는 **[archive/](archive/)** 에 있습니다.

```text
%cd C:\work\rag_lab
%pip install -r requirements.txt
copy .env.example .env        (명령 프롬프트)
```
