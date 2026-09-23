# -*- coding: utf-8 -*-
"""
골든셋 · 정량 평가 팩 → golden_eval_pack_rev1.xlsx
사내에서 채우는 순서: 1 검수 → 2 확정 → 3 실행 기록 → 5 전후 비교 → 6 문항별 · 7 답변 평가
수식으로 판정 · 유의차까지 자동 계산 (값만 기입)
"""
import os
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter as L

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, LAB)
os.environ.setdefault('LAB_MODE', 'sample')
_cwd = os.getcwd()
os.chdir(LAB)
import lab_sample, lab_autoeval, lab_ragas, lab_graph   # noqa: E402
sys.path.insert(0, HERE)
import answers_golden as AG                          # noqa: E402
import lab_golden_llm, lab_io                        # noqa: E402
os.chdir(_cwd)

OUT = os.path.join(HERE, '..', 'golden_eval_pack_rev4.xlsx')
FONT, PRI = '맑은 고딕', '185463'
thin = Side(style='thin', color='BFCACB')
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
F = lambda c: PatternFill('solid', start_color=c, end_color=c)
HDR, INP, CALC, EXF = F('E7EDEE'), F('FFFDE7'), F('EEF4F5'), F('F5F5F5')
f = lambda **k: Font(name=FONT, size=k.pop('size', 10), **k)
WRAP = Alignment(wrap_text=True, vertical='top')
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)
N_ROWS = 300            # 기입용 빈 행 수

wb = Workbook()


def head(ws, title, sub, cols, widths, row=4, n_input=N_ROWS, input_cols=(), calc_cols=()):
    ws['A1'] = title; ws['A1'].font = f(size=13, bold=True, color=PRI)
    ws['A2'] = sub; ws['A2'].font = f(size=9, color='6B6B6B')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(cols))
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(cols))
    for j, c in enumerate(cols, 1):
        x = ws.cell(row, j, c); x.font = f(bold=True); x.fill = HDR; x.border = BOX; x.alignment = CEN
        ws.column_dimensions[L(j)].width = widths[j - 1]
    for i in range(row + 1, row + 1 + n_input):
        for j in range(1, len(cols) + 1):
            x = ws.cell(i, j); x.border = BOX; x.alignment = WRAP; x.font = f()
            if j in input_cols:
                x.fill = INP
            elif j in calc_cols:
                x.fill = CALC
    ws.freeze_panes = ws.cell(row + 1, 1)
    ws.auto_filter.ref = f'A{row}:{L(len(cols))}{row + n_input}'
    ws.page_setup.orientation = 'landscape'
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0


def dv(ws, items, rng):
    d = DataValidation(type='list', formula1='"' + ','.join(items) + '"', allow_blank=True)
    ws.add_data_validation(d); d.add(rng)


# ---------------- 0. 안내 ----------------
ws = wb.active; ws.title = '0_안내'
ws['A1'] = '골든셋 · 정량 평가 팩 rev.4'; ws['A1'].font = f(size=14, bold=True, color=PRI)
ws['A2'] = '2026-09-23 · 원본 확보 → 파싱 · 청킹 → 근거 연결 → 골든셋 확정 → 정량 평가 · 연노랑 = 기입 / 회색 = 자동 계산'
ws['A2'].font = f(size=9, color='6B6B6B')
steps = [
 ('0단계 · 선행 조건', 'nb00_pipeline_check 통과 — 적재 · 메타 · 청킹 · 인덱싱 무결성 미달 0 건', '미달 상태 측정은 원인 분리 불가'),
 ('0-1 · 원본 확보', '`2e_원본_수집목록` 에 문서명 · URL · 발행일 · 수집 · 적재 · 파싱 상태 기입', '적재 완료분만 평가 대상'),
 ('0-2 · 근거 연결', 'nb11_evidence_link 실행 → `2d_근거문서_연결` 붙여넣기 → 근거 확보 / 문서 없음 판정', '질문 은행 → 골든셋 전환 단계'),
 ('1단계 · 골든셋 생성 A', 'nb12_golden_llm 실행 → 코퍼스에서 질문 · 정답 · 근거 생성 → `1b_LLM골든셋_검수` 붙여넣기', '권장 경로 · 근거 포함'),
 ('1단계 · 골든셋 생성 B', 'nb08_auto_eval 실행 → out/nb08_set_*.csv 생성 (known-item · 제목 · 합성)', '라벨 작업 0건 · 검색 전용'),
 ('2단계 · 검수', '`1b_LLM골든셋_검수`(LLM 생성) · `1_골든셋_검수`(자동 생성) 에서 채택 / 수정 / 폐기', '자가검증 통과분부터 확인'),
 ('3단계 · 확정', '채택분 + 실제 업무 질문 30건 → `2_골든셋_확정` · 파일: rag_lab/golden/golden_v1.csv', '유형 배분표 준수'),
 ('4단계 · 측정', 'nb06(검색) · nb10(답변) 실행 → `3_평가_실행기록` 에 회차별 값 기입', '설정 변경 시마다 1행 추가'),
 ('5단계 · 판정', '`4_지표_정의` 기준 대비 충족 / 미달 · `5_전후비교` 로 개선 유의성 확인', '표본오차 · McNemar 자동 계산'),
 ('6단계 · 원인 분석', '`6_문항별_결과` 개선 / 퇴행 문항 · `7_답변평가` 충실도 · 인용', '퇴행 문항 = 회귀 위험'),
 ('7단계 · 고도화', 'nb13_langgraph_rag 프리셋 비교 → 채택 프리셋을 `3_평가_실행기록` 의 프리셋 열에 기록', '프리셋별 비교표는 이력 대장 `6_프리셋비교`'),
 ('대안 경로 · 답변 평가', '`2b_질의응답_골든셋`(사외 정보 기반 60문항) — 2d 에서 근거 확보된 문항만 점수 집계', '근거 미확보 문항은 수집 공백으로 분리'),
 ('표준 지표', '`8_표준지표` 16종 (검색 IR · 생성 RAGAS 계열 · 운영) · 계산: nb10_answer_eval', 'auto / judge / manual 구분'),
]
ws['A4'] = '단계'; ws['B4'] = '내용'; ws['C4'] = '소요 · 비고'
for c in ('A4', 'B4', 'C4'):
    ws[c].font = f(bold=True); ws[c].fill = HDR; ws[c].border = BOX; ws[c].alignment = CEN
