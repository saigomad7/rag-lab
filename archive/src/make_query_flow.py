# -*- coding: utf-8 -*-
"""질의 1건이 비정형 + 정형을 함께 도는 과정 — 한 장짜리 도식 (정적 HTML, T2)"""
import html
import flows_render as FR

e = html.escape
B = lambda t, s, k='norm': ('box', t, s, k)
BR = lambda *xs: ('br', list(xs))

Q = '3분기 eSSD 계약가격이 오른 이유가 뭐야? 우리 출하량은 어떻게 됐고?'

MAIN = [
 B('질문', '마케팅 담당', 'in'),
 B('질의 분석', '기간 · 제품 · 지표', 'key'),
 B('라우팅', '혼합 판정', 'key'),
 BR(B('정형 경로', 'SQL → 표', 'out'), B('비정형 경로', '검색 → 청크', 'out')),
 B('컨텍스트 합치기', '표 + 청크 + 출처', 'norm'),
 B('사내 LLM', '인용 · 모름 규칙', 'key'),
 B('답변 · 로그', '수치 출처 + 문서 인용', 'out'),
]

STEPS = [
 ('1', '질의 분석 — 질문에서 무엇을 뽑나', 'S08 · S24', [
   ('기간', '"3분기" → <code>YM BETWEEN 202607 AND 202609</code>'),
   ('제품', '"eSSD" → 코드값 사전 → <code>PRODUCT_CODE = P-ESSD</code>'),
   ('지표', '"계약가격" → M002, "출하량" → M001 (지표 정의서)'),
   ('의도', '수치(얼마) + 이유(왜) 둘 다 → <b>혼합</b>'),
   ('권한', '사용자 그룹 → 비정형 ACL 필터 · 정형 행 접근 제한 동시 적용'),
 ], None),

 ('2-A', '정형 경로 — 숫자는 DB에서', 'S25', [
   ('SQL 생성', '지표 정의서의 집계식으로 조립 (또는 사내 LLM 생성)'),
   ('정적 검증', 'SELECT 전용 · 허용 목록 · LIMIT — 통과해야 실행'),
   ('실행', '읽기 전용 계정 · 타임아웃 · 행 수 상한'),
 ], ('sql', """SELECT YM, SUM(AMT_USD)/NULLIF(SUM(QTY),0) AS 계약가
FROM V_PRICE_MONTHLY
WHERE PRICE_TYPE='CONTRACT'
  AND YM BETWEEN '202607' AND '202609'
  AND PRODUCT_CODE IN ('P-ESSD')
GROUP BY YM ORDER BY YM
FETCH FIRST 200 ROWS ONLY

── 결과 ─────────────────────────
| YM     | 계약가(USD/GB) | 출하량(EB) |
| 202607 | 1.53           | 23.11      |
| 202608 | 1.56  (+2.0%)  | 23.79      |
| 202609 | 1.60  (+2.6%)  | 24.66      |""")),

 ('2-B', '비정형 경로 — 이유는 문서에서', 'S09 ~ S12', [
   ('검색', '하이브리드(BM25 + Dense/Sparse) + <b>같은 기간 필터</b>'),
   ('결합 · 리랭크', 'RRF로 합치고 리랭커로 정렬'),
   ('다양성', 'MMR · 재송고 접기 · 문서당 최대 3개'),
 ], ('doc', """[1 | 증권사 | ○○증권 | 2026-08-12] 서버 고객 재고 소진으로 3분기 계약가
    상승 전망. eSSD는 AI 서버 스토리지 수요가 견조 …
[2 | 뉴스 | 전자신문 | 2026-08-09] 경쟁사 감산 발표로 공급 축소 …
[3 | 사내 회의록 | 시장분석팀 | 2026-09-17] 안건 2. 4Q 전망 유지, 고객별 발주
    재확인 (담당 박○○, 9/24)""")),

 ('3', '컨텍스트 합치기 — 표와 문서에 출처 라벨', 'S26', [
   ('표', '[DB | V_PRICE_MONTHLY | 조건 | 집계식 | 조회 2026-09-20 10:12]'),
   ('문서', '[번호 | 유형 | 기관 | 날짜] 라벨을 청크마다'),
   ('예산', '토큰 예산 안에서 표 20행 + 청크 5~8개'),
 ], None),

 ('4', '답변 — 수치는 DB 출처, 설명은 문서 인용', 'S14 · S27', [
   ('규칙', '문장마다 근거 번호. 근거 없으면 "확인된 자료 없음"'),
   ('충돌', 'DB와 문서 수치가 다르면 <b>DB 우선 + 문서는 시점과 함께 병기</b>'),
 ], ('ans', """3분기 eSSD 계약가격은 7월 1.53 → 9월 1.60 USD/GB 로 약 4.6% 올랐습니다 [DB].
같은 기간 출하량도 23.11 → 24.66 EB 로 늘었습니다 [DB].

상승 요인으로는 ① 서버 고객의 재고 소진에 따른 수요 회복 [1], ② 경쟁사 감산
발표로 인한 공급 축소 [2] 가 지목됩니다. 사내에서는 4Q 전망을 유지하기로
했고, 고객별 발주를 재확인 중입니다 [3].

주의: [1]의 9월 전망치(1.62)는 예측이고, 위 수치는 DB 실적(1.60)입니다.

[DB] V_PRICE_MONTHLY · PRICE_TYPE='CONTRACT' · 3Q26 · 조회 2026-09-20 10:12""")),
]

