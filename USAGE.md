# RAG 점검 랩 (rag_lab) 사용법

체크리스트(S01~S15)의 **현 수준 칸을 실제 값으로 채우기 위한 코드**입니다.
Spyder에서 셀 단위로 실행하고, 결과는 **Variable Explorer**의 DataFrame과 콘솔 출력으로 봅니다.

- 사내 연결 없이 먼저 돌려 볼 수 있습니다 (`LAB_MODE=sample`, 가짜 데이터 16건).
- 사내에서는 `.env`와 `lab_config.py`의 **[사내 맞춤]** 블록만 고치면 됩니다 (`LAB_MODE=live`).
- 결과표는 `out/` 폴더에 CSV와 xlsx로 저장됩니다.

---

## 0. 사내 반입 전 — 개인 노트북에서 연습

사내 DB 없이 샘플 문서 16건으로 전 과정을 돌려볼 수 있습니다.

| 방법 | `.env` 설정 | 결과 |
|---|---|---|
| A. 구조 파악 | `LAB_MODE=sample` (기본) | 검색·지표·표 구조 확인. **답변·골든셋 생성은 stub** |
| B. 실제 동작 (권장) | `LAB_MODE=sample` + `SAMPLE_MODELS=true` + `EMBED_MODE=api` + `LLM_URL` | 샘플 문서 + **실제 임베딩·LLM 호출** → nb12·nb10·nb13 이 진짜로 동작 |

B 는 `.env.example` 하단의 `[개인 노트북 학습용]` 주석 블록을 풀어 쓰면 됩니다.
샘플 문서는 지어낸 예시이므로 외부 API 사용에 문제가 없습니다.
**사내 PC 에서는 이 블록을 쓰지 않습니다** (사내 데이터 외부 전송 금지).

연습 순서: `nb01`·`nb02` → `nb03`·`nb06` → `nb12` → `nb10` → `nb13` → `nb00`

---

## 1. 폴더 구성

