"""Fase 'decodificando' após o último passo do sd-cli (QT_QPA_PLATFORM=offscreen)."""
import os, sys, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from ia_off import sdcpp, engines_registry as er, perf, job_queue as jq
from test_job_queue import app, pump  # noqa: F401

CLI = ("import sys\n"
    "print('[INFO] loading vae from x')\n"
    "for i in range(1,4):\n    sys.stdout.write(f'\\r  |==> | {i}/3 - 2.0s/it'); sys.stdout.flush()\nprint()\n"
    "print('[INFO] decoding 1 latents')\nprint('[INFO] decode_first_stage completed')\n"
    "print('[INFO] save result to o.avi')\n")

def test_run_emite_fases(tmp_path):
    f = tmp_path / "cli.py"; f.write_text(CLI); ev = []
    sdcpp.run([sys.executable, str(f), "--steps", "3"], progress_cb=lambda s, t: ev.append((s, t)),
              phase_cb=ev.append)
    assert ev == [(1, 3), (2, 3), (3, 3), "decodificando", "salvando"]

def test_run_sem_phase_cb_igual(tmp_path):
    f = tmp_path / "cli.py"; f.write_text(CLI); got = []
    sdcpp.run([sys.executable, str(f), "--steps", "3"], progress_cb=lambda s, t: got.append((s, t)))
    assert got == [(1, 3), (2, 3), (3, 3)]

def test_gerar_video_repasse_fase(tmp_path, monkeypatch):
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, phase_cb=None, **kw):
        a = build_args("sd-cli"); open(a[a.index("-o") + 1], "wb").write(b"a")
        progress_cb(1, 1); phase_cb("decodificando"); return "cpu"
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    monkeypatch.setattr(sdcpp, "to_mp4", lambda s, d, fps: open(d, "wb").write(b"m"))
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg: "cpu")
    cfg = {}
    for k in sdcpp.WAN_KEYS["wan21"]:
        p = tmp_path / k; p.write_bytes(b"x"); cfg[k] = str(p)
    ev = []
    def prog(s, t): ev.append((s, t))
    prog.phase = ev.append
    er.gerar_video({"prompt": "x", "saida": str(tmp_path / "v"), "cfg_override": cfg}, prog, threading.Event())
    assert ev == [(1, 1), "decodificando", "convertendo"]

def test_fila_sinal_phase(app):
    def eng(params, on_progress, cancel_flag):
        on_progress(2, 2); getattr(on_progress, "phase")("decodificando"); return "/tmp/x.mp4"
    q = jq.JobQueue(engines={"video": eng}, progress_interval=0); got = []
    q.phase.connect(lambda jid, f: got.append((jid, f)))
    done = []; q.finished.connect(lambda *a: done.append(a))
    jid = q.enqueue("video", {})
    assert pump(app, lambda: done)
    assert got == [(jid, "decodificando")]
    q.shutdown()
