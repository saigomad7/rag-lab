# -*- coding: utf-8 -*-
"""소스별 컬럼 정의서 → 시트 섹션 (정적 HTML)"""
import html
from columns_data import COMMON_DOC, COMMON_CHUNK, PER_SOURCE, SAMPLES, NOTES

e = html.escape
NEED = {'M': ('필수', 'need-m'), 'R': ('권장', 'need-r'), 'O': ('선택', 'need-o')}

CSS = """
.coltbl table{min-width:1100px}
.coltbl td.c1{font-family:var(--mono);font-size:11.5px;color:#1F4E79;font-weight:600;white-space:nowrap}
.coltbl td.c2{white-space:nowrap} .coltbl td.c3{font-family:var(--mono);font-size:11px;color:var(--muted);white-space:nowrap}
.coltbl td.c6{color:var(--pri);font-size:12px} .coltbl td.c7{font-family:var(--mono);font-size:11px;color:#404040}
.coltbl td.fill{background:#FFFDE7;min-width:90px}
.need-m,.need-r,.need-o{display:inline-block;font-size:10.5px;font-weight:700;border-radius:2px;padding:0 6px;white-space:nowrap}
.coltbl td:nth-child(4){white-space:nowrap;text-align:center}
.need-m{color:#8C2F3E;background:#F3DFE2} .need-r{color:#5C440C;background:#F5EAD0} .need-o{color:#5B6A6E;background:#ECF2F2}
.srcbar{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}
.srcbar a{font-size:12px;text-decoration:none;color:var(--pri);border:1px solid var(--line);background:var(--surface);border-radius:2px;padding:3px 9px}
@media (max-width:640px){ .coltbl table{min-width:820px} }
"""


def _rows(items, fill=True):
    h = ('<div class="tw coltbl"><table><tr class="hdr"><td>컬럼명</td><td>논리명</td><td>타입</td><td>필수</td>'
         '<td>어디서 오나</td><td>쓰이는 곳</td><td>샘플값</td><td>사내 보유</td><td>사내 컬럼명</td></tr>')
    for c, ko, ty, nd, src, use, sam in items:
        lab, cls = NEED[nd]
        h += (f'<tr><td class="c1">{e(c)}</td><td class="c2">{e(ko)}</td><td class="c3">{e(ty)}</td>'
              f'<td><span class="{cls}">{lab}</span></td><td>{e(src)}</td><td class="c6">{e(use)}</td>'
              f'<td class="c7">{e(sam)}</td><td class="fill"></td><td class="fill"></td></tr>')
    return h + '</table></div>'


def section():
    h = ['<section class="sheet" id="cols"><div class="flowsec">']
    h.append('<p class="tabname" style="margin:0 0 6px">▸ 시트: 소스별 컬럼 정의서</p>')
    h.append('<h3>0. 쓰는 법</h3>')
    h.append('<p class="lead">소스 유형마다 <b>어떤 컬럼이 있어야 하는지</b>를 권장안으로 정리했습니다. '
             '오른쪽 두 칸(<b>사내 보유 · 사내 컬럼명</b>)을 채우면 그대로 매핑표가 되고, 빈 칸이 곧 보완 대상입니다. '
             '공통 컬럼은 모든 소스에 해당하고, 소스별 표는 그 위에 더해지는 항목입니다.</p>')
    h.append('<div class="flegend"><span><span class="need-m">필수</span> 없으면 검색 · 권한 · 인용 중 하나가 깨짐</span>'
             '<span><span class="need-r">권장</span> 품질 · 운영에 필요</span><span><span class="need-o">선택</span> 있으면 좋음</span></div>')
    h.append('<div class="srcbar">' + ''.join(f'<a href="#col-{k}">{v[0]}</a>' for k, v in PER_SOURCE.items()) + '</div>')

    h.append('<h3>1. 공통 — 문서 단위 (모든 소스)</h3>')
    h.append(_rows(COMMON_DOC))
    h.append('<h3>2. 공통 — 청크 단위</h3>')
    h.append(_rows(COMMON_CHUNK))

    h.append('<h3>3. 소스별 고유 항목 — 공통 컬럼에 더해서</h3>')
    for key, (ko, items) in PER_SOURCE.items():
        h.append(f'<div class="fcard" id="col-{key}"><div class="fh"><b>{e(ko)}</b><span>{key}</span></div>')
        h.append(_rows(items))
        if key in SAMPLES:
            h.append(f'<pre class="chunk rec">{e(SAMPLES[key])}</pre>')
        h.append('</div>')

    h.append('<h3>4. 정리하면서 놓치기 쉬운 것</h3>')
    h.append('<div class="fcard"><table style="margin:0"><tr class="hdr"><td>항목</td><td>내용</td></tr>')
    for a, b in NOTES:
        h.append(f'<tr><td class="k">{e(a)}</td><td data-l="내용">{e(b)}</td></tr>')
    h.append('</table></div>')
    h.append('</div></section>')
    return '\n'.join(h)


CSS += '.chunk.rec::before{content:"샘플 레코드 (한 건)"}'