| 파일 | 역할 |
|---|---|
| `nb00_pipeline_check.py` | **적재 파이프라인 검증** — 통합 문서 · 메타 · 청킹 · 인덱싱 무결성 점검 · 미달 항목 목록 (평가 이전 필수) |
| `nb01_inventory.py` | 소스별 문서·청크 수, 작성일 누락, 메타 채움률, 원문 저장 형태, 중복 → **S01 · S05** |
| `nb02_parse_chunk.py` | 청크 길이·max_length 초과, 문장 잘림·표 깨짐·노이즈·헤더, 소스별 정제 전후 → **S02 · S03 · S04-1** |
| `nb03_bm25_tokenizer.py` | 공백 / 조사 제거 / Kiwi 토크나이저 비교, BM25 적중률 → **S09** |
| `nb04_milvus.py` | Milvus 버전·스키마·인덱스, 필수 필드, Oracle과 건수 비교, 필터 검색 → **S06 · S10-2** |
| `nb05_smoke_test.py` | 스모크 20문항 실행 → 판정용 엑셀 → 실패 유형 집계 → **S07-1** |
| `nb06_retrieval_eval.py` | 골든셋으로 BM25 / Dense / Sparse / Hybrid(RRF) / +Rerank / +MMR 비교 → **S15 · S11 · S12** |
| `nb07_sql_router.py` | **정형 데이터 연계** — 카탈로그 · 라우팅 · SQL 생성 · 정적 검증 · 실행 · 결합 · 평가(EX) → **S22~S29 (Phase 3)** |
| `nb08_auto_eval.py` | **골든셋 없이 정량 평가** — 사내 DB 로 평가셋 자동 생성(known-item · 제목 · 중복쌍 · 합성 QA) · 기준 대비 판정 → **S15** |
| `nb09_golden_build.py` | **골든셋 구성 → 정량 평가** — 자동셋 → 검수 시트 → 골든셋 확정 → 측정 → 실행 기록 · 문항별 결과 (골든_평가_팩 엑셀 연계) |
| `nb11_evidence_link.py` | **질문 ↔ 근거 문서 연결** — 질문 은행을 골든셋으로 전환 · 근거 확보율 · 수집 공백 목록 (검색 실패 / 문서 부재 구분) |
| `nb12_golden_llm.py` | **LLM 기반 골든셋 생성** — 코퍼스 표본 → 질문 · 정답 · 근거 생성 → 자가 검증 → 검수 시트 → 확정 |
| `nb13_langgraph_rag.py` | **LangGraph RAG · 고도화** — 노드별 실행 추적 · 프리셋별 지표 비교 · 개선 폭 정량화 · 퇴행 문항 |
| `nb10_answer_eval.py` | **답변 품질 정량 평가** — 표준 지표(Faithfulness · Answer Relevancy · Context Recall · Citation · Refusal 등) auto 계산 + 사내 LLM judge |
| `lab_config.py` | 설정. **[사내 맞춤] 블록만 수정** |
| `lab_io.py` | Oracle 읽기 · 샘플 · 결과 저장 |
| `lab_text.py` | 토큰 수, 소스별 정제 규칙, 점검 지표, 헤더, 근사 중복(MinHash) |
| `lab_search.py` | 토크나이저, BM25, RRF, MMR, BGE-M3, 리랭커, Milvus, 기존 검색 API, 사내 LLM |
| `lab_eval.py` | 적중 판정 · Hit/Recall/MRR/nDCG · 스모크 표 |
| `lab_sample.py` | 샘플 데이터 (sample 모드 전용) |
| `lab_sql.py` | 카탈로그 읽기 · 라우팅 · SQL 생성/검증/실행 · 실행결과 정확도 |
| `lab_sample_sql.py` | 샘플 정형 DB(SQLite) · 정형 골든셋 (sample 모드 전용) |
| `lab_autoeval.py` | 평가셋 자동 생성 · 합격 기준(CRITERIA) · 표본 오차 |
| `lab_pipeline.py` | 적재 무결성 점검 — 단계별 기준(CRITERIA) · 소스별 필수 메타 |
| `lab_golden_llm.py` | LLM 골든셋 생성 · 자가 검증 · 유형 배분 · 검수 시트 |
| `lab_graph.py` | LangGraph RAG 그래프(route · decompose · retrieve · grade · rewrite · generate · verify) · 프리셋 비교 |
| `lab_ragas.py` | 표준 지표 16종 — 검색(IR) · 생성(RAGAS 계열) · 운영 · LLM 채점 프롬프트 |
| `golden/answer_golden_v1.csv` | 질의 · 답변 골든셋 60문항 (사외 정보 기반 · 필수 요소 채점) |
| `catalog/metric_catalog_example.xlsx` | 지표 정의서 **예시** — 채운 파일은 `catalog/metric_catalog.xlsx` 로 저장 |
| `golden/smoke20.csv` | 스모크 20문항 |
| `golden/golden_v1.csv` | 골든셋 (비어 있음 — 직접 채움) · 예시는 `golden_v1_example.csv` |
| `golden/sql_golden_v1.csv` | 정형 골든셋 (질문 → 정답 SQL) · 예시는 `sql_golden_v1_example.csv` |
| `.env.example` | 접속 정보 양식 → `.env`로 복사 |
| `requirements.txt` | 패키지 목록 |

---

## 2. 설치 (Windows)

### 2-1. 폴더 두기
- zip을 **`C:\work\rag_lab`** 처럼 짧은 영문 경로에 풉니다. 바탕화면이나 한글·공백이 들어간 경로는 피합니다(Oracle Instant Client, 일부 패키지가 경로 문제를 일으킴).
- 압축을 풀면 `C:\work\rag_lab\nb01_inventory.py` 같은 구조가 되어야 합니다. `rag_lab` 폴더가 한 번 더 겹치지 않았는지 확인합니다.

### 2-2. 패키지 설치 — Spyder가 쓰는 파이썬에 설치해야 합니다
가장 확실한 방법은 **Spyder 콘솔(오른쪽 아래 IPython)에서 직접 설치**하는 것입니다.

