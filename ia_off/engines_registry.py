"""Adaptadores dos motores para a fila (job_queue): fn(params, on_progress, cancel_flag) -> caminho.

Uso (thread da GUI, depois de criar a fila):  engines_registry.register_all(self.fila)
Sem Qt widgets aqui: roda na thread de trabalho da fila. Caminhos de modelo só vêm do config.
Chaves de `params`: ver docs/FILA_API.md, seção "Motores".
"""
import threading
import time
from pathlib import Path

from .engine_api import Cancelled

IMAGE_MODES = ("txt2img", "img2img", "inpaint", "pix2pix", "flux2")
_lock = threading.Lock()
_image_engine = [None]


def _cfg(params):
    from . import config
    cfg = config.load()
    cfg.update(params.get("cfg_override") or {})
    return cfg


def _out_dir(params, kind):
    if params.get("saida"):
        d = Path(params["saida"]); d.mkdir(parents=True, exist_ok=True); return d
    from . import config
    return config.output_dir(kind)


def _require(cfg, keys):
    missing = [str(cfg.get(k)) for k in keys if not cfg.get(k) or not Path(cfg[k]).is_file()]
    if missing:
        raise FileNotFoundError("Arquivos não encontrados (ver Configurações): " + "; ".join(missing))


def _seed(v):
    v = int(v if v is not None else -1)
    return v if v >= 0 else int(time.time() * 1000) % (2**31)


def _save_png(im, fp, meta):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    for k, v in meta.items():
        if v not in (None, ""): info.add_itxt(k, str(v))
    im.save(fp, pnginfo=info)


def _get_image_engine(cfg, factory=None):
    with _lock:
        if _image_engine[0] is None:
            if factory is None:
                from .image_engine import ImageEngine as factory
            _image_engine[0] = factory(cfg)
        _image_engine[0].cfg = cfg
        return _image_engine[0]


