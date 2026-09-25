# -*- coding: utf-8 -*-
"""
확장 샘플 데이터 — 문서 약 100건 (lab_sample.py 의 16건 대체용)

목적
  · 평가 지표가 의미를 갖는 최소 규모 확보 (16건은 Recall 이 늘 1.0 에 붙음)
  · 사내 데이터 특성을 흉내 — 소스 7종 · 기간 6개월 · 품질 결함 포함

인터페이스는 lab_sample 과 동일: raw_docs() · chunks() · golden()
전환:  .env 에  SAMPLE_SET=100   (기본값 16)

주의: 모든 회사명 · 수치 · 날짜는 **지어낸 예시**. 실제 시장 데이터가 아니다.
결함을 일부러 섞어 두었다 (nb00 · nb02 가 잡아내는지 확인용).
  결측 발행일 4 · 본문 결측 2 · 재송고 중복 3쌍 · 표 깨짐 2 · 초단문 청크 유발 3 · 고아 청크 1 · 청킹 누락 문서 1
"""
import random

import pandas as pd

SEED = 20260925

# ---------------- 어휘 ----------------
MAKERS = ['SK하이닉스', '삼성전자', '마이크론', 'CXMT', 'YMTC', '키오시아', '웨스턴디지털', '난야']
BUYERS = ['엔비디아', 'AMD', '구글', '메타', '마이크로소프트', '아마존', '브로드컴', '테슬라']
PRODUCTS = ['DDR5 서버 D램', 'LPDDR5X', 'HBM3E 12단', 'HBM4', 'eSSD QLC', 'CXL 2.0 메모리', 'GDDR7', 'DDR4 서버 D램']
FABS = ['이천 M16', '청주 M15X', '용인 클러스터', '히로시마', '시안', '허페이', '기타큐슈']
PRESS = ['한국경제', '전자신문', '디지털데일리', '머니투데이', '아시아경제', 'ZDNet코리아']
BROKERS = ['○○증권', '△△투자증권', '□□금융투자', '◇◇증권', '☆☆투자증권']
INSTS = ['한국반도체산업협회', 'TrendForce', 'Omdia', '산업연구원', '한국무역협회', 'IDC']
DEPTS = ['메모리마케팅팀', 'DRAM사업기획', 'NAND전략팀', '글로벌영업1팀', '수요예측파트', '원가기획팀']
PEOPLE = ['김지훈', '박서연', '이민호', '최유진', '정태현', '한소영', '오준석', '배은지', '신동혁', '윤가람']
QUARTERS = ['1Q26', '2Q26', '3Q26', '4Q26', '1Q27']
MONTHS = [f'2026-{m:02d}' for m in range(4, 10)]

