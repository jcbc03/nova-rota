from tests.test_threads import _run

def test_video_imagem_inicial_so_no_wan22():
    r = _run("video_init_gui.py")
    assert r.returncode == 0 and "INIT OK" in r.stdout, (r.stdout[-1500:], r.stderr[-2500:])