```python
%cd C:\work\rag_lab
%pip install -r requirements.txt
```

- 설치 뒤에는 **콘솔 재시작**을 합니다 (콘솔 탭 우클릭 → Restart kernel, 또는 `Ctrl+.`).
- Anaconda를 쓰면 `Anaconda Prompt`에서 설치해도 됩니다:
  ```bat
  cd /d C:\work\rag_lab
  pip install -r requirements.txt
  ```
- **Spyder 단독 설치판**(Anaconda 없이 받은 Spyder)은 자체 파이썬에 pip 설치가 안 되는 경우가 있습니다. 이때는 Anaconda 환경에 패키지와 `spyder-kernels`를 설치하고, Spyder에서 **도구(Tools) → 환경 설정(Preferences) → Python 인터프리터 → "다음 인터프리터 사용"** 으로 그 환경의 `python.exe`를 지정합니다.
- 폐쇄망이라 pip가 막혀 있으면:
  - 사내 PyPI 미러: `%pip install -r requirements.txt -i http://사내미러/simple --trusted-host 사내미러`
  - 프록시: `%pip install -r requirements.txt --proxy http://프록시:포트`
  - wheel 파일: 받아 둔 `.whl` 폴더에서 `%pip install --no-index --find-links C:\wheels -r requirements.txt`
- 가장 먼저 필요한 것은 `oracledb`, `pymilvus`, `kiwipiepy` 세 개입니다. 나머지(FlagEmbedding, transformers)는 없어도 대체 동작으로 돕니다.
- `oracledb`는 thin 모드라 **Oracle Client 설치가 없어도** 됩니다. 연결이 안 될 때만 5-1의 thick 모드를 씁니다.

---

## 3. 처음 한 번 — 샘플 모드로 돌려 보기

1. **`.env` 만들기** — 명령 프롬프트(cmd)에서:
   ```bat
   cd /d C:\work\rag_lab
   copy .env.example .env
   notepad .env
   ```
   - 탐색기로 복사해도 됩니다. 이때 **보기 → 파일 확장명**을 켜야 `.env.txt`로 저장되는 실수를 막을 수 있습니다.
   - 처음에는 `LAB_MODE=sample`인 채로 저장합니다. 샘플 모드에서는 `.env`의 모델 설정을 무시하고 가짜 데이터로 돕니다.
2. Spyder에서 **파일 → 열기** → `C:\work\rag_lab\nb01_inventory.py`.
3. 첫 셀 `[0] 준비`에 커서를 두고 **`Ctrl+Enter`**.
4. **`Shift+Enter`** 로 한 셀씩 내려가며 실행합니다.
5. 오른쪽 위 **변수 탐색기(Variable Explorer)** 탭에서 `inv`, `meta_fill`, `store_check`를 더블클릭하면 표로 열립니다.
6. `C:\work\rag_lab\out\` 에 CSV와 xlsx가 생기면 성공입니다.

여섯 파일(`nb01`~`nb06`)이 샘플 모드에서 끝까지 돌면 설치가 끝난 것입니다.

---

## 4. Spyder에서 셀 단위로 쓰기

| 동작 | 키 / 메뉴 |
|---|---|
| 현재 셀 실행 | `Ctrl+Enter` (실행 → 셀 실행) |
| 현재 셀 실행 후 다음 셀로 | `Shift+Enter` |
| 파일 전체 실행 | `F5` — 쓰지 않는 것을 권장 (셀 단위로) |
| 변수 보기 | 변수 탐색기에서 DataFrame 더블클릭 |
| 콘솔 초기화 | 콘솔 탭 우클릭 → Restart kernel (`Ctrl+.`) |

- `# %% [번호] 제목` 줄이 셀 경계입니다. Jupyter의 셀과 같습니다. 에디터에서 현재 셀이 옅은 색으로 강조됩니다.
- **각 파일의 `[0] 준비` 셀을 항상 먼저 실행합니다.** 이 셀이 작업 폴더를 `rag_lab`으로 바꾸고, 설정과 모듈을 다시 읽습니다. `.env`나 `lab_*.py`를 고친 뒤에는 `[0]`만 다시 실행하면 반영됩니다.
- `[0]`에서 `NameError: name '__file__' is not defined`가 나면, 셀 안의 `LAB = r'C:\work\rag_lab'` 줄을 실제 폴더로 고칩니다.
- 대문자 변수(`N_PER_TYPE`, `DOC_ID`, `QUERY`, `QID`, `MODE`, `JUDGED`, `CORPUS_N` 등)는 **바꿔 가며 다시 돌리는 조절값**입니다. 해당 셀만 다시 실행하면 됩니다.
- 코드 안에 Windows 경로를 쓸 때는 앞에 `r`을 붙입니다: `JUDGED = r'C:\work\rag_lab\out\nb05_smoke_to_judge_....xlsx'`
- 변수 탐색기는 큰 DataFrame(수십만 행)에서 느려집니다. 이 랩의 결과표는 대부분 수십 행이고, `corpus`처럼 큰 변수는 열지 않습니다.
- **결과 xlsx를 엑셀로 열어 둔 채 같은 셀을 다시 실행해도 됩니다.** 파일 이름에 초 단위 시각이 붙어 새 파일로 저장됩니다. 판정 파일(`JUDGED`)을 읽을 때만 엑셀에서 **저장하고 닫은 뒤** 실행합니다.

