"""Faz executáveis externos (sd-cli.exe) acharem vcomp140.dll (OpenMP do MSVC).

env_para_exe(exe) devolve uma cópia do ambiente com PATH prefixado pelas pastas
que contêm vcomp140.dll. Nunca levanta exceção; inofensivo fora do Windows.
"""
import importlib.util, logging, os, sys
from pathlib import Path

log = logging.getLogger(__name__)
DLL = "vcomp140.dll"
_avisado = False


def _win():
    return os.name == "nt"


def _norm(d):
    d = os.path.normpath(str(d))
    return os.path.normcase(d) if _win() else d


def _cfg_dir(cfg):
    try:
        if cfg is None:
            from ia_off import config
            cfg = config.load()
        return (os.environ.get("IA_OFF_VCRUNTIME_DIR") or cfg.get("vcruntime_dir") or "").strip()
    except Exception:
        return os.environ.get("IA_OFF_VCRUNTIME_DIR", "")


def _pkg_dir(nome):
    try:
        spec = importlib.util.find_spec(nome)  # não importa o Qt
        if spec and spec.submodule_search_locations:
            return list(spec.submodule_search_locations)
        if spec and spec.origin:
            return [str(Path(spec.origin).parent)]
    except Exception:
        pass
    return []


def candidatos(exe_path, cfg=None):
    """Pastas candidatas, em ordem de prioridade."""
    out = []
    try:
        if exe_path: out.append(str(Path(exe_path).parent))
    except Exception:
        pass
    d = _cfg_dir(cfg)
    if d: out.append(d)
    for pkg in ("PySide6", "shiboken6"):
        out += _pkg_dir(pkg)
    try:
        out.append(str(Path(sys.executable).parent))
    except Exception:
        pass
    return out


def _tem_dll(d):
    try:
        return (Path(d) / DLL).is_file()
    except Exception:
        return False


def _pastas_com_dll(exe_path, cfg=None):
    vistos, out = set(), []
    for d in candidatos(exe_path, cfg):
        k = _norm(d)
        if k in vistos: continue
        vistos.add(k)
        if _tem_dll(d): out.append(d)
    return out


def achar_vcomp(exe_path, cfg=None):
    """Primeira vcomp140.dll encontrada (Path) ou None."""
    try:
        ds = _pastas_com_dll(exe_path, cfg)
        return Path(ds[0]) / DLL if ds else None
    except Exception:
        return None


def _no_system32():
    root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT")
    return bool(root) and _tem_dll(Path(root) / "System32")


def env_para_exe(exe_path, base_env=None, cfg=None):
    """Cópia de base_env (padrão os.environ) com PATH prefixado pelas pastas com vcomp140.dll."""
    global _avisado
    env = dict(os.environ if base_env is None else base_env)
    try:
        chave = next((k for k in env if k.upper() == "PATH"), "PATH") if _win() else "PATH"
        atual = env.get(chave, "")
        no_path = {_norm(p) for p in atual.split(os.pathsep) if p}
        dirs = _pastas_com_dll(exe_path, cfg)
        novos = [d for d in dirs if _norm(d) not in no_path]
        if novos:
            env[chave] = os.pathsep.join(novos + ([atual] if atual else []))
        if not dirs and not _no_system32() and not _avisado:
            _avisado = True
            log.warning("vcomp140.dll (OpenMP do MSVC) não encontrada para %s: o sd-cli pode falhar "
                        "com 0xC0000135. Instale o Microsoft Visual C++ Redistributable 2015-2022 (x64) "
                        "ou defina 'vcruntime_dir' nas configurações (ou env IA_OFF_VCRUNTIME_DIR).", exe_path)
    except Exception as e:
        log.debug("env_para_exe: %s", e)
    return env
