# -*- coding: utf-8 -*-
"""
정형 데이터 연계 (Phase 3) — 카탈로그 · 라우팅 · SQL 생성 · 정적 검증 · 실행 · 실행결과 정확도
  S22 카탈로그  : load_catalog()          — 지표정의 · 코드값사전 · 테이블카탈로그 · allow_list
  S24 라우팅    : route()                 — 정형 / 비정형 / 혼합 / 불가
  S25 생성·검증 : make_sql(), validate()  — 규칙 생성 또는 사내 LLM, 실행 전 차단
  S25 실행      : run_sql()               — sample=SQLite, live=Oracle(읽기 전용 계정)
  S29 평가      : exec_match()            — 결과 값 일치(EX)
"""
import os
import re
import json
import numpy as np
import pandas as pd
import lab_config as C

CAT_DIR = os.path.join(C.LAB_DIR, 'catalog')
DEFAULT_CATALOG = os.path.join(CAT_DIR, 'metric_catalog.xlsx')
EXAMPLE_CATALOG = os.path.join(CAT_DIR, 'metric_catalog_example.xlsx')
MAX_ROWS = int(C.env('SQL_MAX_ROWS', '200'))
SQL_TIMEOUT = int(C.env('SQL_TIMEOUT', '20'))

# ---------------- S22 카탈로그 ----------------
_SHEETS = {'metrics': '지표정의', 'codes': '코드값사전', 'tables': '테이블카탈로그', 'allow': 'allow_list'}
_REN = {
    'metrics': {'지표ID': 'id', '지표명 (업무 용어)': 'name', '별칭 (; 구분)': 'alias', '한 줄 정의': 'define',
                '대상 뷰 · 테이블': 'view', '집계식 (SQL)': 'expr', '기본 필터': 'filter', '단위': 'unit',
                '기간 단위': 'period', '소유 부서': 'owner', '갱신 주기': 'refresh'},
    'codes': {'구분': 'kind', '코드': 'code', '표준명': 'name', '별칭 (; 구분)': 'alias', '사용 컬럼': 'column'},
    'tables': {'물리명': 'table', '논리명': 'label', '유형': 'kind', '소유 부서': 'owner', '갱신 주기': 'refresh',
               '주요 컬럼': 'columns', '설명': 'desc', '연계 우선': 'priority'},
    'allow': {'뷰 · 테이블': 'table', '허용 컬럼 (; 구분, * 면 전체)': 'columns', '행 접근 제한 컬럼': 'row_filter', '사용': 'use'},
}


def load_catalog(path=None):
    """지표 정의서 xlsx → {'metrics','codes','tables','allow'} DataFrame. 예시 행(회색)은 그대로 읽힌다."""
    path = path or (DEFAULT_CATALOG if os.path.exists(DEFAULT_CATALOG) else EXAMPLE_CATALOG)
    out = {}
    for key, sheet in _SHEETS.items():
        df = pd.read_excel(path, sheet_name=sheet, header=3).dropna(how='all')
        df = df.rename(columns=_REN[key])
        df = df[[c for c in _REN[key].values() if c in df.columns]].fillna('')
        out[key] = df.reset_index(drop=True)
    out['path'] = path
    return out


def allow_map(cat):
    """{테이블: 허용 컬럼 set 또는 '*'} — 사용='Y' 인 것만."""
    m = {}
    for r in cat['allow'].itertuples():
        if str(getattr(r, 'use', 'Y')).upper() != 'Y':
            continue
        cols = str(r.columns).strip()
        m[str(r.table).upper()] = '*' if cols in ('*', '') else {c.strip().upper() for c in cols.split(';') if c.strip()}
    return m


def alias_index(cat):
    """별칭 → (종류, 값) 색인. 지표명 · 코드 별칭을 한 번에."""
    idx = {}
    for r in cat['metrics'].itertuples():
        for a in [r.name] + str(r.alias).split(';'):
            if str(a).strip():
                idx[str(a).strip().lower()] = ('metric', r.id)
    for r in cat['codes'].itertuples():
        for a in [r.name] + str(r.alias).split(';'):
            if str(a).strip():
                idx[str(a).strip().lower()] = ('code', r.code)
    return idx


# ---------------- S24 라우팅 ----------------
NUM_WORDS = ['얼마', '몇', '수치', '합계', '총', '평균', '최대', '최소', '추이', '증감', '변동', '비중', '점유율',
             '대비', '전월', '전년', '전분기', '누적', '건수', '금액', '단가', '가격', '물량', '출하', '재고', '매출', '%']
