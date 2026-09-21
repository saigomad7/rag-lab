# rag_checklist_sheet_rev3.html 과 같은 데이터로 엑셀 생성 → rag_checklist_rev3.xlsx
import re, runpy, io, contextlib
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.utils import get_column_letter as L

with contextlib.redirect_stdout(io.StringIO()):
    G = runpy.run_path('make_checklist_sheet_rev5.py')
P1A, P1B, P2, SMOKE = G['P1A'], G['P1B'], G['P2'], G['SMOKE']
from sources_data import SOURCES, STAGES
from flows_data import PRECHECK, FAMILIES, FLOWS
from phase3_data import P3, ROUTING, PATTERNS, LINKS
from columns_data import COMMON_DOC, COMMON_CHUNK, PER_SOURCE, NOTES
P3S = [(c, n, [(re.sub(r'</?b>', '', a), b, re.sub(r'</?b>', '', cc), d, e2) for a, b, cc, d, e2 in items]) for c, n, items in P3]

OUT = 'rag_checklist_rev5.xlsx'
FONT = '맑은 고딕'
ST = {'done': '완료', 'doing': '확인중', 'todo': '미확인'}
strip = lambda s: re.sub(r'<[^>]+>', '', s).replace('&gt;', '>')

PRI = '185463'
thin = Side(style='thin', color='BFBFBF')
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
F = lambda c: PatternFill('solid', start_color=c, end_color=c)
HDR_FILL, INPUT_FILL, STG_FILL = F('E7EDEE'), F('FFFDE7'), F('F7FAFA')
KIND_FILL = {'in': F('F2F2F2'), 'norm': F('FFFFFF'), 'key': F('DAEAED'), 'rm': F('F8E1E1'), 'out': F('E2F0D9')}
f = lambda **k: Font(name=FONT, size=k.pop('size', 10), **k)
WRAP = Alignment(wrap_text=True, vertical='top')
CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)

wb = Workbook()

def title(ws, text, sub, ncol):
    ws['A1'] = text; ws['A1'].font = f(size=14, bold=True, color=PRI)
    ws['A2'] = sub; ws['A2'].font = f(size=9, color='6B6B6B')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)

def header(ws, row, cols):
    for i, c in enumerate(cols, 1):
        x = ws.cell(row, i, c); x.font = f(bold=True); x.fill = HDR_FILL; x.alignment = CEN; x.border = BOX

def widths(ws, ws_w):
    for i, w in enumerate(ws_w, 1):
        ws.column_dimensions[L(i)].width = w

def status_rules(ws, rng):
    ws.conditional_formatting.add(rng, CellIsRule(operator='equal', formula=['"완료"'], fill=F('E2F0D9'), font=Font(name=FONT, bold=True, color='375623')))
    ws.conditional_formatting.add(rng, CellIsRule(operator='equal', formula=['"확인중"'], fill=F('FFF2CC'), font=Font(name=FONT, bold=True, color='7F6000')))
    ws.conditional_formatting.add(rng, CellIsRule(operator='equal', formula=['"해당없음"'], fill=F('EDEDED'), font=Font(name=FONT, color='808080')))

def pri_rules(ws, rng):
    for p, c in [('P0', 'C00000'), ('P1', 'B26B00'), ('P2', '808080')]:
        ws.conditional_formatting.add(rng, CellIsRule(operator='equal', formula=[f'"{p}"'], font=Font(name=FONT, bold=True, color=c)))

