# 소스별 처리 흐름 → 정적 SVG(가로: 데스크톱 / 세로: 모바일) + 표 HTML
import html
from flows_data import PRECHECK, FAMILIES, FLOWS
e = html.escape
MK = '<defs><marker id="{id}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" class="fa"/></marker></defs>'

def _box(x, y, w, h, t, s, k, fs=12.5, ss=10.5):
    cy = y + h / 2
    out = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="3" class="fb-{k}"/>'
    if s:
        out += f'<text x="{x+w/2:.1f}" y="{cy-3:.1f}" class="ft" style="font-size:{fs}px">{e(t)}</text>'
        out += f'<text x="{x+w/2:.1f}" y="{cy+13:.1f}" class="fs" style="font-size:{ss}px">{e(s)}</text>'
    else:
        out += f'<text x="{x+w/2:.1f}" y="{cy+4:.1f}" class="ft" style="font-size:{fs}px">{e(t)}</text>'
    return out

def _line(x1, y1, x2, y2, mid):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="fl" marker-end="url(#{mid})"/>'

def hflow(steps, mid):
    W, pad, gap = 1000, 14, 24
    n = len(steps)
    w = (W - 2 * pad - (n - 1) * gap) / n
    brk = max((len(s[1]) for s in steps if s[0] == 'br'), default=1)
    H = 60 + 62 * brk if brk > 1 else 86
    cy = H / 2
    body, prev_out = '', None
    for i, s in enumerate(steps):
        x = pad + i * (w + gap)
        if s[0] == 'box':
            h = 60; y = cy - h / 2
            body += _box(x, y, w, h, s[1], s[2], s[3])
            ins, outs = [(x, cy)], [(x + w, cy)]
        else:
            k = len(s[1]); bh = (H - 16 - (k - 1) * 8) / k
            ins, outs = [], []
            for j, b in enumerate(s[1]):
                y = 8 + j * (bh + 8)
                body += _box(x, y, w, bh, b[1], b[2], b[3], 12, 10)
                ins.append((x, y + bh / 2)); outs.append((x + w, y + bh / 2))
        if prev_out:
            for (x1, y1) in prev_out:
                for (x2, y2) in ins:
                    body += _line(x1, y1, x2 - 2, y2, mid)
        prev_out = outs
    return f'<svg class="hflow" viewBox="0 0 {W} {H:.0f}" role="img">{MK.format(id=mid)}{body}</svg>'

def vflow(steps, mid):
    W, pad, bw, gap = 360, 16, 328, 22
    y, body, prev_out = 6, '', None
    for s in steps:
        if s[0] == 'box':
            h = 44
            body += _box(pad, y, bw, h, s[1], s[2], s[3], 13, 11)
            ins, outs = [(pad + bw / 2, y)], [(pad + bw / 2, y + h)]
        else:
            k = len(s[1]); h = 54; kw = (bw - (k - 1) * 8) / k
            ins, outs = [], []
            for j, b in enumerate(s[1]):
                x = pad + j * (kw + 8)
                sub = b[2] if k <= 3 else ''
                body += _box(x, y, kw, h, b[1], sub, b[3], 12 if k <= 3 else 11.5, 9.5)
                ins.append((x + kw / 2, y)); outs.append((x + kw / 2, y + h))
        if prev_out:
            for (x1, y1) in prev_out:
                for (x2, y2) in ins:
                    body += _line(x1, y1, x2, y2 - 2, mid)
        prev_out = outs
        y += h + gap
    H = y - gap + 6
    return f'<svg class="vflow" viewBox="0 0 {W} {H:.0f}" role="img">{MK.format(id=mid)}{body}</svg>'

def overview():
    B = lambda t, s, k='norm': ('box', t, s, k)
    fam = ('br', [('box', f[0], f[1], 'key') for f in FAMILIES])
    steps = [B('원문 DB', 'doc id · 원문', 'in'), B('유형 분기', 'DOC_TYPE 9종', 'norm'), fam,
             B('정제', '제거 · 정규화', 'rm'), B('청킹', '유형별 규칙', 'out'), B('메타 · 헤더', '→ 임베딩', 'out')]
    return hflow(steps, 'mko') + vflow(steps, 'mkov')