CSS = """
:root{--ink:#111B1E;--ink2:#2A393D;--muted:#5B6A6E;--faint:#87959A;--bg:#D8E0E1;--surface:#F7FAFA;--surface2:#ECF2F2;
 --line:#BFCACB;--hair:#D9E2E2;--pri:#185463;--pri-wash:#DAEAED;--warn-wash:#F5EAD0;--warn-line:#DCC79B;--warn-ink:#5C440C;
 --dk:#111B1E;--dk-h:#F3F9FA;--dk-sd:#8FA1A5;--mono:Consolas,"D2Coding","SFMono-Regular",monospace;
 --sans:"IBM Plex Sans KR","Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.7;padding:0 18px 70px}
.wrap{max-width:1080px;margin:0 auto}
header{padding:46px 0 24px;border-bottom:2px solid var(--ink)}
.kicker{font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--pri);margin:0 0 14px}
h1{font-size:clamp(23px,4vw,34px);font-weight:700;letter-spacing:-.03em;line-height:1.25;margin:0 0 14px}
.qbox{background:var(--dk);color:var(--dk-h);border-radius:3px;padding:18px 20px;margin:18px 0 0}
.qbox small{display:block;color:var(--dk-sd);font-family:var(--mono);font-size:11px;letter-spacing:.1em;margin-bottom:6px}
.qbox b{font-size:clamp(15px,2.2vw,19px);font-weight:600}
.meta{display:flex;flex-wrap:wrap;gap:6px 20px;font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-top:14px}
h2{font-size:20px;font-weight:600;letter-spacing:-.02em;margin:34px 0 10px}
p.d{color:var(--ink2);margin:0 0 12px;max-width:76ch}
.step{background:var(--surface);border:1px solid var(--line);border-radius:3px;margin:12px 0}
.sh{display:flex;gap:10px;align-items:baseline;background:var(--surface2);border-bottom:1px solid var(--hair);padding:9px 14px;flex-wrap:wrap}
.sh .n{font-family:var(--mono);font-size:11px;font-weight:700;color:#fff;background:var(--pri);border-radius:2px;padding:1px 8px}
.sh b{font-size:15px}
.sh span{font-family:var(--mono);font-size:11px;color:var(--faint);margin-left:auto}
.kv{padding:10px 14px}
.kv div{display:grid;grid-template-columns:82px 1fr;gap:10px;padding:3px 0;font-size:13.5px;color:var(--ink2)}
.kv div b:first-child{color:var(--pri)}
.kv code{font-family:var(--mono);font-size:12px;background:var(--surface2);border:1px solid var(--hair);padding:0 4px;border-radius:2px}
pre{margin:0;padding:12px 14px;font-family:var(--mono);font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;border-top:1px solid var(--hair)}
pre.sql{background:#0F2A31;color:#D2E0E2} pre.sql::before{content:"정형 · SQL 과 결과";display:block;color:#85CEDB;font-size:10px;letter-spacing:.1em;margin-bottom:6px}
pre.doc{background:#14212B;color:#D6E2EA} pre.doc::before{content:"비정형 · 검색된 청크";display:block;color:#8FC2DB;font-size:10px;letter-spacing:.1em;margin-bottom:6px}
pre.ans{background:#13251C;color:#DCEBE1} pre.ans::before{content:"최종 답변";display:block;color:#8FD3B4;font-size:10px;letter-spacing:.1em;margin-bottom:6px}
.note{background:var(--warn-wash);border:1px solid var(--warn-line);border-radius:3px;padding:14px 18px;margin:20px 0 0;font-size:13.5px;color:var(--warn-ink)}
.note b{font-weight:600}
footer{padding:36px 0 0;font-family:var(--mono);font-size:11px;color:var(--faint)}
h3{font-size:16px;margin:26px 0 8px;color:var(--pri)}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:3px;background:var(--surface);margin:10px 0}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:12.5px}
th{background:var(--dk);color:#E4EDEE;text-align:left;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;padding:8px 10px;white-space:nowrap;font-weight:500}
td{padding:8px 10px;border-top:1px solid var(--hair);vertical-align:top;color:var(--ink2);line-height:1.55}
td.k{font-weight:600;color:var(--ink);white-space:nowrap}
td.m{font-family:var(--mono);font-size:11.5px;white-space:nowrap}
tr:nth-child(even) td{background:var(--surface2)}
.good,.bad{border-radius:3px;padding:10px 12px;font-size:13px;margin:6px 0}
.good{background:#E8F2E8;border:1px solid #9CC29C} .bad{background:#F8E1E1;border:1px solid #D9A8B0}
.good b{color:#2C5F2C} .bad b{color:#8C2F3E}
.good code,.bad code{font-family:var(--mono);font-size:11.5px;background:#fff;border:1px solid var(--hair);padding:0 4px;border-radius:2px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.ck{list-style:none;margin:8px 0;padding:0}
.ck li{padding:5px 0 5px 24px;position:relative;font-size:13.5px;color:var(--ink2)}
.ck li::before{content:"☐";position:absolute;left:0;color:var(--pri);font-size:15px}
@media (max-width:640px){ body{padding:0 12px 50px} .kv div{grid-template-columns:1fr;gap:0} .sh span{margin-left:0;width:100%} .two{grid-template-columns:1fr} table{min-width:560px} }
"""


