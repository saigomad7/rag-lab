# -*- coding: utf-8 -*-
"""소스별 컬럼 정의서 → 시트 섹션 (정적 HTML) — 저장 위치(컬럼/JSON/TAGS/ACL) 포함"""
import html
from columns_data import (COMMON_DOC, COMMON_BODY, COMMON_CHUNK, PER_SOURCE, SAMPLES, NOTES,
                          JSON_SCHEMA, TAGS_SCHEMA, ACL_SCHEMA, JSON_RULES, MAPPING_CASES, STORE_KO)

e = html.escape
NEED = {'M': ('필수', 'need-m'), 'R': ('권장', 'need-r'), 'O': ('선택', 'need-o')}
STORE_CLS = {'COL': 'st-col', 'JSON': 'st-json', 'TAGS': 'st-tags', 'ACL': 'st-acl', 'CHUNK': 'st-chunk', 'BODY': 'st-body'}
STORE_LBL = {'COL': '공통 컬럼', 'JSON': 'META_EXTRA', 'TAGS': 'TAGS', 'ACL': 'ACL 행', 'CHUNK': '청크 컬럼', 'BODY': '본문 테이블'}

CSS = """
.coltbl table{min-width:1180px}
.coltbl td.c1{font-family:var(--mono);font-size:11.5px;color:#1F4E79;font-weight:600}
.coltbl td.c2{white-space:nowrap} .coltbl td.c3{font-family:var(--mono);font-size:11px;color:var(--muted);white-space:nowrap}
.coltbl td.c7{color:var(--pri);font-size:12px} .coltbl td.c8{font-family:var(--mono);font-size:11px;color:#404040}
.coltbl td.fill{background:#FFFDE7;min-width:90px}
.coltbl td:nth-child(4),.coltbl td:nth-child(5){white-space:nowrap;text-align:center}
.need-m,.need-r,.need-o,.st-col,.st-json,.st-tags,.st-acl,.st-chunk,.st-body{display:inline-block;font-size:10.5px;font-weight:700;border-radius:2px;padding:0 6px;white-space:nowrap}
.need-m{color:#8C2F3E;background:#F3DFE2} .need-r{color:#5C440C;background:#F5EAD0} .need-o{color:#5B6A6E;background:#ECF2F2}
.st-col{color:#14484F;background:#D7E9EC;border:1px solid #9BC3C9} .st-json{color:#5A3E8C;background:#E8E1F5;border:1px solid #B9A8DC}
.st-tags{color:#2C5F2C;background:#E2F0D9;border:1px solid #9CC29C} .st-acl{color:#8C2F3E;background:#F8E1E1;border:1px solid #D9A8B0}
.st-chunk{color:#5B6A6E;background:#ECF2F2;border:1px solid #C6D2D3}
.st-body{color:#7A4A12;background:#FBECD9;border:1px solid #DCC79B}
.srcbar{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}
.srcbar a{font-size:12px;text-decoration:none;color:var(--pri);border:1px solid var(--line);background:var(--surface);border-radius:2px;padding:3px 9px}
.jsonbox{background:#1B2430;color:#DCE6EF;font-family:var(--mono);font-size:11.5px;line-height:1.6;white-space:pre-wrap;margin:0;padding:12px 14px;border-top:1px solid var(--hair)}
.jsonbox::before{content:"META_EXTRA (JSON) — 그대로 복사해 쓰는 형태";display:block;color:#9FB6CF;font-size:10px;letter-spacing:.08em;margin-bottom:6px}
.chunk.rec::before{content:"샘플 레코드 (한 건)"}
.jsonbox.tg::before{content:"TAGS (JSON) — 모든 소스 공통"}
.chunk.acl::before{content:"권한은 JSON 이 아니라 테이블 행으로"}
.legend2{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px;color:var(--muted);margin:8px 0}
@media (max-width:640px){ .coltbl table{min-width:880px} }
"""


