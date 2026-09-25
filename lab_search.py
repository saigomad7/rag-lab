# -*- coding: utf-8 -*-
"""
검색 부품 — 토크나이저 · BM25 · RRF · MMR · 임베딩 · 리랭크 · Milvus · 기존 검색 API · LLM 답변
각 부품은 따로 켜고 끌 수 있어 단계별 비교(ablation)에 쓴다.
"""
import re
import math
import hashlib
import json
import numpy as np
import pandas as pd
import lab_config as C

# ======================= 토크나이저 =======================
_JOSA = r'(으로부터|에서부터|이라고|에게서|으로서|으로써|에서|에게|께서|부터|까지|마저|조차|처럼|보다|이나|이며|이고|으로|하고|의|는|은|이|가|을|를|에|로|와|과|도|만|나|랑|며)$'
_kiwi = None
_kiwi_ok = None


def tok_space(text):
    """공백 분리 (조사가 붙은 채로 색인됨 — 현행 점검용 기준선)."""
    return re.findall(r'[\w%.]+', (text or '').lower())


def tok_josa(text):
    """공백 분리 + 흔한 조사 제거 (Kiwi 없을 때의 근사)."""
    out = []
    for t in tok_space(text):
        if len(t) > 2 and re.search(r'[가-힣]$', t):
            t = re.sub(_JOSA, '', t)
        out.append(t)
    return out


def tok_kiwi(text):
    """Kiwi 형태소 분석: 명사 · 동사/형용사 어간 · 외국어 · 숫자만 남김."""
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    keep = ('NN', 'NP', 'NR', 'VV', 'VA', 'SL', 'SN', 'SH', 'XR')
    return [t.form.lower() for t in _kiwi.tokenize(text or '') if t.tag.startswith(keep)]


def get_tokenizer(name):
    """'space' | 'josa' | 'kiwi' (kiwi 없으면 josa로 대체하고 알린다)."""
    global _kiwi_ok
    if name == 'kiwi':
        if _kiwi_ok is None:
            try:
                tok_kiwi('테스트'); _kiwi_ok = True
            except Exception:
                _kiwi_ok = False
                print('  kiwipiepy 없음 → josa 근사로 대체 (kiwi 열은 josa 결과)')
        return tok_kiwi if _kiwi_ok else tok_josa
    return {'space': tok_space, 'josa': tok_josa}[name]


# ======================= BM25 =======================
class BM25:
    """외부 의존성 없는 BM25 (역색인). 수십만 청크까지 메모리 안에서 돈다."""

    def __init__(self, tokenize=tok_space, k1=1.5, b=0.75):
        self.tok, self.k1, self.b = tokenize, k1, b

    def fit(self, texts):
        self.N = len(texts)
        self.lens = np.zeros(self.N)
        self.inv = {}
        for i, t in enumerate(texts):
            toks = self.tok(t)
            self.lens[i] = len(toks)
            tf = {}
            for w in toks:
                tf[w] = tf.get(w, 0) + 1
            for w, c in tf.items():
                self.inv.setdefault(w, []).append((i, c))
        self.avg = self.lens.mean() if self.N else 0
        self.idf = {w: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5)) for w, p in self.inv.items()}
        return self

    def search(self, query, k=10):
        sc = {}
        for w in set(self.tok(query)):
            for i, c in self.inv.get(w, []):
                denom = c + self.k1 * (1 - self.b + self.b * self.lens[i] / (self.avg or 1))
                sc[i] = sc.get(i, 0) + self.idf[w] * c * (self.k1 + 1) / denom
        return sorted(sc.items(), key=lambda x: -x[1])[:k]


# ======================= 결합 · 다양성 =======================
def rrf(ranked_lists, k=60, weights=None):
    """Reciprocal Rank Fusion. ranked_lists: [[id, id, ...], ...] → [(id, score)] 내림차순."""
    weights = weights or [1.0] * len(ranked_lists)
    sc = {}
    for lst, w in zip(ranked_lists, weights):
        for r, i in enumerate(lst):
            sc[i] = sc.get(i, 0) + w / (k + r + 1)
    return sorted(sc.items(), key=lambda x: -x[1])


