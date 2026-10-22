"""E13: voz (falar/transcrever) pela JobQueue — cancelamento vira CANCELADA e progresso na escala passo/total."""
import os, threading, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QCoreApplication
from ia_off import voice_engine as ve, engines_registry as er, job_queue as jq
from ia_off.engine_api import Cancelled


def _cfg(tmp_path):
    return {"voz_dir": str(tmp_path / "voz"), "whisper_model": "small", "whisper_lang": "pt",
            "piper_voice": "pt_BR-faber-medium", "piper_exe": "", "threads": 2}


class SlowVoice:
    """Piper falso: cada frase leva `dt` s, em vários pedaços."""
    config = SimpleNamespace(sample_rate=16000)
    def __init__(self, dt=0.02, pedacos=1):
        self.n = 0; self.dt = dt; self.pedacos = pedacos; self.first = threading.Event()
    def synthesize(self, text):
        self.n += 1; self.first.set()
        for _ in range(self.pedacos):
            time.sleep(self.dt / self.pedacos)
            yield SimpleNamespace(audio_int16_bytes=b"\x00\x01" * 10, sample_rate=16000)


def _fila(monkeypatch, engines):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(jq, "_cfg", lambda: {"queue_unload_ollama": False})
    q = jq.JobQueue(engines=engines, progress_interval=0)
    ev = {"prog": [], "fin": [], "fail": [], "can": []}
    q.progress.connect(lambda i, s, t, pct, eta: ev["prog"].append((s, t, pct)))
    q.finished.connect(lambda i, r: ev["fin"].append(r)); q.failed.connect(lambda i, e: ev["fail"].append(e))
    q.cancelled.connect(lambda i: ev["can"].append(i))
    def pump(cond, timeout=10):
        t = time.time()
        while not cond() and time.time() - t < timeout: app.processEvents(); time.sleep(0.005)
        app.processEvents(); return cond()
    return q, ev, pump


def _falar_eng(tmp_path, voice):
    return {"falar": lambda p, op, cf: ve.speak(p["texto"], tmp_path / "o.wav", op, cf,
                                                 cfg=_cfg(tmp_path), voice_loader=lambda _: voice)}


def test_falar_progresso_por_frase_escala(tmp_path, monkeypatch):
    v = SlowVoice(0.001); q, ev, pump = _fila(monkeypatch, _falar_eng(tmp_path, v))
    texto = " ".join(f"Frase {i}." for i in range(1, 41))
    q.enqueue("falar", {"texto": texto})
    assert pump(lambda: ev["fin"] or ev["fail"]) and not ev["fail"]
    assert [(s, t) for s, t, _ in ev["prog"]] == [(i, 40) for i in range(1, 41)]
    assert ev["prog"][1][2] == pytest.approx(5.0) and ev["prog"][-1][2] == 100.0   # "2 de 40" = 5 %
    q.shutdown()


def test_falar_cancel_para_entre_frases(tmp_path, monkeypatch):
    v = SlowVoice(0.05); q, ev, pump = _fila(monkeypatch, _falar_eng(tmp_path, v))
    jid = q.enqueue("falar", {"texto": " ".join(f"Frase {i}." for i in range(40))})
    assert v.first.wait(5); q.cancel(jid)
    assert pump(lambda: ev["can"]) and not ev["fin"] and not ev["fail"]
    assert q.get(jid)["estado"] == "cancelada" and v.n <= 2
    assert not (tmp_path / "o.wav").exists() and not list(tmp_path.glob("*.part.wav"))
    q.shutdown()


def test_falar_cancel_no_meio_de_frase_longa(tmp_path):
    flag = threading.Event(); v = SlowVoice(1.0, pedacos=50)
    th = threading.Timer(0.1, flag.set); th.start(); t0 = time.time()
    with pytest.raises(Cancelled):
        ve.speak("Uma frase só, bem longa.", tmp_path / "o.wav", None, flag, cfg=_cfg(tmp_path),
                 voice_loader=lambda _: v)
    assert time.time() - t0 < 0.6 and not (tmp_path / "o.wav").exists()


def test_piper_pcm_api_antiga():
    class Old:
        config = SimpleNamespace(sample_rate=22050)
        def synthesize_stream_raw(self, t): yield b"ab"; yield b"cd"
    assert ve._piper_pcm(Old(), "x") == (b"abcd", 22050)


class SlowWhisper:
    def __init__(self, n=40): self.n = n; self.first = threading.Event(); self.segs = 0
    def transcribe(self, path, **kw):
        def gen():
            for i in range(self.n):
                self.segs += 1; self.first.set(); time.sleep(0.03)
                yield SimpleNamespace(start=i * 1.0, end=(i + 1) * 1.0, text=f" s{i}")
        return gen(), SimpleNamespace(duration=float(self.n))


def _tr_eng(tmp_path, w):
    a = tmp_path / "a.wav"; a.write_bytes(b"RIFF")
    monkey = lambda p, op, cf: ve.transcribe(str(a), op, cf, cfg=_cfg(tmp_path), model_loader=lambda *x, **k: w)
    return {"transcrever": monkey}


def test_transcrever_cancel_vira_cancelada(tmp_path, monkeypatch):
    monkeypatch.setattr(ve, "_decode_audio", lambda p: None)
    w = SlowWhisper(); q, ev, pump = _fila(monkeypatch, _tr_eng(tmp_path, w))
    jid = q.enqueue("transcrever", {})
    assert w.first.wait(5); q.cancel(jid)
    assert pump(lambda: ev["can"]) and not ev["fin"] and not ev["fail"]
    assert q.get(jid)["estado"] == "cancelada"
    time.sleep(0.2); assert w.segs < 40
    q.shutdown()
