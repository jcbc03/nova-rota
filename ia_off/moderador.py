"""Moderação opcional de prompts (imagem, vídeo, voz, chat).

Desligada (cfg["moderacao_ativa"] False) = identidade total: nada é lido,
nada é filtrado. Ver docs/MODERADOR_API.md.
"""
import hashlib, hmac, json, logging, os, re, secrets, unicodedata
from pathlib import Path

log = logging.getLogger(__name__)

NIVEIS = ("leve", "medio", "rigido")
CONTEXTOS = ("imagem", "video", "voz", "chat")
PBKDF2_ITER = 240_000

# Listas embutidas. Cada nível acrescenta ao anterior (cumulativo).
PADRAO = {
    "leve": {
        "bloqueados": [
            "pornografia infantil", "child porn", "child pornography", "csam",
            "crianca nua", "menor nua", "menor nu", "menina nua", "menino nu",
            "sexo com crianca", "sexo com menor", "nude child", "naked child",
            "underage sex", "underage nude", "loli", "lolicon", "shota", "shotacon",
            "pedofilia", "pedophilia",
        ],
        "negativos": ["child", "minor", "underage", "childlike"],
    },
    "medio": {
        "bloqueados": [
            "sexo explicito", "sexo oral", "sexo anal", "fazendo sexo", "cena de sexo",
            "explicit sex", "having sex", "sex scene", "oral sex",
            "porno", "pornografia", "pornografico", "porn", "xxx", "nsfw", "hentai", "nudez explicita", "explicit", "explicito", "explicita",
            "estupro", "rape", "gore", "desmembramento", "dismemberment",
            "decapitacao", "decapitation", "tortura", "torture",
        ],
        "negativos": ["nsfw", "nude", "nudity", "explicit", "sexual", "gore",
                      "blood", "mutilation"],
    },
    "rigido": {
        "bloqueados": [
            "sexo", "sex", "sexual",
            "nu", "nua", "nus", "nuas", "nudez", "nude", "naked", "nudity",
            "lingerie", "topless", "seminu", "seminua",
            "sangue", "sangrento", "blood", "bloody", "violencia", "violence",
            "matar", "assassinato", "murder", "kill", "cadaver", "corpse",
            "arma", "armas", "arma de fogo", "gun", "guns", "rifle", "weapon",
            "weapons", "pistola", "pistol", "fuzil",
            "droga", "drogas", "cocaina", "cocaine", "maconha", "marijuana",
            "heroina", "heroin", "crack", "meth", "metanfetamina",
        ],
        "negativos": ["violence", "weapon", "gun", "drugs", "lingerie",
                      "cleavage", "suggestive", "revealing clothes"],
    },
}

INSTRUCOES = {
    "leve": ("Regras de moderação: recuse qualquer conteúdo sexual envolvendo menores "
             "ou conteúdo claramente ilegal."),
    "medio": ("Não produza conteúdo sexual explícito nem violência gráfica (gore)."),
    "rigido": ("Mantenha tudo apropriado para crianças: sem nudez, violência, armas "
               "ou drogas. Recuse educadamente pedidos fora disso."),
}

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s"})


class PromptBloqueado(Exception):
    """Prompt recusado pela moderação. Atributos: motivo, termo, nivel, contexto."""
    def __init__(self, motivo, termo=None, nivel=None, contexto=None):
        super().__init__(motivo)
        self.motivo, self.termo, self.nivel, self.contexto = motivo, termo, nivel, contexto


def _cfg(cfg):
    if cfg is None:
        from ia_off import config
        cfg = config.load()
    return cfg


def ativa(cfg=None):
    return bool(_cfg(cfg).get("moderacao_ativa", False))


def _nivel(cfg):
    n = str(cfg.get("moderacao_nivel", "medio")).lower()
    return n if n in NIVEIS else "medio"


# ---------- normalização / casamento ----------
def _tokens(texto):
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower().translate(_LEET)
    toks = re.findall(r"[a-z0-9]+", t)
    out, run = [], []
    for tk in toks + [None]:
        if tk is not None and len(tk) == 1 and tk.isalpha():
            run.append(tk); continue
        if len(run) >= 3: out.append("".join(run))
        else: out.extend(run)
        run = []
        if tk is not None: out.append(tk)
    return out


def _contem(toks, termo_toks):
    n = len(termo_toks)
    if not n: return False
    return any(toks[i:i + n] == termo_toks for i in range(len(toks) - n + 1))


# ---------- listas ----------
def _validar(d):
    if not isinstance(d, dict): return None
    niveis = d.get("niveis", d)
    if not isinstance(niveis, dict): return None
    for k, v in niveis.items():
        if k not in NIVEIS or not isinstance(v, dict): return None
        for campo in ("bloqueados", "negativos"):
            if campo in v and not (isinstance(v[campo], list) and all(isinstance(x, str) for x in v[campo])):
                return None
    return niveis, bool(d.get("substituir", False))


