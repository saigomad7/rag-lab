# -*- coding: utf-8 -*-
"""
nb00 · 데이터 파이프라인 적재 검증 — 평가 이전에 먼저 통과해야 하는 단계
  수집 → 통합 테이블 → 메타 → 청킹 테이블(doc_id 연결) → 임베딩 → Milvus 인덱싱
  각 셀은 DataFrame 을 남긴다 (Variable Explorer 확인 대상: raw · chunks · rep · fail)
"""
# %% [0] 준비 — 가장 먼저 실행
import os, sys, importlib
try:
    LAB = os.path.dirname(os.path.abspath(__file__))
except NameError:
    LAB = r'C:\work\rag_lab'
if LAB not in sys.path:
    sys.path.insert(0, LAB)
os.chdir(LAB)
import pandas as pd
import lab_config as C
importlib.reload(C)
import lab_io, lab_pipeline, lab_sources
for _m in (lab_io, lab_pipeline, lab_sources):
    importlib.reload(_m)
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 40)
print(pd.Series(C.summary()).to_string())

# %% [1] 적재 현황 — 통합 문서 테이블 · 청킹 테이블
raw = lab_io.load_raw(n=None if C.IS_SAMPLE else 20000)
chunks = lab_io.load_chunks(n=None if C.IS_SAMPLE else 100000)
print(f'문서 {len(raw):,} 건 · 청크 {len(chunks):,} 건 · 문서당 평균 {len(chunks) / max(len(raw), 1):.1f} 청크')
print(raw.dtypes.to_string())

# %% [1b] 소스 유형 정의 확인 — **사내 코드가 전부 매핑됐는가** (가장 먼저 볼 것)
print('■ 현재 유형 정의 (수정: lab_sources.py 의 SOURCES)')
print(lab_sources.table().to_string(index=False))
chk = lab_sources.unmapped(raw)
print('\n■ 사내 코드 매핑 점검 (수정: lab_config.DOC_TYPE_MAP)')
print(chk.to_string(index=False))
_bad = chk[chk.상태 != '정상']
if len(_bad):
    print('\n! 미정의 · 미사용 유형', len(_bad), '건 — 아래 조치 후 [1] 셀부터 다시 실행')
    print(_bad[['사내_코드', '매핑_결과', '건수', '조치']].to_string(index=False))
else:
    print('\n모든 사내 코드가 정의된 유형으로 매핑됨')

# %% [2] 소스 유형별 분포 — 수집 편중 · 기간 확인
dist = lab_pipeline.type_distribution(raw, chunks)
print(dist.to_string(index=False))

# %% [3] 1단계 점검 · 통합 문서 테이블 무결성
doc_chk = lab_pipeline.doc_integrity(raw)
print(doc_chk.to_string(index=False))

# %% [4] 2단계 점검 · 소스 유형별 필수 메타 충족률
meta_chk = lab_pipeline.meta_completeness(raw)
print(meta_chk.to_string(index=False))
print('\n미달 항목:')
print(meta_chk[meta_chk.판정 == '미달'].to_string(index=False) or '(없음)')

# %% [5] 3단계 점검 · 청킹 테이블 연결 무결성
chunk_chk = lab_pipeline.chunk_integrity(raw, chunks)
print(chunk_chk.to_string(index=False))

# %% [6] 청크 길이 분포 — 임베딩 최대 길이(EMBED_MAX_LENGTH) 초과 여부
size = lab_pipeline.chunk_size_profile(chunks, raw)
print(size.to_string(index=False))
print(f'\n설정된 임베딩 최대 길이 = {C.EMBED_MAX_LENGTH} 토큰 · 초과율 > 0 이면 뒷부분 잘림')

# %% [7] 4단계 점검 · 임베딩 · Milvus 인덱싱 정합성 (live 전용)
idx_chk = lab_pipeline.index_integrity(chunks)
print(idx_chk.to_string(index=False))

# %% [8] 종합 — 단계별 판정 · 미달 과제
rep = lab_pipeline.pipeline_report(doc_chk, meta_chk, chunk_chk, idx_chk)
print(rep.to_string(index=False))
fail = lab_pipeline.failed_only(rep)
print(f'\n미달 {len(fail)} 건 — 평가 이전에 해소 대상')
print(fail.to_string(index=False) if len(fail) else '(없음 · 평가 단계로 진행)')

# %% [9] 저장 — 이력 엑셀 `3_파이프라인_점검` 에 붙여넣기
lab_io.save(rep, 'nb00_pipeline_report')
lab_io.save(dist, 'nb00_type_dist')
if len(fail):
    lab_io.save(fail, 'nb00_failed')
