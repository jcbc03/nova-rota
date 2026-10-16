"""Desempenho: dispositivos, modo máximo (threads/prioridade) e escolha de backend."""
import os, sys, shutil
from pathlib import Path

DEVICES = [("auto", "Auto"), ("cpu", "CPU"), ("openvino", "GPU Intel (OpenVINO)"), ("vulkan", "GPU Vulkan"),
           ("openvino_cpu", "CPU (OpenVINO)")]
LOGICAL = os.cpu_count() or 8

def ov_cache_dir():
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache")
    d = base / "IA_Off_v1" / "ov_cache"; d.mkdir(parents=True, exist_ok=True)
    return d

def set_thread_env(threads):
    """Deve ser chamado ANTES de importar torch/numpy pesado (feito em app.main)."""
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[k] = str(threads)
    os.environ.setdefault("KMP_BLOCKTIME", "1")

def effective_threads(cfg):
    return LOGICAL if cfg.get("max_mode", True) else max(1, int(cfg.get("threads", LOGICAL)))

def set_high_priority(on=True):
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        HIGH, NORMAL = 0x00000080, 0x00000020
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = ctypes.c_void_p  # handle de 64 bits (antes era cortado em int)
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        ok = bool(k32.SetPriorityClass(k32.GetCurrentProcess(), HIGH if on else NORMAL))
        if not ok:
            print(f"[perf] SetPriorityClass falhou: erro {ctypes.get_last_error()}", file=sys.stderr)
        return ok
    except Exception:
        return False

def apply(cfg, import_torch=True):
    """Aplica threads/prioridade ao processo atual. Retorna descrição."""
    import threading
    t = effective_threads(cfg)
    # os.environ só na thread principal: escrever variáveis de ambiente enquanto o Qt as lê em outra
    # thread pode corromper o bloco de ambiente do CRT (access violation no Windows).
    if threading.current_thread() is threading.main_thread():
        set_thread_env(t)
        alta = bool(cfg.get("max_mode", True))
        pr = set_high_priority(alta) and alta
    else:
        pr = False
    try:
        if not import_torch and "torch" not in sys.modules:
            return f"{t} threads" + (", prioridade alta" if pr else "")
        import torch
        torch.set_num_threads(t)
    except Exception:
        pass
    return f"{t} threads" + (", prioridade alta" if pr else "")

def total_ram_gb():
    try:
        if sys.platform == "win32":
            import ctypes
            class M(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("p", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                            ("x1", ctypes.c_ulonglong), ("x2", ctypes.c_ulonglong), ("x3", ctypes.c_ulonglong),
                            ("x4", ctypes.c_ulonglong), ("x5", ctypes.c_ulonglong)]
            m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.t / 2**30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except Exception:
        return 8.0

def tune_torch_pipe(pipe, cfg):
    """Modo máximo para pipelines torch na CPU: sem attention slicing se houver RAM, channels_last.
    torch.compile é ignorado no Windows (exige compilador MSVC/Triton) e só seria usado em Linux."""
    import torch
    notes = []
    # 32 GB: nunca attention slicing nem CPU offload (mais rápido)
    try: pipe.disable_attention_slicing(); notes.append("sem attention slicing")
    except Exception: pass
    if cfg.get("max_mode", True):
        for name in ("unet", "vae"):
            m = getattr(pipe, name, None)
            if m is not None:
                try: m.to(memory_format=torch.channels_last); notes.append(f"{name} channels_last")
                except Exception: pass
    return notes

import functools

@functools.lru_cache(maxsize=1)
def has_openvino_gpu():
    try:
        import openvino as ov
        return any(d.startswith("GPU") for d in ov.Core().available_devices)
    except Exception:
        return False

@functools.lru_cache(maxsize=1)
def ov_devices():
    try:
        import openvino as ov
        return list(ov.Core().available_devices)
    except Exception:
        return []

def has_vulkan():
    if sys.platform == "win32":
        return Path(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "vulkan-1.dll").exists()
    return bool(shutil.which("vulkaninfo")) or any(Path(p).exists() for p in ("/usr/lib/x86_64-linux-gnu/libvulkan.so.1",))

def sd_backend(cfg, gpu_ok=None):
    """Backend do SD 1.5: 'ov:GPU', 'ov:CPU' ou 'torch'."""
    dev = cfg.get("device", "auto")
    if dev == "openvino_cpu":
        return "ov:CPU"
    if dev in ("auto", "openvino"):
        ok = has_openvino_gpu() if gpu_ok is None else gpu_ok
        if ok or dev == "openvino":
            return "ov:GPU"
    return "torch"

def benchmark_backends():
    """Backends de SD disponíveis para o benchmark."""
    out = ["torch"]
    devs = ov_devices()
    try:
        import optimum.intel  # noqa
        if "CPU" in devs: out.append("ov:CPU")
        if any(d.startswith("GPU") for d in devs): out.append("ov:GPU")
    except Exception:
        pass
    return out

BACKEND_TO_DEVICE = {"torch": "cpu", "ov:CPU": "openvino_cpu", "ov:GPU": "openvino"}
BACKEND_LABEL = {"torch": "CPU (PyTorch)", "ov:CPU": "CPU (OpenVINO)", "ov:GPU": "GPU Intel (OpenVINO)"}

def sdcpp_variant(cfg, vulkan_ok=None):
    """Variante do sd.cpp: 'vulkan' ou 'cpu'."""
    dev = cfg.get("device", "auto")
    ok = has_vulkan() if vulkan_ok is None else vulkan_ok
    return "vulkan" if dev in ("auto", "vulkan") and ok else "cpu"
