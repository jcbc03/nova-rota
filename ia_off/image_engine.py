"""Motor de imagem com diffusers (CPU, float32). Carrega modelos locais no lugar."""
import json, os, random
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"

SD15_SCHEDULER = {
    "_class_name": "PNDMScheduler", "beta_end": 0.012, "beta_schedule": "scaled_linear",
    "beta_start": 0.00085, "clip_sample": False, "num_train_timesteps": 1000,
    "set_alpha_to_one": False, "skip_prk_steps": True, "steps_offset": 1,
    "prediction_type": "epsilon", "timestep_spacing": "leading",
}

from .engine_api import Cancelled, make_cancel_check, make_progress  # noqa: F401 (Cancelled reexportado)

def _variant(folder):
    f = Path(folder)
    if not f.is_dir():
        return None
    names = [p.name for p in f.iterdir()]
    plain = any(n in ("diffusion_pytorch_model.safetensors", "model.safetensors", "diffusion_pytorch_model.bin", "pytorch_model.bin") for n in names)
    fp16 = any(".fp16." in n for n in names)
    return "fp16" if fp16 and not plain else None

def inspect_sd_folder(path):
    """Retorna dict de componentes presentes/ausentes (para diagnóstico na UI)."""
    p = Path(path)
    return {k: (p / k).exists() for k in ("model_index.json", "unet", "vae", "text_encoder", "tokenizer", "scheduler")}

def load_sd_components(path):
    import torch
    from diffusers import UNet2DConditionModel, AutoencoderKL, PNDMScheduler
    from transformers import CLIPTextModel, CLIPTokenizer
    p = Path(path)
    if not p.is_dir():
        raise FileNotFoundError(f"Pasta do modelo não encontrada: {p}")
    def load(cls, sub, **kw):
        d = p / sub
        if not d.is_dir():
            raise FileNotFoundError(f"Componente ausente: {d}")
        m = cls.from_pretrained(str(d), variant=_variant(d), local_files_only=True, torch_dtype=torch.float32, **kw)
        return m.to(torch.float32)
    unet = load(UNet2DConditionModel, "unet")
    vae = load(AutoencoderKL, "vae")
    te = load(CLIPTextModel, "text_encoder")
    tok_dir = p / "tokenizer" if (p / "tokenizer" / "vocab.json").exists() else ASSETS / "clip_tokenizer"
    tok = CLIPTokenizer.from_pretrained(str(tok_dir))
    sch_cfg = p / "scheduler" / "scheduler_config.json"
    sched = PNDMScheduler.from_pretrained(str(sch_cfg.parent)) if sch_cfg.exists() else PNDMScheduler.from_config(SD15_SCHEDULER)
    return dict(unet=unet, vae=vae, text_encoder=te, tokenizer=tok, scheduler=sched,
                safety_checker=None, feature_extractor=None, requires_safety_checker=False)

