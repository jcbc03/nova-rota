"""sub2: testes no box (sem modelos) para D1-D3, C3 e I4 do roteiro."""
import time, threading, zlib
import numpy as np
import pytest
from ia_off.rag import VectorStore, index_file, reindex, citations
from ia_off.storage import Storage


def fake_embed(texts):
    out = []
    for t in texts:
        v = np.zeros(128)
        for w in t.lower().split(): v[zlib.crc32(w.strip(".,").encode()) % 128] += 1
        out.append(v.tolist())
    return out


def _pdf(path, texto):
    """PDF mínimo de 1 página com texto (Helvetica), sem dependências."""
    stream = f"BT /F1 12 Tf 40 760 Td ({texto}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = b"%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    path.write_bytes(out)


DOCS = {"pdf": "o vulcao islandes entrou em erupcao com lava e cinzas",
        "docx": "a receita de bolo de cenoura leva ovos farinha e acucar",
        "txt": "o campeonato de xadrez terminou com vitoria das pretas"}
PERGUNTAS = {"pdf": "erupcao do vulcao lava", "docx": "receita bolo cenoura", "txt": "campeonato xadrez vitoria"}


@pytest.fixture
def store_docs(tmp_path):
    docx = pytest.importorskip("docx"); pytest.importorskip("pypdf")
    _pdf(tmp_path / "doc.pdf", DOCS["pdf"])
    d = docx.Document(); d.add_paragraph(DOCS["docx"]); d.save(str(tmp_path / "doc.docx"))
    (tmp_path / "doc.txt").write_text(DOCS["txt"], encoding="utf-8")
    s = VectorStore(tmp_path / "rag", use_faiss=False)
    n = {ext: index_file(str(tmp_path / f"doc.{ext}"), s, fake_embed) for ext in DOCS}
    return s, n


def test_D1_indexa_pdf_docx_txt(store_docs):
    s, n = store_docs
    assert all(v >= 1 for v in n.values()), n
    assert set(s.sources()) >= {"doc.pdf", "doc.docx", "doc.txt"}


def test_D2_busca_cita_fonte_certa(store_docs):
    s, _ = store_docs
    for ext, q in PERGUNTAS.items():
        hits = s.search(fake_embed([q])[0], k=3)
        assert hits[0][1]["source"] == f"doc.{ext}", (ext, hits[0][1])
        cit = citations(hits[:1])
        assert f"doc.{ext}" in cit and ("p. 1" in cit) == (ext == "pdf")


def test_D3_reindex_conclui_e_mantem_respostas(store_docs):
    s, _ = store_docs
    total = len(s.meta); passos = []
    t0 = time.perf_counter()
    assert reindex(s, fake_embed, on_progress=lambda a, b: passos.append((a, b))) == total
    assert time.perf_counter() - t0 < 5 and passos[-1] == (total, total)
    for ext, q in PERGUNTAS.items():
        assert s.search(fake_embed([q])[0], k=1)[0][1]["source"] == f"doc.{ext}"


def test_C3_historico_sobrevive_reabrir(tmp_path):
    db = Storage(tmp_path / "c.db"); c = db.new_conv("teste")
    for i in range(45):
        db.add_msg(c, "user" if i % 2 == 0 else "assistant", f"mensagem {i} ção")
    del db
    db2 = Storage(tmp_path / "c.db")
    msgs = db2.messages(c)
    assert len(msgs) == 45 and msgs[0]["content"] == "mensagem 0 ção" and msgs[-1]["role"] == "user"


def test_I4_tres_imagens_uma_por_vez_na_ordem():
    from PySide6.QtCore import QCoreApplication
    from ia_off.job_queue import JobQueue
    app = QCoreApplication.instance() or QCoreApplication([])
    ativos, max_ativos, ordem, lock = [0], [0], [], threading.Lock()

    def fake_img(params, on_progress, cancel_flag):
        with lock:
            ativos[0] += 1; max_ativos[0] = max(max_ativos[0], ativos[0]); ordem.append(params["n"])
        time.sleep(0.15)
        with lock: ativos[0] -= 1
        return f"img{params['n']}.png"

    q = JobQueue(engines={"imagem": fake_img})
    fim = []
    q.finished.connect(lambda jid, res: fim.append(res))
    ids = [q.enqueue("imagem", {"n": i}) for i in range(3)]
    t0 = time.time()
    while len(fim) < 3 and time.time() - t0 < 10:
        app.processEvents(); time.sleep(0.01)
    q.shutdown(wait=True, timeout=5)
    assert ordem == [0, 1, 2] and max_ativos[0] == 1
    assert fim == ["img0.png", "img1.png", "img2.png"], fim
    assert len(set(ids)) == 3
