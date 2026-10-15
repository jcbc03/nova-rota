"""Teste de estresse offscreen: jobs longos com progresso rápido, cancelamento, segundo job,
chat em streaming, vídeo com subprocesso falso e fechamento da janela durante a execução.
Todos os callbacks de UI devem rodar na thread principal. O processo deve sair com código 0."""
import os, sys, tempfile, threading, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"; os.environ["IA_OFF_HOME"] = tempfile.mkdtemp()
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from ia_off import app as A, jobs
from ia_off.image_engine import Cancelled

QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)
MAIN = threading.main_thread(); bad = []; seen = {"prog": 0, "chunks": 0, "video_lines": 0}
def on_main(tag):
    if threading.current_thread() is not MAIN: bad.append(tag)

class FakeEngine:
    cfg = {}; last_backend = "fake"
    def generate(self, mode, prompt, steps=4, batch=1, progress_cb=None, cancel_flag=None, **kw):
        total = 3000
        for i in range(total):
            if cancel_flag is not None and cancel_flag.is_set(): raise Cancelled()
            if progress_cb: progress_cb(i + 1, total)
            time.sleep(0.0005)
        from PIL import Image
        return [(1, Image.new("RGB", (64, 64)))]

qa = QApplication(sys.argv); A.install_diagnostics()
qa.aboutToQuit.connect(lambda: jobs.shutdown_all(8000))
w = A.MainWindow(); w.show()
from ia_off import engines_registry
engines_registry._image_engine[0] = FakeEngine()   # motor único da fila (a aba não tem motor próprio)
vt = w.video_tab
it = w.image_tab; it.tr_chk.setChecked(False); it.prompt.setPlainText("gato")
results = []
def _prog(jid, *a):
    on_main("prog"); seen["prog"] += 1
    if jid in vt._jobs: seen["video_lines"] += 1
w.fila.progress.connect(_prog)
w.fila.finished.connect(lambda jid, p: (on_main("done"), results.append("ok")))
w.fila.failed.connect(lambda jid, m: (on_main("fail"), results.append(m)))
w.fila.cancelled.connect(lambda jid: (on_main("cancel"), results.append("Cancelado.")))

# chat com streaming falso e rápido
def fake_stream(model, msgs, opts, stop_flag=lambda: False):
    for k in range(5000):
        if stop_flag(): return
        yield f"t{k} "
w.client.chat_stream = fake_stream; w.client.ensure_running = lambda *a: True
orig_render = w.render
def render(partial=None): on_main("render"); seen["chunks"] += 1; orig_render(partial)
w.render = render
w.model_box.addItem("fake"); w.model_box.setCurrentText("fake")

# vídeo: sd.cpp falso (subprocesso python que imprime progresso muito rápido)
from ia_off import sdcpp, perf
fake = os.path.join(os.environ["IA_OFF_HOME"], "fake_sd.py")
open(fake, "w").write("import sys,time\nfor i in range(1,100000):\n sys.stdout.write(f'\\r|==> | {i}/99999 - 0.01s/it')\n if i%500==0: print('linha de log', i)\n")
real_rwf = sdcpp.run_with_fallback
sdcpp.run_with_fallback = lambda folder, variant, mk, *a, **kw: \
    real_rwf(folder, "cpu", lambda b: [sys.executable, fake], *a, **dict(kw, ensure=lambda *x: fake))
for k in ("wan_model", "wan_t5", "wan_vae"): w.cfg[k] = fake
vt.prompt.setPlainText("um gato"); vt.tr_chk.setChecked(False)

steps = []
def step(fn, ms): steps.append((fn, ms))
step(lambda: it.generate(), 0)                       # 1º job de imagem
step(lambda: it.cancel(), 400)                       # cancela no meio
step(lambda: it.generate(), 900)                     # 2º job
step(lambda: (w.input.setPlainText("oi"), w.send()), 950)  # chat em paralelo
step(lambda: w.stop(), 1600)                         # para o chat
step(lambda: vt.generate(), 1700)                    # vídeo (subprocesso)
step(lambda: vt.cancel_queue(), 2600)               # cancela vídeo pela fila (mata o processo)
step(lambda: vt.generate(), 3200)                    # vídeo de novo
step(lambda: it.generate(), 3300)                    # e imagem de novo
step(lambda: w.close(), 3600)                        # fecha com tudo rodando
step(lambda: qa.quit(), 3700)
for fn, ms in steps: QTimer.singleShot(ms, fn)
QTimer.singleShot(30000, lambda: (print("TIMEOUT"), os._exit(3)))
qa.exec()
assert not bad, f"callbacks fora da thread principal: {set(bad)}"
assert "Cancelado." in results, results
assert seen["prog"] > 20 and seen["chunks"] >= 2 and seen["video_lines"] > 0, seen  # a fila agrupa o progresso (~10/s) e o vídeo espera a imagem
assert not jobs.running(), "threads ainda rodando"
print("STRESS OK", seen, results)