TXT_WORDS = ['왜', '이유', '배경', '경위', '동향', '전망', '리스크', '영향', '대응', '평가', '의견', '요약', '정리', '내용']
NOANS = ['개인정보', '연봉', '급여']


def route(question, cat=None, use_llm=False):
    """질문 → ('sql'|'rag'|'hybrid'|'none', 근거dict). 규칙 우선, use_llm=True 면 애매할 때만 사내 LLM."""
    q = str(question)
    ql = q.lower()
    idx = alias_index(cat) if cat is not None else {}
    hits = sorted({v for k, v in idx.items() if k and k in ql})
    n_num = sum(1 for w in NUM_WORDS if w in q)
    n_txt = sum(1 for w in TXT_WORDS if w in q)
    has_metric = any(t == 'metric' for t, _ in hits)
    has_period = bool(re.search(r'(\d{4}\s*년|\d\s*분기|[1-4]Q|\d{1,2}\s*월|최근|올해|작년|전년|주간|월별|분기별)', q))
    why = dict(numeric_words=n_num, text_words=n_txt, metric_hit=has_metric,
               catalog_hits=[v for _, v in hits], period=has_period)
    if any(w in q for w in NOANS):
        return 'none', dict(reason='민감 정보', **why)
    if has_metric and n_txt >= 1:
        return 'hybrid', dict(reason='지표 + 설명 요구', **why)
    if has_metric or (n_num >= 2 and has_period):
        return 'sql', dict(reason='지표 · 수치 질문', **why)
    if n_txt >= 1 or n_num == 0:
        return 'rag', dict(reason='서술형', **why)
    if use_llm and C.LLM_URL:
        import lab_search
        lab = lab_search.llm_answer(
            f'다음 질문을 sql / rag / hybrid / none 중 하나로만 분류하라. 설명 금지.\n질문: {q}', pd.DataFrame(columns=['text', 'doc_id']))
        lab = re.findall(r'sql|rag|hybrid|none', str(lab).lower())
        if lab:
            return lab[0], dict(reason='LLM 분류', **why)
    return 'rag', dict(reason='기본값', **why)


# ---------------- S25 SQL 생성 ----------------
def _period_filter(question, col='YM'):
    """질문의 기간 표현 → SQL 조건 (YYYYMM 기준). 못 찾으면 빈 문자열."""
    q = str(question)
    m = re.search(r'(20\d{2})\s*년\s*([1-4])\s*분기', q) or re.search(r'([1-4])Q\s*(\d{2})', q)
    if m:
        if '분기' in q:
            y, qq = int(m.group(1)), int(m.group(2))
        else:
            qq, y = int(m.group(1)), 2000 + int(m.group(2))
        s, e = (qq - 1) * 3 + 1, qq * 3
        return f"{col} BETWEEN '{y}{s:02d}' AND '{y}{e:02d}'"
    m = re.search(r'(20\d{2})\s*년\s*(\d{1,2})\s*월', q)
    if m:
        return f"{col} = '{int(m.group(1))}{int(m.group(2)):02d}'"
    m = re.search(r'(20\d{2})\s*년', q)
    if m:
        return f"{col} LIKE '{m.group(1)}%'"
    return ''


def make_sql(question, cat, dialect=None, use_llm=None):
    """질문 → SQL. 기본은 카탈로그 기반 규칙 생성(설명 가능), 사내 LLM 이 있으면 llm 모드.
       반환: (sql, how)  how = 'rule' | 'llm' | ''"""
    dialect = dialect or ('sqlite' if C.IS_SAMPLE else 'oracle')
    use_llm = C.USE_LLM if use_llm is None else use_llm
    if use_llm:
        sql = _llm_sql(question, cat, dialect)
        if sql:
            return sql, 'llm'
    ql = str(question).lower()
    met = None
    for r in cat['metrics'].itertuples():
        for a in [r.name] + str(r.alias).split(';'):
            if str(a).strip() and str(a).strip().lower() in ql:
                met = r
                break
        if met is not None:
            break
    if met is None:
        return '', ''
    codes = [r.code for r in cat['codes'].itertuples()
             if any(str(a).strip() and str(a).strip().lower() in ql for a in [r.name] + str(r.alias).split(';'))]
    col = 'YW' if str(met.period) == '주' else 'YM'
    where = [w for w in [str(met.filter).strip(), _period_filter(question, col)] if w]
    if codes:
        where.append('PRODUCT_CODE IN (' + ', '.join(f"'{c}'" for c in codes) + ')')
    sql = f"SELECT {col}, {met.expr} AS {met.id}\nFROM {met.view}"
    if where:
        sql += '\nWHERE ' + '\n  AND '.join(where)
    sql += f'\nGROUP BY {col}\nORDER BY {col}'
    return add_limit(sql, MAX_ROWS, dialect), 'rule'