def _jaccard_matrix(texts, k=4):
    sh = [{t[i:i + k] for i in range(max(1, len(t) - k + 1))} for t in texts]
    n = len(sh)
    m = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            v = len(sh[i] & sh[j]) / (len(sh[i] | sh[j]) or 1)
            m[i, j] = m[j, i] = v
    return m


def mmr(rel_scores, sim, lam=0.7, top_n=8):
    """Maximal Marginal Relevance. rel_scores: 관련도(리랭크 점수), sim: 후보 간 유사도 행렬 → 선택 인덱스 목록.
    lam=1 이면 관련도만, 낮을수록 다양성 우선."""
    rel = np.asarray(rel_scores, dtype=float)
    if rel.max() > rel.min():
        rel = (rel - rel.min()) / (rel.max() - rel.min())
    chosen, rest = [], list(range(len(rel)))
    while rest and len(chosen) < top_n:
        best = max(rest, key=lambda i: lam * rel[i] - (1 - lam) * (max(sim[i][j] for j in chosen) if chosen else 0))
        chosen.append(best)
        rest.remove(best)
    return chosen


def cap_per_doc(df, max_per_doc=3):
    """문서당 청크 수 상한."""
    return df.groupby('doc_id', sort=False).head(max_per_doc).reset_index(drop=True)


# ======================= 임베딩 =======================
def _fp16():
    """GPU가 있을 때만 fp16. Windows CPU 환경에서 fp16 강제는 오류·저속의 원인."""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def _hash_vec(text, dim=256):
    """샘플 모드용 가짜 임베딩(토큰 + 글자 3-gram 해시). 의미가 아니라 표면 유사도라는 점에 주의."""
    v = np.zeros(dim)
    t = (text or '').lower()
    feats = tok_josa(t) + [t[i:i + 3] for i in range(max(0, len(t) - 2))]
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest()[:8], 16)
        v[h % dim] += 1 if (h >> 8) & 1 else -1
    n = np.linalg.norm(v)
    return v / n if n else v


def _api_hint(what, url, model, r):
    """API 호출 실패 시 원인과 조치를 한 번에 보여 준다."""
    tip = {
        400: '요청 형식 · 모델 이름 확인',
        401: 'API 키가 없거나 잘못됨 — .env 의 LLM_API_KEY (또는 EMBED_API_KEY) 확인',
        403: '키 권한 · 지역 제한 확인',
        404: '주소가 틀림 — 끝까지 적었는지 확인 (예: .../v1/embeddings, .../v1beta/openai/embeddings)',
        429: '호출 한도 초과 — 잠시 후 재시도',
    }.get(r.status_code, '응답 본문을 확인')
    body = (r.text or '')[:300].replace('\n', ' ')
    return (f'{what} API 실패 [{r.status_code}] {tip}\n'
            f'  URL   : {url}\n'
            f'  모델   : {model}\n'
            f'  응답   : {body}')


