import os, sys, tempfile
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
from pathlib import Path
import pytest
from ia_off import sdcpp

CFG = {"wan_model": r"C:\m\wan.gguf", "wan_t5": r"C:\m\umt5.gguf", "wan_vae": r"C:\m\vae.safetensors",
       "flux2_model": r"C:\m\klein.gguf", "flux2_vae": r"C:\m\fvae.safetensors", "flux2_llm": r"C:\m\Qwen3.gguf", "threads": 4}

def test_wan_args():
    a = sdcpp.build_wan_args("sd-cli.exe", CFG, "um gato", "out.avi", width=480, height=272, frames=18, seed=7)
    s = " ".join(a)
    assert a[:3] == ["sd-cli.exe", "-M", "vid_gen"]
    for flag, val in [("--diffusion-model", CFG["wan_model"]), ("--t5xxl", CFG["wan_t5"]), ("--vae", CFG["wan_vae"]),
                      ("--video-frames", "17"), ("-W", "480"), ("-H", "272"), ("-s", "7"), ("-t", "4"), ("-o", "out.avi")]:
        assert a[a.index(flag) + 1] == val
    assert "--flow-shift" in a and "--sampling-method" in a

def test_flux2_args():
    a = sdcpp.build_flux2_args("sd-cli.exe", CFG, "gato", "o.png", 512, 512, 4, 1)
    assert a[a.index("--llm") + 1] == CFG["flux2_llm"] and a[a.index("--cfg-scale") + 1] == "1.0"
    assert "-M" not in a and "-r" not in a

def test_frames_progress():
    assert [sdcpp.wan_frames(n) for n in (17, 18, 20, 33, 2)] == [17, 17, 17, 33, 5]
    assert sdcpp.parse_progress("  |=====>        | 3/20 - 12.31s/it") == (3, 20)
    assert sdcpp.parse_progress("[INFO ] loading model") is None

def test_url():
    assert sdcpp.RELEASE_URL.endswith("/master-964-1d0a58a/sd-master-1d0a58a-bin-win-cpu-x64.zip")

def test_run_fake_binary(tmp_path):
    fake = tmp_path / "fake.py"
    fake.write_text("import sys\nfor i in range(1,4): sys.stdout.write(f'\\r|==> | {i}/3 - 1.0s/it'); sys.stdout.flush()\nprint()\n")
    got = []
    sdcpp.run([sys.executable, str(fake)], lambda s: got.append(sdcpp.parse_progress(s)))
    assert (3, 3) in got
    bad = tmp_path / "bad.py"; bad.write_text("print('erro x'); raise SystemExit(2)")
    with pytest.raises(RuntimeError, match="código 2"):
        sdcpp.run([sys.executable, str(bad)])

TINY = "/tmp/tinysd"
@pytest.mark.skipif(not Path(TINY).exists(), reason="modelo tiny ausente")
def test_diffusers_tiny_all_modes():
    from PIL import Image
    from ia_off.image_engine import ImageEngine, inspect_sd_folder, Cancelled
    assert inspect_sd_folder(TINY)["model_index.json"] is False
    eng = ImageEngine({"sd15_path": TINY, "inpaint_path": TINY, "threads": 2, "lcm_lora_path": "x"})
    prog = []
    r = eng.generate("txt2img", "cat", width=64, height=64, steps=2, guidance=1.0, seed=1, batch=2, lcm=False,
                     progress=lambda i, n: prog.append((i, n)))
    assert len(r) == 2 and r[0][1].size == (64, 64) and prog[-1] == (4, 4)
    init = r[0][1]
    r2 = eng.generate("img2img", "dog", width=64, height=64, steps=4, seed=2, init_image=init, strength=0.5, lcm=False)
    assert r2[0][1].size == (64, 64)
    with pytest.raises(Cancelled):
        eng.generate("txt2img", "x", width=64, height=64, steps=3, lcm=False, cancelled=lambda: True)

def test_bundled_tokenizer():
    from transformers import CLIPTokenizer
    from ia_off.image_engine import ASSETS
    t = CLIPTokenizer.from_pretrained(str(ASSETS / "clip_tokenizer"))
    assert t("a cat").input_ids[0] == 49406

def test_to_mp4(tmp_path):
    import subprocess, imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe(); avi = tmp_path / "a.avi"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=480x272:rate=16", "-frames:v", "17",
                    "-c:v", "mjpeg", str(avi)], check=True)
    out = sdcpp.to_mp4(avi, tmp_path / "a.mp4", 16)
    assert Path(out).stat().st_size > 1000