---

## 5. 사내 연결 — live 모드

### 5-1. `.env` 채우기

```ini
LAB_MODE=live
ORA_USER=...
ORA_PASSWORD=...
ORA_DSN=host:1521/SERVICE_NAME
MILVUS_URI=http://milvus-host:19530
MILVUS_COLLECTION=rag_chunks
EMBED_MODE=local            # 또는 api
BGE_M3_PATH=D:\models\bge-m3
EMBED_MAX_LENGTH=512        # ← 지금 운영 중인 값 그대로 (잘림 점검 기준)
RERANK_MODE=local           # 또는 api / none
RERANK_PATH=D:\models\bge-reranker-v2-m3
LLM_URL=http://llm-host:8000/v1/chat/completions
LLM_MODEL=...
SEARCH_API_URL=             # 기존 검색 API가 있으면 (스모크 테스트를 "지금 시스템 그대로" 돌림)
```

- `.env`는 **공유·전송하지 않습니다.**
- Oracle이 오래된 버전이라 thin 모드 연결이 안 되면(DPY-3010 등) Oracle Instant Client(Windows x64)를 풀고 `ORA_THICK_LIB=C:\oracle\instantclient_19_20`처럼 적습니다.
- 경로는 `D:\models\bge-m3`, `D:/models/bge-m3` 둘 다 됩니다. 따옴표는 붙이지 않습니다.
- GPU가 없는 PC면 BGE-M3·리랭커가 자동으로 CPU(fp32)로 돕니다. 느리므로 `N_PER_TYPE`, `CORPUS_N`을 줄여서 씁니다.

### 5-2. `lab_config.py`의 [사내 맞춤] 블록

오른쪽 값만 사내 이름으로 바꿉니다. 없는 컬럼은 `None`으로 둡니다.

```python
RAW = dict(table='원문테이블', doc_id='DOC_ID', doc_type='DOC_TYPE', title='TITLE', body='본문CLOB컬럼',
           published_at='작성일컬럼', collected_at='수집일컬럼', org_name='기관컬럼', author='작성자컬럼',
           security_level=None, src_url=None, file_path=None)
CHUNK = dict(table='청크테이블', chunk_id='CHUNK_ID', doc_id='DOC_ID', seq='CHUNK_SEQ', text='CHUNK_TEXT')
MV = dict(pk='chunk_id', doc_id='doc_id', text='chunk_text', dense='dense', sparse=None, doc_type=None, published_at=None)
DOC_TYPE_MAP = {'사내코드': 'NEWS', ...}      # 사내 유형 코드 → 표준 9종
SEARCH_API = dict(...)                        # 기존 검색 API의 요청·응답 모양
```

