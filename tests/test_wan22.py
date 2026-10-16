import os, threading, logging
from ia_off import sdcpp, engines_registry as er, perf

def _files(tmp_path, keys):
    d = {}
    for k in keys:
        f = tmp_path / f"{k}.bin"; f.write_bytes(b"x"); d[k] = str(f)
    return d

def test_wan21_padrao_identico():
    cfg = {"wan_model": "m", "wan_vae": "v", "wan_t5": "t", "wan22_model": "M2"}
    assert sdcpp.build_wan_args("sd", cfg, "p", "o.avi") == sdcpp.build_wan_args("sd", cfg, "p", "o.avi", modelo="wan21")
    a = sdcpp.build_wan_args("sd", cfg, "p", "o.avi")
    assert a[a.index("--diffusion-model") + 1] == "m" and a[a.index("--vae") + 1] == "v"

def test_wan22_escolhido(tmp_path):
    cfg = _files(tmp_path, sdcpp.WAN_KEYS["wan21"] + sdcpp.WAN_KEYS["wan22"]); cfg["video_modelo"] = "wan22"
    assert sdcpp.wan_modelo(cfg) == "wan22"
    a = sdcpp.build_wan_args("sd", cfg, "p", "o.avi")
    assert a[a.index("--diffusion-model") + 1] == cfg["wan22_model"]
    assert a[a.index("--vae") + 1] == cfg["wan22_vae"] and a[a.index("--t5xxl") + 1] == cfg["wan22_t5"]

def test_wan22_faltando_volta_21(tmp_path, caplog):
    cfg = _files(tmp_path, sdcpp.WAN_KEYS["wan21"] + ("wan22_model", "wan22_t5"))
    cfg.update(video_modelo="wan22", wan22_vae=str(tmp_path / "nao.safetensors"))
    with caplog.at_level(logging.WARNING):
        assert sdcpp.wan_modelo(cfg) == "wan21"
    assert "wan22_vae" in caplog.text
    a = sdcpp.build_wan_args("sd", cfg, "p", "o.avi")
    assert a[a.index("--diffusion-model") + 1] == cfg["wan_model"]

def test_gerar_video_wan22(tmp_path, monkeypatch):
    seen = {}
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, **kw):
        a = build_args("sd-cli"); seen["a"] = a; open(a[a.index("-o") + 1], "wb").write(b"avi"); return "cpu"
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    monkeypatch.setattr(sdcpp, "to_mp4", lambda s, d, fps: (seen.__setitem__("fps", fps), open(d, "wb").write(b"m")))
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg: "cpu")
    cfg = _files(tmp_path, sdcpp.WAN_KEYS["wan22"]); cfg["video_modelo"] = "wan22"  # sem wan_* : não exige 2.1
    r = er.gerar_video({"prompt": "gato", "seed": 1, "saida": str(tmp_path / "v"), "cfg_override": cfg},
                       lambda s, t: None, threading.Event())
    a = seen["a"]
    assert os.path.isfile(r) and a[a.index("--diffusion-model") + 1] == cfg["wan22_model"]
    assert a[a.index("--fps") + 1] == "24" and seen["fps"] == 24
    assert a[a.index("--cfg-scale") + 1] == "6.0" and a[a.index("--flow-shift") + 1] == "3.0"
    assert a[a.index("--sampling-method") + 1] == "euler"
