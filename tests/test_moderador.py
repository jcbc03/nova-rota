import os, json, logging, tempfile, builtins
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
import pytest
from ia_off import moderador as M
from ia_off import config


def cfg(tmp_path, ativa=True, nivel="medio"):
    return {"moderacao_ativa": ativa, "moderacao_nivel": nivel,
            "moderacao_arquivo": str(tmp_path / "moderacao.json"),
            "moderacao_senha_arquivo": str(tmp_path / "sub" / "senha.json")}


NORMAIS = [
    "Uma paisagem de montanhas ao pôr do sol, estilo aquarela",
    "Retrato de um gato laranja dormindo no sofá",
    "Explique a diferença entre sexta e sétima nota musical",
    "O nuance da luz na nuvem sobre Essex e Sussex",
    "Descreva a sexualidade? não; descreva a sexta-feira na praça e a numeração das casas",
    "Um carro esportivo vermelho na estrada, e a ponte ao fundo",
    "A banda tocou o show e o público aplaudiu",
    "Escreva um poema sobre a armadura do cavaleiro e o armário da avó",
    "Receita de bolo de cenoura com cobertura de chocolate",
]


def test_config_defaults():
    d = config.DEFAULTS
    assert d["moderacao_ativa"] is False and d["moderacao_nivel"] == "medio"
    assert d["moderacao_arquivo"].endswith("moderacao.json")
    assert d["moderacao_senha_arquivo"].endswith("moderacao_senha.json")


def test_off_identity_no_reads(tmp_path, monkeypatch):
    c = cfg(tmp_path, ativa=False)
    M.exportar_padrao(c["moderacao_arquivo"])
    orig = builtins.open
    def boom(*a, **k): raise AssertionError("leitura de arquivo com moderação desligada")
    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(M, "_carregar", lambda *_: (_ for _ in ()).throw(AssertionError()))
    for txt in ["sexo explícito gore", "pornografia infantil"]:
        assert M.checar_prompt(txt, "imagem", c) is None
    neg = "blurry, low quality"
    assert M.completar_negativo(neg, c) is neg
    assert M.completar_negativo(None, c) is None
    assert M.instrucoes_chat(c) == "" and M.ativa(c) is False
    monkeypatch.setattr(builtins, "open", orig)


@pytest.mark.parametrize("nivel", M.NIVEIS)
def test_normais_passam(tmp_path, nivel):
    c = cfg(tmp_path, nivel=nivel)
    for t in NORMAIS:
        for ctx in M.CONTEXTOS:
            assert M.checar_prompt(t, ctx, c) is None, t


def _bloq(c, t):
    try: M.checar_prompt(t, "imagem", c); return False
    except M.PromptBloqueado: return True


def test_niveis_cumulativos(tmp_path):
    casos = {"pornografia infantil": "leve", "foto sexo explícito": "medio", "homem com uma arma": "rigido"}
    for t, min_n in casos.items():
        for n in M.NIVEIS:
            esperado = M.NIVEIS.index(n) >= M.NIVEIS.index(min_n)
            assert _bloq(cfg(tmp_path, nivel=n), t) == esperado, (t, n)
    negs = [set(M.completar_negativo("", cfg(tmp_path, nivel=n)).split(", ")) for n in M.NIVEIS]
    assert negs[0] < negs[1] < negs[2]
    ins = [M.instrucoes_chat(cfg(tmp_path, nivel=n)) for n in M.NIVEIS]
    assert all(ins) and ins[1].startswith(ins[0]) and ins[2].startswith(ins[1])


def test_completar_negativo_formato(tmp_path):
    c = cfg(tmp_path, nivel="leve")
    r = M.completar_negativo("blurry, child", c)
    assert r.startswith("blurry, child, ") and r.count("child") == 1 + r.count("childlike")


