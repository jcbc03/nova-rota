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
        self.send_response(200); self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        def chunk(d):
            b = (json.dumps(d) + "\n").encode()
            self.wfile.write(f"{len(b):x}\r\n".encode() + b + b"\r\n"); self.wfile.flush()
        try:
            if self.server.lento:
                time.sleep(ESPERA_ANTES_DO_1o)   # "processando o prompt"
            for t in ["Olá", ", ", "mundo"]:
                chunk({"message": {"content": t}, "done": False})
            chunk({"message": {"content": ""}, "done": True})
            self.wfile.write(b"0\r\n\r\n")
        except OSError:
            pass


@pytest.fixture
def server():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _H); s.daemon_threads = True; s.lento = False
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
