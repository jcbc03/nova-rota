import time
from PySide6.QtWidgets import QApplication, QWidget, QProgressBar, QPushButton, QStatusBar
from ia_off.media_tabs import QueueClient

app = QApplication.instance() or QApplication([])

class Tab(QWidget, QueueClient):
    def __init__(self):
        super().__init__(); self.bar = QProgressBar(); self.status = QStatusBar()
        self.gen_btn = QPushButton(); self.cancel_btn = QPushButton(); self._jobs = {"j1"}
    def cfg(self): return {}

def test_falta_desce_e_pct_anda_entre_passos(monkeypatch):
    t = [100.0]; monkeypatch.setattr(time, "monotonic", lambda: t[0])
    w = Tab(); w._q_progress("j1", 1, 4, 25.0, 30.0)
    assert "falta 30s" in w.bar.format() and "25%" in w.bar.format()
    t[0] += 5; w._show_progress()
    f = w.bar.format()
    assert "falta 25s" in f and "Passo 1/4" in f
    assert w.bar.value() > 250  # andou além de 25%
    t[0] += 60; w._show_progress()
    assert "quase lá" in w.bar.format() and w.bar.value() < 500  # não passa do próximo passo
    w._q_progress("j1", 2, 4, 50.0, 20.0)
    assert "falta 20s" in w.bar.format() and w.bar.value() == 500

def test_tick_para_no_cancelar_e_no_fim(monkeypatch):
    w = Tab(); w._q_progress("j1", 1, 4, 25.0, 30.0)
    assert w._prog_timer().isActive()
    w._cancelando = {"j1"}; w._show_progress()
    assert not w._prog_timer().isActive()

def test_passo_unico_mostra_tempo_decorrido(monkeypatch):
    t = [10.0]; monkeypatch.setattr(time, "monotonic", lambda: t[0])
    w = Tab(); w._tipos = {"j1": "ampliar"}
    w._q_started("j1"); t[0] += 7; w._show_progress()
    assert w.bar.format() == "Processando… 7s" and w._prog_timer().isActive()
    w._q_progress("j1", 1, 1, 100.0, 0.0)
    assert "Passo 1/1" in w.bar.format()

def test_carregando_modelo_conta_tempo(monkeypatch):
    t = [0.0]; monkeypatch.setattr(time, "monotonic", lambda: t[0])
    w = Tab(); w._tipos = {"j1": "imagem"}
    w._q_started("j1"); t[0] += 12; w._show_progress()
    assert w.bar.format() == "Carregando modelo… 12s"