class Embedder:
    """encode(texts) → {'dense': (n, d) 정규화 행렬, 'sparse': [ {token_id: weight}, ... ] 또는 None}"""

    def __init__(self, mode=None, max_length=None):
        self.mode = mode or C.EMBED_MODE
        self.max_length = max_length or C.EMBED_MAX_LENGTH
        self.model = None
        if self.mode == 'local':
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError:
                print('  ! FlagEmbedding 미설치 → 임베딩을 sample 로 대체합니다.\n'
                      '    실제 임베딩을 쓰려면 .env 에  EMBED_MODE=api  + EMBED_URL · LLM_API_KEY 를 넣거나,\n'
                      '    로컬 모델을 쓰려면  pip install FlagEmbedding  후 BGE_M3_PATH 를 지정하세요.')
                self.mode = 'sample'
                return
            self.model = BGEM3FlagModel(C.BGE_M3_PATH, use_fp16=_fp16())

    def encode(self, texts, batch_size=16):
        texts = list(texts)
        if self.mode == 'local':
            out = self.model.encode(texts, batch_size=batch_size, max_length=self.max_length,
                                    return_dense=True, return_sparse=True)
            dense = np.asarray(out['dense_vecs'], dtype=np.float32)
            sparse = [{int(k): float(v) for k, v in lw.items()} for lw in out['lexical_weights']]
            return {'dense': dense, 'sparse': sparse}
        if self.mode == 'api':
            import requests
            hdr = {'Authorization': f'Bearer {C.EMBED_API_KEY}'} if C.EMBED_API_KEY not in ('', 'none') else {}
            vecs = []
            for i in range(0, len(texts), batch_size):
                r = requests.post(C.EMBED_URL, headers=hdr,
                                  json={'model': C.EMBED_MODEL, 'input': texts[i:i + batch_size]},
                                  timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
                if r.status_code >= 400:
                    raise RuntimeError(_api_hint('임베딩', C.EMBED_URL, C.EMBED_MODEL, r))
                vecs += [d['embedding'] for d in r.json()['data']]
            d = np.asarray(vecs, dtype=np.float32)
            return {'dense': d / np.linalg.norm(d, axis=1, keepdims=True), 'sparse': None}
        # sample
        dense = np.vstack([_hash_vec(t) for t in texts]) if texts else np.zeros((0, 256))
        sparse = []
        for t in texts:
            tf = {}
            for w in tok_josa(t):
                h = int(hashlib.md5(w.encode()).hexdigest()[:6], 16)
                tf[h] = tf.get(h, 0) + 1.0
            sparse.append(tf)
        return {'dense': dense, 'sparse': sparse}


def sparse_dot(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


# ======================= 리랭커 =======================
class Reranker:
    def __init__(self, mode=None):
        self.mode = mode or C.RERANK_MODE
        self.model = None
        if self.mode == 'local':
            try:
                from FlagEmbedding import FlagReranker
            except ImportError:
                print('  ! FlagEmbedding 미설치 → 리랭커를 sample 로 대체합니다. (.env 의 RERANK_MODE 확인)')
                self.mode = 'sample'
                return
            self.model = FlagReranker(C.RERANK_PATH, use_fp16=_fp16())

    def score(self, query, texts, batch_size=16):
        """관련도 점수 목록. mode=none 이면 None (순서 유지)."""
        texts = list(texts)
        if not texts or self.mode == 'none':
            return None
        if self.mode == 'local':
            s = self.model.compute_score([[query, t] for t in texts], batch_size=batch_size, normalize=True)
            return list(s) if isinstance(s, (list, tuple)) else [s]
        if self.mode == 'api':
            import requests
            hdr = {'Authorization': f'Bearer {C.RERANK_API_KEY}'} if C.RERANK_API_KEY not in ('', 'none') else {}
            r = requests.post(C.RERANK_URL, headers=hdr,
                              json={'query': query, 'documents': texts, 'texts': texts},
                              timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
            if r.status_code >= 400:
                raise RuntimeError(_api_hint('리랭커', C.RERANK_URL, '', r))
            js = r.json()
            items = js.get('results', js) if isinstance(js, dict) else js
            out = [0.0] * len(texts)
            for it in items:
                out[it['index']] = it.get('relevance_score', it.get('score', 0.0))
            return out
        # sample: 질의 토큰이 청크에 얼마나 들어 있나
        q = set(tok_josa(query))
        return [len(q & set(tok_josa(t))) / (len(q) or 1) for t in texts]


# ======================= Milvus =======================
class MilvusSearcher:
    def __init__(self):
        from pymilvus import MilvusClient
        self.cli = MilvusClient(uri=C.MILVUS_URI, token=C.MILVUS_TOKEN or None)
        self.col = C.MILVUS_COLLECTION
        self.out_fields = [f for f in (C.MV['pk'], C.MV['doc_id'], C.MV['text'], C.MV['doc_type'], C.MV['published_at']) if f]

    def describe(self):
        """스키마 · 인덱스 · 건수 → (fields_df, indexes_df, row_count)."""
        d = self.cli.describe_collection(self.col)
        fields = pd.DataFrame([{'name': f['name'], 'type': str(f['type']), 'params': json.dumps(f.get('params', {}), ensure_ascii=False),
                                'is_primary': f.get('is_primary', False)} for f in d['fields']])
        idx = []
        for name in self.cli.list_indexes(self.col):
            info = self.cli.describe_index(self.col, name)
            idx.append({'index_name': name, **{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v) for k, v in info.items()}})
        cnt = self.cli.get_collection_stats(self.col).get('row_count')
        return fields, pd.DataFrame(idx), cnt

    def _hits(self, res, via):
        rows = []
        for r, h in enumerate(res[0]):
            e = h.get('entity', {})
            rows.append({'chunk_id': h.get('id', e.get(C.MV['pk'])), 'doc_id': e.get(C.MV['doc_id']),
                         'text': e.get(C.MV['text'], ''), 'doc_type': e.get(C.MV['doc_type']) if C.MV['doc_type'] else None,
                         'score': h.get('distance'), 'via': via})
        return pd.DataFrame(rows)

    def dense(self, vec, k=50, expr=''):
        res = self.cli.search(self.col, data=[list(map(float, vec))], anns_field=C.MV['dense'], limit=k,
                              filter=expr or '', output_fields=self.out_fields)
        return self._hits(res, 'dense')

    def sparse(self, sp, k=50, expr=''):
        res = self.cli.search(self.col, data=[sp], anns_field=C.MV['sparse'], limit=k,
                              filter=expr or '', output_fields=self.out_fields)
        return self._hits(res, 'sparse')


# ======================= 통합 검색기 (단계별 on/off) =======================
MODES = ['bm25', 'dense', 'sparse', 'hybrid', 'hybrid+rerank', 'hybrid+rerank+mmr']


class Retriever:
    """
    search(q, mode) 로 단계별 비교.
      bm25 / dense / sparse : 단독
      hybrid                : 켜진 검색기들을 RRF로 결합
      +rerank               : 후보(cand)개를 리랭크
      +mmr                  : 리랭크 뒤 MMR(λ) + 문서당 상한
    sample 모드: 모든 검색을 메모리에서. live 모드: dense/sparse = Milvus, bm25 = 적재한 청크(corpus)에서.
    """

    def __init__(self, chunks=None, bm25_tokenizer='kiwi', parts=('bm25', 'dense', 'sparse'),
                 embedder=None, reranker=None, use_milvus=None):
        self.chunks = chunks.reset_index(drop=True) if chunks is not None else None
        self.parts = list(parts)
        self.emb = embedder or Embedder()
        self.rr = reranker or Reranker()
        self.use_milvus = (not C.IS_SAMPLE) if use_milvus is None else use_milvus
        self.mv = MilvusSearcher() if self.use_milvus else None
        self.bm = None
        if self.chunks is not None and 'bm25' in self.parts:
            self.bm = BM25(get_tokenizer(bm25_tokenizer)).fit(self.chunks['text'].tolist())
        if not self.use_milvus and self.chunks is not None:
            enc = self.emb.encode(self.chunks['text'].tolist())
            self.D, self.S = enc['dense'], enc['sparse']

    # --- 단독 검색기 ---
    def _local(self, pairs, via):
        rows = [dict(self.chunks.iloc[i][['chunk_id', 'doc_id', 'text']].to_dict(), score=s, via=via) for i, s in pairs]
        return pd.DataFrame(rows, columns=['chunk_id', 'doc_id', 'text', 'score', 'via'])

    def bm25(self, q, k=50):
        return self._local(self.bm.search(q, k), 'bm25') if self.bm else pd.DataFrame()

    def dense(self, q, k=50, expr=''):
        v = self.emb.encode([q])['dense'][0]
        if self.mv:
            return self.mv.dense(v, k, expr)
        s = self.D @ v
        idx = np.argsort(-s)[:k]
        return self._local([(i, float(s[i])) for i in idx], 'dense')

    def sparse(self, q, k=50, expr=''):
        sp = self.emb.encode([q])['sparse']
        if sp is None:
            return pd.DataFrame()
        if self.mv and C.MV['sparse']:
            return self.mv.sparse(sp[0], k, expr)
        s = np.array([sparse_dot(sp[0], d) for d in self.S])
        idx = [i for i in np.argsort(-s)[:k] if s[i] > 0]
        return self._local([(i, float(s[i])) for i in idx], 'sparse')

    # --- 조합 ---
    def search(self, q, mode='hybrid+rerank+mmr', k=10, cand=50, lam=0.7, max_per_doc=3, expr='', rrf_k=60):
        if mode in ('bm25', 'dense', 'sparse'):
            fn = {'bm25': lambda: self.bm25(q, cand), 'dense': lambda: self.dense(q, cand, expr), 'sparse': lambda: self.sparse(q, cand, expr)}[mode]
            return self._rank(fn().head(k))
        lists = {p: getattr(self, p)(q, cand) if p == 'bm25' else getattr(self, p)(q, cand, expr) for p in self.parts}
        lists = {p: d for p, d in lists.items() if d is not None and len(d)}
        pool = pd.concat(lists.values(), ignore_index=True).drop_duplicates('chunk_id').set_index('chunk_id')
        fused = rrf([d['chunk_id'].tolist() for d in lists.values()], k=rrf_k)[:cand]
        res = pool.loc[[i for i, _ in fused]].reset_index()
        res['score'] = [s for _, s in fused]
        res['via'] = 'rrf(' + '+'.join(lists) + ')'
        if 'rerank' in mode:
            sc = self.rr.score(q, res['text'].tolist())
            if sc is not None:
                res['rerank'] = sc
                res = res.sort_values('rerank', ascending=False).reset_index(drop=True)
        if 'mmr' in mode and len(res) > 1:
            rel = res['rerank'] if 'rerank' in res else res['score']
            sel = mmr(rel.tolist(), _jaccard_matrix(res['text'].tolist()), lam=lam, top_n=min(len(res), k * 2))
            res = cap_per_doc(res.iloc[sel].reset_index(drop=True), max_per_doc)
        return self._rank(res.head(k))

    @staticmethod
    def _rank(df):
        df = df.reset_index(drop=True)
        df.insert(0, 'rank', range(1, len(df) + 1))
        return df


# ======================= 기존 사내 검색 API =======================
def _dig(js, path):
    for p in path.split('.'):
        js = js[p]
    return js


def api_search(q, k=10):
    """기존 시스템 그대로 검색 → (결과 DataFrame, 답변 or None). 요청 · 응답 모양은 lab_config.SEARCH_API."""
    import requests
    m = C.SEARCH_API
    h = {'Authorization': f'Bearer {C.SEARCH_API_TOKEN}'} if C.SEARCH_API_TOKEN else {}
    r = requests.post(C.SEARCH_API_URL, json=m['request'](q, k), headers=h, timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
    r.raise_for_status()
    js = r.json()
    items = _dig(js, m['results_key'])
    rows = [{std: it.get(src) for std, src in m['fields'].items()} for it in items]
    df = Retriever._rank(pd.DataFrame(rows))
    ans = _dig(js, m['answer_key']) if m.get('answer_key') and m['answer_key'] in json.dumps(js) else None
    return df, ans


# ======================= 사내 LLM 답변 =======================
PROMPT = """아래 [자료]만 근거로 질문에 답하세요.
규칙:
1. 문장마다 근거 자료 번호를 [1]처럼 붙인다.
2. 자료에 근거가 없으면 "확인된 자료 없음"이라고만 답한다. 추측하지 않는다.
3. 자료끼리 시점이나 수치가 다르면 둘 다 날짜와 함께 제시한다.

[자료]
{context}

[질문] {question}
[답변]"""


def build_context(results, meta=None, n=6):
    """청크에 [번호 | 유형 | 기관 | 날짜] 라벨을 붙여 컨텍스트 생성. meta: doc_id → (유형, 기관, 날짜) DataFrame."""
    lines = []
    for i, r in enumerate(results.head(n).itertuples(), 1):
        lab = ''
        if meta is not None and r.doc_id in meta.index:
            m = meta.loc[r.doc_id]
            d = m.get('published_at')
            d = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') and not pd.isna(d) else '날짜미상'
            lab = f" | {C.DOC_TYPE_KO.get(m.get('doc_type'), m.get('doc_type'))} | {m.get('org_name') or ''} | {d}"
        lines.append(f'[{i}{lab}]\n{r.text}')
    return '\n\n'.join(lines)


def llm_answer(question, results, meta=None, n=6, temperature=0.0):
    ctx = build_context(results, meta, n)
    if not C.LLM_URL or (C.IS_SAMPLE and not C.SAMPLE_MODELS):
        return f'(샘플 모드: LLM 미호출) 상위 청크 → {results.iloc[0]["text"][:60] if len(results) else "없음"} …'
    import requests
    r = requests.post(C.LLM_URL, headers={'Authorization': f'Bearer {C.LLM_API_KEY}'}, timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL,
                      json={'model': C.LLM_MODEL, 'temperature': temperature,
                            'messages': [{'role': 'user', 'content': PROMPT.format(context=ctx, question=question)}]})
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']
