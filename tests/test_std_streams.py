import sys
import pytest
from ia_off import app

def _zera(monkeypatch):
    for n in ("stdout", "stderr", "__stdout__", "__stderr__"):
        monkeypatch.setattr(sys, n, None)

def test_ensure_std_streams_sem_console(monkeypatch):
    _zera(monkeypatch)
    app.ensure_std_streams()
    for n in ("stdout", "stderr", "__stdout__", "__stderr__"):
        assert getattr(sys, n).isatty() is False
    sys.stderr.write("x"); sys.stdout.write("x")

def test_tqdm_real_sem_console(monkeypatch):
    tqdm = pytest.importorskip("tqdm").tqdm
    _zera(monkeypatch)
    app.ensure_std_streams()
    for _ in tqdm(range(3)):
        pass

def test_transformers_loading_report_sem_console(monkeypatch):
    lr = pytest.importorskip("transformers.utils.loading_report")
    _zera(monkeypatch)
    app.ensure_std_streams()
    import inspect
    style = lr._style
    n = len([p for p in inspect.signature(style).parameters.values()
             if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
    style(*(["x"] * n))  # sem a guarda: AttributeError 'NoneType' object has no attribute 'isatty'
