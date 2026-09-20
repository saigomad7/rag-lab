# -*- coding: utf-8 -*-
"""샘플 정형 DB (SQLite) — LAB_MODE=sample 에서 SQL 이 실제로 돌게 한다.
   카탈로그 예시(metric_catalog_example.xlsx)의 뷰 · 컬럼과 같은 이름을 쓴다."""
import sqlite3
import numpy as np
import pandas as pd

_con = None
PRODUCTS = ['P-HBM3E-12', 'P-ESSD']
CUSTOMERS = ['C-0001', 'C-0002']
REGIONS = ['R-CN', 'R-US']


def _build():
    rng = np.random.RandomState(11)
    ym = [f'2026{m:02d}' for m in range(1, 10)]
    rows = []
    for y in ym:
        for p in PRODUCTS:
            for c in CUSTOMERS:
                base = 9.0 if p == 'P-ESSD' else 3.0
                qty = round(base * (1 + 0.04 * ym.index(y)) + rng.rand() * 0.6, 2)
                rows.append(dict(YM=y, PRODUCT_CODE=p, CUSTOMER_CODE=c, REGION_CODE=REGIONS[CUSTOMERS.index(c)],
                                 SHIP_QTY_EB=qty, AMT_USD=round(qty * (1450 if p == 'P-ESSD' else 9800), 1),
                                 STATUS='CONFIRMED'))
    sales = pd.DataFrame(rows)
    rows = []
    for y in ym:
        for p in PRODUCTS:
            for t in ('CONTRACT', 'SPOT'):
                q = round(80 + rng.rand() * 20, 1)
                unit = (1.45 if p == 'P-ESSD' else 9.8) * (1 + 0.02 * ym.index(y)) * (1.0 if t == 'CONTRACT' else 1.06)
                rows.append(dict(YM=y, PRODUCT_CODE=p, PRICE_TYPE=t, QTY=q, AMT_USD=round(q * unit, 2)))
    price = pd.DataFrame(rows)
    rows = []
    for w in range(1, 14):
        for p in PRODUCTS:
            ship = round(2.0 + rng.rand(), 2)
            rows.append(dict(YW=f'2026W{w:02d}', PRODUCT_CODE=p, INV_QTY=round(ship * (4 + rng.rand()), 2), WEEKLY_SHIP=ship))
    inv = pd.DataFrame(rows)
    con = sqlite3.connect(':memory:')
    sales.to_sql('V_SALES_MONTHLY', con, index=False)
    price.to_sql('V_PRICE_MONTHLY', con, index=False)
    inv.to_sql('V_INVENTORY_WEEKLY', con, index=False)
    sales.to_sql('T_SALES_RAW', con, index=False)          # 원본 테이블 — allow_list 에서 사용=N (차단 확인용)
    return con


def connect():
    global _con
    if _con is None:
        _con = _build()
    return _con


def golden():
    """정형 골든셋 (질문 → 정답 SQL). 정답 수치는 정답 SQL 을 실행해 만든다."""
    q = [
     ('Q01', '2026년 3분기 eSSD 출하량은?', 'sql',
      "SELECT YM, SUM(SHIP_QTY_EB) AS M001 FROM V_SALES_MONTHLY WHERE STATUS='CONFIRMED' "
      "AND YM BETWEEN '202607' AND '202609' AND PRODUCT_CODE IN ('P-ESSD') GROUP BY YM ORDER BY YM"),
     ('Q02', '2026년 8월 HBM3E 12단 출하량은?', 'sql',
      "SELECT YM, SUM(SHIP_QTY_EB) AS M001 FROM V_SALES_MONTHLY WHERE STATUS='CONFIRMED' "
      "AND YM = '202608' AND PRODUCT_CODE IN ('P-HBM3E-12') GROUP BY YM ORDER BY YM"),
     ('Q03', '2026년 eSSD 계약가격 추이는?', 'sql',
      "SELECT YM, SUM(AMT_USD)/NULLIF(SUM(QTY),0) AS M002 FROM V_PRICE_MONTHLY WHERE PRICE_TYPE='CONTRACT' "
      "AND YM LIKE '2026%' AND PRODUCT_CODE IN ('P-ESSD') GROUP BY YM ORDER BY YM"),
     ('Q04', 'eSSD 재고주수는 어떻게 되나?', 'sql',
      "SELECT YW, SUM(INV_QTY)/NULLIF(AVG(WEEKLY_SHIP),0) AS M003 FROM V_INVENTORY_WEEKLY "
      "WHERE PRODUCT_CODE IN ('P-ESSD') GROUP BY YW ORDER BY YW"),
     ('Q05', '3분기 eSSD 출하량과 그렇게 본 이유는?', 'hybrid', ''),
     ('Q06', 'HBM 시장 동향은 어떤가?', 'rag', ''),
     ('Q07', '담당자 연봉 정보 알려줘', 'none', ''),
    ]
    return pd.DataFrame(q, columns=['qid', 'question', 'gold_route', 'gold_sql'])
