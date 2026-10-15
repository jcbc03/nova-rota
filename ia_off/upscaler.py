"""Ampliador de imagens (Real-ESRGAN via ONNX Runtime CPU / OpenVINO, sem torch). Responsável: DEV beck.

Motor da fila, tipo "ampliar":  ampliar(params, on_progress, cancel_flag) -> caminho do PNG.
- Processa em blocos (tiles) com margem (overlap): RAM limitada mesmo em 4x de imagens grandes,
  progresso "bloco i de N" e checagem de cancel_flag entre blocos (levanta engine_api.Cancelled).
- Modelo: cfg["upscale_model"] (.onnx, Real-ESRGAN com entrada [1,3,H,W] RGB 0..1 e saída 4x ou 2x).
  Escala pedida != escala do modelo -> saída do modelo redimensionada com Lanczos (como o outscale do Real-ESRGAN).
- Sem modelo/runtime -> Lanczos (Pillow) puro, SINALIZADO: nome do arquivo com "_lanczos" e metadado
  "upscaler" = "lanczos (fallback: <motivo>)"; também em ULTIMO_FALLBACK e em log.
Sem Qt aqui: roda na thread de trabalho da fila.
"""
import logging
import os
import threading
import time
from pathlib import Path

import numpy as np

from .engine_api import Cancelled

log = logging.getLogger(__name__)

MODEL_URL = "https://huggingface.co/Heliosoph/realesrgan-onnx/resolve/main/realesr-general-x4v3.onnx"
MODEL_SHA256 = "09b757accd747d7e423c1d352b3e8f23e77cc5742d04bae958d4eb8082b76fa4"
SCALES = (2, 4)
DEFAULT_TILE = 256
DEFAULT_PAD = 24          # margem por lado (px de entrada) descartada na colagem; medido: 24 -> dif. máx 2/255 vs imagem inteira
ULTIMO_FALLBACK = [None]  # motivo do último fallback Lanczos (None = usou modelo)

_lock = threading.Lock()
_cache = {}               # (backend, caminho, mtime) -> runner


# ---------------------------------------------------------------- runtimes
class _OrtRunner:
    name = "onnxruntime"

    def __init__(self, path, threads):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(threads or 0)
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
        self.inp = self.sess.get_inputs()[0].name

    def __call__(self, x):
        return self.sess.run(None, {self.inp: x})[0]


class _OvRunner:
    name = "openvino"

    def __init__(self, path, threads, device="CPU"):
        import openvino as ov
        core = ov.Core()
        cfg = {"INFERENCE_NUM_THREADS": int(threads)} if threads and device == "CPU" else {}
        self.req = core.compile_model(core.read_model(str(path)), device, cfg).create_infer_request()

    def __call__(self, x):
        self.req.infer({0: x})
        return self.req.get_output_tensor(0).data.copy()


def _load_runner(cfg):
    """Devolve (runner, motivo_fallback). runner None -> usar Lanczos."""
    backend = str(cfg.get("upscale_backend") or "auto").lower()
    if backend == "lanczos":
        return None, "upscale_backend=lanczos no config"
    path = Path(str(cfg.get("upscale_model") or ""))
    if not path.is_file():
        return None, f"modelo não encontrado: {path} (rode tools/baixar_ampliador.py)"
    order = {"auto": ("onnxruntime", "openvino"), "onnxruntime": ("onnxruntime",),
             "openvino": ("openvino",)}.get(backend, ("onnxruntime", "openvino"))
    threads = int(cfg.get("threads") or os.cpu_count() or 4)
    errors = []
    for b in order:
        key = (b, str(path), path.stat().st_mtime)
        with _lock:
            if key in _cache:
                return _cache[key], None
            try:
                r = _OrtRunner(path, threads) if b == "onnxruntime" else _OvRunner(path, threads)
            except Exception as e:  # runtime ausente ou modelo inválido
                errors.append(f"{b}: {type(e).__name__}: {e}")
                continue
            _cache.clear(); _cache[key] = r
            return r, None
    return None, "runtime indisponível (" + "; ".join(errors) + ")"


# ---------------------------------------------------------------- tiling
def tile_grid(w, h, tile):
    """Lista de (x0, y0, x1, y1) cobrindo a imagem, blocos de no máximo tile x tile."""
    tile = max(8, int(tile))
    return [(x, y, min(x + tile, w), min(y + tile, h))
            for y in range(0, h, tile) for x in range(0, w, tile)]