def schema_prompt(cat, tables=None):
    """LLM 에 줄 스키마 설명 — 전체가 아니라 허용 뷰만."""
    am = allow_map(cat)
    lines = []
    for r in cat['tables'].itertuples():
        t = str(r.table).upper()
        if t not in am or (tables and t not in {x.upper() for x in tables}):
            continue
        cols = str(r.columns) if am[t] == '*' else '; '.join(sorted(am[t]))
        lines.append(f'- {r.table} ({r.label}): {cols}  // {r.desc}')
    met = '\n'.join(f'- {r.name}({r.alias}) = {r.expr} FROM {r.view} {("WHERE " + r.filter) if str(r.filter).strip() else ""} [{r.unit}]'
                    for r in cat['metrics'].itertuples())
    codes = '\n'.join(f'- {r.kind} {r.name}({r.alias}) = {r.column} {r.code}' for r in cat['codes'].itertuples())
    return f'[조회 가능 뷰]\n' + '\n'.join(lines) + f'\n\n[지표 정의]\n{met}\n\n[코드값]\n{codes}'


def _llm_sql(question, cat, dialect):
    """사내 LLM 으로 SQL 생성 (OpenAI 호환). 실패하면 빈 문자열."""
    if not C.LLM_URL:
        return ''
    import requests
    prompt = (f'{schema_prompt(cat)}\n\n규칙:\n- {dialect} 문법\n- SELECT 문 하나만, 세미콜론 없이\n'
              f'- 위 목록에 없는 테이블 · 컬럼 사용 금지\n- 최대 {MAX_ROWS}행\n- 설명 없이 SQL만 출력\n\n질문: {question}\nSQL:')
    try:
        r = requests.post(C.LLM_URL, headers={'Authorization': f'Bearer {C.LLM_API_KEY}'},
                          json={'model': C.LLM_MODEL, 'temperature': 0,
                                'messages': [{'role': 'user', 'content': prompt}]},
                          timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
        r.raise_for_status()
        sql = r.json()['choices'][0]['message']['content']
        sql = re.sub(r'^```(?:sql)?|```$', '', sql.strip(), flags=re.M).strip()
        return sql
    except Exception as ex:
        print('  LLM SQL 생성 실패:', type(ex).__name__, '→ 규칙 생성으로 대체')
        return ''


# ---------------- S25 정적 검증 ----------------
FORBIDDEN = r'\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|CALL|COMMIT|ROLLBACK)\b'


def add_limit(sql, n=MAX_ROWS, dialect='oracle'):
    s = sql.rstrip().rstrip(';')
    if re.search(r'\b(LIMIT|FETCH FIRST)\b', s, re.I):
        return s
    return s + (f'\nLIMIT {n}' if dialect == 'sqlite' else f'\nFETCH FIRST {n} ROWS ONLY')


def used_tables(sql):
    return {t.upper() for t in re.findall(r'\b(?:FROM|JOIN)\s+([A-Za-z_][\w.$]*)', sql or '', re.I)}


def used_columns(sql):
    toks = set(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]{2,})\b', sql or ''))
    kw = {'SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'BY', 'AND', 'OR', 'AS', 'SUM', 'AVG', 'COUNT', 'MIN', 'MAX',
          'NULLIF', 'BETWEEN', 'LIKE', 'FETCH', 'FIRST', 'ROWS', 'ONLY', 'LIMIT', 'DESC', 'ASC', 'CASE', 'WHEN',
          'THEN', 'ELSE', 'END', 'NOT', 'NULL', 'DISTINCT', 'HAVING', 'JOIN', 'ON', 'WITH', 'ROUND', 'COALESCE'}
    return {t.upper() for t in toks} - kw


