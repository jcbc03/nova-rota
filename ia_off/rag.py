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

class VectorStore:
    def __init__(self, folder):
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True)
        self.meta = []; self.vecs = np.zeros((0, 0), dtype=np.float32)
        self.load()

    def load(self):
        m, v = self.folder / "meta.json", self.folder / "vecs.npy"
        if m.exists() and v.exists():
            self.meta = json.loads(m.read_text(encoding="utf-8")); self.vecs = np.load(v)

    def save(self):
        (self.folder / "meta.json").write_text(json.dumps(self.meta, ensure_ascii=False), encoding="utf-8")
        np.save(self.folder / "vecs.npy", self.vecs)

    @staticmethod
    def _norm(a):
        a = np.asarray(a, dtype=np.float32)
        n = np.linalg.norm(a, axis=-1, keepdims=True); n[n == 0] = 1
        return a / n

    def add(self, metas, vectors):
        v = self._norm(vectors)
        if len(self.meta) and self.vecs.shape[1] != v.shape[1]:
            raise ValueError("Dimensão de embedding diferente da base existente. Limpe a base.")
        self.vecs = v if not len(self.meta) else np.vstack([self.vecs, v])
        self.meta.extend(metas); self.save()

    def remove_source(self, source):
        keep = [i for i, m in enumerate(self.meta) if m["source"] != source]
        self.meta = [self.meta[i] for i in keep]
        self.vecs = self.vecs[keep] if keep else np.zeros((0, 0), dtype=np.float32); self.save()

    def sources(self):
        return sorted({m["source"] for m in self.meta})

    def clear(self):
        self.meta = []; self.vecs = np.zeros((0, 0), dtype=np.float32); self.save()

    def search(self, qvec, k=4):
        if not self.meta:
            return []
        s = self.vecs @ self._norm(qvec).reshape(-1)
        idx = np.argsort(-s)[:k]
        return [(float(s[i]), self.meta[i]) for i in idx]

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
