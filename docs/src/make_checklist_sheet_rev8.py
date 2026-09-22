import html
import re
OUT='rag_checklist_sheet_rev8.html'
import flows_render, phase3_render, columns_render
from phase3_data import P3
D,W,T='done','doing','todo'
# (stage, name, [(check, current, improve, pri, status)])
P1A=[
('S01','수집',[
 ('원천 키 유일 · 재수집 중복 체크','doc id 있음, 재수집 시 중복 체크 중','—','P0',D),
 ('작성일 · 수집일 분리, 날짜 누락률','분리 저장, 날짜 95% 보유','누락 5%가 몰린 소스만 확인','P2',D),
 ('중복 수집 (뉴스 재송고 · 메일 인용)','','해시 → 근사 중복(MinHash)','P1',T)]),
('S02','파싱',[
 ('증권사 PDF 표 · 수치 보존','','표는 별도 청크, 파서 교체 검토','P1',T),
 ('메일 인용 · 서명 제거','','메일 정제 규칙','P1',T)]),
('S03','청킹',[
 ('분할 방식 · 크기 · 오버랩','','문서 유형별 규칙 (뉴스=기사, 리포트=섹션·표)','P0',T),
 ('문장 잘림 · 표 깨짐 (샘플 20)','','구조 기반 분할','P0',T),
 ('청크 헤더 [유형|날짜|기관|제목]','','HEADER_TEXT 별도 컬럼','P0',T)]),
('S04','임베딩',[
 ('BGE-M3 max_length 잘림 여부','','잘림 0건','P0',T),
 ('dense만? sparse도?','','dense + sparse 동시 생성','P0',T),
 ('입력 구성','','dense=헤더+본문, sparse=본문만','P1',T)]),
('S05','메타데이터',[
 ('공통 컬럼 (유형 · 날짜 · 기관 · 보안등급)','','필터에 쓰는 값은 공통 컬럼으로','P0',T),
 ('권한 원천 (메일 수신자 · 임원 결재선)','','ACL 테이블, 어려우면 보안등급만 1차','P0',T),
 ('회사 · 제품 · 주제 태그','','사내 LLM 추출 — Phase 2 기반','P1',T)]),
('S06','벡터 DB',[
 ('Milvus 버전','','2.4+ (sparse · hybrid), 2.5+ (BM25 내장)','P0',T),
 ('필터 필드가 스칼라로 있는지','','유형 · 날짜 · 권한 · 기관 복제','P0',T),
 ('Oracle 수정 · 삭제 반영','','증분 동기화 잡','P1',T)]),
]
P1B=[
('S07','질의 입력',[
 ('실제 질문 20개 스모크 테스트','문항 작성 완료 (SM01~SM20)','실패 유형 5종 집계 → 우선순위','P0',W),
 ('질의 · 결과 · 답변 로그','','Oracle 로그 테이블 3개','P0',T)]),
('S08','질의 분석 · 분해',[
 ('분해 시 고유명사 누락','','원 질의도 항상 함께 검색','P0',T),
 ('"최근 · 3분기" → 날짜 필터','','기간 추출 (규칙 우선)','P0',T),
 ('분해 적용 범위','','비교 · 종합형 질문에만','P1',T)]),
('S09','BM25',[
 ('실행 위치 (파이썬 / Oracle Text / Milvus)','','','P0',T),
 ('토크나이저 — "하이닉스의 / 는" 동일 토큰?','','형태소 분석 (Kiwi / Oracle Text)','P0',T),
 ('BM25 vs BGE-M3 sparse','','코드명 · 수치 질문으로 비교 후 택1','P1',T)]),
('S10','시맨틱 검색',[
 ('권한 · 기간 필터가 검색과 동시에','','Milvus 사전 필터 (사후 필터 금지)','P0',T),
 ('top-k','','50','P1',T)]),
('S11','결합 · 다양성',[
 ('결합 방식','계획만 있음','RRF k=60','P0',T),
 ('MMR 위치 · λ','계획만 있음','리랭크 뒤, λ 0.5~0.7','P1',T),
 ('문서당 청크 상한','','문서당 3개','P1',T)]),
('S12','리랭크',[
 ('모델 · 후보 수 → 최종 수','','bge-reranker-v2-m3, 50 → 5~8','P0',T),
 ('지연','','p95 예산 안','P1',T)]),
('S13','컨텍스트',[
 ('청크 라벨 [번호|유형|기관|날짜]','','라벨 필수','P0',T),
 ('넘기는 청크 수','','토큰 예산 기준','P1',T)]),
('S14','LLM 답변',[
 ('출처 번호 인용','','문장별 인용 강제','P0',T),
 ('근거 없을 때','','"확인된 자료 없음" 응답','P0',T),
 ('자료 간 시점 · 수치 충돌','','둘 다 날짜와 함께 제시','P1',T)]),
('S15','평가',[
 ('골든셋','','문서 ID + 정답 문장 (청크 ID 금지)','P0',T),
 ('검색 지표 · 단계별 비교','','Recall@k · MRR, BM25/Dense/Hybrid/+Rerank','P0',T),
 ('답변 채점','','사내 LLM + 20문항 사람 교차','P1',T)]),
]
P2=[
('S16','센싱 축',[
 ('축 확정','6축 전부 사용 (수요 · 공급 · 가격 · 기술 · 정책 · 고객)','—','P0',D),
 ('축당 하위 신호 3~5 + "이상" 정의','','축별 담당자와 한 문장씩','P0',T)]),
('S17','상시 질의',[
 ('신호당 질의 2~4개 (한 · 영)','','사내 LLM 초안 + 검수','P0',T),
 ('기간 창 · 태그 필터 템플릿','','이번 주 vs 지난 4주','P0',T)]),
('S18','검색 · 수집',[
 ('하이브리드 재사용 + 기간 창','','Phase 1 S10 그대로','P0',T),
 ('재송고 뉴스 접기','','MinHash + MMR → 사건 단위','P0',T)]),
('S19','변화 감지',[
 ('언급량 급증','','지난 4주 평균 대비 z-score','P0',T),
 ('새 엔티티 · 방향 변화','','백테스트에서 이득 있으면 추가','P1',T),
 ('축 점수 집계 → 정렬','신호 뚜렷한 축을 위로 (요구사항)','하위 신호 점수 → 축 점수(최대값)','P0',T)]),
('S20','요약 · 알림',[
 ('축 점수순 리포트 + 근거 인용','','주간 리포트 + 임계 초과 즉시','P0',T),
 ('담당자 유효 / 무효 표시','','임계 조정 근거','P1',T)]),
('S21','백테스트',[
 ('과거 실제 사건 10건','','감산 · 가격 급등 · 규제','P0',T),
 ('회수율 · 오탐','','임계 · 질의 조정','P0',T)]),
]
SMOKE=[('SM01','사실','마이크론 HBM 생산 확대 계획'),('SM02','사실','Sufficiency Ratio 정의'),('SM03','사실','최근 주간회의 액션 아이템'),('SM04','사실','임원 보고 HBM 리스크 (권한)'),
('SM05','수치','2H26 DRAM 계약가 분기별'),('SM06','수치','2026 HBM 시장 규모 · 성장률'),('SM07','수치','당사 eSSD 수요 (EB)'),('SM08','수치','엔비디아 최근 DC 매출'),
('SM09','기간','최근 2주 CXMT 뉴스'),('SM10','기간','3Q NAND 전망 상향 증권사'),('SM11','기간','이번 달 고객 발주 조정 메일 (권한)'),
('SM12','종합','하이퍼스케일러 CapEx 사외 vs 사내'),('SM13','종합','HBM4 12단 기술 이슈 + 경쟁사 (권한)'),('SM14','종합','美 수출규제 변경 → 중국 사업'),
('SM15','비교','삼성 vs 하이닉스 HBM 점유율'),('SM16','비교','사내 vs 임원 보고 NAND 판단 (권한)'),('SM17','비교','마이크론 vs 삼성 미국 팹'),
('SM18','답없음','2027 HBM 판가 확정치'),('SM19','답없음','경쟁사 HBM 수율 정확값'),('SM20','답없음','TSMC DRAM 출하량 (전제 오류)')]

