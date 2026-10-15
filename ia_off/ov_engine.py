"""SD 1.5 (txt2img / img2img / inpaint) via OpenVINO (optimum-intel) na GPU Intel integrada.

Fluxo: o loader do app monta os componentes locais -> (opcional) funde o LCM LoRA -> salva uma pasta
diffusers temporária -> exporta para OpenVINO IR em %LOCALAPPDATA%\\IA_Off_v1\\ov_cache\\<chave> -> carrega,
faz reshape estático para o tamanho pedido e compila no dispositivo (GPU). Pipelines ficam residentes.
"""
import hashlib, json, shutil, tempfile
from pathlib import Path
from .perf import ov_cache_dir

def _key(src_path, lcm_path, lcm, kind):
    p = Path(src_path)
    stamp = []
    for f in sorted(p.rglob("*.safetensors")) + sorted(p.rglob("*.bin")):
        try: stamp.append(f"{f.relative_to(p)}:{f.stat().st_size}:{int(f.stat().st_mtime)}")
        except OSError: pass
    if lcm and lcm_path and Path(lcm_path).exists():
        stamp.append(f"lcm:{Path(lcm_path).stat().st_size}")
    h = hashlib.sha1(("|".join([str(p.resolve()), kind, str(lcm)] + stamp)).encode()).hexdigest()[:16]
    return f"{kind}_{'lcm' if lcm else 'base'}_{h}"

def ir_dir_for(src_path, lcm_path, lcm, kind):
    return ov_cache_dir() / _key(src_path, lcm_path, lcm, kind)

def export_ir(src_path, kind, lcm, lcm_path, log=lambda s: None):
    """Exporta (uma vez) e retorna a pasta IR."""
    out = ir_dir_for(src_path, lcm_path, lcm, kind)
    if (out / "model_index.json").exists() and (out / "unet" / "openvino_model.xml").exists():
        return out
    from diffusers import StableDiffusionPipeline, StableDiffusionInpaintPipeline, LCMScheduler
    from .image_engine import load_sd_components
    log(f"OpenVINO: exportando modelo ({kind}{', LCM fundido' if lcm else ''}) — só na 1ª vez, pode levar alguns minutos…")
    cls = StableDiffusionInpaintPipeline if kind == "inpaint" else StableDiffusionPipeline
    pipe = cls(**load_sd_components(src_path))
    if lcm:
        lp = Path(lcm_path)
        pipe.load_lora_weights(str(lp.parent), weight_name=lp.name, adapter_name="lcm")
        pipe.fuse_lora(); pipe.unload_lora_weights()
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    tmp = Path(tempfile.mkdtemp(prefix="iaoff_ovexp_", dir=str(ov_cache_dir())))
    try:
        pipe.save_pretrained(str(tmp), safe_serialization=True)
        del pipe
        from optimum.intel import OVStableDiffusionPipeline, OVStableDiffusionInpaintPipeline
        ocls = OVStableDiffusionInpaintPipeline if kind == "inpaint" else OVStableDiffusionPipeline
        ovp = ocls.from_pretrained(str(tmp), export=True, compile=False, load_in_8bit=False)
        out.mkdir(parents=True, exist_ok=True)
        ovp.save_pretrained(str(out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log(f"OpenVINO: IR salvo em {out}")
    return out

class OVEngine:
    """Mantém as pipelines OV compiladas residentes (chave = modo, dispositivo e tamanho)."""
    def __init__(self, cfg, device="GPU"):
        self.cfg = cfg; self.device = device; self._pipes = {}

    def _ov_config(self):
        c = {"CACHE_DIR": str(ov_cache_dir() / "kernels"), "PERFORMANCE_HINT": "LATENCY"}
        if self.device.startswith("CPU"):
            from .perf import effective_threads
            c["INFERENCE_NUM_THREADS"] = str(effective_threads(self.cfg))
        return c

    def pipeline(self, mode, lcm, width, height, batch, log=lambda s: None, cfg_on=True):
        from optimum.intel import (OVStableDiffusionPipeline, OVStableDiffusionImg2ImgPipeline,
                                   OVStableDiffusionInpaintPipeline)
        kind = "inpaint" if mode == "inpaint" else "sd15"
        src = self.cfg["inpaint_path"] if kind == "inpaint" else self.cfg["sd15_path"]
        ir = export_ir(src, kind, lcm, self.cfg.get("lcm_lora_path"), log)
        key = (mode, lcm, self.device)
        cls = {"txt2img": OVStableDiffusionPipeline, "img2img": OVStableDiffusionImg2ImgPipeline,
               "inpaint": OVStableDiffusionInpaintPipeline}[mode]
        entry = self._pipes.get(key)
        if entry is None:
            log(f"OpenVINO: carregando {mode} em {self.device}…")
            pipe = cls.from_pretrained(str(ir), compile=False, device=self.device, ov_config=self._ov_config())
            entry = self._pipes[key] = {"pipe": pipe, "shape": None}
        shape = (width, height, batch, cfg_on)
        if entry["shape"] != shape:
            # optimum-intel assume CFG (lote x2) no reshape estático; com guidance <= 1 deixamos o lote dinâmico
            b = batch if cfg_on else -1
            log(f"OpenVINO: reshape {width}×{height}{'' if cfg_on else ' (lote dinâmico, sem CFG)'} e compilação em {self.device}…")
            entry["pipe"].reshape(batch_size=b, height=height, width=width, num_images_per_prompt=b)
            entry["pipe"].compile()
            entry["shape"] = shape
        return entry["pipe"]
