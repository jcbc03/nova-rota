"""Parar enquanto o ensure_running ainda espera o Ollama subir: o pedido não pode chegar ao chat_stream."""
import os, sys, tempfile, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"; os.environ["IA_OFF_HOME"] = tempfile.mkdtemp()
from PySide6.QtWidgets import QApplication
from ia_off import app as A
qa = QApplication(sys.argv)
w = A.MainWindow()
chamadas = []
class Fake:
    def ensure_running(self): time.sleep(0.6)
    def chat_stream(self, *a, **k): chamadas.append(a); yield "x"
    def __getattr__(self, n): return lambda *a, **k: []
w.client = Fake()
w.model_box.addItem("fake:1b"); w.model_box.setCurrentText("fake:1b")
w.new_conv(); w.input.setPlainText("oi"); w.send()
assert w.worker is not None
w.stop(); t0 = time.time()
while w.worker is not None and time.time() - t0 < 10: qa.processEvents(); time.sleep(0.01)
assert w.worker is None, "worker não terminou"
assert not chamadas, "pedido chegou ao Ollama depois do Parar"
assert w.send_btn.isEnabled()
print("STOP_ENSURE OK")
