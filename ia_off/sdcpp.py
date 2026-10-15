"""Integração com stable-diffusion.cpp (sd-cli) para Wan 2.1 (vídeo) e FLUX.2 Klein (imagem)."""
import os, re, subprocess, sys, zipfile, shutil
from pathlib import Path

RELEASE_TAG = "master-964-1d0a58a"
ASSET_WIN_CPU = "sd-master-1d0a58a-bin-win-cpu-x64.zip"
ASSET_WIN_VULKAN = "sd-master-1d0a58a-bin-win-vulkan-x64.zip"
BASE_URL = f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{RELEASE_TAG}/"
RELEASE_URL = BASE_URL + ASSET_WIN_CPU
ASSETS = {"cpu": ASSET_WIN_CPU, "vulkan": ASSET_WIN_VULKAN}
BIN_NAMES = ("sd-cli.exe", "sd.exe", "sd-cli", "sd")
WAN_NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
           "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
           "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

PROG_RE = re.compile(r"\|\s*(\d+)/(\d+)\s*-")

def default_dir():
    from .config import APP_DIR
    return APP_DIR / "sdcpp"

def _variant_dir(folder, variant):
    folder = Path(folder) if folder else default_dir()
    return folder / "vulkan" if variant == "vulkan" else folder

def find_binary(folder, variant="cpu"):
    """CPU: pasta raiz (compatível com v2, ignora a subpasta vulkan). Vulkan: subpasta 'vulkan'."""
    d = _variant_dir(folder, variant)
    if not d.exists():
        return None
    for name in BIN_NAMES:
        for p in d.rglob(name):
            if p.is_file() and (variant == "vulkan" or "vulkan" not in p.relative_to(d).parts):
                return p
    return None

def download_binary(folder, progress=lambda done, total: None, cancelled=lambda: False, variant="cpu"):
    import requests
    d = _variant_dir(folder, variant); d.mkdir(parents=True, exist_ok=True)
    asset = ASSETS[variant]; z = d / asset
    with requests.get(BASE_URL + asset, stream=True, timeout=(10, 300)) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)); done = 0
        with open(z, "wb") as f:
            for c in r.iter_content(1 << 16):
                if cancelled():
                    raise RuntimeError("Download cancelado.")
                f.write(c); done += len(c); progress(done, total)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(d)
    z.unlink(missing_ok=True)
    b = find_binary(folder, variant)
    if not b:
        raise RuntimeError("sd-cli.exe não encontrado após extrair o zip.")
    return b

def ensure_binary(folder, variant="cpu", progress=lambda d, t: None, cancelled=lambda: False):
    return find_binary(folder, variant) or download_binary(folder, progress, cancelled, variant)

def run_with_fallback(folder, variant, build_args, on_line=lambda s: None, cancelled=lambda: False,
                      log=lambda s: None, progress=lambda d, t: None, ensure=None):
    """Executa com a variante pedida (ex.: vulkan); se falhar (e não foi cancelado), repete na CPU."""
    ensure = ensure or ensure_binary
    if variant == "vulkan":
        try:
            b = ensure(folder, "vulkan", progress, cancelled)
            log(f"sd.cpp: usando GPU Vulkan ({b})")
            run(build_args(b), on_line, cancelled)
            return "vulkan"
        except Exception as e:
            if cancelled():
                raise
            log(f"sd.cpp Vulkan falhou, voltando para CPU: {str(e)[-300:]}")
    b = ensure(folder, "cpu", progress, cancelled)
    log(f"sd.cpp: usando CPU ({b})")
    run(build_args(b), on_line, cancelled)
    return "cpu"

def wan_frames(n):
    """Wan exige 4k+1 quadros."""
    n = max(5, int(n))
    return n if (n - 1) % 4 == 0 else ((n - 1) // 4) * 4 + 1

def build_wan_args(binary, cfg, prompt, out_path, negative="", width=480, height=272, frames=17,
                   steps=20, cfg_scale=6.0, seed=-1, fps=16, flow_shift=3.0):
    return [str(binary), "-M", "vid_gen",
            "--diffusion-model", cfg["wan_model"], "--vae", cfg["wan_vae"], "--t5xxl", cfg["wan_t5"],
            "-p", prompt, "-n", negative or WAN_NEG,
            "--cfg-scale", str(cfg_scale), "--sampling-method", "euler", "--steps", str(int(steps)),
            "-W", str(int(width)), "-H", str(int(height)), "--video-frames", str(wan_frames(frames)),
            "--fps", str(int(fps)), "--flow-shift", str(flow_shift), "-s", str(int(seed)),
            "-t", str(int(cfg.get("threads", 4))), "--vae-tiling", "-o", str(out_path), "-v"]

def build_flux2_args(binary, cfg, prompt, out_path, width=512, height=512, steps=4, seed=-1,
                     cfg_scale=1.0, ref_image=None):
    a = [str(binary), "--diffusion-model", cfg["flux2_model"], "--vae", cfg["flux2_vae"], "--llm", cfg["flux2_llm"],
         "-p", prompt, "--cfg-scale", str(cfg_scale), "--sampling-method", "euler", "--steps", str(int(steps)),
         "-W", str(int(width)), "-H", str(int(height)), "-s", str(int(seed)),
         "-t", str(int(cfg.get("threads", 4))), "-o", str(out_path), "-v"]
    if ref_image:
        a += ["-r", str(ref_image)]
    return a

def parse_progress(line):
    m = PROG_RE.search(line)
    return (int(m.group(1)), int(m.group(2))) if m else None

def run(args, on_line=lambda s: None, cancelled=lambda: False):
    flags = 0x08000000 if sys.platform == "win32" else 0
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags,
                         cwd=str(Path(args[0]).parent))
    import threading
    tail = []; killed = []
    stop = threading.Event()
    def watch():  # mata o processo mesmo se ele não imprimir nada (leitura bloqueada)
        while not stop.wait(0.3):
            if cancelled() and p.poll() is None:
                killed.append(1); p.kill(); return
    threading.Thread(target=watch, daemon=True, name="sdcpp-cancel").start()
    try:
        _read_loop(p, on_line, tail)
    finally:
        stop.set()
    code = p.wait()
    if killed or cancelled():
        raise RuntimeError("Cancelado.")
    if code != 0:
        raise RuntimeError(f"sd-cli terminou com código {code}:\n" + "\n".join(tail))

def _read_loop(p, on_line, tail):
    buf = b""
    while True:
        c = p.stdout.read(1)
        if not c:
            break
        if c in (b"\r", b"\n"):
            if buf:
                s = buf.decode("utf-8", "replace"); on_line(s); tail.append(s); del tail[:-15]
            buf = b""
        else:
            buf += c
    if buf:
        s = buf.decode("utf-8", "replace"); on_line(s); tail.append(s)

def to_mp4(src, dst, fps=16):
    """Converte .avi/.webm do sd.cpp em MP4 (H.264) com o ffmpeg do imageio-ffmpeg."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    flags = 0x08000000 if sys.platform == "win32" else 0
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-r", str(fps), "-movflags", "+faststart", str(dst)], capture_output=True, text=True,
                       creationflags=flags)
    if r.returncode != 0:
        raise RuntimeError("Falha na conversão para MP4: " + r.stderr[-400:])
    return dst
