"""Testes do sub2 para o moderador (roteiro MO1-MO6, SE1-SE4)."""
import json, pytest
from ia_off import moderador as M

NORMAIS = ["um gato dormindo no sofá", "paisagem de montanha ao pôr do sol",
           "qual o sexo do bebê", "retrato de mulher, sexo feminino", "e a casa o e a rua",
           "receita de bolo de cenoura", "carro esportivo vermelho na estrada"]

def cfg(tmp_path, ativa=True, nivel="medio", arquivo=None):
    return {"moderacao_ativa": ativa, "moderacao_nivel": nivel,
            "moderacao_arquivo": str(arquivo) if arquivo else str(tmp_path / "nao_existe.json"),
            "moderacao_senha_arquivo": str(tmp_path / "senha.json")}

def bloqueia(texto, c):
    try: M.checar_prompt(texto, "imagem", c); return False
    except M.PromptBloqueado: return True

def test_mo1_desligada_nao_muda_nada(tmp_path):
    c = cfg(tmp_path, ativa=False)
    for t in NORMAIS + ["cena de sexo explícito", "arma com sangue"]:
        assert M.checar_prompt(t, "video", c) is None
    for neg in ["", "blurry, low quality", None]:
        assert M.completar_negativo(neg, c) == neg
    assert M.instrucoes_chat(c) == ""

def test_mo1_desligada_nao_le_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "_carregar", lambda *a: pytest.fail("leu as listas desligada"))
    c = cfg(tmp_path, ativa=False)
    M.checar_prompt("qualquer coisa", "imagem", c); M.completar_negativo("x", c)

def test_mo2_niveis_sao_crescentes(tmp_path):
    listas = M._carregar(cfg(tmp_path))
    termos = set()
    for n in M.NIVEIS: termos |= set(listas[n]["bloqueados"])
    for t in termos:
        res = [bloqueia(t, cfg(tmp_path, nivel=n)) for n in M.NIVEIS]
        assert res == sorted(res), (t, res)   # se bloqueia num nível, bloqueia nos seguintes
    assert bloqueia(M.PADRAO["leve"]["bloqueados"][0], cfg(tmp_path, nivel="leve"))

@pytest.mark.parametrize("nivel", ["leve", "medio"])
def test_mo3_normais_passam(tmp_path, nivel):
    for t in NORMAIS:
        assert not bloqueia(t, cfg(tmp_path, nivel=nivel)), t

def test_mo4_burla_e_letras_curtas(tmp_path):
    c = cfg(tmp_path, nivel="medio")
    termo = next(t for t in M.PADRAO["medio"]["bloqueados"] + M.PADRAO["leve"]["bloqueados"]
                 if " " not in t and len(t) >= 4)
    assert bloqueia(termo.upper(), c)
    assert bloqueia(" ".join(termo), c)          # letras separadas por espaço
    assert not bloqueia("e a o e a", c)          # letras curtas normais não colam em termo

def test_mo5_erro_tem_motivo(tmp_path):
    c = cfg(tmp_path, nivel="rigido")
    with pytest.raises(M.PromptBloqueado) as e:
        M.checar_prompt("uma arma", "video", c)
    assert "bloque" in e.value.motivo.lower() and e.value.nivel == "rigido" and e.value.contexto == "video"

@pytest.mark.parametrize("conteudo", ["{ isso não é json", '["lista"]', '{"niveis": {"medio": {"bloqueados": "x"}}}'])
def test_mo6_json_ruim_usa_padrao(tmp_path, conteudo):
    p = tmp_path / "moderacao.json"; p.write_text(conteudo, encoding="utf-8")
    c = cfg(tmp_path, arquivo=p)
    assert M._carregar(c)["medio"]["bloqueados"] == list(M.PADRAO["medio"]["bloqueados"])
    M.checar_prompt("um gato", "imagem", c)

def test_mo6_json_soma_e_substitui(tmp_path):
    p = tmp_path / "moderacao.json"
    p.write_text(json.dumps({"niveis": {"leve": {"bloqueados": ["abacaxi"]}}}), encoding="utf-8")
    assert bloqueia("um abacaxi", cfg(tmp_path, nivel="leve", arquivo=p))
    p.write_text(json.dumps({"substituir": True, "niveis": {n: {"bloqueados": []} for n in M.NIVEIS}}), encoding="utf-8")
    assert not bloqueia("uma arma", cfg(tmp_path, nivel="rigido", arquivo=p))

def test_se1_cria_e_guarda_so_hash(tmp_path):
    c = cfg(tmp_path)
    assert not M.senha_definida(c)
    M.definir_senha("Segredo123", c)
    txt = (tmp_path / "senha.json").read_text()
    assert "Segredo123" not in txt and M.senha_definida(c)
    d = json.loads(txt); assert d["iterations"] >= 100_000 and len(d["salt"]) >= 32
    with pytest.raises(ValueError): M.definir_senha("outra", c)
    with pytest.raises(ValueError): M.definir_senha("", cfg(tmp_path / "x"))

def test_se2_se3_errada_e_certa(tmp_path):
    c = cfg(tmp_path); M.definir_senha("abc", c)
    assert not M.verificar_senha("abd", c) and not M.verificar_senha("", c)
    assert M.verificar_senha("abc", c)
    assert not M.trocar_senha("errada", "nova", c) and M.verificar_senha("abc", c)
    assert M.trocar_senha("abc", "nova", c) and M.verificar_senha("nova", c)

def test_se4_apagar_arquivo_reseta(tmp_path):
    c = cfg(tmp_path); M.definir_senha("abc", c)
    (tmp_path / "senha.json").unlink()
    assert not M.senha_definida(c) and not M.verificar_senha("abc", c)
    M.definir_senha("nova", c); assert M.verificar_senha("nova", c)

def test_se_arquivo_corrompido_nao_libera(tmp_path):
    c = cfg(tmp_path); (tmp_path / "senha.json").write_text("lixo")
    assert not M.senha_definida(c) and not M.verificar_senha("lixo", c)
