import sys
from ia_off import app

def test_ensure_std_streams_sem_console(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None); monkeypatch.setattr(sys, "stderr", None)
    app.ensure_std_streams()
    assert sys.stderr.isatty() is False and sys.stdout.isatty() is False
    sys.stderr.write("x"); sys.stdout.write("x")