- `DOC_TYPE_MAP`을 맞추지 않으면, `nb01 [1]`에 "미등록 DOC_TYPE" 목록으로 나옵니다. 그 목록을 보고 채우면 됩니다.
- `SEARCH_API`: 응답 JSON에서 결과 목록이 있는 위치(`results_key`, 중첩되면 `'data.items'`)와 각 필드 이름(`fields`)을 사내 API에 맞춥니다.

### 5-3. 권장 실행 순서

1. `nb01` → 소스별 규모·날짜·메타·저장 형태를 확인합니다.
2. `nb02` → 청킹·파싱 상태를 확인합니다.
3. `nb04` → Milvus를 확인합니다.
4. `nb05` → 스모크 20문항을 돌리고 판정합니다.
5. `nb03` → 한국어 BM25를 확인합니다.
6. `nb06` → 골든셋을 만든 뒤 단계별로 비교합니다.

---

## 6. 노트북별 설명

### nb01 · 소스 인벤토리 (S01 · S05)

| 셀 | 만드는 변수 | 보는 법 |
|---|---|---|
| [1] | `inv` | 유형별 문서 수, 청크 수, 청크/문서, **작성일 누락%**. 전체 테이블을 집계합니다. |
| [2] | `raw_s` | 유형별 `N_PER_TYPE`건 표본 (이후 셀은 이 표본으로 계산) |
| [3] | `meta_fill` | 유형 × 메타 컬럼별 **값이 채워진 비율%**. 0%인 칸이 공통 컬럼 승격 대상입니다. |
| [4] | `store_check` | **원문 저장 형태 선확인** (처리 흐름 0번). 줄바꿈 보존%가 낮고 "구분자 없는 표 의심%"가 높으면 원본 재파싱을 검토합니다. |
| [5] | `dup_exact`, `dup_near` | 완전 중복, 근사 중복(재송고·인용). 정제한 본문으로 비교합니다. |
| [6] | — | `out/`에 저장하고, 체크리스트에 옮겨 적을 요약을 출력합니다. |

### nb02 · 파싱·청킹 (S02 · S03 · S04-1)

| 셀 | 만드는 변수 | 보는 법 |
|---|---|---|
| [2] | `chunk_stats` | 유형별 토큰 최소·중앙·p95·최대, **max_length 초과 수** (= 임베딩할 때 뒷부분이 잘리는 청크) |
| [3] | `chunk_quality` | 유형별 **문장잘림% · 표깨짐의심% · 노이즈잔존% · 헤더포함%** |
| [4] | `clean_cmp` | 소스별 정제 규칙을 적용했을 때 평균 제거율, 노이즈가 전후로 몇 %인지 |
| [5] | `doc_view` | `DOC_ID`를 바꿔 가며 원문 → 정제 후 → 현재 청크를 한 문서씩 봅니다 |
| [6] | `header_preview` | 청크 앞에 붙일 `[유형 · 날짜 · 기관 · 제목]` 헤더 미리보기 |

- 토큰 수는 `BGE_M3_PATH`에 모델이 있으면 BGE-M3 토크나이저로 정확하게 셉니다. 없으면 근사치입니다(콘솔 첫 줄에 표시).
- 정제 규칙은 `lab_text.py`의 `NOISE`, `EMAIL_CUT`, `EMAIL_SIG`에 있습니다. 사내 문서에 맞게 패턴을 추가합니다. 예: 사내 메일 서명 형식, 특정 증권사 면책 문구.

### nb03 · 한국어 BM25 (S09)

| 셀 | 만드는 변수 | 보는 법 |
|---|---|---|
| [1] | `tok_cmp` | 같은 문장을 토크나이저별로 쪼갠 결과. **"하이닉스의 / 하이닉스는"이 같은 토큰이 되는지** |
| [2] | `corpus`, `golden` | live에서는 청크 `CORPUS_N`개 + 골든셋 정답 문서의 청크 |
| [3] | `bm25_cmp` | 토크나이저별 Hit@1 · Hit@5 · MRR |
| [4] | `drill` | `QUERY` 하나를 토크나이저별 상위 5개로 나란히 |