e=html.escape
ST={D:('☑ 완료','s-done'),W:('◐ 확인중','s-doing'),T:('☐','s-todo')}
COLS=['A','B','C','D','E','F','G','H']
def colhead(widths):
    return '<tr class="ch"><th class="rn"></th>'+''.join(f'<th style="width:{w}">{c}</th>' for c,w in zip(COLS,widths))+'</tr>'
def sheet(sid,title,groups,start=1):
    r=start
    rows=[f'<tr><td class="rn">{r}</td><td class="h" colspan="7">{e(title)}</td></tr>']; r+=1
    rows.append(f'<tr class="hdr"><td class="rn">{r}</td><td>단계</td><td>No</td><td>체크 항목</td><td>현 수준</td><td>개선 방향</td><td>우선</td><td>상태</td></tr>'); r+=1
    for code,name,items in groups:
        for i,(chk,cur,imp,pri,st) in enumerate(items):
            lab,cls=ST[st]
            a=f'<td class="stg" rowspan="{len(items)}"><b>{code}</b><br>{e(name)}</td>' if i==0 else ''
            rows.append(f'<tr class="{cls}"><td class="rn">{r}</td>{a}<td class="c">{code[1:]}-{i+1}</td><td>{e(chk)}</td><td class="cur">{e(cur)}</td><td class="imp">{e(imp)}</td><td class="c {pri}">{pri}</td><td class="c st">{lab}</td></tr>'); r+=1
    return r,'\n'.join(rows)
