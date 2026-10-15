"""Adaptadores da fila (engines_registry) com motores falsos; nada de modelos reais."""
import os, threading, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication
from ia_off import engines_registry as er, job_queue as jq, sdcpp, perf
from ia_off.engine_api import Cancelled


@pytest.fixture(scope="module")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


class FakeImageEngine:
    def __init__(self, cfg): self.cfg = cfg; self.calls = []
    def generate(self, mode, prompt, steps=4, batch=1, seed=-1, width=64, height=64,
                 progress_cb=None, cancel_flag=None, **kw):
        self.calls.append(dict(mode=mode, prompt=prompt, steps=steps, batch=batch, **kw))
        out = []
        for b in range(batch):
            for i in range(steps):
                if cancel_flag is not None and cancel_flag.is_set(): raise Cancelled()
                progress_cb(b * steps + i + 1, steps * batch)
            out.append((seed + b, Image.new("RGB", (width, height))))
        return out


@pytest.fixture
def fake_engine(monkeypatch):
    eng = FakeImageEngine({})
    monkeypatch.setattr(er, "_image_engine", [eng])
    return eng


def test_imagem_txt2img(tmp_path, fake_engine):
    got = []
    r = er.gerar_imagem({"prompt": "gato", "steps": 2, "batch": 2, "seed": 5, "width": 32, "height": 32,
                         "saida": str(tmp_path)}, lambda s, t: got.append((s, t)), threading.Event())
    assert r.endswith("_txt2img_5.png") and os.path.isfile(r)
    assert len(list(tmp_path.glob("*.png"))) == 2
    assert got == [(1, 4), (2, 4), (3, 4), (4, 4)]
    with Image.open(r) as im: assert im.text["prompt"] == "gato"


def test_imagem_img2img_e_validacao(tmp_path, fake_engine):
    init = tmp_path / "in.png"; Image.new("RGB", (8, 8)).save(init)
    r = er.gerar_imagem({"prompt": "x", "modo": "img2img", "init_image": str(init), "strength": 0.3,
                         "saida": str(tmp_path)}, lambda s, t: None, threading.Event())
    assert os.path.isfile(r) and fake_engine.calls[-1]["strength"] == 0.3
    assert fake_engine.calls[-1]["init_image"].size == (8, 8)
    for bad in ({}, {"prompt": "x", "modo": "zzz"}, {"prompt": "x", "modo": "img2img"},
                {"prompt": "x", "modo": "inpaint", "init_image": str(init)}):
        with pytest.raises(ValueError):
            er.gerar_imagem({**bad, "saida": str(tmp_path)}, lambda s, t: None, threading.Event())


def test_imagem_cancel(tmp_path, fake_engine):
    flag = threading.Event(); flag.set()
    with pytest.raises(Cancelled):
        er.gerar_imagem({"prompt": "x", "saida": str(tmp_path)}, lambda s, t: None, flag)


def _wan_cfg(tmp_path):
    files = {}
    for k in ("wan_model", "wan_t5", "wan_vae", "flux2_model", "flux2_vae", "flux2_llm"):
        f = tmp_path / f"{k}.bin"; f.write_bytes(b"x"); files[k] = str(f)
    return files


def test_video(tmp_path, monkeypatch):
    seen = {}
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, **kw):
        args = build_args("sd-cli"); seen["args"] = args
        out = args[args.index("-o") + 1]; open(out, "wb").write(b"avi")
        for i in range(1, 4): progress_cb(i, 3)
        return "cpu"
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    monkeypatch.setattr(sdcpp, "to_mp4", lambda src, dst, fps: open(dst, "wb").write(b"mp4"))
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg: "cpu")
    got = []
    r = er.gerar_video({"prompt": "um gato", "frames": 18, "seed": 3, "saida": str(tmp_path / "v"),
                        "cfg_override": _wan_cfg(tmp_path)}, lambda s, t: got.append((s, t)), threading.Event())
    assert r.endswith("_wan_3.mp4") and os.path.isfile(r) and got[-1] == (3, 3)
    a = seen["args"]; assert a[a.index("--video-frames") + 1] == "17"
    assert a[a.index("--diffusion-model") + 1].endswith("wan_model.bin")


def test_video_arquivos_faltando(tmp_path):
    with pytest.raises(FileNotFoundError):
        er.gerar_video({"prompt": "x", "saida": str(tmp_path), "cfg_override": {"wan_model": str(tmp_path / "nao")}},
                       lambda s, t: None, threading.Event())


def test_flux2_progresso_por_lote(tmp_path, monkeypatch):
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, **kw):
        a = build_args("sd-cli"); Image.new("RGB", (8, 8)).save(a[a.index("-o") + 1])
        for i in range(1, 3): progress_cb(i, 2)
        return variant
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg: "cpu")
    got = []
    r = er.gerar_imagem({"prompt": "x", "modo": "flux2", "batch": 2, "seed": 1, "saida": str(tmp_path),
                         "cfg_override": _wan_cfg(tmp_path)}, lambda s, t: got.append((s, t)), threading.Event())
    assert r.endswith("_flux2_1.png") and got == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_register_all_na_fila(app, tmp_path, fake_engine):
    q = jq.JobQueue(progress_interval=0)
    try:
        er.register_all(q)
        ev = []
        q.progress.connect(lambda *a: ev.append(("progress",) + a))
        q.finished.connect(lambda *a: ev.append(("finished",) + a))
        jid = q.enqueue("imagem", {"prompt": "gato", "steps": 3, "saida": str(tmp_path)})
        end = time.time() + 5
        while time.time() < end and not any(e[0] == "finished" for e in ev):
            app.processEvents(); time.sleep(0.01)
        fin = [e for e in ev if e[0] == "finished"]
        assert fin and fin[0][1] == jid and os.path.isfile(fin[0][2])
        last = [e for e in ev if e[0] == "progress"][-1]
        assert last[2:4] == (3, 3) and last[4] == 100.0
        assert q._engine("video") is er.gerar_video
    finally:
        q.shutdown(wait=True, timeout=5)


def test_register_all_global(monkeypatch):
    monkeypatch.setattr(jq, "_ENGINES", {})
    er.register_all()
    assert jq.engines() == {"imagem": er.gerar_imagem, "video": er.gerar_video}