for i, r in enumerate(steps, 5):
    for j, v in enumerate(r, 1):
        x = ws.cell(i, j, v); x.font = f(bold=(j == 1)); x.border = BOX; x.alignment = WRAP
rules = [
 ('측정 성립 조건', '원본 문서 적재 → 파싱 → 청킹 → 인덱싱 완료 후에만 검색 · 답변 평가 유효 · 미적재 문항을 오답 처리하면 검색 성능이 과소평가됨'),
 ('실패 구분', '① 근거 문서 없음 = 수집 공백  ② 문서 있으나 미검색 = 검색 실패  ③ 검색됐으나 답변 오류 = 생성 실패 — 셋을 섞어 집계하지 않는다'),
 ('정답 표기', 'gold_doc_ids: 복수 시 ";" 구분 / gold_text: 문서 내 정답 문장 · 청크 ID 사용 금지(재청킹 시 무효)'),
 ('판정 방식', '결과 청크 doc_id 일치 + 정답 문장 3-gram 겹침 ≥ 0.5 → 적중'),
 ('최소 규모', '자동 200 + 수동 30 · n=200 → 95% 신뢰구간 ±6.9%p · 개선 폭이 오차보다 작으면 판단 보류'),
 ('회차 관리', '설정 1개만 바꾸고 1회차 측정 (동시 변경 시 원인 분리 불가)'),
 ('문서 역할', '본 파일 = 골든셋 구성 · 문항 단위 평가 / `rag_project_log_rev1.xlsx` = 과제 전체 이력 · 프리셋 비교 · 지표 현황'),
 ('평가셋 고정', '평가셋 버전 고정 후 비교 · 문항 추가 시 버전 번호 변경'),
]
r0 = 5 + len(steps) + 1
ws.cell(r0, 1, '규칙').font = f(size=11, bold=True, color=PRI)
for i, (a, b) in enumerate(rules, r0 + 1):
    x = ws.cell(i, 1, a); x.font = f(bold=True); x.border = BOX; x.alignment = WRAP
    y = ws.cell(i, 2, b); y.font = f(); y.border = BOX; y.alignment = WRAP
    ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=3)
for col, w in (('A', 20), ('B', 92), ('C', 30)):
    ws.column_dimensions[col].width = w

# ---------------- 1. 골든셋 검수 ----------------
ws = wb.create_sheet('1_골든셋_검수')
cols = ['qid', 'set', 'level', '질문(자동 생성)', '정답 문서', '정답 문장', '검수 결과', '수정 질문', '수정 정답 문서', '폐기 사유', '검수자', '검수일']
head(ws, '1. 골든셋 검수 — 자동 생성분 판정', 'nb08 출력(out/nb08_set_*.csv) 붙여넣기 → G~L 열 기입 · 채택분만 2단계로 이동',
     cols, [9, 13, 7, 46, 14, 40, 11, 40, 14, 20, 10, 11], input_cols=(7, 8, 9, 10, 11, 12))
dv(ws, ['채택', '수정 후 채택', '폐기'], f'G5:G{4 + N_ROWS}')
dv(ws, ['질의 부적절(머리글 · 인용)', '정답 모호(복수 문서)', '중복 질문', '업무 무관', '기타'], f'J5:J{4 + N_ROWS}')
for v, c in (('채택', 'E2F0D9'), ('수정 후 채택', 'FFF2CC'), ('폐기', 'F8E1E1')):
    ws.conditional_formatting.add(f'G5:G{4 + N_ROWS}', CellIsRule(operator='equal', formula=[f'"{v}"'], fill=F(c)))
smp = lab_autoeval.make_known_item(lab_sample.chunks(), n=3)
for i, r in enumerate(smp.itertuples(), 5):          # 예시 3행 (회색)
    for j, v in enumerate([r.qid, 'known-item', r.level, r.question, r.gold_doc_ids, r.gold_text, '채택', '', '', '', '홍길동', '2026-10-05'], 1):
        x = ws.cell(i, j, v); x.font = f(color='808080', italic=True); x.fill = EXF; x.border = BOX; x.alignment = WRAP
ws.cell(4 + N_ROWS + 2, 1, '집계').font = f(bold=True, color=PRI)
agg = [('채택', f'=COUNTIF(G5:G{4 + N_ROWS},"채택")'), ('수정 후 채택', f'=COUNTIF(G5:G{4 + N_ROWS},"수정 후 채택")'),
       ('폐기', f'=COUNTIF(G5:G{4 + N_ROWS},"폐기")'), ('검수 완료', f'=COUNTIF(G5:G{4 + N_ROWS},"<>")'),
       ('채택률', f'=IFERROR((COUNTIF(G5:G{4 + N_ROWS},"채택")+COUNTIF(G5:G{4 + N_ROWS},"수정 후 채택"))/COUNTIF(G5:G{4 + N_ROWS},"<>"),0)')]
