import os, sys, logging, tempfile
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
import pytest
from ia_off import runtime_dlls as R


def _dll(d):
    d.mkdir(parents=True, exist_ok=True); (d / "vcomp140.dll").write_bytes(b"x"); return d


@pytest.fixture(autouse=True)
def isolar(monkeypatch, tmp_path):
    monkeypatch.delenv("IA_OFF_VCRUNTIME_DIR", raising=False)
    monkeypatch.setenv("SystemRoot", str(tmp_path / "win"))
    monkeypatch.setattr(R, "_pkg_dir", lambda n: [])
    monkeypatch.setattr(R.sys, "executable", str(tmp_path / "py" / "python"))
    monkeypatch.setattr(R, "_avisado", False)


def test_ordem(tmp_path, monkeypatch):
    exe = _dll(tmp_path / "sdcpp") / "sd-cli.exe"
    cfgd = _dll(tmp_path / "vc")
    pys = _dll(tmp_path / "pyside")
    py = _dll(tmp_path / "py")
    monkeypatch.setattr(R, "_pkg_dir", lambda n: [str(pys)] if n == "PySide6" else [])
    env = R.env_para_exe(exe, {"PATH": "/usr/bin"}, cfg={"vcruntime_dir": str(cfgd)})
    assert env["PATH"].split(os.pathsep) == [str(exe.parent), str(cfgd), str(pys), str(py), "/usr/bin"]
    assert R.achar_vcomp(exe, cfg={}) == exe.parent / "vcomp140.dll"


def test_pula_sem_dll_e_dedupe(tmp_path, monkeypatch):
    exe = (tmp_path / "semdll" / "sd-cli.exe")
    vc = _dll(tmp_path / "vc")
    monkeypatch.setattr(R, "_pkg_dir", lambda n: [str(vc)])  # PySide6 e shiboken6 = mesma pasta
    base = {"PATH": os.pathsep.join(["/bin", str(vc)])}
    env = R.env_para_exe(exe, base, cfg={"vcruntime_dir": str(vc)})
    assert env["PATH"] == base["PATH"]  # já estava no PATH
    env = R.env_para_exe(exe, {"PATH": ""}, cfg={"vcruntime_dir": str(vc) + os.sep})
    assert env["PATH"] == str(vc) or env["PATH"] == str(vc) + os.sep


def test_env_override(tmp_path, monkeypatch):
    a, b = _dll(tmp_path / "a"), _dll(tmp_path / "b")
    monkeypatch.setenv("IA_OFF_VCRUNTIME_DIR", str(b))
    env = R.env_para_exe(tmp_path / "x" / "sd.exe", {}, cfg={"vcruntime_dir": str(a)})
    assert env["PATH"] == str(b)


def test_config_key():
    from ia_off import config
    assert "vcruntime_dir" in config.DEFAULTS


def test_nao_achou_avisa_uma_vez(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        e1 = R.env_para_exe(tmp_path / "x.exe", {"PATH": "/bin"}, cfg={})
        R.env_para_exe(tmp_path / "x.exe", {"PATH": "/bin"}, cfg={})
    assert e1 == {"PATH": "/bin"} and R.achar_vcomp(tmp_path / "x.exe", cfg={}) is None
    ws = [r for r in caplog.records if "vcomp140" in r.message]
    assert len(ws) == 1 and "Redistributable" in ws[0].message


def test_system32_sem_aviso(tmp_path, caplog):
    _dll(tmp_path / "win" / "System32")
    with caplog.at_level(logging.WARNING):
        R.env_para_exe(tmp_path / "x.exe", {"PATH": "/bin"}, cfg={})
    assert not caplog.records


def test_base_env_intacto_e_nunca_levanta(tmp_path):
    exe = _dll(tmp_path / "s") / "sd.exe"
    base = {"PATH": "/bin", "X": "1"}
    env = R.env_para_exe(exe, base, cfg={})
    assert base == {"PATH": "/bin", "X": "1"} and env["X"] == "1" and env is not base
    assert R.env_para_exe(None, {}, cfg=None) is not None
    assert R.env_para_exe(object(), None, cfg={}) is not None


def test_pkg_dir_real_sem_importar_qt():
    import importlib
    importlib.reload(R)  # restaura _pkg_dir real
    mods = set(sys.modules)
    R._pkg_dir("PySide6"); R._pkg_dir("pacote_que_nao_existe")
    assert "PySide6.QtCore" not in set(sys.modules) - mods