def count(groups):
    n=sum(len(g[2]) for g in groups); d=sum(1 for g in groups for x in g[2] if x[4]==D); w=sum(1 for g in groups for x in g[2] if x[4]==W)
    return n,d,w

W7=['92px','46px','30%','22%','26%','46px','78px']
_,s1=sheet('p1a','Phase 1 · 적재 공통 — 모든 소스에 해당하는 항목 (소스별 차이는 앞 두 시트)',P1A)
_,s2=sheet('p1b','Phase 1 · 검색 — 질의가 흐르는 순서 (S07 → S15)',P1B)
_,s3=sheet('p2','Phase 2 · 마켓 센싱 (S16 → S21)',P2)
P3S=[(c,n,[(re.sub(r'</?b>','',a),b,re.sub(r'</?b>','',cc),d,e2) for a,b,cc,d,e2 in items]) for c,n,items in P3]
_,s5=sheet('p3','Phase 3 · 정형 데이터 연계 — 사내 DB · SQL × 비정형 (S22 → S29)',P3S)

# ---------- 소스 유형별 시트 (rev2) ----------
from sources_data import SOURCES, STAGES
SYM={D:'☑',W:'◐',T:'☐'}
# 매트릭스: 소스 × 단계
mx=['<tr><td class="rn">1</td><td class="h" colspan="8">소스별 매트릭스 — 소스 9종 × 적재 5단계 (칸 = 상태 + 핵심 필요사항)</td></tr>',
    '<tr class="hdr"><td class="rn">2</td><td>소스</td><td>DOC_TYPE</td><td>문서 수</td>'+''.join(f'<td>{x}</td>' for x in STAGES)+'</tr>']
r=3; last=None
for name,dt,grp,lvl,st in SOURCES:
    cells=''
    for sg in STAGES:
        chk,cur,imp,pri,stt,short=st[sg]
        cls={D:'m-done',W:'m-doing',T:''}[stt]
        cells+=f'<td class="mx {cls}"><span class="sym">{SYM[stt]}</span> {short}<span class="mp {pri}">{pri}</span></td>'
    g=f'<span class="grp-{"ext" if grp=="사외" else "int"}">{grp}</span> ' 
    mx.append(f'<tr><td class="rn">{r}</td><td class="src">{g}<b>{name}</b></td><td class="c mono">{dt}</td><td class="fillc"></td>{cells}</tr>'); r+=1
smx='\n'.join(mx)
# 상세: 소스별 5행
dt_rows=['<tr><td class="rn">1</td><td class="h" colspan="8">소스별 상세 — 소스마다 수집 · 파싱 · 청킹 · 메타 · 권한을 확인</td></tr>',
    '<tr class="hdr"><td class="rn">2</td><td>소스</td><td>단계</td><td>체크 항목</td><td>현 수준</td><td>필요사항</td><td>우선</td><td>상태</td><td>등급</td></tr>']
