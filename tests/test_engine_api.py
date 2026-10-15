"""Contrato dos motores: progress_cb(step,total) + cancel_flag.is_set() -> Cancelled. Só fakes."""
import sys, threading, time
from types import SimpleNamespace
import pytest
from ia_off import sdcpp
from ia_off.engine_api import Cancelled, make_cancel_check, make_progress
from ia_off.image_engine import ImageEngine, Cancelled as IECancelled
from ia_off.ov_engine import step_callback_kwargs


@pytest.fixture(autouse=True)
def fake_torch(monkeypatch):
    """Sem torch instalado, usa um torch falso mínimo (Generator/inference_mode/get_num_threads)."""
    try:
        import torch  # noqa: F401
        return
    except ImportError:
        import contextlib, types
        t = types.ModuleType("torch")
        class Gen:
            def __init__(self, dev): pass
            def manual_seed(self, s): return self
        t.Generator = Gen; t.inference_mode = contextlib.nullcontext; t.get_num_threads = lambda: 1
        monkeypatch.setitem(sys.modules, "torch", t)


class Flag:  # qualquer objeto com is_set()
    def __init__(self, v=False): self.v = v
    def is_set(self): return self.v


def test_api_helpers():
    assert IECancelled is Cancelled and issubclass(Cancelled, RuntimeError) and str(Cancelled()) == "Cancelado."
    assert make_cancel_check()() is False
    assert make_cancel_check(Flag(True))() and make_cancel_check(None, lambda: True)()
    a, b = [], []
    make_progress(lambda s, t: a.append((s, t)), lambda s, t: b.append((s, t)))(2, 5)
    assert a == b == [(2, 5)]


class FakePipe:
    """Imita StableDiffusionPipeline: chama callback_on_step_end a cada passo."""
    def __init__(self, on_call=None): self.on_call = on_call; self.calls = 0
    def __call__(self, num_inference_steps, callback_on_step_end=None, **kw):
        self.calls += 1
        for i in range(num_inference_steps):
            if self.on_call: self.on_call(i)
            callback_on_step_end(self, i, 0, {})
        return SimpleNamespace(images=[f"img{self.calls}"])


class FakeEngine(ImageEngine):
    def __init__(self, pipe):
        super().__init__({"threads": 1}); self.fake = pipe
    def _threads(self): pass
    def pipeline(self, mode, lcm=True): return self.fake


def test_diffusers_progress_and_compat():
    got, legacy = [], []
    eng = FakeEngine(FakePipe())
    r = eng.generate("txt2img", "gato", steps=3, batch=2, seed=1, backend="torch",
                     progress_cb=lambda s, t: got.append((s, t)), progress=lambda s, t: legacy.append((s, t)))
    assert [x[0] for x in r] == [1, 2]
    assert got == legacy == [(1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6)]
    # sem os novos args (chamada antiga) continua funcionando
    assert len(FakeEngine(FakePipe()).generate("txt2img", "x", steps=2, backend="torch")) == 1


def test_diffusers_cancel_mid_run():
    flag = threading.Event(); got = []
    pipe = FakePipe(on_call=lambda i: flag.set() if i == 2 else None)
    with pytest.raises(Cancelled):
        FakeEngine(pipe).generate("txt2img", "x", steps=5, batch=3, backend="torch",
                                  progress_cb=lambda s, t: got.append(s), cancel_flag=flag)
    assert got == [1, 2] and pipe.calls == 1
    with pytest.raises(Cancelled):  # já cancelado: nem carrega
        FakeEngine(FakePipe()).generate("txt2img", "x", backend="torch", cancel_flag=Flag(True))


def test_ov_callback_new_and_legacy():
    seen = []
    class New:
        def __call__(self, prompt=None, callback_on_step_end=None): pass
    class Old:
        def __call__(self, prompt=None, callback=None, callback_steps=1): pass
    kw = step_callback_kwargs(New(), seen.append)
    assert kw["callback_on_step_end"](None, 0, 0, {"a": 1}) == {"a": 1}
    kw = step_callback_kwargs(Old(), seen.append)
    assert kw["callback_steps"] == 1; kw["callback"](1, 0, None)
    assert seen == [0, 1]


def test_ov_backend_cancel_does_not_fallback():
    flag = Flag(False); got = []
    class OVPipe:
        def __call__(self, num_inference_steps, callback=None, callback_steps=1, **kw):
            for i in range(num_inference_steps):
                if i == 1: flag.v = True
                callback(i, 0, None)
    class FakeOV:
        def pipeline(self, *a, cancel_flag=None, **k): return OVPipe()
    eng = FakeEngine(FakePipe()); eng._ov_engine = lambda dev: FakeOV()
    with pytest.raises(Cancelled):
        eng.generate("txt2img", "x", steps=4, backend="ov:GPU", progress_cb=lambda s, t: got.append(s), cancel_flag=flag)
    assert got == [1] and not eng.ov_failed and eng.fake.calls == 0


def test_ov_pipeline_checks_flag_before_loading():
    from ia_off.ov_engine import OVEngine
    with pytest.raises(Cancelled):
        OVEngine({}, "GPU").pipeline("txt2img", True, 64, 64, 1, cancel_flag=Flag(True))


FAKE_CLI = ("import sys,time\nn=int(sys.argv[1])\nprint('[INFO] loading', flush=True)\n"
            "for i in range(1,n+1):\n    sys.stdout.write(f'\\r  |==> | {i}/{n} - 1.0s/it'); sys.stdout.flush(); time.sleep(float(sys.argv[2]))\nprint()\n")


def test_sdcpp_progress_cb(tmp_path):
    f = tmp_path / "cli.py"; f.write_text(FAKE_CLI); got = []
    sdcpp.run([sys.executable, str(f), "4", "0"], progress_cb=lambda s, t: got.append((s, t)))
    assert got == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_sdcpp_cancel_kills_process(tmp_path):
    f = tmp_path / "cli.py"; f.write_text(FAKE_CLI); flag = threading.Event(); got = []
    def cb(s, t):
        got.append(s)
        if s == 2: flag.set()
    t0 = time.time()
    with pytest.raises(Cancelled):
        sdcpp.run([sys.executable, str(f), "100", "0.2"], progress_cb=cb, cancel_flag=flag)
    assert time.time() - t0 < 10 and max(got) < 100


def test_sdcpp_cancel_silent_process(tmp_path):
    f = tmp_path / "quiet.py"; f.write_text("import time\ntime.sleep(60)\n"); flag = threading.Event()
    threading.Timer(0.5, flag.set).start(); t0 = time.time()
    with pytest.raises(Cancelled):
        sdcpp.run([sys.executable, str(f)], cancel_flag=flag)
    assert time.time() - t0 < 10


def test_run_with_fallback_cancel_and_progress(tmp_path):
    f = tmp_path / "cli.py"; f.write_text(FAKE_CLI); got = []
    used = sdcpp.run_with_fallback(None, "cpu", lambda b: [sys.executable, str(f), "3", "0"],
                                   ensure=lambda *a: "x", progress_cb=lambda s, t: got.append(s))
    assert used == "cpu" and got == [1, 2, 3]
    calls = []
    def ensure(folder, variant, progress, cancelled):
        calls.append(variant); return "x"
    with pytest.raises(Cancelled):
        sdcpp.run_with_fallback(None, "vulkan", lambda b: [sys.executable, str(f), "3", "0"],
                                ensure=ensure, cancel_flag=Flag(True))
    assert calls == ["vulkan"]  # não cai para a CPU após cancelar
