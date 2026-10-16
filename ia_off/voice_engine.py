"""Voz offline: fala->texto (faster-whisper, CPU int8) e texto->fala (Piper, pt_BR). Sem Qt.

Contrato dos motores (ver docs/FILA_API.md, "Motores"): progress_cb(step, total) e cancel_flag (is_set())
opcionais; cancelado -> engine_api.Cancelled. Caminhos de modelo só do config (voz_dir, whisper_model, piper_voice, piper_exe).
"""
import re
import subprocess
import sys
import threading
import wave
from pathlib import Path

from .engine_api import Cancelled, make_cancel_check

_lock = threading.Lock()
_whisper_cache = {}   # (pasta, compute_type) -> WhisperModel
_piper_cache = {}     # caminho .onnx -> PiperVoice


def _cfg(cfg):
    if cfg is not None:
        return cfg
    from . import config
    return config.load()


def whisper_model_dir(cfg):
    m = str(cfg.get("whisper_model") or "small")
    p = Path(m)
    if p.is_absolute() or p.exists():
        return p
    return Path(cfg["voz_dir"]) / "whisper" / f"faster-whisper-{m}"


def piper_voice_path(cfg):
    v = str(cfg.get("piper_voice") or "pt_BR-faber-medium")
    p = Path(v)
    if p.suffix == ".onnx" and (p.is_absolute() or p.exists()):
        return p
    return Path(cfg["voz_dir"]) / "piper" / f"{v}.onnx"


def _load_whisper(model_dir, threads):
    key = (str(model_dir), "int8")
    with _lock:
        if key not in _whisper_cache:
            from faster_whisper import WhisperModel
            _whisper_cache[key] = WhisperModel(str(model_dir), device="cpu", compute_type="int8",
                                               cpu_threads=int(threads or 0), local_files_only=True)
        return _whisper_cache[key]


CHUNK_S = 10          # trechos de ~10 s: o cancelamento é checado entre eles
SAMPLE_RATE = 16000


def _decode_audio(path):
    """numpy float32 mono 16 kHz, ou None se o decodificador do faster-whisper não estiver disponível."""
    try:
        from faster_whisper.audio import decode_audio
    except Exception:
        return None
    try:
        return decode_audio(str(path), sampling_rate=SAMPLE_RATE)
    except Exception:  # formato que o PyAV não abre: deixa o faster-whisper tentar/relatar com o arquivo
        return None


def _transcribe_work(model, audio, arr, lang, progress_cb, check):
    if arr is None:  # sem decodificador: arquivo inteiro (cancelamento entre segmentos)
        segments, info = model.transcribe(str(audio), language=lang, beam_size=5, vad_filter=True)
        total = max(1, int(round(getattr(info, "duration", 0) or 0)))
        parts = []
        for seg in segments:
            if check(): raise Cancelled()
            t = seg.text.strip()
            if t: parts.append(t)
            if progress_cb: progress_cb(min(total, int(round(seg.end))), total)
        return parts, total
    n = len(arr); step = CHUNK_S * SAMPLE_RATE
    total = max(1, int(round(n / SAMPLE_RATE))); parts = []
    for off in range(0, max(n, 1), step):
        if check(): raise Cancelled()
        chunk = arr[off:off + step]
        if len(chunk) < SAMPLE_RATE // 10:
            break
        prompt = " ".join(parts)[-200:] or None   # contexto do trecho anterior
        segments, _ = model.transcribe(chunk, language=lang, beam_size=5, vad_filter=True,
                                       initial_prompt=prompt, condition_on_previous_text=False)
        for seg in segments:
            if check(): raise Cancelled()
            t = seg.text.strip()
            if t: parts.append(t)
        if progress_cb: progress_cb(min(total, int(round((off + len(chunk)) / SAMPLE_RATE))), total)
    return parts, total


def transcribe(audio_path, progress_cb=None, cancel_flag=None, cfg=None, language=None, model_loader=None,
               audio_loader=None):
    """Áudio -> texto. Progresso em segundos de áudio processados: progress_cb(seg, duração_total).
    O trabalho (carregar modelo + decodificar) roda numa thread auxiliar, em trechos de ~10 s; ao cancelar,
    esta função levanta Cancelled em até ~0,1 s e a thread para no fim do trecho atual."""
    import threading
    cfg = _cfg(cfg); check = make_cancel_check(cancel_flag)
    audio = Path(audio_path)
    if not audio.is_file():
        raise FileNotFoundError(f"Áudio não encontrado: {audio}")
    md = whisper_model_dir(cfg)
    if model_loader is None:
        if not (md / "model.bin").is_file():
            raise FileNotFoundError(f"Modelo Whisper não encontrado: {md} (rode baixar_voz.bat)")
        model_loader = _load_whisper
    if check(): raise Cancelled()
    lang = language or cfg.get("whisper_lang") or "pt"
    res = {}; done = threading.Event()
    def work():
        try:
            model = model_loader(md, cfg.get("threads"))
            if check(): raise Cancelled()
            arr = (audio_loader or _decode_audio)(audio)
            res["v"] = _transcribe_work(model, audio, arr, lang, progress_cb, check)
        except BaseException as e:
            res["e"] = e
        finally:
            done.set()
    threading.Thread(target=work, daemon=True, name="whisper").start()
    while not done.wait(0.1):
        if check(): raise Cancelled()
    if "e" in res: raise res["e"]
    if check(): raise Cancelled()
    parts, total = res["v"]
    if progress_cb: progress_cb(total, total)
    return " ".join(parts).strip()


