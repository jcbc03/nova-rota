import pytest
from ia_off import engines_registry as R, sdcpp, perf

def _roda(monkeypatch, cfg, env=None):
    monkeypatch.delenv("IA_OFF_SDCPP_VARIANT", raising=False); monkeypatch.delenv("IA_OFF_FLUX2_VULKAN", raising=False)
    for k, v in (env or {}).items(): monkeypatch.setenv(k, v)
    monkeypatch.setattr(perf, "sdcpp_variant", lambda *a, **k: "vulkan")  # Auto numa máquina com Vulkan
    monkeypatch.setattr(R, "_require", lambda *a, **k: None)
    pegou = []
    def fake_run(d, variant, mk, **kw): pegou.append(variant); return variant
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_run)
    R._flux2({}, cfg, __import__("pathlib").Path("/tmp"), "x", 64, 64, 4, 1, 1, 1.0, "t", lambda s: {}, lambda *a: None, None)
    return pegou[0]

def test_flux2_vai_pra_cpu_no_auto(monkeypatch):
    assert _roda(monkeypatch, {"device": "auto"}) == "cpu"

def test_flux2_vulkan_so_quando_ligado(monkeypatch):
    assert _roda(monkeypatch, {"device": "auto", "flux2_vulkan": True}) == "vulkan"

def test_env_manda(monkeypatch):
    assert _roda(monkeypatch, {"device": "auto"}, {"IA_OFF_SDCPP_VARIANT": "vulkan"}) == "vulkan"

def test_media_tabs_usa_flux2_variant():
    import inspect
    from ia_off import media_tabs as M
    src = inspect.getsource(M.ImageTab._flux2)
    assert "sdcpp.flux2_variant(cfg)" in src and "perf.sdcpp_variant(cfg)" not in src
