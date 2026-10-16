"""Integração com stable-diffusion.cpp (sd-cli) para Wan 2.1 (vídeo), FLUX.2 Klein e Z-Image Turbo (imagem)."""
import os, re, subprocess, sys, zipfile, shutil
from pathlib import Path
from . import runtime_dlls

RELEASE_TAG = "master-964-1d0a58a"
ASSET_WIN_CPU = "sd-master-1d0a58a-bin-win-cpu-x64.zip"
ASSET_WIN_VULKAN = "sd-master-1d0a58a-bin-win-vulkan-x64.zip"
BASE_URL = f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{RELEASE_TAG}/"
RELEASE_URL = BASE_URL + ASSET_WIN_CPU
ASSETS = {"cpu": ASSET_WIN_CPU, "vulkan": ASSET_WIN_VULKAN}
BIN_NAMES = ("sd-cli.exe", "sd.exe", "sd-cli", "sd")
# Negativo padrão do Wan 2.1, tradução fiel do original em chinês. Em ASCII porque o sd-cli no Windows lê
# argv pela página de código ANSI: o texto chinês chegava como "????".
WAN_NEG = ("vivid garish colors, overexposed, static, blurry details, subtitles, style, artwork, painting, "
           "picture, still, overall grayish, worst quality, low quality, JPEG compression artifacts, ugly, "
           "mutilated, extra fingers, poorly drawn hands, poorly drawn face, deformed, disfigured, "
           "malformed limbs, fused fingers, motionless frame, cluttered background, three legs, "
           "many people in the background, walking backwards")

_PUNCT = {"\uff0c": ", ", "\u3001": ", ", "\u3002": ". ", "\uff1a": ": ", "\uff1b": "; ", "\uff01": "! ",
          "\uff1f": "? ", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
          "\u2014": "-", "\u2026": "...", "\u00a0": " ", "\u00ab": '"', "\u00bb": '"'}

def cli_safe(text, what="prompt"):
    """Texto seguro para argv do sd-cli: só ASCII. Acentos viram a letra base (NFKD), pontuação
    tipográfica/CJK vira a ASCII equivalente; o que sobrar é removido com aviso no log."""
    import logging, unicodedata
    text = str(text or "")
    if text.isascii():
        return text
    t = "".join(_PUNCT.get(c, c) for c in text)
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    lost = sorted({c for c in t if not c.isascii()})
    if lost:
        logging.getLogger(__name__).warning("sd-cli: %s com caracteres não ASCII removidos: %s", what, "".join(lost)[:40])
        t = "".join(c if c.isascii() else " " for c in t)
    return re.sub(r"\s{2,}", " ", t).strip()

PROG_RE = re.compile(r"\|\s*(\d+)/(\d+)\s*-")
# Depois da amostragem o sd-cli decodifica o VAE e grava o arquivo sem barra de progresso.
PHASE_DECODE, PHASE_SAVE = "decodificando", "salvando"
PHASE_RES = ((re.compile(r"decod", re.I), PHASE_DECODE), (re.compile(r"\bsav(e|ing)\b", re.I), PHASE_SAVE))

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

def run_with_fallback(folder, variant, build_args, on_line=lambda s: None, cancelled=None,
                      log=lambda s: None, progress=lambda d, t: None, ensure=None,
                      progress_cb=None, cancel_flag=None, phase_cb=None):
    """Executa com a variante pedida (ex.: vulkan); se falhar (e não foi cancelado), repete na CPU.
    `progress` é o do download do binário; `progress_cb(step, total)` é o dos passos da geração."""
    from .engine_api import Cancelled, make_cancel_check
    ensure = ensure or ensure_binary
    check = make_cancel_check(cancel_flag, cancelled)
    if variant == "vulkan":
        try:
            b = ensure(folder, "vulkan", progress, check)
            log(f"sd.cpp: usando GPU Vulkan ({b})")
            run(build_args(b), on_line, check, progress_cb=progress_cb, phase_cb=phase_cb)
            return "vulkan"
        except Exception as e:
            if check() or isinstance(e, Cancelled):
                raise Cancelled() from e
            log(f"sd.cpp Vulkan falhou, voltando para CPU: {str(e)[-300:]}")
    b = ensure(folder, "cpu", progress, check)
    if check():
        raise Cancelled()
    log(f"sd.cpp: usando CPU ({b})")
    run(build_args(b), on_line, check, progress_cb=progress_cb, phase_cb=phase_cb)
    return "cpu"

