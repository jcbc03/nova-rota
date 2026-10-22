"""Testes do rag.py v3 (FAISS + fallback numpy). Ollama é simulado."""
import json, threading
import numpy as np
import pytest
from ia_off import rag
from ia_off.rag import VectorStore, index_file, migrate, reindex, citations, build_prompt

WORDS = ["carros", "estrada", "gato", "peixe", "chuva", "sol", "livro", "mesa"]

def fake_embed(texts, dim=64):
    out = []
    for t in texts:
        v = np.zeros(dim, dtype=np.float32)
        for w in t.lower().split():
            v[hash(w.strip(".,")) % dim] += 1
        out.append(v.tolist())
    return out

@pytest.fixture(params=[True, False], ids=["faiss", "numpy"])
def use_faiss(request):
    if request.param and rag.faiss is None:
        pytest.skip("faiss não instalado")
    return request.param

def _doc(tmp_path, name="a.txt"):
    f = tmp_path / name
    f.write_text(" ".join(["carros na estrada com sol."] * 20 + ["gato come peixe na chuva."] * 20), encoding="utf-8")
    return f

def test_index_search_persist(tmp_path, use_faiss):
    s = VectorStore(tmp_path / "vs", use_faiss=use_faiss)
    assert s.backend == ("faiss" if use_faiss else "numpy")
    n = index_file(str(_doc(tmp_path)), s, fake_embed, size=200, overlap=40)
    hits = s.search(fake_embed(["gato peixe"])[0], k=3)
    assert len(hits) == 3 and "gato" in hits[0][1]["text"]
    assert hits[0][0] >= hits[1][0] >= hits[2][0]
    s2 = VectorStore(tmp_path / "vs", use_faiss=use_faiss)
    assert len(s2.meta) == n and not s2.needs_migration
    assert s2.search(fake_embed(["gato peixe"])[0], k=1)[0][1]["text"] == hits[0][1]["text"]
    assert "a.txt" in citations(hits) and "[1]" in build_prompt("q", hits)
    assert (tmp_path / "vs" / "index.faiss").exists() == use_faiss

def test_k_larger_than_base_and_remove(tmp_path, use_faiss):
    s = VectorStore(tmp_path / "vs", use_faiss=use_faiss)
    index_file(str(_doc(tmp_path, "a.txt")), s, fake_embed, size=200)
    index_file(str(_doc(tmp_path, "b.txt")), s, fake_embed, size=200)
    assert s.sources() == ["a.txt", "b.txt"]
    assert len(s.search(fake_embed(["sol"])[0], k=999)) == len(s.meta)
    s.remove_source("a.txt"); assert s.sources() == ["b.txt"]
    assert all(m["source"] == "b.txt" for _, m in s.search(fake_embed(["sol"])[0], k=50))
    s.clear(); assert s.search([1.0] * 64) == []

def test_dim_mismatch(tmp_path, use_faiss):
    s = VectorStore(tmp_path / "vs", use_faiss=use_faiss)
    index_file(str(_doc(tmp_path)), s, fake_embed, size=200)
    with pytest.raises(ValueError):
        s.search([1.0] * 32)
    with pytest.raises(ValueError):
        s.add([{"source": "x", "page": None, "text": "x"}], [[1.0] * 32])

def test_migrate_legacy_v2(tmp_path):
    d = tmp_path / "vs"; d.mkdir()
    metas = [{"source": "old.pdf", "page": i + 1, "text": f"gato {i}"} for i in range(5)]
    (d / "meta.json").write_text(json.dumps(metas), encoding="utf-8")
    np.save(d / "vecs.npy", np.asarray(fake_embed([m["text"] for m in metas]), dtype=np.float32))
    s = VectorStore(d)
    assert s.needs_migration
    log = []
    assert migrate(s, progress=log.append) == 5 and log
    assert (d / "manifest.json").exists() and not VectorStore(d).needs_migration
    assert migrate(s) == 0
    assert "old.pdf, p. " in citations(s.search(fake_embed(["gato"])[0], k=2))