for i, (k, v) in enumerate(agg, 4 + N_ROWS + 3):
    ws.cell(i, 1, k).font = f(bold=True); ws.cell(i, 1).border = BOX
    c = ws.cell(i, 2, v); c.border = BOX; c.fill = CALC; c.font = f()
    if k == '채택률':
        c.number_format = '0%'

# ---------------- 2. 골든셋 확정 ----------------
ws = wb.create_sheet('2_골든셋_확정')
cols = ['qid', 'question', 'q_type', 'source', 'gold_doc_ids', 'gold_text', 'level', 'origin', 'memo']
head(ws, '2. 골든셋 확정 (golden_v1.csv 와 동일 구조)', '채택분 + 실제 업무 질문 · 이 시트를 CSV 로 저장 → rag_lab/golden/golden_v1.csv',
     cols, [9, 46, 10, 13, 16, 40, 8, 12, 24], input_cols=tuple(range(1, 10)))
dv(ws, ['사실', '수치', '기간', '종합', '비교', '답없음'], f'C5:C{4 + N_ROWS}')
dv(ws, ['NEWS', 'BROKER', 'INSTITUTION', 'EMAIL', 'MEETING', 'REPORT', 'EXEC_REPORT', '-'], f'D5:D{4 + N_ROWS}')
dv(ws, ['easy', 'mid', 'hard'], f'G5:G{4 + N_ROWS}')
dv(ws, ['자동-known', '자동-제목', '자동-합성', '수동-업무질문', '스모크'], f'H5:H{4 + N_ROWS}')
for i, r in enumerate(lab_sample.golden().head(3).itertuples(), 5):
    for j, v in enumerate([r.qid, r.question, r.q_type, r.source, r.gold_doc_ids, r.gold_text, 'easy', '수동-업무질문', '예시 행'], 1):
        x = ws.cell(i, j, v); x.font = f(color='808080', italic=True); x.fill = EXF; x.border = BOX; x.alignment = WRAP
base = 4 + N_ROWS + 2
ws.cell(base, 1, '배분 점검 — 권장 대비').font = f(bold=True, color=PRI)
mix = [('사실', '30%'), ('수치', '25%'), ('기간', '10%'), ('종합', '15%'), ('비교', '10%'), ('답없음', '10%')]
ws.cell(base + 1, 1, '유형').font = f(bold=True); ws.cell(base + 1, 2, '권장').font = f(bold=True)
ws.cell(base + 1, 3, '현재 건수').font = f(bold=True); ws.cell(base + 1, 4, '현재 비율').font = f(bold=True)
for i, (t, p) in enumerate(mix, base + 2):
    ws.cell(i, 1, t).font = f(); ws.cell(i, 2, p).font = f()
    c = ws.cell(i, 3, f'=COUNTIF(C5:C{4 + N_ROWS},A{i})'); c.fill = CALC
    d = ws.cell(i, 4, f'=IFERROR(C{i}/COUNTIF(C5:C{4 + N_ROWS},"<>"),0)'); d.fill = CALC; d.number_format = '0%'
    for j in range(1, 5):
        ws.cell(i, j).border = BOX

# ---------------- 3. 평가 실행 기록 ----------------
ws = wb.create_sheet('3_평가_실행기록')
cols = ['RUN_ID', '일자', '평가셋 버전', '문항수', '변경 설정(1개)', '프리셋', '청킹', '헤더', 'BM25 토크나이저', '리랭커', '후보수',
        'R@1', 'R@5', 'R@10', 'MRR', 'nDCG@10', '충실도', '인용 정확도', '모름 정확도', 'R@5 판정', '오차(±%p)', '비고']
head(ws, '3. 평가 실행 기록 — 회차별', 'nb06 · nb10 · nb13 출력값 기입 · 설정은 1회차에 1개만 변경 · T · U 열 자동 계산',
     cols, [12, 11, 12, 8, 24, 13, 16, 10, 14, 16, 8, 8, 8, 8, 8, 9, 8, 9, 9, 10, 11, 26],
     input_cols=tuple(range(1, 20)), calc_cols=(20, 21))
dv(ws, list(lab_graph.PRESETS.keys()), f'F5:F{4 + N_ROWS}')
for i in range(5, 5 + N_ROWS):
    ws.cell(i, 20, f'=IF(M{i}="","",IF(M{i}>=0.8,"충족","미달"))')
    ws.cell(i, 21, f'=IF(OR(D{i}="",M{i}=""),"",1.96*SQRT(M{i}*(1-M{i})/D{i})*100)')
    ws.cell(i, 21).number_format = '0.0'
for j in (12, 13, 14, 15, 16, 17, 18, 19):
    for i in range(5, 5 + N_ROWS):
        ws.cell(i, j).number_format = '0.000'
