"""voice_engine com Whisper/Piper falsos (sem modelos reais)."""
import sys, threading, wave
from types import SimpleNamespace
import pytest
from ia_off import voice_engine as ve, engines_registry as er
from ia_off.engine_api import Cancelled


def cfg(tmp_path, **kw):
    return {"voz_dir": str(tmp_path / "voz"), "whisper_model": "small", "whisper_lang": "pt",
            "piper_voice": "pt_BR-faber-medium", "piper_exe": "", "threads": 2, **kw}


class FakeWhisper:
    def __init__(self, flag=None): self.flag = flag; self.kw = None
    def transcribe(self, path, **kw):
        self.kw = kw
        def gen():
            for i, t in enumerate(["Olá,", "tudo bem?", "Até logo."]):
                if self.flag and i == 1: self.flag.set()
                yield SimpleNamespace(start=i * 2.0, end=(i + 1) * 2.0, text=" " + t)
        return gen(), SimpleNamespace(duration=6.0)


class FakeVoice:
    config = SimpleNamespace(sample_rate=16000)
    def __init__(self): self.said = []
    def synthesize(self, text):
        self.said.append(text)
        yield SimpleNamespace(audio_int16_bytes=b"\x00\x01" * 100, sample_rate=16000)


def audio(tmp_path):
    a = tmp_path / "a.wav"; a.write_bytes(b"RIFF"); return a


def test_paths_from_config(tmp_path):
    c = cfg(tmp_path)
    assert ve.whisper_model_dir(c) == tmp_path / "voz" / "whisper" / "faster-whisper-small"
    assert ve.piper_voice_path(c) == tmp_path / "voz" / "piper" / "pt_BR-faber-medium.onnx"
    from ia_off import config
    for k in ("voz_dir", "whisper_model", "whisper_lang", "piper_voice", "piper_exe"):
        assert k in config.DEFAULTS


def test_transcribe(tmp_path):
    got = []; fw = FakeWhisper()
    t = ve.transcribe(audio(tmp_path), lambda s, n: got.append((s, n)), cfg=cfg(tmp_path), model_loader=lambda d, th: fw)
    assert t == "Olá, tudo bem? Até logo." and fw.kw["language"] == "pt"
    assert got == [(2, 6), (4, 6), (6, 6), (6, 6)]


def test_transcribe_cancel_e_faltando(tmp_path):
    flag = threading.Event()
    with pytest.raises(Cancelled):
        ve.transcribe(audio(tmp_path), cancel_flag=flag, cfg=cfg(tmp_path), model_loader=lambda d, th: FakeWhisper(flag))
    with pytest.raises(FileNotFoundError, match="Whisper"):
        ve.transcribe(audio(tmp_path), cfg=cfg(tmp_path))
    with pytest.raises(FileNotFoundError):
        ve.transcribe(tmp_path / "nao.wav", cfg=cfg(tmp_path))


def test_speak(tmp_path):
    v = FakeVoice(); got = []
    out = ve.speak("Olá mundo. Tudo bem?\nTchau!", tmp_path / "o" / "f.wav", lambda s, n: got.append((s, n)),
                   cfg=cfg(tmp_path), voice_loader=lambda p: v)
    assert v.said == ["Olá mundo.", "Tudo bem?", "Tchau!"] and got == [(1, 3), (2, 3), (3, 3)]
    with wave.open(out) as w:
        assert w.getframerate() == 16000 and w.getnframes() == 300 and w.getsampwidth() == 2


def test_speak_cancel_nao_deixa_arquivo(tmp_path):
    flag = threading.Event(); out = tmp_path / "f.wav"
    with pytest.raises(Cancelled):
        ve.speak("Um. Dois. Três.", out, lambda s, n: flag.set(), flag, cfg=cfg(tmp_path), voice_loader=lambda p: FakeVoice())
    assert not out.exists() and not list(tmp_path.glob("*.part.wav"))
    with pytest.raises(ValueError):
        ve.speak("   ", out, cfg=cfg(tmp_path), voice_loader=lambda p: FakeVoice())
    with pytest.raises(FileNotFoundError, match="Piper"):
        ve.speak("oi", out, cfg=cfg(tmp_path))


def test_split_sentences():
    assert ve.split_sentences("a. b!  c") == ["a.", "b!", "c"]
    assert all(len(s) <= 10 for s in ve.split_sentences("palavra " * 20, max_len=10))


FAKE_PIPER = """import sys, wave, pathlib, time
d = pathlib.Path(sys.argv[sys.argv.index('--output_dir') + 1]); slow = 'slow' in sys.argv[0]
for i, line in enumerate(sys.stdin.read().splitlines()):
    if slow: time.sleep(5)
    with wave.open(str(d / f'{i:03d}.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b'\\0\\0' * 10)
"""


def _exe(tmp_path, name):
    py = tmp_path / f"{name}.py"; py.write_text(FAKE_PIPER)
    if sys.platform == "win32":
        pytest.skip("teste do piper.exe falso só em POSIX")
    sh = tmp_path / name; sh.write_text(f"#!/bin/sh\nexec {sys.executable} {py} \"$@\"\n"); sh.chmod(0o755)
    return str(sh)


def _voice_files(tmp_path):
    d = tmp_path / "voz" / "piper"; d.mkdir(parents=True)
    (d / "pt_BR-faber-medium.onnx").write_bytes(b"x"); (d / "pt_BR-faber-medium.onnx.json").write_text("{}")


