import json, os, shutil, subprocess, sys, time, tempfile, threading, socket, queue
from pathlib import Path
import requests
import urllib3.connection
import urllib3.connectionpool
import requests.adapters

class OllamaError(Exception):
    pass


def _sessao_com_socket(socks):
    """Cria uma requests.Session que registra todo socket TCP conectado na lista socks
    (para poder matá-lo antes dos headers chegarem)."""
    class _Conn(urllib3.connection.HTTPConnection):
        def connect(self):
            super().connect()
            socks.append(self.sock)

    class _Pool(urllib3.connectionpool.HTTPConnectionPool):
        ConnectionCls = _Conn

    class _Adapter(requests.adapters.HTTPAdapter):
        def init_poolmanager(self, *a, **kw):
            super().init_poolmanager(*a, **kw)
            self.poolmanager.pool_classes_by_scheme = {
                **self.poolmanager.pool_classes_by_scheme,
                "http": _Pool,
            }

    s = requests.Session()
    s.mount("http://", _Adapter())
    return s


def _matar_sockets(socks):
    """Fecha agressivamente todos os sockets registrados (shutdown + close)."""
    for sock in socks:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

class OllamaClient:
    def __init__(self, url="http://localhost:11434", exe=""):
        self.url = url.rstrip("/")
        self.exe = exe

    def find_exe(self):
        if self.exe and Path(self.exe).is_file():
            return self.exe
        return shutil.which("ollama") or ""

    def is_running(self):
        try:
            return requests.get(self.url + "/api/version", timeout=2).ok
        except requests.RequestException:
            return False

    def ensure_running(self, wait=15):
        if self.is_running():
            return True
        exe = self.find_exe()
        if not exe:
            raise OllamaError("Ollama não encontrado. Verifique o caminho em Configurações.")
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags)
        t = time.time()
        while time.time() - t < wait:
            if self.is_running():
                return True
            time.sleep(0.5)
        raise OllamaError("Não foi possível iniciar o Ollama (ollama serve).")

    def list_models(self):
        r = requests.get(self.url + "/api/tags", timeout=5)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))

    def has_model(self, name):
        names = self.list_models()
        return any(n == name or n.split(":")[0] == name.split(":")[0] for n in names)

    def chat_stream(self, model, messages, options, stop_flag=lambda: False):
        """Gera tokens via streaming do /api/chat com worker daemon para resposta rápida ao stop_flag.
        Problema resolvido: requests.post bloqueia até primeiro header (~5s); worker inicia request imediatamente.
        """
        body = {"model": model, "messages": messages, "stream": True, "options": options}
        parar = threading.Event()
        estado = {}
        q = queue.Queue()
        socks = []

        def _fechar(r):
            """Fecha conexão de forma agressiva (best-effort) para acordar iter_lines bloqueado."""
            try:
                if not r:
                    return
                sock = None
                try:
                    conn = getattr(r.raw, "_connection", None)
                    sock = getattr(conn, "sock", None)
                except Exception:
                    pass
                if sock is None:
                    try:
                        sock = r.raw._fp.fp.raw._sock
                    except Exception:
                        pass
                if sock is not None:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                r.close()
                if hasattr(r, 'raw') and r.raw:
                    r.raw.close()
            except Exception:
                pass

        def worker():
            r = None
            sessao = None
            try:
                sessao = _sessao_com_socket(socks)
                r = sessao.post(self.url + "/api/chat", json=body, stream=True, timeout=(5, 600))
                estado["r"] = r
                if parar.is_set():
                    _fechar(r)
                    return
                if not r.ok:
                    q.put(("erro", OllamaError(f"Erro {r.status_code}: {r.text[:300]}")))
                    return
                for line in r.iter_lines():
                    if parar.is_set():
                        break
                    q.put(("linha", line))
                q.put(("fim", None))
            except Exception as e:
                if not parar.is_set():
                    q.put(("erro", e))
            finally:
                if r:
                    _fechar(r)
                if sessao:
                    try:
                        sessao.close()
                    except Exception:
                        pass
                _matar_sockets(socks)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def _parou():
            try:
                return bool(stop_flag())
            except Exception:
                return False

        try:
            while True:
                if _parou():
                    parar.set()
                    if estado.get("r") is not None:
                        _fechar(estado["r"])
                    _matar_sockets(socks)
                    return
                try:
                    kind, val = q.get(timeout=0.05)
                    if kind == "fim":
                        return
                    elif kind == "erro":
                        raise val
                    elif kind == "linha":
                        if not val:
                            continue
                        d = json.loads(val)
                        if "error" in d:
                            raise OllamaError(d["error"])
                        c = d.get("message", {}).get("content", "")
                        if c:
                            yield c
                        if d.get("done"):
                            parar.set()
                            return
                except queue.Empty:
                    continue
        finally:
            parar.set()
            if estado.get("r") is not None:
                _fechar(estado.get("r"))
            _matar_sockets(socks)

    def chat(self, model, messages, options=None):
        r = requests.post(self.url + "/api/chat", json={"model": model, "messages": messages, "stream": False,
                          "options": options or {}}, timeout=(5, 300))
        if not r.ok:
            raise OllamaError(f"Erro {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {}).get("content", "")

    def generate(self, model, prompt, options=None):
        r = requests.post(self.url + "/api/generate", json={"model": model, "prompt": prompt,
                          "stream": False, "options": options or {}}, timeout=600)
        r.raise_for_status()
        return r.json().get("response", "")

    def embed(self, model, texts):
        r = requests.post(self.url + "/api/embed", json={"model": model, "input": texts}, timeout=600)
        if r.status_code == 404 and "not found" not in r.text.lower():
            # old Ollama fallback
            return [requests.post(self.url + "/api/embeddings", json={"model": model, "prompt": t},
                                  timeout=300).json()["embedding"] for t in texts]
        if not r.ok:
            raise OllamaError(f"Erro de embeddings {r.status_code}: {r.text[:300]}")
        return r.json()["embeddings"]

    def pull(self, model, progress=lambda s: None):
        with requests.post(self.url + "/api/pull", json={"model": model, "stream": True},
                           stream=True, timeout=(5, 3600)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if "error" in d:
                    raise OllamaError(d["error"])
                st = d.get("status", "")
                if d.get("total"):
                    st += f" {100*d.get('completed',0)//d['total']}%"
                progress(st)

def build_modelfile(gguf_path, num_ctx=4096, threads=4, temperature=0.7, system=""):
    lines = [f'FROM "{gguf_path}"',
             f"PARAMETER num_ctx {int(num_ctx)}",
             f"PARAMETER num_thread {int(threads)}",
             f"PARAMETER temperature {float(temperature)}"]
    if system:
        lines.append('SYSTEM """' + system.replace('"""', "'''") + '"""')
    return "\n".join(lines) + "\n"

def create_from_gguf(exe, name, gguf_path, **kw):
    """Gera Modelfile referenciando o GGUF no lugar e executa `ollama create`."""
    if not Path(gguf_path).is_file():
        raise OllamaError(f"Arquivo GGUF não encontrado: {gguf_path}")
    if not exe:
        raise OllamaError("ollama.exe não encontrado.")
    d = Path(tempfile.mkdtemp(prefix="iaoff_mf_"))
    mf = d / "Modelfile"
    mf.write_text(build_modelfile(gguf_path, **kw), encoding="utf-8")
    flags = 0x08000000 if sys.platform == "win32" else 0
    p = subprocess.run([exe, "create", name, "-f", str(mf)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=flags)
    if p.returncode != 0:
        raise OllamaError((p.stderr or p.stdout)[-800:])
    return (p.stdout or "") + (p.stderr or "")
