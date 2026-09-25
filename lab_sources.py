# -*- coding: utf-8 -*-
"""
소스 유형 정의 — **여기 한 곳만 고치면 전부 따라온다**

이 파일이 정하는 것
  · 유형 코드와 한글 이름          → 모든 표 · 도식 · 프롬프트 표기
  · 유형별 필수 메타               → nb00 메타 충족률 점검 기준
  · 유형별 정제 규칙               → nb02 노이즈 제거 · 잔존 점검
  · 유형별 청킹 · 보안 기본값       → 청크 크기 · 보안 등급

사내 적용 순서
  1) SOURCES 에 유형 추가 · 이름 변경 · 사용 안 함 표시
  2) lab_config.DOC_TYPE_MAP 에 **사내 코드 → 여기 코드** 매핑
  3) nb00 [1b] 셀에서 미매핑 코드가 없는지 확인

자주 하는 세 가지
  [추가] 없던 유형을 넣는다
      SOURCES['SNS'] = dict(ko='SNS', group='외부', enabled=True, security=0,
                            required=['org_name'],
                            clean=dict(email=False, repeated=False, noise=[r'^RT\s@\S+']),
                            chunk=dict(size=280, table=False))
      또는  lab_sources.add('SNS', 'SNS', group='외부', required=['org_name'], size=280)
      → 사내 코드가 다르면 lab_config.DOC_TYPE_MAP 에 {'SNS_POST': 'SNS'} 추가

  [수정] 있는 유형의 기준을 바꾼다  (무엇을 바꿔도 모든 점검 · 표기에 즉시 반영)
      SOURCES['NEWS']['ko'] = '뉴스기사'                       # 표기 이름
      SOURCES['NEWS']['required'] = ['org_name', 'src_url']     # 필수 메타
      SOURCES['NEWS']['clean']['noise'] += [r'^\[속보\]']       # 정제 규칙
      SOURCES['NEWS']['chunk'] = dict(size=250, table=False)    # 청킹 기준
      SOURCES['NEWS']['security'] = 1                           # 보안 등급

  [미사용] 쓰지 않는 유형을 뺀다
      SOURCES['MEETING']['enabled'] = False      # 정의는 남기고 판정에서만 제외
      → 다른 유형으로 흡수하려면 DOC_TYPE_MAP 에 {'MOM': 'EMAIL'}

수정 후에는 Spyder 에서 [0] 준비 셀을 다시 실행한다 (reload 포함).
"""

# 공통 필수 메타 — 모든 유형에 적용
COMMON_REQUIRED = ['title', 'published_at']

# =====================================================================
# [사내 맞춤] 소스 유형 정의
#   code      : 표준 코드 (DOC_TYPE_MAP 의 오른쪽 값)
#   ko        : 표기 이름
#   group     : 외부 / 내부  (수집 경로 구분 · 보고용)
#   enabled   : False 면 점검 · 통계에서 제외 (코드는 남겨 둠)
#   security  : 기본 보안 등급 0~3
#   required  : 이 유형에서 반드시 있어야 하는 메타 (COMMON_REQUIRED 에 더해짐)
#   clean     : 정제 옵션  email=인용·서명 제거 / repeated=반복 머리글 제거 / noise=정규식 목록
#   chunk     : 청킹 기본값  size=목표 글자 수 / table=표를 별도 청크로
# =====================================================================
SOURCES = {
 'NEWS': dict(
     ko='뉴스', group='외부', enabled=True, security=0,
     required=['org_name'],
     clean=dict(email=False, repeated=False, noise=[
         r'무단\s*전재.*', r'재배포\s*금지.*', r'저작권자\s*ⓒ.*', r'^관련기사.*', r'^-\s.*',
         r'\S+@\S+\.\S+', r'^\S+\s기자\s*$']),
     chunk=dict(size=500, table=False)),

 'BROKER': dict(
     ko='증권사', group='외부', enabled=True, security=1,
     required=['org_name', 'author'],
     clean=dict(email=False, repeated=True, noise=[
         r'Compliance Notice.*', r'본 자료는 투자 참고용.*', r'당사는 자료 작성일 현재.*',
         r'투자의견\s*(매수|중립|비중확대).*']),
     chunk=dict(size=600, table=True)),

 'INSTITUTION': dict(
     ko='기관', group='외부', enabled=True, security=1,
     required=['org_name'],
     clean=dict(email=False, repeated=True, noise=[r'^목차$', r'.*\.{5,}\s*\d+\s*$']),
     chunk=dict(size=600, table=True)),

 'EMAIL': dict(
     ko='메일', group='내부', enabled=True, security=2,
     required=['author'],
     clean=dict(email=True, repeated=False, noise=[]),
     chunk=dict(size=400, table=False)),

 'MEETING': dict(
     ko='회의록', group='내부', enabled=True, security=2,
     required=['org_name'],
     clean=dict(email=False, repeated=False, noise=[r'^참석\s*:.*', r'^회의명\s*:.*']),
     chunk=dict(size=450, table=False)),

 'REPORT': dict(
     ko='사내 보고서', group='내부', enabled=True, security=2,
     required=['org_name', 'author'],
     clean=dict(email=False, repeated=True, noise=[r'※\s*본 문서는 사내 한정.*']),
     chunk=dict(size=600, table=True)),

 'EXEC_REPORT': dict(
     ko='임원 보고서', group='내부', enabled=True, security=3,
     required=['org_name'],
     clean=dict(email=False, repeated=True, noise=[r'^보고\s*:.*→.*']),
     chunk=dict(size=500, table=True)),

 # ---- 사내에 있으면 주석 해제 · 없으면 그대로 두면 됨 ----
 # 'SNS': dict(
 #     ko='SNS', group='외부', enabled=True, security=0,
 #     required=['org_name'],            # 계정명을 org_name 에 넣는 경우
 #     clean=dict(email=False, repeated=False, noise=[
 #         r'^RT\s@\S+', r'https?://\S+', r'#\S+', r'^\d+\s*(좋아요|리트윗|댓글).*']),
 #     chunk=dict(size=280, table=False)),   # 글이 짧아 원문 1건 = 1청크에 가깝다
}


