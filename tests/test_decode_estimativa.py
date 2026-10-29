"""F7: estimativa da decodificação usa o tempo do mesmo tamanho/quadros antes da taxa proporcional."""
import time
from ia_off.media_tabs import QueueClient


class _W:
    def setRange(self, *a): pass
    def setFormat(self, *a): pass
    def showMessage(self, *a): pass


class _T:
    def start(self): pass
    def stop(self): pass


class _Fake:
    _q_phase = QueueClient._q_phase
    _show_decode = QueueClient._show_decode
    _save_decode_rate = QueueClient._save_decode_rate

    def __init__(self, cfg):
        self._cfg = dict(cfg); self._jobs = {1}; self.bar = self.status = _W(); self.log = None
        self._dec_info = {1: {"chave": "decode_rate_video_wan22", "exata": "decode_rate_video_wan22_256x256x9",
                              "un": 256 * 256 * 9}}
    def cfg(self): return self._cfg
    def cfg_set(self, **kw): self._cfg.update(kw)
    def _mine(self, j): return j in self._jobs
    def _stop_progress(self): pass
    def _dec_timer(self): return _T()


def test_usa_tempo_exato():
    f = _Fake({"decode_rate_video_wan22": 1e-3, "decode_rate_video_wan22_256x256x9": 218.0})
    f._q_phase(1, "decodificando")
    assert f._dec_info[1]["est"] == 218.0


def test_sem_exato_usa_proporcional():
    f = _Fake({"decode_rate_video_wan22": 1e-3})
    f._q_phase(1, "decodificando")
    assert abs(f._dec_info[1]["est"] - 1e-3 * 256 * 256 * 9) < 1e-6


def test_grava_as_duas_chaves():
    f = _Fake({})
    info = dict(f._dec_info[1], dur=218.0)
    f._save_decode_rate(info)
    assert f._cfg["decode_rate_video_wan22_256x256x9"] == 218.0
    assert abs(f._cfg["decode_rate_video_wan22"] - 218.0 / (256 * 256 * 9)) < 1e-12
    info["dur"] = 200.0; f._save_decode_rate(info)
    assert f._cfg["decode_rate_video_wan22_256x256x9"] == 209.0