CSS = """
.flowsec{padding:14px 14px 4px}
.flowsec h3{margin:18px 0 6px;font-size:15px;color:var(--pri)}
.flowsec .lead{margin:0 0 10px;color:#404040;font-size:13px;line-height:1.6;max-width:80ch}
.fcard{border:1px solid var(--grid);background:#fff;margin:14px 0 18px}
.fcard .fh{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;background:var(--hd2);padding:7px 10px;border-bottom:1px solid var(--grid)}
.fcard .fh b{font-size:14px;color:var(--pri)} .fcard .fh span{font-size:11.5px;color:var(--mut);font-family:var(--mono)}
.fcard .fig{padding:10px 8px 4px}
.fcard .fig svg{display:block;width:100%;height:auto}
.flowsec table{min-width:0!important;width:100%;table-layout:auto}
.fcard td{font-size:12.5px}
.fcard td.k{width:120px;background:#F7FAFA;font-weight:600;color:#333;white-space:nowrap}
.fcard td.j{color:#1F4E79;width:36%}
.chunk{margin:0;padding:8px 10px;background:#0F2A31;color:#D2E0E2;font-family:var(--mono);font-size:11.5px;line-height:1.55;white-space:pre-wrap;word-break:break-all;border-top:1px solid var(--grid)}
.chunk::before{content:"청크 예시";display:block;color:#85CEDB;font-size:10px;letter-spacing:.1em;margin-bottom:3px}
.fcard .fig svg.vflow{display:none}
.fb-in{fill:#F2F2F2;stroke:#BFBFBF;stroke-width:1.2}
.fb-norm{fill:#fff;stroke:#BFBFBF;stroke-width:1.2}
.fb-key{fill:var(--pri-wash);stroke:var(--pri);stroke-width:1.8}
.fb-rm{fill:#F8E1E1;stroke:#D9A8B0;stroke-width:1.2}
.fb-out{fill:#E2F0D9;stroke:#8DB47A;stroke-width:1.2}
.ft{font-family:var(--sans);font-weight:700;fill:#1F1F1F;text-anchor:middle}
.fs{font-family:var(--sans);fill:#595959;text-anchor:middle}
.fl{stroke:#8C8C8C;stroke-width:1.4;fill:none} .fa{fill:#8C8C8C}
.flegend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--mut);margin:4px 0 8px}
.flegend i{display:inline-block;width:14px;height:10px;border:1px solid #BFBFBF;vertical-align:-1px;margin-right:4px}
.pre-t td.k{width:170px}
@media (max-width:640px){
 .fcard .fig svg.hflow{display:none} .fcard .fig svg.vflow{display:block;max-width:100%;margin:0 auto}
 .fcard table,.fcard tbody,.fcard tr,.fcard td{display:block;width:auto!important}
 .fcard tr.hdr{display:none}
 .fcard tr{border-top:2px solid var(--grid);padding:4px 0}
 .fcard td{border:0;padding:2px 10px;white-space:normal!important}
 .fcard td::before{content:attr(data-l);display:block;font-family:var(--mono);font-size:10px;color:var(--mut);letter-spacing:.08em}
 .fcard td.k{background:none;color:var(--pri)} .fcard td.k::before{display:none}
 .flowsec{padding:10px 8px 4px}
}
"""

def section():
    h = ['<section class="sheet" id="flow"><div class="flowsec">']
    h.append('<p class="tabname" style="margin:0 0 6px">▸ 시트: 소스별 처리 흐름 (청킹 전)</p>')
    h.append('<h3>0. 처리 방식을 정하기 전에 — 원문 DB 상태부터</h3>')
    h.append('<p class="lead">DB에 데이터가 들어 있어도, <b>원본 파일이 있는지, 텍스트만 있는지</b>에 따라 할 수 있는 처리가 달라집니다. 아래 세 가지를 먼저 확인하면 소스별 흐름 중 어디까지 적용할지 정해집니다.</p>')
    h.append('<div class="fcard"><table class="pre-t" style="margin:0"><tr class="hdr"><td>확인할 것</td><td>어떻게</td><td>결과에 따라</td></tr>')
    for a, b, c in PRECHECK:
        h.append(f'<tr><td class="k">{a}</td><td data-l="어떻게">{b}</td><td class="j" data-l="결과에 따라">{c}</td></tr>')
    h.append('</table></div>')
    h.append('<h3>1. 전체 — 9개 소스를 4개 파서 계열로</h3>')
    h.append('<p class="lead">소스는 9종이지만 파서는 4계열이면 됩니다. 계열 안에서는 파서를 공유하고, 정제 규칙과 청킹 단위만 소스별로 다릅니다.</p>')
    h.append('<div class="flegend"><span><i style="background:#F2F2F2"></i>입력</span><span><i style="background:var(--pri-wash);border-color:var(--pri)"></i>핵심 처리</span><span><i style="background:#F8E1E1"></i>제거</span><span><i style="background:#fff"></i>일반</span><span><i style="background:#E2F0D9"></i>청킹 · 메타 산출</span></div>')
    h.append(f'<div class="fcard"><div class="fig">{overview()}</div>')
    h.append('<div class="scroll"><table style="margin:0"><tr class="hdr"><td>계열</td><td>소스</td><td>공통 처리</td></tr>')
    for f, s, p in FAMILIES:
        h.append(f'<tr><td class="k">{f}</td><td data-l="소스">{s}</td><td class="j" data-l="공통 처리">{p}</td></tr>')
    h.append('</table></div></div>')
    h.append('<h3>2. 소스별 처리 흐름</h3>')
    for i, (src, fam, steps, rows, ex) in enumerate(FLOWS):
        h.append(f'<div class="fcard" id="f{i+1}"><div class="fh"><b>{i+1}. {src}</b><span>계열 · {fam}</span></div>')
        h.append(f'<div class="fig">{hflow(steps, f"mh{i}")}{vflow(steps, f"mv{i}")}</div>')
        h.append('<div class="scroll"><table style="margin:0"><tr class="hdr"><td>단계</td><td>처리 내용</td><td>판단 기준 · 확인 방법</td></tr>')
        for a, b, c in rows:
            h.append(f'<tr><td class="k">{a}</td><td data-l="처리 내용">{b}</td><td class="j" data-l="판단 기준 · 확인 방법">{c}</td></tr>')
        h.append(f'</table></div><pre class="chunk">{e(ex)}</pre></div>')
    h.append('</div></section>')
    return '\n'.join(h)