def validate(sql, cat, dialect=None, max_rows=MAX_ROWS):
    """실행 전 차단. 반환: dict(ok, problems[], sql=보정된 SQL)"""
    dialect = dialect or ('sqlite' if C.IS_SAMPLE else 'oracle')
    p = []
    s = (sql or '').strip()
    if not s:
        p.append('SQL 없음')
        return dict(ok=False, problems=p, sql='')
    if not re.match(r'^\s*(SELECT|WITH)\b', s, re.I):
        p.append('SELECT/WITH 로 시작하지 않음')
    if re.search(FORBIDDEN, s, re.I):
        p.append('금지 구문 포함(DDL/DML)')
    if s.rstrip().rstrip(';').count(';'):
        p.append('여러 문장(;) 포함')
    am = allow_map(cat)
    bad_t = {t for t in used_tables(s) if t not in am}
    if bad_t:
        p.append('허용 목록 밖 테이블: ' + ', '.join(sorted(bad_t)))
    for t in used_tables(s) & set(am):
        if am[t] != '*':
            known = {c.upper() for c in am[t]}
            allc = used_columns(s) & {c.upper() for r in cat['allow'].itertuples() if str(r.columns) != '*'
                                      for c in str(r.columns).split(';') if c.strip()}
            bad_c = (allc - known)
            if bad_c and len(used_tables(s)) == 1:
                p.append('허용 목록 밖 컬럼: ' + ', '.join(sorted(bad_c)))
    s2 = add_limit(s, max_rows, dialect)
    return dict(ok=not p, problems=p, sql=s2)


# ---------------- S25 실행 ----------------
def run_sql(sql, dialect=None, max_rows=MAX_ROWS):
    """sample=SQLite(샘플 정형 DB), live=Oracle. 읽기 전용 계정 권장."""
    dialect = dialect or ('sqlite' if C.IS_SAMPLE else 'oracle')
    if dialect == 'sqlite':
        import lab_sample_sql
        con = lab_sample_sql.connect()
        return pd.read_sql_query(sql, con).head(max_rows)
    import lab_io
    cur = lab_io.connect().cursor()
    cur.callTimeout = SQL_TIMEOUT * 1000
    cur.execute(sql)
    cols = [d[0].lower() for d in cur.description]
    rows = cur.fetchmany(max_rows)
    cur.close()
    return pd.DataFrame(rows, columns=cols)


def explain(sql, dialect=None):
    """드라이런 — 문법 · 비용 확인 (결과를 읽지 않는다)."""
    dialect = dialect or ('sqlite' if C.IS_SAMPLE else 'oracle')
    try:
        if dialect == 'sqlite':
            import lab_sample_sql
            pd.read_sql_query('EXPLAIN QUERY PLAN ' + sql, lab_sample_sql.connect())
        else:
            import lab_io
            cur = lab_io.connect().cursor()
            cur.execute('EXPLAIN PLAN FOR ' + sql)
            cur.close()
        return True, ''
    except Exception as ex:
        return False, f'{type(ex).__name__}: {ex}'


# ---------------- S29 실행결과 정확도 ----------------
def _norm(v, nd=2):
    if isinstance(v, (int, float, np.integer, np.floating)) and not pd.isna(v):
        return round(float(v), nd)
    return str(v).strip()


def exec_match(pred, gold, nd=2):
    """결과 값 일치(EX) — 컬럼 순서 · 이름은 무시하고 값 집합으로 비교."""
    if pred is None or gold is None or len(pred) == 0 or len(gold) == 0:
        return False
    a = {tuple(_norm(v, nd) for v in row) for row in pred.itertuples(index=False)}
    b = {tuple(_norm(v, nd) for v in row) for row in gold.itertuples(index=False)}
    return a == b


def answer_from_sql(question, df, meta_label='', llm=True):
    """S26 결합 — 표(Markdown) + 출처 라벨을 컨텍스트로 만들어 사내 LLM 에 요약을 맡긴다."""
    head = df.head(20)
    table = '| ' + ' | '.join(head.columns) + ' |\n|' + '---|' * len(head.columns) + '\n'
    table += '\n'.join('| ' + ' | '.join(str(v) for v in r) + ' |' for r in head.itertuples(index=False))
    ctx = f'[{meta_label}]\n{table}'
    if not llm or not C.USE_LLM:
        return ctx
    import lab_search
    return lab_search.llm_answer(question, pd.DataFrame([{'text': ctx, 'doc_id': 'DB'}]))
