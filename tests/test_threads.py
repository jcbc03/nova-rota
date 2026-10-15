import os, subprocess, sys, threading, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def _run(script):
    env = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM="offscreen", IA_OFF_HOME=tempfile.mkdtemp())
    return subprocess.run([sys.executable, str(ROOT / "tests" / script)], env=env, capture_output=True, text=True, timeout=120)

def test_stress_gui_exits_cleanly():
    r = _run("stress_gui.py")
    assert r.returncode == 0, (r.returncode, r.stdout[-2000:], r.stderr[-3000:])
    assert "STRESS OK" in r.stdout

def test_smoke_gui_exits_cleanly():
    r = _run("smoke_gui.py")
    assert r.returncode == 0, (r.returncode, r.stderr[-3000:])

def test_run_bg_callbacks_on_main_thread():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    from ia_off.app import run_bg
    from PySide6.QtCore import QObject
    app = QApplication.instance() or QApplication([])
    owner = QObject(); where = []; text = []
    def fn(j):
        for k in range(200): j.chunk.emit(str(k))
        return "fim"
    run_bg(owner, fn, on_chunk=lambda c: (text.append(c), where.append(threading.current_thread() is threading.main_thread())),
           on_done=lambda r: (where.append(threading.current_thread() is threading.main_thread()), app.quit()))
    app.exec()
    assert len(where) >= 2 and all(where)  # pedaços podem ser agrupados (throttle)
    assert "".join(text) == "".join(str(k) for k in range(200))  # nada perdido

def test_sdcpp_cancel_without_output(tmp_path):
    """Processo que não imprime nada deve ser morto pelo cancelamento."""
    import time, pytest
    from ia_off import sdcpp
    p = tmp_path / "sleep.py"; p.write_text("import time; time.sleep(60)")
    flag = {"c": False}; t0 = time.time()
    threading.Timer(0.5, lambda: flag.update(c=True)).start()
    with pytest.raises(RuntimeError, match="Cancelado"):
        sdcpp.run([sys.executable, str(p)], cancelled=lambda: flag["c"])
    assert time.time() - t0 < 5
