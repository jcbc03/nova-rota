import os, tempfile
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
from ia_off import sizing as S

def test_targets():
    assert S.target_size("16:9", 4320) == (7680, 4320)
    assert S.target_size("16:9", 2160) == (3840, 2160)
    assert S.target_size("1:1", 512) == (512, 512)
    assert S.target_size("9:16", 1024) == (1024, 1824)
    assert S.target_size("21:9", 256, 64) == (576, 256)
    for n, _, _ in S.ASPECTS:
        for _, r in S.RESOLUTIONS:
            w, h = S.target_size(n, r); assert w % 8 == 0 and h % 8 == 0 and min(w, h) == r

def test_native_plan():
    assert S.plan("sd15", 512, 512) == (512, 512, 512, 512, False)
    gw, gh, fw, fh, up = S.plan("sd15", 7680, 4320)
    assert up and (fw, fh) == (7680, 4320) and max(gw, gh) <= 768 and gw % 64 == 0 and gh % 64 == 0
    assert abs(gw / gh - 16 / 9) < 0.15
    gw, gh, *_ , up = S.plan("flux2", 1024, 1824); assert up and max(gw, gh) <= 1024
    assert S.plan("flux2", 1024, 1024)[4] is False
    # Wan: máximo 832x480 (ou 480x832), múltiplos de 16
    for asp in ("16:9", "9:16", "1:1", "21:9", "4:3"):
        w, h = S.target_size(asp, 480, 16); gw, gh = S.native_size("wan", w, h)
        assert max(gw, gh) <= 832 and min(gw, gh) <= 480 and gw % 16 == 0 and gh % 16 == 0
    assert S.native_size("wan", 848, 480) == (832, 480)

def test_upscale_and_warning():
    from PIL import Image
    im = S.upscale(Image.new("RGB", (64, 36), "red"), 640, 360)
    assert im.size == (640, 360) and im.getpixel((5, 5))[0] > 200
    assert "8K" in S.warning(7680, 4320) and "4K" in S.warning(3840, 2160) and S.warning(512, 512) == ""