- 여기서 쓰는 BM25는 **랩에서 불러온 청크(표본)만으로** 만든 색인입니다. 목적은 운영 BM25 점수를 재현하는 게 아니라 **토크나이저 효과를 비교**하는 것입니다.

### nb04 · Milvus (S06 · S10-2) — live 전용

| 셀 | 만드는 변수 | 보는 법 |
|---|---|---|
| [1] | `mv_fields`, `mv_indexes`, `mv_count` | 서버 버전, 필드, 인덱스(HNSW 파라미터·metric), 엔티티 수 |
| [2] | `field_check` | sparse · doc_type · published_at · security_level · acl · 본문 필드가 있는지 |
| [3] | `sync_check` | Oracle 청크 수 vs Milvus 엔티티 수. 차이가 있으면 동기화 문제 |
| [4] | `mv_test`, `mv_test_filtered` | 같은 질의를 필터 없이 / `FILTER`로 검색. 필터가 검색과 동시에 걸리는지 확인 |

- 샘플 모드에서는 표 모양만 보여 줍니다. 수치는 의미가 없습니다.

### nb05 · 스모크 테스트 (S07-1)

1. `[2]`: 기존 검색 API(`SEARCH_API_URL`)가 있으면 **지금 시스템 그대로**, 없으면 랩 검색기로 돌립니다.
2. `[3]`: `out/nb05_smoke_to_judge_*.xlsx`가 생깁니다. 질문마다 10행이고, **rank=1 행에** 답변과 판정 칸이 있습니다.
3. 엑셀에서 rank=1 행의 판정 칸 세 개를 채웁니다.
   - 검색판정: 적중 / 순위 낮음 / 누락
   - 답변판정: 정답 / 부분 / 오답 / 자료 없음
   - 실패유형: 정상 / ①검색 누락 / ②엉뚱한 청크 / ③파싱 깨짐 / ④답변 환각 / ⑤권한 노출
4. `[4]`: `JUDGED`에 판정한 파일 경로를 넣고 실행하면 `fail_counts`에 집계가 나옵니다.

- 가장 많은 실패 유형이 먼저 볼 단계입니다: ①→S08·S09·S03 / ②→S05·S11·S12 / ③→S02·S03 / ④→S13·S14 / ⑤→S05·S10.
- 권한 확인(⑤)은 **권한이 있는 계정과 없는 계정으로 두 번** 돌려야 합니다.

### nb06 · 검색 평가·단계별 비교 (S15 · S11 · S12)

| 셀 | 만드는 변수 | 보는 법 |
|---|---|---|
| [1] | `golden` | `golden/golden_v1.csv` |
| [2] | `ret` | `PARTS`(켤 검색기), `BM25_TOK`(토크나이저)로 구성 |
| [3] | `summary`, `detail` | **모드별 Hit@1/3/5/10 · Recall · MRR · nDCG**. 이 표가 베이스라인입니다. |
| [4] | `by_type`, `by_source` | 질문 유형별 · 소스별 Hit@5 — 어디서 약한지 |
| [5] | `sweep` | RRF k(20/60) × MMR λ(0.5/0.7/1.0) |
| [6] | `failures` | `MODE`에서 틀린 문항과 정답 |
| [7] | `drill` | `QID` 하나를 모드별 상위 5개로 나란히 |
| [8] | — | 설정과 함께 `out/`에 저장 (실험 기록) |

- 모드 `hybrid`는 `PARTS`에 켠 검색기들을 **RRF**로 합칩니다. `+rerank`는 후보 50개를 리랭크하고, `+mmr`은 리랭크 뒤에 **MMR(λ)** 과 문서당 3개 상한을 적용합니다.
- live 모드에서 dense·sparse는 **Milvus 전체**를 검색하고, BM25는 **불러온 청크(표본)** 만 검색합니다. BM25 비중을 해석할 때 이 점을 감안합니다. 운영 BM25와 정확히 비교하려면 기존 검색 API로 비교하거나, Oracle Text·Milvus BM25로 옮긴 뒤 다시 잽니다.

