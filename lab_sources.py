# -*- coding: utf-8 -*-
"""
소스 유형 정의 — 아래 SOURCES 딕셔너리가 전부다.

한 줄이 한 카테고리다. 넣으면 생기고, 지우면 없어지고, 고치면 바뀐다.

    'NEWS': dict(ko='뉴스', alias=['뉴스', 'NEWS_EN'], ...)
      │            │              └ 사내 DB 에 들어 있는 값들 (여러 개 가능)
      │            └ 표에 찍힐 이름
      └ 이 카테고리를 부를 코드

  [추가]  항목을 하나 넣는다        'SNS': dict(ko='SNS', alias=['SNS', 'SNS_POST'])
  [제거]  항목을 지운다             'MEETING': ... 줄 삭제 → 그 유형은 점검 대상에서 빠진다
  [수정]  이름 · 별칭을 고친다       ko='증권사' → '리서치'  /  alias 목록에 코드 추가 · 삭제

alias 를 안 적으면 키와 같은 값이 DB 에 있다고 본다 ('NEWS' → 'NEWS').
두 코드를 한 카테고리로 합치려면 그 카테고리의 alias 에 둘 다 적는다.

여기서 정한 값이 모든 점검 · 표기에 그대로 쓰인다
  ko       표기 이름          → 모든 표 · 도식 · 프롬프트
  alias    사내 DB 의 DOC_TYPE 값 목록 (생략하면 키와 동일)
  required 필수 메타          → nb00 메타 충족률 기준 (title · published_at 은 공통이라 자동)
  noise    정제할 정규식       → nb02 노이즈 제거 · 잔존 점검
  chunk    청크 목표 글자 수    → nb02 청킹 기준 비교
  table    표를 별도 청크로     → 표가 많은 유형(증권사 · 보고서)
  strip_email   메일 인용 · 서명 제거
  strip_repeat  반복 머리글 · 바닥글 제거
  group    외부 / 내부        → 보고용 구분
  security 보안 등급 0~3

적을 것이 없으면 생략해도 된다.  예:  'SNS': dict(ko='SNS')

수정 후 Spyder 에서 [0] 준비 셀을 다시 실행하면 반영된다.
"""

COMMON_REQUIRED = ['title', 'published_at']      # 모든 유형 공통

# =====================================================================
# 쓰는 유형만 남긴다 — 안 쓰면 줄을 지우고, 새로 생기면 한 항목 추가.
# 키 = 사내 DB 의 DOC_TYPE 값 · ko = 화면 · 보고서에 찍힐 이름
# =====================================================================
SOURCES = {
 'NEWS': dict(
     alias=['NEWS'], ko='뉴스', group='외부', security=0,
     required=['org_name'],
     noise=[r'무단\s*전재.*', r'재배포\s*금지.*', r'저작권자\s*ⓒ.*', r'^관련기사.*', r'^-\s.*',
            r'\S+@\S+\.\S+', r'^\S+\s기자\s*$'],
     chunk=500),

 'BROKER': dict(
     alias=['BROKER'], ko='증권사', group='외부', security=1,
     required=['org_name', 'author'],
     noise=[r'Compliance Notice.*', r'본 자료는 투자 참고용.*', r'당사는 자료 작성일 현재.*',
            r'투자의견\s*(매수|중립|비중확대).*'],
     chunk=600, table=True, strip_repeat=True),

 'INSTITUTION': dict(
     alias=['INSTITUTION'], ko='기관', group='외부', security=1,
     required=['org_name'],
     noise=[r'^목차$', r'.*\.{5,}\s*\d+\s*$'],
     chunk=600, table=True, strip_repeat=True),

 'EMAIL': dict(
     alias=['EMAIL'], ko='메일', group='내부', security=2,
     required=['author'],
     chunk=400, strip_email=True),

 'MEETING': dict(
     alias=['MEETING'], ko='회의록', group='내부', security=2,
     required=['org_name'],
     noise=[r'^참석\s*:.*', r'^회의명\s*:.*'],
     chunk=450),

 'REPORT': dict(
     alias=['REPORT'], ko='사내 보고서', group='내부', security=2,
     required=['org_name', 'author'],
     noise=[r'※\s*본 문서는 사내 한정.*'],
     chunk=600, table=True, strip_repeat=True),

 'EXEC_REPORT': dict(
     alias=['EXEC_REPORT'], ko='임원 보고서', group='내부', security=3,
     required=['org_name'],
     noise=[r'^보고\s*:.*→.*'],
     chunk=500, table=True, strip_repeat=True),

 # ---- [추가] 예시 — 주석만 풀면 바로 쓰인다 ----
 # 'SNS': dict(alias=['SNS', 'SNS_POST'], ko='SNS', group='외부', required=['org_name'],
 #             noise=[r'^RT\s@\S+', r'https?://\S+', r'#\S+'], chunk=280),
 # 최소 형태:  'SNS': dict(ko='SNS'),
}



