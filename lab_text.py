# -*- coding: utf-8 -*-
"""
텍스트 점검 · 정제 — 소스 유형별 처리(청킹 전)
  - 토큰 수(BGE-M3 토크나이저 있으면 정확, 없으면 근사)
  - 소스별 정제: 뉴스 노이즈 / 증권사 면책 · 반복 머리글 / 메일 인용 · 서명 / 지식문서 UI 문구
  - 점검 지표: 문장 잘림, 표 깨짐 의심, 노이즈 잔존
  - 헤더 생성, 근사 중복(MinHash)
"""
import re
import hashlib
import numpy as np
import pandas as pd
import lab_config as C

# ---------------- 토큰 수 ----------------
_tok = None


def tokenizer():
    """BGE-M3 토크나이저 (transformers + 모델 폴더가 있을 때). 없으면 None."""
    global _tok
    if _tok is None and C.BGE_M3_PATH:
        try:
            from transformers import AutoTokenizer
            _tok = AutoTokenizer.from_pretrained(C.BGE_M3_PATH)
        except Exception as ex:
            print('  토크나이저 로드 실패 → 근사치 사용:', type(ex).__name__)
            _tok = False
    return _tok or None


def count_tokens(text):
    """토큰 수. 토크나이저가 없으면 근사(한글 1자≈0.8토큰, 영숫자 4자≈1토큰)."""
    text = text or ''
    t = tokenizer()
    if t:
        return len(t.encode(text, add_special_tokens=False))
    ko = len(re.findall(r'[가-힣]', text))
    other = len(re.sub(r'[가-힣\s]', '', text))
    return int(ko * 0.8 + other / 4 + 0.5)


# ---------------- 소스별 정제 규칙 ----------------
NOISE = {
    'NEWS': [r'무단\s*전재.*', r'재배포\s*금지.*', r'저작권자\s*ⓒ.*', r'^관련기사.*', r'^-\s.*', r'\S+@\S+\.\S+', r'^\S+\s기자\s*$'],
    'BROKER': [r'Compliance Notice.*', r'본 자료는 투자 참고용.*', r'당사는 자료 작성일 현재.*'],
    'INSTITUTION': [r'^목차$', r'.*\.{5,}\s*\d+\s*$'],
    'KNOWLEDGE': [r'.*이 문서를 편집.*', r'^메뉴\s*\|.*'],
}
EMAIL_CUT = [r'-{3,}\s*Original Message\s*-{3,}', r'^보낸 사람\s*:', r'^From\s*:', r'^-----.*원본 메시지']
EMAIL_SIG = [r'^감사합니다\.?\s*$', r'.*\|\s*0\d{1,2}-\d{3,4}-\d{4}.*', r'.*\S+@\S+\.\S+.*', r'.*드림\s*$']
EMAIL_DISCLAIMER = [r'본 메일은.*', r'This e-?mail.*confidential.*']


def remove_repeated_lines(text, min_repeat=2, max_len=60):
    """여러 번 반복되는 짧은 줄(페이지 머리글 · 바닥글) 제거."""
    lines = text.split('\n')
    cnt = pd.Series([l.strip() for l in lines if l.strip()]).value_counts()
    rep = set(cnt[(cnt >= min_repeat) & (cnt.index.str.len() <= max_len)].index)
    return '\n'.join(l for l in lines if l.strip() not in rep)


def clean_email(text):
    """인용(이전 메일) 이후 삭제 → '>' 인용 줄 삭제 → 서명 · 면책 삭제."""
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if any(re.search(p, l.strip()) for p in EMAIL_CUT):
            lines = lines[:i]
            break
    lines = [l for l in lines if not l.lstrip().startswith('>')]
    out = []
    for l in lines:
        s = l.strip()
        if any(re.match(p, s) for p in EMAIL_SIG + EMAIL_DISCLAIMER):
            continue
        out.append(l)
    return '\n'.join(out).strip()