# 주제 템플릿 — (주제 코드, 제목 틀, 본문 문장 틀 목록)
TOPICS = [
 ('price', '{prod} 고정거래가 {dir} — {q} {pct}% 전망', [
   '{q} {prod} 고정거래가는 전분기 대비 {pct}% {dir}할 것으로 전망된다.',
   '현물가는 {mon} 기준 {price}달러로, 전월 대비 {pct2}% {dir2}했다.',
   '{maker}는 계약 가격 협상에서 {pct3}% 인상을 요구한 것으로 파악된다.',
   '가격 {dir}의 배경은 AI 서버 수요 집중과 {prod} 공급 제약이다.']),
 ('supply', '{maker}, {fab} {prod} 라인 {act}', [
   '{maker}가 {fab} 공장의 {prod} 생산능력을 {act}한다고 {day}일 밝혔다.',
   '투자 규모는 약 {capex}조원이며 {year}년 {half}반기 양산이 목표다.',
   '월 웨이퍼 투입 기준 {wafer}만장 규모로, 전체 캐파의 약 {share}%에 해당한다.',
   '업계는 이번 결정으로 {q} 이후 공급 지형이 달라질 것으로 본다.']),
 ('demand', '{buyer} {prod} 발주 {dir} — {q} {vol}만개 규모', [
   '{buyer}가 {q} {prod} 발주 물량을 {vol}만개로 {dir} 조정했다.',
   'AI 가속기 출하 계획이 {pct}% 상향되면서 메모리 탑재량도 함께 늘었다.',
   '{maker}는 해당 물량의 약 {share}%를 확보한 것으로 추정된다.',
   '데이터센터 투자 확대가 {year}년까지 이어질 것이라는 관측이 우세하다.']),
 ('inventory', '{prod} 재고 {week}주 — {mon} 기준 {dir}', [
   '{mon} 기준 {prod} 유통 재고는 {week}주 수준으로 전월 대비 {dir}했다.',
   '정상 재고 기준인 {norm}주를 {gap} 상태가 {q}까지 이어질 전망이다.',
   '{maker}의 자체 재고는 {week2}주로 업계 평균을 밑돈다.',
   '재고 조정 국면이 마무리되면서 가격 협상력이 공급자 쪽으로 이동하고 있다.']),
 ('tech', '{maker} {prod} {tech} 적용 — {q} 양산 목표', [
   '{maker}가 {prod}에 {tech} 공정을 적용해 {q} 양산에 들어간다.',
   '기존 대비 전력 효율이 {pct}% 개선되고 집적도는 {pct2}% 높아진다.',
   '{buyer} 인증 절차는 {mon}에 착수해 {month2}개월가량 소요될 전망이다.',
   '경쟁사 대비 {month3}개월 앞선 일정으로, 초기 물량 배분에 유리하다는 평가다.']),
 ('policy', '{country} {prod} 수출규제 {act2} — {q} 영향 점검', [
   '{country} 당국이 {prod} 관련 수출 통제를 {act2}한다고 발표했다.',
   '적용 시점은 {mon}이며, 기존 계약분은 {month2}개월 유예된다.',
   '{maker}의 {fab} 생산분 가운데 약 {share}%가 영향권에 든다.',
   '대체 공급선 확보와 인증 전환에 최소 {month3}개월이 필요하다는 분석이다.']),
 ('customer', '{buyer} {prod} 인증 {res} — {maker} 물량 배분 {dir}', [
   '{buyer}의 {prod} 품질 인증에서 {maker}가 {res}했다.',
   '초기 배분 물량은 전체의 {share}% 수준으로 {q}부터 공급이 시작된다.',
   '단가는 기존 대비 {pct}% {dir2}된 수준에서 합의된 것으로 전해진다.',
   '고객사 집중도가 높아 특정 고객 의존 리스크는 남아 있다.']),
 ('capex', '{maker} {year}년 CapEx {capex}조원 — 전년 대비 {pct}% {dir}', [
   '{maker}가 {year}년 설비투자 규모를 {capex}조원으로 제시했다.',
   '전년 대비 {pct}% {dir}한 수치로, {prod} 비중이 {share}%를 차지한다.',
   '{fab} 신규 라인과 후공정 투자에 집중 배분될 예정이다.',
   '감가상각 부담은 {year2}년부터 본격화될 것으로 보인다.']),
]

_DIR = [('상승', '상승'), ('하락', '하락'), ('상향', '상향'), ('하향', '하향'), ('확대', '확대'), ('축소', '축소')]
_TECH = ['1c나노', 'EUV 다중패터닝', 'TSV 적층', '하이브리드 본딩', '4세대 10나노급', 'MR-MUF']
_ACT = ['증설', '전환', '감축', '재가동']
_ACT2 = ['강화', '일부 완화', '유예 연장']
_RES = ['통과', '조건부 통과', '재시험 판정']
_COUNTRY = ['미국', '일본', '네덜란드', '중국']



# ---------------- 조사 교정 ----------------
_JOSA = {'가': ('이', '가'), '이': ('이', '가'), '는': ('은', '는'), '은': ('은', '는'),
         '를': ('을', '를'), '을': ('을', '를'), '와': ('과', '와'), '과': ('과', '와')}
_TAIL_CONS = set('BCDGKLMNPRSTXZ')          # 영문 끝소리에 받침이 있는 자음
_NUM_CONS = set('136780')                    # 일 삼 육 칠 팔 영


def _has_batchim(w):
    ch = str(w).strip()[-1:]
    if not ch:
        return False
    if '가' <= ch <= '힣':
        return (ord(ch) - 0xAC00) % 28 != 0
    if ch.isdigit():
        return ch in _NUM_CONS
    return ch.upper() in _TAIL_CONS


