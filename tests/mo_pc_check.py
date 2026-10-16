"""MO1-MO4 e MO6 no PC, sem mexer no config.json nem no moderacao.json do Julio.
Uso (na pasta do app):  python tests\\mo_pc_check.py
Usa cfg em memória; MO6 usa arquivos temporários. Sai com código 0 se tudo passar."""
import json, os, sys, tempfile, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ia_off import moderador as m

ok = True
def check(nome, cond, extra=""):
    global ok
    ok &= bool(cond); print(("OK  " if cond else "FALHA ") + nome + (f"  {extra}" if extra else ""))

def bloqueia(txt, nivel, arq=None):
    cfg = {"moderacao_ativa": True, "moderacao_nivel": nivel, "moderacao_arquivo": arq}
    try: m.checar_prompt(txt, "imagem", cfg); return False
    except m.PromptBloqueado: return True

leve, medio, rigido = "pedofilia", "cena de sexo explicito", "homem com pistola"
normais = ["um gato dormindo no sofa", "paisagem de praia ao por do sol, e a lua",
           "retrato de uma senhora sorrindo", "o e a casa azul", "carro vermelho na estrada"]

# MO1 desligada: nada bloqueia, negativo e instruções intactos
off = {"moderacao_ativa": False, "moderacao_nivel": "rigido"}
check("MO1 desligada nao bloqueia", all(m.checar_prompt(t, "imagem", off) is None for t in (leve, medio, rigido)))
check("MO1 negativo intacto", m.completar_negativo("blurry", off) == "blurry")
check("MO1 sem instrucao no chat", m.instrucoes_chat(off) == "")
# MO2 cumulativo
check("MO2 leve", bloqueia(leve, "leve") and not bloqueia(medio, "leve") and not bloqueia(rigido, "leve"))
check("MO2 medio", bloqueia(leve, "medio") and bloqueia(medio, "medio") and not bloqueia(rigido, "medio"))
check("MO2 rigido", all(bloqueia(t, "rigido") for t in (leve, medio, rigido)))
# MO3 sem falso positivo
falsos = [(t, n) for n in m.NIVEIS for t in normais if bloqueia(t, n)]
check("MO3 sem bloqueio falso", not falsos, str(falsos))
# MO4 burla
check("MO4 acento/maiusc/leet/espacado", all(bloqueia(t, "medio") for t in ("PEDOFÍLIA", "p3d0f1l1a", "p e d o f i l i a", "Cena de SEXO Explícito")))
# MO6 arquivo ausente / quebrado / extra
logging.basicConfig(level=logging.WARNING)
with tempfile.TemporaryDirectory() as d:
    ruim = os.path.join(d, "ruim.json"); open(ruim, "w").write("{ isso nao e json")
    extra = os.path.join(d, "extra.json"); json.dump({"niveis": {"leve": {"bloqueados": ["palavrateste"]}}}, open(extra, "w"))
    check("MO6 arquivo ausente usa padrao", bloqueia(leve, "leve", os.path.join(d, "naoexiste.json")))
    check("MO6 json quebrado usa padrao", bloqueia(leve, "leve", ruim))
    check("MO6 lista extra soma ao padrao", bloqueia("uma palavrateste aqui", "leve", extra) and bloqueia(leve, "leve", extra))
print("RESULTADO:", "TUDO OK" if ok else "HA FALHAS"); sys.exit(0 if ok else 1)