def test_speak_piper_exe(tmp_path):
    _voice_files(tmp_path); got = []
    out = ve.speak("Um. Dois.", tmp_path / "e.wav", lambda s, n: got.append((s, n)),
                   cfg=cfg(tmp_path, piper_exe=_exe(tmp_path, "piper")))
    with wave.open(out) as w: assert w.getnframes() == 20
    assert got[-1] == (2, 2)


def test_speak_piper_exe_cancel(tmp_path):
    import time
    _voice_files(tmp_path); flag = threading.Event(); threading.Timer(0.5, flag.set).start(); t0 = time.time()
    with pytest.raises(Cancelled):
        ve.speak("Um. Dois.", tmp_path / "e.wav", cancel_flag=flag, cfg=cfg(tmp_path, piper_exe=_exe(tmp_path, "slow")))
    assert time.time() - t0 < 4


def test_queue_adapters(tmp_path, monkeypatch):
    seen = {}
    def fake_tr(a, pcb, cf, cfg):
        seen["cfg"] = cfg; pcb(1, 1); return "texto ok"
    monkeypatch.setattr(ve, "transcribe", fake_tr)
    got = []
    r = er.transcrever({"audio": str(audio(tmp_path)), "idioma": "en", "modelo": "base", "saida": str(tmp_path / "t")},
                       lambda s, n: got.append((s, n)), threading.Event())
    assert open(r, encoding="utf-8").read() == "texto ok" and got == [(1, 1)]
    assert seen["cfg"]["whisper_lang"] == "en" and seen["cfg"]["whisper_model"] == "base"
    monkeypatch.setattr(ve, "speak", lambda t, w, pcb, cf, cfg: (seen.update(voz=cfg["piper_voice"], wav=w), str(w))[1])
    r = er.falar({"texto": "oi", "voz": "pt_BR-edresson-low", "arquivo": str(tmp_path / "x.wav")}, lambda s, n: None,
                 threading.Event())
    assert r.endswith("x.wav") and seen["voz"] == "pt_BR-edresson-low"
    for fn, bad in ((er.transcrever, {}), (er.falar, {"texto": " "})):
        with pytest.raises(ValueError):
            fn(bad, lambda s, n: None, threading.Event())


def test_espeak_data_dir_copia_quando_caminho_tem_acento(tmp_path):
    from ia_off import voice_engine as ve
    src = tmp_path / "Área" / "espeak-ng-data"; src.mkdir(parents=True); (src / "phontab").write_bytes(b"x")
    voz = tmp_path / "voz"; voz.mkdir()
    d = ve.espeak_data_dir(voz / "v.onnx", src=src)
    if not str(voz).isascii():
        return
    assert d == voz / "espeak-ng-data" and (d / "phontab").read_bytes() == b"x"
    ok = tmp_path / "ascii"; ok.mkdir()
    assert ve.espeak_data_dir(voz / "v.onnx", src=ok) is None


class SlowChunkWhisper:
    """Cada trecho leva 'delay' s (como um decode de 30 s na CPU); conta trechos processados."""
    def __init__(self, delay): self.delay = delay; self.calls = 0; self.prompts = []
    def transcribe(self, chunk, **kw):
        import time
        self.calls += 1; self.prompts.append(kw.get("initial_prompt")); time.sleep(self.delay)
        n = self.calls
        return iter([SimpleNamespace(start=0.0, end=1.0, text=f" t{n}")]), SimpleNamespace(duration=10.0)


def test_transcribe_em_trechos(tmp_path):
    import numpy as np
    fw = SlowChunkWhisper(0); got = []
    arr = np.zeros(25 * ve.SAMPLE_RATE, dtype=np.float32)   # 25 s -> 3 trechos
    t = ve.transcribe(audio(tmp_path), lambda s, n: got.append((s, n)), cfg=cfg(tmp_path),
                      model_loader=lambda d, th: fw, audio_loader=lambda p: arr)
    assert t == "t1 t2 t3" and fw.calls == 3 and fw.prompts[0] is None and fw.prompts[1] == "t1"
    assert got == [(10, 25), (20, 25), (25, 25), (25, 25)]


def test_transcribe_cancel_rapido_no_meio_do_trecho(tmp_path):
    import numpy as np, time
    fw = SlowChunkWhisper(3.0); flag = threading.Event()
    arr = np.zeros(120 * ve.SAMPLE_RATE, dtype=np.float32)
    threading.Timer(0.5, flag.set).start(); t0 = time.time()
    with pytest.raises(Cancelled):
        ve.transcribe(audio(tmp_path), cancel_flag=flag, cfg=cfg(tmp_path),
                      model_loader=lambda d, th: fw, audio_loader=lambda p: arr)
    assert time.time() - t0 < 1.5
    time.sleep(3.2); assert fw.calls == 1   # a thread parou no fim do trecho em andamento


def test_transcribe_cancel_durante_carga_do_modelo(tmp_path):
    import time
    flag = threading.Event(); threading.Timer(0.3, flag.set).start(); t0 = time.time()
    with pytest.raises(Cancelled):
        ve.transcribe(audio(tmp_path), cancel_flag=flag, cfg=cfg(tmp_path),
                      model_loader=lambda d, th: (time.sleep(3), FakeWhisper())[1], audio_loader=lambda p: None)
    assert time.time() - t0 < 1.5