def _fix_josa(text, names):
    """고유명사 뒤 조사를 받침에 맞게 교정 — '마이크론가' → '마이크론이'"""
    for n in names:
        if n not in text:
            continue
        b = _has_batchim(n)
        for j, (with_b, without_b) in _JOSA.items():
            text = text.replace(n + j, n + (with_b if b else without_b))
    return text


_NAMES = None


def _names():
    global _NAMES
    if _NAMES is None:
        _NAMES = sorted(set(MAKERS + BUYERS + PRODUCTS + FABS + PRESS + BROKERS + INSTS + DEPTS + PEOPLE
                            + _TECH + _COUNTRY), key=len, reverse=True)
    return _NAMES


def _fill(tpl, r):
    d = dict(
        maker=r.choice(MAKERS), buyer=r.choice(BUYERS), prod=r.choice(PRODUCTS), fab=r.choice(FABS),
        q=r.choice(QUARTERS), mon=r.choice(MONTHS), year=r.choice([2026, 2027, 2028]), year2=r.choice([2027, 2028]),
        pct=r.randint(3, 42), pct2=r.randint(2, 28), pct3=r.randint(5, 30), price=round(r.uniform(2.1, 18.7), 2),
        capex=round(r.uniform(3.5, 24.0), 1), wafer=r.randint(2, 18), share=r.randint(8, 65),
        vol=r.randint(30, 480), week=round(r.uniform(2.1, 11.8), 1), week2=round(r.uniform(1.5, 9.2), 1),
        norm=r.choice([4, 5, 6]), gap=r.choice(['웃도는', '밑도는']), day=r.randint(1, 28),
        half=r.choice(['상', '하']), month2=r.randint(2, 9), month3=r.randint(1, 12),
        tech=r.choice(_TECH), act=r.choice(_ACT), act2=r.choice(_ACT2), res=r.choice(_RES),
        country=r.choice(_COUNTRY),
    )
    dr = r.choice(_DIR)
    d['dir'], d['dir2'] = dr[0], dr[1]
    return _fix_josa(tpl.format(**d), _names())


def _make_body(r, n_sent=None):
    """주제 하나를 골라 제목 · 본문 문장을 생성. 뒤에 연관 주제 문단을 덧붙여 분량을 키운다."""
    code, title_t, sents = r.choice(TOPICS)
    seed_vals = r.getstate()
    title = _fill(title_t, r)
    r.setstate(seed_vals)                      # 제목과 본문이 같은 값을 쓰도록 상태 복원
    body = [_fill(s, r) for s in sents[:(n_sent or len(sents))]]
    _, _, sub = r.choice([t for t in TOPICS if t[0] != code])          # 연관 주제 문단
    body += [_fill(s, r) for s in r.sample(sub, k=min(3, len(sub)))]
    body += [_fill(s, r) for s in r.sample(r.choice(TOPICS)[2], k=2)]  # 배경 문단
    return code, title, body


# ---------------- 소스 유형별 포장 ----------------
def _news(r, title, body):
    press = r.choice(PRESS)
    rep = r.choice(PEOPLE)
    tail = f"\n관련기사\n- {_fill(r.choice(TOPICS)[1], r)}\n{rep} 기자 {rep[0].lower()}{r.randint(10,99)}@{press.lower()}.example\n무단 전재 및 재배포 금지"
    return ' '.join(body[:4]) + '\n\n' + ' '.join(body[4:]) + tail, press, rep


def _broker(r, title, body):
    br = r.choice(BROKERS)
    an = r.choice(PEOPLE)
    tbl = ('\n\n| 구분 | ' + ' | '.join(QUARTERS[:4]) + ' |\n|---|---|---|---|---|\n'
           + '| 출하량(만개) | ' + ' | '.join(str(r.randint(120, 980)) for _ in range(4)) + ' |\n'
           + '| ASP(달러) | ' + ' | '.join(str(round(r.uniform(2.2, 16.5), 2)) for _ in range(4)) + ' |\n'
           + '| 영업이익률(%) | ' + ' | '.join(str(r.randint(-8, 48)) for _ in range(4)) + ' |')
    head = f'{br} 리서치센터 | Industry Report\n{title}\n'
    return head + ' '.join(body[:4]) + '\n\n' + ' '.join(body[4:7]) + tbl + f'\n\n투자의견 {r.choice(["매수", "중립", "비중확대"])} · 목표주가 {r.randint(9, 38)}만원\n{an} 연구원', br, an