def video_variant(cfg, vulkan_ok=None):
    """Variante do sd.cpp para vídeo (Wan). Padrão: CPU. No i5-8365U/UHD 620 o Vulkan fez ~200 s/passo
    em 480x272 (pior que a CPU); só usa Vulkan se cfg["video_vulkan"] for verdadeiro."""
    from . import perf
    if not cfg.get("video_vulkan"):
        return "cpu"
    return perf.sdcpp_variant(cfg, vulkan_ok)

def wan_frames(n):
    """Wan exige 4k+1 quadros."""
    n = max(5, int(n))
    return n if (n - 1) % 4 == 0 else ((n - 1) // 4) * 4 + 1

WAN_KEYS = {"wan21": ("wan_model", "wan_t5", "wan_vae"), "wan22": ("wan22_model", "wan22_t5", "wan22_vae")}
# Wan2.2 TI2V 5B conforme docs/wan.md do sd.cpp (T2V): -M vid_gen --diffusion-model ... --vae wan2.2_vae
# --t5xxl umt5 --cfg-scale 6.0 --sampling-method euler --flow-shift 3.0 (mesma forma do Wan 2.1; só o VAE muda).
# fps: o 5B foi treinado a 24 fps (o doc não fixa --fps); o Wan 2.1 segue com 16.
WAN22_DEFAULTS = {"cfg_scale": 6.0, "sampling_method": "euler", "flow_shift": 3.0, "steps": 20, "fps": 24}

def wan_modelo(cfg, log=None):
    """'wan22' se cfg['video_modelo'] == 'wan22' e os três arquivos wan22_* existirem; senão 'wan21'
    (com aviso no log se o 2.2 foi pedido mas falta arquivo)."""
    if str(cfg.get("video_modelo") or "wan21").strip().lower() != "wan22":
        return "wan21"
    falta = [k for k in WAN_KEYS["wan22"] if not str(cfg.get(k) or "").strip() or not os.path.isfile(str(cfg[k]))]
    if not falta:
        return "wan22"
    import logging
    msg = "Wan 2.2 pedido mas arquivo(s) ausente(s): " + ", ".join(falta) + "; usando Wan 2.1."
    logging.getLogger(__name__).warning(msg)
    if log:
        log(msg)
    return "wan21"

def wan_keys(cfg, log=None):
    return WAN_KEYS[wan_modelo(cfg, log)]

def build_wan_args(binary, cfg, prompt, out_path, negative="", width=480, height=272, frames=17,
                   steps=20, cfg_scale=6.0, seed=-1, fps=16, flow_shift=3.0, modelo=None):
    km, kt, kv = WAN_KEYS[modelo] if modelo else wan_keys(cfg)
    return [str(binary), "-M", "vid_gen",
            "--diffusion-model", cfg[km], "--vae", cfg[kv], "--t5xxl", cfg[kt],
            "-p", cli_safe(prompt), "-n", cli_safe(negative or WAN_NEG, "negativo"),
            "--cfg-scale", str(cfg_scale), "--sampling-method", "euler", "--steps", str(int(steps)),
            "-W", str(int(width)), "-H", str(int(height)), "--video-frames", str(wan_frames(frames)),
            "--fps", str(int(fps)), "--flow-shift", str(flow_shift), "-s", str(int(seed)),
            "-t", str(int(cfg.get("threads", 4))), "--vae-tiling", "-o", str(out_path), "-v"]

def build_flux2_args(binary, cfg, prompt, out_path, width=512, height=512, steps=4, seed=-1,
                     cfg_scale=1.0, ref_image=None):
    a = [str(binary), "--diffusion-model", cfg["flux2_model"], "--vae", cfg["flux2_vae"], "--llm", cfg["flux2_llm"],
         "-p", cli_safe(prompt), "--cfg-scale", str(cfg_scale), "--sampling-method", "euler", "--steps", str(int(steps)),
         "-W", str(int(width)), "-H", str(int(height)), "-s", str(int(seed)),
         "-t", str(int(cfg.get("threads", 4))), "-o", str(out_path), "-v"]
    if ref_image:
        a += ["-r", str(ref_image)]
    return a

ZIMAGE_KEYS = (("zimage_model", "Z-Image Turbo (GGUF)"), ("zimage_vae", "Z-Image: VAE"),
               ("zimage_llm", "Z-Image: codificador Qwen3-4B (GGUF)"))

def build_zimage_args(binary, cfg, prompt, out_path, width=512, height=512, steps=8, seed=-1,
                      cfg_scale=1.0, negative="", diffusion_fa=False, offload_to_cpu=False):
    """Z-Image-Turbo, conforme docs/z_image.md do sd.cpp: --diffusion-model, --vae, --llm, -p,
    --cfg-scale 1.0, --steps 8, -H/-W. Sem negativo por padrão; -n só se `negative` vier preenchido."""
    empty = [f"{k} ({label})" for k, label in ZIMAGE_KEYS if not str(cfg.get(k) or "").strip()]
    if empty:
        raise ValueError("Z-Image: preencha em Configurações (ou IA_OFF_ZIMAGE_*): " + "; ".join(empty))
    a = [str(binary), "--diffusion-model", str(cfg["zimage_model"]), "--vae", str(cfg["zimage_vae"]),
         "--llm", str(cfg["zimage_llm"]), "-p", cli_safe(prompt)]
    if negative:
        a += ["-n", cli_safe(negative, "negativo")]
    a += ["--cfg-scale", str(cfg_scale), "--steps", str(int(steps)), "-H", str(int(height)), "-W", str(int(width)),
          "-s", str(int(seed)), "-t", str(int(cfg.get("threads", 4))), "-o", str(out_path), "-v"]
    if diffusion_fa:
        a.append("--diffusion-fa")
    if offload_to_cpu:
        a.append("--offload-to-cpu")
    return a

def parse_progress(line):
    m = PROG_RE.search(line)
    return (int(m.group(1)), int(m.group(2))) if m else None

def expected_steps(args):
    """Valor de --steps nos argumentos (None se ausente). O sd-cli também desenha barras "n/N"
    ao carregar tensores (ex.: 242/242, 825/825); só as de amostragem têm N == --steps."""
    try:
        i = list(args).index("--steps")
        return int(args[i + 1])
    except (ValueError, IndexError):
        return None

def kill_tree(p, timeout=5.0):
    """Encerra o processo e os filhos (Windows: taskkill /T /F; POSIX: grupo de processos)."""
    if p.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                           creationflags=0x08000000, timeout=timeout)
        else:
            import signal
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                p.terminate()
        p.wait(timeout)
    except Exception:
        pass
    if p.poll() is None:
        try:
            if sys.platform != "win32":
                import signal
                os.killpg(p.pid, signal.SIGKILL)
            else:
                p.kill()
        except Exception:
            p.kill()

