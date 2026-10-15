import os, tempfile
os.environ.setdefault("IA_OFF_HOME", tempfile.mkdtemp())
from ia_off.translate import Translator, is_english, clean_output, SYSTEM_PROMPT

class FakeClient:
    def __init__(self, reply="A cat on the beach", fail=None):
        self.reply = reply; self.fail = fail; self.calls = []
    def ensure_running(self):
        if self.fail: raise self.fail
    def chat(self, model, messages, options=None):
        self.calls.append((model, messages, options))
        return self.reply(messages[-1]["content"]) if callable(self.reply) else self.reply

def test_heuristic():
    assert is_english("a cat sitting on the beach, high quality, 4k")
    assert not is_english("um gato na praia, alta qualidade")
    assert not is_english("menina com vestido azul")
    assert not is_english("coração")
    assert is_english("") and is_english("8k, 4k")

def test_clean():
    assert clean_output('"A red car"') == "A red car"
    assert clean_output("Here is the translation:\nA red car") == "A red car"
    assert clean_output("Translation: “A red car”") == "A red car"
    assert clean_output("<think>hmm</think>\nA red car") == "A red car"
    assert clean_output("```\nred car, night\n```") == "red car, night"

def test_translate_and_cache(tmp_path):
    c = FakeClient('Here is the translation: "a cat on the beach, high quality"')
    t = Translator(c, "qwen2.5:3b", tmp_path / "cache.json")
    assert t.translate("um gato na praia, alta qualidade") == "a cat on the beach, high quality"
    assert t.translate("um gato na praia, alta qualidade") == "a cat on the beach, high quality"
    assert len(c.calls) == 1
    model, msgs, opts = c.calls[0]
    assert model == "qwen2.5:3b" and opts["temperature"] == 0 and msgs[0]["content"] == SYSTEM_PROMPT
    assert "censor" in SYSTEM_PROMPT and "comma-separated" in SYSTEM_PROMPT
    # cache persistido em disco
    c2 = FakeClient("NÃO DEVE SER USADO"); t2 = Translator(c2, "qwen2.5:3b", tmp_path / "cache.json")
    assert t2.translate("um gato na praia, alta qualidade") == "a cat on the beach, high quality" and not c2.calls

def test_skip_english():
    c = FakeClient(); t = Translator(c)
    assert t.translate("a portrait of a woman with red hair") == "a portrait of a woman with red hair"
    assert not c.calls

def test_pair_and_fallback():
    c = FakeClient(lambda s: "blurry, low quality" if "borrado" in s else "a dog in the city")
    pe, ne, w = Translator(c).translate_pair("um cachorro na cidade", "borrado, baixa qualidade")
    assert (pe, ne, w) == ("a dog in the city", "blurry, low quality", "")
    down = FakeClient(fail=ConnectionError("recusado"))
    pe, ne, w = Translator(down).translate_pair("um gato", "feio")
    assert (pe, ne) == ("um gato", "feio") and "original" in w

def test_png_meta(tmp_path):
    from PIL import Image
    from ia_off.media_tabs import save_png, image_meta
    p = {"prompt": "a cat", "prompt_original": "um gato", "negative": "", "negative_original": "", "steps": 4,
         "guidance": 1.0, "width": 64, "height": 64}
    fp = tmp_path / "x.png"; save_png(Image.new("RGB", (8, 8)), fp, image_meta(p, "txt2img", 5))
    info = Image.open(fp).text
    assert info["prompt"] == "a cat" and info["prompt_original"] == "um gato" and info["seed"] == "5"
