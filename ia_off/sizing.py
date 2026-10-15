"""Proporção × resolução -> tamanho final, tamanho nativo de geração e upscale."""
import math

ASPECTS = [("1:1", 1, 1), ("16:9", 16, 9), ("9:16", 9, 16), ("4:3", 4, 3), ("3:4", 3, 4), ("3:2", 3, 2),
           ("2:3", 2, 3), ("5:4", 5, 4), ("4:5", 4, 5), ("21:9", 21, 9), ("9:21", 9, 21), ("2:1", 2, 1)]
CUSTOM = "Personalizado"
RESOLUTIONS = [("256p", 256), ("384p", 384), ("512p", 512), ("768p", 768), ("1024p (HD/1080)", 1024),
               ("1440p (2K)", 1440), ("2160p (4K)", 2160), ("4320p (8K)", 4320)]
VIDEO_RESOLUTIONS = [("256p", 256), ("384p", 384), ("480p (máx. Wan 1.3B)", 480)]

# max lado longo / lado curto e múltiplo exigido por motor (CPU)
NATIVE = {
    "sd15": dict(long=768, short=768, mult=64),
    "flux2": dict(long=1024, short=1024, mult=64),
    "wan": dict(long=832, short=480, mult=16),
}
ENGINE_OF_MODE = {"txt2img": "sd15", "img2img": "sd15", "inpaint": "sd15", "pix2pix": "sd15", "flux2": "flux2"}

def _round(v, m):
    return max(m, int(round(v / m)) * m)

def target_size(aspect, short, mult=8):
    """Tamanho final pelo lado curto. 16:9 @ 4320 -> 7680x4320."""
    a = dict((n, (w, h)) for n, w, h in ASPECTS)[aspect]
    aw, ah = a
    if aw >= ah:
        w, h = short * aw / ah, short
    else:
        w, h = short, short * ah / aw
    return _round(w, mult), _round(h, mult)

def native_size(engine, w, h):
    """Maior tamanho dentro do nativo do motor com a mesma proporção (múltiplo exigido, nunca acima do nativo)."""
    n = NATIVE[engine]; m = n["mult"]
    s = min(1.0, n["long"] / max(w, h), n["short"] / min(w, h))
    gw, gh = max(m, int(w * s / m + 0.5) * m), max(m, int(h * s / m + 0.5) * m)
    lo, sh = (gw, gh) if gw >= gh else (gh, gw)
    lo, sh = min(lo, n["long"] // m * m), min(sh, n["short"] // m * m)
    # se o tamanho nativo máximo tem quase a mesma proporção (<5%), usa-o (ex.: 16:9 no Wan -> 832x480)
    L, Sh = n["long"] // m * m, n["short"] // m * m
    if s < 1.0 and L != Sh and abs((L / Sh) / (max(w, h) / min(w, h)) - 1) < 0.05:
        lo, sh = L, Sh
    return (lo, sh) if gw >= gh else (sh, lo)

def plan(engine, w, h):
    """(gen_w, gen_h, final_w, final_h, precisa_upscale)."""
    gw, gh = native_size(engine, w, h)
    up = w > gw or h > gh
    return gw, gh, (w if up else gw), (h if up else gh), up

def upscale(img, w, h, sharpen=True):
    from PIL import Image, ImageFilter
    if img.size == (w, h):
        return img
    out = img.resize((w, h), Image.LANCZOS)
    if sharpen and (w > img.width):
        out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    return out

def warning(w, h):
    px = w * h
    if px >= 7680 * 4320 * 0.9:
        return "⚠ 8K: upscale pode levar 1–3 min e usar ~1–2 GB de RAM por imagem; arquivos PNG de 50–150 MB."
    if px >= 3840 * 2160 * 0.9:
        return "⚠ 4K: upscale leva ~10–40 s e ~0,5 GB de RAM por imagem; PNG de 15–40 MB."
    if px >= 2560 * 1440 * 0.9:
        return "2K: gerado no tamanho nativo e ampliado (Lanczos + nitidez)."
    return ""