# ---------------- 부록: 지표 정의서 샘플 ----------------
def T(head, rows, cls=''):
    h = '<div class="tw"><table><tr>' + ''.join(f'<th>{c}</th>' for c in head) + '</tr>'
    for r in rows:
        h += '<tr>' + ''.join(f'<td class="{c}">{v}</td>' for c, v in r) + '</tr>'
    return h + '</table></div>'

APX = ['<h2>부록 · 지표 정의서는 이렇게 만든다</h2>',
 '<p class="d">앞의 질문 하나를 답하기 위해 카탈로그에 무엇이 있어야 했는지를 실제 값으로 보여 드립니다. '
 '네 개 시트가 각각 SQL의 다른 부분을 만듭니다. 이 네 줄이 없으면 위의 SQL은 나오지 않습니다.</p>',

 '<h3>A-1. 지표정의 — 업무 용어를 집계식으로 (SELECT 절이 여기서 나온다)</h3>',
 T(['지표ID', '지표명', '별칭 (; 구분)', '한 줄 정의', '대상 뷰', '집계식 (SQL)', '기본 필터', '단위', '기간'],
   [[('m', 'M001'), ('k', '출하량'), ('', '출하;shipment;판매량'), ('', '기간 중 고객에게 출하한 물량'), ('m', 'V_SALES_MONTHLY'),
     ('m', 'SUM(SHIP_QTY_EB)'), ('m', "STATUS='CONFIRMED'"), ('', 'EB'), ('', '월')],
    [('m', 'M002'), ('k', '계약가격'), ('', '계약가;ASP;contract price'), ('', '월 단위 확정 계약 단가(가중평균)'), ('m', 'V_PRICE_MONTHLY'),
     ('m', 'SUM(AMT_USD)/NULLIF(SUM(QTY),0)'), ('m', "PRICE_TYPE='CONTRACT'"), ('', 'USD/GB'), ('', '월')],
    [('m', 'M003'), ('k', '재고주수'), ('', '재고 주수;WOI'), ('', '기말 재고 ÷ 주 평균 출하량'), ('m', 'V_INVENTORY_WEEKLY'),
     ('m', 'SUM(INV_QTY)/NULLIF(AVG(WEEKLY_SHIP),0)'), ('', ''), ('', '주'), ('', '주')]]),
 '<p class="d" style="font-size:13.5px"><b>기본 필터</b>가 중요합니다. "출하량"은 확정 건만 세야 하는데, 이 조건을 적어 두지 않으면 '
 'LLM 이 취소 건까지 더해도 아무도 알아채지 못합니다.</p>',

 '<h3>A-2. 코드값사전 — 말을 코드로 (WHERE 절의 제품 조건이 여기서 나온다)</h3>',
 T(['구분', '코드', '표준명', '별칭 (; 구분)', '사용 컬럼'],
   [[('', '제품'), ('m', 'P-ESSD'), ('k', 'eSSD'), ('', 'eSSD;enterprise SSD;기업용 SSD;이에스에스디'), ('m', 'PRODUCT_CODE')],
    [('', '제품'), ('m', 'P-HBM3E-12'), ('k', 'HBM3E 12단'), ('', 'HBM3E 12H;12단 HBM3E;HBM3E-12'), ('m', 'PRODUCT_CODE')],
    [('', '고객'), ('m', 'C-0001'), ('k', '고객사 A'), ('', '고객사 A;A사'), ('m', 'CUSTOMER_CODE')]]),
 '<p class="d" style="font-size:13.5px">별칭은 <b>질문에 나올 법한 말</b>을 그대로 넣습니다. 담당자마다 부르는 이름이 다르면 다 넣습니다. '
 '이 사전이 라우팅에서 "정형 질문"이라고 판단하는 근거도 됩니다.</p>',

 '<h3>A-3. 테이블카탈로그 · allow_list — 어디를 열어 줄지 (FROM 절과 차단 기준)</h3>',
 T(['물리명', '논리명', '유형', '소유', '갱신', '주요 컬럼', '연계 우선'],
   [[('m', 'V_PRICE_MONTHLY'), ('k', '월별 가격'), ('', '뷰'), ('', '마케팅팀'), ('', '월 1회'),
     ('m', 'YM;PRODUCT_CODE;PRICE_TYPE;QTY;AMT_USD'), ('', 'P0')],
    [('m', 'V_SALES_MONTHLY'), ('k', '월별 출하'), ('', '뷰'), ('', '영업전략팀'), ('', '일 1회'),
     ('m', 'YM;PRODUCT_CODE;CUSTOMER_CODE;SHIP_QTY_EB;AMT_USD'), ('', 'P0')],
    [('m', 'T_SALES_RAW'), ('k', '출하 원장(원본)'), ('', '테이블'), ('', '영업전략팀'), ('', '실시간'), ('m', '—'), ('', '—')]]),
 T(['뷰 · 테이블', '허용 컬럼', '행 접근 제한', '사용', '비고'],
   [[('m', 'V_PRICE_MONTHLY'), ('m', 'YM;PRODUCT_CODE;PRICE_TYPE;QTY;AMT_USD'), ('', ''), ('k', 'Y'), ('', '')],
    [('m', 'V_SALES_MONTHLY'), ('m', 'YM;PRODUCT_CODE;CUSTOMER_CODE;SHIP_QTY_EB;AMT_USD'), ('m', 'REGION_CODE'), ('k', 'Y'), ('', '고객 실명 컬럼 제외')],
    [('m', 'T_SALES_RAW'), ('', ''), ('', ''), ('k', 'N'), ('', '원본 직접 조회 금지 — 실행 전 차단됨')]]),

 '<h3>A-4. 그래서 SQL 의 어느 부분이 어디서 왔나</h3>',
 T(['SQL 조각', '어디서 왔나', '없으면 생기는 일'],
   [[('m', 'SELECT SUM(AMT_USD)/NULLIF(SUM(QTY),0)'), ('', '지표정의 · 집계식 (M002)'), ('', 'LLM 이 단순 평균으로 계산해 값이 틀림')],
    [('m', 'FROM V_PRICE_MONTHLY'), ('', '지표정의 · 대상 뷰 + allow_list 허용'), ('', '원본 테이블을 뒤지거나 실행이 차단됨')],
    [('m', "WHERE PRICE_TYPE='CONTRACT'"), ('', '지표정의 · 기본 필터'), ('', '현물가가 섞여 "계약가"가 아니게 됨')],
    [('m', "AND PRODUCT_CODE IN ('P-ESSD')"), ('', '코드값사전 · 별칭 → 코드'), ('', '제품 구분 없이 전체가 집계됨')],
    [('m', "AND YM BETWEEN '202607' AND '202609'"), ('', '질의 분석 · 기간 + 카탈로그의 기간 표준'), ('', '"3분기"가 회계/달력 중 무엇인지 몰라 엉뚱한 기간')],
    [('m', 'GROUP BY YM'), ('', '지표정의 · 기간 단위(월)'), ('', '월별 추이 대신 한 줄 합계만 나옴')],
    [('m', 'FETCH FIRST 200 ROWS ONLY'), ('', '시스템이 자동 부착'), ('', '대량 조회로 DB 부하')]]),

 '<h3>A-5. 한 줄 정의, 이렇게 씁니다</h3>',
 '<div class="two">'
 '<div class="good"><b>좋은 예</b><br>계약가격 = 월 단위 <b>확정</b> 계약 단가의 <b>가중평균</b><br>'
 '<code>SUM(AMT_USD)/NULLIF(SUM(QTY),0)</code> · <code>PRICE_TYPE=\'CONTRACT\'</code> · 단위 USD/GB · 월<br>'
 '<span style="color:#2C5F2C">→ 계산식 · 대상 · 조건 · 단위가 모두 한 줄에</span></div>'
 '<div class="bad"><b>나쁜 예</b><br>계약가격 = 고객과 계약한 가격<br>'
 '<span style="color:#8C2F3E">→ 단순평균인지 가중평균인지, 현물가 포함인지, 단위가 USD/GB 인지 USD/TB 인지 알 수 없음. '
 'SQL 로 옮길 수 없으니 카탈로그에 넣은 의미가 없음</span></div></div>',

 '<h3>A-6. 자주 빠뜨리는 것</h3>',
 T(['빠뜨리는 것', '증상', '대응'],
   [[('k', '기본 필터'), ('', '취소 · 반품 · 테스트 건이 섞여 수치가 조금씩 큼'), ('', '지표마다 "무엇을 제외하는지" 한 줄')],
    [('k', '단위'), ('', 'EB 와 TB, USD/GB 와 USD/TB 가 섞여 1000배 오차'), ('', '단위 칸 필수 · 답변에도 단위 표기')],
    [('k', '기간 기준'), ('', '"3분기"가 회계연도인지 달력인지 사람마다 다름'), ('', '카탈로그에 기간 표준 한 줄 고정')],
    [('k', '별칭'), ('', '현업이 부르는 이름으로 물으면 라우팅이 비정형으로 샘'), ('', '실제 질문 20개에서 쓰인 표현을 그대로 별칭에')],
    [('k', '유사 지표 구분'), ('', '"가격"이 계약가인지 현물가인지 모호'), ('', '별칭을 겹치지 않게 · 모호하면 되묻기')],
    [('k', '소유 부서'), ('', '수치가 이상할 때 물어볼 사람이 없음'), ('', '지표마다 담당 부서 · 갱신 주기')]]),

 '<h3>A-7. 채우는 순서 (한 번에 다 하지 않습니다)</h3>',
 '<ul class="ck">'
 '<li><b>1주차</b> — 테이블카탈로그: 연계 대상 뷰 5~10개만 고릅니다. 전부 열지 않습니다</li>'
 '<li><b>1주차</b> — allow_list: 그 뷰의 허용 컬럼과 제외 컬럼(고객 실명 등)을 정합니다</li>'
 '<li><b>2주차</b> — 지표정의: <b>실제 질문 20개에 나온 지표부터</b> 5~10개. 집계식 · 기본 필터 · 단위는 반드시</li>'
 '<li><b>2주차</b> — 코드값사전: 그 지표에 걸리는 제품 · 고객 · 지역 코드와 별칭</li>'
 '<li><b>3주차</b> — nb07 로 확인: 라우팅이 맞게 갈라지는지, SQL 이 나오는지, 차단이 도는지</li>'
 '<li><b>완료 기준</b> — 실제 질문 20개 중 정형 질문이 <b>카탈로그만으로 SQL 이 되는 비율</b>을 적습니다. 이 비율이 Phase 3 의 출발 점수입니다</li>'
 '</ul>',
 '<div class="note" style="margin-top:18px"><b>한 줄 요약</b> — 지표 정의서는 문서가 아니라 <b>코드의 입력</b>입니다. '
 '"이 칸을 비워 두면 SQL 의 어느 부분이 사라지는가"를 기준으로 채우면 됩니다. 채운 파일은 '
 '<code>rag_lab/catalog/metric_catalog.xlsx</code> 로 저장하면 nb07 이 그대로 읽습니다.</div>']