class ImageEngine:
    def __init__(self, cfg):
        self.cfg = cfg; self._cache = {}; self._ov = {}; self.ov_failed = False; self.last_backend = None

    def _threads(self):
        from . import perf
        perf.apply(self.cfg)

    def resolve_backend(self, mode):
        """'torch' ou 'ov:GPU'. Pix2Pix sempre torch (CPU)."""
        from . import perf
        if mode not in ("txt2img", "img2img", "inpaint") or self.ov_failed:
            return "torch"
        return perf.sd_backend(self.cfg)

    def _ov_engine(self, device):
        from .ov_engine import OVEngine
        if device not in self._ov:
            self._ov[device] = OVEngine(self.cfg, device)
        self._ov[device].cfg = self.cfg
        return self._ov[device]

    def _lcm(self, pipe):
        from diffusers import LCMScheduler
        lp = Path(self.cfg["lcm_lora_path"])
        if not lp.is_file():
            raise FileNotFoundError(f"LCM LoRA não encontrado: {lp}")
        pipe.load_lora_weights(str(lp.parent), weight_name=lp.name, adapter_name="lcm")
        pipe.fuse_lora()
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
        return pipe

    def pipeline(self, mode, lcm=True):
        from diffusers import (StableDiffusionPipeline, StableDiffusionImg2ImgPipeline,
                               StableDiffusionInpaintPipeline, StableDiffusionInstructPix2PixPipeline)
        import torch
        if mode == "pix2pix":
            lcm = False
        key = (mode if mode in ("inpaint", "pix2pix") else "sd15", lcm)
        if key not in self._cache:
            if key[0] == "sd15":
                base = StableDiffusionPipeline(**load_sd_components(self.cfg["sd15_path"]))
                if lcm: self._lcm(base)
            elif key[0] == "inpaint":
                base = StableDiffusionInpaintPipeline(**load_sd_components(self.cfg["inpaint_path"]))
                if lcm:
                    try:
                        self._lcm(base)
                    except Exception:  # LoRA incompatível: segue sem LCM
                        base = StableDiffusionInpaintPipeline(**load_sd_components(self.cfg["inpaint_path"]))
                        self.lcm_failed = True
            else:
                src = self.cfg["pix2pix_path"]
                base = StableDiffusionInstructPix2PixPipeline.from_pretrained(
                    src, local_files_only=True, torch_dtype=torch.float32,
                    safety_checker=None, requires_safety_checker=False)
            base.set_progress_bar_config(disable=True)
            from .perf import tune_torch_pipe
            tune_torch_pipe(base, self.cfg)
            # pipelines ficam residentes (32 GB de RAM): sem descarregar outros modos
            self._cache[key] = base
        pipe = self._cache[key]
        if mode == "img2img":
            return StableDiffusionImg2ImgPipeline(**pipe.components)
        return pipe

    def generate(self, mode, prompt, negative="", width=512, height=512, steps=4, guidance=1.0,
                 seed=-1, batch=1, init_image=None, mask=None, strength=0.6, image_guidance=1.5,
                 lcm=True, progress=None, cancelled=None, log=lambda s: None, backend=None,
                 progress_cb=None, cancel_flag=None):
        """progress_cb(step, total) e cancel_flag (is_set()) opcionais; `progress`/`cancelled` são o legado."""
        import torch
        cancelled = make_cancel_check(cancel_flag, cancelled)
        progress = make_progress(progress_cb, progress)
        if cancelled(): raise Cancelled()
        self._threads()
        backend = backend or self.resolve_backend(mode)
        if backend.startswith("ov:"):
            try:
                pipe = self._ov_engine(backend[3:]).pipeline(mode, lcm, width, height, 1, log, cfg_on=guidance > 1.0,
                                                             cancel_flag=cancel_flag)
                self.last_backend = backend
                log(f"Dispositivo: OpenVINO {backend[3:]}")
                return self._run(pipe, mode, prompt, negative, width, height, steps, guidance, seed, batch,
                                 init_image, mask, strength, image_guidance, progress, cancelled, ov=True)
            except Cancelled:
                raise
            except Exception as e:
                if cancelled(): raise Cancelled()
                self.ov_failed = True
                log(f"OpenVINO falhou ({type(e).__name__}: {str(e)[:300]}). Voltando para CPU (torch).")
        pipe = self.pipeline(mode, lcm)
        if cancelled(): raise Cancelled()
        self.last_backend = "torch"
        log(f"Dispositivo: CPU (torch, {torch.get_num_threads()} threads)")
        return self._run(pipe, mode, prompt, negative, width, height, steps, guidance, seed, batch,
                         init_image, mask, strength, image_guidance, progress, cancelled)

    def _run(self, pipe, mode, prompt, negative, width, height, steps, guidance, seed, batch,
             init_image, mask, strength, image_guidance, progress, cancelled, ov=False):
        import torch
        from .ov_engine import step_callback_kwargs
        if seed is None or seed < 0:
            seed = random.randint(0, 2**31 - 1)
        total = steps * batch
        images = []
        for b in range(batch):
            gen = torch.Generator("cpu").manual_seed(seed + b)
            if cancelled():
                raise Cancelled()
            def on_step(i, b=b):
                if cancelled():
                    raise Cancelled()
                progress(b * steps + min(i + 1, steps), total)
            if ov:
                cbkw = step_callback_kwargs(pipe, on_step)
            else:
                def cb(p, i, t, kw, on_step=on_step):
                    on_step(i); return kw
                cbkw = dict(callback_on_step_end=cb)
            kw = dict(prompt=prompt, negative_prompt=negative or None, num_inference_steps=steps,
                      guidance_scale=guidance, generator=gen, **cbkw)
            if mode == "txt2img":
                kw.update(width=width, height=height)
            elif mode == "img2img":
                kw.update(image=init_image.convert("RGB").resize((width, height)), strength=strength)
            elif mode == "inpaint":
                kw.update(image=init_image.convert("RGB").resize((width, height)),
                          mask_image=mask.convert("L").resize((width, height)), width=width, height=height,
                          strength=strength)
            elif mode == "pix2pix":
                kw.update(image=init_image.convert("RGB").resize((width, height)), image_guidance_scale=image_guidance)
            if ov:
                kw.pop("width", None); kw.pop("height", None)  # forma estática já definida no reshape
                if mode == "txt2img": kw.update(width=width, height=height)
            with torch.inference_mode():
                out = pipe(**kw)
            if cancelled():
                raise Cancelled()
            images.append((seed + b, out.images[0]))
        return images
