"""Testes para flux2_variant (e que Z-Image continua inalterado)."""
import importlib
import inspect
import os

import pytest

from ia_off import config, sdcpp, perf, engines_registry as er


def test_defaults_and_basic(monkeypatch):
    monkeypatch.delenv("IA_OFF_SDCPP_VARIANT", raising=False)
    monkeypatch.delenv("IA_OFF_FLUX2_VULKAN", raising=False)
    importlib.reload(config)
    assert config.DEFAULTS["flux2_vulkan"] is False
    assert sdcpp.flux2_variant({"device": "auto"}, vulkan_ok=True) == "cpu"
    # _env_bool behaviour
    assert config._env_bool("IA_OFF_FLUX2_VULKAN", False) is False


def test_sdcpp_variant_env_precedence(monkeypatch):
    monkeypatch.setenv("IA_OFF_SDCPP_VARIANT", "vulkan")
    assert sdcpp.flux2_variant({"flux2_vulkan": False}, vulkan_ok=False) == "vulkan"
    monkeypatch.setenv("IA_OFF_SDCPP_VARIANT", "cpu")
    assert sdcpp.flux2_variant({"flux2_vulkan": True}, vulkan_ok=True) == "cpu"


def test_flux2_vulkan_cfg(monkeypatch):
    monkeypatch.delenv("IA_OFF_SDCPP_VARIANT", raising=False)
    cfg = {"device": "auto", "flux2_vulkan": True}
    assert sdcpp.flux2_variant(cfg, vulkan_ok=True) == "vulkan"
    assert sdcpp.flux2_variant(cfg, vulkan_ok=False) == "cpu"


def test_flux2_vulkan_via_env_and_reload(monkeypatch):
    monkeypatch.delenv("IA_OFF_SDCPP_VARIANT", raising=False)
    try:
        monkeypatch.setenv("IA_OFF_FLUX2_VULKAN", "1")
        importlib.reload(config)
        assert config.DEFAULTS["flux2_vulkan"] is True
        cfg = dict(config.DEFAULTS, device="auto")
        assert sdcpp.flux2_variant(cfg, vulkan_ok=True) == "vulkan"
    finally:
        monkeypatch.delenv("IA_OFF_FLUX2_VULKAN", raising=False)
        importlib.reload(config)


def test_zimage_unchanged(monkeypatch):
    monkeypatch.delenv("IA_OFF_SDCPP_VARIANT", raising=False)
    monkeypatch.setattr(perf, "has_vulkan", lambda: True)
    # Check source of _zimage still uses the old logic
    src = inspect.getsource(er._zimage)
    assert 'cfg.get("zimage_vulkan")' in src
    assert er._zimage.__code__.co_filename.endswith("engines_registry.py")
    # The expression in _zimage for variant (with has_vulkan=True)
    assert sdcpp.video_variant({"device": "auto"}, True) == "cpu"
    # With zimage_vulkan=True it would use perf
    assert perf.sdcpp_variant({"device": "auto", "zimage_vulkan": True}, True) == "vulkan"