ws.conditional_formatting.add(f'T5:T{4 + N_ROWS}', CellIsRule(operator='equal', formula=['"충족"'], fill=F('E2F0D9')))
ws.conditional_formatting.add(f'T5:T{4 + N_ROWS}', CellIsRule(operator='equal', formula=['"미달"'], fill=F('F8E1E1')))
ex = [['RUN-001', '2026-10-06', 'v1', 230, '기준선(현행)', 'v0_baseline', '고정 500', '없음', '공백', 'bge-reranker-v2-m3', 50,
       0.62, 0.78, 0.85, 0.69, 0.72, 0.74, 0.61, 0.55, '', '', '보강 전 기준선'],
      ['RUN-002', '2026-10-13', 'v1', 230, 'BM25 토크나이저', 'v1_hybrid', '고정 500', '없음', 'Kiwi', 'bge-reranker-v2-m3', 50,
       0.71, 0.86, 0.92, 0.77, 0.80, 0.76, 0.63, 0.58, '', '', '형태소 적용']]
for i, row in enumerate(ex, 5):
    for j, v in enumerate(row, 1):
        if j in (20, 21):
            continue
        x = ws.cell(i, j, v); x.font = f(color='808080', italic=True); x.fill = EXF; x.border = BOX; x.alignment = WRAP

# ---------------- 4. 지표 정의 ----------------
ws = wb.create_sheet('4_지표_정의')
cols = ['지표', '정의', '계산식', '합격 기준', '미달 시 점검 단계']
head(ws, '4. 지표 정의 · 합격 기준', '기준은 사내 실정에 맞게 조정 가능 · 조정 시 근거를 비고에 기록', cols,
     [16, 40, 40, 16, 34], n_input=0)
METRICS = [
 ('Recall@1', '1순위 결과가 정답 문서', '정답 top-1 문항 수 / 전체 문항 수', '≥ 0.70', 'S11 결합 가중 · S12 리랭크'),
 ('Recall@5', '상위 5개 안에 정답 문서 포함', '정답 top-5 문항 수 / 전체 문항 수', '≥ 0.80', 'S09 토크나이저 · S03 청킹'),
 ('Recall@10', '상위 10개 안에 정답 포함', '정답 top-10 문항 수 / 전체', '≥ 0.90', 'S10 필터 · 후보 수'),
 ('MRR', '첫 정답 순위의 역수 평균', 'Σ(1/첫 정답 순위) / 전체', '≥ 0.65', 'S12 리랭크'),
 ('nDCG@10', '순위 가중 정확도', 'DCG@10 / IDCG@10', '≥ 0.70', 'S11 · S12'),
 ('known-item R@5', '원문 문장 질의 회수율', '동일 (자동셋)', '≥ 0.95', '색인 · 토크나이저 결함 의심'),
 ('충실도', '답변 문장이 근거 청크 내용과 일치', '근거 일치 문장 수 / 전체 문장 수', '≥ 0.85', 'S13 컨텍스트 · S14 프롬프트'),
 ('인용 정확도', '인용 번호가 실제 근거와 일치', '정확 인용 수 / 전체 인용 수', '≥ 0.90', 'S14 인용 규칙'),
 ('모름 정확도', '답 없는 질문에 "자료 없음" 응답', '정답 거절 수 / 답없음 문항 수', '≥ 0.80', 'S14 · S29 임계값'),
 ('소스별 편차', '소스별 R@5 최저값과 전체 평균 차', '전체 평균 − 최저 소스', '≤ 0.15', '해당 소스 S02 · S03'),
 ('난이도 편차', 'easy − mid R@5 차', 'easy 평균 − mid 평균', '≤ 0.15', '어휘 검색 편중 · dense 보강'),
 ('p95 지연', '질의 응답 95 분위 시간', '측정값', '검색 ≤ 2초 · 답변 ≤ 8초', 'S12 후보 수 · 모델 크기'),
]
for i, row in enumerate(METRICS, 5):
    for j, v in enumerate(row, 1):
        x = ws.cell(i, j, v); x.font = f(bold=(j == 1)); x.border = BOX; x.alignment = WRAP

# ---------------- 5. 전후 비교 ----------------
ws = wb.create_sheet('5_전후비교')
ws['A1'] = '5. 전후 비교 — 개선 유의성 판정'; ws['A1'].font = f(size=13, bold=True, color=PRI)
ws['A2'] = 'B2 · B3 에 비교할 RUN_ID 기입 → 값 · 차이 · 유의 판정 자동'; ws['A2'].font = f(size=9, color='6B6B6B')
ws['A4'] = 'A 회차 (기준)'; ws['A5'] = 'B 회차 (비교)'; ws['A6'] = '문항 수 n'
for c in ('A4', 'A5', 'A6'):
    ws[c].font = f(bold=True); ws[c].border = BOX
ws['B4'] = 'RUN-001'; ws['B5'] = 'RUN-002'
for c in ('B4', 'B5'):
    ws[c].fill = INP; ws[c].border = BOX
ws['B6'] = "=IFERROR(INDEX('3_평가_실행기록'!D:D,MATCH(B4,'3_평가_실행기록'!A:A,0)),0)"
ws['B6'].fill = CALC; ws['B6'].border = BOX
# 3_평가_실행기록 에 프리셋 열이 들어가 지표 열이 한 칸씩 뒤로 밀림 (L~S)
rows = [('R@1', 'L'), ('R@5', 'M'), ('R@10', 'N'), ('MRR', 'O'), ('nDCG@10', 'P'),
        ('충실도', 'Q'), ('인용 정확도', 'R'), ('모름 정확도', 'S')]
hdr = ['지표', 'A 값', 'B 값', '차이(B−A)', '오차 ±(%p)', '판정']
for j, c in enumerate(hdr, 1):
    x = ws.cell(8, j, c); x.font = f(bold=True); x.fill = HDR; x.border = BOX; x.alignment = CEN
    ws.column_dimensions[L(j)].width = [16, 11, 11, 12, 12, 30][j - 1]
