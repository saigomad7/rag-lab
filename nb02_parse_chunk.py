# -*- coding: utf-8 -*-
"""
nb02 · 파싱 · 청킹 · 임베딩 입력 점검 — 체크리스트 S02 파싱 · S03 청킹 · S04-1 max_length · 소스별 처리 흐름
"""
# %% [0] 준비 — 가장 먼저 실행
import os, sys, importlib
try:
    LAB = os.path.dirname(os.path.abspath(__file__))
except NameError:
    LAB = r'C:\work\rag_lab'          # ← __file__ 이 없다고 나오면 이 폴더 경로를 직접 적는다
if LAB not in sys.path:
    sys.path.insert(0, LAB)
os.chdir(LAB)
import pandas as pd
import lab_config as C
importlib.reload(C)
import lab_io, lab_text, lab_sources, lab_search, lab_eval
for _m in (lab_io, lab_text, lab_search, lab_eval):
    importlib.reload(_m)
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 60)
print('LAB_MODE =', C.LAB_MODE, '| EMBED_MAX_LENGTH =', C.EMBED_MAX_LENGTH, '| 토크나이저:', 'BGE-M3' if lab_text.tokenizer() else '근사치')

# %% [1] 표본 원문 + 그 문서들의 청크
N_PER_TYPE = 30
raw_s = lab_io.sample_per_type(N_PER_TYPE)
ch = lab_io.load_chunks(doc_ids=raw_s['doc_id'].tolist())
ch = ch.merge(raw_s[['doc_id', 'doc_type', 'title']], on='doc_id', how='left')
print('원문', len(raw_s), '건 · 청크', len(ch), '개')

# %% [2] 청크 길이 분포 (S03-1) · max_length 초과 = 임베딩 때 뒷부분이 잘리는 청크 (S04-1)
ch['chars'] = ch['text'].fillna('').str.len()
ch['tokens'] = ch['text'].map(lab_text.count_tokens)
chunk_stats = ch.groupby('doc_type').agg(청크=('chunk_id', 'count'), 토큰_최소=('tokens', 'min'), 토큰_중앙=('tokens', 'median'),
                                          토큰_p95=('tokens', lambda s: s.quantile(.95)), 토큰_최대=('tokens', 'max'),
                                          max_length_초과=('tokens', lambda s: int((s > C.EMBED_MAX_LENGTH).sum())))
chunk_stats.insert(0, '유형', chunk_stats.index.map(C.DOC_TYPE_KO))
print(chunk_stats.round(0).to_string())

# %% [3] 청크 품질 (S03-2 · S03-3) — 문장 잘림 · 표 깨짐 의심 · 노이즈 잔존 · 헤더 포함, 유형별 %
ch['문장잘림'] = ch['text'].map(lab_text.ends_mid_sentence)
ch['표깨짐의심'] = ch['text'].map(lab_text.table_suspect)
ch['노이즈잔존'] = [lab_text.noise_left(t, d) for t, d in zip(ch['text'], ch['doc_type'])]
ch['헤더포함'] = [lab_text.has_header(t, ti) for t, ti in zip(ch['text'], ch['title'])]
chunk_quality = (ch.groupby('doc_type')[['문장잘림', '표깨짐의심', '노이즈잔존', '헤더포함']].mean() * 100).round(0)
chunk_quality.insert(0, '유형', chunk_quality.index.map(C.DOC_TYPE_KO))
print(chunk_quality.to_string())
print('\n읽는 법: 문장잘림% 높음 → 고정 길이 분할 의심 / 노이즈잔존% → 정제 규칙 필요 / 헤더포함% 낮음 → 헤더 부착(S03-3)')

