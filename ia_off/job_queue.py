"""Fila de tarefas pesadas (interface v1, ver docs/FILA_API.md). Responsável: DEV beck.

- UMA tarefa pesada por vez (um único worker thread), adequado ao i5-8365U sem GPU.
- O worker NUNCA toca em widgets: só emite sinais Qt. Como o JobQueue vive na thread da GUI,
  conexões automáticas viram QueuedConnection e os slots da tela rodam na thread da GUI.
- Motores são plugados por registro (register_engine), sem editar este arquivo:

    from ia_off.job_queue import register_engine
    def gerar_imagem(params, on_progress, cancel_flag):
        for passo in range(1, n + 1):
            if cancel_flag.is_set(): return None      # encerra limpo
            ...; on_progress(passo, n)
        return caminho_resultado                      # str/Path
    register_engine("imagem", gerar_imagem)
"""
import itertools
import json
import logging
import urllib.request
import threading
import time
import traceback
from collections import deque

from PySide6.QtCore import QObject, Qt, Signal

NA_FILA, RODANDO, CONCLUIDA, FALHOU, CANCELADA = "na_fila", "rodando", "concluida", "falhou", "cancelada"

_log = logging.getLogger(__name__)

# Antes destes tipos, a fila descarrega os modelos do Ollama para liberar RAM (config: queue_unload_*).
DEFAULT_UNLOAD_TYPES = ("video", "imagem", "ampliar")
UNLOAD_TIMEOUT_S = 3.0
UNLOAD_ENABLED = True  # padrão de queue_unload_ollama (igual a config.DEFAULTS)
UNLOAD_WAIT_S = 120.0   # padrão de queue_unload_wait_s
CHAT_POLL_S = 0.1

# ---------- marcador "chat em andamento" (contador, thread-safe) ----------
_chat_cond = threading.Condition()
_chat_n = 0


def chat_iniciado():
    """Marca início de uma resposta do chat (pode aninhar / várias threads)."""
    global _chat_n
    with _chat_cond:
        _chat_n += 1


def chat_terminado():
    """Marca fim de uma resposta do chat (nunca fica negativo)."""
    global _chat_n
    with _chat_cond:
        _chat_n = max(0, _chat_n - 1)
        _chat_cond.notify_all()


def chat_ativo():
    with _chat_cond:
        return _chat_n > 0


class chat_em_andamento:
    """with chat_em_andamento(): ...  — a fila não descarrega o Ollama enquanto ativo."""
    def __enter__(self):
        chat_iniciado(); return self
    def __exit__(self, *exc):
        chat_terminado(); return False


def esperar_chat_livre(timeout, cancel_flag=None, poll=CHAT_POLL_S):
    """True se não há chat ativo (já ou após esperar); False em timeout ou cancelamento."""
    fim = time.monotonic() + max(0.0, float(timeout))
    with _chat_cond:
        while _chat_n > 0:
            if cancel_flag is not None and cancel_flag.is_set():
                return False
            resta = fim - time.monotonic()
            if resta <= 0:
                return False
            _chat_cond.wait(min(poll, resta))
        return True


def _cfg():
    try:
        from ia_off import config
        return config.load()
    except Exception as e:
        _log.warning("fila: config indisponível (%s); usando padrões", e)
        return {}


