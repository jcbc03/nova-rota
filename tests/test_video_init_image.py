"""E16: params['init_image'] chega ao sd-cli no Wan 2.2 (motor + fila); V8: negativo vazio -> WAN_NEG no .txt e no sd-cli."""
import os, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from ia_off import sdcpp, engines_registry as er, perf, job_queue as jq
from test_job_queue import app, pump  # noqa: F401


def _cfg(tmp_path, modelo):
    cfg = {"video_modelo": modelo}
    for m in ("wan21", "wan22"):
        for k in sdcpp.WAN_KEYS[m]:
            f = tmp_path / f"{k}.bin"; f.write_bytes(b"x"); cfg[k] = str(f)
    return cfg


@pytest.fixture
def seen(monkeypatch):
    seen = {}
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, **kw):
        a = build_args("sd-cli"); seen["args"] = a
        open(a[a.index("-o") + 1], "wb").write(b"a"); progress_cb(1, 1); return "cpu"
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    monkeypatch.setattr(sdcpp, "to_mp4", lambda s, d, fps: open(d, "wb").write(b"m"))
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg: "cpu")
    return seen


def _run(tmp_path, modelo, **extra):
    return er.gerar_video({"prompt": "x", "saida": str(tmp_path / "v"), "cfg_override": _cfg(tmp_path, modelo), **extra},
                          lambda s, t: None, threading.Event())


def test_wan22_com_imagem(tmp_path, seen):
    img = tmp_path / "i.png"; img.write_bytes(b"x")
    r = _run(tmp_path, "wan22", init_image=str(img))
    a = seen["args"]; assert a[a.index("-i") + 1] == str(img)
    txt = open(os.path.splitext(r)[0] + ".txt", encoding="utf-8").read()
    assert "modelo: wan22" in txt and f"init_image: {img}" in txt


@pytest.mark.parametrize("extra", [{}, {"init_image": ""}, {"init_image": None}, {"init_image": "  "}])
def test_sem_imagem_sem_flag(tmp_path, seen, extra):
    _run(tmp_path, "wan22", **extra)
    assert "-i" not in seen["args"]


def test_wan21_com_imagem_erro(tmp_path, seen):
    img = tmp_path / "i.png"; img.write_bytes(b"x")
    with pytest.raises(ValueError):
        _run(tmp_path, "wan21", init_image=str(img))
    assert "args" not in seen  # sd-cli nem é chamado


def test_imagem_ausente_erro(tmp_path, seen):
    with pytest.raises(FileNotFoundError):
        _run(tmp_path, "wan22", init_image=str(tmp_path / "nao.png"))
    assert "args" not in seen


def test_negativo_vazio_v8(tmp_path, seen):
    r = _run(tmp_path, "wan22", negative="")
    a = seen["args"]; assert a[a.index("-n") + 1] == sdcpp.cli_safe(sdcpp.WAN_NEG, "negativo")
    txt = open(os.path.splitext(r)[0] + ".txt", encoding="utf-8").read()
    assert f"negative: {sdcpp.WAN_NEG}\n" in txt


def test_fila_imagem(app, tmp_path, seen):
    img = tmp_path / "i.png"; img.write_bytes(b"x")
    q = jq.JobQueue(engines={"video": er.gerar_video}, progress_interval=0); done, fail = [], []
    q.finished.connect(lambda *a: done.append(a)); q.failed.connect(lambda *a: fail.append(a))
    q.enqueue("video", {"prompt": "x", "saida": str(tmp_path / "v"), "cfg_override": _cfg(tmp_path, "wan22"),
                        "init_image": str(img)})
    assert pump(app, lambda: done or fail) and done and not fail
    a = seen["args"]; assert a[a.index("-i") + 1] == str(img)
    q.shutdown()


@pytest.mark.parametrize("modelo,nome", [("wan21", "i.png"), ("wan22", "nao.png")])
def test_fila_erro_vira_falha(app, tmp_path, seen, modelo, nome):
    img = tmp_path / nome
    if nome == "i.png": img.write_bytes(b"x")
    q = jq.JobQueue(engines={"video": er.gerar_video}, progress_interval=0); done, fail = [], []
    q.finished.connect(lambda *a: done.append(a)); q.failed.connect(lambda *a: fail.append(a))
    jid = q.enqueue("video", {"prompt": "x", "saida": str(tmp_path / "v"), "cfg_override": _cfg(tmp_path, modelo),
                              "init_image": str(img)})
    assert pump(app, lambda: done or fail) and fail and not done
    assert fail[0][0] == jid and fail[0][1]
    q.shutdown()


def test_fila_cancelar_com_imagem(app, tmp_path, monkeypatch):
    img = tmp_path / "i.png"; img.write_bytes(b"x"); started = threading.Event(); seen = {}
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, **kw):
        seen["args"] = build_args("sd-cli"); started.set(); cancel_flag.wait(10); return "cpu"
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg: "cpu")
    q = jq.JobQueue(engines={"video": er.gerar_video}, progress_interval=0); canc, done = [], []
    q.cancelled.connect(lambda *a: canc.append(a)); q.finished.connect(lambda *a: done.append(a))
    jid = q.enqueue("video", {"prompt": "x", "saida": str(tmp_path / "v"), "cfg_override": _cfg(tmp_path, "wan22"),
                              "init_image": str(img)})
    assert pump(app, started.is_set)
    q.cancel(jid)
    assert pump(app, lambda: canc) and not done and "-i" in seen["args"]
    q.shutdown()
