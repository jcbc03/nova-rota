"""Ampliador (upscaler.py) com modelos falsos: emendas do tiling, progresso, cancelamento, fallback."""
import os, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication
from ia_off import upscaler as up, job_queue as jq
from ia_off.engine_api import Cancelled


def blur_up(scale=4, radius=2):
    """Modelo falso com campo receptivo `radius`: média (2r+1)^2 com borda replicada + vizinho mais próximo."""
    def run(x):
        c = x[0]; k = 2 * radius + 1
        p = np.pad(c, ((0, 0), (radius, radius), (radius, radius)), mode="edge")
        acc = sum(p[:, dy:dy + c.shape[1], dx:dx + c.shape[2]] for dy in range(k) for dx in range(k)) / (k * k)
        return acc.repeat(scale, 1).repeat(scale, 2)[None].astype(np.float32)
    return run


def rnd(w, h, seed=0):
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)


@pytest.mark.parametrize("tile,scale", [(16, 4), (23, 2), (64, 4)])
def test_tiling_sem_emendas(tile, scale):
    a = rnd(70, 45); run = blur_up(scale)
    whole = up.upscale_array(a, run, scale, tile=10_000, pad=0)
    tiled = up.upscale_array(a, run, scale, tile=tile, pad=4)
    assert tiled.shape == (45 * scale, 70 * scale, 3)
    assert np.array_equal(whole, tiled)


def test_sem_margem_aparece_emenda():
    a = rnd(64, 64); run = blur_up(4)
    assert not np.array_equal(up.upscale_array(a, run, 4, tile=10_000, pad=0),
                              up.upscale_array(a, run, 4, tile=16, pad=0))


def test_progresso_por_bloco():
    got = []
    up.upscale_array(rnd(50, 30), blur_up(2), 2, tile=16, pad=4, on_progress=lambda i, n: got.append((i, n)))
    assert got == [(i, 8) for i in range(1, 9)]          # ceil(50/16)=4 x ceil(30/16)=2


def test_cancel_entre_blocos():
    ev = threading.Event(); calls = []
    def run(x):
        calls.append(1)
        if len(calls) == 2: ev.set()
        return blur_up(2)(x)
    with pytest.raises(Cancelled):
        up.upscale_array(rnd(64, 64), run, 2, tile=16, cancel_flag=ev)
    assert len(calls) == 2


def test_ampliar_x2_com_modelo_4x(tmp_path):
    src = tmp_path / "a.png"; Image.fromarray(rnd(40, 30)).save(src)
    got = []
    out = up.ampliar({"entrada": str(src), "escala": 2, "saida": str(tmp_path / "o.png"), "tile": 16},
                     lambda i, n: got.append((i, n)), threading.Event(), runner=blur_up(4))
    with Image.open(out) as im:
        assert im.size == (80, 60) and "real-esrgan" in im.text["upscaler"]
    assert got[-1] == (6, 6) and up.ULTIMO_FALLBACK[0] is None


def test_ampliar_alpha_e_pasta(tmp_path):
    src = tmp_path / "t.png"; Image.new("RGBA", (20, 10), (1, 2, 3, 128)).save(src)
    out = up.ampliar({"entrada": str(src), "escala": 4, "saida": str(tmp_path / "sub")}, None, None, runner=blur_up(4))
    assert out.endswith("_x4.png") and os.path.dirname(out) == str(tmp_path / "sub")
    with Image.open(out) as im:
        assert im.mode == "RGBA" and im.size == (80, 40)


def test_fallback_lanczos_sinalizado(tmp_path):
    src = tmp_path / "a.jpg"; Image.fromarray(rnd(30, 20)).save(src)
    got = []
    out = up.ampliar({"entrada": str(src), "escala": 4, "saida": str(tmp_path),
                      "cfg_override": {"upscale_model": str(tmp_path / "nao_existe.onnx")}},
                     lambda i, n: got.append((i, n)), threading.Event())
    assert "_lanczos" in out and got == [(1, 1)]
    with Image.open(out) as im:
        assert im.size == (120, 80) and im.text["upscaler"].startswith("lanczos (fallback")
    assert "nao_existe" in up.ULTIMO_FALLBACK[0]


def test_params_invalidos(tmp_path):
    src = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(src)
    with pytest.raises(ValueError):
        up.ampliar({"entrada": str(src), "escala": 3}, None, None, runner=blur_up(4))
    with pytest.raises(FileNotFoundError):
        up.ampliar({"entrada": str(tmp_path / "x.png")}, None, None)


def test_na_fila_progresso_e_cancel(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    src = tmp_path / "a.png"; Image.fromarray(rnd(64, 64)).save(src)
    gate = threading.Event()
    def slow(x):
        gate.wait(2); return blur_up(4)(x)
    q = jq.JobQueue(engines={"ampliar": lambda p, op, cf: up.ampliar(p, op, cf, runner=slow)}, progress_interval=0)
    ev = {"prog": [], "fin": [], "can": []}
    q.progress.connect(lambda i, s, t, pct, eta: ev["prog"].append((s, t)))
    q.finished.connect(lambda i, r: ev["fin"].append(r)); q.cancelled.connect(lambda i: ev["can"].append(i))
    j1 = q.enqueue("ampliar", {"entrada": str(src), "escala": 4, "tile": 32, "saida": str(tmp_path)})
    gate.set()
    import time
    t = time.time()
    while not ev["fin"] and time.time() - t < 10: app.processEvents(); time.sleep(0.01)
    assert ev["fin"] and (4, 4) in ev["prog"]
    gate.clear()
    j2 = q.enqueue("ampliar", {"entrada": str(src), "escala": 4, "tile": 16, "saida": str(tmp_path)})
    time.sleep(0.2); q.cancel(j2); gate.set()
    t = time.time()
    while not ev["can"] and time.time() - t < 10: app.processEvents(); time.sleep(0.01)
    assert ev["can"] == [j2]
    q.shutdown()
