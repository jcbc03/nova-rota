import json
from pathlib import Path
import numpy as np

def read_file(path):
    p = Path(path); ext = p.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return [(i + 1, (pg.extract_text() or "")) for i, pg in enumerate(PdfReader(str(p)).pages)]
    if ext == ".docx":
        import docx
        return [(None, "\n".join(par.text for par in docx.Document(str(p)).paragraphs))]
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return [(None, p.read_text(encoding=enc))]
        except UnicodeDecodeError:
            continue
    return [(None, p.read_bytes().decode("utf-8", "replace"))]

def chunk_text(text, size=800, overlap=150):
    text = " ".join(text.split())
    if not text:
        return []
    if overlap >= size:
        overlap = size // 4
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            sp = text.rfind(" ", start + size // 2, end)
            if sp > start:
                end = sp
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in out if c]

# ---------------------------------------------------------------------------
# Armazenamento vetorial local (CPU, sem servidor).
# Backend preferido: FAISS (faiss-cpu, wheels prontos p/ Windows, sem compilar).
# Se faiss não estiver instalado, cai para numpy (mesmo formato de metadados).
# Arquivos na pasta: meta.json (+ ids), index.faiss (faiss) ou vecs.npy (numpy),
# manifest.json (backend, dimensão, versão).
# ---------------------------------------------------------------------------
try:  # dependência opcional
    import faiss  # type: ignore
except Exception:  # pragma: no cover - depende do ambiente
    faiss = None

FORMAT_VERSION = 2


def default_folder():
    """Pasta do índice: config['rag_dir'] (padrão C:\\IA\\dados\\rag, env IA_OFF_RAG_DIR)."""
    from . import config
    return Path(config.load().get("rag_dir") or (config.APP_DIR / "rag"))


class VectorStore:
    """API compatível com a v2: meta, add, remove_source, sources, clear, search, save, load."""

    def __init__(self, folder=None, use_faiss=None):
        self.folder = Path(folder) if folder else default_folder()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.use_faiss = (faiss is not None) if use_faiss is None else (bool(use_faiss) and faiss is not None)
        self.backend = "faiss" if self.use_faiss else "numpy"
        self.meta = []
        self.vecs = np.zeros((0, 0), dtype=np.float32)  # sempre mantido (permite trocar de backend/reindexar)
        self.index = None
        self.needs_migration = False
        self.load()

    # ---------- persistência ----------
    def _build_index(self):
        self.index = None
        if self.use_faiss and len(self.meta):
            self.index = faiss.IndexFlatIP(int(self.vecs.shape[1]))
            self.index.add(np.ascontiguousarray(self.vecs, dtype=np.float32))

    def load(self):
        m, v = self.folder / "meta.json", self.folder / "vecs.npy"
        man = self.folder / "manifest.json"
        if m.exists() and v.exists():
            self.meta = json.loads(m.read_text(encoding="utf-8"))
            self.vecs = np.load(v).astype(np.float32)
            if len(self.meta) != len(self.vecs):
                raise ValueError("Índice RAG corrompido (meta e vetores com tamanhos diferentes). Use 'Limpar'.")
            fi = self.folder / "index.faiss"
            if self.use_faiss and fi.exists():
                self.index = faiss.read_index(str(fi))
                if self.index.ntotal != len(self.meta):
                    self._build_index()
            else:
                self._build_index()
            # base antiga (v2: só meta.json+vecs.npy) -> converter uma vez
            self.needs_migration = len(self.meta) > 0 and not man.exists()

    def save(self):
        tmp = self.folder / "meta.json.tmp"
        tmp.write_text(json.dumps(self.meta, ensure_ascii=False), encoding="utf-8")
        np.save(self.folder / "vecs.npy", self.vecs)
        tmp.replace(self.folder / "meta.json")
        fi = self.folder / "index.faiss"
        if self.use_faiss and self.index is not None:
            faiss.write_index(self.index, str(fi))
        elif fi.exists():
            fi.unlink()
        dim = int(self.vecs.shape[1]) if len(self.meta) else 0
        (self.folder / "manifest.json").write_text(json.dumps(
            {"version": FORMAT_VERSION, "backend": self.backend, "dim": dim, "count": len(self.meta)}), encoding="utf-8")
        self.needs_migration = False

    @staticmethod
    def _norm(a):
        a = np.asarray(a, dtype=np.float32)
        if a.ndim == 1:
            a = a.reshape(1, -1)
        n = np.linalg.norm(a, axis=-1, keepdims=True); n[n == 0] = 1
        return a / n

    # ---------- operações ----------
    def add(self, metas, vectors):
        v = self._norm(vectors)
        if len(metas) != len(v):
            raise ValueError("Quantidade de trechos e vetores diferente.")
        if len(self.meta) and self.vecs.shape[1] != v.shape[1]:
            raise ValueError("Dimensão de embedding diferente da base existente. Limpe a base ou reindexe.")
        self.vecs = v if not len(self.meta) else np.vstack([self.vecs, v])
        self.meta.extend(metas)
        if self.use_faiss:
            if self.index is None:
                self.index = faiss.IndexFlatIP(int(v.shape[1]))
            self.index.add(np.ascontiguousarray(v))
        self.save()

    def remove_source(self, source):
        keep = [i for i, m in enumerate(self.meta) if m["source"] != source]
        if len(keep) == len(self.meta):
            return
        self.meta = [self.meta[i] for i in keep]
        self.vecs = self.vecs[keep] if keep else np.zeros((0, 0), dtype=np.float32)
        self._build_index(); self.save()

    def sources(self):
        return sorted({m["source"] for m in self.meta})

    def clear(self):
        self.meta = []; self.vecs = np.zeros((0, 0), dtype=np.float32); self.index = None; self.save()

    def search(self, qvec, k=4):
        if not self.meta:
            return []
        q = self._norm(qvec)
        if q.shape[1] != self.vecs.shape[1]:
            raise ValueError("Dimensão da pergunta difere da base (modelo de embeddings mudou?). Reindexe.")
        k = max(1, min(int(k), len(self.meta)))
        if self.use_faiss and self.index is not None:
            D, I = self.index.search(np.ascontiguousarray(q), k)
            return [(float(d), self.meta[int(i)]) for d, i in zip(D[0], I[0]) if i >= 0]
        s = self.vecs @ q.reshape(-1)
        idx = np.argsort(-s)[:k]
        return [(float(s[i]), self.meta[i]) for i in idx]


