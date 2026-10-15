"""Tradução offline PT -> EN de prompts usando um modelo de chat do Ollama."""
import json, re, threading, unicodedata
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a translation engine. Translate the user's text from Portuguese to English.\n"
    "Rules:\n"
    "- Output ONLY the English translation, nothing else: no preamble, no explanations, no notes, no quotes.\n"
    "- Keep the exact meaning and EVERY detail. Do not add, remove, soften or censor anything.\n"
    "- If the text is a comma-separated list of tags, keep it as a comma-separated list of tags in the same order.\n"
    "- Keep numbers, weights like (word:1.2), proper names, and technical terms (e.g. 4k, 8k, HDR, bokeh) unchanged.\n"
    "- If part of the text is already in English, keep that part as is."
)

PT_WORDS = set("""de da do das dos um uma uns umas com para pra em no na nos nas e é o os as que por pela pelo mais muito
muita sobre sob entre sem seu sua ao à cabelo olhos rosto mulher homem menina menino gato cachorro cidade noite dia
luz fundo azul vermelho verde amarelo preto branco bonito bonita foto retrato estilo alta qualidade detalhado
paisagem praia floresta céu mar sol chuva cor cores grande pequeno pequena usando segurando vestido""".split())
EN_WORDS = set("""the a an of with and in on at to is are by for from wearing holding background high quality detailed
photo portrait style woman man girl boy cat dog city night day light blue red green yellow black white beautiful
landscape beach forest sky sea sun rain colors large small dress hair eyes face""".split())
ACCENTS = set("ãõçáéíóúâêôàü")

def is_english(text):
    """Heurística simples: sem acentos e com mais palavras inglesas que portuguesas."""
    t = text.lower()
    if not t.strip():
        return True
    if any(c in ACCENTS for c in t):
        return False
    words = re.findall(r"[a-z]+", t)
    pt = sum(w in PT_WORDS for w in words); en = sum(w in EN_WORDS for w in words)
    if pt == 0 and en == 0:
        return not any(len(w) >= 3 for w in words)  # sem palavras reais (ex.: "8k, 4k") = não traduz
    # palavras ambíguas ("a") contam nos dois; exige maioria inglesa
    return en > pt

PREAMBLE = re.compile(r"^\s*(here(?:'s| is)[^:\n]*:|translation\s*:|english\s*:|tradução\s*:|sure[^:\n]*:)\s*", re.I)

def clean_output(text):
    t = text.strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    t = re.sub(r"^```\w*\s*|\s*```$", "", t).strip()
    for _ in range(2):
        t = PREAMBLE.sub("", t).strip()
    if len(t) >= 2 and t[0] in "\"'“”‘’«" and t[-1] in "\"'“”‘’»":
        t = t[1:-1].strip()
    return t

class Translator:
    def __init__(self, client, model="qwen2.5:3b", cache_file=None):
        self.client = client; self.model = model
        self.cache_file = Path(cache_file) if cache_file else None
        self.cache = {}; self._lock = threading.Lock()
        if self.cache_file and self.cache_file.exists():
            try: self.cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
            except Exception: self.cache = {}

    def _save(self):
        if self.cache_file:
            try: self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0), encoding="utf-8")
            except Exception: pass

    def translate(self, text):
        """Retorna o texto em inglês. Lança exceção se o Ollama falhar (o chamador decide o fallback)."""
        text = (text or "").strip()
        if not text or is_english(text):
            return text
        key = f"{self.model}\n{text}"
        with self._lock:
            if key in self.cache:
                return self.cache[key]
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
        out = clean_output(self.client.chat(self.model, msgs, {"temperature": 0, "seed": 0}))
        if not out:
            raise RuntimeError("Tradução vazia.")
        with self._lock:
            self.cache[key] = out; self._save()
        return out

    def translate_pair(self, prompt, negative=""):
        """(prompt_en, negative_en, aviso). Em caso de falha devolve os originais e um aviso."""
        try:
            self.client.ensure_running()
            return self.translate(prompt), self.translate(negative), ""
        except Exception as e:
            return prompt, negative, f"Tradução indisponível (Ollama: {e}). Usando o prompt original."