def _inst(r, title, body):
    inst = r.choice(INSTS)
    sec = (f'\n\n1. 개요\n{body[0]}\n\n2. 현황\n{" ".join(body[1:4])}\n\n3. 세부 동향\n{" ".join(body[4:7])}\n\n4. 전망\n{body[-1]}\n'
           f'\n자료 기준일: {r.choice(MONTHS)}-{r.randint(10, 28)}')
    return f'[{inst}] {title}' + sec, inst, None


def _email(r, title, body):
    sender = r.choice(PEOPLE)
    dept = r.choice(DEPTS)
    quote = f'> 이전 메일: {_fill(r.choice(TOPICS)[1], r)}\n> 확인 부탁드립니다.\n'
    sig = f'\n\n{sender} | {dept} | 010-{r.randint(1000,9999)}-{r.randint(1000,9999)}\n본 메일은 사내 기밀입니다.'
    return quote + ' '.join(body[:3]) + '\n\n' + ' '.join(body[3:6]) + sig, dept, sender


def _meeting(r, title, body):
    att = ', '.join(r.sample(PEOPLE, 4))
    dept = r.choice(DEPTS)
    act = '\n'.join(f'- [{r.choice(PEOPLE)}] {_fill(r.choice(TOPICS)[2][0], r)}' for _ in range(3))
    return (f'회의명: {title}\n참석: {att}\n\n[논의]\n' + '\n'.join('- ' + s for s in body)
            + f'\n\n[액션 아이템]\n{act}'), dept, att.split(',')[0]


def _report(r, title, body):
    dept = r.choice(DEPTS)
    au = r.choice(PEOPLE)
    return (f'{title}\n작성: {dept} {au} | 버전 v{r.randint(1,4)}.{r.randint(0,9)} | 승인: 완료\n\n'
            f'1. 배경\n{body[0]}\n\n2. 분석\n{" ".join(body[1:4])}\n\n3. 세부 검토\n{" ".join(body[4:7])}\n\n4. 시사점\n{body[-1]}\n'
            f'\n※ 본 문서는 사내 한정 자료임'), dept, au


def _exec(r, title, body):
    dept = r.choice(DEPTS)
    return (f'[슬라이드 1] {title}\n[슬라이드 2] 요약\n' + '\n'.join('· ' + s for s in body[:3])
            + '\n[슬라이드 3] 세부\n' + '\n'.join('· ' + s for s in body[3:6])
            + f'\n[슬라이드 4] 리스크\n· {body[-1]}\n[슬라이드 5] 결론\n· {r.choice(["현 기조 유지", "투자 재검토", "물량 재배분 필요"])}'
            + f'\n보고: {dept} → 경영진'), dept, None


WRAP = {'NEWS': _news, 'BROKER': _broker, 'INSTITUTION': _inst, 'EMAIL': _email,
        'MEETING': _meeting, 'REPORT': _report, 'EXEC_REPORT': _exec}
MIX = [('NEWS', 32), ('BROKER', 18), ('INSTITUTION', 10), ('EMAIL', 14),
       ('MEETING', 8), ('REPORT', 12), ('EXEC_REPORT', 6)]     # 합 100
PREFIX = {'NEWS': 'N', 'BROKER': 'B', 'INSTITUTION': 'I', 'EMAIL': 'E',
          'MEETING': 'M', 'REPORT': 'R', 'EXEC_REPORT': 'X'}
SEC = {'NEWS': 0, 'BROKER': 0, 'INSTITUTION': 0, 'EMAIL': 2, 'MEETING': 2, 'REPORT': 2, 'EXEC_REPORT': 3}


