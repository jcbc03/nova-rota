"""Testes da fila (QT_QPA_PLATFORM=offscreen)."""
import os, threading, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QCoreApplication, QObject, Slot
from ia_off import job_queue as jq

@pytest.fixture(scope="session")
def app():
    return QCoreApplication.instance() or QCoreApplication([])

class Rec(QObject):
    def __init__(self, q):
        super().__init__(); self.ev = []; self.threads = set(); self.gui = threading.current_thread()
        for name in ("started", "progress", "finished", "failed", "cancelled"):
            getattr(q, name).connect(lambda *a, n=name: self._on(n, a))
    def _on(self, n, a):
        self.threads.add(threading.current_thread()); self.ev.append((n,) + tuple(a))
    def names(self, jid): return [e[0] for e in self.ev if e[1] == jid]

def pump(app, cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond(): return True
        time.sleep(0.005)
    return False

def steps_engine(n=5, delay=0.01, record=None):
    def eng(params, on_progress, cancel_flag):
        if record is not None:
            record.append(("in", params.get("name"), threading.current_thread().name, time.time()))
        for i in range(1, n + 1):
            if cancel_flag.is_set(): return None
            time.sleep(delay); on_progress(i, n)
        if record is not None:
            record.append(("out", params.get("name"), time.time()))
        return f"/tmp/{params.get('name', 'x')}.png"
    return eng

def done(q, jid): return q.get(jid)["estado"] in ("concluida", "falhou", "cancelada")

def test_success_signals_in_gui_thread(app):
    q = jq.JobQueue(engines={"imagem": steps_engine()}, progress_interval=0); r = Rec(q)
    jid = q.enqueue("imagem", {"name": "a"})
    assert pump(app, lambda: "finished" in r.names(jid))
    n = r.names(jid); assert n[0] == "started" and n[-1] == "finished" and n.count("progress") == 5
    prog = [e for e in r.ev if e[0] == "progress"]
    assert prog[-1][2:5] == (5, 5, 100.0) and prog[-1][5] == pytest.approx(0, abs=0.01)
    assert ("finished", jid, "/tmp/a.png") in r.ev
    assert r.threads == {threading.current_thread()}   # slots rodaram na thread da GUI
    assert q.get(jid)["estado"] == "concluida"; q.shutdown()

def test_one_job_at_a_time_fifo(app):
    rec = []; q = jq.JobQueue(engines={"video": steps_engine(3, 0.02, rec)}); Rec(q)
    ids = [q.enqueue("video", {"name": str(i)}) for i in range(3)]
    assert pump(app, lambda: all(done(q, i) for i in ids))
    seq = [(e[0], e[1]) for e in rec]
    assert seq == [("in", "0"), ("out", "0"), ("in", "1"), ("out", "1"), ("in", "2"), ("out", "2")]
    assert len({e[2] for e in rec if e[0] == "in"}) == 1
    assert [j["estado"] for j in q.list_jobs()] == ["concluida"] * 3; q.shutdown()

def test_cancel_running_and_queued(app):
    q = jq.JobQueue(engines={"video": steps_engine(200, 0.01)}); r = Rec(q)
    a = q.enqueue("video", {"name": "a"}); b = q.enqueue("video", {"name": "b"})
    assert pump(app, lambda: "started" in r.names(a))
    assert q.cancel(b) is True and q.get(b)["estado"] == "cancelada"
    assert q.cancel(a) is True
    assert pump(app, lambda: done(q, a) and "cancelled" in r.names(a))
    assert q.get(a)["estado"] == "cancelada" and "started" not in r.names(b) and "cancelled" in r.names(b)
    assert "finished" not in r.names(a) and q.cancel(a) is False and q.cancel("nao-existe") is False
    q.shutdown()

def test_failure_then_queue_continues(app):
    def bad(p, on_progress, cancel_flag): raise RuntimeError("sem memória")
    q = jq.JobQueue(engines={"imagem": bad, "video": steps_engine(2)}); r = Rec(q)
    a = q.enqueue("imagem"); b = q.enqueue("video", {"name": "b"})
    assert pump(app, lambda: done(q, a) and done(q, b))
    assert ("failed", a, "RuntimeError: sem memória") in r.ev and "finished" in r.names(b); q.shutdown()

def test_engine_exception_after_cancel_is_cancelled(app):
    def eng(p, on_progress, cancel_flag):
        while not cancel_flag.is_set(): time.sleep(0.005)
        raise jq.JobCancelled()
    q = jq.JobQueue(engines={"imagem": eng}); r = Rec(q)
    a = q.enqueue("imagem"); assert pump(app, lambda: "started" in r.names(a)); q.cancel(a)
    assert pump(app, lambda: "cancelled" in r.names(a)); q.shutdown()

def test_global_registry_and_unknown_type(app):
    jq.register_engine("teste_global", steps_engine(1))
    try:
        q = jq.JobQueue(); r = Rec(q); a = q.enqueue("teste_global", {"name": "g"})
        assert pump(app, lambda: "finished" in r.names(a))
        with pytest.raises(ValueError): q.enqueue("nao_registrado")
        q.shutdown()
    finally:
        jq.unregister_engine("teste_global")

def test_progress_throttle_and_eta(app):
    q = jq.JobQueue(engines={"imagem": steps_engine(50, 0.002)}, progress_interval=10); r = Rec(q)
    a = q.enqueue("imagem", {"name": "t"}); assert pump(app, lambda: "finished" in r.names(a))
    prog = [e for e in r.ev if e[0] == "progress"]
    assert 1 <= len(prog) <= 2 and prog[-1][2] == 50   # último passo sempre emitido
    q.shutdown()

def test_shutdown_cancels_running(app):
    q = jq.JobQueue(engines={"video": steps_engine(1000, 0.01)}); r = Rec(q)
    a = q.enqueue("video"); assert pump(app, lambda: "started" in r.names(a))
    q.shutdown(timeout=3); assert not q._worker.is_alive() and q.get(a)["estado"] == "cancelada"
    with pytest.raises(RuntimeError): q.enqueue("video")
