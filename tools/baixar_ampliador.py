"""Instala o modelo do ampliador (Real-ESRGAN realesr-general-x4v3, ONNX, ~5 MB, BSD-3) e confere o SHA-256.

O .onnx vem do próprio repo (models/realesr-general-x4v3.onnx), convertido dos pesos OFICIAIS
(xinntao/Real-ESRGAN v0.2.5.0) por tools/converter_ampliador.py; nada é baixado de terceiros.
Uso:  python tools\\baixar_ampliador.py [destino.onnx]
Destino padrão: cfg["upscale_model"] (config.py / config.json / env IA_OFF_UPSCALE_MODEL).
"""
import hashlib, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ia_off import config, upscaler  # noqa: E402


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else config.load()["upscale_model"])
    if dest.is_file() and _sha(dest) == upscaler.MODEL_SHA256:
        print("Já existe e confere:", dest); return 0
    src = upscaler.MODEL_REPO_FILE
    if not src.is_file() or _sha(src) != upscaler.MODEL_SHA256:
        print("ERRO: modelo do repo ausente ou SHA-256 não confere:", src,
              "(regenere com tools/converter_ampliador.py)"); return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    print("Instalando", src, "->", dest)
    shutil.copyfile(src, tmp)
    got = _sha(tmp)
    if got != upscaler.MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        print("ERRO: SHA-256 não confere:", got); return 1
    tmp.replace(dest); print("OK:", dest); return 0


if __name__ == "__main__":
    sys.exit(main())
