from tests.test_threads import _run

def test_video_tamanho_nao_espreme_em_janela_baixa():
    r = _run("video_layout_gui.py")
    assert r.returncode == 0 and "LAYOUT OK" in r.stdout, (r.stdout[-1500:], r.stderr[-2500:])
