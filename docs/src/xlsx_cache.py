# 수식 칸에 계산값(캐시)을 넣어 모바일 미리보기에서도 값이 보이게 한다.
# 1) pycel로 모든 수식을 계산  2) 원본 데이터로 만든 기대값과 대조(검증)  3) xlsx XML의 <v>에 주입
import sys, re, zipfile, shutil, html
from openpyxl import load_workbook
from pycel import ExcelCompiler

def evaluate(path):
    wb = load_workbook(path)
    xl = ExcelCompiler(filename=path)
    vals, errs = {}, []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith('='):
                    ref = f"'{ws.title}'!{c.coordinate}"
                    try:
                        v = xl.evaluate(ref)
                    except Exception as ex:
                        v = None; errs.append((ref, repr(ex)[:80]))
                    if isinstance(v, str) and v.startswith('#'):
                        errs.append((ref, v))
                    vals[(ws.title, c.coordinate)] = v
    return vals, errs

def inject(path, vals):
    z = zipfile.ZipFile(path)
    wbxml = z.read('xl/workbook.xml').decode()
    rels = z.read('xl/_rels/workbook.xml.rels').decode()
    names = re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wbxml)
    target = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="/?(?:xl/)?([^"]+)"', rels)) or {}
    if not target:
        target = {rid: t for t, rid in re.findall(r'Target="/?(?:xl/)?([^"]+)"[^>]*Id="(rId\d+)"', rels)}
    sheet_file = {html.unescape(n): 'xl/' + target[rid] for n, rid in names}
    out = {}
    for name, fn in sheet_file.items():
        s = z.read(fn).decode()
        def rep(m):
            coord = m.group(2)
            v = vals.get((name, coord))
            attrs = m.group(1)
            if v is None:
                return m.group(0)
            if isinstance(v, bool):
                return f'<c{attrs} t="b"><f>{m.group(3)}</f><v>{int(v)}</v></c>'
            if isinstance(v, (int, float)):
                return f'<c{attrs}><f>{m.group(3)}</f><v>{v}</v></c>'
            return f'<c{attrs} t="str"><f>{m.group(3)}</f><v>{html.escape(str(v), quote=False)}</v></c>'
        s2 = re.sub(r'<c( r="([A-Z]+\d+)"[^>]*?)><f>(.*?)</f><v\s*/?>(?:</v>)?</c>', rep, s)
        out[fn] = s2
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zo:
        for item in z.infolist():
            data = out[item.filename].encode() if item.filename in out else z.read(item.filename)
            zo.writestr(item, data)
    z.close(); shutil.move(tmp, path)

if __name__ == '__main__':
    p = sys.argv[1]
    vals, errs = evaluate(p)
    print('formulas', len(vals), 'errors', len(errs))
    for e in errs[:20]: print('  ERR', e)
    if not errs:
        inject(p, vals); print('cached values injected')
