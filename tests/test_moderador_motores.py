"""Moderador nos motores (engines_registry.moderado). MO1: desligado = idêntico ao anterior."""
import os, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from ia_off import engines_registry as er, moderador as mod, sdcpp


def _wan_params(tmp_path, ativa, neg=""):
    for n in ("m", "t5", "vae"): (tmp_path / n).write_bytes(b"x")
    return {"prompt": "um gato andando", "negative": neg, "seed": 7, "saida": str(tmp_path / "out"),
            "cfg_override": {"wan_model": str(tmp_path / "m"), "wan_t5": str(tmp_path / "t5"),
                             "wan_vae": str(tmp_path / "vae"), "moderacao_ativa": ativa,
                             "moderacao_arquivo": str(tmp_path / "nao_existe.json")}}


@pytest.fixture
def argv(monkeypatch):
    got = []
    def fake_run(folder, variant, mk, **kw):
        a = mk("sd-cli"); i = a.index("-o"); a[i + 1] = "<out>"; got.append(a); return variant
    monkeypatch.setattr(sdcpp, "run_with_fallback", fake_run)
    monkeypatch.setattr(sdcpp, "to_mp4", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sem ffmpeg")))
    return got


@pytest.mark.parametrize("neg", ["", "feio, borrado"])
def test_mo1_desligado_argv_identico(tmp_path, argv, monkeypatch, neg):
    lidos = []
    monkeypatch.setattr(mod, "_carregar", lambda cfg: lidos.append(1) or {})
    p = _wan_params(tmp_path, False, neg)
    er.gerar_video(dict(p), lambda s, t: None, threading.Event())
    er.moderado(er.gerar_video, "video", negativo=True, neg_padrao=er._wan_neg)(dict(p), lambda s, t: None,
                                                                               threading.Event())
    assert len(argv) == 2 and argv[0] == argv[1]
    assert lidos == []  # nenhuma lista/arquivo de moderação lido


def test_mo1_desligado_mesmos_params():
    seen = []
    w = er.moderado(lambda p, a, b: seen.append(p) or "ok", "imagem", negativo=True)
    p = {"prompt": "sexo explícito", "negative": "x", "cfg_override": {"moderacao_ativa": False}}
    assert w(p, None, None) == "ok" and seen[0] is p and p["negative"] == "x"


@pytest.mark.parametrize("ctx,campo", [("imagem", "prompt"), ("video", "prompt"), ("voz", "texto")])
def test_bloqueado_antes_do_motor(tmp_path, ctx, campo):
    chamado = []
    w = er.moderado(lambda *a: chamado.append(1), ctx, campo=campo)
    p = {campo: "pornografia", "cfg_override": {"moderacao_ativa": True, "moderacao_nivel": "medio",
                                                "moderacao_arquivo": str(tmp_path / "x.json")}}
    with pytest.raises(mod.PromptBloqueado) as ei:
        w(p, None, None)
    assert chamado == [] and ei.value.motivo in f"{type(ei.value).__name__}: {ei.value}"
    assert ei.value.contexto == ctx and "bloque" in str(ei.value).lower()


def test_negativo_completado_quando_ligado(tmp_path, argv):
    p = _wan_params(tmp_path, True, "")
    cfg = dict(p["cfg_override"])
    er.moderado(er.gerar_video, "video", negativo=True, neg_padrao=er._wan_neg)(p, lambda s, t: None,
                                                                               threading.Event())
    neg = argv[0][argv[0].index("-n") + 1]
    esperado = sdcpp.cli_safe(mod.completar_negativo(sdcpp.WAN_NEG, cfg), "negativo")
    assert neg == esperado and len(neg) > len(sdcpp.cli_safe(sdcpp.WAN_NEG, "negativo"))
    seen = []
    er.moderado(lambda q, a, b: seen.append(q), "imagem", negativo=True)(
        {"prompt": "gato", "negative": "feio", "cfg_override": cfg}, None, None)
    assert seen[0]["negative"].startswith("feio, ") and len(seen[0]["negative"]) > 6


def test_register_all_envolve(monkeypatch):
    regs = {}
    class Q:
        def register_engine(self, n, f): regs[n] = f
    er.register_all(Q())
    assert regs["imagem"].__wrapped__ is er.gerar_imagem and regs["video"].__wrapped__ is er.gerar_video
    assert regs["falar"].__wrapped__ is er.falar
    assert regs["transcrever"] is er.transcrever and regs["ampliar"] is er.ampliar


def test_wan_neg_padrao_no_argv():
    a = sdcpp.build_wan_args("sd-cli", {"wan_model": "m", "wan_vae": "v", "wan_t5": "t"}, "p", "o.avi", "")
    assert a[a.index("-n") + 1] == sdcpp.cli_safe(sdcpp.WAN_NEG, "negativo")