def dv_list(ws, items, rng):
    dv = DataValidation(type='list', formula1='"' + ','.join(items) + '"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(rng)

def finish(ws, hdr_row, last_col, last_row):
    ws.freeze_panes = ws.cell(hdr_row + 1, 1)
    ws.auto_filter.ref = f'A{hdr_row}:{L(last_col)}{last_row}'
    ws.page_setup.orientation = 'landscape'; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_view.zoomScale = 90

# ---------- 안내 ----------
ws = wb.active; ws.title = '안내'
title(ws, 'RAG 단계별 체크리스트 (엑셀판) rev.5', '2026-09-21 · rag_checklist_sheet_rev5.html 과 같은 내용 · 소스별 컬럼 정의서 포함 · 사내 확인용', 4)
rows = [
 ('이 파일', 'HTML 간소화 시트 rev3의 엑셀판. 사내에서 직접 고치며 쓰는 용도'),
 ('입력하는 칸', '연노랑 칸만 입력: 현 수준 · 상태(드롭다운) · 메모 · 문서 수 · 스모크 판정'),
 ('상태 값', '미확인 / 확인중 / 완료 / 해당없음 — 드롭다운에서 선택하면 색이 자동으로 바뀜'),
 ('자동 계산', '요약 시트와 소스별 매트릭스는 수식. 상세 시트의 상태를 바꾸면 자동 갱신 (직접 입력하지 않음)'),
 ('입력 예시', "P1_적재공통 시트 S01 1행: 현 수준 = 'doc id 있음, 재수집 시 중복 체크 중', 상태 = 완료"),
 ('우선순위', 'P0 먼저 확인 · P1 다음 · P2 필요할 때'),
 ('시트 순서', '요약 → 소스별_매트릭스 → 소스별_상세 → 처리흐름_도식 → 처리흐름_판단기준 → P1_적재공통 → P1_검색 → P2_센싱 → P3_정형연계 → 정형연계_패턴 → 스모크20'),
 ('Phase 3', '정형 데이터 연계(S22~S29). 지표 정의서 양식은 metric_catalog_template_rev1.xlsx, 코드는 rag_lab/nb07_sql_router.py'),
 ('소스별_컬럼정의', '소스 유형마다 있어야 할 컬럼(권장안). J·K 열(사내 보유 · 사내 컬럼명)을 채우면 사내 현황 매핑표가 된다'),
 ('사용자 확인값 출처', '2026-09-19 대화: doc id 원천키 · 재수집 중복 체크 · 작성일/수집일 분리 · 날짜 95% 보유 · 6축 전부 사용'),
 ('도식 색', '회색 = 입력 · 청록 = 핵심 처리 · 분홍 = 제거 · 흰색 = 일반 · 연두 = 청킹/메타 산출'),
]
header(ws, 4, ['항목', '내용'])
for i, (a, b) in enumerate(rows, 5):
    ws.cell(i, 1, a).font = f(bold=True); ws.cell(i, 2, b).font = f()
    for c in (1, 2):
        ws.cell(i, c).border = BOX; ws.cell(i, c).alignment = WRAP
ws.cell(6, 2).fill = INPUT_FILL
widths(ws, [18, 110])

# ---------- 단계 시트 (P1 적재 공통 / P1 검색 / P2 센싱) ----------
STAGE_SHEETS = [('P1_적재공통', 'Phase 1 · 적재 공통 — 모든 소스에 해당 (소스별 차이는 소스별_상세)', P1A),
                ('P1_검색', 'Phase 1 · 검색 — 질의가 흐르는 순서 (S07 → S15)', P1B),
                ('P2_센싱', 'Phase 2 · 마켓 센싱 (S16 → S21)', P2),
                ('P3_정형연계', 'Phase 3 · 정형 데이터 연계 — 사내 DB · SQL × 비정형 (S22 → S29)', P3S)]
stage_index = []  # (sheet, code, name)
for sname, stitle, groups in STAGE_SHEETS:
    ws = wb.create_sheet(sname)
    title(ws, stitle, '연노랑 칸(현 수준 · 상태 · 메모)만 입력', 9)
    cols = ['단계', '단계명', 'No', '체크 항목', '현 수준', '개선 방향', '우선', '상태', '메모']
    header(ws, 4, cols); r = 5
    for code, name, items in groups:
        stage_index.append((sname, code, name))
        for i, (chk, cur, imp, pri, st) in enumerate(items):
            vals = [code, name, f'{code[1:]}-{i+1}', strip(chk), cur, strip(imp), pri, ST[st], '']
            for c, v in enumerate(vals, 1):
                x = ws.cell(r, c, v); x.font = f(); x.border = BOX; x.alignment = WRAP
            for c in (1, 2, 3, 7, 8):
                ws.cell(r, c).alignment = CEN
            ws.cell(r, 1).fill = STG_FILL; ws.cell(r, 1).font = f(bold=True, color=PRI)
            for c in (5, 8, 9):
                ws.cell(r, c).fill = INPUT_FILL
            r += 1
    last = r - 1
    status_rules(ws, f'H5:H{last}'); pri_rules(ws, f'G5:G{last}')
    dv_list(ws, ['미확인', '확인중', '완료', '해당없음'], f'H5:H{last}')
    dv_list(ws, ['P0', 'P1', 'P2'], f'G5:G{last}')
    widths(ws, [7, 14, 6, 40, 30, 38, 6, 9, 24])
    finish(ws, 4, 9, last)

# ---------- 소스별_상세 ----------
wd = wb.create_sheet('소스별_상세', 1)
title(wd, '소스별 상세 — 소스마다 수집 · 파싱 · 청킹 · 메타 · 권한', '연노랑 칸만 입력 · L열(키)은 매트릭스 연결용 수식', 12)
header(wd, 4, ['소스', 'DOC_TYPE', '구분', '단계', '체크 항목', '현 수준', '필요사항', '우선', '상태', '보안등급', '메모', '키'])
r = 5
for name, dt, grp, lvl, st in SOURCES:
    for sg in STAGES:
        chk, cur, imp, pri, stt, short = st[sg]
        vals = [name, dt, grp, sg, strip(chk), cur, strip(imp), pri, ST[stt], lvl, '', f'=A{r}&"|"&D{r}']
        for c, v in enumerate(vals, 1):
            x = wd.cell(r, c, v); x.font = f(); x.border = BOX; x.alignment = WRAP
        for c in (2, 3, 4, 8, 9, 10):
            wd.cell(r, c).alignment = CEN
        wd.cell(r, 1).font = f(bold=True, color=PRI); wd.cell(r, 1).fill = STG_FILL
        for c in (6, 9, 11):
            wd.cell(r, c).fill = INPUT_FILL
        wd.cell(r, 12).font = f(size=8, color='A6A6A6')
        r += 1
dl = r - 1
status_rules(wd, f'I5:I{dl}'); pri_rules(wd, f'H5:H{dl}')
dv_list(wd, ['미확인', '확인중', '완료', '해당없음'], f'I5:I{dl}')
dv_list(wd, ['P0', 'P1', 'P2'], f'H5:H{dl}')
widths(wd, [13, 13, 6, 7, 38, 28, 38, 6, 9, 8, 22, 14])
finish(wd, 4, 12, dl)

# ---------- 소스별_매트릭스 (수식 연결) ----------
wm = wb.create_sheet('소스별_매트릭스', 1)
title(wm, '소스별 매트릭스 — 소스 9종 × 적재 5단계', '칸 = 상태(소스별_상세에서 자동) · 핵심 필요사항 · 우선 | 문서 수만 입력', 10)
header(wm, 4, ['소스', 'DOC_TYPE', '구분', '문서 수'] + STAGES + ['보안등급'])
r = 5
for name, dt, grp, lvl, st in SOURCES:
    wm.cell(r, 1, name).font = f(bold=True, color=PRI)
    wm.cell(r, 2, dt); wm.cell(r, 3, grp); wm.cell(r, 4).fill = INPUT_FILL
    for j, sg in enumerate(STAGES):
        chk, cur, imp, pri, stt, short = st[sg]
        col = 5 + j
        wm.cell(r, col, f'=IFERROR(INDEX(\'소스별_상세\'!$I$5:$I${dl},MATCH($A{r}&"|"&{L(col)}$4,\'소스별_상세\'!$L$5:$L${dl},0)),"")&" · {short} ({pri})"')
    wm.cell(r, 10, lvl)
    for c in range(1, 11):
        x = wm.cell(r, c); x.border = BOX; x.alignment = CEN if c != 1 else Alignment(vertical='center')
        if c != 1: x.font = f()
    r += 1
ml = r - 1
rng = f'E5:I{ml}'
wm.conditional_formatting.add(rng, FormulaRule(formula=['LEFT(E5,2)="완료"'], fill=F('E2F0D9')))
wm.conditional_formatting.add(rng, FormulaRule(formula=['LEFT(E5,3)="확인중"'], fill=F('FFF2CC')))
widths(wm, [14, 13, 6, 9, 24, 24, 22, 24, 26, 8])
for i in range(5, ml + 1):
    wm.row_dimensions[i].height = 34
finish(wm, 4, 10, ml)

# ---------- 처리흐름_도식 (셀로 그린 흐름도) ----------
wf = wb.create_sheet('처리흐름_도식', 3)
title(wf, '소스별 처리 흐름 (청킹 전) — 셀 도식', '색: 회색=입력 · 청록=핵심 처리 · 분홍=제거 · 흰색=일반 · 연두=청킹/메타 산출 · 세로로 여러 줄인 칸 = 분기', 12)
r = 4
wf.cell(r, 1, '계열').font = f(bold=True); r += 1
for fam, srcs, proc in FAMILIES:
    wf.cell(r, 1, fam).font = f(bold=True, color=PRI); wf.cell(r, 2, srcs).font = f(); wf.cell(r, 4, proc).font = f(color='1F4E79')
    wf.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    wf.merge_cells(start_row=r, start_column=4, end_row=r, end_column=9)
    r += 1
r += 1
for i, (src, fam, steps, rows_, ex) in enumerate(FLOWS, 1):
    wf.cell(r, 1, f'{i}. {src}').font = f(size=11, bold=True, color=PRI)
    wf.cell(r, 3, f'계열 · {fam}').font = f(size=9, color='6B6B6B'); r += 1
    col = 1; maxlines = 2
    for j, s in enumerate(steps):
        if s[0] == 'box':
            txt, kind = f'{s[1]}\n{s[2]}', s[3]
        else:
            txt = '\n'.join(f'▸ {b[1]} · {b[2]}' for b in s[1]); kind = 'key'; maxlines = max(maxlines, len(s[1]) + 1)
        x = wf.cell(r, col, txt); x.fill = KIND_FILL[kind]; x.border = BOX; x.alignment = CEN
        x.font = f(bold=(kind == 'key'))
        if j < len(steps) - 1:
            a = wf.cell(r, col + 1, '→'); a.font = f(size=12, color='8C8C8C'); a.alignment = CEN
        col += 2
    wf.row_dimensions[r].height = 16 * maxlines + 6
    r += 1
    wf.cell(r, 1, '청크 예시').font = f(size=8, bold=True, color='6B6B6B')
    x = wf.cell(r, 2, ex); x.font = Font(name='Consolas', size=9, color='D2E0E2'); x.fill = F('0F2A31'); x.alignment = WRAP
    wf.merge_cells(start_row=r, start_column=2, end_row=r, end_column=11)
    wf.row_dimensions[r].height = 15 * (ex.count('\n') + 1) + 8
    r += 2
widths(wf, [16, 3, 16, 3, 16, 3, 16, 3, 16, 3, 16, 3])
for c in (1, 3, 5, 7, 9, 11):
    wf.column_dimensions[L(c)].width = 17
wf.sheet_view.zoomScale = 90
wf.page_setup.orientation = 'landscape'; wf.sheet_properties.pageSetUpPr.fitToPage = True; wf.page_setup.fitToHeight = 0

# ---------- 처리흐름_판단기준 ----------
wj = wb.create_sheet('처리흐름_판단기준', 4)
title(wj, '소스별 처리 흐름 — 단계별 처리 내용 · 판단 기준', '맨 위 "선확인" 3행부터 · 연노랑 칸만 입력', 7)
header(wj, 4, ['소스', '단계', '처리 내용', '판단 기준 · 확인 방법', '현 수준', '상태', '메모'])
r = 5
for a, b, c in PRECHECK:
    vals = ['① 선확인', a, b, c, '', '미확인', '']
    for k, v in enumerate(vals, 1):
        x = wj.cell(r, k, strip(v)); x.font = f(bold=(k == 1)); x.border = BOX; x.alignment = WRAP
    r += 1
for src, fam, steps, rows_, ex in FLOWS:
    for a, b, c in rows_:
        vals = [src, a, strip(b), strip(c), '', '미확인', '']
        for k, v in enumerate(vals, 1):
            x = wj.cell(r, k, v); x.font = f(); x.border = BOX; x.alignment = WRAP
        r += 1
jl = r - 1
for i in range(5, jl + 1):
    wj.cell(i, 1).font = f(bold=True, color=PRI); wj.cell(i, 1).fill = STG_FILL
    for c in (5, 6, 7): wj.cell(i, c).fill = INPUT_FILL
    wj.cell(i, 6).alignment = CEN
status_rules(wj, f'F5:F{jl}'); dv_list(wj, ['미확인', '확인중', '완료', '해당없음'], f'F5:F{jl}')
widths(wj, [13, 16, 44, 44, 28, 9, 22])
finish(wj, 4, 7, jl)

# ---------- 소스별_컬럼정의 ----------
wc = wb.create_sheet('소스별_컬럼정의')
title(wc, '소스별 컬럼 정의서 — 어떤 컬럼이 있어야 하는가 (권장안)',
      '연노랑 두 칸(사내 보유 · 사내 컬럼명)을 채우면 매핑표가 된다 · 필수 M / 권장 R / 선택 O', 11)
header(wc, 4, ['구분', '소스', '컬럼명', '논리명', '타입', '필수', '어디서 오나', '쓰이는 곳', '샘플값', '사내 보유', '사내 컬럼명'])
NEED_KO = {'M': '필수', 'R': '권장', 'O': '선택'}
r = 5
def _put(grp, src, items):
    global r
    for c_, ko, ty, nd, o, use, sam in items:
        vals = [grp, src, c_, ko, ty, NEED_KO[nd], o, use, sam, '', '']
        for k, v in enumerate(vals, 1):
            x = wc.cell(r, k, v); x.font = f(); x.border = BOX; x.alignment = WRAP
        wc.cell(r, 1).font = f(bold=True, color=PRI); wc.cell(r, 1).fill = STG_FILL
        wc.cell(r, 3).font = Font(name='Consolas', size=10, color='1F4E79', bold=True)
        wc.cell(r, 9).font = Font(name='Consolas', size=9)
        for k in (2, 6):
            wc.cell(r, k).alignment = CEN
        for k in (10, 11):
            wc.cell(r, k).fill = INPUT_FILL
        r += 1
_put('공통', '문서', COMMON_DOC)
_put('공통', '청크', COMMON_CHUNK)
for key, (ko, items) in PER_SOURCE.items():
    _put('소스별', ko, items)
cl = r - 1
dv_list(wc, ['보유', '파생 가능', '없음', '해당없음'], f'J5:J{cl}')
for p_, c_ in [('필수', 'C00000'), ('권장', 'B26B00'), ('선택', '808080')]:
    wc.conditional_formatting.add(f'F5:F{cl}', CellIsRule(operator='equal', formula=[f'"{p_}"'], font=Font(name=FONT, bold=True, color=c_)))
wc.conditional_formatting.add(f'J5:J{cl}', CellIsRule(operator='equal', formula=['"보유"'], fill=F('E2F0D9')))
wc.conditional_formatting.add(f'J5:J{cl}', CellIsRule(operator='equal', formula=['"파생 가능"'], fill=F('FFF2CC')))
wc.conditional_formatting.add(f'J5:J{cl}', CellIsRule(operator='equal', formula=['"없음"'], fill=F('F8E1E1')))
widths(wc, [8, 13, 20, 16, 20, 7, 26, 22, 34, 11, 16])
finish(wc, 4, 11, cl)
r += 1
wc.cell(r, 1, '정리하면서 놓치기 쉬운 것').font = f(size=11, bold=True, color=PRI); r += 1
for a_, b_ in NOTES:
    x = wc.cell(r, 1, a_); x.font = f(bold=True); x.border = BOX; x.alignment = WRAP
    wc.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    y = wc.cell(r, 3, b_); y.font = f(); y.border = BOX; y.alignment = WRAP
    wc.merge_cells(start_row=r, start_column=3, end_row=r, end_column=11)
    wc.row_dimensions[r].height = 28
    r += 1

# ---------- 정형연계_패턴 ----------
wp = wb.create_sheet('정형연계_패턴')
title(wp, '정형 × 비정형 결합 패턴 (Phase 3)', '질문 유형별로 A~D 중 하나를 쓴다 · 색: 회색=입력 · 청록=핵심 · 분홍=거절 · 연두=산출', 12)
r = 4
wp.cell(r, 1, '라우팅').font = f(size=11, bold=True, color=PRI); r += 1
col = 1
for j, st in enumerate(ROUTING):
    if st[0] == 'box':
        txt, kind = f'{st[1]}\n{st[2]}', st[3]
    else:
        txt = '\n'.join(f'▸ {b[1]} · {b[2]}' for b in st[1]); kind = 'key'
    x = wp.cell(r, col, txt); x.fill = KIND_FILL[kind]; x.border = BOX; x.alignment = CEN; x.font = f(bold=(kind == 'key'))
    if j < len(ROUTING) - 1:
        a = wp.cell(r, col + 1, '→'); a.font = f(size=12, color='8C8C8C'); a.alignment = CEN
    col += 2
wp.row_dimensions[r].height = 74
r += 2
for i, (ttl, desc, steps, ex) in enumerate(PATTERNS, 1):
    wp.cell(r, 1, ttl).font = f(size=11, bold=True, color=PRI)
    wp.cell(r, 4, desc).font = f(size=9, color='6B6B6B')
    wp.merge_cells(start_row=r, start_column=4, end_row=r, end_column=12)
    r += 1
    col, maxl = 1, 2
    for j, st in enumerate(steps):
        if st[0] == 'box':
            txt, kind = f'{st[1]}\n{st[2]}', st[3]
        else:
            txt = '\n'.join(f'▸ {b[1]} · {b[2]}' for b in st[1]); kind = 'key'; maxl = max(maxl, len(st[1]) + 1)
        x = wp.cell(r, col, txt); x.fill = KIND_FILL[kind]; x.border = BOX; x.alignment = CEN; x.font = f(bold=(kind == 'key'))
        if j < len(steps) - 1:
            a = wp.cell(r, col + 1, '→'); a.font = f(size=12, color='8C8C8C'); a.alignment = CEN
        col += 2
    wp.row_dimensions[r].height = 16 * maxl + 8
    r += 1
    wp.cell(r, 1, '출력 예시').font = f(size=8, bold=True, color='6B6B6B')
    x = wp.cell(r, 2, ex); x.font = Font(name='Consolas', size=9, color='D2E0E2'); x.fill = F('0F2A31'); x.alignment = WRAP
    wp.merge_cells(start_row=r, start_column=2, end_row=r, end_column=11)
    wp.row_dimensions[r].height = 15 * (ex.count('\n') + 1) + 8
    r += 2
wp.cell(r, 1, '기존 단계와의 연결').font = f(size=11, bold=True, color=PRI); r += 1
for col, lab, e_ in ((1, '기존 단계 (Phase 1 · 2)', 2), (3, 'Phase 3에서', 4), (5, '무엇이 달라지나', 12)):
    x = wp.cell(r, col, lab); x.font = f(bold=True); x.fill = HDR_FILL; x.alignment = CEN; x.border = BOX
    wp.merge_cells(start_row=r, start_column=col, end_row=r, end_column=e_)
r += 1
for a_, b_, c_ in LINKS:
    for col, v, e_ in ((1, a_, 2), (3, b_, 4), (5, c_, 12)):
        x = wp.cell(r, col, v); x.font = f(bold=(col == 1)); x.border = BOX; x.alignment = WRAP
        wp.merge_cells(start_row=r, start_column=col, end_row=r, end_column=e_)
    wp.row_dimensions[r].height = 30
    r += 1
for c in range(1, 13):
    wp.column_dimensions[L(c)].width = 17 if c % 2 else 3
wp.column_dimensions['A'].width = 18; wp.column_dimensions['C'].width = 20
wp.page_setup.orientation = 'landscape'; wp.sheet_properties.pageSetUpPr.fitToPage = True; wp.page_setup.fitToHeight = 0

# ---------- 스모크20 ----------
wsm = wb.create_sheet('스모크20')
title(wsm, '스모크 테스트 20문항 — 사내에서 돌리고 결과만 입력', '질문 원문 · 기대 근거는 smoke_test_20_rev1.html · 실패 유형 ①검색 누락 ②엉뚱한 청크 ③파싱 깨짐 ④답변 환각 ⑤권한 노출', 7)
header(wsm, 4, ['No', '유형', '질문 (요약)', '검색 판정', '답변 판정', '실패 유형', '메모'])
r = 5
for no, t, q in SMOKE:
    for k, v in enumerate([no, t, q, '', '', '', ''], 1):
        x = wsm.cell(r, k, v); x.font = f(); x.border = BOX; x.alignment = WRAP
    for c in (1, 2, 4, 5, 6): wsm.cell(r, c).alignment = CEN
    for c in (4, 5, 6, 7): wsm.cell(r, c).fill = INPUT_FILL
    r += 1
sl = r - 1
dv_list(wsm, ['적중', '순위 낮음', '누락'], f'D5:D{sl}')
dv_list(wsm, ['정답', '부분', '오답', '자료 없음'], f'E5:E{sl}')
dv_list(wsm, ['정상', '①검색 누락', '②엉뚱한 청크', '③파싱 깨짐', '④답변 환각', '⑤권한 노출'], f'F5:F{sl}')
widths(wsm, [7, 8, 42, 11, 11, 15, 30])
finish(wsm, 4, 7, sl)

# ---------- 요약 (수식) ----------
wsum = wb.create_sheet('요약', 1)
title(wsum, '요약 — 단계별 · 소스별 진행 현황', '전부 수식 · 각 시트의 상태 칸을 바꾸면 자동 갱신', 8)
header(wsum, 4, ['구분', '코드', '이름', '항목', '완료', '확인중', '미확인', '완료율'])
r = 5; first = r
grp_label = {'P1_적재공통': 'P1 적재 공통', 'P1_검색': 'P1 검색', 'P2_센싱': 'P2 센싱', 'P3_정형연계': 'P3 정형연계'}
for sname, code, name in stage_index:
    q = f"'{sname}'"
    vals = [grp_label[sname], code, name,
            f'=COUNTIF({q}!$A:$A,B{r})',
            f'=COUNTIFS({q}!$A:$A,B{r},{q}!$H:$H,"완료")',
            f'=COUNTIFS({q}!$A:$A,B{r},{q}!$H:$H,"확인중")',
            f'=D{r}-E{r}-F{r}-COUNTIFS({q}!$A:$A,B{r},{q}!$H:$H,"해당없음")',
            f'=IF(D{r}=0,0,E{r}/D{r})']
    for k, v in enumerate(vals, 1):
        wsum.cell(r, k, v)
    r += 1
for name, dt, grp, lvl, st in SOURCES:
    q = "'소스별_상세'"
    vals = ['소스별 적재', dt, name,
            f'=COUNTIF({q}!$A:$A,C{r})',
            f'=COUNTIFS({q}!$A:$A,C{r},{q}!$I:$I,"완료")',
            f'=COUNTIFS({q}!$A:$A,C{r},{q}!$I:$I,"확인중")',
            f'=D{r}-E{r}-F{r}-COUNTIFS({q}!$A:$A,C{r},{q}!$I:$I,"해당없음")',
            f'=IF(D{r}=0,0,E{r}/D{r})']
    for k, v in enumerate(vals, 1):
        wsum.cell(r, k, v)
    r += 1
q = "'처리흐름_판단기준'"
vals = ['처리 흐름', 'FLOW', '판단기준 전체', f'=COUNTIF({q}!$A$5:$A${jl},"<>")', f'=COUNTIF({q}!$F$5:$F${jl},"완료")',
        f'=COUNTIF({q}!$F$5:$F${jl},"확인중")', f'=D{r}-E{r}-F{r}-COUNTIF({q}!$F$5:$F${jl},"해당없음")', f'=IF(D{r}=0,0,E{r}/D{r})']
for k, v in enumerate(vals, 1):
    wsum.cell(r, k, v)
r += 1
last = r - 1
for k, v in enumerate(['합계', '', '', f'=SUM(D{first}:D{last})', f'=SUM(E{first}:E{last})', f'=SUM(F{first}:F{last})', f'=SUM(G{first}:G{last})', f'=IF(D{r}=0,0,E{r}/D{r})'], 1):
    x = wsum.cell(r, k, v); x.font = f(bold=True); x.fill = HDR_FILL
tot = r
for i in range(first, tot + 1):
    for c in range(1, 9):
        x = wsum.cell(i, c); x.border = BOX
        if i != tot: x.font = f(bold=(c == 1), color=(PRI if c == 1 else '000000'))
        x.alignment = CEN if c != 3 else Alignment(vertical='center')
    wsum.cell(i, 8).number_format = '0%'
wsum.conditional_formatting.add(f'E{first}:E{tot}', CellIsRule(operator='greaterThan', formula=['0'], fill=F('E2F0D9')))
wsum.conditional_formatting.add(f'F{first}:F{tot}', CellIsRule(operator='greaterThan', formula=['0'], fill=F('FFF2CC')))
# 스모크 집계
r = tot + 2
wsum.cell(r, 1, '스모크 20 — 실패 유형 집계').font = f(size=11, bold=True, color=PRI); r += 1
header(wsum, r, ['실패 유형', '', '', '건수']); r += 1
s0 = r
for lab in ['정상', '①검색 누락', '②엉뚱한 청크', '③파싱 깨짐', '④답변 환각', '⑤권한 노출']:
    wsum.cell(r, 1, lab); wsum.cell(r, 4, f"=COUNTIF('스모크20'!$F$5:$F${sl},A{r})")
    for c in (1, 4): wsum.cell(r, c).border = BOX; wsum.cell(r, c).font = f()
    r += 1
wsum.cell(r, 1, '미기입').font = f(color='808080'); wsum.cell(r, 4, f"=COUNTIF('스모크20'!$F$5:$F${sl},\"\")").font = f(color='808080')
widths(wsum, [13, 12, 20, 8, 8, 8, 8, 9])
wsum.freeze_panes = 'A5'
wsum.page_setup.orientation = 'portrait'; wsum.sheet_properties.pageSetUpPr.fitToPage = True; wsum.page_setup.fitToHeight = 0

# 시트 순서 정리
order = ['안내', '요약', '소스별_매트릭스', '소스별_상세', '소스별_컬럼정의', '처리흐름_도식', '처리흐름_판단기준', 'P1_적재공통', 'P1_검색', 'P2_센싱', 'P3_정형연계', '정형연계_패턴', '스모크20']
wb._sheets = [wb[n] for n in order]
wb.active = 1
from openpyxl.workbook.properties import CalcProperties
wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb.save(OUT)
print('saved', OUT, [ws.title for ws in wb.worksheets])
