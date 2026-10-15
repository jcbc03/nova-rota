"""Execução em segundo plano segura para Qt.

Regras:
- A função de trabalho roda em um QThread e NUNCA toca em widgets; ela só emite sinais.
- Os sinais são ligados (QueuedConnection) a slots do próprio Job, que vive na thread da GUI;
  esses slots chamam os callbacks Python — portanto os callbacks sempre rodam na thread da GUI.
- Todo Job fica num registro global (referência forte) até terminar; depois deleteLater.
- shutdown_all() cancela e espera todos os jobs (chamado no closeEvent / aboutToQuit).
"""
import threading
from PySide6.QtCore import QThread, Signal, Slot, Qt, QCoreApplication

_ALL = set()
_LOCK = threading.Lock()

import time

class _Throttle:
    """Agrupa emissões muito frequentes (progresso, linhas de log, pedaços de texto) para não inundar a GUI."""
    def __init__(self, job, interval=0.05):
        self.job = job; self.interval = interval; self.lock = threading.Lock()
        self.last_p = 0.0; self.pending_p = None; self.logs = []; self.chunks = []; self.last_flush = 0.0

    def progress(self, i, n, m=""):
        now = time.monotonic()
        with self.lock:
            if i == -1:
                self.logs.append(m)
            else:
                self.pending_p = (int(i), int(n), m or "")
                if n > 0 and i >= n: self.last_p = 0  # sempre entrega o 100%
        self.flush(force=False)

    def chunk(self, c):
        with self.lock: self.chunks.append(c)
        self.flush(force=False)

    def flush(self, force=True):
        now = time.monotonic()
        with self.lock:
            if not force and now - self.last_flush < self.interval and not (self.pending_p and self.last_p == 0):
                return
            self.last_flush = now; self.last_p = now
            p, self.pending_p = self.pending_p, None
            logs, self.logs = self.logs, []
            ch, self.chunks = self.chunks, []
        if logs: self.job._sig_progress.emit(-1, -1, "\n".join(logs[-200:]))
        if p: self.job._sig_progress.emit(*p)
        if ch: self.job._sig_chunk.emit("".join(ch))

class _Emitter:
    def __init__(self, fn): self.emit = fn

class Job(QThread):
    _sig_progress = Signal(int, int, str)
    info = Signal(str, str)
    _sig_chunk = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None, on_progress=None, on_info=None, on_chunk=None, on_done=None, on_error=None):
        super().__init__(parent)
        self.fn = fn; self.cancel = False
        self._thr = _Throttle(self)
        self.progress = _Emitter(self._thr.progress)  # mesma API: job.progress.emit(i, n, msg)
        self.chunk = _Emitter(self._thr.chunk)
        self._cb = dict(progress=on_progress, info=on_info, chunk=on_chunk, done=on_done, error=on_error)
        Q = Qt.QueuedConnection
        self._sig_progress.connect(self._on_progress, Q); self.info.connect(self._on_info, Q)
        self._sig_chunk.connect(self._on_chunk, Q); self.finished_ok.connect(self._on_done, Q)
        self.failed.connect(self._on_error, Q)
        self.finished.connect(self._cleanup, Q)

    # compatibilidade com o antigo Worker (chat)
    @property
    def stopped(self): return self.cancel
    @stopped.setter
    def stopped(self, v): self.cancel = bool(v)

    def start(self, *a):
        with _LOCK: _ALL.add(self)
        super().start(*a)

    def run(self):
        try:
            r = self.fn(self)
            self._thr.flush()
            self.finished_ok.emit(r)
        except BaseException as e:  # noqa: nunca deixa exceção escapar da thread
            try: self._thr.flush()
            except Exception: pass
            name = type(e).__name__
            msg = str(e) if name == "OllamaError" else f"{name}: {e}"
            self.failed.emit("Cancelado." if name == "Cancelled" or self.cancel else msg)

    def _call(self, key, *args):
        cb = self._cb.get(key)
        if cb is not None and not getattr(self, "_shutting", False):
            try: cb(*args)
            except Exception:
                import traceback, sys; sys.excepthook(*sys.exc_info())

    @Slot(int, int, str)
    def _on_progress(self, i, n, m): self._call("progress", i, n, m)
    @Slot(str, str)
    def _on_info(self, k, t): self._call("info", k, t)
    @Slot(str)
    def _on_chunk(self, c): self._call("chunk", c)
    @Slot(object)
    def _on_done(self, r): self._call("done", r)
    @Slot(str)
    def _on_error(self, m): self._call("error", m)

    @Slot()
    def _cleanup(self):
        with _LOCK: _ALL.discard(self)
        self._cb = {}
        self.deleteLater()

def running():
    with _LOCK: return [j for j in _ALL if j.isRunning()]

def shutdown_all(timeout_ms=8000):
    """Cancela e espera. Retorna True se todas as threads pararam."""
    jobs = running()
    for j in jobs:
        j._shutting = True; j.cancel = True
    ok = True
    for j in jobs:
        ok = j.wait(timeout_ms) and ok
    return ok