# ---------------- 아래는 읽기용 — 고칠 일 없음 ----------------
def codes():
    return list(SOURCES)


def ko_map():
    return {c: v.get('ko', c) for c, v in SOURCES.items()}


def ko(code):
    return SOURCES.get(code, {}).get('ko', code)


def group(code):
    return SOURCES.get(code, {}).get('group', '-')


def security(code):
    return SOURCES.get(code, {}).get('security', 0)


def required(code):
    return COMMON_REQUIRED + list(SOURCES.get(code, {}).get('required', []))


def required_map():
    return {c: required(c) for c in SOURCES}


def noise(code):
    return list(SOURCES.get(code, {}).get('noise', []))


def clean_opts(code):
    v = SOURCES.get(code, {})
    return bool(v.get('strip_email')), bool(v.get('strip_repeat'))


def chunk_opts(code):
    v = SOURCES.get(code, {})
    return int(v.get('chunk', 500)), bool(v.get('table'))


def aliases(code):
    """이 카테고리를 가리키는 사내 DB 값들 (생략 시 키 자신)"""
    return list(SOURCES.get(code, {}).get('alias') or [code])


def type_map():
    """사내 DB 값 → 카테고리 코드"""
    m = {}
    for c in SOURCES:
        m[c] = c
        for a in aliases(c):
            m[str(a)] = c
    return m


def unmapped(raw):
    """
    데이터에 있는 사내 코드가 SOURCES 에 있는지 확인 — 없으면 기준이 적용되지 않은 채 통과한다.
    """
    import pandas as pd
    m = type_map()
    col = 'doc_type_raw' if 'doc_type_raw' in raw else 'doc_type'
    rows = []
    for t, g in raw.groupby(col):
        std = m.get(str(t), str(t))
        ok = std in SOURCES
        rows.append(dict(사내_코드=t, 유형=std, 건수=len(g), 상태=('정상' if ok else '정의 없음'),
                         조치=('-' if ok else
                               f"SOURCES 에 '{t}' 항목을 추가하거나, 쓸 카테고리의 alias 에 '{t}' 를 넣는다")))
    return pd.DataFrame(rows).sort_values('건수', ascending=False).reset_index(drop=True)


def table():
    """현재 정의 — 확인 · 공유용"""
    import pandas as pd
    rows = []
    for c, v in SOURCES.items():
        size, tbl = chunk_opts(c)
        cl = [x for x, on in (('메일 정제', v.get('strip_email')), ('반복 머리글', v.get('strip_repeat'))) if on]
        cl += [f'정규식 {len(noise(c))}'] if noise(c) else []
        rows.append(dict(코드=c, 이름=v.get('ko', c), 사내_DB_값=' · '.join(str(a) for a in aliases(c)),
                         구분=v.get('group', '-'), 보안=v.get('security', 0),
                         필수_메타=' · '.join(required(c)), 정제=' · '.join(cl) or '-',
                         청크=f'{size}자' + (' · 표 분리' if tbl else '')))
    return pd.DataFrame(rows)
