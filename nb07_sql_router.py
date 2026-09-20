# -*- coding: utf-8 -*-
"""
nb07 · 정형 데이터 연계 (Phase 3) — 체크리스트 S22~S29
  카탈로그 로드 → 질의 라우팅 → SQL 생성 → 정적 검증(실행 전 차단) → 드라이런 → 실행 → 결합 → 평가(EX)
sample 모드에서는 SQLite 샘플 정형 DB로 SQL 이 실제로 돈다.
"""
# %% [0] 준비 — 가장 먼저 실행
import os, sys, importlib
try:
    LAB = os.path.dirname(os.path.abspath(__file__))
except NameError:
    LAB = r'C:\work\rag_lab'          # ← __file__ 이 없다고 나오면 이 폴더 경로를 직접 적는다
if LAB not in sys.path:
    sys.path.insert(0, LAB)
os.chdir(LAB)
import pandas as pd
import lab_config as C
importlib.reload(C)
import lab_io, lab_search, lab_eval, lab_sql
for _m in (lab_io, lab_search, lab_eval, lab_sql):
    importlib.reload(_m)
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 70)
print('LAB_MODE =', C.LAB_MODE, '| SQL 실행 대상 =', 'SQLite 샘플' if C.IS_SAMPLE else 'Oracle(읽기 전용 계정 권장)')

# %% [1] S22 카탈로그 — 지표 정의서 읽기 (catalog/metric_catalog.xlsx, 없으면 예시 파일)
cat = lab_sql.load_catalog()
metrics, codes, tables, allow = cat['metrics'], cat['codes'], cat['tables'], cat['allow']
print('카탈로그:', cat['path'])
print(metrics[['id', 'name', 'view', 'expr', 'unit']].to_string(index=False))
print()
print(allow.to_string(index=False))
print('\n허용 테이블:', list(lab_sql.allow_map(cat)))

# %% [2] LLM 에 줄 스키마 설명 — 전체가 아니라 허용 뷰만 (S23 · S25)
schema_txt = lab_sql.schema_prompt(cat)
print(schema_txt)

# %% [3] S24 라우팅 — 질문을 정형 / 비정형 / 혼합 / 불가로
QUESTIONS = [
 '2026년 3분기 eSSD 출하량은?',
 '2026년 8월 HBM3E 12단 출하량은?',
 '3분기 eSSD 출하량과 그렇게 본 이유는?',
 'HBM 시장 동향은 어떤가?',
 '최근 계약가격이 오른 이유가 뭐야?',
 '담당자 연봉 정보 알려줘',
]
rows = []
for q in QUESTIONS:
    r, why = lab_sql.route(q, cat)
    rows.append(dict(question=q, route=r, 근거=why['reason'], 수치어=why['numeric_words'],
                     서술어=why['text_words'], 카탈로그=','.join(map(str, why['catalog_hits'])), 기간=why['period']))
routing = pd.DataFrame(rows)
print(routing.to_string(index=False))

# %% [4] S25 SQL 생성 + 정적 검증 — 실행 전에 막는다
QUESTION = '2026년 3분기 eSSD 출하량은?'
sql, how = lab_sql.make_sql(QUESTION, cat)
check = lab_sql.validate(sql, cat)
ok_plan, plan_msg = lab_sql.explain(check['sql']) if check['ok'] else (False, '검증 실패로 드라이런 생략')
print(f'생성 방식: {how}\n--- SQL ---\n{check["sql"]}\n--- 검증 ---')
print('통과' if check['ok'] else '차단: ' + ' / '.join(check['problems']))
print('드라이런:', '통과' if ok_plan else plan_msg)

# %% [5] 차단 동작 확인 — 금지 구문 · 허용 목록 밖 테이블 (S25 · S28)
BAD = {
 '삭제 구문': 'DELETE FROM V_SALES_MONTHLY',
 '원본 테이블(사용=N)': 'SELECT * FROM T_SALES_RAW',
 '여러 문장': 'SELECT 1; DROP TABLE V_SALES_MONTHLY',
 '정상': "SELECT YM, SUM(SHIP_QTY_EB) FROM V_SALES_MONTHLY WHERE YM LIKE '2026%' GROUP BY YM",
}
guard = pd.DataFrame([dict(사례=k, 통과=lab_sql.validate(v, cat)['ok'],
                           차단사유=' / '.join(lab_sql.validate(v, cat)['problems'])) for k, v in BAD.items()])
