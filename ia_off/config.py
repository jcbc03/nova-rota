import json, os
from pathlib import Path

APP_DIR = Path(os.environ.get("IA_OFF_HOME") or (Path(os.environ.get("APPDATA", Path.home())) / "IA_Off_v1"))
APP_DIR.mkdir(parents=True, exist_ok=True)
CFG_FILE = APP_DIR / "config.json"

DEFAULTS = {
    "ollama_url": "http://localhost:11434",
    "ollama_exe": r"C:\Users\jcbc\AppData\Local\Programs\Ollama\ollama.exe",
    "threads": os.cpu_count() or 8,
    "device": "auto",
    "max_mode": True,
    "num_ctx": 4096,
    "temperature": 0.7,
    "system_prompt": "Você é um assistente útil. Responda em português do Brasil.",
    "model": "qwen2.5:3b",
    "embed_model": "nomic-embed-text",
    "translate_model": "qwen2.5:3b",
    # --- RAG (rag.py): pasta do índice vetorial; env IA_OFF_RAG_DIR sobrepõe ---
    "rag_dir": os.environ.get("IA_OFF_RAG_DIR") or r"C:\IA\dados\rag",
    # --- Imagem (diffusers) ---
    "sd15_path": r"C:\estudio_local\models\imagem\sd15",
    "lcm_lora_path": r"C:\estudio_local\models\imagem\lcm-lora-sdv1-5\pytorch_lora_weights.safetensors",
    "inpaint_path": r"C:\estudio_local\models\imagem\sd15-inpainting",
    "pix2pix_path": "timbrooks/instruct-pix2pix",
    # --- Ampliador (upscaler.py): Real-ESRGAN ONNX; env IA_OFF_UPSCALE_MODEL sobrepõe ---
    "upscale_model": os.environ.get("IA_OFF_UPSCALE_MODEL") or r"C:\IA\modelos\imagem\realesr-general-x4v3.onnx",
    "upscale_backend": "auto",  # auto (onnxruntime -> openvino) | onnxruntime | openvino | lanczos
    "upscale_tile": 256,        # lado do bloco de entrada (px); menor = menos RAM
    # --- sd.cpp (Wan / FLUX.2) ---
    "video_vulkan": False,  # vídeo (Wan) usa o sd.cpp de CPU; True tenta Vulkan
    "sdcpp_dir": "",  # vazio = %APPDATA%\IA_Off_v1\sdcpp
    "wan_model": r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\wan2.1-t2v-1.3b\wan2.1_t2v_1.3b-q5_k_m.gguf",
    "wan_t5": r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\wan2.1-t2v-1.3b\umt5-xxl-encoder-Q4_K_M.gguf",
    "wan_vae": r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\wan2.1-t2v-1.3b\wan_2.1_vae.safetensors",
    "flux2_model": r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\flux2-klein-4b\flux-2-klein-4b-Q4_0.gguf",
    "flux2_vae": r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\shared\flux2-vae.safetensors",
    "flux2_llm": r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\shared\Qwen3-4B-Q4_K_M.gguf",
    # --- Voz (voice_engine.py): modelos em <voz_dir>\whisper\faster-whisper-<modelo> e <voz_dir>\piper\<voz>.onnx ---
    "voz_dir": os.environ.get("IA_OFF_VOZ_DIR") or r"C:\IA\modelos\voz",
    "whisper_model": "small",  # small | base | caminho de uma pasta CTranslate2
    "whisper_lang": "pt",
    "piper_voice": "pt_BR-faber-medium",  # nome em <voz_dir>\piper ou caminho do .onnx
    "piper_exe": "",  # vazio = pacote python piper-tts; senão caminho do piper.exe
}

MEDIA_PATH_KEYS = [
    ("sd15_path", "SD 1.5 (pasta diffusers)", "dir"),
    ("lcm_lora_path", "LCM LoRA (.safetensors)", "file"),
    ("inpaint_path", "SD 1.5 Inpainting (pasta)", "dir"),
    ("pix2pix_path", "InstructPix2Pix (pasta ou id HF em cache)", "dir"),
    ("upscale_model", "Ampliador: Real-ESRGAN (.onnx)", "file"),
    ("sdcpp_dir", "Pasta do stable-diffusion.cpp (vazio = automático)", "dir"),
    ("wan_model", "Wan 2.1 T2V 1.3B (GGUF)", "file"),
    ("wan_t5", "Wan: codificador UMT5 (GGUF)", "file"),
    ("wan_vae", "Wan: VAE", "file"),
    ("flux2_model", "FLUX.2 Klein 4B (GGUF)", "file"),
    ("flux2_vae", "FLUX.2: VAE", "file"),
    ("flux2_llm", "FLUX.2: codificador Qwen3-4B (GGUF)", "file"),
]

def output_dir(kind):
    """kind: 'pictures' ou 'videos' -> pasta IA_Off (respeita redirecionamento do OneDrive)."""
    try:
        from PySide6.QtCore import QStandardPaths as QS
        loc = QS.PicturesLocation if kind == "pictures" else QS.MoviesLocation
        base = Path(QS.writableLocation(loc))
    except Exception:
        base = Path.home() / ("Pictures" if kind == "pictures" else "Videos")
    d = base / "IA_Off"; d.mkdir(parents=True, exist_ok=True)
    return d

GGUF_SUGGESTIONS = [
    ("qwen3-4b-local", r"C:\Users\jcbc\OneDrive\Documentos 1\ChatGPT\IA_Off\data\models\shared\Qwen3-4B-Q4_K_M.gguf"),
    ("qwen2.5-coder-7b-local", r"C:\EngenhariaIA-0.2.0-win-x64\models\qwen2.5-coder-7b-instruct-q4_k_m\qwen2.5-coder-7b-instruct-q4_k_m.gguf"),
]

def load():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg

def save(cfg):
    CFG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