for i, (name, col) in enumerate(rows, 9):
    ws.cell(i, 1, name).font = f(bold=True)
    ws.cell(i, 2, f"=IFERROR(INDEX('3_평가_실행기록'!{col}:{col},MATCH($B$4,'3_평가_실행기록'!A:A,0)),\"\")")
    ws.cell(i, 3, f"=IFERROR(INDEX('3_평가_실행기록'!{col}:{col},MATCH($B$5,'3_평가_실행기록'!A:A,0)),\"\")")
    ws.cell(i, 4, f'=IF(OR(B{i}="",C{i}=""),"",C{i}-B{i})')
    ws.cell(i, 5, f'=IF(OR(B{i}="",C{i}="",$B$6=0),"",1.96*SQRT((B{i}*(1-B{i})+C{i}*(1-C{i}))/$B$6)*100)')
    ws.cell(i, 6, f'=IF(D{i}="","",IF(ABS(D{i})*100>E{i},IF(D{i}>0,"개선 (유의)","퇴행 (유의)"),"판단 보류 (오차 이내)"))')
    for j in range(1, 7):
        ws.cell(i, j).border = BOX; ws.cell(i, j).alignment = CEN if j > 1 else WRAP
        if j in (2, 3, 4):
            ws.cell(i, j).number_format = '0.000'
        if j == 5:
            ws.cell(i, j).number_format = '0.0'
        if j in (2, 3, 4, 5, 6):
            ws.cell(i, j).fill = CALC
ws.conditional_formatting.add('F9:F16', CellIsRule(operator='containsText', formula=['"개선"'], fill=F('E2F0D9')))
ws.conditional_formatting.add('F9:F16', CellIsRule(operator='containsText', formula=['"퇴행"'], fill=F('F8E1E1')))
note = ['판정 기준 — 차이 절대값이 오차 범위를 넘으면 유의',
        '오차 = 1.96 × √((pA(1−pA)+pB(1−pB))/n) · 문항 수가 적으면 오차 증가',
        '문항 단위 짝 비교(McNemar)는 6_문항별_결과 시트 참조 — 같은 문항을 비교하므로 검정력 높음']
for i, t in enumerate(note, 18):
    x = ws.cell(i, 1, t); x.font = f(size=9, color='5C440C'); x.fill = F('F5EAD0'); x.border = BOX
    ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=6)

# ---------------- 6. 문항별 결과 ----------------
ws = wb.create_sheet('6_문항별_결과')
cols = ['qid', 'set', 'level', 'source', '질문', 'A hit@5', 'B hit@5', '변화', 'A 순위', 'B 순위', '비고']
head(ws, '6. 문항별 결과 — 개선 · 퇴행 분류', 'nb06 · nb08 의 detail 붙여넣기 (hit@5 는 1 / 0) · H 열 자동',
     cols, [9, 13, 7, 12, 46, 9, 9, 10, 9, 9, 26], input_cols=(1, 2, 3, 4, 5, 6, 7, 9, 10, 11), calc_cols=(8,))
for i in range(5, 5 + N_ROWS):
    ws.cell(i, 8, f'=IF(OR(F{i}="",G{i}=""),"",IF(AND(F{i}=0,G{i}=1),"개선",IF(AND(F{i}=1,G{i}=0),"퇴행","동일")))')
ws.conditional_formatting.add(f'H5:H{4 + N_ROWS}', CellIsRule(operator='equal', formula=['"개선"'], fill=F('E2F0D9')))
ws.conditional_formatting.add(f'H5:H{4 + N_ROWS}', CellIsRule(operator='equal', formula=['"퇴행"'], fill=F('F8E1E1')))
b = 4 + N_ROWS + 2
ws.cell(b, 1, 'McNemar 짝 비교 — 같은 문항 기준').font = f(bold=True, color=PRI)
mc = [('개선 문항 b', f'=COUNTIF(H5:H{4 + N_ROWS},"개선")'),
      ('퇴행 문항 c', f'=COUNTIF(H5:H{4 + N_ROWS},"퇴행")'),
      ('동일 문항', f'=COUNTIF(H5:H{4 + N_ROWS},"동일")'),
      ('검정통계량', f'=IFERROR((ABS(B{b + 1}-B{b + 2})-1)^2/(B{b + 1}+B{b + 2}),"")'),
      ('판정 (3.84 초과 = 유의)', f'=IF(B{b + 4}="","",IF(B{b + 4}>3.84,IF(B{b + 1}>B{b + 2},"개선 유의","퇴행 유의"),"판단 보류"))')]
for i, (k, v) in enumerate(mc, b + 1):
    ws.cell(i, 1, k).font = f(bold=True); ws.cell(i, 1).border = BOX
    c = ws.cell(i, 2, v); c.fill = CALC; c.border = BOX; c.font = f()

# ---------------- 7. 답변 평가 ----------------
ws = wb.create_sheet('7_답변평가')
cols = ['qid', '질문', '답변(요약)', '충실도', '인용 정확도', '모름 적정', '평가자', '비고']
head(ws, '7. 답변 평가 — 사내 LLM 채점 + 사람 교차 검증', '0 / 1 기입 · 답없음 문항만 모름 적정 평가 · 20문항은 사람이 교차 확인',
     cols, [9, 40, 52, 10, 12, 10, 10, 26], input_cols=(1, 2, 3, 4, 5, 6, 7, 8))