APPENDIX = '\n'.join(APX)

fig = f'<div class="fcard" style="background:var(--surface);border:1px solid var(--line);border-radius:3px;padding:14px 10px 8px;margin:16px 0">' \
      f'<div class="fig">{FR.hflow(MAIN, "qm")}{FR.vflow(MAIN, "qmv")}</div></div>'

body = [f'<header><p class="kicker">Query Walkthrough · 비정형 + 정형</p>',
        '<h1>질의 하나가 도는 길 — 문서와 DB를 함께 쓰는 경우</h1>',
        f'<div class="qbox"><small>마케팅 담당자 질문</small><b>{e(Q)}</b></div>',
        '<div class="meta"><span>판정 · 혼합(hybrid)</span><span>정형 · V_PRICE_MONTHLY · V_SALES_MONTHLY</span>'
        '<span>비정형 · 증권사 · 뉴스 · 회의록</span><span>2026-09-20</span></div></header>',
        '<h2>전체 흐름</h2>',
        '<p class="d">숫자를 묻는 부분과 이유를 묻는 부분이 한 질문에 같이 있습니다. 라우팅이 이를 <b>혼합</b>으로 판정하면 두 경로가 동시에 돌고, 결과를 하나의 컨텍스트로 합쳐 답변합니다.</p>',
        '<div class="flegend" style="display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted)">'
        '<span><i style="display:inline-block;width:14px;height:10px;background:#F2F2F2;border:1px solid #BFBFBF;margin-right:4px"></i>입력</span>'
        '<span><i style="display:inline-block;width:14px;height:10px;background:var(--pri-wash);border:1px solid var(--pri);margin-right:4px"></i>핵심 처리</span>'
        '<span><i style="display:inline-block;width:14px;height:10px;background:#E2F0D9;border:1px solid #8DB47A;margin-right:4px"></i>경로 · 산출</span></div>',
        fig, '<h2>단계마다 나오는 것</h2>']