r=3; SRC_CNT=[]
for name,dt,grp,lvl,st in SOURCES:
    n=d=w=0
    for i,sg in enumerate(STAGES):
        chk,cur,imp,pri,stt,short=st[sg]; n+=1; d+=stt==D; w+=stt==W
        lab,cls=ST[stt]
        a=f'<td class="stg" rowspan="{len(STAGES)}"><b>{name}</b><br><span class="mono">{dt}</span><br><small>{grp}</small></td>' if i==0 else ''
        lv=f'<td class="c stg" rowspan="{len(STAGES)}">{lvl}</td>' if i==0 else ''
        dt_rows.append(f'<tr class="{cls}"><td class="rn">{r}</td>{a}<td class="c">{sg}</td><td>{chk}</td><td class="cur">{e(cur)}</td><td class="imp">{imp}</td><td class="c {pri}">{pri}</td><td class="c st">{lab}</td>{lv}</tr>'); r+=1
    SRC_CNT.append((name,dt,n,d,w,st))
sdt='\n'.join(dt_rows)

# summary sheet
sm=['<tr><td class="rn">1</td><td class="h" colspan="7">요약 — Phase 1 · 2 · 3 단계별 · 소스별 진행 현황</td></tr>',
    '<tr class="hdr"><td class="rn">2</td><td>구분</td><td>단계</td><td>단계명</td><td>항목</td><td>완료</td><td>확인중</td><td>미확인</td></tr>']
r=3; tot=[0,0,0]
for lab,groups in [('P1 적재',P1A),('P1 검색',P1B),('P2 센싱',P2),('P3 정형연계',P3S)]:
    for j,(code,name,items) in enumerate(groups):
        n,d,w=count([(code,name,items)]); tot[0]+=n; tot[1]+=d; tot[2]+=w
        a=f'<td class="stg" rowspan="{len(groups)}"><b>{lab}</b></td>' if j==0 else ''
        bar=''.join('■' if x[4]==D else ('◧' if x[4]==W else '□') for x in items)
        sm.append(f'<tr><td class="rn">{r}</td>{a}<td class="c">{code}</td><td>{e(name)} <span class="bar">{bar}</span></td><td class="c">{n}</td><td class="c g">{d or ""}</td><td class="c y">{w or ""}</td><td class="c">{n-d-w}</td></tr>'); r+=1
for j,(name,dt,n,d,w,st) in enumerate(SRC_CNT):
    a=f'<td class="stg" rowspan="{len(SRC_CNT)}"><b>소스별<br>적재</b></td>' if j==0 else ''
    bar=''.join('■' if st[x][4]==D else ('◧' if st[x][4]==W else '□') for x in STAGES)
    tot[0]+=n; tot[1]+=d; tot[2]+=w
    sm.append(f'<tr><td class="rn">{r}</td>{a}<td class="c mono" style="font-size:10.5px">{dt}</td><td>{name} <span class="bar">{bar}</span></td><td class="c">{n}</td><td class="c g">{d or ""}</td><td class="c y">{w or ""}</td><td class="c">{n-d-w}</td></tr>'); r+=1
sm.append(f'<tr class="tot"><td class="rn">{r}</td><td colspan="3">합계</td><td class="c">{tot[0]}</td><td class="c g">{tot[1]}</td><td class="c y">{tot[2]}</td><td class="c">{tot[0]-tot[1]-tot[2]}</td></tr>')
s0='\n'.join(sm)

# smoke sheet
sk=['<tr><td class="rn">1</td><td class="h" colspan="7">스모크 테스트 20문항 — 사내에서 돌리고 결과만 기입</td></tr>',
    '<tr class="hdr"><td class="rn">2</td><td>No</td><td>유형</td><td>질문 (요약)</td><td>검색<br><small>적중·낮음·누락</small></td><td>답변<br><small>정답·부분·오답·없음</small></td><td>실패<br><small>①~⑤</small></td><td>메모</td></tr>']
r=3
for i,t,q in SMOKE:
    sk.append(f'<tr><td class="rn">{r}</td><td class="c">{i}</td><td class="c">{t}</td><td>{e(q)}</td><td></td><td></td><td></td><td></td></tr>'); r+=1
s4='\n'.join(sk)

def tbl(sid,body,widths,label,cls=''):
    return f'''<section class="sheet" id="{sid}"><div class="scroll"><table class="{cls}">
<colgroup><col style="width:34px">{''.join(f'<col style="width:{w}">' for w in widths)}</colgroup>
{colhead(widths)}
{body}
</table></div><p class="tabname">▸ 시트: {label}</p></section>'''

