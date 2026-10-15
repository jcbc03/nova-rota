"""Baixa o modelo do ampliador (Real-ESRGAN realesr-general-x4v3, ONNX, ~5 MB, licença BSD-3) e confere o SHA-256.

Uso:  python tools\\baixar_ampliador.py [destino.onnx]
Destino padrão: cfg["upscale_model"] (config.py / config.json / env IA_OFF_UPSCALE_MODEL).
"""
import hashlib, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ia_off import config, upscaler  # noqa: E402


def main():
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else config.load()["upscale_model"])
    if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == upscaler.MODEL_SHA256:
        print("Já existe e confere:", dest); return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    print("Baixando", upscaler.MODEL_URL, "->", dest)
    urllib.request.urlretrieve(upscaler.MODEL_URL, tmp)
    got = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if got != upscaler.MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        print("ERRO: SHA-256 não confere:", got); return 1
    tmp.replace(dest); print("OK:", dest); return 0


if __name__ == "__main__":
    sys.exit(main())
