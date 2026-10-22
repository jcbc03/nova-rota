import pytest
from ia_off import sdcpp

def _cfg(tmp_path):
    cfg = {}
    for m in ("wan21", "wan22"):
        for k in sdcpp.WAN_KEYS[m]:
            f = tmp_path / f"{k}.bin"; f.write_text("x"); cfg[k] = str(f)
    return cfg

def test_no_image_no_flag(tmp_path):
    a = sdcpp.build_wan_args("sd", _cfg(tmp_path), "p", "o.mp4", modelo="wan22")
    assert "-i" not in a

def test_wan22_image(tmp_path):
    img = tmp_path / "i.png"; img.write_text("x")
    a = sdcpp.build_wan_args("sd", _cfg(tmp_path), "p", "o.mp4", modelo="wan22", init_image=img)
    assert a[a.index("-i") + 1] == str(img)

def test_wan21_image_raises(tmp_path):
    img = tmp_path / "i.png"; img.write_text("x")
    with pytest.raises(ValueError):
        sdcpp.build_wan_args("sd", _cfg(tmp_path), "p", "o.mp4", modelo="wan21", init_image=img)

def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        sdcpp.build_wan_args("sd", _cfg(tmp_path), "p", "o.mp4", modelo="wan22", init_image=tmp_path / "nope.png")
