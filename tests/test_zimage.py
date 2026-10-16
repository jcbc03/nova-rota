"""Z-Image Turbo (sd.cpp): argv, registro do modo e MO1."""
import os, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from ia_off import engines_registry as er, moderador as mod, sdcpp


def _cfg(tmp_path):
    for n in ("z.gguf", "ae.safetensors", "qwen.gguf"): (tmp_path / n).write_bytes(b"x")
    return {"zimage_model": str(tmp_path / "z.gguf"), "zimage_vae": str(tmp_path / "ae.safetensors"),
            "zimage_llm": str(tmp_path / "qwen.gguf"), "threads": 2}


def test_argv_flags(tmp_path):
    c = _cfg(tmp_path)
    a = sdcpp.build_zimage_args("sd-cli", c, "café à noite", "o.png", 1024, 512, 8, 3, 1.0)
    for f, v in (("--diffusion-model", c["zimage_model"]), ("--vae", c["zimage_vae"]), ("--llm", c["zimage_llm"]),
                 ("-p", "cafe a noite"), ("--cfg-scale", "1.0"), ("--steps", "8"), ("-H", "512"), ("-W", "1024"),
                 ("-o", "o.png")):
        assert a[a.index(f) + 1] == v
    assert "-n" not in a and "--diffusion-fa" not in a and "--offload-to-cpu" not in a
    b = sdcpp.build_zimage_args("sd-cli", c, "x", "o.png", negative="borrão", diffusion_fa=True, offload_to_cpu=True)
    assert b[b.index("-n") + 1] == "borrao" and "--diffusion-fa" in b and "--offload-to-cpu" in b
    assert sdcpp.expected_steps(a) == 8


@pytest.mark.parametrize("k", ["zimage_model", "zimage_vae", "zimage_llm"])
def test_caminho_vazio_erro_claro(tmp_path, k):
    c = _cfg(tmp_path); c[k] = ""
    with pytest.raises(ValueError, match=k):
        sdcpp.build_zimage_args("sd-cli", c, "x", "o.png")
    with pytest.raises(ValueError, match=k):
        er.gerar_imagem({"prompt": "x", "modo": "zimage", "saida": str(tmp_path / "o"), "cfg_override": c},
                        lambda s, t: None, threading.Event())


def test_modo_registrado():
    import re, pathlib
    assert "zimage" in er.IMAGE_MODES
    ui = pathlib.Path(er.__file__).with_name("media_tabs.py").read_text(encoding="utf-8")
    assert re.search(r'\("zimage",\s*"Z-Image Turbo \(sd\.cpp\)"\)', ui)


@pytest.fixture
def argv(monkeypatch):
    got = []
    def fake_run(folder, variant, mk, **kw):
        a = mk("sd-cli"); i = a.index("-o"); a[i + 1] = "<out>"; got.append((variant, a)); return variant
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_run)
    return got


def _params(tmp_path, ativa, neg=""):
    c = _cfg(tmp_path); c.update(moderacao_ativa=ativa, moderacao_arquivo=str(tmp_path / "nao_existe.json"))
    return {"prompt": "um gato", "modo": "zimage", "steps": 8, "seed": 7, "negative": neg,
            "saida": str(tmp_path / "out"), "cfg_override": c}


@pytest.mark.parametrize("neg", ["", "feio"])
def test_mo1_zimage(tmp_path, argv, monkeypatch, neg):
    lidos = []
    monkeypatch.setattr(mod, "_carregar", lambda cfg: lidos.append(1) or {})
    p = _params(tmp_path, False, neg)
    er.gerar_imagem(dict(p), lambda s, t: None, threading.Event())
    er.moderado(er.gerar_imagem, "imagem", negativo=True)(dict(p), lambda s, t: None, threading.Event())
    assert len(argv) == 2 and argv[0] == argv[1] and argv[0][0] == "cpu"
    assert lidos == []


def test_ligado_sem_negativo_nao_completa(tmp_path, argv, monkeypatch):
    chamado = []
    monkeypatch.setattr(mod, "completar_negativo", lambda b, c=None: chamado.append(b) or b + ", extra")
    w = er.moderado(er.gerar_imagem, "imagem", negativo=True)
    w(_params(tmp_path, True, ""), lambda s, t: None, threading.Event())
    assert chamado == [] and "-n" not in argv[-1][1]
    w(_params(tmp_path, True, "feio"), lambda s, t: None, threading.Event())
    assert chamado == ["feio"] and argv[-1][1][argv[-1][1].index("-n") + 1] == "feio, extra"