def run(args, on_line=lambda s: None, cancelled=None, progress_cb=None, cancel_flag=None, phase_cb=None):
    """Roda o sd-cli. progress_cb(step, total) recebe as linhas "3/20"; cancel_flag (is_set()) ou
    cancelled() encerram a árvore de processos e levantam Cancelled. phase_cb(fase), opcional, recebe
    "decodificando" logo após o último passo (N/N) e "salvando" se o log indicar a gravação."""
    from .engine_api import Cancelled, make_cancel_check
    check = make_cancel_check(cancel_flag, cancelled)
    if check():
        raise Cancelled()
    win = sys.platform == "win32"
    kw = dict(creationflags=0x08000000 | 0x00000200) if win else dict(start_new_session=True)  # NO_WINDOW|NEW_PROCESS_GROUP
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         cwd=str(Path(args[0]).parent), env=runtime_dlls.env_para_exe(args[0]), **kw)
    import threading
    tail = []; killed = []
    stop = threading.Event()
    def watch():  # mata o processo mesmo se ele não imprimir nada (leitura bloqueada)
        while not stop.wait(0.2):
            if check() and p.poll() is None:
                killed.append(1); kill_tree(p); return
    threading.Thread(target=watch, daemon=True, name="sdcpp-cancel").start()
    last = [None]; fase = [None]; sampling = [False]
    want = expected_steps(args)
    def set_phase(f):
        if phase_cb is not None and f != fase[0]:
            fase[0] = f
            try:
                phase_cb(f)
            except Exception:
                pass
    def line(s):
        on_line(s)
        if progress_cb is None and phase_cb is None:
            return
        pr = parse_progress(s)
        if pr and want is not None and pr[1] != want:
            pr = None  # barra de carregamento de tensores, não passo de geração
        if pr:
            sampling[0] = True
            if pr != last[0]:
                last[0] = pr
                if progress_cb is not None:
                    progress_cb(*pr)
                if pr[0] >= pr[1]:
                    set_phase(PHASE_DECODE)
        elif sampling[0]:  # só depois da amostragem: "vae"/"decode" também aparecem no carregamento
            for rx, f in PHASE_RES:
                if rx.search(s):
                    set_phase(f); break
    try:
        _read_loop(p, line, tail)
    except BaseException:
        kill_tree(p); raise
    finally:
        stop.set()
    code = p.wait()
    if killed or check():
        raise Cancelled()
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