for col in (4, 5, 6):
    dv(ws, ['1', '0', '-'], f'{L(col)}5:{L(col)}{4 + N_ROWS}')
b = 4 + N_ROWS + 2
ws.cell(b, 1, '집계').font = f(bold=True, color=PRI)
for i, (k, col) in enumerate([('충실도', 'D'), ('인용 정확도', 'E'), ('모름 정확도', 'F')], b + 1):
    ws.cell(i, 1, k).font = f(bold=True); ws.cell(i, 1).border = BOX
    c = ws.cell(i, 2, f'=IFERROR(COUNTIF({col}5:{col}{4 + N_ROWS},"1")/(COUNTIF({col}5:{col}{4 + N_ROWS},"1")+COUNTIF({col}5:{col}{4 + N_ROWS},"0")),"")')
    c.fill = CALC; c.border = BOX; c.number_format = '0.000'; c.font = f()


# ---------------- 1b. LLM 골든셋 검수 (nb12) ----------------
ws = wb.create_sheet('1b_LLM골든셋_검수')
cols = lab_golden_llm.REVIEW_COLS
head(ws, '1b. LLM 골든셋 검수 — 코퍼스에서 생성한 질의 · 정답 · 근거',
     'nb12_golden_llm 출력(out/nb12_golden_review_*.csv) 붙여넣기 → L~P 열 기입 · 자가검증 "통과" 부터 확인',
     cols, [9, 8, 8, 12, 11, 44, 40, 40, 14, 10, 24, 11, 40, 36, 20, 10],
     input_cols=(12, 13, 14, 15, 16))
dv(ws, ['채택', '수정 후 채택', '폐기'], f'L5:L{4 + N_ROWS}')
dv(ws, ['근거 불일치', '질문 모호', '정답 복수', '업무 무관', '중복', '기타'], f'O5:O{4 + N_ROWS}')
for v, c in (('채택', 'E2F0D9'), ('수정 후 채택', 'FFF2CC'), ('폐기', 'F8E1E1')):
    ws.conditional_formatting.add(f'L5:L{4 + N_ROWS}', CellIsRule(operator='equal', formula=[f'"{v}"'], fill=F(c)))
ws.conditional_formatting.add(f'J5:J{4 + N_ROWS}', CellIsRule(operator='equal', formula=['"보류"'], fill=F('FFF2CC')))
try:                                   # 예시 3행 — 샘플 코퍼스에서 실제 생성
    _raw, _ch = lab_io.load_raw(), lab_io.load_chunks()
    _s = lab_golden_llm.sample_chunks(_ch, _raw, per_type=2, min_len=120)
    _g = lab_golden_llm.generate(_s, n=3, use_llm=False)
    _g = lab_golden_llm.apply_check(_g, lab_golden_llm.self_check(_g, _ch))
    _rv = lab_golden_llm.to_review(_g)
    for i, r in enumerate(_rv.head(3).itertuples(index=False), 5):
        for j, v in enumerate(list(r) + ['채택', '', '', '', '홍길동'], 1):
            if j > len(cols):
                break
            x = ws.cell(i, j, v); x.font = f(color='808080', italic=True); x.fill = EXF; x.border = BOX; x.alignment = WRAP
except Exception as _ex:
    print('  (1b 예시 생략:', type(_ex).__name__, _ex, ')')
b = 4 + N_ROWS + 2
ws.cell(b, 1, '집계').font = f(bold=True, color=PRI)
for i, (k, v) in enumerate([
    ('생성 문항', f'=COUNTIF(A5:A{4 + N_ROWS},"<>")'),
    ('자가검증 통과', f'=COUNTIF(J5:J{4 + N_ROWS},"통과")'),
    ('채택', f'=COUNTIF(L5:L{4 + N_ROWS},"채택")+COUNTIF(L5:L{4 + N_ROWS},"수정 후 채택")'),
    ('폐기', f'=COUNTIF(L5:L{4 + N_ROWS},"폐기")'),
    ('채택률', f'=IFERROR((COUNTIF(L5:L{4 + N_ROWS},"채택")+COUNTIF(L5:L{4 + N_ROWS},"수정 후 채택"))/COUNTIF(L5:L{4 + N_ROWS},"<>"),"")')], b + 1):
    ws.cell(i, 1, k).font = f(bold=True); ws.cell(i, 1).border = BOX
    c = ws.cell(i, 2, v); c.fill = CALC; c.border = BOX; c.font = f()
    if k == '채택률':
        c.number_format = '0%'
note = ['자가검증 항목: 근거 실재 · 복붙 아님 · 지시어 없음 · 길이 적정 · 중복 아님 · 회수 가능(질문으로 정답 문서가 검색되는지)',
        '검수 기준: 질문만 보고 답할 수 있는가 · 정답이 근거 문장에서 도출되는가 · 정답이 하나로 특정되는가',
        '채택분 → nb12 [7] 셀로 golden/golden_llm_v1.csv 생성 → 이후 모든 평가에 고정 사용']
for i, t in enumerate(note, b + 7):
    x = ws.cell(i, 1, t); x.font = f(size=9, color='5C440C'); x.fill = F('F5EAD0'); x.border = BOX
    ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=len(cols))

