# -*- coding: utf-8 -*-
"""골든셋 실물 예시 → golden_set_example_rev2.xlsx
   샘플 데이터로 실제 생성한 값이 들어간다 (LLM 생성 · 수동 · 자동 평가셋 3종 · 정형 · 근거 연결 · 스모크 20)."""
import os
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter as L

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, LAB)
os.chdir(LAB)
os.environ.setdefault('LAB_MODE', 'sample')
import lab_io, lab_sample, lab_sample_sql, lab_autoeval, lab_golden_llm, lab_search   # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, '..', 'golden_set_example_rev2.xlsx'))
FONT, PRI = '맑은 고딕', '185463'
thin = Side(style='thin', color='BFCACB')
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
F = lambda c: PatternFill('solid', start_color=c, end_color=c)
HDR, INP, EX = F('E7EDEE'), F('FFFDE7'), F('F2F7F7')
f = lambda **k: Font(name=FONT, size=k.pop('size', 10), **k)
WRAP = Alignment(wrap_text=True, vertical='top')
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)

docs = lab_sample.raw_docs()
chunks = lab_sample.chunks()
manual = lab_sample.golden()
known = lab_autoeval.make_known_item(chunks, n=12)
title_q = lab_autoeval.make_title_query(docs, n=10)
syn = lab_autoeval.make_synthetic(chunks, n=8, llm=lambda p: '2026년 eSSD 수요 전망치는 얼마인가?')
sqlg = lab_sample_sql.golden()
# LLM 생성 골든셋 (nb12) — 샘플 모드는 규칙 생성, 사내 live 에서는 LLM 이 생성
_smp = lab_golden_llm.sample_chunks(chunks, docs, per_type=3, min_len=120)
llm_g = lab_golden_llm.generate(_smp, n=10, use_llm=False)
llm_g = lab_golden_llm.apply_check(llm_g, lab_golden_llm.self_check(
    llm_g, chunks, retriever=lab_search.Retriever(chunks, bm25_tokenizer='josa')))
noans = lab_golden_llm.make_unanswerable(docs, n=3, use_llm=False)
llm_g = pd.concat([llm_g, noans], ignore_index=True)
# 근거 문서 연결 (nb11) — 사외 질문 → 코퍼스 후보 → 사람 판정
_ret = lab_search.Retriever(chunks, bm25_tokenizer='josa')
_bank = lab_io.read_table(os.path.join(LAB, 'golden', 'answer_golden_v1.csv')).head(4)
link = lab_autoeval.link_evidence(_bank, lambda q, k=3: _ret.search(q, 'hybrid', k=k, cand=20), k=3,
                                  meta=docs.set_index('doc_id'))
smoke = lab_io.read_table(os.path.join(LAB, 'golden', 'smoke20.csv'))

wb = Workbook()
ws = wb.active
ws.title = '안내'
ws['A1'] = '골든셋 실물 예시 rev.1'
ws['A1'].font = f(size=14, bold=True, color=PRI)
ws['A2'] = '2026-09-23 · 샘플 데이터로 실제 생성한 값 · 사내 적용 시 동일 구조로 생성'
ws['A2'].font = f(size=9, color='6B6B6B')
rows = [
 ('구성', 'LLM 생성 골든셋 + 수동 골든셋 + 자동 평가셋 3종 + 정형 골든셋 + 근거 연결 + 스모크 20문항'),
 ('LLM_골든셋', '코퍼스 청크에서 질문 · 정답 · 근거를 함께 생성 → 자가 검증 → 검수 · nb12 생성 · 권장 기본 경로'),
 ('근거연결', '사외 질문에 코퍼스 근거를 붙이는 단계 · 근거 확보 / 문서 없음 / 보류 판정 · nb11 생성'),
 ('수동_골든셋', '사람이 작성 · 정답 = 문서 ID + 정답 문장 · 파일: rag_lab/golden/golden_v1.csv'),
 ('자동_known-item', '문서 문장 1개를 질의로 사용 → 해당 문서가 정답 · 라벨 작업 0건 · nb08 생성'),
 ('자동_제목질의', '제목을 질의로 사용 → 해당 문서가 정답 · nb08 생성'),
 ('자동_합성QA', '사내 LLM 이 청크에서 질문 생성 → 원문 복붙(3-gram 겹침 0.6 초과) 자동 제외 · nb08 생성'),
 ('정형_골든셋', '질문 → 정답 SQL · 채점: 실행 결과 값 일치(EX) · 파일: rag_lab/golden/sql_golden_v1.csv'),
 ('스모크20', '실행 후 사람이 판정 · 실패 문항이 수동 골든셋 후보'),
 ('정답 표기', 'gold_doc_ids: 복수 시 " ; " 구분 · gold_text: 문서 내 정답 문장(청크 ID 사용 금지 — 재청킹 시 무효)'),
 ('판정 기준', '결과 청크의 doc_id 일치 + 정답 문장 3-gram 겹침 ≥ 0.5 → 적중'),
 ('작성 순서', '① nb00 적재 검증 통과 → ② nb12 LLM 골든셋 생성 · 검수 → ③ nb08 자동 평가셋 병행 → ④ 실제 업무 질문 추가'),
 ('권장 규모', '자동 200~500문항 + 수동 30~50문항 · n=200 → 95% 신뢰구간 ±6.9%p'),
]
ws['A4'] = '항목'; ws['B4'] = '내용'
for c in ('A4', 'B4'):
    ws[c].font = f(bold=True); ws[c].fill = HDR; ws[c].border = BOX; ws[c].alignment = CEN
