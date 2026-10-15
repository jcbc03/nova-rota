import os, sys, html, traceback
import markdown as md
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextBrowser, QPlainTextEdit, QPushButton, QComboBox, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QFormLayout, QFileDialog, QMessageBox, QInputDialog, QSplitter, QDialog,
    QDialogButtonBox)
from . import config
from .ollama_client import OllamaClient, OllamaError, create_from_gguf
from .storage import Storage
from .rag import VectorStore, index_file, build_prompt, citations, migrate
from .job_queue import JobQueue

STYLE = """
* { font-family: 'Segoe UI', sans-serif; font-size: 10.5pt; color: #e6e6e6; }
QMainWindow, QWidget { background: #1e1f24; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #2a2c33; padding: 8px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
QTabBar::tab:selected { background: #3b5bdb; }
QPushButton { background: #3b5bdb; border: 0; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background: #4c6ef5; } QPushButton:disabled { background: #444; color: #888; }
QPushButton#danger { background: #c92a2a; }
QListWidget, QTextBrowser, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
  background: #2a2c33; border: 1px solid #3a3d46; border-radius: 6px; padding: 4px; }
QListWidget::item:selected { background: #3b5bdb; }
QLabel#hint { color: #9aa0aa; }
"""
CSS = "body{color:#e6e6e6} pre{background:#111;padding:6px} code{background:#111} .u{color:#8ab4ff} .a{color:#9be9a8}"

def md_html(text):
    return md.markdown(text, extensions=["fenced_code", "tables"])