def gerar_imagem(params, on_progress, cancel_flag, engine_factory=None):
    """Retorna o caminho do 1º PNG; com batch > 1 os demais ficam na mesma pasta."""
    p = dict(params)
    prompt = str(p.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("params['prompt'] é obrigatório.")
    mode = p.get("modo", "txt2img")
    if mode not in IMAGE_MODES:
        raise ValueError(f"modo inválido: {mode!r} (use {', '.join(IMAGE_MODES)})")
    cfg = _cfg(p); out = _out_dir(p, "pictures")
    w, h = int(p.get("width", 512)), int(p.get("height", 512))
    steps, batch, seed = int(p.get("steps", 4)), max(1, int(p.get("batch", 1))), _seed(p.get("seed"))
    guidance = float(p.get("guidance", 1.0)); stamp = time.strftime("%Y%m%d_%H%M%S")
    meta = lambda s: {"prompt": prompt, "negative_prompt": p.get("negative", ""), "mode": mode, "seed": s,
                      "steps": steps, "guidance": guidance, "size": f"{w}x{h}", "software": "IA Off 3.0"}
    if mode == "flux2":
        return _flux2(p, cfg, out, prompt, w, h, steps, batch, seed, guidance, stamp, meta, on_progress, cancel_flag)
    from PIL import Image
    def opened(key, conv):
        v = p.get(key)
        if not v: return None
        with Image.open(v) as im: return im.convert(conv).copy()
    init, mask = opened("init_image", "RGB"), opened("mask", "L")
    if mode in ("img2img", "inpaint", "pix2pix") and init is None:
        raise ValueError(f"modo {mode} precisa de params['init_image'] (caminho).")
    if mode == "inpaint" and mask is None:
        raise ValueError("modo inpaint precisa de params['mask'] (caminho).")
    eng = _get_image_engine(cfg, engine_factory)
    imgs = eng.generate(mode, prompt, negative=p.get("negative", ""), width=w, height=h, steps=steps,
                        guidance=guidance, seed=seed, batch=batch, init_image=init, mask=mask,
                        strength=float(p.get("strength", 0.6)), image_guidance=float(p.get("image_guidance", 1.5)),
                        lcm=bool(p.get("lcm", True)), progress_cb=on_progress, cancel_flag=cancel_flag)
    paths = []
    for s, im in imgs:
        fp = out / f"{stamp}_{mode}_{s}.png"; _save_png(im, fp, meta(s)); paths.append(fp)
    return str(paths[0]) if paths else None


def _flux2(p, cfg, out, prompt, w, h, steps, batch, seed, guidance, stamp, meta, on_progress, cancel_flag):
    from . import sdcpp, perf
    _require(cfg, ("flux2_model", "flux2_vae", "flux2_llm"))
    variant = perf.sdcpp_variant(cfg); paths = []
    for i in range(batch):
        if cancel_flag is not None and cancel_flag.is_set():
            raise Cancelled()
        s = seed + i; fp = out / f"{stamp}_flux2_{s}.png"
        mk = lambda b, fp=fp, s=s: sdcpp.build_flux2_args(b, cfg, prompt, fp, w, h, steps, s, guidance,
                                                          p.get("init_image") or None)
        cb = lambda st, tot, i=i: on_progress(i * tot + st, batch * tot)
        variant = sdcpp.run_with_fallback(cfg.get("sdcpp_dir"), variant, mk, progress_cb=cb, cancel_flag=cancel_flag)
        try:
            from PIL import Image
            with Image.open(fp) as im0: im = im0.copy()
            _save_png(im, fp, meta(s))
        except Exception:
            pass
        paths.append(fp)
    return str(paths[0])


def gerar_video(params, on_progress, cancel_flag):
    """Wan 2.1 via sd.cpp. Retorna o .mp4 (ou o .avi se a conversão falhar)."""
    from . import sdcpp, perf
    p = dict(params)
    prompt = str(p.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("params['prompt'] é obrigatório.")
    cfg = _cfg(p); _require(cfg, ("wan_model", "wan_t5", "wan_vae"))
    out = _out_dir(p, "videos")
    w, h = int(p.get("width", 480)), int(p.get("height", 272))
    frames, steps = sdcpp.wan_frames(p.get("frames", 17)), int(p.get("steps", 20))
    cfgs, fps, seed = float(p.get("cfg_scale", 6.0)), int(p.get("fps", 16)), _seed(p.get("seed"))
    neg = p.get("negative", ""); stem = f"{time.strftime('%Y%m%d_%H%M%S')}_wan_{seed}"
    avi = out / f"{stem}.avi"
    (out / f"{stem}.txt").write_text(f"prompt: {prompt}\nnegative: {neg}\nseed: {seed}\nsize: {w}x{h}\n"
                                     f"frames: {frames}\nsteps: {steps}\ncfg: {cfgs}\nfps: {fps}\n", encoding="utf-8")
    mk = lambda b: sdcpp.build_wan_args(b, cfg, prompt, avi, neg, w, h, frames, steps, cfgs, seed, fps,
                                        float(p.get("flow_shift", 3.0)))
    sdcpp.run_with_fallback(cfg.get("sdcpp_dir"), sdcpp.video_variant(cfg), mk,
                            progress_cb=on_progress, cancel_flag=cancel_flag)
    if cancel_flag is not None and cancel_flag.is_set():
        raise Cancelled()
    mp4 = out / f"{stem}.mp4"
    try:
        sdcpp.to_mp4(avi, mp4, fps); avi.unlink(missing_ok=True); return str(mp4)
    except Exception:
        return str(avi)


def transcrever(params, on_progress, cancel_flag):
    """Áudio -> texto. Grava <saida>/<nome>.txt e retorna esse caminho (o texto vai no arquivo)."""
    from . import voice_engine
    p = dict(params); audio = p.get("audio")
    if not audio:
        raise ValueError("params['audio'] (caminho) é obrigatório.")
    cfg = _cfg(p)
    if p.get("idioma"): cfg["whisper_lang"] = p["idioma"]
    if p.get("modelo"): cfg["whisper_model"] = p["modelo"]
    txt = voice_engine.transcribe(audio, on_progress, cancel_flag, cfg=cfg)
    out = Path(p["saida"]) if p.get("saida") else Path(audio).parent
    out.mkdir(parents=True, exist_ok=True)
    fp = out / f"{Path(audio).stem}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    fp.write_text(txt, encoding="utf-8")
    return str(fp)


def _music_dir(params):
    if params.get("saida"):
        return _out_dir(params, "pictures")
    try:
        from PySide6.QtCore import QStandardPaths as QS
        base = Path(QS.writableLocation(QS.MusicLocation)) or Path.home() / "Music"
    except Exception:
        base = Path.home() / "Music"
    d = base / "IA_Off"; d.mkdir(parents=True, exist_ok=True)
    return d


def falar(params, on_progress, cancel_flag):
    """Texto -> WAV. Retorna o caminho do .wav."""
    from . import voice_engine
    p = dict(params); text = str(p.get("texto") or "").strip()
    if not text:
        raise ValueError("params['texto'] é obrigatório.")
    cfg = _cfg(p)
    if p.get("voz"): cfg["piper_voice"] = p["voz"]
    if p.get("arquivo"):
        wav = Path(p["arquivo"])
    else:
        wav = _music_dir(p) / f"{time.strftime('%Y%m%d_%H%M%S')}_voz.wav"
    return voice_engine.speak(text, wav, on_progress, cancel_flag, cfg=cfg)


def register_all(queue=None):
    """Registra 'imagem', 'video', 'transcrever' e 'falar'. Com `queue`, só naquela fila; sem, no registro global do job_queue."""
    reg = queue.register_engine if queue is not None else __import__(
        "ia_off.job_queue", fromlist=["register_engine"]).register_engine
    reg("imagem", gerar_imagem)
    reg("video", gerar_video)
    reg("transcrever", transcrever)
    reg("falar", falar)
    return queue
