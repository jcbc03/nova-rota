import os, sys, tempfile
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
from pathlib import Path
import pytest
from ia_off import perf, sdcpp

def test_backend_selection():
    assert perf.sd_backend({"device": "cpu"}, gpu_ok=True) == "torch"
    assert perf.sd_backend({"device": "auto"}, gpu_ok=True) == "ov:GPU"
    assert perf.sd_backend({"device": "auto"}, gpu_ok=False) == "torch"
    assert perf.sd_backend({"device": "openvino"}, gpu_ok=False) == "ov:GPU"
    assert perf.sd_backend({"device": "openvino_cpu"}) == "ov:CPU"
    assert perf.sdcpp_variant({"device": "auto"}, vulkan_ok=True) == "vulkan"
    assert perf.sdcpp_variant({"device": "vulkan"}, vulkan_ok=False) == "cpu"
    assert perf.sdcpp_variant({"device": "openvino"}, vulkan_ok=True) == "cpu"

def test_threads_env():
    assert perf.effective_threads({"max_mode": True, "threads": 2}) == perf.LOGICAL
    assert perf.effective_threads({"max_mode": False, "threads": 2}) == 2
    perf.apply({"max_mode": False, "threads": 3})
    assert os.environ["OMP_NUM_THREADS"] == "3" and os.environ["MKL_NUM_THREADS"] == "3"
    import torch; assert torch.get_num_threads() == 3
    perf.apply({"max_mode": True})

def test_vulkan_asset_and_find(tmp_path):
    assert sdcpp.BASE_URL + sdcpp.ASSETS["vulkan"] == \
        "https://github.com/leejet/stable-diffusion.cpp/releases/download/master-964-1d0a58a/sd-master-1d0a58a-bin-win-vulkan-x64.zip"
    (tmp_path / "sd-cli.exe").write_text("cpu"); (tmp_path / "vulkan").mkdir(); (tmp_path / "vulkan" / "sd-cli.exe").write_text("vk")
    assert sdcpp.find_binary(tmp_path, "cpu").read_text() == "cpu"
    assert sdcpp.find_binary(tmp_path, "vulkan").read_text() == "vk"

def _fake(tmp_path, name, code):
    p = tmp_path / name; p.write_text(code); return p

def test_vulkan_fallback(tmp_path):
    vk = _fake(tmp_path, "vk.py", "import sys; print('ggml_vulkan: device lost'); sys.exit(3)")
    cpu = _fake(tmp_path, "cpu.py", "import sys; sys.stdout.write('\\r| 2/2 - 1s/it'); print()")
    ens = lambda folder, variant, *a: vk if variant == "vulkan" else cpu
    logs, prog = [], []
    used = sdcpp.run_with_fallback(None, "vulkan", lambda b: [sys.executable, str(b)],
                                   on_line=lambda s: prog.append(sdcpp.parse_progress(s)), log=logs.append, ensure=ens)
    assert used == "cpu" and (2, 2) in prog and any("Vulkan falhou" in l for l in logs)
    ok = _fake(tmp_path, "ok.py", "print('ok')")
    assert sdcpp.run_with_fallback(None, "vulkan", lambda b: [sys.executable, str(ok)], ensure=ens) == "vulkan"

def test_ov_fallback_to_torch(monkeypatch):
    if not Path("/tmp/tinysd").exists(): pytest.skip("modelo tiny ausente")
    from ia_off import image_engine as IE
    class Boom:
        def __init__(self, *a, **k): pass
        def pipeline(self, *a, **k): raise RuntimeError("GPU device not found")
    import ia_off.ov_engine as OE; monkeypatch.setattr(OE, "OVEngine", Boom)
    monkeypatch.setattr(perf, "has_openvino_gpu", lambda: True)
    e = IE.ImageEngine({"sd15_path": "/tmp/tinysd", "device": "auto", "lcm_lora_path": "x"}); logs = []
    r = e.generate("txt2img", "cat", width=64, height=64, steps=2, lcm=False, log=logs.append)
    assert r and e.last_backend == "torch" and e.ov_failed and any("Voltando para CPU" in l for l in logs)
    assert e.resolve_backend("txt2img") == "torch"

def test_ov_cpu_real(tmp_path, monkeypatch):
    pytest.importorskip("optimum.intel")
    if not Path("/tmp/tinysd").exists(): pytest.skip("modelo tiny ausente")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from ia_off.image_engine import ImageEngine
    e = ImageEngine({"sd15_path": "/tmp/tinysd", "inpaint_path": "/tmp/tinysd", "lcm_lora_path": "x"}); logs = []
    for g in (1.0, 7.5):
        r = e.generate("txt2img", "cat", width=64, height=64, steps=2, guidance=g, batch=2, lcm=False, backend="ov:CPU", log=logs.append)
        assert len(r) == 2 and e.last_backend == "ov:CPU"
    assert any((tmp_path / "IA_Off_v1" / "ov_cache").glob("sd15_base_*/unet/openvino_model.xml"))
    e.generate("img2img", "dog", width=64, height=64, steps=4, guidance=7.5, init_image=r[0][1], lcm=False, backend="ov:CPU", log=logs.append)
    assert e.last_backend == "ov:CPU" and sum("exportando" in l for l in logs) == 1