### nb07 · 정형 데이터 연계 (S22~S29, Phase 3)

비정형 검색과 **사내 DB(SQL)** 를 붙이는 단계입니다. 먼저 `catalog/metric_catalog.xlsx`(지표 정의서)를 채워야 합니다.

| 셀 | 만드는 변수 | 보는 법 |
|---|---|---|
| [1] | `cat`, `metrics`, `allow` | 지표 정의 · 코드값 · 허용 목록. 파일이 없으면 예시 파일을 읽습니다 |
| [2] | `schema_txt` | LLM 에 줄 스키마 설명 — 허용 뷰만 들어갑니다 |
| [3] | `routing` | 질문별 **정형 / 비정형 / 혼합 / 불가** 판정과 근거(수치어 · 서술어 · 카탈로그 적중 · 기간) |
| [4] | `check`, `sql` | 생성된 SQL과 **정적 검증** 결과, 드라이런(EXPLAIN) 통과 여부 |
| [5] | `guard` | 차단 동작 확인 — 삭제 구문 · 허용 목록 밖 테이블 · 여러 문장이 실제로 막히는지 |
| [6] | `result`, `context` | 실행 결과와, 표에 쿼리 출처 라벨을 붙인 컨텍스트 |
| [7] | `mixed_context` | 혼합 질문(패턴 A) — SQL 표 + RAG 청크를 한 컨텍스트로 |
| [8] | `sql_eval`, `summary_sql` | **라우팅 정확도 · SQL 유효율 · 실행결과 정확도(EX)** |

- **SQL 생성 방식은 두 가지입니다.** `rule`은 카탈로그(지표 정의서)에서 조립하는 방식이라 설명 가능하고 안전합니다. `llm`은 사내 LLM 이 생성합니다(live + `LLM_URL` 설정 시 우선). LLM 이 실패하면 자동으로 규칙 생성으로 돌아갑니다.
- **실행 전에 반드시 막습니다.** SELECT/WITH 로 시작하지 않거나, DDL·DML 구문이 있거나, 문장이 여러 개거나, allow_list 밖 테이블을 쓰면 실행하지 않습니다. LIMIT(Oracle 은 FETCH FIRST)도 자동으로 붙입니다.
- **live 에서는 읽기 전용 계정**을 쓰십시오. 코드가 막더라도 권한으로 한 번 더 막는 것이 원칙입니다(S28).
- 샘플 모드의 라우팅·EX 수치는 규칙 생성 기준이라 높게 나옵니다. **의미 있는 값은 사내 LLM 이 SQL 을 생성할 때** 나옵니다.
- 정형 골든셋은 `golden/sql_golden_v1.csv` 에 `질문 → 정답 SQL` 로 적습니다. 채점은 SQL 문자열이 아니라 **실행 결과 값이 같은지(EX)** 로 합니다.

---

## 7. 골든셋 만드는 법 (`golden/golden_v1.csv`)

| 컬럼 | 내용 |
|---|---|
| `qid` | G001, G002 … |
| `question` | 질문 원문 |
| `q_type` | 사실 / 수치 / 기간 / 종합 / 비교 / 답없음 |
| `source` | NEWS, BROKER … (정답 문서의 유형) |
| `gold_doc_ids` | 정답 문서 ID. 여러 개면 `;`로 구분 (재송고 기사는 둘 다) |
| `gold_text` | **정답 문장** (문서 안의 한 문장). 청크 ID가 아니라 문장으로 적습니다 — 재청킹해도 골든셋이 유지됩니다 |
| `memo` | 자유 |

- 예시는 `golden_v1_example.csv`를 봅니다.
- 답이 없는 문항은 `gold_doc_ids`를 비워 둡니다. 검색 지표에서는 빠지고, 답변 평가에서 "자료 없음"이 정답입니다.
- 스모크 20문항에서 정상으로 판정된 문항부터 옮겨 담으면 빠르게 만들 수 있습니다.
- 엑셀로 작성해 CSV나 xlsx로 저장해도 됩니다. 인코딩(utf-8 / cp949)은 자동으로 판별합니다.
- 적중 판정: 결과 청크의 `doc_id`가 정답 문서이고, 정답 문장의 3글자 조각 50% 이상이 청크에 들어 있으면 적중입니다(`lab_eval.judge`의 `th`).