for no, title, tag, kvs, pre in STEPS:
    body.append(f'<div class="step"><div class="sh"><span class="n">{no}</span><b>{e(title)}</b><span>{tag}</span></div><div class="kv">')
    for k, v in kvs:
        body.append(f'<div><b>{e(k)}</b><span>{v}</span></div>')
    body.append('</div>')
    if pre:
        cls, txt = pre
        body.append(f'<pre class="{cls}">{e(txt)}</pre>')
    body.append('</div>')

body.append('<div class="note"><b>이 흐름이 성립하려면</b> 세 가지가 먼저 있어야 합니다. ① 지표 정의서 — "계약가격"을 집계식으로 옮길 수 있어야 SQL이 나옵니다(S22). '
            '② 문서 날짜 메타 — 같은 기간으로 문서를 거를 수 있어야 이유가 그 분기의 것이 됩니다(S05). ③ 권한 — 두 경로에 같은 사용자 권한이 걸려야 합니다(S28).</div>')
body.append(APPENDIX)
body.append('<footer>MIS RAG-FLOW-001 rev.2 · 2026-09-20 · 부록: 지표 정의서 샘플 · 반도체 MIS DT · 수치 · 문서는 설명용 예시</footer>')

page = ('<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>질의 흐름 · 비정형 + 정형</title><style>' + CSS + FR.CSS + '</style></head><body><div class="wrap">'
        + '\n'.join(body) + '</div></body></html>')
open('query_flow_example_rev2.html', 'w', encoding='utf-8').write(page)
print('saved query_flow_example_rev2.html', len(page), 'scripts', page.count('<script'))
