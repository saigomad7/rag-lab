# -*- coding: utf-8 -*-
"""
검색 부품 — 토크나이저 · BM25 · RRF · MMR · 임베딩 · 리랭크 · Milvus · 기존 검색 API · LLM 답변
각 부품은 따로 켜고 끌 수 있어 단계별 비교(ablation)에 쓴다.
"""
import re
import math
import hashlib
import os
import pickle
import time
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
        404: '주소 또는 모델 이름이 틀림',
        429: '호출 한도 초과 — 잠시 후 재시도',
        500: '서비스 일시 오류 — 잠시 후 재시도',
        503: '서비스 과부하 — 잠시 후 재시도 (.env 에 LLM_RPM=10 · LLM_RETRY=5)',
    }.get(r.status_code, '응답 본문을 확인')
    body = (r.text or '')[:300].replace('\n', ' ')
    if 'not found' in body.lower() or 'does not exist' in body.lower():
        tip = (f'모델 이름 확인 — .env 의 EMBED_MODEL 이 이 서비스에 없는 이름입니다 (현재 "{model}")\n'
               '         OpenAI: text-embedding-3-small · 구글: text-embedding-004 · 사내 BGE: bge-m3')
    return (f'{what} API 실패 [{r.status_code}] {tip}\n'
            f'  URL   : {url}\n'
            f'  모델   : {model}\n'
            f'  응답   : {body}')