def _rows(items):
    h = ('<div class="tw coltbl"><table><tr class="hdr"><td>이름</td><td>논리명</td><td>타입</td><td>필수</td><td>저장 위치</td>'
         '<td>어디서 오나</td><td>쓰이는 곳</td><td>샘플값</td><td>사내 보유</td><td>사내 컬럼명</td></tr>')
    for name, ko, ty, nd, store, src, use, sam in items:
        lab, cls = NEED[nd]
        h += (f'<tr><td class="c1">{e(name)}</td><td class="c2">{e(ko)}</td><td class="c3">{e(ty)}</td>'
              f'<td><span class="{cls}">{lab}</span></td><td><span class="{STORE_CLS[store]}">{STORE_LBL[store]}</span></td>'
              f'<td>{e(src)}</td><td class="c7">{e(use)}</td><td class="c8">{e(sam)}</td>'
              f'<td class="fill"></td><td class="fill"></td></tr>')
    return h + '</table></div>'


def section():
    h = ['<section class="sheet" id="cols"><div class="flowsec">']
    h.append('<p class="tabname" style="margin:0 0 6px">▸ 시트: 소스별 컬럼 정의서</p>')
    h.append('<h3>0. 사용 기준 — 항목 · 저장 위치</h3>')
    h.append('<p class="lead">소스별 필요 항목 + <b>저장 위치</b>(공통 컬럼 · META_EXTRA JSON · TAGS · ACL 행) 정의. '
             '저장 위치에 따라 검색 필터 · 권한 사용 가능 여부 결정. '
             '우측 2개 칸(<b>사내 보유 · 사내 컬럼명</b>) 기입 시 사내 테이블 매핑표로 사용.</p>')
    h.append('<div class="legend2">'
             '<span><span class="st-col">공통 컬럼</span> 모든 소스가 같은 이름으로 — 필터 · 권한 · 정렬 · 인용</span>'
             '<span><span class="st-json">META_EXTRA</span> 소스별 고유 값 — JSON 키</span>'
             '<span><span class="st-tags">TAGS</span> 회사 · 제품 · 주제 — JSON 배열</span>'
             '<span><span class="st-acl">ACL 행</span> 권한 — 별도 테이블</span>'
             '<span><span class="st-body">본문 테이블</span> 원문 · 정제본 · 요약 (CLOB)</span>'
             '<span><span class="st-chunk">청크 컬럼</span> RAG_CHUNK</span></div>')
    h.append('<div class="legend2"><span><span class="need-m">필수</span> 없으면 검색 · 권한 · 인용이 깨짐</span>'
             '<span><span class="need-r">권장</span> 품질 · 운영</span><span><span class="need-o">선택</span> 있으면 좋음</span>'
             '<span>표기 <b>"ORG_NAME ← publisher"</b> = 소스 항목 publisher 를 공통 컬럼 ORG_NAME 에 적재</span></div>')
    h.append('<div class="srcbar">' + ''.join(f'<a href="#col-{k}">{v[0]}</a>' for k, v in PER_SOURCE.items()) + '</div>')

    h.append('<h3>1. 공통 — 문서 단위 (모든 소스가 같은 이름으로)</h3>')
    h.append(_rows(COMMON_DOC))
    h.append('<h3>2. 공통 — 본문 · 요약 (검색 대상 본체)</h3>')
    h.append('<p class="lead">메타 단독 = 검색 대상 부재. <b>원문(RAW_BODY) · 정제본(CLEAN_BODY) · 요약(SUMMARY)</b> 은 용도 상이 → 분리 저장. '
             'CLOB 특성상 메타 테이블(RAG_DOC)과 분리 시 조회 · 동기화 부하 감소. <b>기존 원문 테이블 재사용 가능.</b></p>')
    h.append(_rows(COMMON_BODY))
    h.append('<div class="fcard"><table style="margin:0"><tr class="hdr"><td>무엇</td><td>언제 만드나</td><td>어디에 쓰나</td></tr>'
             '<tr><td class="k">RAW_BODY 원문</td><td data-l="언제">파싱 직후 (정제 전)</td>'
             '<td class="j" data-l="어디에">파서 교체 · 정제 규칙 변경 시 <b>재처리 기준</b> · 파싱 품질 점검(S02)</td></tr>'
             '<tr><td class="k">CLEAN_BODY 정제본</td><td data-l="언제">소스별 정제 규칙 적용 후</td>'
             '<td class="j" data-l="어디에"><b>청킹 입력</b> · 중복 판정 해시(CONTENT_HASH) 산출 기준</td></tr>'
             '<tr><td class="k">SUMMARY 요약</td><td data-l="언제">적재 후 <b>배치 1회</b> (질의 시점 생성 금지)</td>'
             '<td class="j" data-l="어디에">검색 결과 목록 표시 · 장문 컨텍스트 압축 · 센싱 리포트 · (선택) 문서 단위 검색 임베딩</td></tr>'
             '<tr><td class="k">CHUNK_SUMMARY</td><td data-l="언제">표 · 장문 청크 한정</td>'
             '<td class="j" data-l="어디에">수치 위주 표 청크는 질의어와 어휘 중복 부족 → 한 줄 요약 부착으로 검색력 보강</td></tr>'
             '</table></div>')
    h.append('<h3>3. 공통 — 청크 단위</h3>')
    h.append(_rows(COMMON_CHUNK))

    h.append('<h3>4. 공통 JSON · 권한 스키마</h3>')
    h.append(f'<div class="fcard"><div class="fh"><b>TAGS · ACL</b><span>모든 소스 공통</span></div>'
             f'<pre class="jsonbox tg">{e(TAGS_SCHEMA)}</pre>'
             f'<pre class="chunk acl">{e(ACL_SCHEMA)}</pre></div>')

    h.append('<h3>5. 소스별 — 공통 컬럼 적재분 + JSON 키 + 권한 행</h3>')
    for key, (ko, items) in PER_SOURCE.items():
        h.append(f'<div class="fcard" id="col-{key}"><div class="fh"><b>{e(ko)}</b><span>{key}</span></div>')
        h.append(_rows(items))
        if key in JSON_SCHEMA:
            h.append(f'<pre class="jsonbox">{e(JSON_SCHEMA[key])}</pre>')
        if key in SAMPLES:
            h.append(f'<pre class="chunk rec">{e(SAMPLES[key])}</pre>')
        h.append('</div>')

    h.append('<h3>6. JSON 사용 규칙</h3>')
    h.append('<div class="fcard"><table style="margin:0"><tr class="hdr"><td>규칙</td><td>내용</td><td>예</td></tr>')
    for a, b, c in JSON_RULES:
        h.append(f'<tr><td class="k">{e(a)}</td><td data-l="내용">{e(b)}</td><td class="j" data-l="예">{e(c)}</td></tr>')
    h.append('</table></div>')

    h.append('<h3>7. 사내 테이블 매핑 — 4가지 경우</h3>')
    h.append('<div class="fcard"><table style="margin:0"><tr class="hdr"><td>경우</td><td>처리 방법</td><td>예</td><td>사내 보유 칸에</td></tr>')
    for a, b, c, d in MAPPING_CASES:
        h.append(f'<tr><td class="k">{e(a)}</td><td data-l="처리 방법">{e(b)}</td><td class="j" data-l="예">{e(c)}</td><td data-l="사내 보유 칸에">{e(d)}</td></tr>')
    h.append('</table></div>')

    h.append('<h3>8. 작성 시 유의 사항</h3>')
    h.append('<div class="fcard"><table style="margin:0"><tr class="hdr"><td>항목</td><td>내용</td></tr>')
    for a, b in NOTES:
        h.append(f'<tr><td class="k">{e(a)}</td><td data-l="내용">{b}</td></tr>')
    h.append('</table></div>')
    h.append('</div></section>')
    return '\n'.join(h)