# %% [4] 소스별 정제 전후 (처리 흐름의 '제거' 단계) — 얼마나 걷어내나
raw_s['clean'] = [lab_text.clean(b, d) for b, d in zip(raw_s['body'], raw_s['doc_type'])]
raw_s['제거율%'] = (100 - raw_s['clean'].str.len() / raw_s['body'].str.len().clip(lower=1) * 100).round(1)
raw_s['노이즈_전'] = [lab_text.noise_left(b, d) for b, d in zip(raw_s['body'], raw_s['doc_type'])]
raw_s['노이즈_후'] = [lab_text.noise_left(b, d) for b, d in zip(raw_s['clean'], raw_s['doc_type'])]
clean_cmp = raw_s.groupby('doc_type').agg(문서=('doc_id', 'count'), 평균제거율=('제거율%', 'mean'),
                                           노이즈_전=('노이즈_전', 'mean'), 노이즈_후=('노이즈_후', 'mean'))
clean_cmp[['노이즈_전', '노이즈_후']] = (clean_cmp[['노이즈_전', '노이즈_후']] * 100).round(0)
clean_cmp.insert(0, '유형', clean_cmp.index.map(C.DOC_TYPE_KO))
print(clean_cmp.round(1).to_string())

# %% [5] 문서 하나 들여다보기 — DOC_ID 만 바꿔서 반복 실행
DOC_ID = raw_s.loc[raw_s.doc_type == 'EMAIL', 'doc_id'].iloc[0] if (raw_s.doc_type == 'EMAIL').any() else raw_s.doc_id.iloc[0]
_d = raw_s.set_index('doc_id').loc[DOC_ID]
doc_view = ch[ch.doc_id == DOC_ID][['chunk_id', 'tokens', '문장잘림', '표깨짐의심', '노이즈잔존', 'text']].reset_index(drop=True)
print(f'■ {DOC_ID} [{_d.doc_type}] {_d.title}\n--- 원문 ---\n{_d.body}\n--- 정제 후 ---\n{_d.clean}\n--- 현재 청크 ({len(doc_view)}개) ---')
for r in doc_view.itertuples():
    print(f'[{r.chunk_id}] {r.text!r}')

# %% [6] 헤더 미리보기 (S03-3) — 청크 앞에 붙일 [유형 | 날짜 | 기관 | 제목]
header_preview = raw_s[['doc_id', 'doc_type', 'published_at', 'org_name', 'title']].copy()
header_preview['header'] = [lab_text.build_header(r) for r in raw_s.to_dict('records')]
print(header_preview[['doc_id', 'header']].head(12).to_string(index=False))

# %% [7] 저장
for _df, _n in ((chunk_stats.reset_index(), 'nb02_chunk_stats'), (chunk_quality.reset_index(), 'nb02_chunk_quality'),
                (clean_cmp.reset_index(), 'nb02_clean_cmp'), (header_preview, 'nb02_header_preview')):
    lab_io.save(_df, _n)

# %% [+] 유형별 청킹 기준 대비 — lab_sources.SOURCES[코드]['chunk'] 를 바꾸면 여기 값이 바뀐다
import lab_sources
importlib.reload(lab_sources)
rows = []
for t, g in raw_s.groupby('doc_type'):
    base, tbl = lab_sources.chunk_opts(t)
    now = ch[ch.doc_type == t]['text'].astype(str).str.len()
    re_ch = [len(c) for b in g['body'] for c in lab_text.chunk_text(b, t)]
    rows.append(dict(소스=lab_sources.ko(t), 기준_글자=base, 표_분리=('O' if tbl else 'X'),
                     현재_청크수=len(now), 현재_중앙=int(now.median()) if len(now) else 0,
                     기준적용시_청크수=len(re_ch), 기준적용시_중앙=int(pd.Series(re_ch).median()) if re_ch else 0))
rechunk = pd.DataFrame(rows)
print(rechunk.to_string(index=False))
print('\n현재 청크가 기준과 크게 다르면 → 적재 파이프라인의 청킹 설정을 기준에 맞추거나, 기준을 실제에 맞게 수정')