def _post(url, payload, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read()


def unload_ollama_models(host, timeout=UNLOAD_TIMEOUT_S):
    """GET /api/ps e, para cada modelo carregado, keep_alive=0. Nunca levanta; devolve nomes descarregados."""
    host = str(host or "").rstrip("/")
    done = []
    try:
        with urllib.request.urlopen(host + "/api/ps", timeout=timeout) as r:
            models = json.loads(r.read().decode() or "{}").get("models") or []
    except Exception as e:
        _log.info("fila: Ollama indisponível em %s (%s); seguindo sem descarregar", host, e)
        return done
    for m in models:
        name = m.get("name") or m.get("model")
        if not name:
            continue
        try:
            _post(host + "/api/generate", {"model": name, "keep_alive": 0}, timeout)
        except Exception as e:
            # modelos de embedding não aceitam /api/generate: descarrega via /api/embed
            try:
                _post(host + "/api/embed", {"model": name, "input": "", "keep_alive": 0}, timeout)
            except Exception as e2:
                _log.warning("fila: falha ao descarregar %s (%s / %s)", name, e, e2)
                continue
        done.append(name)
    if done:
        _log.info("fila: modelos do Ollama descarregados: %s", ", ".join(done))
    return done


_ENGINES = {}
_ENGINES_LOCK = threading.Lock()


class JobCancelled(Exception):
    """Motor pode lançar isto ao perceber cancel_flag (alternativa a retornar None)."""


def register_engine(tipo, fn):
    """Registra motor global: fn(params, on_progress, cancel_flag) -> caminho_resultado."""
    if not callable(fn):
        raise TypeError("motor precisa ser chamável")
    with _ENGINES_LOCK:
        _ENGINES[str(tipo)] = fn


def unregister_engine(tipo):
    with _ENGINES_LOCK:
        _ENGINES.pop(str(tipo), None)


def engines():
    with _ENGINES_LOCK:
        return dict(_ENGINES)


class _Job:
    __slots__ = ("id", "tipo", "params", "estado", "passo", "total", "pct", "eta_s",
                 "resultado", "erro", "criado", "inicio", "fim", "cancel_flag", "fase")

    def __init__(self, jid, tipo, params):
        self.id, self.tipo, self.params = jid, tipo, dict(params or {})
        self.estado = NA_FILA; self.passo = 0; self.total = 0; self.pct = 0.0; self.eta_s = -1.0; self.fase = ""
        self.resultado = None; self.erro = None
        self.criado = time.time(); self.inicio = None; self.fim = None
        self.cancel_flag = threading.Event()

    def info(self):
        return {"id": self.id, "tipo": self.tipo, "estado": self.estado, "passo": self.passo,
                "total": self.total, "pct": self.pct, "eta_s": self.eta_s, "resultado": self.resultado,
                "erro": self.erro, "criado": self.criado, "inicio": self.inicio, "fim": self.fim,
                "params": dict(self.params)}


class JobQueue(QObject):
    started = Signal(str)
    progress = Signal(str, int, int, float, float)   # id, passo, total, pct (0-100), eta_s (-1 = desconhecido)
    finished = Signal(str, str)                      # id, caminho_resultado
    failed = Signal(str, str)                        # id, erro
    cancelled = Signal(str)
    _progress_raw = Signal(str, int, int, float, float)  # interno: worker -> thread da GUI (filtra cancelados)
    phase = Signal(str, str)                         # id, fase ("decodificando", "salvando", "convertendo")
    _phase_raw = Signal(str, str)

    def __init__(self, parent=None, engines=None, progress_interval=0.1):
        super().__init__(parent)
        self._local_engines = dict(engines or {})
        self._jobs = {}                  # id -> _Job (ordem de inserção)
        self._pending = deque()
        self._cond = threading.Condition()
        self._ids = itertools.count(1)
        self._stop = False
        self._interval = float(progress_interval)
        self._progress_raw.connect(self._relay_progress, Qt.QueuedConnection)
        self._phase_raw.connect(self._relay_phase, Qt.QueuedConnection)
        self._worker = threading.Thread(target=self._run, name="ia_off-job-queue", daemon=True)
        self._worker.start()

    # ---------- API pública (chamar da thread da GUI) ----------
    # atalhos do marcador de chat (o estado é global do módulo, vale para todas as filas)
    chat_iniciado = staticmethod(chat_iniciado)
    chat_terminado = staticmethod(chat_terminado)
    chat_ativo = staticmethod(chat_ativo)
    chat_em_andamento = chat_em_andamento

    def register_engine(self, tipo, fn):
        """Registro só desta fila (sobrepõe o global)."""
        self._local_engines[str(tipo)] = fn

    def enqueue(self, tipo, params=None):
        tipo = str(tipo)
        if self._engine(tipo) is None:
            raise ValueError(f"Nenhum motor registrado para o tipo '{tipo}'.")
        with self._cond:
            if self._stop:
                raise RuntimeError("Fila encerrada.")
            jid = f"job-{next(self._ids)}"
            job = _Job(jid, tipo, params)
            self._jobs[jid] = job; self._pending.append(job)
            self._cond.notify()
        return jid

    def cancel(self, jid):
        """Cancela na fila (imediato) ou rodando (sinaliza cancel_flag). Retorna True se agiu."""
        emit = False
        with self._cond:
            job = self._jobs.get(jid)
            if job is None or job.estado in (CONCLUIDA, FALHOU, CANCELADA):
                return False
            job.cancel_flag.set()
            if job.estado == NA_FILA:
                try:
                    self._pending.remove(job)
                except ValueError:
                    pass
                job.estado = CANCELADA; job.fim = time.time(); emit = True
        if emit:
            self.cancelled.emit(jid)
        return True

    def list_jobs(self):
        with self._cond:
            return [j.info() for j in self._jobs.values()]

    def get(self, jid):
        with self._cond:
            j = self._jobs.get(jid)
            return j.info() if j else None

    def clear_finished(self):
        with self._cond:
            for k in [k for k, j in self._jobs.items() if j.estado in (CONCLUIDA, FALHOU, CANCELADA)]:
                del self._jobs[k]

    def shutdown(self, wait=True, timeout=None):
        """Cancela tudo e para o worker (chamar no closeEvent/aboutToQuit)."""
        with self._cond:
            self._stop = True
            ids = [j.id for j in self._jobs.values() if j.estado in (NA_FILA, RODANDO)]
            self._cond.notify_all()
        for jid in ids:
            self.cancel(jid)
        if wait and self._worker.is_alive() and threading.current_thread() is not self._worker:
            self._worker.join(timeout)

    def _relay_progress(self, jid, passo, total, pct, eta):
        """Na thread da GUI: descarta progresso enfileirado de tarefa cujo cancelamento já foi pedido.
        (Progresso de tarefa concluída/falha chega antes de finished/failed: mesma ordem do worker.)"""
        job = self._jobs.get(jid)
        if job is None or job.cancel_flag.is_set():
            return
        self.progress.emit(jid, passo, total, pct, eta)

    def _relay_phase(self, jid, fase):
        job = self._jobs.get(jid)
        if job is None or job.cancel_flag.is_set():
            return
        self.phase.emit(jid, fase)

    # ---------- worker ----------
    def _engine(self, tipo):
        return self._local_engines.get(tipo) or engines().get(tipo)

    def _run(self):
        while True:
            with self._cond:
                while not self._pending and not self._stop:
                    self._cond.wait()
                if self._stop and not self._pending:
                    return
                job = self._pending.popleft()
                if job.estado != NA_FILA:
                    continue
                job.estado = RODANDO; job.inicio = time.time()
            self.started.emit(job.id)
            self._pre_job(job)
            self._execute(job)

    def _pre_job(self, job):
        """Gancho antes do motor (na thread de trabalho). Nunca falha a tarefa."""
        try:
            cfg = _cfg()
            if not cfg.get("queue_unload_ollama", UNLOAD_ENABLED):
                return
            tipos = cfg.get("queue_unload_types")
            tipos = set(DEFAULT_UNLOAD_TYPES if tipos is None else tipos)
            if job.tipo not in tipos or job.cancel_flag.is_set():
                return
            if chat_ativo():
                espera = cfg.get("queue_unload_wait_s", UNLOAD_WAIT_S)
                espera = UNLOAD_WAIT_S if espera is None else float(espera)
                _log.info("fila: chat em andamento; aguardando até %.0f s para liberar o Ollama", espera)
                if not esperar_chat_livre(espera, job.cancel_flag):
                    if not job.cancel_flag.is_set():
                        _log.warning("fila: chat ainda em andamento após %.0f s; descarga do Ollama "
                                     "pulada e a tarefa %s roda mesmo assim", espera, job.id)
                    return
            unload_ollama_models(cfg.get("ollama_url") or "http://localhost:11434")
        except Exception as e:
            _log.warning("fila: gancho pré-tarefa ignorado (%s)", e)

    def _execute(self, job):
        last = [0.0]

        def on_progress(passo, total):
            if job.cancel_flag.is_set() or job.estado != RODANDO:
                return  # cancelamento pedido / já terminou: nada de passo fantasma
            passo, total = int(passo), int(total)
            now = time.time()
            pct = (100.0 * passo / total) if total > 0 else 0.0
            el = now - job.inicio
            eta = (el / passo * (total - passo)) if passo > 0 and total > 0 else -1.0
            job.passo, job.total, job.pct, job.eta_s = passo, total, pct, eta
            if now - last[0] >= self._interval or (total > 0 and passo >= total):
                last[0] = now
                self._progress_raw.emit(job.id, passo, total, float(pct), float(eta))

        def on_phase(fase):
            """Opcional p/ motores: getattr(on_progress, "phase", None)(fase). Etapa sem passos (ex.: VAE)."""
            if job.cancel_flag.is_set() or job.estado != RODANDO:
                return
            job.fase = str(fase)
            self._phase_raw.emit(job.id, str(fase))
        on_progress.phase = on_phase

        try:
            res = self._engine(job.tipo)(dict(job.params), on_progress, job.cancel_flag)
        except JobCancelled:
            res = None; job.cancel_flag.set()
        except Exception as e:
            if job.cancel_flag.is_set():
                _log.info("fila: tarefa %s cancelada; exceção do motor descartada (%s: %s)",
                          job.id, type(e).__name__, e)
                res = None
            else:
                # Erros "pro usuário" (ex.: PromptBloqueado do moderador) vão sem o nome técnico da classe.
                if getattr(e, "motivo", None) is not None or type(e).__name__ == "PromptBloqueado":
                    job.erro = str(e)
                else:
                    job.erro = f"{type(e).__name__}: {e}"
                with self._cond:
                    job.estado = FALHOU; job.fim = time.time()
                traceback.print_exc()
                _log.error("fila: tarefa %s (%s) falhou: %s", job.id, job.tipo, job.erro)
                self.failed.emit(job.id, job.erro)
                return
        with self._cond:
            job.fim = time.time()
            if job.cancel_flag.is_set():
                job.estado = CANCELADA
            elif res is None or str(res) == "":
                job.estado = FALHOU; job.erro = "Motor terminou sem resultado."
                _log.warning("fila: tarefa %s (%s) terminou sem resultado", job.id, job.tipo)
            else:
                job.estado = CONCLUIDA; job.resultado = str(res)
            estado = job.estado
        if estado == CANCELADA:
            self.cancelled.emit(job.id)
        elif estado == FALHOU:
            self.failed.emit(job.id, job.erro)
        else:
            self.finished.emit(job.id, job.resultado)