---

## 8. 결과 공유

- `out/`의 CSV·xlsx는 파일 이름에 날짜와 시각이 붙어 쌓입니다.
- 체크리스트나 Claude에게 공유할 때는 **집계표만** 공유합니다: `inv`, `meta_fill`, `store_check`, `chunk_stats`, `chunk_quality`, `bm25_cmp`, `field_check`, `sync_check`, `fail_counts`, `summary`, `by_type`.
- **원문·청크 텍스트가 들어간 표**(`doc_view`, `drill`, `smoke_tbl`, `detail`, `failures`)는 사내에서만 봅니다.

---

## 9. 자주 나는 문제

| 증상 | 조치 |
|---|---|
| `ModuleNotFoundError: lab_config` | `[0] 준비` 셀을 먼저 실행합니다. 안 되면 `LAB` 경로를 확인합니다. |
| `DPY-3010` 등 Oracle thin 모드 연결 오류 | `.env`의 `ORA_THICK_LIB`에 Instant Client 경로를 적습니다. |
| `ORA-00942` 테이블 없음 | `lab_config.RAW/CHUNK`의 table 이름과 스키마 접두어(`SCHEMA.TABLE`)를 확인합니다. |
| CLOB이 `LOB` 객체로 나옴 | `lab_io.connect()`가 `fetch_lobs=False`로 설정합니다. 직접 연결했다면 이 설정을 추가합니다. |
| Milvus 필드 오류 | `lab_config.MV`의 필드 이름을 `nb04 [1]`의 `mv_fields`와 맞춥니다. |
| 리랭커 API 응답 형식이 다름 | `lab_search.Reranker.score`의 api 부분에서 응답 키(`results` / `index` / `relevance_score`)를 맞춥니다. |
| 메모리 부족 | `CORPUS_N`, `N_PER_TYPE`을 줄입니다. |
| 엑셀에서 CSV 한글이 깨짐 | 같은 이름의 xlsx를 엽니다 (CSV는 utf-8-sig로 저장됨). |
| `PermissionError` / 저장 실패 | 해당 파일이 엑셀에 열려 있습니다. 닫고 셀을 다시 실행합니다. |
| `.env` 값이 반영 안 됨 | 파일 이름이 `.env.txt`가 아닌지 확인합니다(탐색기 → 보기 → 파일 확장명). 고친 뒤 `[0]` 셀을 다시 실행합니다. 그래도 안 되면 콘솔을 재시작합니다(환경변수는 한 번 읽으면 콘솔이 살아 있는 동안 유지됨). |
| `%pip install` 후에도 `ModuleNotFoundError` | 콘솔을 재시작합니다. 그래도 안 되면 Spyder가 다른 파이썬을 쓰는 것입니다 → 2-2의 인터프리터 설정. |
| 한글 경로에서 오류 | 폴더를 `C:\work\rag_lab` 같은 영문 경로로 옮깁니다. |
| BGE-M3 로딩이 매우 느림 · 메모리 부족 | GPU 없는 PC입니다. 모델을 API 방식(`EMBED_MODE=api`)으로 쓰거나 표본 수를 줄입니다. |

---

## 10. 알아 둘 제약

- **샘플 모드의 임베딩은 가짜입니다** (해시 기반 표면 유사도). 샘플 결과의 수치로 판단하지 않습니다. 코드가 도는지만 확인하는 용도입니다.
- 이 랩은 **점검·측정용**입니다. 운영 파이프라인을 바꾸지 않습니다. DB에는 SELECT만 합니다.
- 정제 규칙, 표 깨짐 판정, 문장 잘림 판정은 **휴리스틱**입니다. `doc_view`로 실제 문서를 몇 건 보고 규칙을 맞춰 가며 씁니다.