def migrate(store, progress=lambda s: None):
    """Conversão única de base antiga (v2) para o formato atual, sem chamar o Ollama.
    Retorna nº de trechos migrados (0 se não havia nada a migrar)."""
    if not store.needs_migration:
        return 0
    n = len(store.meta)
    progress(f"Convertendo índice antigo: {n} trechos...")
    store._build_index(); store.save()
    progress(f"Índice convertido ({store.backend}): {n}/{n} trechos")
    return n


def reindex(store, embed_fn, batch=16, progress=lambda s: None, on_progress=None, cancel_flag=None):
    """Reindexação única de todos os documentos já indexados (recalcula embeddings a partir
    do texto salvo; use após trocar o modelo de embeddings). Não precisa dos arquivos originais.
    progress(str) para log; on_progress(passo, total) compatível com a fila. Retorna nº de trechos."""
    metas = list(store.meta)
    total = len(metas)
    if not total:
        return 0
    vecs = []
    for i in range(0, total, batch):
        if cancel_flag is not None and cancel_flag.is_set():
            progress("Reindexação cancelada; índice anterior mantido.")
            return 0
        vecs.extend(embed_fn([m["text"] for m in metas[i:i + batch]]))
        done = min(i + batch, total)
        progress(f"Reindexando: {done}/{total} trechos")
        if on_progress:
            on_progress(done, total)
    store.meta = []; store.vecs = np.zeros((0, 0), dtype=np.float32); store.index = None
    store.add(metas, vecs)
    return total


def index_file(path, store, embed_fn, size=800, overlap=150, progress=lambda s: None):
    name = Path(path).name
    store.remove_source(name)
    metas = []
    for page, txt in read_file(path):
        for c in chunk_text(txt, size, overlap):
            metas.append({"source": name, "page": page, "text": c})
    if not metas:
        raise ValueError(f"Nenhum texto extraído de {name}.")
    vecs = []
    for i in range(0, len(metas), 16):
        vecs.extend(embed_fn([m["text"] for m in metas[i:i + 16]]))
        progress(f"{name}: {min(i + 16, len(metas))}/{len(metas)} trechos")
    store.add(metas, vecs)
    return len(metas)

def build_prompt(question, hits):
    ctx = []
    for n, (_, m) in enumerate(hits, 1):
        ref = m["source"] + (f", p. {m['page']}" if m.get("page") else "")
        ctx.append(f"[{n}] ({ref})\n{m['text']}")
    return ("Use apenas os trechos abaixo para responder em português. Cite as fontes com [n]. "
            "Se a resposta não estiver nos trechos, diga que não encontrou.\n\n"
            + "\n\n".join(ctx) + f"\n\nPergunta: {question}\nResposta:")

def citations(hits):
    return "\n".join(f"[{n}] {m['source']}" + (f", p. {m['page']}" if m.get("page") else "") + f" (score {s:.2f})"
                     for n, (s, m) in enumerate(hits, 1))