def split_sentences(text, max_len=400):
    out = []
    for s in re.split(r"(?<=[.!?…;:])\s+|\n+", text.strip()):
        s = s.strip()
        while len(s) > max_len:
            cut = s.rfind(" ", 0, max_len); cut = cut if cut > 0 else max_len
            out.append(s[:cut]); s = s[cut:].strip()
        if s: out.append(s)
    return out


def espeak_data_dir(onnx, src=None):
    """O espeak-ng (C) do piper não abre a pasta de dados se o caminho tem acento (ex.: "Área de Trabalho"):
    procura o caminho de compilação, falha e derruba o processo. Nesse caso copia os dados (uma vez)
    para uma pasta só ASCII ao lado da voz (ou no TEMP). None = usar o padrão do piper."""
    import shutil, tempfile
    if src is None:
        try:
            from piper.phonemize_espeak import ESPEAK_DATA_DIR as src
        except Exception:
            return None
    src = Path(src)
    if str(src).isascii() or not src.is_dir():
        return None
    for base in (Path(onnx).parent, Path(tempfile.gettempdir()) / "ia_off"):
        dst = base / "espeak-ng-data"
        if not str(dst).isascii():
            continue
        if not (dst / "phontab").is_file():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        return dst
    return None


def _load_piper(onnx):
    with _lock:
        if str(onnx) not in _piper_cache:
            from piper import PiperVoice
            d = espeak_data_dir(onnx)
            _piper_cache[str(onnx)] = (PiperVoice.load(str(onnx), espeak_data_dir=str(d)) if d
                                       else PiperVoice.load(str(onnx)))
        return _piper_cache[str(onnx)]


def _piper_pcm(voice, text):
    """(bytes PCM16, sample_rate) para piper-tts >=1.3 (synthesize -> AudioChunk) ou antigo (synthesize_stream_raw)."""
    rate = getattr(getattr(voice, "config", None), "sample_rate", 22050)
    if hasattr(voice, "synthesize_stream_raw"):
        return b"".join(voice.synthesize_stream_raw(text)), rate
    data = b""
    for ch in voice.synthesize(text):
        data += ch.audio_int16_bytes; rate = ch.sample_rate
    return data, rate


def speak(text, out_wav, progress_cb=None, cancel_flag=None, cfg=None, voice_loader=None):
    """Texto -> WAV (mono 16 bits). Progresso por frase: progress_cb(frase, total_frases). Retorna o caminho."""
    cfg = _cfg(cfg); check = make_cancel_check(cancel_flag)
    sents = split_sentences(text or "")
    if not sents:
        raise ValueError("Texto vazio.")
    onnx = piper_voice_path(cfg)
    if voice_loader is None and not (onnx.is_file() and Path(str(onnx) + ".json").is_file()):
        raise FileNotFoundError(f"Voz Piper não encontrada: {onnx} (+ .onnx.json; rode baixar_voz.bat)")
    out = Path(out_wav); out.parent.mkdir(parents=True, exist_ok=True)
    if check(): raise Cancelled()
    if cfg.get("piper_exe") and voice_loader is None:
        return _speak_exe(cfg, onnx, sents, out, progress_cb, check)
    voice = (voice_loader or _load_piper)(onnx)
    tmp = out.with_suffix(".part.wav")
    try:
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); started = False
            for i, s in enumerate(sents, 1):
                if check(): raise Cancelled()
                pcm, rate = _piper_pcm(voice, s)
                if not started: w.setframerate(rate); started = True
                w.writeframes(pcm)
                if progress_cb: progress_cb(i, len(sents))
        if check(): raise Cancelled()
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    return str(out)


def _speak_exe(cfg, onnx, sents, out, progress_cb, check):
    """piper.exe: uma frase por linha no stdin; --output_dir gera 1 wav por linha, juntados no fim."""
    from .sdcpp import kill_tree
    import tempfile, shutil
    tmpd = Path(tempfile.mkdtemp(prefix="iaoff_piper_"))
    win = sys.platform == "win32"
    kw = dict(creationflags=0x08000000 | 0x00000200) if win else dict(start_new_session=True)
    try:
        p = subprocess.Popen([cfg["piper_exe"], "--model", str(onnx), "--output_dir", str(tmpd)],
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        p.stdin.write(("\n".join(sents) + "\n").encode("utf-8")); p.stdin.close()
        n = len(sents)
        while p.poll() is None:
            if check():
                kill_tree(p); raise Cancelled()
            if progress_cb: progress_cb(min(n, len(list(tmpd.glob("*.wav")))), n)
            try: p.wait(0.2)
            except subprocess.TimeoutExpired: pass
        if check(): raise Cancelled()
        if p.returncode != 0:
            raise RuntimeError(f"piper.exe terminou com código {p.returncode}")
        wavs = sorted(tmpd.glob("*.wav"), key=lambda f: f.stat().st_mtime)
        if not wavs:
            raise RuntimeError("piper.exe não gerou áudio.")
        with wave.open(str(out), "wb") as w:
            for k, f in enumerate(wavs):
                with wave.open(str(f), "rb") as r:
                    if k == 0: w.setparams(r.getparams())
                    w.writeframes(r.readframes(r.getnframes()))
        if progress_cb: progress_cb(n, n)
        return str(out)
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