def run_bg(owner, fn, on_chunk=None, on_done=None, on_error=None):
    """Roda fn(job) numa thread; callbacks sempre na thread da GUI (ver jobs.py)."""
    from .jobs import Job
    j = Job(fn, owner, on_chunk=on_chunk, on_done=lambda r: on_done and on_done(r if r is not None else ""),
            on_error=on_error or (lambda m: QMessageBox.warning(owner, "Erro", m)))
    j.start(); return j

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self.client = OllamaClient(self.cfg["ollama_url"], self.cfg["ollama_exe"])
        self.db = Storage(config.APP_DIR / "conversas.db")
        self.store = VectorStore()  # pasta vem do rag_dir do config.py
        self.fila = JobQueue(self)  # criada na thread da tela; a interface só escuta os sinais
        from .engines_registry import register_all; register_all(self.fila)
        self.conv_id = None; self.worker = None; self.answer = ""
        self.setWindowTitle("IA Off — Assistente Local"); self.resize(1200, 780)
        tabs = QTabWidget(); self.setCentralWidget(tabs)
        tabs.addTab(self._chat_tab(), "Chat")
        tabs.addTab(self._docs_tab(), "Documentos")
        self.status = self.statusBar()
        from .media_tabs import ImageTab, VideoTab
        self.image_tab = ImageTab(lambda: dict(self.cfg), self.status, self.set_cfg)
        self.video_tab = VideoTab(lambda: dict(self.cfg), self.status, self.set_cfg)
        tabs.addTab(self.image_tab, "Imagem")
        tabs.addTab(self.video_tab, "Vídeo")
        tabs.addTab(self._soon("Reconhecimento e síntese de voz"), "Voz")
        tabs.addTab(self._settings_tab(), "Configurações")
        self.reload_convs()
        self.refresh_models()
        if self.store.needs_migration:
            try:
                n = migrate(self.store, lambda m: (self.status.showMessage(m), QApplication.processEvents()))
                self.status.showMessage(f"Índice de documentos convertido: {n} trechos", 8000)
            except Exception as ex:
                QMessageBox.warning(self, "Documentos", f"Não consegui converter o índice antigo: {ex}")

    # ---------- Chat ----------
    def _chat_tab(self):
        w = QWidget(); sp = QSplitter(); lay = QHBoxLayout(w); lay.addWidget(sp)
        left = QWidget(); l = QVBoxLayout(left)
        b = QPushButton("+ Nova conversa"); b.clicked.connect(self.new_conv); l.addWidget(b)
        self.conv_list = QListWidget(); self.conv_list.currentItemChanged.connect(self.open_conv); l.addWidget(self.conv_list)
        h = QHBoxLayout(); r = QPushButton("Renomear"); r.clicked.connect(self.rename_conv)
        d = QPushButton("Excluir"); d.setObjectName("danger"); d.clicked.connect(self.delete_conv)
        h.addWidget(r); h.addWidget(d); l.addLayout(h)
        right = QWidget(); v = QVBoxLayout(right)
        top = QHBoxLayout(); top.addWidget(QLabel("Modelo:"))
        self.model_box = QComboBox(); self.model_box.setMinimumWidth(260); top.addWidget(self.model_box)
        rb = QPushButton("Atualizar"); rb.clicked.connect(self.refresh_models); top.addWidget(rb)
        ib = QPushButton("Importar GGUF…"); ib.clicked.connect(self.import_gguf); top.addWidget(ib)
        top.addStretch(); v.addLayout(top)
        self.view = QTextBrowser(); self.view.setOpenExternalLinks(False); v.addWidget(self.view, 1)
        self.input = QPlainTextEdit(); self.input.setPlaceholderText("Digite sua mensagem… (Ctrl+Enter para enviar)")
        self.input.setMaximumHeight(110); self.input.keyPressEvent = self._key(self.input.keyPressEvent); v.addWidget(self.input)
        bh = QHBoxLayout()
        self.send_btn = QPushButton("Enviar"); self.send_btn.clicked.connect(self.send)
        self.stop_btn = QPushButton("Parar"); self.stop_btn.setObjectName("danger"); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        cb = QPushButton("Copiar última resposta"); cb.clicked.connect(self.copy_last)
        bh.addWidget(self.send_btn); bh.addWidget(self.stop_btn); bh.addWidget(cb); bh.addStretch(); v.addLayout(bh)
        sp.addWidget(left); sp.addWidget(right); sp.setSizes([260, 940])
        return w

    def _key(self, orig):
        def f(e):
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ControlModifier:
                self.send()
            else:
                orig(e)
        return f

    def options(self):
        return {"num_ctx": self.cfg["num_ctx"], "num_thread": self.cfg["threads"], "temperature": self.cfg["temperature"]}

    def ensure(self):
        try:
            self.client.ensure_running(); return True
        except OllamaError as e:
            QMessageBox.warning(self, "Ollama", str(e)); return False

    def refresh_models(self):
        cur = self.model_box.currentText() or self.cfg.get("model")
        def job(w):
            self.client.ensure_running(); return "\n".join(self.client.list_models())
        def ok(s):
            self.model_box.clear(); names = [n for n in s.split("\n") if n]
            self.model_box.addItems(names)
            if cur in names: self.model_box.setCurrentText(cur)
            self.status.showMessage(f"{len(names)} modelo(s) no Ollama", 5000)
        run_bg(self, job, on_done=ok, on_error=lambda m: self.status.showMessage("Ollama indisponível: " + m))

    def reload_convs(self):
        self.conv_list.blockSignals(True); self.conv_list.clear()
        for cid, title in self.db.list_convs():
            it = QListWidgetItem(title); it.setData(Qt.UserRole, cid); self.conv_list.addItem(it)
            if cid == self.conv_id: self.conv_list.setCurrentItem(it)
        self.conv_list.blockSignals(False)

    def new_conv(self):
        self.conv_id = self.db.new_conv(); self.reload_convs(); self.render()

    def open_conv(self, it, _=None):
        if it: self.conv_id = it.data(Qt.UserRole); self.render()

    def rename_conv(self):
        if not self.conv_id: return
        t, ok = QInputDialog.getText(self, "Renomear", "Novo título:")
        if ok and t.strip(): self.db.rename(self.conv_id, t.strip()); self.reload_convs()

    def delete_conv(self):
        if self.conv_id and QMessageBox.question(self, "Excluir", "Excluir esta conversa?") == QMessageBox.Yes:
            self.db.delete(self.conv_id); self.conv_id = None; self.reload_convs(); self.view.clear()

    def render(self, partial=None):
        """Desenha a conversa. Com partial, reaproveita o HTML do histórico em cache
        (sem reler o banco nem reconverter o markdown antigo a cada pedaço)."""
        if partial is None or getattr(self, "_hist_cid", object()) != self.conv_id:
            msgs = self.db.messages(self.conv_id) if self.conv_id else []
            out = [f"<style>{CSS}</style>"]
            for m in msgs:
                who = "<b class='u'>Você</b>" if m["role"] == "user" else "<b class='a'>IA</b>"
                out.append(f"<p>{who}</p>{md_html(m['content'])}<hr>")
            self._hist_html = "".join(out); self._hist_cid = self.conv_id
        html_ = self._hist_html
        if partial is not None:
            html_ += f"<p><b class='a'>IA</b> <i>(gerando…)</i></p>{md_html(partial)}"
        sb = self.view.verticalScrollBar()
        at_end = partial is None or sb.value() >= sb.maximum() - 40
        self.view.setHtml(html_)
        if at_end: sb.setValue(sb.maximum())

    def _schedule_render(self):
        """Agrupa os pedaços do streaming: no máximo ~12 redesenhos por segundo."""
        if not hasattr(self, "_render_timer"):
            self._render_timer = QTimer(self); self._render_timer.setSingleShot(True); self._render_timer.setInterval(80)
            self._render_timer.timeout.connect(lambda: self.worker and self.render(self.answer))
        if not self._render_timer.isActive(): self._render_timer.start()

    def send(self):
        text = self.input.toPlainText().strip()
        model = self.model_box.currentText()
        if not text or self.worker: return
        if not model:
            QMessageBox.information(self, "Modelo", "Nenhum modelo selecionado. Clique em Atualizar ou importe um GGUF."); return
        if not self.conv_id:
            self.conv_id = self.db.new_conv(text[:40]); self.reload_convs()
        elif not self.db.messages(self.conv_id):
            self.db.rename(self.conv_id, text[:40]); self.reload_convs()
        self.db.add_msg(self.conv_id, "user", text); self.input.clear()
        msgs = [{"role": "system", "content": self.cfg["system_prompt"]}] + self.db.messages(self.conv_id)
        self.cfg["model"] = model; config.save(self.cfg)
        self.answer = ""; self._hist_cid = None; self.render("")
        cid = self.conv_id
        def job(w):
            self.client.ensure_running()
            for c in self.client.chat_stream(model, msgs, self.options(), lambda: w.stopped):
                w.chunk.emit(c)
            return ""
        def chunk(c):
            self.answer += c; self._schedule_render()
        def fin(_=""):
            if self.answer: self.db.add_msg(cid, "assistant", self.answer)
            if hasattr(self, "_render_timer"): self._render_timer.stop()
            self.worker = None; self.send_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.render()
        def err(m):
            fin(); QMessageBox.warning(self, "Erro no chat", m)
        self.send_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.worker = run_bg(self, job, chunk, fin, err)

    def stop(self):
        if self.worker: self.worker.stopped = True

    def copy_last(self):
        msgs = [m for m in (self.db.messages(self.conv_id) if self.conv_id else []) if m["role"] == "assistant"]
        if msgs: QApplication.clipboard().setText(msgs[-1]["content"]); self.status.showMessage("Copiado!", 3000)

    def import_gguf(self):
        dlg = QDialog(self); dlg.setWindowTitle("Importar GGUF para o Ollama"); f = QFormLayout(dlg)
        sug = QComboBox(); sug.addItem("(escolher arquivo…)")
        for n, p in config.GGUF_SUGGESTIONS: sug.addItem(f"{n} — {p}", (n, p))
        name = QLineEdit(); path = QLineEdit(); br = QPushButton("Procurar…")
        def pick(i):
            d = sug.itemData(i)
            if d: name.setText(d[0]); path.setText(d[1])
        sug.currentIndexChanged.connect(pick)
        br.clicked.connect(lambda: path.setText(QFileDialog.getOpenFileName(dlg, "GGUF", "", "GGUF (*.gguf)")[0] or path.text()))
        ph = QHBoxLayout(); ph.addWidget(path); ph.addWidget(br)
        f.addRow("Sugestões:", sug); f.addRow("Nome no Ollama:", name); f.addRow("Arquivo:", ph)
        f.addRow(QLabel("O arquivo é usado no lugar (não é copiado pelo app).", objectName="hint"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); f.addRow(bb)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted or not name.text().strip() or not path.text().strip(): return
        n, p = name.text().strip().lower(), path.text().strip()
        self.status.showMessage(f"Importando {n}… (pode demorar)")
        def job(w):
            self.client.ensure_running()
            return create_from_gguf(self.client.find_exe(), n, p, num_ctx=self.cfg["num_ctx"],
                                    threads=self.cfg["threads"], temperature=self.cfg["temperature"])
        run_bg(self, job, on_done=lambda s: (self.status.showMessage(f"Modelo {n} criado!", 8000), self.refresh_models()))

    # ---------- Documentos ----------
    def _docs_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        h = QHBoxLayout()
        a = QPushButton("Adicionar arquivos…"); a.clicked.connect(self.add_docs)
        r = QPushButton("Remover selecionado"); r.clicked.connect(self.remove_doc)
        c = QPushButton("Limpar base"); c.setObjectName("danger"); c.clicked.connect(self.clear_docs)
        self.pull_btn = QPushButton("Baixar modelo de embeddings"); self.pull_btn.clicked.connect(self.pull_embed)
        for x in (a, r, c, self.pull_btn): h.addWidget(x)
        h.addStretch(); v.addLayout(h)
        self.emb_label = QLabel(f"Modelo de embeddings: {self.cfg['embed_model']}", objectName="hint"); v.addWidget(self.emb_label)
        self.doc_list = QListWidget(); self.doc_list.setMaximumHeight(160); v.addWidget(self.doc_list)
        self.rag_out = QTextBrowser(); v.addWidget(self.rag_out, 1)
        qh = QHBoxLayout(); self.rag_q = QLineEdit(); self.rag_q.setPlaceholderText("Pergunte sobre seus documentos…")
        self.rag_q.returnPressed.connect(self.ask_docs)
        self.rag_btn = QPushButton("Perguntar"); self.rag_btn.clicked.connect(self.ask_docs)
        qh.addWidget(self.rag_q); qh.addWidget(self.rag_btn); v.addLayout(qh)
        self.reload_docs(); return w

    def reload_docs(self):
        self.doc_list.clear(); self.doc_list.addItems(self.store.sources())

    def _embed_ok(self):
        try:
            self.client.ensure_running()
            if not self.client.has_model(self.cfg["embed_model"]):
                QMessageBox.information(self, "Embeddings", f"O modelo '{self.cfg['embed_model']}' não está instalado.\n"
                                        "Clique em 'Baixar modelo de embeddings' (precisa de internet uma vez).")
                return False
            return True
        except Exception as e:
            QMessageBox.warning(self, "Ollama", str(e)); return False

    def pull_embed(self):
        m = self.cfg["embed_model"]; self.pull_btn.setEnabled(False)
        def job(w):
            self.client.ensure_running(); self.client.pull(m, w.chunk.emit); return ""
        def end(*_): self.pull_btn.setEnabled(True)
        run_bg(self, job, on_chunk=lambda s: self.status.showMessage("Baixando: " + s),
               on_done=lambda _: (end(), self.status.showMessage(f"{m} instalado!", 5000)),
               on_error=lambda e: (end(), QMessageBox.warning(self, "Erro", e)))

    def add_docs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Documentos", "", "Documentos (*.pdf *.txt *.md *.docx)")
        if not files or not self._embed_ok(): return
        em = self.cfg["embed_model"]
        def job(w):
            n = 0
            for f in files:
                n += index_file(f, self.store, lambda t: self.client.embed(em, t), progress=w.chunk.emit)
            return f"{n} trechos indexados."
        run_bg(self, job, on_chunk=lambda s: self.status.showMessage(s),
               on_done=lambda s: (self.reload_docs(), self.status.showMessage(s, 6000)),
               on_error=lambda e: (self.reload_docs(), QMessageBox.warning(self, "Erro", e)))

    def remove_doc(self):
        it = self.doc_list.currentItem()
        if it: self.store.remove_source(it.text()); self.reload_docs()

    def clear_docs(self):
        if QMessageBox.question(self, "Limpar", "Apagar toda a base de documentos?") == QMessageBox.Yes:
            self.store.clear(); self.reload_docs()

    def ask_docs(self):
        q = self.rag_q.text().strip(); model = self.model_box.currentText()
        if not q or not model or not self.store.meta or not self._embed_ok(): 
            if not self.store.meta: self.rag_out.setPlainText("Adicione documentos primeiro.")
            return
        self.rag_btn.setEnabled(False); self.rag_out.setHtml(f"<style>{CSS}</style><i>Buscando…</i>")
        em = self.cfg["embed_model"]; buf = []
        def job(w):
            hits = self.store.search(self.client.embed(em, [q])[0], k=4)
            msgs = [{"role": "user", "content": build_prompt(q, hits)}]
            for c in self.client.chat_stream(model, msgs, self.options()):
                w.chunk.emit(c)
            return citations(hits)
        def chunk(c):
            buf.append(c); self.rag_out.setHtml(f"<style>{CSS}</style>" + md_html("".join(buf)))
        def done(cit):
            self.rag_btn.setEnabled(True)
            self.rag_out.setHtml(f"<style>{CSS}</style>" + md_html("".join(buf)) + "<hr><b>Fontes:</b><pre>" + html.escape(cit) + "</pre>")
        run_bg(self, job, chunk, done, lambda e: (self.rag_btn.setEnabled(True), QMessageBox.warning(self, "Erro", e)))

    # ---------- Outros ----------
    def _soon(self, txt):
        w = QWidget(); v = QVBoxLayout(w); l = QLabel(f"<h2>Em breve</h2><p>{txt}</p>"); l.setAlignment(Qt.AlignCenter)
        v.addWidget(l); return w

    def _settings_tab(self):
        inner = QWidget(); f = QFormLayout(inner)
        from PySide6.QtWidgets import QScrollArea
        w = QScrollArea(); w.setWidgetResizable(True); w.setWidget(inner)
        self.s_url = QLineEdit(self.cfg["ollama_url"]); self.s_exe = QLineEdit(self.cfg["ollama_exe"])
        self.s_thr = QSpinBox(); self.s_thr.setRange(1, 64); self.s_thr.setValue(self.cfg["threads"])
        self.s_ctx = QSpinBox(); self.s_ctx.setRange(512, 131072); self.s_ctx.setSingleStep(1024); self.s_ctx.setValue(self.cfg["num_ctx"])
        self.s_tmp = QDoubleSpinBox(); self.s_tmp.setRange(0, 2); self.s_tmp.setSingleStep(0.1); self.s_tmp.setValue(self.cfg["temperature"])
        self.s_emb = QLineEdit(self.cfg["embed_model"])
        self.s_trm = QLineEdit(self.cfg.get("translate_model", "qwen2.5:3b"))
        self.s_sys = QPlainTextEdit(self.cfg["system_prompt"]); self.s_sys.setMaximumHeight(120)
        f.addRow("URL do Ollama:", self.s_url); f.addRow("Caminho do ollama.exe:", self.s_exe)
        f.addRow("Threads (CPU):", self.s_thr); f.addRow("Tamanho do contexto:", self.s_ctx)
        f.addRow("Temperatura:", self.s_tmp); f.addRow("Modelo de embeddings:", self.s_emb)
        f.addRow("Modelo de tradução (PT→EN):", self.s_trm)
        f.addRow("Prompt de sistema:", self.s_sys)
        f.addRow(QLabel("<b>Caminhos dos modelos de imagem/vídeo</b>"))
        self.s_paths = {}
        for key, label, kind in config.MEDIA_PATH_KEYS:
            le = QLineEdit(self.cfg.get(key, "")); br = QPushButton("…"); br.setFixedWidth(32)
            def pick(_=False, le=le, kind=kind):
                r = (QFileDialog.getExistingDirectory(self, "Pasta", le.text()) if kind == "dir"
                     else QFileDialog.getOpenFileName(self, "Arquivo", le.text())[0])
                if r: le.setText(r)
            br.clicked.connect(pick); h = QHBoxLayout(); h.addWidget(le); h.addWidget(br)
            self.s_paths[key] = le; f.addRow(label + ":", h)
        from . import perf
        from PySide6.QtWidgets import QCheckBox
        f.addRow(QLabel("<b>Desempenho</b>"))
        self.s_dev = QComboBox(); [self.s_dev.addItem(t, k) for k, t in perf.DEVICES]
        i = self.s_dev.findData(self.cfg.get("device", "auto")); self.s_dev.setCurrentIndex(max(0, i))
        self.s_max = QCheckBox("Modo máximo (todas as threads, prioridade alta, pipelines residentes, sem attention slicing)")
        self.s_max.setChecked(self.cfg.get("max_mode", True))
        self.s_max.toggled.connect(lambda on: self.s_thr.setEnabled(not on)); self.s_thr.setEnabled(not self.s_max.isChecked())
        f.addRow("Dispositivo:", self.s_dev); f.addRow(self.s_max)
        bb = QPushButton("Benchmark (SD 1.5, 4 passos, 512×512)"); bb.clicked.connect(self.run_benchmark); f.addRow(bb)
        self.bench_lbl = QLabel(objectName="hint"); self.bench_lbl.setWordWrap(True); f.addRow(self.bench_lbl)
        n = QLabel("Auto: SD 1.5 usa a GPU Intel via OpenVINO se disponível; Wan/FLUX.2 usam sd.cpp Vulkan se houver driver Vulkan. "
                   "Qualquer erro na GPU volta automaticamente para a CPU. Ollama (chat/tradução) roda na CPU com as "
                   "threads acima — o Ollama não acelera GPUs Intel integradas oficialmente.", objectName="hint")
        n.setWordWrap(True); f.addRow(n)
        b = QPushButton("Salvar"); b.clicked.connect(self.save_settings); f.addRow(b)
        f.addRow(QLabel(f"Dados salvos em: {config.APP_DIR}", objectName="hint"))
        return w

    def run_benchmark(self):
        from . import perf
        from .jobs import Job, running
        if getattr(self, "_bench", None) in running(): return
        if QMessageBox.question(self, "Benchmark", "Gera 1 imagem 512×512 (4 passos) em cada dispositivo.\n"
                "Na primeira vez inclui a exportação para OpenVINO (vários minutos). Continuar?") != QMessageBox.Yes:
            return
        cfg = dict(self.cfg); cfg["max_mode"] = self.s_max.isChecked()
        def job(j):
            from pathlib import Path
            from .image_engine import ImageEngine
            import time
            eng = self.image_tab.engine or ImageEngine(cfg); self.image_tab.engine = eng; eng.cfg = cfg
            lcm = Path(cfg.get("lcm_lora_path", "")).is_file(); res = {}
            for be in perf.benchmark_backends():
                j.progress.emit(0, 0, f"Benchmark: {perf.BACKEND_LABEL[be]} (aquecimento)…")
                try:
                    kw = dict(prompt="a photo of a cat", width=512, height=512, steps=4, guidance=1.0, seed=1, lcm=lcm, backend=be)
                    eng.generate("txt2img", **{**kw, "steps": 1})
                    if eng.last_backend != be: raise RuntimeError("falhou e caiu para CPU")
                    t = time.perf_counter(); eng.generate("txt2img", **kw); res[be] = time.perf_counter() - t
                    if eng.last_backend != be: raise RuntimeError("falhou e caiu para CPU")
                except Exception as e:
                    res[be] = str(e)[:120]
                eng.ov_failed = False
            return res
        def done(res):
            ok = {k: v for k, v in res.items() if isinstance(v, float)}
            txt = "\n".join(f"{perf.BACKEND_LABEL[k]}: " + (f"{v:.1f} s" if isinstance(v, float) else f"erro ({v})") for k, v in res.items())
            self.bench_lbl.setText(txt.replace("\n", "<br>")); self.status.showMessage("Benchmark concluído", 5000)
            if ok:
                best = min(ok, key=ok.get)
                if QMessageBox.question(self, "Benchmark", txt + f"\n\nMais rápido: {perf.BACKEND_LABEL[best]}. Usar como padrão?") == QMessageBox.Yes:
                    dev = perf.BACKEND_TO_DEVICE[best]; self.s_dev.setCurrentIndex(self.s_dev.findData(dev)); self.set_cfg(device=dev)
        self._bench = Job(job, self, on_progress=lambda i, n, m: m and self.status.showMessage(m), on_done=done,
                          on_error=lambda m: QMessageBox.warning(self, "Benchmark", m))
        self._bench.start()

    def closeEvent(self, e):
        from . import jobs
        try: self.fila.shutdown(wait=True, timeout=5)
        except Exception as ex: log_line(f"Fila não encerrou limpa: {ex}")
        busy = jobs.running()
        if busy:
            self.status.showMessage("Encerrando tarefas em andamento…"); QApplication.processEvents()
        if not jobs.shutdown_all(8000):
            # alguma thread presa (ex.: passo longo na CPU ou requisição HTTP): encerra o processo sem destruir QThreads vivas
            log_line("Encerramento forçado: thread ainda em execução após 8 s.")
            try: self.db.db.commit()
            except Exception: pass
            os._exit(0)
        try:
            if getattr(self.video_tab, "player", None): self.video_tab.player.stop()
        except Exception: pass
        super().closeEvent(e)

    def set_cfg(self, **kw):
        self.cfg.update(kw); config.save(self.cfg)

    def save_settings(self):
        self.cfg.update(ollama_url=self.s_url.text().strip(), ollama_exe=self.s_exe.text().strip(),
                        threads=self.s_thr.value(), num_ctx=self.s_ctx.value(), temperature=self.s_tmp.value(),
                        device=self.s_dev.currentData(), max_mode=self.s_max.isChecked(),
                        embed_model=self.s_emb.text().strip(), translate_model=self.s_trm.text().strip() or "qwen2.5:3b", system_prompt=self.s_sys.toPlainText(),
                        **{k: le.text().strip() for k, le in self.s_paths.items()})
        config.save(self.cfg)
        try:
            from . import perf; perf.apply(self.cfg)
        except Exception: pass
        self.client = OllamaClient(self.cfg["ollama_url"], self.cfg["ollama_exe"])
        self.emb_label.setText(f"Modelo de embeddings: {self.cfg['embed_model']}")
        self.status.showMessage("Configurações salvas.", 4000); self.refresh_models()

def log_line(msg):
    try:
        import time
        with open(config.APP_DIR / "erro.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass

_CRASH_FILE = None
def install_diagnostics():
    """faulthandler -> crash.log; exceções Python (main e threads) -> erro.log; mensagens Qt -> qt.log."""
    global _CRASH_FILE
    import faulthandler, threading, time
    from PySide6.QtCore import qInstallMessageHandler
    try:
        _CRASH_FILE = open(config.APP_DIR / "crash.log", "a", encoding="utf-8")
        _CRASH_FILE.write(time.strftime("\n=== início %Y-%m-%d %H:%M:%S ===\n")); _CRASH_FILE.flush()
        faulthandler.enable(file=_CRASH_FILE, all_threads=True)
    except Exception:
        pass
    def hook(t, v, tb):
        log_line("Exceção não tratada:\n" + "".join(traceback.format_exception(t, v, tb)))
        if sys.stderr is not None:  # pythonw não tem stderr
            try: sys.__excepthook__(t, v, tb)
            except Exception: pass
    sys.excepthook = hook
    def thook(a):
        log_line(f"Exceção na thread {getattr(a.thread, 'name', '?')}:\n" +
                 "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    threading.excepthook = thook
    names = {0: "DEBUG", 1: "WARNING", 2: "CRITICAL", 3: "FATAL", 4: "INFO"}
    def qt_handler(mode, ctx, msg):
        try:
            with open(config.APP_DIR / "qt.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("[%H:%M:%S] ") + f"{names.get(int(getattr(mode, 'value', mode)), mode)}: {msg}\n")
        except Exception:
            pass
    qInstallMessageHandler(qt_handler)

def main():
    install_diagnostics()
    from . import perf
    try:
        perf.apply(config.load(), import_torch=False)  # variáveis OMP/MKL só aqui, na thread principal, antes do torch
    except Exception:
        pass
    app = QApplication(sys.argv); app.setStyleSheet(STYLE)
    from . import jobs
    app.aboutToQuit.connect(lambda: jobs.shutdown_all(8000))
    w = MainWindow(); w.show(); code = app.exec()
    if jobs.running():
        os._exit(code)
    sys.exit(code)
