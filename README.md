# rag-lab — 사내 RAG 점검 랩

Oracle(원문·청크) → BGE-M3 → Milvus → 하이브리드 검색(BM25 + Dense/Sparse, RRF) → 리랭크 → MMR → 사내 LLM 구성의
**현재 상태를 측정하고 단계별로 비교**하기 위한 점검 코드입니다.

- **Windows + Spyder** 에서 Jupyter처럼 `# %%` 셀 단위로 실행하고, 결과는 변수 탐색기(Variable Explorer)의 DataFrame으로 봅니다.
- `LAB_MODE=sample` 이면 DB · Milvus · 모델 없이 가짜 샘플 데이터로 모든 셀이 돕니다. 샘플 데이터와 수치는 모두 지어낸 예시입니다.
- 사내에서는 `.env`와 `lab_config.py`의 **[사내 맞춤]** 블록만 고쳐 `LAB_MODE=live`로 씁니다. DB에는 SELECT만 합니다.

| 노트북 | 점검 내용 |
|---|---|
| `nb01_inventory.py` | 소스별 문서·청크 수, 작성일 누락, 메타 채움률, 원문 저장 형태, 중복 |
| `nb02_parse_chunk.py` | 청크 길이·max_length 초과, 문장 잘림·표 깨짐·노이즈·헤더, 소스별 정제 전후 |
| `nb03_bm25_tokenizer.py` | 공백 / 조사 제거 / Kiwi 토크나이저 비교, BM25 적중률 |
| `nb04_milvus.py` | Milvus 스키마·인덱스·필수 필드, Oracle과 건수 정합성, 필터 검색 |
| `nb05_smoke_test.py` | 스모크 20문항 실행 → 판정용 엑셀 → 실패 유형 집계 |
| `nb06_retrieval_eval.py` | 골든셋으로 BM25 / Dense / Sparse / Hybrid / +Rerank / +MMR 비교 |

설치 · 설정 · 셀별 설명은 **[USAGE.md](USAGE.md)** 를 봅니다.

```text
%cd C:\work\rag_lab
%pip install -r requirements.txt
copy .env.example .env        (명령 프롬프트)
```
