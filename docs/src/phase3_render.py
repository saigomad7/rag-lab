# -*- coding: utf-8 -*-
"""Phase 3 · 정형 데이터 연계 — 라우팅 · 결합 패턴 흐름 섹션 (flows_render 의 SVG 렌더러 재사용)"""
import html
from flows_render import hflow, vflow
from phase3_data import ROUTING, PATTERNS, LINKS

e = html.escape
CSS = '.chunk.ex::before{content:"출력 예시 (표 · 수치는 조회 시점 기준)"}'


def section():
    h = ['<section class="sheet" id="p3flow"><div class="flowsec">']
    h.append('<p class="tabname" style="margin:0 0 6px">▸ 시트: 정형 연계 흐름 (Phase 3)</p>')
    h.append('<h3>1. 질의 라우팅 — 정형 · 비정형 · 혼합을 먼저 가른다</h3>')
    h.append('<p class="lead">정형 데이터를 붙인다는 것은 SQL을 하나 더 붙이는 일이 아니라, <b>질문이 들어올 때마다 어느 경로로 보낼지 판단하는 단계</b>가 새로 생기는 일입니다. '
             '수치 · 집계 · 추이 · 비교는 DB, 경위 · 이유 · 동향은 문서, 둘 다 필요한 질문은 혼합입니다.</p>')
    h.append('<div class="flegend"><span><i style="background:#F2F2F2"></i>입력</span><span><i style="background:var(--pri-wash);border-color:var(--pri)"></i>핵심 처리</span>'
             '<span><i style="background:#F8E1E1"></i>거절 · 되묻기</span><span><i style="background:#fff"></i>일반</span><span><i style="background:#E2F0D9"></i>경로 · 산출</span></div>')
    h.append(f'<div class="fcard"><div class="fig">{hflow(ROUTING, "p3r")}{vflow(ROUTING, "p3rv")}</div></div>')

    h.append('<h3>2. 결합 패턴 — 정형과 비정형을 어떻게 합치나</h3>')
    h.append('<p class="lead">질문 유형별로 아래 넷 중 하나를 씁니다. 패턴을 정해 두지 않으면 같은 질문에 매번 다른 방식으로 답이 나옵니다.</p>')
    for i, (title, desc, steps, ex) in enumerate(PATTERNS, 1):
        h.append(f'<div class="fcard"><div class="fh"><b>{e(title)}</b></div>')
        h.append(f'<div style="padding:8px 12px 0;font-size:13px;color:#404040">{e(desc)}</div>')
        h.append(f'<div class="fig">{hflow(steps, f"p3p{i}")}{vflow(steps, f"p3pv{i}")}</div>')
        h.append(f'<pre class="chunk ex">{e(ex)}</pre></div>')

    h.append('<h3>3. 기존 단계와의 연결 — 새로 만드는 것과 넓히는 것</h3>')
    h.append('<div class="fcard"><table style="margin:0"><tr class="hdr"><td>기존 단계 (Phase 1 · 2)</td><td>Phase 3에서</td><td>무엇이 달라지나</td></tr>')
    for a, b, c in LINKS:
        h.append(f'<tr><td class="k">{e(a)}</td><td data-l="Phase 3에서">{e(b)}</td><td class="j" data-l="무엇이 달라지나">{e(c)}</td></tr>')
    h.append('</table></div>')
    h.append('<div class="note" style="margin:14px 0">정형 연계는 <b>비정형 쪽 S05(메타 · 권한) · S08(질의 분석) · S15(평가)가 자리를 잡은 뒤</b>에 붙이는 것이 안전합니다. '
             '권한 체계와 평가 기준을 두 번 만들지 않기 위해서입니다.</div>')
    h.append('</div></section>')
    return '\n'.join(h)