print(guard.to_string(index=False))

# %% [6] 실행 + S26 결합 — 표에 쿼리 출처 라벨을 붙여 컨텍스트로
result = lab_sql.run_sql(check['sql']) if check['ok'] else pd.DataFrame()
label = f'DB | {metrics.loc[0, "view"] if len(metrics) else ""} | {QUESTION} | 조회 {pd.Timestamp.now():%Y-%m-%d %H:%M}'
context = lab_sql.answer_from_sql(QUESTION, result, label, llm=False)
print(result.to_string(index=False))
print('\n--- LLM 에 넘길 컨텍스트 ---\n' + context)

# %% [7] 혼합 질문 — SQL 표 + RAG 청크를 한 답변으로 (패턴 A)
HYBRID_Q = '3분기 eSSD 출하량과 그렇게 본 이유는?'
sql_h, _ = lab_sql.make_sql(HYBRID_Q, cat)
chk_h = lab_sql.validate(sql_h, cat)
tbl_h = lab_sql.run_sql(chk_h['sql']) if chk_h['ok'] else pd.DataFrame()
_corpus = lab_io.load_chunks(n=None if C.IS_SAMPLE else 20000)
_ret = lab_search.Retriever(_corpus)
rag_h = _ret.search(HYBRID_Q, 'hybrid+rerank+mmr', k=3)
mixed_context = lab_sql.answer_from_sql(HYBRID_Q, tbl_h, f'DB | {HYBRID_Q}', llm=False) + '\n\n' + \
    '\n\n'.join(f'[문서 {r.rank} | {r.doc_id}]\n{str(r.text)[:200]}' for r in rag_h.itertuples())
print(mixed_context)
print('\n(live 모드에서는 lab_sql.answer_from_sql(..., llm=True) 로 사내 LLM 요약)')

# %% [8] S29 평가 — 라우팅 정확도 · SQL 유효율 · 실행결과 정확도(EX)
import lab_sample_sql
golden_sql = lab_sample_sql.golden() if C.IS_SAMPLE else lab_io.read_table(os.path.join(C.GOLDEN_DIR, 'sql_golden_v1.csv'))
rows = []
for g in golden_sql.itertuples():
    route, _ = lab_sql.route(g.question, cat)
    rec = dict(qid=g.qid, question=g.question, gold_route=g.gold_route, route=route, 라우팅=route == g.gold_route)
    if str(g.gold_sql).strip():
        s, how = lab_sql.make_sql(g.question, cat)
        v = lab_sql.validate(s, cat)
        rec.update(생성방식=how, SQL유효=v['ok'], 차단사유=' / '.join(v['problems']))
        if v['ok']:
            try:
                pred = lab_sql.run_sql(v['sql'])
                gold = lab_sql.run_sql(g.gold_sql)
                rec['EX일치'] = lab_sql.exec_match(pred, gold)
                rec['행수'] = len(pred)
            except Exception as ex:
                rec['EX일치'] = False; rec['오류'] = f'{type(ex).__name__}: {ex}'[:60]
    rows.append(rec)
sql_eval = pd.DataFrame(rows)
summary_sql = pd.Series({
    '라우팅 정확도': round(sql_eval['라우팅'].mean(), 3),
    'SQL 유효율': round(sql_eval['SQL유효'].dropna().mean(), 3) if 'SQL유효' in sql_eval else float('nan'),
    '실행결과 정확도(EX)': round(sql_eval['EX일치'].dropna().mean(), 3) if 'EX일치' in sql_eval else float('nan'),
    '문항 수': len(sql_eval),
})
print(sql_eval.to_string(index=False)); print(); print(summary_sql.to_string())
if C.IS_SAMPLE:
    print('\n주의: 샘플은 카탈로그 기반 규칙 생성이라 수치가 높게 나온다. 의미 있는 값은 live 에서 사내 LLM 이 SQL 을 생성할 때의 결과다.')

# %% [9] 저장
lab_io.save(routing, 'nb07_routing')
lab_io.save(guard, 'nb07_guard')
lab_io.save(sql_eval, 'nb07_sql_eval')
lab_io.save(summary_sql.rename('value').reset_index().rename(columns={'index': 'metric'}), 'nb07_summary')
