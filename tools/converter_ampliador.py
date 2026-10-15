"""Converte os pesos OFICIAIS do Real-ESRGAN (realesr-general-x4v3.pth, xinntao/Real-ESRGAN v0.2.5.0, BSD-3)
para ONNX (models/realesr-general-x4v3.onnx), no formato que ia_off/upscaler.py espera:
entrada "input" [N,3,H,W] float32 RGB 0..1, saída "output" [N,3,4H,4W]. Responsável: DEV beck.

Só para quem quer reproduzir o .onnx versionado no repo; precisa de torch (CPU) e onnx:
    pip install torch --index-url https://download.pytorch.org/whl/cpu ; pip install onnx
Uso:  python tools\\converter_ampliador.py [pesos.pth] [saida.onnx]
Sem pesos.pth: baixa PTH_URL e confere PTH_SHA256.
Obs.: o SHA-256 do .onnx pode variar com a versão do torch/onnx; o que importa é a verificação numérica
(máx. dif. torch x ONNX), impressa no final.
"""
import hashlib, sys, tempfile, urllib.request
from pathlib import Path

PTH_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"
PTH_SHA256 = "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292"
ROOT = Path(__file__).resolve().parents[1]
OPSET = 17


def build_model():
    import torch
    from torch import nn
    import torch.nn.functional as F

    class SRVGGNetCompact(nn.Module):
        """Cópia da arquitetura oficial (realesrgan/archs/srvgg_arch.py, BSD-3)."""

        def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type="prelu"):
            super().__init__()
            self.upscale = upscale
            act = lambda: nn.PReLU(num_parameters=num_feat) if act_type == "prelu" else (
                nn.ReLU(inplace=True) if act_type == "relu" else nn.LeakyReLU(0.1, inplace=True))
            self.body = nn.ModuleList([nn.Conv2d(num_in_ch, num_feat, 3, 1, 1), act()])
            for _ in range(num_conv):
                self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
                self.body.append(act())
            self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
            self.upsampler = nn.PixelShuffle(upscale)

        def forward(self, x):
            out = x
            for layer in self.body:
                out = layer(out)
            out = self.upsampler(out)
            return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")

    return SRVGGNetCompact()


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import numpy as np, torch
    pth = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "realesr-general-x4v3.pth"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "models" / "realesr-general-x4v3.onnx"
    if not pth.is_file():
        print("Baixando", PTH_URL); urllib.request.urlretrieve(PTH_URL, pth)
    got = sha256(pth)
    if got != PTH_SHA256:
        print("ERRO: SHA-256 do .pth não confere:", got); return 1
    sd = torch.load(pth, map_location="cpu", weights_only=True)
    sd = sd.get("params_ema", sd.get("params", sd))
    model = build_model(); model.load_state_dict(sd, strict=True); model.eval()
    out.parent.mkdir(parents=True, exist_ok=True)
    x = torch.rand(1, 3, 64, 64)
    torch.onnx.export(model, x, str(out), opset_version=OPSET, input_names=["input"], output_names=["output"],
                      dynamic_axes={"input": {0: "batch_size", 2: "height", 3: "width"},
                                    "output": {0: "batch_size", 2: "height", 3: "width"}},
                      do_constant_folding=True, dynamo=False)
    import onnxruntime as ort
    sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    worst = 0.0
    for h, w in ((64, 64), (37, 91)):
        t = torch.rand(1, 3, h, w)
        with torch.no_grad():
            ref = model(t).numpy()
        worst = max(worst, float(np.abs(ref - sess.run(None, {"input": t.numpy()})[0]).max()))
    print(f"OK: {out}\n  sha256 {sha256(out)}\n  máx. dif. torch x ONNX (aleatório): {worst:.2e}")
    return 0 if worst < 1e-3 else 1


if __name__ == "__main__":
    sys.exit(main())