# ---------------- 2b. 질의 · 답변 골든셋 (사외 정보 기반 60문항) ----------------
ws = wb.create_sheet('2b_질의응답_골든셋')
cols = ['qid', '질문', '유형', '난이도', '근거 소스', '필수 요소 (; 구분)', '채점 기준', '흔한 오답', '측정 점수', '평가자', '비고']
head(ws, '2b. 질의 · 답변 골든셋 — 사외 정보 기반 60문항',
     '문서 ID 없이 필수 요소로 채점 → 사내 골든셋 확보 전에도 정량 평가 가능 · I~K 열 기입',
     cols, [9, 46, 8, 8, 16, 44, 34, 28, 10, 10, 22], n_input=0)
ag = pd.DataFrame(AG.ROWS, columns=AG.COLUMNS)
for i, r in enumerate(ag.itertuples(), 5):
    vals = [r.qid, r.question, r.q_type, r.level, r.source_hint, r.must_include, r.scoring, r.fail_mode, '', '', '']
    for j, v in enumerate(vals, 1):
        x = ws.cell(i, j, v); x.font = f(); x.border = BOX; x.alignment = WRAP
        if j in (1, 3, 4, 9):
            x.alignment = CEN
        if j in (9, 10, 11):
            x.fill = INP
last = 4 + len(ag)
ws.freeze_panes = 'A5'
ws.auto_filter.ref = f'A4:{L(len(cols))}{last}'
dv(ws, ['1', '0.67', '0.5', '0.33', '0'], f'I5:I{last}')
b = last + 2
ws.cell(b, 1, '집계').font = f(bold=True, color=PRI)
for i, (k, v) in enumerate([
    ('채점 완료', f'=COUNT(I5:I{last})'),
    ('평균 점수', f'=IFERROR(AVERAGE(I5:I{last}),"")'),
    ('답없음 정확도', f'=IFERROR(SUMIFS(I5:I{last},C5:C{last},"답없음")/COUNTIFS(C5:C{last},"답없음",I5:I{last},"<>"),"")'),
    ('합격 판정 (평균 ≥ 0.75)', f'=IF(B{b + 2}="","",IF(B{b + 2}>=0.75,"충족","미달"))')], b + 1):
    ws.cell(i, 1, k).font = f(bold=True); ws.cell(i, 1).border = BOX
    c = ws.cell(i, 2, v); c.fill = CALC; c.border = BOX; c.font = f(); c.number_format = '0.000'

# ---------------- 2c. 답변 채점 기준 ----------------
ws = wb.create_sheet('2c_답변_채점기준')
cols = ['규칙', '내용', '예']
head(ws, '2c. 답변 채점 기준', '2b 시트의 측정 점수 부여 기준 · 사내 실정에 맞게 조정 가능', cols, [18, 68, 40], n_input=0)
for i, row in enumerate(AG.SCORING_RULES, 5):
    for j, v in enumerate(row, 1):
        x = ws.cell(i, j, v); x.font = f(bold=(j == 1)); x.border = BOX; x.alignment = WRAP

# ---------------- 8. 표준 지표 (RAGAS 계열) ----------------
ws = wb.create_sheet('8_표준지표')
cat = lab_ragas.catalog()
cols = ['구분', '지표', '정의', '계산 방식', '합격 기준', '대응 단계', '측정값', '판정', '비고']
head(ws, '8. 표준 지표 — 검색(IR) · 생성(RAGAS 계열) · 운영',
     'nb10_answer_eval 로 auto 계산 · judge = 사내 LLM 채점 · manual = 20문항 표본 확인 · G · I 열 기입',
     cols, [8, 20, 44, 14, 24, 18, 10, 9, 24], n_input=0)
for i, r in enumerate(cat.itertuples(), 5):
    for j, v in enumerate([r.구분, r.지표, r.정의, r._4, r._5, r._6, '', '', ''], 1):
        x = ws.cell(i, j, v); x.font = f(bold=(j == 2)); x.border = BOX; x.alignment = WRAP
        if j in (1, 4, 7, 8):
            x.alignment = CEN
        if j in (7, 9):
            x.fill = INP
    ws.cell(i, 8, f'=IF(G{i}="","","기준과 대조")').fill = CALC
last = 4 + len(cat)
ws.freeze_panes = 'A5'
ws.auto_filter.ref = f'A4:{L(len(cols))}{last}'
note = ['RAGAS 원 구현은 외부 LLM · 패키지 사용 → 여기서는 동일 정의를 사내 자원(임베딩 · 규칙 · 사내 LLM)으로 근사',
        'auto 지표는 표현 차이로 과소평가 가능 → 20문항은 사람 교차 확인 권장',
        'Faithfulness · Hallucination 은 상호 보완 — 둘 다 기록']
for i, t in enumerate(note, last + 2):
    x = ws.cell(i, 1, t); x.font = f(size=9, color='5C440C'); x.fill = F('F5EAD0'); x.border = BOX
    ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=9)


# ---------------- 2d. 근거 문서 연결 (질문 → 코퍼스 근거 확정) ----------------
ws = wb.create_sheet('2d_근거문서_연결')
cols = ['qid', '질문', '유형', '후보 순위', '후보 doc_id', '소스 유형', '문서 일자', '후보 청크 (앞 300자)', '점수',
        '근거 판정', '확정 doc_id', '확정 정답 문장', '검수자']
head(ws, '2d. 근거 문서 연결 — 질문 은행 → 골든셋 전환',
     'nb11_evidence_link 출력(out/nb11_evidence_link_*.csv) 붙여넣기 → J~M 열 기입 · 근거 확보분만 검색 · 답변 평가 대상',
     cols, [9, 40, 8, 8, 14, 12, 11, 52, 8, 12, 14, 40, 10], input_cols=(10, 11, 12, 13))