def test_evasao(tmp_path):
    c = cfg(tmp_path, nivel="medio")
    for t in ["SEXO EXPLÍCITO", "séxo explicito na praia", "s e x o explicito", "fazendo S E X O agora", "s3x0 0r4l", "P0RN0GR4F1A", "GÓRE"]:
        assert _bloq(c, t), t
    assert _bloq(cfg(tmp_path, nivel="leve"), "Pornografia Infântil")


def test_letras_soltas_nao_coladas():
    assert "oe" not in M._tokens("eu e a o e tu")
    assert M._tokens("ele e a mãe") == ["ele", "e", "a", "mae"]
    assert M._tokens("o e") == ["o", "e"]
    assert M._tokens("s e x o") == ["sexo"]


def test_motivo(tmp_path):
    with pytest.raises(M.PromptBloqueado) as e:
        M.checar_prompt("cena de gore", "video", cfg(tmp_path))
    ex = e.value
    assert "gore" in ex.motivo and ex.termo == "gore" and ex.nivel == "medio" and ex.contexto == "video"
    assert str(ex) == ex.motivo


def test_json_invalido(tmp_path, caplog):
    c = cfg(tmp_path)
    (tmp_path / "moderacao.json").write_text("{nao é json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert _bloq(c, "gore") and not _bloq(c, "bolo")
    assert any("moderacao" in r.message for r in caplog.records)
    caplog.clear()
    (tmp_path / "moderacao.json").write_text(json.dumps({"niveis": {"medio": {"bloqueados": "x"}}}))
    with caplog.at_level(logging.WARNING):
        assert _bloq(c, "gore")
    assert caplog.records


def test_arquivo_estende_e_exporta(tmp_path):
    c = cfg(tmp_path, nivel="medio")
    p = M.exportar_padrao(c["moderacao_arquivo"])
    d = json.loads(p.read_text(encoding="utf-8"))
    d["niveis"]["leve"]["bloqueados"].append("palavra proibida")
    p.write_text(json.dumps(d), encoding="utf-8")
    assert _bloq(c, "uma Palavra Proibida aqui") and _bloq(c, "pornografia")
    assert not _bloq(cfg(tmp_path, nivel="leve"), "pornografia")
    p.write_text(json.dumps({"substituir": True, "niveis": {"medio": {"bloqueados": []}}}))
    assert not _bloq(c, "pornografia") and _bloq(c, "pornografia infantil")


def test_senha(tmp_path):
    c = cfg(tmp_path)
    assert not M.senha_definida(c)
    with pytest.raises(ValueError): M.definir_senha("", c)
    M.definir_senha("Segredo#123", c)
    p = tmp_path / "sub" / "senha.json"
    raw = p.read_text(encoding="utf-8")
    assert "Segredo#123" not in raw
    d = json.loads(raw)
    assert d["iterations"] >= 200000 and len(bytes.fromhex(d["salt"])) == 16 and d["algo"]
    assert M.senha_definida(c)
    assert M.verificar_senha("Segredo#123", c) and not M.verificar_senha("errada", c)
    assert not M.verificar_senha("", c)
    with pytest.raises(ValueError): M.definir_senha("outra", c)
    assert not M.trocar_senha("errada", "nova", c)
    with pytest.raises(ValueError): M.trocar_senha("Segredo#123", "", c)
    assert M.trocar_senha("Segredo#123", "nova", c) and M.verificar_senha("nova", c)
    p.unlink()
    assert not M.senha_definida(c) and not M.verificar_senha("nova", c)
    M.definir_senha("recomeço", c)
    assert M.verificar_senha("recomeço", c)


def test_sexo_neutro_passa_leve_medio(tmp_path):
    for n in ("leve", "medio"):
        c = cfg(tmp_path, nivel=n)
        for t in ["sexo feminino", "Sexo masculino", "qual o sexo do bebê?", "sex: female"]:
            assert not _bloq(c, t), (n, t)
    c = cfg(tmp_path, nivel="medio")
    for t in ["cena de sexo explícito", "pornografia", "having sex", "xxx"]:
        assert _bloq(c, t), t
    assert _bloq(cfg(tmp_path, nivel="rigido"), "sexo feminino")