def _carregar(cfg):
    base = {n: {c: list(PADRAO[n][c]) for c in ("bloqueados", "negativos")} for n in NIVEIS}
    p = cfg.get("moderacao_arquivo")
    if not p or not os.path.isfile(p): return base
    try:
        r = _validar(json.loads(Path(p).read_text(encoding="utf-8")))
    except Exception as e:
        log.warning("moderacao.json inválido (%s): usando listas padrão", e); return base
    if r is None:
        log.warning("moderacao.json com formato errado: usando listas padrão"); return base
    niveis, substituir = r
    for n, v in niveis.items():
        for c in ("bloqueados", "negativos"):
            if c in v:
                base[n][c] = list(v[c]) if substituir else base[n][c] + [x for x in v[c] if x not in base[n][c]]
    return base


def _acumulado(listas, nivel, campo):
    out = []
    for n in NIVEIS[:NIVEIS.index(nivel) + 1]:
        out += [x for x in listas[n][campo] if x not in out]
    return out


def exportar_padrao(path):
    """Grava o moderacao.json padrão (editável) em path."""
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"versao": 1, "substituir": False, "niveis": PADRAO},
                            indent=2, ensure_ascii=False), encoding="utf-8")
    return p


# ---------- API ----------
def checar_prompt(texto, contexto="imagem", cfg=None):
    cfg = _cfg(cfg)
    if not cfg.get("moderacao_ativa", False): return None
    nivel = _nivel(cfg)
    toks = _tokens(texto)
    for termo in _acumulado(_carregar(cfg), nivel, "bloqueados"):
        if _contem(toks, _tokens(termo)):
            raise PromptBloqueado(
                f'Pedido bloqueado pela moderação (nível "{nivel}"): contém o termo "{termo}". '
                f'Reformule o pedido ou ajuste a moderação nas configurações.',
                termo=termo, nivel=nivel, contexto=contexto)
    return None


def completar_negativo(negativo, cfg=None):
    cfg = _cfg(cfg)
    if not cfg.get("moderacao_ativa", False): return negativo
    neg = negativo or ""
    ja = set(t.strip().lower() for t in neg.split(","))
    extras = [t for t in _acumulado(_carregar(cfg), _nivel(cfg), "negativos") if t.lower() not in ja]
    if not extras: return neg
    return (neg.rstrip().rstrip(",") + ", " if neg.strip() else "") + ", ".join(extras)


def instrucoes_chat(cfg=None):
    cfg = _cfg(cfg)
    if not cfg.get("moderacao_ativa", False): return ""
    nivel = _nivel(cfg)
    return " ".join(INSTRUCOES[n] for n in NIVEIS[:NIVEIS.index(nivel) + 1])


# ---------- senha ----------
def _senha_path(cfg):
    return Path(_cfg(cfg)["moderacao_senha_arquivo"])


def senha_definida(cfg=None):
    p = _senha_path(cfg)
    if not p.is_file(): return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return all(k in d for k in ("salt", "hash", "iterations"))
    except Exception as e:
        log.warning("arquivo de senha do moderador ilegível (%s): %s", p, e)
        return False


def _hash(senha, salt, it):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, it)


def _gravar(senha, cfg):
    if not isinstance(senha, str) or not senha:
        raise ValueError("A senha não pode ser vazia.")
    salt = secrets.token_bytes(16)
    p = _senha_path(cfg); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps({"algo": "pbkdf2_hmac_sha256", "iterations": PBKDF2_ITER,
                               "salt": salt.hex(), "hash": _hash(senha, salt, PBKDF2_ITER).hex()}),
                   encoding="utf-8")
    os.replace(tmp, p)


def definir_senha(senha, cfg=None):
    """Define a senha somente se nenhuma existir (senão ValueError; use trocar_senha)."""
    cfg = _cfg(cfg)
    if senha_definida(cfg): raise ValueError("Já existe senha; use trocar_senha.")
    _gravar(senha, cfg)


def verificar_senha(senha, cfg=None):
    p = _senha_path(cfg)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        calc = _hash(str(senha), bytes.fromhex(d["salt"]), int(d["iterations"]))
        return hmac.compare_digest(calc, bytes.fromhex(d["hash"]))
    except FileNotFoundError:
        return False
    except Exception as e:
        log.warning("verificação de senha do moderador falhou (arquivo %s inválido?): %s", p, e)
        return False


def trocar_senha(atual, nova, cfg=None):
    cfg = _cfg(cfg)
    if not verificar_senha(atual, cfg): return False
    _gravar(nova, cfg)
    return True
