"""Texto da barra da aba Voz: sem 'frase(s)', plural certo."""
from types import SimpleNamespace
from ia_off.media_tabs import VoiceTab


class _W:
    def __init__(self): self.fmt = ""
    def setRange(self, *a): pass
    def setValue(self, *a): pass
    def setFormat(self, t): self.fmt = t
    def showMessage(self, t, *a): pass


def _txt(tipo, passo, total):
    bar = _W()
    fake = SimpleNamespace(_mine=lambda j: True, _tipos={1: tipo}, _tipo=tipo, bar=bar, status=bar)
    VoiceTab._q_progress(fake, 1, passo, total, 50, 3)
    return bar.fmt


def test_falar_plural():
    assert "1 de 3 frases" in _txt("falar", 1, 3)
    assert "frase(s)" not in _txt("falar", 1, 3)


def test_falar_singular():
    assert "1 de 1 frase ·" in _txt("falar", 1, 1)


def test_transcrever_segundos():
    assert "2 de 10 s de áudio" in _txt("transcrever", 2, 10)
