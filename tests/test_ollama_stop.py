"""chat_stream: Parar interrompe rápido mesmo sem chunk chegando (servidor HTTP falso local)."""
import json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from ia_off.ollama_client import OllamaClient

ESPERA_ANTES_DO_1o = 6.0


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.server.modo == "vigia_desconexao":
            # segura antes dos headers e registra quando o cliente desconecta (EOF no recv)
            import select, socket as _s
            fim = time.monotonic() + ESPERA_ANTES_DO_1o
            while time.monotonic() < fim:
                pr, _, _ = select.select([self.connection], [], [], 0.02)
                if pr:
                    try:
                        dado = self.connection.recv(1, _s.MSG_PEEK)
                    except OSError:
                        dado = b""
                    if not dado:
                        self.server.desconectou = time.monotonic(); return
            self.server.modo = ""
        if self.server.modo == "sem_headers":
            time.sleep(ESPERA_ANTES_DO_1o)   # Ollama: headers só saem junto com o 1º chunk
        if self.server.modo == "erro_http":
            self.send_response(500); self.end_headers(); self.wfile.write(b"falhou"); return
        self.send_response(200); self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        def chunk(d):
            b = (json.dumps(d) + "\n").encode()
            self.wfile.write(f"{len(b):x}\r\n".encode() + b + b"\r\n"); self.wfile.flush()
        try:
            if self.server.lento:
                time.sleep(ESPERA_ANTES_DO_1o)   # "processando o prompt"
            if self.server.modo == "erro_linha":
                chunk({"error": "modelo quebrou"}); self.wfile.write(b"0\r\n\r\n"); return
            for t in ["Olá", ", ", "mundo"]:
                chunk({"message": {"content": t}, "done": False})
            chunk({"message": {"content": ""}, "done": True})
            self.wfile.write(b"0\r\n\r\n")
        except OSError:
            pass


@pytest.fixture
def server():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _H); s.daemon_threads = True; s.lento = False; s.modo = ""; s.desconectou = None
    th = threading.Thread(target=s.serve_forever, daemon=True); th.start()
    yield s
    s.shutdown(); s.server_close()


def _cli(s): return OllamaClient(f"http://127.0.0.1:{s.server_address[1]}")


def test_stream_completo(server):
    assert "".join(_cli(server).chat_stream("m", [], {})) == "Olá, mundo"


def test_parar_antes_do_primeiro_chunk(server):
    server.lento = True; stop = threading.Event(); out = []
    gen = _cli(server).chat_stream("m", [], {}, stop_flag=stop.is_set)
    threading.Timer(0.3, stop.set).start(); t0 = time.monotonic()
    for c in gen: out.append(c)          # não pode levantar
    dt = time.monotonic() - (t0 + 0.3)   # tempo desde o stop
    print(f"\nparada em {dt:.3f} s após o stop")
    assert out == [] and dt < 1.0


def test_parar_antes_dos_headers(server):
    server.modo = "sem_headers"; stop = threading.Event(); out = []
    gen = _cli(server).chat_stream("m", [], {}, stop_flag=stop.is_set)
    threading.Timer(0.3, stop.set).start(); t0 = time.monotonic()
    for c in gen: out.append(c)
    dt = time.monotonic() - (t0 + 0.3)
    print(f"\nparada antes dos headers em {dt:.3f} s após o stop")
    assert out == [] and dt < 1.0


@pytest.mark.parametrize("modo", ["erro_http", "erro_linha"])
def test_erros_reais_ainda_levantam(server, modo):
    from ia_off.ollama_client import OllamaError
    server.modo = modo
    with pytest.raises(OllamaError):
        list(_cli(server).chat_stream("m", [], {}))


def test_stop_flag_que_levanta_nao_quebra(server):
    def ruim(): raise RuntimeError("x")
    assert "".join(_cli(server).chat_stream("m", [], {}, stop_flag=ruim)) == "Olá, mundo"


def test_servidor_fora_levanta():
    import requests
    with pytest.raises(requests.RequestException):
        list(OllamaClient("http://127.0.0.1:9").chat_stream("m", [], {}))


def test_parar_antes_dos_headers_derruba_conexao(server):
    """O servidor (Ollama) precisa VER a desconexão logo, para cancelar o prompt na CPU."""
    server.modo = "vigia_desconexao"; stop = threading.Event()
    gen = _cli(server).chat_stream("m", [], {}, stop_flag=stop.is_set)
    threading.Timer(0.3, stop.set).start(); t0 = time.monotonic()
    assert list(gen) == []
    t_stop = t0 + 0.3; dt_cli = time.monotonic() - t_stop
    while server.desconectou is None and time.monotonic() - t_stop < 3: time.sleep(0.01)
    assert server.desconectou is not None, "servidor não viu a desconexão"
    dt_srv = server.desconectou - t_stop
    print(f"\ncliente parou em {dt_cli:.3f} s; servidor detectou desconexão em {dt_srv:.3f} s")
    assert dt_cli < 1.0 and dt_srv < 1.0
    server.modo = ""   # 2º pedido logo depois funciona normal
    assert "".join(_cli(server).chat_stream("m", [], {})) == "Olá, mundo"