def clean(text, doc_type):
    """소스 유형별 정제. 규칙이 없는 유형은 공백 정리만."""
    text = text or ''
    if doc_type == 'EMAIL':
        text = clean_email(text)
    if doc_type in ('BROKER', 'INSTITUTION', 'ENG_REPORT'):
        text = remove_repeated_lines(text)
    for p in NOISE.get(doc_type, []):
        text = re.sub(p, '', text, flags=re.M)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------- 점검 지표 ----------------
_END = re.compile(r'([.!?。…]|다|요|음|함|임|됨|중|것|\)|\]|%|원|EB|달러)\s*$')


def ends_mid_sentence(chunk):
    """청크가 문장 중간에서 끝났는지 (마지막 글자가 종결 표현이 아니면 True)."""
    s = (chunk or '').rstrip()
    return bool(s) and not _END.search(s)


def table_suspect(text):
    """구분자 없는 표 의심: 숫자 · %가 2개 이상인 짧은 줄이 3줄 이상 연속하고 '|' 표기가 없음."""
    run = best = 0
    for l in (text or '').split('\n'):
        nums = re.findall(r'\d+(?:\.\d+)?%?', l)
        if len(nums) >= 2 and len(l) < 60 and '|' not in l:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best >= 3


def noise_left(text, doc_type):
    """정제 규칙에 걸리는 문구가 남아 있는지 (정제 전 점검)."""
    pats = NOISE.get(doc_type, []) + (EMAIL_CUT + EMAIL_DISCLAIMER if doc_type == 'EMAIL' else [])
    return any(re.search(p, text or '', flags=re.M) for p in pats)


def has_header(chunk, title=None):
    """청크 텍스트에 제목 · 날짜가 들어 있는지 (헤더 부착 여부)."""
    s = (chunk or '')[:120]
    date = bool(re.search(r'20\d\d[-./]\d{1,2}', s))
    ttl = bool(title) and str(title)[:8] in s
    return date or ttl


def build_header(row):
    """[유형 | 날짜 | 기관 | 제목 | 섹션] — 청크 앞에 붙일 문맥 헤더."""
    d = row.get('published_at')
    d = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') and not pd.isna(d) else '날짜미상'
    parts = [C.DOC_TYPE_KO.get(row.get('doc_type'), row.get('doc_type')), d, row.get('org_name') or '', row.get('title') or '']
    if row.get('section'):
        parts.append(row['section'])
    return '[' + ' | '.join(str(p) for p in parts if p) + ']'


# ---------------- 근사 중복 (MinHash, 의존성 없음) ----------------
def _shingles(text, k=5):
    t = re.sub(r'\s+', ' ', text or '')
    return {t[i:i + k] for i in range(max(1, len(t) - k + 1))}


def minhash_sig(text, n_perm=64, seed=1):
    sh = _shingles(text)
    rng = np.random.RandomState(seed)
    a = rng.randint(1, 2**31 - 1, n_perm, dtype=np.int64)
    b = rng.randint(0, 2**31 - 1, n_perm, dtype=np.int64)
    h = np.array([int(hashlib.md5(s.encode()).hexdigest()[:8], 16) for s in sh], dtype=np.int64)
    return ((np.outer(h, a) + b) % (2**31 - 1)).min(axis=0)


def near_duplicates(df, text_col='body', id_col='doc_id', threshold=0.8, bands=16):
    """MinHash + LSH 로 근사 중복 쌍 찾기. 수만 건까지 가볍게 돈다."""
    sigs = {r[id_col]: minhash_sig(r[text_col]) for _, r in df.iterrows()}
    rows = len(next(iter(sigs.values()))) // bands
    buckets = {}
    for i, s in sigs.items():
        for bnd in range(bands):
            buckets.setdefault((bnd, tuple(s[bnd * rows:(bnd + 1) * rows])), []).append(i)
    cand = {tuple(sorted((x, y))) for ids in buckets.values() for xi, x in enumerate(ids) for y in ids[xi + 1:]}
    out = [(x, y, float((sigs[x] == sigs[y]).mean())) for x, y in cand]
    res = pd.DataFrame(out, columns=['id_a', 'id_b', 'similarity'])
    return res[res.similarity >= threshold].sort_values('similarity', ascending=False).reset_index(drop=True)