for i, (a, b) in enumerate(rows, 5):
    ws.cell(i, 1, a).font = f(bold=True)
    ws.cell(i, 2, b).font = f()
    for c in (1, 2):
        ws.cell(i, c).border = BOX; ws.cell(i, c).alignment = WRAP
ws.column_dimensions['A'].width = 20
ws.column_dimensions['B'].width = 108

SHEETS = [
 ('LLM생성_골든셋', llm_g, 'nb12 생성 · 질문 + 정답 + 근거 문장 + 자가검증 (샘플은 규칙 생성, 사내는 LLM)',
  ['qid', 'doc_type', 'q_type', 'level', 'question', 'gold_answer', 'gold_text', 'gold_doc_ids', '자가검증', '사유'],
  [9, 12, 9, 8, 40, 40, 40, 16, 10, 20]),
 ('근거문서_연결', link, 'nb11 생성 · 사외 질문 → 코퍼스 후보 → 근거 판정 칸(사람 기입)',
  ['qid', 'question', 'cand_rank', 'cand_doc_id', 'cand_doc_type', 'cand_text', 'score', '근거 판정', '확정 doc_id'],
  [9, 40, 9, 14, 13, 50, 9, 11, 14]),
 ('수동_골든셋', manual, '사람이 작성 · 실제 업무 질문 기반 · 최종 기준', ['qid', 'question', 'q_type', 'source', 'gold_doc_ids', 'gold_text'], [10, 42, 9, 13, 16, 34]),
 ('자동_known-item', known, '문서 문장 = 질의 · 라벨 0건 · 시스템 건전성 점검용', ['qid', 'question', 'q_type', 'level', 'gold_doc_ids', 'gold_text', 'src_chunk'], [9, 52, 12, 8, 14, 40, 16]),
 ('자동_제목질의', title_q, '제목 = 질의 · 대표 표현 회수 확인', ['qid', 'question', 'q_type', 'level', 'gold_doc_ids'], [9, 44, 9, 8, 14]),
 ('자동_합성QA', syn, '사내 LLM 생성 질문 · 표현 변형 대응 확인 (샘플은 고정 문구)', ['qid', 'question', 'q_type', 'level', 'gold_doc_ids', 'gold_text'], [9, 40, 11, 8, 14, 46]),
 ('정형_골든셋', sqlg, '질문 → 정답 SQL · 채점은 실행 결과 값 일치(EX)', ['qid', 'question', 'gold_route', 'gold_sql'], [9, 40, 11, 76]),
 ('스모크20', smoke, '실행 후 판정 기입 · 실패 문항 = 수동 골든셋 후보', ['no', 'q_type', 'source', 'question', 'expected'], [9, 12, 18, 48, 52]),
]

for name, df, desc, cols, widths in SHEETS:
    s = wb.create_sheet(name)
    s['A1'] = name.replace('_', ' ')
    s['A1'].font = f(size=13, bold=True, color=PRI)
    s['A2'] = f'{desc} · {len(df)}건'
    s['A2'].font = f(size=9, color='6B6B6B')
    use = [c for c in cols if c in df.columns]
    s.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(use))
    s.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(use))
    for j, c in enumerate(use, 1):
        x = s.cell(4, j, c); x.font = f(bold=True); x.fill = HDR; x.border = BOX; x.alignment = CEN
        s.column_dimensions[L(j)].width = widths[cols.index(c)]
    for i, (_, r) in enumerate(df[use].iterrows(), 5):
        for j, c in enumerate(use, 1):
            v = r[c]
            x = s.cell(i, j, '' if pd.isna(v) else str(v))
            x.font = Font(name='Consolas', size=9) if c in ('gold_sql', 'src_chunk') else f()
            x.border = BOX; x.alignment = WRAP
            if c in ('qid', 'no', 'q_type', 'level', 'gold_route', 'source'):
                x.alignment = CEN
    last = 4 + len(df)
    s.freeze_panes = 'A5'
    s.auto_filter.ref = f'A4:{L(len(use))}{last}'
    if name == '스모크20':                      # 판정 입력 칸 추가
        for j, c in enumerate(['검색판정', '답변판정', '실패유형', '메모'], len(use) + 1):
            x = s.cell(4, j, c); x.font = f(bold=True); x.fill = HDR; x.border = BOX; x.alignment = CEN
            s.column_dimensions[L(j)].width = 12
            for i in range(5, last + 1):
                y = s.cell(i, j); y.fill = INP; y.border = BOX
        for col, items in ((len(use) + 1, ['적중', '순위 낮음', '누락']), (len(use) + 2, ['정답', '부분', '오답', '자료 없음']),
                           (len(use) + 3, ['정상', '①검색 누락', '②부적합 청크', '③파싱 손상', '④답변 환각', '⑤권한 노출'])):
            dv = DataValidation(type='list', formula1='"' + ','.join(items) + '"', allow_blank=True)
            s.add_data_validation(dv); dv.add(f'{L(col)}5:{L(col)}{last}')
    s.page_setup.orientation = 'landscape'
    s.sheet_properties.pageSetUpPr.fitToPage = True
    s.page_setup.fitToWidth = 1; s.page_setup.fitToHeight = 0

wb.save(OUT)
print('saved', OUT)
print({n: len(d) for n, d, *_ in SHEETS})
