# -*- coding: utf-8 -*-
"""
데이터 입출력 — Oracle 읽기(live) / 샘플(sample) / 결과 저장
모든 함수는 '표준 컬럼 이름'의 DataFrame을 돌려준다 (lab_config.RAW · CHUNK 매핑으로 변환).
"""
import os
import datetime as dt
import pandas as pd
import lab_config as C

_conn = None


def sample_mod():
    """샘플 데이터 모듈 — SAMPLE_SET 값으로 16건 / 100건 선택"""
    import importlib
    return importlib.import_module('lab_sample100' if str(C.SAMPLE_SET) == '100' else 'lab_sample')


def connect():
    """Oracle 연결 (한 번 만들고 재사용). thin 모드 기본, ORA_THICK_LIB 있으면 thick."""
    global _conn
    if _conn is not None:
        return _conn
    import oracledb
    if C.ORA_THICK_LIB:
        oracledb.init_oracle_client(lib_dir=C.ORA_THICK_LIB)
    oracledb.defaults.fetch_lobs = False          # CLOB → str 로 바로 받기
    _conn = oracledb.connect(user=C.ORA_USER, password=C.ORA_PASSWORD, dsn=C.ORA_DSN)
    return _conn


def read_sql(sql, params=None):
    """임의 SQL → DataFrame (컬럼명 소문자)."""
    cur = connect().cursor()
    cur.execute(sql, params or {})
    cols = [d[0].lower() for d in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    cur.close()
    return df


def _select(m, n=None, where=None, sample_pct=None):
    """매핑(dict)으로 SELECT 문 생성. None 인 컬럼은 건너뛴다."""
    cols = [f'{v} AS {k}' for k, v in m.items() if k != 'table' and v]
    tbl = m['table'] + (f' SAMPLE({sample_pct})' if sample_pct else '')
    sql = f"SELECT {', '.join(cols)} FROM {tbl}"
    if where:
        sql += f' WHERE {where}'
    if n:
        sql += f' FETCH FIRST {int(n)} ROWS ONLY'
    return sql


def _std_types(df):
    if 'doc_type' in df:
        df['doc_type_raw'] = df['doc_type']
        df['doc_type'] = df['doc_type'].map(lambda x: C.DOC_TYPE_MAP.get(str(x), str(x)))
    # 날짜 컬럼 자동 변환 — 사내에서 추가한 날짜 항목(_at · _dt · _date)도 함께
    for c in df.columns:
        if c in ('published_at', 'collected_at') or str(c).lower().endswith(('_at', '_dt', '_date')):
            df[c] = pd.to_datetime(df[c], errors='coerce')
    return df


def load_raw(n=None, where=None, sample_pct=None):
    """원문 문서. n: 최대 행 수, where: SQL 조건(예: "DOC_TYPE='EMAIL'"), sample_pct: 테이블 표본 %."""
    if C.IS_SAMPLE:
        df = _std_types(sample_mod().raw_docs())      # 샘플도 live 와 같은 변환(별칭 매핑)을 거친다
        return df.head(n) if n else df
    return _std_types(read_sql(_select(C.RAW, n, where, sample_pct)))


def load_chunks(n=None, where=None, doc_ids=None, sample_pct=None):
    """청크. doc_ids 를 주면 해당 문서의 청크만 (1000개씩 나눠 조회)."""
    if C.IS_SAMPLE:
        df = sample_mod().chunks()
        if doc_ids is not None:
            df = df[df.doc_id.isin(list(doc_ids))]
        return df.head(n) if n else df
    if doc_ids is not None:
        ids, parts = list(doc_ids), []
        for i in range(0, len(ids), 1000):
            part = ids[i:i + 1000]
            binds = ', '.join(f':b{j}' for j in range(len(part)))
            sql = _select(C.CHUNK, None, f"{C.CHUNK['doc_id']} IN ({binds})")
            parts.append(read_sql(sql, {f'b{j}': v for j, v in enumerate(part)}))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return read_sql(_select(C.CHUNK, n, where, sample_pct))


def count_by_type():
    """소스 유형별 문서 수 · 날짜 누락 수 (DB에서 집계 — 전체 대상)."""
    if C.IS_SAMPLE:
        d = load_raw()
        g = d.groupby('doc_type').agg(docs=('doc_id', 'count'), no_pub_date=('published_at', lambda s: s.isna().sum()))
        return g.reset_index()
    r = C.RAW
    sql = (f"SELECT {r['doc_type']} AS doc_type, COUNT(*) AS docs, "
           f"SUM(CASE WHEN {r['published_at']} IS NULL THEN 1 ELSE 0 END) AS no_pub_date "
           f"FROM {r['table']} GROUP BY {r['doc_type']} ORDER BY 2 DESC")
    return _std_types(read_sql(sql))


def count_chunks_by_type():
    """소스 유형별 청크 수."""
    if C.IS_SAMPLE:
        ch, raw = load_chunks(), load_raw()
        return ch.merge(raw[['doc_id', 'doc_type']], on='doc_id').groupby('doc_type').size().rename('chunks').reset_index()
    r, c = C.RAW, C.CHUNK
    sql = (f"SELECT d.{r['doc_type']} AS doc_type, COUNT(*) AS chunks FROM {c['table']} ch "
           f"JOIN {r['table']} d ON d.{r['doc_id']} = ch.{c['doc_id']} GROUP BY d.{r['doc_type']}")
    return _std_types(read_sql(sql))


def sample_per_type(n_per_type=20):
    """유형별로 n건씩 원문 표본 (파싱 · 청킹 점검용)."""
    if C.IS_SAMPLE:
        return load_raw().groupby('doc_type', group_keys=False).head(n_per_type).reset_index(drop=True)
    types = count_by_type()['doc_type_raw'].tolist()
    parts = [load_raw(n_per_type, f"{C.RAW['doc_type']} = '{t}'") for t in types]
    return pd.concat(parts, ignore_index=True)


def read_table(path):
    """CSV(utf-8 · utf-8-sig · cp949 자동) 또는 xlsx 읽기 — 엑셀에서 저장한 골든셋용."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'파일 없음: {path}  (경로의 역슬래시는 r"C:\\..." 처럼 r 을 붙여 쓴다)')
    if path.lower().endswith(('.xlsx', '.xls')):
        try:
            return pd.read_excel(path)
        except PermissionError:
            raise PermissionError(f'엑셀에서 파일을 닫고 다시 실행하세요: {path}')
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError('read_table', b'', 0, 1, f'인코딩 판별 실패: {path}')


def save(df, name, excel=True):
    """out/ 폴더에 CSV(엑셀용 utf-8-sig)와 xlsx 로 저장. 경로를 돌려준다."""
    stamp = dt.datetime.now().strftime('%y%m%d_%H%M%S')
    base = os.path.join(C.OUT_DIR, f'{name}_{stamp}')
    try:
        df.to_csv(base + '.csv', index=False, encoding='utf-8-sig')
    except PermissionError:
        print('  ! 저장 실패: 같은 이름의 파일이 엑셀에 열려 있습니다. 닫고 셀을 다시 실행하세요 →', base + '.csv')
        return base + '.csv'
    if excel:
        try:
            df.to_excel(base + '.xlsx', index=False)
        except PermissionError:
            print('  ! xlsx 저장 실패: 엑셀에 열려 있음 →', base + '.xlsx')
        except Exception as ex:          # openpyxl 없거나 셀 길이 초과
            print('  (xlsx 저장 생략:', type(ex).__name__, ')')
    print('  저장:', base + '.csv')
    return base + '.csv'