dv(ws, ['근거 확보', '문서 없음', '보류'], f'J5:J{4 + N_ROWS}')
b = 4 + N_ROWS + 2
ws.cell(b, 1, '집계 · 근거 확보율').font = f(size=11, bold=True, color=PRI)
agg = [('후보 행 수', f'=COUNTIF(E5:E{4 + N_ROWS},"<>")'),
       ('근거 확보 (행)', f'=COUNTIF(J5:J{4 + N_ROWS},"근거 확보")'),
       ('문서 없음 (행)', f'=COUNTIF(J5:J{4 + N_ROWS},"문서 없음")'),
       ('보류 (행)', f'=COUNTIF(J5:J{4 + N_ROWS},"보류")'),
       ('판정 완료율', f'=IFERROR(COUNTIF(J5:J{4 + N_ROWS},"<>")/COUNTIF(A5:A{4 + N_ROWS},"<>"),"")')]
for i, (k, v) in enumerate(agg, b + 1):
    x = ws.cell(i, 1, k); x.font = f(bold=True); x.border = BOX
    c = ws.cell(i, 2, v); c.fill = CALC; c.border = BOX; c.font = f(); c.number_format = '0.000'
note = ['근거 확보 = 해당 청크가 질문의 정답을 담고 있음 → 확정 doc_id · 정답 문장 기입 (청크 ID 아님)',
        '문서 없음 = 코퍼스에 근거 문서 자체가 없음 → 검색 실패가 아니라 수집 공백 · 2e 시트에 원본 등록 후 재적재',
        '보류 = 부분 근거 · 판단 유보 → 평가 대상에서 제외하고 사유 기록']
for i, t in enumerate(note, b + len(agg) + 2):
    x = ws.cell(i, 1, t); x.font = f(size=9, color='5C440C'); x.fill = F('F5EAD0'); x.border = BOX
    ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=len(cols))

# ---------------- 2e. 원본 수집 목록 ----------------
ws = wb.create_sheet('2e_원본_수집목록')
cols = ['no', '연결 qid', '소스 유형', '문서명 · 제목', '원본 URL · 파일 경로', '발행일', '수집 여부', '적재 doc_id',
        '파싱 상태', '청킹 수', '인덱싱 여부', '담당', '비고']
head(ws, '2e. 원본 수집 목록 — 골든셋의 근거가 될 원본 확보 대장',
     '2d 에서 "문서 없음" 판정된 문항의 원본을 여기 등록 → 수집 · 파싱 · 청킹 · 인덱싱 완료 후 재측정',
     cols, [6, 10, 13, 40, 46, 11, 10, 14, 12, 9, 11, 10, 24], input_cols=tuple(range(1, 14)))
dv(ws, ['뉴스', '증권사', '기관', '메일', '회의록', '사내 보고서', '임원 보고서'], f'C5:C{4 + N_ROWS}')
dv(ws, ['완료', '진행', '미착수', '수집 불가'], f'G5:G{4 + N_ROWS}')
dv(ws, ['성공', '부분 실패', '실패', '미실행'], f'I5:I{4 + N_ROWS}')
dv(ws, ['완료', '미완료'], f'K5:K{4 + N_ROWS}')
b = 4 + N_ROWS + 2
ws.cell(b, 1, '집계 · 적재 진행률').font = f(size=11, bold=True, color=PRI)
agg = [('등록 원본 수', f'=COUNTIF(D5:D{4 + N_ROWS},"<>")'),
       ('수집 완료', f'=COUNTIF(G5:G{4 + N_ROWS},"완료")'),
       ('파싱 성공', f'=COUNTIF(I5:I{4 + N_ROWS},"성공")'),
       ('인덱싱 완료', f'=COUNTIF(K5:K{4 + N_ROWS},"완료")'),
       ('평가 가능 비율', f'=IFERROR(COUNTIF(K5:K{4 + N_ROWS},"완료")/COUNTIF(D5:D{4 + N_ROWS},"<>"),"")')]
for i, (k, v) in enumerate(agg, b + 1):
    x = ws.cell(i, 1, k); x.font = f(bold=True); x.border = BOX
    c = ws.cell(i, 2, v); c.fill = CALC; c.border = BOX; c.font = f(); c.number_format = '0.000'
ex = [1, 'A001', '뉴스', '마이크론 FY26 2분기 실적 발표 — HBM 매출 비중', 'https://(사내 수집 URL)', '2026-03-20',
      '완료', 'NEWS_20260320_0012', '성공', 7, '완료', '(담당)', '예시 행 — 형식 참고용, 실제 기입 시 삭제']
for j, v in enumerate(ex, 1):
    x = ws.cell(5, j, v); x.font = f(italic=True, color='6B6B6B'); x.border = BOX; x.alignment = WRAP

from openpyxl.workbook.properties import CalcProperties
wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb._sheets = [wb[n] for n in ['0_안내', '1b_LLM골든셋_검수', '1_골든셋_검수', '2_골든셋_확정', '2b_질의응답_골든셋', '2c_답변_채점기준', '2d_근거문서_연결', '2e_원본_수집목록',
                              '3_평가_실행기록', '4_지표_정의', '8_표준지표', '5_전후비교', '6_문항별_결과', '7_답변평가']]
wb.active = 0
wb.save(OUT)
print('saved', OUT, [w.title for w in wb.worksheets])