# ---------------- 문서 생성 ----------------
def _build():
    r = random.Random(SEED)
    rows, meta = [], []
    start = pd.Timestamp('2026-04-01')
    for dtype, cnt in MIX:
        for i in range(1, cnt + 1):
            code, title, body = _make_body(r)
            text, org, author = WRAP[dtype](r, title, body)
            pub = start + pd.Timedelta(days=r.randint(0, 172))
            rows.append(dict(
                doc_id=f'{PREFIX[dtype]}{i:03d}', doc_type=dtype, title=title, body=text,
                published_at=pub, collected_at=pub + pd.Timedelta(days=r.randint(0, 3)),
                org_name=org, author=author, security_level=SEC[dtype], src_url=None, file_path=None))
            meta.append(dict(topic=code, sents=body))
    df = pd.DataFrame(rows)
    df['topic_'] = [m['topic'] for m in meta]
    df['sents_'] = [m['sents'] for m in meta]

    # ---- 일부러 심는 결함 (nb00 · nb02 가 잡아내는지 확인용) ----
    df.loc[df.doc_id.isin(['N005', 'N019', 'E007', 'M003']), 'published_at'] = pd.NaT     # 발행일 결측 4
    df.loc[df.doc_id.isin(['B012', 'R009']), 'body'] = ''                                  # 본문 결측(파싱 실패) 2
    for src, dst in [('N002', 'N021'), ('N008', 'N027'), ('I003', 'I009')]:                # 재송고 중복 3쌍
        df.loc[df.doc_id == dst, 'body'] = df.loc[df.doc_id == src, 'body'].values[0]
        df.loc[df.doc_id == dst, 'title'] = df.loc[df.doc_id == src, 'title'].values[0]
    for d in ['B004', 'B015']:                                                             # 표 깨짐 2
        b = df.loc[df.doc_id == d, 'body'].values[0]
        df.loc[df.doc_id == d, 'body'] = b.replace(' | ', '  ').replace('|---|---|---|---|---|', '')
    for d in ['N011', 'E013', 'X002']:                                                     # 초단문 청크 유발 3
        df.loc[df.doc_id == d, 'body'] = df.loc[df.doc_id == d, 'body'].values[0] + '\n\n확인 요망.\n\n끝.'
    return df


_CACHE = {}


def raw_docs():
    """통합 문서 테이블 — 100건 (lab_sample.raw_docs 와 같은 컬럼)"""
    if 'raw' not in _CACHE:
        _CACHE['raw'] = _build()
    return _CACHE['raw'].drop(columns=['topic_', 'sents_']).copy()


def _split(text, size=420):
    """문단 경계 우선 · 표(| 로 시작하는 줄 묶음)는 통째로 한 청크"""
    if not str(text).strip():
        return []
    parts, buf = [], ''
    for para in str(text).split('\n\n'):
        if para.lstrip().startswith('|'):
            if buf.strip():
                parts.append(buf.strip()); buf = ''
            parts.append(para.strip()); continue
        if len(buf) + len(para) > size and buf.strip():
            parts.append(buf.strip()); buf = para
        else:
            buf = (buf + '\n\n' + para) if buf else para
    if buf.strip():
        parts.append(buf.strip())
    return parts


def chunks(size=420):
    """청크 테이블 — DOC_ID 로 원문 연결. 고아 청크 1건 · 청킹 누락 문서 1건 포함"""
    if f'ch{size}' in _CACHE:
        return _CACHE[f'ch{size}'].copy()
    raw = raw_docs()
    rows = []
    for d in raw.itertuples():
        if d.doc_id == 'R011':                        # 청킹 누락 문서 1건
            continue
        for seq, t in enumerate(_split(d.body, size), 1):
            rows.append(dict(chunk_id=f'{d.doc_id}#{seq}', doc_id=d.doc_id, seq=seq, text=t))
    rows.append(dict(chunk_id='Z999#1', doc_id='Z999', seq=1,                 # 고아 청크 1건
                     text='원문 테이블에 없는 문서의 청크. 적재 정합성 점검용.'))
    df = pd.DataFrame(rows)
    _CACHE[f'ch{size}'] = df
    return df.copy()