# ---------------- 조회 도우미 (코드에서 사용) ----------------
def codes(only_enabled=True):
    """표준 코드 목록"""
    return [k for k, v in SOURCES.items() if v.get('enabled', True) or not only_enabled]


def ko_map(only_enabled=False):
    """코드 → 한글 이름"""
    return {k: v['ko'] for k, v in SOURCES.items() if v.get('enabled', True) or not only_enabled}


def ko(code):
    return SOURCES.get(code, {}).get('ko', code)


def group(code):
    return SOURCES.get(code, {}).get('group', '-')


def security(code):
    return SOURCES.get(code, {}).get('security', 0)


def required(code):
    """유형별 필수 메타 = 공통 + 개별"""
    return COMMON_REQUIRED + SOURCES.get(code, {}).get('required', [])


def required_map(only_enabled=True):
    return {c: required(c) for c in codes(only_enabled)}


def noise(code):
    return SOURCES.get(code, {}).get('clean', {}).get('noise', [])


def clean_opts(code):
    d = SOURCES.get(code, {}).get('clean', {})
    return bool(d.get('email')), bool(d.get('repeated'))


def chunk_opts(code):
    d = SOURCES.get(code, {}).get('chunk', {})
    return int(d.get('size', 500)), bool(d.get('table', False))


# ---------------- 편집 도우미 (셀에서 한 줄로 수정) ----------------
def add(code, ko, group='외부', security=0, required=None, noise=None,
        email=False, repeated=False, size=500, table=False, enabled=True):
    """유형 추가 — 예: lab_sources.add('SNS', 'SNS', '외부', noise=[r'^RT\\s@\\S+'])"""
    SOURCES[code] = dict(ko=ko, group=group, enabled=enabled, security=security,
                         required=list(required or []),
                         clean=dict(email=email, repeated=repeated, noise=list(noise or [])),
                         chunk=dict(size=size, table=table))
    return SOURCES[code]


def rename(code, ko_name):
    """표기 이름만 변경 (코드는 유지)"""
    SOURCES[code]['ko'] = ko_name


def disable(code):
    """사용하지 않는 유형 — 점검 · 통계에서 제외"""
    SOURCES[code]['enabled'] = False


def set_required(code, items):
    """필수 메타 교체 — 사내 기준에 맞게"""
    SOURCES[code]['required'] = list(items)


# ---------------- 점검 ----------------
def unmapped(raw, type_map=None):
    """
    사내 코드 중 SOURCES 에 정의되지 않은 것 — **가장 먼저 확인할 항목**
    매핑이 빠지면 그 유형은 필수 메타 · 정제 규칙이 적용되지 않은 채 통과한다.
    """
    import pandas as pd
    if type_map is None:
        import lab_config as C
        type_map = C.DOC_TYPE_MAP
    col = 'doc_type_raw' if 'doc_type_raw' in raw else 'doc_type'
    known = set(SOURCES)
    rows = []
    for t, g in raw.groupby(col):
        std = type_map.get(str(t), str(t))
        rows.append(dict(사내_코드=t, 매핑_결과=std, 건수=len(g),
                         상태=('정상' if std in known and SOURCES[std].get('enabled', True)
                               else ('사용 안 함' if std in known else '미정의')),
                         조치=('-' if std in known and SOURCES[std].get('enabled', True)
                               else (f'SOURCES["{std}"]["enabled"] = True'
                                     if std in known else
                                     f'lab_sources.add("{std}", "<한글명>") 또는 DOC_TYPE_MAP 에 매핑 추가'))))
    return pd.DataFrame(rows).sort_values('건수', ascending=False).reset_index(drop=True)


def table():
    """현재 정의를 표로 — 사내 공유 · 확인용"""
    import pandas as pd
    rows = []
    for c, v in SOURCES.items():
        size, tbl = chunk_opts(c)
        rows.append(dict(코드=c, 이름=v['ko'], 구분=v['group'], 사용=('O' if v.get('enabled', True) else 'X'),
                         보안=v.get('security', 0), 필수_메타=' · '.join(required(c)),
                         정제=' · '.join([x for x, on in (('메일 인용·서명', v['clean'].get('email')),
                                                        ('반복 머리글', v['clean'].get('repeated'))) if on]
                                       + [f'패턴 {len(noise(c))}개'] if (v['clean'].get('email') or v['clean'].get('repeated') or noise(c)) else '-'),
                         청크=f'{size}자' + (' · 표 분리' if tbl else '')))
    return pd.DataFrame(rows)
