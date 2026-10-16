import zlib
import os, tempfile, numpy as np
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
from ia_off.rag import chunk_text, VectorStore, index_file, build_prompt, citations
from ia_off.ollama_client import build_modelfile
from ia_off.storage import Storage

def fake_embed(texts):
    out = []
    for t in texts:
        v = np.zeros(64)
        for w in t.lower().split(): v[zlib.crc32(w.encode()) % 64] += 1
        out.append(v.tolist())
    return out

def test_chunk():
    text = " ".join(f"palavra{i}" for i in range(1000))
    ch = chunk_text(text, 200, 50)
    assert len(ch) > 5 and all(len(c) <= 200 for c in ch)
    assert ch[0].split()[-1] in ch[1]  # overlap
    assert chunk_text("") == [] and chunk_text("oi") == ["oi"]

def test_store_search(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("gatos gostam de leite. " * 50 + " carros andam na estrada rapidamente. " * 50, encoding="utf-8")
    s = VectorStore(tmp_path / "vs")
    n = index_file(str(f), s, fake_embed, size=200, overlap=40)
    assert n > 2
    hits = s.search(fake_embed(["carros estrada"])[0], k=2)
    assert "carros" in hits[0][1]["text"]
    s2 = VectorStore(tmp_path / "vs"); assert len(s2.meta) == n  # persisted
    assert "[1]" in build_prompt("q", hits) and "a.txt" in citations(hits)
    index_file(str(f), s2, fake_embed, size=200, overlap=40); assert len(s2.meta) == n  # reindex replaces
    s2.remove_source("a.txt"); assert s2.search([1]*64) == []

def test_modelfile_storage(tmp_path):
    m = build_modelfile(r"C:\a b\x.gguf", 2048, 4, 0.5, "oi")
    assert 'FROM "C:\\a b\\x.gguf"' in m and "num_thread 4" in m
    db = Storage(tmp_path / "d.db"); c = db.new_conv("t"); db.add_msg(c, "user", "olá")
    assert db.messages(c) == [{"role": "user", "content": "olá"}]