def upscale_array(arr, run, model_scale, tile=DEFAULT_TILE, pad=DEFAULT_PAD,
                  on_progress=None, cancel_flag=None):
    """arr: uint8 HxWx3 RGB. run(x float32 [1,3,h,w] 0..1) -> [1,3,h*s,w*s]. Retorna uint8 (H*s)x(W*s)x3.

    Cada bloco é processado com `pad` px extras de contexto (cortados da imagem real, nunca inventados),
    e só o miolo da saída é colado: com campo receptivo <= pad o resultado é idêntico ao da imagem inteira.
    """
    h, w = arr.shape[:2]; s = int(model_scale)
    out = np.empty((h * s, w * s, 3), dtype=np.uint8)
    grid = tile_grid(w, h, tile); n = len(grid)
    for i, (x0, y0, x1, y1) in enumerate(grid, 1):
        if cancel_flag is not None and cancel_flag.is_set():
            raise Cancelled()
        px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
        px1, py1 = min(w, x1 + pad), min(h, y1 + pad)
        x = arr[py0:py1, px0:px1].astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        y = np.asarray(run(np.ascontiguousarray(x)))[0]
        if y.shape[1:] != ((py1 - py0) * s, (px1 - px0) * s):
            raise RuntimeError(f"modelo devolveu {y.shape}, esperado escala {s}x")
        cy, cx = (y0 - py0) * s, (x0 - px0) * s
        y = y[:, cy:cy + (y1 - y0) * s, cx:cx + (x1 - x0) * s]
        out[y0 * s:y1 * s, x0 * s:x1 * s] = (np.clip(y, 0, 1).transpose(1, 2, 0) * 255.0 + 0.5).astype(np.uint8)
        if on_progress is not None:
            on_progress(i, n)
    return out


def detect_scale(run):
    """Escala do modelo testando um bloco 8x8."""
    y = np.asarray(run(np.zeros((1, 3, 8, 8), np.float32)))
    return int(y.shape[-1] // 8)


# ---------------------------------------------------------------- motor da fila
def _cfg(params):
    from . import config
    cfg = config.load()
    cfg.update(params.get("cfg_override") or {})
    return cfg


def ampliar(params, on_progress, cancel_flag, runner=None):
    """params: entrada (obrigatório), escala (2|4, padrão 4), saida (arquivo .png ou pasta; opcional),
    tile, cfg_override. `runner` (testes): callable que substitui o modelo."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    p = dict(params or {})
    src = p.get("entrada") or p.get("input")
    if not src or not Path(src).is_file():
        raise FileNotFoundError(f"params['entrada'] não encontrado: {src}")
    scale = int(p.get("escala", p.get("scale", 4)))
    if scale not in SCALES:
        raise ValueError(f"escala inválida: {scale} (use 2 ou 4)")
    cfg = _cfg(p)
    with Image.open(src) as im0:
        alpha = im0.getchannel("A").copy() if "A" in im0.getbands() else None
        im = im0.convert("RGB")
    w, h = im.size; W, H = w * scale, h * scale

    reason = None
    if runner is None:
        runner, reason = _load_runner(cfg)
    if cancel_flag is not None and cancel_flag.is_set():
        raise Cancelled()
    t0 = time.time()
    if runner is not None:
        ms = int(p.get("model_scale") or getattr(runner, "scale", 0) or detect_scale(runner))
        arr = upscale_array(np.asarray(im), runner, ms, tile=int(p.get("tile") or cfg.get("upscale_tile") or DEFAULT_TILE),
                            pad=int(p.get("pad", DEFAULT_PAD)), on_progress=on_progress, cancel_flag=cancel_flag)
        res = Image.fromarray(arr)
        if res.size != (W, H):
            res = res.resize((W, H), Image.LANCZOS)
        method = f"real-esrgan ({getattr(runner, 'name', 'custom')}, modelo {ms}x)"
        ULTIMO_FALLBACK[0] = None
    else:
        log.warning("Ampliador sem IA, usando Lanczos: %s", reason)
        ULTIMO_FALLBACK[0] = reason
        res = im.resize((W, H), Image.LANCZOS)
        method = f"lanczos (fallback: {reason})"
        if on_progress is not None:
            on_progress(1, 1)
    if cancel_flag is not None and cancel_flag.is_set():
        raise Cancelled()
    if alpha is not None:
        res.putalpha(alpha.resize((W, H), Image.LANCZOS))

    tag = f"x{scale}" + ("_lanczos" if reason else "")
    out = p.get("saida") or p.get("output")
    if out and Path(out).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        fp = Path(out); fp.parent.mkdir(parents=True, exist_ok=True)
    else:
        if out:
            d = Path(out); d.mkdir(parents=True, exist_ok=True)
        else:
            from . import config
            d = config.output_dir("pictures")
        fp = d / f"{time.strftime('%Y%m%d_%H%M%S')}_{Path(src).stem}_{tag}.png"
    if fp.suffix.lower() == ".png":
        info = PngInfo()
        for k, v in {"upscaler": method, "source": str(src), "scale": scale,
                     "seconds": f"{time.time() - t0:.1f}", "software": "IA Off 3.0"}.items():
            info.add_itxt(k, str(v))
        res.save(fp, pnginfo=info)
    else:
        (res.convert("RGB") if fp.suffix.lower() in (".jpg", ".jpeg") else res).save(fp, quality=95)
    return str(fp)
