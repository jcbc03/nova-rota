"""engines_registry: FLUX.2 usa sdcpp.flux2_variant (CPU por padrão com device auto)."""
import threading

import pytest
from PIL import Image

from ia_off import engines_registry as er, sdcpp, perf


@pytest.mark.parametrize("device", [None, "auto", "Auto"])
def test_flux2_registry_cpu_por_padrao(tmp_path, monkeypatch, device):
    monkeypatch.delenv("IA_OFF_SDCPP_VARIANT", raising=False)
    monkeypatch.delenv("IA_OFF_FLUX2_VULKAN", raising=False)
    # mesmo com Vulkan "disponível", FLUX.2 deve ir de CPU sem flux2_vulkan
    monkeypatch.setattr(perf, "sdcpp_variant", lambda cfg, vulkan_ok=None: "vulkan")
    seen = []
    def fake_rwf(folder, variant, build_args, progress_cb=None, cancel_flag=None, **kw):
        seen.append(variant)
        a = build_args("sd-cli"); Image.new("RGB", (8, 8)).save(a[a.index("-o") + 1])
        return variant
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_rwf)
    cfg = {}
    for k in ("flux2_model", "flux2_vae", "flux2_llm"):
        f = tmp_path / f"{k}.bin"; f.write_bytes(b"x"); cfg[k] = str(f)
    if device is not None:
        cfg["device"] = device
    er.gerar_imagem({"prompt": "x", "modo": "flux2", "batch": 1, "seed": 1, "saida": str(tmp_path),
                     "cfg_override": cfg}, lambda s, t: None, threading.Event())
    assert seen == ["cpu"]