# ---------------- 골든셋 ----------------
# 주제별 (질문 꼬리, 근거 문장 번호, 유형)
Q_TPL = {
 'price':     [('의 가격 전망은?', 0, '수치'), ('의 현물가 수준은?', 1, '수치')],
 'supply':    [('의 투자 규모와 양산 시점은?', 1, '수치'), ('의 캐파 비중은?', 2, '수치')],
 'demand':    [('의 발주 물량은?', 0, '수치'), ('의 물량 확보 비중은?', 2, '수치')],
 'inventory': [('의 재고 수준은?', 0, '수치'), ('의 정상 재고 대비 상태는?', 1, '사실')],
 'tech':      [('의 공정 적용과 양산 일정은?', 0, '사실'), ('의 성능 개선 폭은?', 1, '수치')],
 'policy':    [('의 수출규제 변경 내용은?', 0, '사실'), ('의 영향 범위는?', 2, '수치')],
 'customer':  [('의 인증 결과는?', 0, '사실'), ('의 초기 배분 물량은?', 1, '수치')],
 'capex':     [('의 설비투자 규모는?', 0, '수치'), ('의 제품 비중은?', 1, '수치')],
}
NO_ANSWER = [
 ('TSMC 의 2026년 DRAM 출하량은?', '전제 오류 — 코퍼스에 없는 대상'),
 ('2025년 1분기 eSSD 계약가격 추이는?', '수집 기간(2026-04~09) 밖'),
 ('인텔 파운드리의 HBM 수율은?', '보유 자료에 없는 대상 · 지표'),
]


def golden():
    """평가용 골든셋 30문항 — 정답 문서 · 정답 문장이 실제 코퍼스에 존재"""
    if 'gold' in _CACHE:
        return _CACHE['gold'].copy()
    df = _CACHE.get('raw')
    if df is None:
        raw_docs(); df = _CACHE['raw']
    ok = df[(df.body.str.len() > 200) & (~df.doc_id.isin(['N021', 'N027', 'I009', 'R011']))]
    r = random.Random(SEED + 1)
    rows, used = [], set()
    pool = list(ok.itertuples())
    r.shuffle(pool)
    for d in pool:
        if len(rows) >= 22:
            break
        if d.doc_type in used and len([x for x in rows if x['source'] == d.doc_type]) >= 5:
            continue
        opts = Q_TPL[d.topic_]
        n_num = len([x for x in rows if x['q_type'] == '수치'])
        tail, idx, qt = (opts[1] if (n_num > len(rows) * 0.55 and len(opts) > 1 and opts[1][2] != '수치')
                         else r.choice(opts))
        key = str(d.title).split('—')[0].strip()
        sent = d.sents_[idx] if idx < len(d.sents_) else d.sents_[0]
        rows.append(dict(qid=f'G{len(rows) + 1:03d}', question=key + tail, q_type=qt,
                         source=d.doc_type, gold_doc_ids=d.doc_id, gold_text=sent))
        used.add(d.doc_type)
    # 비교형 3 — 같은 주제 문서 2건
    cmp_pool = [t for t in pool if t.topic_ in ('price', 'capex', 'inventory')]
    for i in range(3):
        a, b = cmp_pool[i * 2], cmp_pool[i * 2 + 1]
        ka = str(a.title).split('—')[0].strip()
        kb = str(b.title).split('—')[0].strip()
        rows.append(dict(qid=f'G{len(rows) + 1:03d}', question=f'{ka} 와 {kb} 를 비교하면?', q_type='비교',
                         source=a.doc_type, gold_doc_ids=f'{a.doc_id};{b.doc_id}', gold_text=a.sents_[0]))
    # 종합형 2
    for i, t in enumerate(['supply', 'demand']):
        g = [x for x in pool if x.topic_ == t][:2]
        rows.append(dict(qid=f'G{len(rows) + 1:03d}',
                         question=('공급 측 증설 · 감축 동향을 정리하면?' if t == 'supply' else '고객사 발주 동향을 정리하면?'),
                         q_type='종합', source=g[0].doc_type,
                         gold_doc_ids=';'.join(x.doc_id for x in g), gold_text=g[0].sents_[0]))
    # 답없음 3
    for q, memo in NO_ANSWER:
        rows.append(dict(qid=f'G{len(rows) + 1:03d}', question=q, q_type='답없음',
                         source='-', gold_doc_ids='', gold_text=memo))
    out = pd.DataFrame(rows)
    _CACHE['gold'] = out
    return out.copy()