def test_reindex_progress_and_cancel(tmp_path, use_faiss):
    s = VectorStore(tmp_path / "vs", use_faiss=use_faiss)
    n = index_file(str(_doc(tmp_path)), s, fake_embed, size=100)
    steps = []
    emb32 = lambda t: fake_embed(t, dim=32)
    assert reindex(s, emb32, batch=4, on_progress=lambda a, b: steps.append((a, b))) == n
    assert steps[-1] == (n, n) and s.vecs.shape == (n, 32)
    assert VectorStore(tmp_path / "vs", use_faiss=use_faiss).vecs.shape == (n, 32)
    ev = threading.Event(); ev.set()
    assert reindex(s, fake_embed, cancel_flag=ev) == 0 and s.vecs.shape[1] == 32

def test_fallback_without_faiss(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "faiss", None)
    s = VectorStore(tmp_path / "vs")
    assert s.backend == "numpy"
    index_file(str(_doc(tmp_path)), s, fake_embed, size=200)
    assert s.search(fake_embed(["carros"])[0], k=1)

def test_default_folder_from_config(tmp_path, monkeypatch):
    from ia_off import config
    monkeypatch.setattr(config, "load", lambda: {"rag_dir": str(tmp_path / "cfgrag")})
    s = VectorStore()
    assert s.folder == tmp_path / "cfgrag" and s.folder.exists()
    assert config.DEFAULTS["rag_dir"]

def test_with_mocked_ollama_client(tmp_path, monkeypatch):
    from ia_off import ollama_client
    class R:
        status_code = 200; ok = True; text = ""
        def __init__(self, data): self._d = data
        def json(self): return self._d
    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/api/embed")
        return R({"embeddings": fake_embed(json["input"])})
    monkeypatch.setattr(ollama_client.requests, "post", fake_post)
    cli = ollama_client.OllamaClient("http://localhost:11434")
    s = VectorStore(tmp_path / "vs")
    index_file(str(_doc(tmp_path)), s, lambda t: cli.embed("nomic-embed-text", t), size=200)
    assert "carros" in s.search(cli.embed("nomic-embed-text", ["carros estrada"])[0], k=1)[0][1]["text"]


# ---------- robustez (beck) ----------
def _emb(texts):
    return [[1.0, float(len(t) % 7), 0.5] for t in texts]


def test_add_vazio_e_noop(tmp_path):
    from ia_off import rag
    st = rag.VectorStore(tmp_path / "i", use_faiss=False)
    st.add([], [])                       # antes: ValueError
    assert st.meta == [] and st.search([1, 0, 0]) == []


def test_index_file_falha_no_embed_mantem_trechos_antigos(tmp_path):
    from ia_off import rag
    st = rag.VectorStore(tmp_path / "i", use_faiss=False)
    doc = tmp_path / "doc.txt"; doc.write_text("versão um do documento. " * 20, encoding="utf-8")
    n = rag.index_file(doc, st, _emb)
    assert n > 0 and st.sources() == ["doc.txt"]
    doc.write_text("versão dois. " * 20, encoding="utf-8")
    def quebra(t): raise ConnectionError("Ollama fora")
    with pytest.raises(ConnectionError):
        rag.index_file(doc, st, quebra)
    st2 = rag.VectorStore(tmp_path / "i", use_faiss=False)
    assert len(st2.meta) == n and "versão um" in st2.meta[0]["text"]


def test_save_atomico_sem_tmp_e_falha_nao_corrompe(tmp_path, monkeypatch):
    from ia_off import rag
    import numpy as np
    st = rag.VectorStore(tmp_path / "i", use_faiss=False)
    st.add([{"source": "a", "page": None, "text": "x"}], [[1.0, 0, 0]])
    assert not list((tmp_path / "i").glob("*.tmp"))
    def boom(fh, a): fh.write(b"lixo"); raise OSError("disco cheio")
    monkeypatch.setattr(rag.np, "save", boom)
    with pytest.raises(OSError):
        st.add([{"source": "b", "page": None, "text": "y"}], [[0, 1.0, 0]])
    monkeypatch.undo()
    st2 = rag.VectorStore(tmp_path / "i", use_faiss=False)   # carrega a versão anterior íntegra
    assert [m["source"] for m in st2.meta] == ["a"] and st2.vecs.shape == (1, 3)