page=f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAG 체크리스트 시트</title>
<style>
:root{{--pri:#185463;--pri-wash:#DAEAED;--grid:#D4D4D4;--hd:#F2F2F2;--hd2:#E7EDEE;--ink:#1F1F1F;--mut:#6B6B6B;
 --ok:#E2F0D9;--ok-t:#375623;--wip:#FFF2CC;--wip-t:#7F6000;--p0:#C00000;--p1:#B26B00;--p2:#808080;
 --sans:"Malgun Gothic","Apple SD Gothic Neo","Pretendard",system-ui,sans-serif;--mono:Consolas,"D2Coding","SFMono-Regular",monospace}}
*{{box-sizing:border-box}}
body{{margin:0;background:#E9ECEC;color:var(--ink);font-family:var(--sans);font-size:13px}}
.app{{max-width:1180px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 0 1px #cfd6d7}}
.title{{background:var(--pri);color:#fff;padding:9px 14px;font-size:13px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.title b{{font-weight:600}} .title span{{opacity:.75;font-size:12px}}
.fx{{display:flex;border-bottom:1px solid var(--grid);font-size:12px;background:#fff}}
.fx .ref{{width:74px;padding:5px 8px;border-right:1px solid var(--grid);color:var(--mut);font-family:var(--mono)}}
.fx .f{{padding:5px 8px;color:var(--mut);border-right:1px solid var(--grid);font-style:italic}}
.fx .v{{padding:5px 10px;flex:1}}
.tabs{{position:sticky;top:0;z-index:5;display:flex;gap:0;background:var(--hd);border-bottom:1px solid var(--grid);overflow-x:auto}}
.tabs a{{padding:7px 14px;font-size:12px;color:#333;text-decoration:none;border-right:1px solid var(--grid);white-space:nowrap;background:var(--hd)}}
.tabs a:first-child{{background:#fff;color:var(--pri);font-weight:600;border-bottom:2px solid var(--pri)}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 16px;padding:8px 14px;font-size:12px;color:var(--mut);border-bottom:1px solid var(--grid)}}
.legend i{{display:inline-block;width:12px;height:12px;border:1px solid var(--grid);vertical-align:-2px;margin-right:4px}}
.sheet{{padding:14px 0 6px;border-bottom:6px solid #E9ECEC}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;table-layout:fixed;width:100%;min-width:820px;font-size:12.5px}}
td,th{{border:1px solid var(--grid);padding:5px 7px;vertical-align:top;line-height:1.45;word-break:keep-all;overflow-wrap:anywhere}}
tr.ch th{{background:var(--hd);color:var(--mut);font-weight:400;text-align:center;font-family:var(--mono);font-size:11px;padding:3px}}
td.rn,th.rn{{background:var(--hd);color:var(--mut);text-align:center;font-family:var(--mono);font-size:11px;width:34px;padding:5px 2px}}
td.h{{font-weight:700;font-size:13.5px;color:var(--pri);background:#fff;border-left:0;border-right:0}}
tr.hdr td{{background:var(--hd2);font-weight:700;text-align:center;color:#333}}
tr.hdr td.rn{{background:var(--hd);font-weight:400}}
td.stg{{background:#F7FAFA;text-align:center;vertical-align:middle;color:#333}} td.stg b{{color:var(--pri);font-family:var(--mono)}}
td.c{{text-align:center}}
table.wide{{min-width:960px}}
td.mono,.mono{{font-family:var(--mono);font-size:11px}}
td.src{{white-space:nowrap}} td.fillc{{background:#fff}}
td.mx{{font-size:12px;position:relative;padding-right:30px}} td.mx .sym{{font-size:13px}}
td.m-done{{background:var(--ok)}} td.m-doing{{background:var(--wip)}}
.mp{{position:absolute;top:4px;right:5px;font-size:10px;font-family:var(--mono)}}
.grp-ext,.grp-int{{font-size:10px;padding:0 4px;border:1px solid var(--grid);border-radius:2px;margin-right:2px}}
.grp-ext{{color:#1F4E79;background:#EAF1F8}} .grp-int{{color:#7F3F00;background:#FBEFE3}}
table.narrow{{min-width:440px}} table.mid{{min-width:600px}}
.legend span i + *{{}}
td.cur{{color:#1F4E79}} td.imp{{color:#404040}}
.P0{{color:var(--p0);font-weight:700}} .P1{{color:var(--p1);font-weight:700}} .P2{{color:var(--p2);font-weight:700}}
tr.s-done td:not(.rn):not(.stg){{background:var(--ok)}} tr.s-done td.st{{color:var(--ok-t);font-weight:700}}
tr.s-doing td:not(.rn):not(.stg){{background:var(--wip)}} tr.s-doing td.st{{color:var(--wip-t);font-weight:700}}
td.st{{font-size:12px;color:#999}}
td.g{{background:var(--ok);color:var(--ok-t);font-weight:700}} td.y{{background:var(--wip);color:var(--wip-t);font-weight:700}}
tr.tot td{{background:var(--hd2);font-weight:700}} tr.tot td.rn{{background:var(--hd);font-weight:400}}
.bar{{font-family:var(--mono);letter-spacing:1px;color:var(--pri);font-size:11px;margin-left:6px}}
small{{font-weight:400;color:var(--mut);font-size:10.5px}}
.tabname{{margin:6px 14px 0;font-size:11.5px;color:var(--mut);font-family:var(--mono)}}
.foot{{padding:14px;font-size:11.5px;color:var(--mut);line-height:1.7}}
@media (max-width:640px){{ .fx .f,.fx .ref{{display:none}} .title span{{width:100%}} }}
{flows_render.CSS}
{phase3_render.CSS}
{columns_render.CSS}</style></head><body><div class="app">
<div class="title"><b>RAG_단계별_체크리스트_간소화</b><span>rev.8 · 2026-09-22 · 기술문서 표기 정리 (개조식) · 정적 문서</span></div>
<div class="fx"><div class="ref">A1</div><div class="f">fx</div><div class="v">1행 = 확인 항목 1건 · 확인값 → <b>현 수준</b> 칸 · 완료 시 <b>상태</b> ☑ · 옵션 상세는 퀘스트 보드 · 설계 가이드 참조</div></div>
<div class="tabs"><a href="#sum">요약</a><a href="#smx">소스별 매트릭스</a><a href="#sdt">소스별 상세</a><a href="#cols">소스별 컬럼 정의</a><a href="#flow">소스별 처리 흐름</a><a href="#p1a">P1 적재 공통</a><a href="#p1b">P1 검색</a><a href="#p2">P2 센싱</a><a href="#p3">P3 정형연계</a><a href="#p3flow">정형연계 흐름</a><a href="#smoke">스모크 20</a></div>
<div class="legend"><span><i style="background:var(--ok)"></i>완료 ☑</span><span><i style="background:var(--wip)"></i>확인중 ◐</span><span><i style="background:#fff"></i>미확인 ☐</span><span><b class="P0">P0</b> 먼저</span><span><b class="P1">P1</b> 다음</span><span><b class="P2">P2</b> 필요 시</span></div>
{tbl('sum',s0,['64px','44px','34%','44px','44px','50px','50px'],'요약','narrow')}
{tbl('smx',smx,['118px','92px','56px','17%','17%','16%','17%','17%'],'소스별 매트릭스','wide')}
{tbl('sdt',sdt,['104px','50px','27%','18%','25%','40px','64px','40px'],'소스별 상세','wide')}
{flows_render.section()}
{columns_render.section()}
{tbl('p1a',s1,W7,'P1 적재 공통')}
{tbl('p1b',s2,W7,'P1 검색')}
{tbl('p2',s3,W7,'P2 센싱')}
{tbl('p3',s5,W7,'P3 정형연계')}
{phase3_render.section()}
{tbl('smoke',s4,['50px','50px','34%','70px','80px','46px','20%'],'스모크 20','mid')}
<div class="foot">관련 문서: 단계별 체크리스트 rev3 · 설계 가이드 rev4 · 퀘스트 보드 rev4 · 스모크 20문항 (본 시트 = 간소화 병행본)<br>MIS RAG-SHEET-001 rev.8 · 2026-09-19 · 반도체 MIS DT</div>
</div></body></html>'''
open(OUT,'w').write(page)
print('items',tot,'size',len(page),'scripts',page.count('<script'))