def list_models(kind='embed'):
    """
    지금 키로 쓸 수 있는 모델 이름을 조회한다 — 모델 404 가 날 때 확인용.
      lab_search.list_models()          → 임베딩 모델
      lab_search.list_models('chat')    → 대화 모델
    구글(generativelanguage) · OpenAI 호환 서버 모두 지원.
    """
    import requests
    import pandas as _pd
    url = C.EMBED_URL or C.LLM_URL
    key = C.EMBED_API_KEY if C.EMBED_API_KEY not in ('', 'none') else C.LLM_API_KEY
    if not url:
        return _pd.DataFrame([{'안내': '.env 에 EMBED_URL 또는 LLM_URL 을 먼저 넣으세요'}])
    if 'generativelanguage.googleapis.com' in url:              # 구글 네이티브 목록 API
        r = requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                         params={'key': key}, timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
        if r.status_code >= 400:
            return _pd.DataFrame([{'실패': r.status_code, '응답': (r.text or '')[:200]}])
        rows = []
        for m in r.json().get('models', []):
            meth = ','.join(m.get('supportedGenerationMethods', []))
            ok = ('embedContent' in meth) if kind == 'embed' else ('generateContent' in meth)
            if ok:
                rows.append(dict(모델=m['name'].replace('models/', ''), 지원=meth,
                                 설명=str(m.get('description', ''))[:60]))
        return _pd.DataFrame(rows)
    base = url.rsplit('/', 1)[0]                                 # OpenAI 호환 /v1/models
    r = requests.get(base.rsplit('/embeddings', 1)[0] + '/models',
                     headers={'Authorization': f'Bearer {key}'}, timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
    if r.status_code >= 400:
        return _pd.DataFrame([{'실패': r.status_code, '응답': (r.text or '')[:200]}])
    ids = [d.get('id', '') for d in r.json().get('data', [])]
    key_w = 'embed' if kind == 'embed' else ''
    return _pd.DataFrame([{'모델': i} for i in ids if key_w in i.lower()])


class Embedder:
    """encode(texts) → {'dense': (n, d) 정규화 행렬, 'sparse': [ {token_id: weight}, ... ] 또는 None}"""

    def __init__(self, mode=None, max_length=None):
        self.mode = mode or C.EMBED_MODE
        self.max_length = max_length or C.EMBED_MAX_LENGTH
        self.model = None
        self._cache = None
        self._last_call = 0.0
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

    # ---- 임베딩 캐시 (api 모드) — 같은 문장은 재호출하지 않는다 ----
    def _cache_path(self):
        d = os.path.join(C.OUT_DIR, '_embed_cache')
        os.makedirs(d, exist_ok=True)
        safe = re.sub(r'[^A-Za-z0-9_.-]', '_', f'{C.EMBED_MODEL}')
        return os.path.join(d, f'{safe}.pkl')

    def _cache_load(self):
        if self._cache is not None:
            return self._cache
        self._cache = {}
        if C.EMBED_CACHE:
            try:
                with open(self._cache_path(), 'rb') as f:
                    self._cache = pickle.load(f)
                print(f'  임베딩 캐시 {len(self._cache)} 건 불러옴')
            except Exception:
                pass
        return self._cache

    def _cache_save(self):
        if not C.EMBED_CACHE or not self._cache:
            return
        try:
            with open(self._cache_path(), 'wb') as f:
                pickle.dump(self._cache, f)
        except Exception as ex:
            print('  (임베딩 캐시 저장 생략:', type(ex).__name__, ')')

    def _post(self, batch):
        """임베딩 1회 호출 — 429 는 대기 후 재시도(최대 4회)"""
        import requests
        hdr = {'Authorization': f'Bearer {C.EMBED_API_KEY}'} if C.EMBED_API_KEY not in ('', 'none') else {}
        wait = 20
        for attempt in range(4):
            if C.EMBED_RPM > 0:                       # 분당 요청 수 제한
                gap = 60.0 / C.EMBED_RPM
                since = time.time() - self._last_call
                if since < gap:
                    time.sleep(gap - since)
            r = requests.post(C.EMBED_URL, headers=hdr,
                              json={'model': C.EMBED_MODEL, 'input': batch},
                              timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL)
            self._last_call = time.time()
            if r.status_code == 429 and attempt < 3:
                m = re.search(r'retryDelay["\s:]+(\d+)', r.text or '')
                sec = int(m.group(1)) if m else wait
                print(f'  한도 초과(429) — {sec}초 대기 후 재시도 {attempt + 1}/3')
                time.sleep(sec)
                wait = min(wait * 2, 120)
                continue
            if r.status_code >= 400:
                raise RuntimeError(_api_hint('임베딩', C.EMBED_URL, C.EMBED_MODEL, r))
            return [d['embedding'] for d in r.json()['data']]
        raise RuntimeError('임베딩 API 실패 [429] 재시도 후에도 한도 초과 — '
                           '.env 에 EMBED_RPM=5 · EMBED_BATCH=8 로 낮추거나, 잠시 후 다시 실행하세요')

    def encode(self, texts, batch_size=16):
        texts = list(texts)
        if self.mode == 'local':
            out = self.model.encode(texts, batch_size=batch_size, max_length=self.max_length,
                                    return_dense=True, return_sparse=True)
            dense = np.asarray(out['dense_vecs'], dtype=np.float32)
            sparse = [{int(k): float(v) for k, v in lw.items()} for lw in out['lexical_weights']]
            return {'dense': dense, 'sparse': sparse}
        if self.mode == 'api':
            cache = self._cache_load()
            keys = [hashlib.md5(t.encode('utf-8', 'ignore')).hexdigest() for t in texts]
            todo = [i for i, k in enumerate(keys) if k not in cache]
            bs = min(batch_size, C.EMBED_BATCH)
            if len(todo) > 2:                       # 질의 1~2건은 조용히 처리
                print(f'  임베딩 호출 {len(todo)} 건 (캐시 {len(texts) - len(todo)} 건 재사용) · 배치 {bs}')
            for s0 in range(0, len(todo), bs):
                idx = todo[s0:s0 + bs]
                for j, v in zip(idx, self._post([texts[j] for j in idx])):
                    cache[keys[j]] = np.asarray(v, dtype=np.float32)
            if todo:
                self._cache_save()
            d = np.vstack([cache[k] for k in keys]) if texts else np.zeros((0, 8), dtype=np.float32)
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
        self.D = self.S = None
        if not self.use_milvus and self.chunks is not None:
            enc = self.emb.encode(self.chunks['text'].tolist())
            self.D, self.S = enc['dense'], enc['sparse']
            if self.S is None and 'sparse' in self.parts:      # api 임베딩은 sparse 미지원
                self.parts = [p for p in self.parts if p != 'sparse']
                print("  ! 이 임베딩(api)은 sparse 벡터를 주지 않습니다 → parts 에서 'sparse' 제외"
                      " (BM25 가 그 역할을 대신합니다)")

    COLS = ['chunk_id', 'doc_id', 'text', 'score', 'via']

    @classmethod
    def empty(cls):
        """결과 없음 — 컬럼은 유지한다 (하위 코드가 doc_id 를 찾으므로)"""
        return pd.DataFrame(columns=cls.COLS)

    # --- 단독 검색기 ---
    def _local(self, pairs, via):
        rows = [dict(self.chunks.iloc[i][['chunk_id', 'doc_id', 'text']].to_dict(), score=s, via=via) for i, s in pairs]
        return pd.DataFrame(rows, columns=['chunk_id', 'doc_id', 'text', 'score', 'via'])

    def bm25(self, q, k=50):
        return self._local(self.bm.search(q, k), 'bm25') if self.bm else self.empty()

    def dense(self, q, k=50, expr=''):
        v = self.emb.encode([q])['dense'][0]
        if self.mv:
            return self.mv.dense(v, k, expr)
        s = self.D @ v
        idx = np.argsort(-s)[:k]
        return self._local([(i, float(s[i])) for i in idx], 'dense')

    def sparse(self, q, k=50, expr=''):
        sp = self.emb.encode([q])['sparse']
        if sp is None or self.S is None:            # api 임베딩은 sparse 를 주지 않는다
            return self.empty()
        if self.mv and C.MV['sparse']:
            return self.mv.sparse(sp[0], k, expr)
        s = np.array([sparse_dot(sp[0], d) for d in self.S])
        idx = [i for i in np.argsort(-s)[:k] if s[i] > 0]
        return self._local([(i, float(s[i])) for i in idx], 'sparse')

    # --- 조합 ---
    def search(self, q, mode='hybrid+rerank+mmr', k=10, cand=50, lam=0.7, max_per_doc=3, expr='', rrf_k=60):
        if mode in ('bm25', 'dense', 'sparse'):
            fn = {'bm25': lambda: self.bm25(q, cand), 'dense': lambda: self.dense(q, cand, expr), 'sparse': lambda: self.sparse(q, cand, expr)}[mode]
            r = fn()
            return self._rank(r.head(k)) if len(r) else self.empty()
        lists = {p: getattr(self, p)(q, cand) if p == 'bm25' else getattr(self, p)(q, cand, expr) for p in self.parts}
        lists = {p: d for p, d in lists.items() if d is not None and len(d)}
        if not lists:
            return self.empty()
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


_LLM_LAST = [0.0]          # 마지막 호출 시각 (LLM_RPM 제한용)
RETRY_CODES = (429, 500, 502, 503, 504)


def llm_call(prompt, temperature=0.0):
    """
    LLM 1회 호출 — 과부하(503) · 한도(429) · 일시 오류(5xx)는 대기 후 재시도.
    무료 키는 .env 에 LLM_RPM=10 을 두면 호출 간격을 자동으로 벌린다.
    """
    import requests
    wait = 10
    for attempt in range(max(1, C.LLM_RETRY) + 1):
        if C.LLM_RPM > 0:
            gap = 60.0 / C.LLM_RPM
            since = time.time() - _LLM_LAST[0]
            if since < gap:
                time.sleep(gap - since)
        r = requests.post(C.LLM_URL, headers={'Authorization': f'Bearer {C.LLM_API_KEY}'},
                          timeout=C.HTTP_TIMEOUT, verify=C.VERIFY_SSL,
                          json={'model': C.LLM_MODEL, 'temperature': temperature,
                                'messages': [{'role': 'user', 'content': prompt}]})
        _LLM_LAST[0] = time.time()
        if r.status_code in RETRY_CODES and attempt < C.LLM_RETRY:
            m = re.search(r'retryDelay["\s:]+(\d+)', r.text or '')
            sec = int(m.group(1)) if m else wait
            why = '과부하' if r.status_code >= 500 else '한도 초과'
            print(f'  LLM {why}({r.status_code}) — {sec}초 대기 후 재시도 {attempt + 1}/{C.LLM_RETRY}')
            time.sleep(sec)
            wait = min(wait * 2, 60)
            continue
        if r.status_code >= 400:
            raise RuntimeError(_api_hint('LLM', C.LLM_URL, C.LLM_MODEL, r))
        try:
            return r.json()['choices'][0]['message']['content']
        except Exception:
            raise RuntimeError(f'LLM 응답 형식이 예상과 다릅니다: {(r.text or "")[:200]}')
    raise RuntimeError(f'LLM 호출 실패 — {C.LLM_RETRY}회 재시도 후에도 응답 없음 '
                       f'(.env 에 LLM_RPM=10 · LLM_RETRY=5 로 낮춰 보거나 잠시 후 재실행)')


def llm_answer(question, results, meta=None, n=6, temperature=0.0):
    ctx = build_context(results, meta, n)
    if not C.LLM_URL or (C.IS_SAMPLE and not C.SAMPLE_MODELS):
        return f'(샘플 모드: LLM 미호출) 상위 청크 → {results.iloc[0]["text"][:60] if len(results) else "없음"} …'
    return llm_call(PROMPT.format(context=ctx, question=question), temperature)
