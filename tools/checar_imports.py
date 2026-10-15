"""Confere se as dependências e módulos da v3 importam. Uso: python tools\\checar_imports.py [arquivo_de_log]"""
import importlib, sys, time, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OBRIG = ["PySide6", "numpy", "faiss", "torch", "diffusers", "transformers", "onnxruntime", "faster_whisper",
         "ctranslate2", "piper", "imageio_ffmpeg",
         "ia_off.config", "ia_off.app", "ia_off.media_tabs", "ia_off.job_queue", "ia_off.engines_registry",
         "ia_off.image_engine", "ia_off.sdcpp", "ia_off.voice_engine", "ia_off.upscaler", "ia_off.rag"]
OPCIONAIS = ["openvino", "optimum.intel"]  # GPU Intel (instalar_gpu.bat)


def main():
    log = open(sys.argv[1], "a", encoding="utf-8") if len(sys.argv) > 1 else None
    def out(s):
        print(s, flush=True)
        if log: log.write(f"[{time.strftime('%H:%M:%S')}] {s}\n"); log.flush()
    falhas = 0
    for m in OBRIG + OPCIONAIS:
        try:
            mod = importlib.import_module(m)
            out(f"   ok   {m} {getattr(mod, '__version__', '')}")
        except Exception as e:
            opc = m in OPCIONAIS
            out(f"   {'aviso' if opc else 'FALHA'} {m}: {type(e).__name__}: {e}")
            if not opc:
                falhas += 1
                if log: log.write(traceback.format_exc())
    try:  # onnxruntime e openvino juntos no mesmo processo
        import onnxruntime as ort
        out(f"   onnxruntime providers: {ort.get_available_providers()}")
        try:
            import openvino as ov
            out(f"   openvino devices: {ov.Core().available_devices}")
        except ImportError:
            pass
    except Exception as e:
        out(f"   aviso runtime: {e}")
    out("   importações OK" if not falhas else f"   {falhas} importação(ões) falharam")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
