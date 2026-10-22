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


# ---------- descarregar Ollama antes de tarefas pesadas ----------
class _Resp:
    def __init__(self, body=b"{}"): self.body = body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False

def _fake_ollama(monkeypatch, calls, down=False, cfg=None):
    import json as _j
    def urlopen(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        body = None if isinstance(req, str) else _j.loads(req.data)
        calls.append((url, body, timeout))
        if down: raise OSError("connection refused")
        if url.endswith("/api/ps"):
            return _Resp(_j.dumps({"models": [{"name": "qwen3:30b"}, {"name": "nomic-embed-text"}]}).encode())
        if url.endswith("/api/generate") and body["model"] == "nomic-embed-text":
            raise OSError("400 does not support generate")
        return _Resp()
    monkeypatch.setattr(jq.urllib.request, "urlopen", urlopen)
    base = {"ollama_url": "http://h:1", "queue_unload_ollama": True}; base.update(cfg or {})
    monkeypatch.setattr(jq, "_cfg", lambda: dict(base))

def _run_one(app, tipo):
    q = jq.JobQueue(engines={tipo: steps_engine(2, 0)}); r = Rec(q)
    jid = q.enqueue(tipo, {"name": "a"})
    assert pump(app, lambda: "finished" in r.names(jid) or "failed" in r.names(jid))
    q.shutdown(); return r.names(jid)

def test_unload_heavy(app, monkeypatch):
    calls = []; _fake_ollama(monkeypatch, calls)
    assert "finished" in _run_one(app, "imagem")
    urls = [(u, b and b.get("model")) for u, b, _ in calls]
    assert urls[0] == ("http://h:1/api/ps", None)
    assert ("http://h:1/api/generate", "qwen3:30b") in urls
    assert ("http://h:1/api/embed", "nomic-embed-text") in urls
    assert all(t and t <= 5 for _, _, t in calls)
    assert all(b["keep_alive"] == 0 for _, b, _ in calls if b)

def test_no_unload_light(app, monkeypatch):
    calls = []; _fake_ollama(monkeypatch, calls)
    assert "finished" in _run_one(app, "falar") and calls == []

def test_unload_disabled(app, monkeypatch):
    calls = []; _fake_ollama(monkeypatch, calls, cfg={"queue_unload_ollama": False})
    assert "finished" in _run_one(app, "video") and calls == []

def test_unload_custom_types(app, monkeypatch):
    calls = []; _fake_ollama(monkeypatch, calls, cfg={"queue_unload_types": ["falar"]})
    assert "finished" in _run_one(app, "falar") and calls
    calls.clear(); assert "finished" in _run_one(app, "video") and calls == []

def test_ollama_down_tolerated(app, monkeypatch):
    calls = []; _fake_ollama(monkeypatch, calls, down=True)
    assert "finished" in _run_one(app, "ampliar") and len(calls) == 1

def test_unload_on_by_default(app, monkeypatch):
    calls = []
    def urlopen(req, timeout=None):
        calls.append(req); return _Resp()
    monkeypatch.setattr(jq.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(jq, "_cfg", lambda: {"ollama_url": "http://h:1"})  # chave ausente = padrão True
    _run_one(app, "video")
    assert calls  # consultou /api/ps


# ---------- proteção do chat em andamento ----------
@pytest.fixture
def chat_limpo():
    while jq.chat_ativo(): jq.chat_terminado()
    yield
    while jq.chat_ativo(): jq.chat_terminado()

def test_chat_contador_aninhado(chat_limpo):
    assert not jq.chat_ativo()
    with jq.chat_em_andamento():
        with jq.JobQueue.chat_em_andamento():
            assert jq.chat_ativo()
        assert jq.chat_ativo()
    assert not jq.chat_ativo()
    jq.chat_terminado(); assert not jq.chat_ativo()   # nunca negativo
    jq.chat_iniciado(); assert jq.chat_ativo(); jq.chat_terminado()
    ts = [threading.Thread(target=lambda: [jq.chat_iniciado() or jq.chat_terminado() for _ in range(500)]) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not jq.chat_ativo()

def test_unload_espera_chat_e_depois_descarrega(app, monkeypatch, chat_limpo):
    calls = []; _fake_ollama(monkeypatch, calls, cfg={"queue_unload_wait_s": 10})
    q = jq.JobQueue(engines={"imagem": steps_engine(2, 0)}); r = Rec(q)
    jq.chat_iniciado()
    jid = q.enqueue("imagem", {})
    pump(app, lambda: False, timeout=0.4)
    assert calls == [] and "finished" not in r.names(jid)   # não descarrega com chat ativo
    jq.chat_terminado()
    assert pump(app, lambda: "finished" in r.names(jid))
    assert calls and calls[0][0].endswith("/api/ps")
    q.shutdown()

def test_unload_timeout_pula_e_roda(app, monkeypatch, chat_limpo, caplog):
    import logging
    calls = []; _fake_ollama(monkeypatch, calls, cfg={"queue_unload_wait_s": 0.3})
    with jq.chat_em_andamento(), caplog.at_level(logging.WARNING):
        names = _run_one(app, "video")
    assert "finished" in names and calls == []
    assert any("pulada" in rec.message for rec in caplog.records)

def test_cancel_durante_espera(app, monkeypatch, chat_limpo):
    calls = []; _fake_ollama(monkeypatch, calls, cfg={"queue_unload_wait_s": 30})
    q = jq.JobQueue(engines={"imagem": steps_engine(3, 0.01)}); r = Rec(q)
    with jq.chat_em_andamento():
        jid = q.enqueue("imagem", {})
        assert pump(app, lambda: "started" in r.names(jid))
        t0 = time.time(); q.cancel(jid)
        assert pump(app, lambda: "cancelled" in r.names(jid), timeout=3)
        assert time.time() - t0 < 2 and calls == []
    q.shutdown()

def test_chat_ativo_sem_unload_padrao_intocado(app, monkeypatch, chat_limpo):
    calls = []
    monkeypatch.setattr(jq.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(jq, "_cfg", lambda: {"ollama_url": "http://h:1", "queue_unload_ollama": False})
    with jq.chat_em_andamento():
        t0 = time.time(); names = _run_one(app, "video")
    assert "finished" in names and calls == [] and time.time() - t0 < 2


def test_sem_progresso_fantasma_apos_cancelar(app):
    cont = threading.Event(); chegou3 = threading.Event()
    def eng(params, on_progress, cancel_flag):
        for p in range(1, 21):
            on_progress(p, 20)
            if p == 3:
                chegou3.set(); cont.wait(3)
                on_progress(4, 20)   # motor ainda reporta depois do cancelamento
                return None
        return "x"
    q = jq.JobQueue(engines={"video": eng}, progress_interval=0); r = Rec(q)
    jid = q.enqueue("video", {})
    assert chegou3.wait(3)
    assert pump(app, lambda: any(e[0] == "progress" and e[2] == 3 for e in r.ev))
    q.cancel(jid); cont.set()
    assert pump(app, lambda: "cancelled" in r.names(jid))
    pump(app, lambda: False, timeout=0.2)
    passos = [e[2] for e in r.ev if e[0] == "progress" and e[1] == jid]
    assert 4 not in passos and passos and max(passos) == 3
    i = [e[0] for e in r.ev if e[1] == jid]
    assert "progress" not in i[i.index("cancelled"):]
    q.shutdown()

def test_progresso_atrasado_descartado_na_gui(app):
    q = jq.JobQueue(engines={"video": steps_engine(50, 0.02)}); r = Rec(q)
    jid = q.enqueue("video", {})
    assert pump(app, lambda: "started" in r.names(jid))
    q._progress_raw.emit(jid, 4, 20, 20.0, 1.0)   # já na fila de eventos da GUI
    q.cancel(jid)                                  # cancelado antes da entrega
    assert pump(app, lambda: "cancelled" in r.names(jid))
    assert not any(e[0] == "progress" and e[2] == 4 and e[3] == 20 for e in r.ev if e[1] == jid)
    q.shutdown()


def test_falha_e_sem_resultado_logados(app, caplog):
    import logging
    def bad(p, op, cf): raise RuntimeError("boom")
    def vazio(p, op, cf): return None
    q = jq.JobQueue(engines={"imagem": bad, "video": vazio}); Rec(q)
    with caplog.at_level(logging.INFO, logger="ia_off.job_queue"):
        a = q.enqueue("imagem", {}); b = q.enqueue("video", {})
        pump(app, lambda: done(q, a) and done(q, b))
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "boom" in msgs and "sem resultado" in msgs
    q.shutdown()


def test_excecao_apos_cancel_logada(app, caplog):
    import logging
    ev = threading.Event()
    def eng(p, op, cf):
        ev.set(); cf.wait(5); raise RuntimeError("interrompido")
    q = jq.JobQueue(engines={"imagem": eng}); Rec(q)
    with caplog.at_level(logging.INFO, logger="ia_off.job_queue"):
        a = q.enqueue("imagem", {}); ev.wait(5); q.cancel(a)
        pump(app, lambda: done(q, a))
    assert q.get(a)["estado"] == "cancelada"
    assert any("descartada" in r.getMessage() for r in caplog.records)
    q.shutdown()


# ---------- descarga do Ollama ligada por padrão (config) ----------
def test_unload_video_sem_chat(app, monkeypatch, chat_limpo):
    calls = []; _fake_ollama(monkeypatch, calls)
    assert "finished" in _run_one(app, "video")
    assert calls and calls[0][0] == "http://h:1/api/ps"


@pytest.mark.parametrize("tipo", ["chat", "transcrever", "falar", "rag"])
def test_sem_unload_fora_da_lista(app, monkeypatch, tipo):
    calls = []; _fake_ollama(monkeypatch, calls)
    assert "finished" in _run_one(app, tipo) and calls == []


def test_chat_ativo_espera_curta_pula(app, monkeypatch, chat_limpo, caplog):
    import logging
    calls = []; _fake_ollama(monkeypatch, calls, cfg={"queue_unload_wait_s": 0.2})
    with jq.chat_em_andamento(), caplog.at_level(logging.WARNING, logger="ia_off.job_queue"):
        names = _run_one(app, "imagem")
    assert "finished" in names and calls == []
    assert any("pulada" in r.getMessage() for r in caplog.records)


def test_unload_excecao_tarefa_conclui(app, monkeypatch, chat_limpo):
    def boom(*a, **k): raise RuntimeError("falha inesperada")
    monkeypatch.setattr(jq, "_cfg", lambda: {"queue_unload_ollama": True})
    monkeypatch.setattr(jq, "unload_ollama_models", boom)
    assert "finished" in _run_one(app, "video")


def test_padroes_consistentes():
    from ia_off import config
    assert config.DEFAULTS["queue_unload_ollama"] is jq.UNLOAD_ENABLED is True
    assert tuple(config.DEFAULTS["queue_unload_types"]) == jq.DEFAULT_UNLOAD_TYPES
    assert float(config.DEFAULTS["queue_unload_wait_s"]) == jq.UNLOAD_WAIT_S


@pytest.mark.parametrize("val,esp", [("0", False), ("1", True), ("false", False), ("TRUE", True),
                                     (" False ", False), ("", True), ("xyz", True)])
def test_env_queue_unload(monkeypatch, val, esp):
    from ia_off import config
    monkeypatch.setenv("IA_OFF_QUEUE_UNLOAD_OLLAMA", val)
    assert config._env_bool("IA_OFF_QUEUE_UNLOAD_OLLAMA", True) is esp


def test_prompt_bloqueado_sem_prefixo_tecnico(app, monkeypatch):
    from ia_off.moderador import PromptBloqueado
    import time as _t
    monkeypatch.setattr(jq, "_cfg", lambda: {"queue_unload_ollama": False})
    def motor(p, on_progress, cancel):
        raise PromptBloqueado("Pedido bloqueado pela moderação (nível \"medio\"): teste")
    q = jq.JobQueue(engines={"imagem": motor})
    erros = []
    q.failed.connect(lambda jid, err: erros.append(err))
    q.enqueue("imagem", {})
    fim = _t.time() + 5
    while not erros and _t.time() < fim:
        app.processEvents(); _t.sleep(0.02)
    q.shutdown()
    assert erros and erros[0].startswith("Pedido bloqueado")
    assert "PromptBloqueado:" not in erros[0]
