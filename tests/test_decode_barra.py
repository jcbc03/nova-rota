"""O decode do Wan chega como passos depois da fase 'decodificando'; a barra não pode voltar pra 'Passo x/y'."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QStatusBar

class _Sig:
    def connect(self, *a): pass

class _FilaFalsa:
    def __getattr__(self, n): return _Sig()
    def enqueue(self, *a): return "j1"
    def cancel(self, j): pass

def test_passos_do_decode_nao_sobrescrevem_rotulo():
    QApplication.instance() or QApplication([])
    from ia_off.media_tabs import VideoTab
    t = VideoTab(lambda: {}, QStatusBar()); t.set_queue(_FilaFalsa())
    t._jobs = {"j1"}; t._dec_info = {"j1": {"chave": "decode_rate_video_wan22", "un": 1}}
    t._q_progress("j1", 2, 4, 50, 60)
    assert t.bar.format().startswith("Passo 2/4")
    t._q_phase("j1", "decodificando")
    t._q_progress("j1", 1, 4, 25, 1620)
    assert t.bar.format().startswith("Decodificando")
    t._q_end("j1")
    assert "j1" not in getattr(t, "_fases", {})
