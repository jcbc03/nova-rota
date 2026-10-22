"""Abas Imagem e Vídeo."""
import os, sys, time, traceback
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QComboBox,
    QPlainTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QProgressBar, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QSlider, QSplitter, QGroupBox, QScrollArea)
from . import config

def open_path(p):
    if sys.platform == "win32": os.startfile(str(p))

from .jobs import Job  # noqa: E402  (QThread seguro, callbacks na GUI)

_TRANSLATOR = None
def get_translator(cfg):
    """Tradutor compartilhado (cache em memória + disco)."""
    global _TRANSLATOR
    from .translate import Translator
    from .ollama_client import OllamaClient
    model = cfg.get("translate_model") or "qwen2.5:3b"
    client = OllamaClient(cfg.get("ollama_url", "http://localhost:11434"), cfg.get("ollama_exe", ""))
    if _TRANSLATOR is None:
        _TRANSLATOR = Translator(client, model, config.APP_DIR / "traducoes.json")
    _TRANSLATOR.client = client; _TRANSLATOR.model = model
    return _TRANSLATOR

def translate_in_job(j, cfg, prompt, negative):
    """Roda na thread do worker. Emite o resultado para a UI e devolve (prompt, negativo, original)."""
    j.progress.emit(0, 0, "Traduzindo prompt para inglês…")
    pe, ne, warn = get_translator(cfg).translate_pair(prompt, negative)
    if warn:
        j.info.emit("warn", warn)
    j.info.emit("translated", pe + (f"\n[negativo] {ne}" if ne else ""))
    return pe, ne

def save_png(im, fp, meta):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    for k, v in meta.items():
        if v not in (None, ""): info.add_itxt(k, str(v))
    im.save(fp, pnginfo=info)

def pil_to_pixmap(img):
    img = img.convert("RGBA"); data = img.tobytes("raw", "RGBA")
    return QPixmap.fromImage(QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy())

def image_meta(p, mode, seed):
    return {"prompt": p["prompt"], "negative_prompt": p.get("negative", ""),
            "prompt_original": p.get("prompt_original", "") if p.get("prompt_original") != p["prompt"] else "",
            "negative_original": p.get("negative_original", "") if p.get("negative_original") != p.get("negative") else "",
            "mode": mode, "seed": seed, "steps": p.get("steps"), "guidance": p.get("guidance"),
            "size": f'{p.get("final_w", p.get("width"))}x{p.get("final_h", p.get("height"))}',
            "generated_size": f'{p.get("width")}x{p.get("height")}',
            "upscale": "lanczos" if p.get("final_w", p.get("width")) != p.get("width") else "", "software": "IA Off 2.3.1"}

class MaskPainter(QLabel):
    """Mostra a imagem de entrada; pinte em branco a área a ser refeita (inpaint)."""
    def __init__(self):
        super().__init__(); self.setAlignment(Qt.AlignCenter); self.setMinimumSize(320, 320)
        self.setText("Sem imagem de entrada"); self.base = None; self.mask = None; self.brush = 32; self.paint_on = False
        self.setStyleSheet("background:#15161a;border:1px dashed #444;")
    def set_image(self, pil):
        self.base = pil.convert("RGB"); self.mask = QImage(self.base.width, self.base.height, QImage.Format_Grayscale8)
        self.mask.fill(0); self._redraw()
    def clear_mask(self):
        if self.mask is not None: self.mask.fill(0); self._redraw()
    def _scale(self):
        pm = self.pixmap()
        return (self.base.width / pm.width()) if pm and not pm.isNull() else 1.0
    def _to_img(self, pos):
        pm = self.pixmap(); s = self._scale()
        ox = (self.width() - pm.width()) / 2; oy = (self.height() - pm.height()) / 2
        return QPoint(int((pos.x() - ox) * s), int((pos.y() - oy) * s))
    def _stroke(self, pos):
        if self.mask is None or not self.paint_on: return
        p = QPainter(self.mask); p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255))
        r = int(self.brush * self._scale()); c = self._to_img(pos); p.drawEllipse(c, r, r); p.end(); self._redraw()
    def mousePressEvent(self, e): self._stroke(e.position())
    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton: self._stroke(e.position())
    def _redraw(self):
        if self.base is None: return
        img = self.base
        if self.paint_on:
            from PIL import Image
            m = self.mask_pil()
            red = Image.new("RGB", img.size, (255, 60, 60))
            img = Image.composite(Image.blend(img, red, 0.55), img, m)
        pm = pil_to_pixmap(img)
        self.setPixmap(pm.scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    def resizeEvent(self, e): self._redraw(); super().resizeEvent(e)
    def mask_pil(self):
        from PIL import Image
        m = self.mask.convertToFormat(QImage.Format_Grayscale8)
        ptr = m.constBits(); bpl = m.bytesPerLine()
        return Image.frombuffer("L", (m.width(), m.height()), bytes(ptr), "raw", "L", bpl, 1).copy()

MODES = [("txt2img", "Texto → Imagem"), ("img2img", "Imagem → Imagem"), ("inpaint", "Inpaint (pintar máscara)"),
         ("pix2pix", "Editar por instrução (InstructPix2Pix)"), ("flux2", "FLUX.2 Klein 4B (sd.cpp, melhor qualidade)"),
         ("zimage", "Z-Image Turbo (sd.cpp)")]

class SizeSelector(QWidget):
    """Proporção + resolução (pelo lado curto) + W/H personalizados + rótulo do tamanho final."""
    def __init__(self, resolutions, engine_fn, cfg_get, cfg_set, prefix, default_res, mult=8, max_custom=8192):
        super().__init__(); from . import sizing as S; self.S = S
        self.engine_fn = engine_fn; self.cfg_set = cfg_set; self.prefix = prefix; self.mult = mult
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)
        r1 = QHBoxLayout(); self.aspect = QComboBox(); [self.aspect.addItem(n) for n, _, _ in S.ASPECTS]; self.aspect.addItem(S.CUSTOM)
        self.res = QComboBox(); [self.res.addItem(n, sh) for n, sh in resolutions]
        r1.addWidget(QLabel("Proporção:")); r1.addWidget(self.aspect); r1.addWidget(QLabel("Resolução:")); r1.addWidget(self.res); v.addLayout(r1)
        r2 = QHBoxLayout(); self.w = QSpinBox(); self.h = QSpinBox()
        for x in (self.w, self.h): x.setRange(64, max_custom); x.setSingleStep(mult)
        r2.addWidget(QLabel("L×A:")); r2.addWidget(self.w); r2.addWidget(QLabel("×")); r2.addWidget(self.h); v.addLayout(r2)
        self.label = QLabel(objectName="hint"); self.label.setWordWrap(True); v.addWidget(self.label)
        self.warn = QLabel(); self.warn.setWordWrap(True); self.warn.setStyleSheet("color:#ffb347;"); v.addWidget(self.warn)
        c = cfg_get()
        self.aspect.setCurrentText(c.get(prefix + "aspect", "1:1"))
        i = self.res.findData(c.get(prefix + "res", default_res)); self.res.setCurrentIndex(i if i >= 0 else self.res.findData(default_res))
        self.w.setValue(c.get(prefix + "w", 512)); self.h.setValue(c.get(prefix + "h", 512))
        self.aspect.currentIndexChanged.connect(self._preset); self.res.currentIndexChanged.connect(self._preset)
        self.w.valueChanged.connect(self.update_label); self.h.valueChanged.connect(self.update_label)
        self._preset()

    def custom(self):
        return self.aspect.currentText() == self.S.CUSTOM

    def _preset(self, *_):
        cu = self.custom(); self.w.setEnabled(cu); self.h.setEnabled(cu); self.res.setEnabled(not cu)
        if not cu:
            w, h = self.S.target_size(self.aspect.currentText(), self.res.currentData(), self.mult)
            for x, val in ((self.w, w), (self.h, h)):
                x.blockSignals(True); x.setValue(val); x.blockSignals(False)
        self.update_label()

    def set_custom(self, w, h):
        self.aspect.setCurrentText(self.S.CUSTOM); self.w.setValue(w // self.mult * self.mult); self.h.setValue(h // self.mult * self.mult)

    def target(self):
        return self.w.value() // self.mult * self.mult, self.h.value() // self.mult * self.mult

    def plan(self):
        tw, th = self.target(); return self.S.plan(self.engine_fn(), tw, th)

    def update_label(self, *_):
        gw, gh, fw, fh, up = self.plan()
        self.label.setText(f"Final: <b>{fw}×{fh}</b>" + (f" — gera em {gw}×{gh} (nativo) e amplia" if up else " (nativo)"))
        self.warn.setText(self.S.warning(fw, fh) if up else "")
        self.cfg_set(**{self.prefix + "aspect": self.aspect.currentText(), self.prefix + "res": self.res.currentData(),
                        self.prefix + "w": self.w.value(), self.prefix + "h": self.h.value()})

def fmt_eta(eta_s):
    if eta_s is None or eta_s < 0: return "calculando…"
    m, sec = divmod(int(eta_s), 60); h, m = divmod(m, 60)
    return f"{h}h{m:02d}min" if h else (f"{m}min{sec:02d}s" if m else f"{sec}s")

class QueueClient:
    """Liga uma aba à JobQueue (fila única do app). A aba só escuta sinais; nada de thread mexendo na tela."""
    def set_queue(self, fila):
        self.fila = fila; self._jobs = set()
        fila.started.connect(self._q_started); fila.progress.connect(self._q_progress)
        fila.finished.connect(self._q_finished); fila.failed.connect(self._q_failed); fila.cancelled.connect(self._q_cancelled)
        if hasattr(fila, "phase"): fila.phase.connect(self._q_phase)

    def _enqueue(self, tipo, params):
        if getattr(self, "fila", None) is None:
            raise RuntimeError("Fila de tarefas indisponível.")
        jid = self.fila.enqueue(tipo, params); self._jobs.add(jid); self.qid = jid
        self.__dict__.setdefault("_tipos", {})[jid] = tipo
        cfo = params.get("cfg_override") or {}
        mod = cfo.get("video_modelo", "") if tipo == "video" else params.get("modo", "")
        un = int(params.get("width") or 0) * int(params.get("height") or 0) * max(1, int(params.get("frames") or 1))
        self.__dict__.setdefault("_dec_info", {})[jid] = {"chave": f"decode_rate_{tipo}_{mod}".rstrip("_"), "un": un}
        self.gen_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.bar.setRange(0, 0); self.bar.setFormat("Na fila…"); self.status.showMessage("Tarefa na fila…")
        return jid

    def _mine(self, jid): return jid in getattr(self, "_jobs", ())

    def _q_started(self, jid):
        if self._mine(jid) and jid not in getattr(self, "_cancelando", ()):
            self.bar.setRange(0, 0); self.bar.setFormat("Carregando modelo…"); self.status.showMessage("Rodando…")
            # até o 1º passo chegar (ou num passo único, como o Lanczos) mostra o tempo decorrido
            self._p_anc = {"jid": jid, "t": time.monotonic(), "passo": None}
            t = self._prog_timer()
            if not t.isActive(): t.start()

    def _q_progress(self, jid, passo, total, pct, eta_s):
        if not self._mine(jid): return
        if jid in getattr(self, "_cancelando", ()): return  # ignora passo emitido depois do Cancelar
        if getattr(self, "_fases", {}).get(jid) == "decodificando":  # Wan manda o decode como passos; mantém o rótulo
            self.bar.setRange(0, 0); self._show_decode(); return
        if total <= 0: self.bar.setRange(0, 0); return
        # âncora do último passo: entre passos o tick de 1 s faz o "falta" descer e a % andar
        self._p_anc = {"jid": jid, "t": time.monotonic(), "passo": passo, "total": total, "pct": pct, "eta": eta_s}
        self._show_progress()
        t = self._prog_timer()
        if not t.isActive(): t.start()

    def _prog_timer(self):
        t = getattr(self, "_ptimer", None)
        if t is None:
            from PySide6.QtCore import QTimer
            t = self._ptimer = QTimer(self); t.setInterval(1000); t.timeout.connect(self._show_progress)
        return t

    def _stop_progress(self):
        self._p_anc = None
        t = getattr(self, "_ptimer", None)
        if t is not None: t.stop()

    def _show_progress(self):
        a = getattr(self, "_p_anc", None)
        if not a or a["jid"] not in getattr(self, "_jobs", ()) or a["jid"] in getattr(self, "_cancelando", ()):
            self._stop_progress(); return
        if a["passo"] is None:
            el = int(time.monotonic() - a["t"])
            rot = "Processando…" if getattr(self, "_tipos", {}).get(a["jid"]) == "ampliar" else "Carregando modelo…"
            txt = f"{rot} {fmt_eta(el)}"
            self.bar.setRange(0, 0); self.bar.setFormat(txt); self.status.showMessage(txt); return
        passo, total, eta = a["passo"], a["total"], a["eta"]
        el = time.monotonic() - a["t"]; frac = 0.0; eta_now = eta
        if eta is not None and eta >= 0:
            eta_now = max(0.0, eta - el)
            resta = total - passo
            if resta > 0 and eta > 0: frac = min(0.95, el / (eta / resta))
        pct = max(float(a["pct"]), min(99.0, (passo + frac) / total * 100.0)) if passo < total else float(a["pct"])
        self.bar.setRange(0, 1000); self.bar.setValue(int(pct * 10))
        falta = "quase lá" if (eta is not None and eta >= 0 and eta_now <= 0 and passo < total) else f"falta {fmt_eta(eta_now)}"
        txt = f"Passo {passo}/{total} · {int(pct)}% · {falta}"
        self.bar.setFormat(txt); self.status.showMessage(txt)

    def _q_phase(self, jid, fase):
        if not self._mine(jid) or jid in getattr(self, "_cancelando", ()): return
        self._stop_progress()
        self.__dict__.setdefault("_fases", {})[jid] = fase
        txt = {"decodificando": "Decodificando…", "salvando": "Salvando…", "convertendo": "Convertendo para MP4…"}.get(fase, fase)
        info = getattr(self, "_dec_info", {}).get(jid)
        if info is not None:
            if fase == "decodificando":
                info["t0"] = time.monotonic(); self._dec_jid = jid
                rate = (self.cfg() or {}).get(info["chave"])
                info["est"] = rate * info["un"] if rate and info["un"] else None
                self._dec_timer().start()
            elif "t0" in info and "dur" not in info:
                info["dur"] = time.monotonic() - info["t0"]; self._save_decode_rate(info)
        if fase != "decodificando": self._dec_timer().stop()
        self._dec_txt = txt
        self.bar.setRange(0, 0); self._show_decode() if fase == "decodificando" else (self.bar.setFormat(txt), self.status.showMessage(txt))
        lg = getattr(self, "log", None)
        if lg is not None: lg.appendPlainText(f"[fase] {txt}")

    def _dec_timer(self):
        t = getattr(self, "_dtimer", None)
        if t is None:
            from PySide6.QtCore import QTimer
            t = self._dtimer = QTimer(self); t.setInterval(1000); t.timeout.connect(self._show_decode)
        return t

    def _show_decode(self):
        info = getattr(self, "_dec_info", {}).get(getattr(self, "_dec_jid", None))
        if not info or "t0" not in info: return
        el = time.monotonic() - info["t0"]; est = info.get("est")
        if est: txt = f"Decodificando… {fmt_eta(el)} de ~{fmt_eta(est)}" + (f" · falta ~{fmt_eta(est - el)}" if est > el else " · quase lá")
        else: txt = f"Decodificando… {fmt_eta(el)} (a primeira vez não tem estimativa; pode levar vários minutos)"
        self.bar.setFormat(txt); self.status.showMessage(txt)

    def _save_decode_rate(self, info):
        if not info.get("un") or info.get("dur", 0) <= 0: return
        rate = info["dur"] / info["un"]; old = (self.cfg() or {}).get(info["chave"])
        rate = rate if not old else 0.5 * old + 0.5 * rate  # média móvel simples
        cs = getattr(self, "cfg_set", None)
        if callable(cs): cs(**{info["chave"]: rate})

    def _q_end(self, jid):
        info = getattr(self, "_dec_info", {}).pop(jid, None)
        if info and "t0" in info and "dur" not in info and jid not in getattr(self, "_cancelando", ()):
            info["dur"] = time.monotonic() - info["t0"]; self._save_decode_rate(info)
        if getattr(self, "_dec_jid", None) == jid: self._dec_timer().stop(); self._dec_jid = None
        if (getattr(self, "_p_anc", None) or {}).get("jid") == jid: self._stop_progress()
        self._jobs.discard(jid); getattr(self, "_cancelando", set()).discard(jid); getattr(self, "_fases", {}).pop(jid, None)
        if getattr(self, "qid", None) == jid: self.qid = None
        if not self._jobs:
            self.gen_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.bar.setRange(0, 100); self.bar.setFormat("%p%")

    def _q_finished(self, jid, path):
        if not self._mine(jid): return
        self._q_end(jid); self.bar.setValue(100); self.on_result(path)

    def _q_failed(self, jid, err):
        if not self._mine(jid): return
        self._q_end(jid); self.bar.setValue(0); self.status.showMessage(err, 8000)
        if err != "Cancelado.":
            blk = "bloque" in err.lower() or "PromptBloqueado" in err
            if blk: err += "\n\nNenhum modelo foi carregado, nada foi gerado nem salvo; o texto continua na caixa.\nPara mudar o nível ou desligar: Configurações > Moderação > \"Alterar filtro…\" (pede a senha)."
            QMessageBox.warning(self, "Prompt bloqueado pela moderação" if blk else "Erro na geração", err)

    def _q_cancelled(self, jid):
        if not self._mine(jid): return
        self._q_end(jid); self.bar.setValue(0); self.status.showMessage("Cancelado.", 6000)

    def cancel_queue(self):
        if getattr(self, "qid", None):
            self.__dict__.setdefault("_cancelando", set()).add(self.qid)
            self._stop_progress(); self.fila.cancel(self.qid); self.status.showMessage("Cancelando… (termina o passo atual)")
            self.bar.setRange(0, 0); self.bar.setFormat("Cancelando…")
            self.cancel_btn.setEnabled(False)  # evita cliques repetidos; _q_end reabilita o Gerar
            return True
        return False

class ImageTab(QueueClient, QWidget):
    def __init__(self, cfg_getter, status, cfg_set=lambda **kw: None):
        super().__init__(); self.cfg = cfg_getter; self.status = status; self.engine = None; self.job = None
        self.init_image = None
        self.cfg_set = cfg_set
        root = QHBoxLayout(self); sp = QSplitter(); root.addWidget(sp)
        left = QWidget(); f = QFormLayout(left)
        self.mode = QComboBox(); [self.mode.addItem(t, k) for k, t in MODES]; self.mode.currentIndexChanged.connect(self._mode_changed)
        self.prompt = QPlainTextEdit(); self.prompt.setPlaceholderText("Descreva a imagem (inglês funciona melhor)…"); self.prompt.setMaximumHeight(90)
        self.neg = QPlainTextEdit(); self.neg.setPlaceholderText("Prompt negativo (opcional)"); self.neg.setMaximumHeight(60)
        from .sizing import RESOLUTIONS, ENGINE_OF_MODE
        self.sizesel = SizeSelector(RESOLUTIONS, lambda: ENGINE_OF_MODE.get(self.mode.currentData(), "sd15"),
                                    cfg_getter, cfg_set, "image_", 512)
        self.sharpen = QCheckBox("Nitidez leve no upscale"); self.sharpen.setChecked(True)
        self.steps = QSpinBox(); self.steps.setRange(1, 100); self.steps.setValue(5)
        self.guid = QDoubleSpinBox(); self.guid.setRange(0, 20); self.guid.setSingleStep(0.1); self.guid.setValue(1.2)
        self.seed = QSpinBox(); self.seed.setRange(-1, 2**31 - 1); self.seed.setValue(-1); self.seed.setSpecialValueText("aleatória")
        self.batch = QSpinBox(); self.batch.setRange(1, 8); self.batch.setValue(1)
        self.strength = QDoubleSpinBox(); self.strength.setRange(0.05, 1.0); self.strength.setSingleStep(0.05); self.strength.setValue(0.6)
        self.img_guid = QDoubleSpinBox(); self.img_guid.setRange(0.5, 5); self.img_guid.setSingleStep(0.1); self.img_guid.setValue(1.5)
        self.lcm = QCheckBox("Usar LCM LoRA (rápido: 4–6 passos, guidance 1–1,5)"); self.lcm.setChecked(True)
        self.lcm.toggled.connect(self._lcm_toggled)
        self.tr_chk = QCheckBox("Traduzir prompt para inglês"); self.tr_chk.setChecked(True)
        self.tr_out = QPlainTextEdit(); self.tr_out.setReadOnly(True); self.tr_out.setMaximumHeight(55)
        self.tr_out.setPlaceholderText("Prompt traduzido (aparece aqui antes de gerar)")
        f.addRow("Modo:", self.mode); f.addRow("Prompt:", self.prompt); f.addRow("Negativo:", self.neg)
        f.addRow(self.tr_chk); f.addRow("Em inglês:", self.tr_out)
        f.addRow("Tamanho:", self.sizesel); f.addRow(self.sharpen); f.addRow("Passos:", self.steps); f.addRow("Guidance (CFG):", self.guid)
        f.addRow("Semente:", self.seed); f.addRow("Quantidade:", self.batch); f.addRow("Força (img2img/inpaint):", self.strength)
        f.addRow("Guidance da imagem (pix2pix):", self.img_guid); f.addRow(self.lcm)
        ib = QHBoxLayout(); b = QPushButton("Abrir imagem de entrada…"); b.clicked.connect(self.pick_input); ib.addWidget(b)
        self.paint_chk = QCheckBox("Pintar máscara"); self.paint_chk.toggled.connect(self._paint_toggle); ib.addWidget(self.paint_chk)
        f.addRow(ib)
        bh = QHBoxLayout(); self.brush = QSlider(Qt.Horizontal); self.brush.setRange(4, 120); self.brush.setValue(32)
        self.brush.valueChanged.connect(lambda v: setattr(self.painter, "brush", v))
        cm = QPushButton("Limpar máscara"); cm.clicked.connect(lambda: self.painter.clear_mask())
        bh.addWidget(QLabel("Pincel:")); bh.addWidget(self.brush); bh.addWidget(cm); f.addRow(bh)
        gh = QHBoxLayout(); self.gen_btn = QPushButton("Gerar"); self.gen_btn.clicked.connect(self.generate)
        self.cancel_btn = QPushButton("Cancelar"); self.cancel_btn.setObjectName("danger"); self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel); gh.addWidget(self.gen_btn); gh.addWidget(self.cancel_btn); f.addRow(gh)
        self.bar = QProgressBar(); self.bar.setValue(0); f.addRow(self.bar)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(80); self.log.setMaximumBlockCount(200)
        self.log.setPlaceholderText("Log (dispositivo usado, fallback…)"); f.addRow(self.log)
        self.info = QLabel("A primeira geração carrega o modelo (pode levar 1–2 min). CPU: ~5–20 s por passo a 512×512.",
                           objectName="hint"); self.info.setWordWrap(True); f.addRow(self.info)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(left)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setMinimumWidth(left.sizeHint().width() + 24)
        mid = QWidget(); mv = QVBoxLayout(mid)
        self.painter = MaskPainter(); mv.addWidget(QLabel("Entrada / máscara:")); mv.addWidget(self.painter, 1)
        self.result = QLabel("Resultado aparecerá aqui"); self.result.setAlignment(Qt.AlignCenter); self.result.setMinimumSize(320, 320)
        mv.addWidget(QLabel("Resultado:")); mv.addWidget(self.result, 1)
        right = QWidget(); rv = QVBoxLayout(right); rv.addWidget(QLabel("Galeria (Imagens\\IA_Off):"))
        self.gallery = QListWidget(); self.gallery.setViewMode(QListWidget.IconMode); self.gallery.setIconSize(QSize(120, 120))
        self.gallery.setResizeMode(QListWidget.Adjust); self.gallery.itemDoubleClicked.connect(lambda it: open_path(it.data(Qt.UserRole)))
        self.gallery.itemClicked.connect(self._show_gallery); rv.addWidget(self.gallery, 1)
        gb = QHBoxLayout(); u = QPushButton("Usar como entrada"); u.clicked.connect(self.use_selected)
        o = QPushButton("Abrir pasta"); o.clicked.connect(lambda: open_path(config.output_dir("pictures")))
        gb.addWidget(u); gb.addWidget(o); rv.addLayout(gb)
        ab = QHBoxLayout(); self.up_scale = QComboBox(); self.up_scale.addItem("2x", 2); self.up_scale.addItem("4x", 4)
        self.up_scale.setCurrentIndex(1); self.up_btn = QPushButton("Ampliar com IA")
        self.up_btn.setToolTip("Amplia a imagem selecionada na galeria (ou escolha um arquivo) com Real-ESRGAN na CPU")
        self.up_btn.clicked.connect(self.upscale_image); ab.addWidget(self.up_btn); ab.addWidget(self.up_scale); rv.addLayout(ab)
        sp.addWidget(scroll); sp.addWidget(mid); sp.addWidget(right); sp.setSizes([460, 460, 280])
        self.load_gallery(); self._mode_changed()

    def _mode_changed(self, *_):
        m = self.mode.currentData()
        self.lcm.setEnabled(m in ("txt2img", "img2img", "inpaint"))
        self.img_guid.setEnabled(m == "pix2pix"); self.strength.setEnabled(m in ("img2img", "inpaint"))
        self.paint_chk.setEnabled(m == "inpaint"); self.neg.setEnabled(m not in ("flux2", "zimage"))
        self.tr_chk.setChecked(m not in ("flux2", "zimage"))  # padrão por motor: SD1.5/inpaint/pix2pix ON, FLUX.2 OFF
        if m == "flux2": self.steps.setValue(4); self.guid.setValue(1.0)
        elif m == "zimage": self.steps.setValue(8); self.guid.setValue(1.0)
        elif m == "pix2pix": self.steps.setValue(15); self.guid.setValue(7.0)
        else: self._lcm_toggled(self.lcm.isChecked())
        if m != "inpaint": self.paint_chk.setChecked(False)
        if hasattr(self, "sizesel"): self.sizesel.update_label()

    def _lcm_toggled(self, on):
        if self.mode.currentData() in ("txt2img", "img2img", "inpaint"):
            self.steps.setValue(5 if on else 25); self.guid.setValue(1.2 if on else 7.5)

    def _paint_toggle(self, on):
        self.painter.paint_on = on; self.painter._redraw()

    def pick_input(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Imagem de entrada", str(config.output_dir("pictures")), "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)")
        if fn: self.set_input(fn)

    def set_input(self, fn):
        from PIL import Image
        self.init_image = Image.open(fn).convert("RGB"); self.init_path = fn; self.painter.set_image(self.init_image)
        w, h = self.init_image.size; self.sizesel.set_custom(w, h)

    def load_gallery(self):
        self.gallery.clear()
        files = sorted(config.output_dir("pictures").glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:200]
        for p in files:
            it = QListWidgetItem(QIcon(QPixmap(str(p)).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)), "")
            it.setData(Qt.UserRole, str(p)); it.setToolTip(p.name); self.gallery.addItem(it)

    def _show_gallery(self, it):
        pm = QPixmap(it.data(Qt.UserRole))
        self.result.setPixmap(pm.scaled(self.result.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def use_selected(self):
        it = self.gallery.currentItem()
        if it: self.set_input(it.data(Qt.UserRole))

    def generate(self):
        m = self.mode.currentData(); prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Imagem", "Escreva um prompt."); return
        if m in ("img2img", "inpaint", "pix2pix") and self.init_image is None:
            QMessageBox.information(self, "Imagem", "Abra uma imagem de entrada primeiro."); return
        mask = self.painter.mask_pil() if m == "inpaint" else None
        if m == "inpaint" and mask.getbbox() is None:
            QMessageBox.information(self, "Inpaint", "Marque 'Pintar máscara' e pinte a área a ser refeita."); return
        cfg = self.cfg(); w, h, fw, fh, up = self.sizesel.plan(); sharpen = self.sharpen.isChecked()
        neg = self.neg.toPlainText().strip(); do_tr = self.tr_chk.isChecked(); self.tr_out.clear()
        params = dict(modo=m, width=w, height=h, steps=self.steps.value(), guidance=self.guid.value(), seed=self.seed.value(),
                      batch=self.batch.value(), strength=self.strength.value(), image_guidance=self.img_guid.value(),
                      lcm=self.lcm.isChecked(), cfg_override=cfg, saida=str(config.output_dir("pictures")))
        if self.init_image is not None and m != "txt2img":
            params["init_image"] = str(getattr(self, "init_path", ""))
        if mask is not None:
            mp = config.APP_DIR / "tmp_mask.png"; mp.parent.mkdir(parents=True, exist_ok=True); mask.save(mp)
            params["mask"] = str(mp)
        self._upscale = (fw, fh, sharpen) if up else None; self._kind = "imagem"
        self._submit(params, prompt, neg, do_tr, cfg)

    def _submit(self, params, prompt, neg, do_tr, cfg):
        """Tradução (rápida, LLM pequeno) roda antes; a geração pesada vai pra fila."""
        if not do_tr:
            params.update(prompt=prompt, negative=neg); self._enqueue("imagem", params); return
        self.gen_btn.setEnabled(False); self.bar.setRange(0, 0); self.bar.setFormat("Traduzindo prompt…")
        def job(j): return translate_in_job(j, cfg, prompt, neg)
        def ok(r):
            params.update(prompt=r[0], negative=r[1]); self._enqueue("imagem", params)
        def err(msg):
            self.gen_btn.setEnabled(True); self.bar.setRange(0, 100); self.bar.setFormat("%p%"); QMessageBox.warning(self, "Tradução", msg)
        self.tjob = Job(job, self, on_info=self._info, on_done=ok, on_error=err); self.tjob.start()

    def upscale_image(self):
        it = self.gallery.currentItem(); src = it.data(Qt.UserRole) if it else None
        if not src:
            src, _ = QFileDialog.getOpenFileName(self, "Imagem para ampliar", str(config.output_dir("pictures")),
                                                 "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not src: return
        self._kind = "ampliar"; self.up_btn.setEnabled(False)
        self._enqueue("ampliar", {"entrada": src, "escala": self.up_scale.currentData(), "cfg_override": self.cfg(),
                                  "saida": str(config.output_dir("pictures"))})

    def _q_end(self, jid):
        super()._q_end(jid)
        if not self._jobs: self.up_btn.setEnabled(True)

    def on_result(self, path):
        if getattr(self, "_kind", None) == "ampliar":
            self._kind = None; self._done([path] if path else [])
            if path and "_lanczos" in Path(path).name:
                QMessageBox.information(self, "Ampliar", "O modelo de IA do ampliador não foi encontrado, então a imagem foi "
                                        "ampliada pelo método simples (Lanczos). Instale o modelo com tools\\baixar_ampliador.py.")
            return
        self._kind = None
        up = getattr(self, "_upscale", None)
        if up and path:
            fw, fh, sharpen = up
            self.status.showMessage(f"Ampliando para {fw}×{fh} (Lanczos)…")
            def job(j):
                from PIL import Image
                from .sizing import upscale
                import glob
                stem = Path(path).name.rsplit("_", 1)[0]
                outs = [Path(path)] + [Path(x) for x in glob.glob(str(Path(path).parent / (stem + "_*.png"))) if Path(x) != Path(path)]
                for fp in outs:
                    with Image.open(fp) as im0: im0.load(); info = dict(im0.info); im = im0.copy()
                    from PIL.PngImagePlugin import PngInfo
                    pi = PngInfo(); [pi.add_itxt(k, str(v)) for k, v in info.items() if isinstance(v, str)]
                    upscale(im, fw, fh, sharpen).save(fp, pnginfo=pi)
                return [path]
            self.ujob = Job(job, self, on_done=self._done, on_error=self._fail); self.ujob.start()
        else:
            self._done([path] if path else [])

    def _flux2(self, j, cfg, p, out, finish=lambda im: im):
        from . import sdcpp, perf
        variant = sdcpp.flux2_variant(cfg)
        for k in ("flux2_model", "flux2_vae", "flux2_llm"):
            if not Path(cfg[k]).is_file(): raise FileNotFoundError(f"Arquivo não encontrado: {cfg[k]}")
        paths = []
        for i in range(p["batch"]):
            seed = p["seed"] + i if p["seed"] >= 0 else int(time.time() * 1000) % (2**31)
            tag = "_en" if p["prompt"] != p.get("prompt_original", p["prompt"]) else ""
            fp = out / f"{time.strftime('%Y%m%d_%H%M%S')}_flux2_{seed}{tag}.png"
            mk = lambda b, fp=fp, seed=seed: sdcpp.build_flux2_args(b, cfg, p["prompt"], fp, p["width"], p["height"], p["steps"], seed, p["guidance"])
            def line(s, i=i):
                pr = sdcpp.parse_progress(s)
                if pr: j.progress.emit(i * pr[1] + pr[0], p["batch"] * pr[1], f"Imagem {i+1}: passo {pr[0]}/{pr[1]}")
            used = sdcpp.run_with_fallback(cfg.get("sdcpp_dir"), variant, mk, line, lambda: j.cancel,
                                           log=lambda m: j.info.emit("log", m),
                                           progress=lambda d, t: j.progress.emit(d, t or 1, "Baixando sd.cpp…"))
            variant = used  # se o Vulkan falhou, as próximas imagens já vão direto para a CPU
            try:
                from PIL import Image
                with Image.open(fp) as im0: im0.load(); im = im0.copy()
                save_png(finish(im), fp, image_meta(p, "flux2", seed))
            except Exception:
                pass
            paths.append(fp)
        return paths

    def _start(self, fn):
        self.gen_btn.setEnabled(False); self.cancel_btn.setEnabled(True); self.bar.setRange(0, 0)
        self.job = Job(fn, self, on_progress=self._prog, on_info=self._info, on_done=self._done, on_error=self._fail)
        self.job.start()

    def _info(self, kind, text):
        if kind == "translated": self.tr_out.setPlainText(text)
        elif kind == "log": self.log.appendPlainText(text); self.status.showMessage(text, 6000)
        elif kind == "warn": self.status.showMessage(text, 10000); QMessageBox.warning(self, "Tradução", text)

    def _prog(self, i, n, msg):
        if n <= 0: self.bar.setRange(0, 0)
        else: self.bar.setRange(0, n); self.bar.setValue(i)
        if msg: self.status.showMessage(msg)

    def _end(self):
        self.gen_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.bar.setRange(0, 100)

    def _done(self, paths):
        self._end(); self.bar.setValue(100); self.load_gallery()
        if paths:
            pm = QPixmap(str(paths[-1])); self.result.setPixmap(pm.scaled(self.result.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.status.showMessage(f"{len(paths)} imagem(ns) salva(s) em {config.output_dir('pictures')}", 8000)

    def _fail(self, msg):
        self._end(); self.bar.setValue(0); self.status.showMessage(msg, 8000)
        if msg != "Cancelado.": QMessageBox.warning(self, "Erro na geração", msg)

    def cancel(self):
        if self.cancel_queue(): return
        if self.job:
            self.job.cancel = True; self.cancel_btn.setEnabled(False)
            self.status.showMessage("Cancelando… (termina o passo atual)")

class VideoTab(QueueClient, QWidget):
    def __init__(self, cfg_getter, status, cfg_set=lambda **kw: None):
        super().__init__(); self.cfg = cfg_getter; self.status = status; self.job = None
        root = QHBoxLayout(self); sp = QSplitter(); root.addWidget(sp)
        left = QWidget(); f = QFormLayout(left)
        warn = QLabel("⚠ Geração de vídeo na CPU é MUITO lenta: 17 quadros em 480×272 podem levar de 20 a 60+ minutos. "
                      "Comece pequeno.", objectName="hint"); warn.setWordWrap(True); warn.setStyleSheet("color:#ffb347;")
        f.addRow(warn)
        self.cfg_set = cfg_set
        self.vmodel = QComboBox(); self.vmodel.addItem("Wan 2.1 1.3B", "wan21"); self.vmodel.addItem("Wan 2.2 5B (TI2V)", "wan22")
        self.vmodel.currentIndexChanged.connect(lambda _: self.cfg_set(video_modelo=self.vmodel.currentData()))
        f.addRow("Modelo:", self.vmodel); self.refresh_vmodels()
        self.prompt = QPlainTextEdit(); self.prompt.setPlaceholderText("Descreva o vídeo (inglês funciona melhor)…"); self.prompt.setMaximumHeight(90)
        self.neg = QPlainTextEdit(); self.neg.setPlaceholderText("Negativo (vazio = padrão do Wan)"); self.neg.setMaximumHeight(50)
        from .sizing import VIDEO_RESOLUTIONS
        self.sizesel = SizeSelector(VIDEO_RESOLUTIONS, lambda: "wan", cfg_getter, cfg_set, "video_", 256, mult=16, max_custom=832)
        if "video_aspect" not in cfg_getter(): self.sizesel.aspect.setCurrentText("16:9")
        self.frames = QSpinBox(); self.frames.setRange(5, 81); self.frames.setSingleStep(4); self.frames.setValue(17)
        self.steps = QSpinBox(); self.steps.setRange(4, 50); self.steps.setValue(20)
        self.cfgs = QDoubleSpinBox(); self.cfgs.setRange(1, 15); self.cfgs.setValue(6.0)
        self.fps = QSpinBox(); self.fps.setRange(4, 30); self.fps.setValue(16)
        self.fps.setValue(24 if self.vmodel.currentData() == "wan22" else 16)
        self.vmodel.currentIndexChanged.connect(lambda _: self.fps.setValue(24 if self.vmodel.currentData() == "wan22" else 16))
        self.seed = QSpinBox(); self.seed.setRange(-1, 2**31 - 1); self.seed.setValue(-1); self.seed.setSpecialValueText("aleatória")
        self.tr_chk = QCheckBox("Traduzir prompt para inglês"); self.tr_chk.setChecked(False)  # Wan entende PT razoavelmente
        self.tr_out = QPlainTextEdit(); self.tr_out.setReadOnly(True); self.tr_out.setMaximumHeight(55)
        self.tr_out.setPlaceholderText("Prompt traduzido (aparece aqui antes de gerar)")
        f.addRow("Prompt:", self.prompt); f.addRow("Negativo:", self.neg); f.addRow(self.tr_chk); f.addRow("Em inglês:", self.tr_out)
        f.addRow("Tamanho:", self.sizesel)
        f.addRow("Quadros (4k+1):", self.frames); f.addRow("Passos:", self.steps); f.addRow("CFG:", self.cfgs)
        f.addRow("FPS:", self.fps); f.addRow("Semente:", self.seed)
        gh = QHBoxLayout(); self.gen_btn = QPushButton("Gerar vídeo"); self.gen_btn.clicked.connect(self.generate)
        self.cancel_btn = QPushButton("Cancelar"); self.cancel_btn.setObjectName("danger"); self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel)
        gh.addWidget(self.gen_btn); gh.addWidget(self.cancel_btn); f.addRow(gh)
        self.bar = QProgressBar(); f.addRow(self.bar)
        self.dl_btn = QPushButton("Baixar/verificar stable-diffusion.cpp"); self.dl_btn.clicked.connect(self.check_bin); f.addRow(self.dl_btn)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(400); f.addRow(QLabel("Log:")); f.addRow(self.log)
        right = QWidget(); rv = QVBoxLayout(right)
        self.player = None; self.video_w = None
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtMultimediaWidgets import QVideoWidget
            self.video_w = QVideoWidget(); self.player = QMediaPlayer(self); self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.video_w)
            self.player.setLoops(QMediaPlayer.Infinite); rv.addWidget(self.video_w, 2)
        except Exception as e:
            rv.addWidget(QLabel(f"Prévia indisponível ({e})"))
        pb = QHBoxLayout(); pl = QPushButton("▶ Tocar"); pl.clicked.connect(lambda: self.player and self.player.play())
        ps = QPushButton("⏸ Pausar"); ps.clicked.connect(lambda: self.player and self.player.pause())
        od = QPushButton("Abrir pasta"); od.clicked.connect(lambda: open_path(config.output_dir("videos")))
        for b in (pl, ps, od): pb.addWidget(b)
        rv.addLayout(pb); rv.addWidget(QLabel("Vídeos (Vídeos\\IA_Off):"))
        self.list = QListWidget(); self.list.itemClicked.connect(lambda it: self.preview(it.data(Qt.UserRole))); rv.addWidget(self.list, 1)
        self.log.setMinimumHeight(80)
        # painel com rolagem: em janela baixa o formulário rola em vez de espremer o seletor de tamanho
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(left)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setMinimumWidth(left.sizeHint().width() + 24)
        self.left_scroll = scroll
        sp.addWidget(scroll); sp.addWidget(right); sp.setSizes([420, 700]); self.load_list()

    @staticmethod
    def wan22_ok(cfg):
        return all(cfg.get(k) and Path(cfg[k]).is_file() for k in ("wan22_model", "wan22_t5", "wan22_vae"))

    def refresh_vmodels(self):
        """Wan 2.2 só fica selecionável com os três arquivos (wan22_*) presentes."""
        cfg = self.cfg(); ok = self.wan22_ok(cfg)
        item = self.vmodel.model().item(1); item.setEnabled(ok)
        item.setToolTip("" if ok else "Configure wan22_model, wan22_t5 e wan22_vae nas Configurações.")
        want = cfg.get("video_modelo", "wan21") if ok else "wan21"
        self.vmodel.blockSignals(True); self.vmodel.setCurrentIndex(max(0, self.vmodel.findData(want))); self.vmodel.blockSignals(False)

    def load_list(self):
        self.list.clear()
        for p in sorted(config.output_dir("videos").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
            it = QListWidgetItem(p.name); it.setData(Qt.UserRole, str(p)); self.list.addItem(it)

    def preview(self, path):
        if self.player:
            self.player.setSource(QUrl.fromLocalFile(str(path))); self.player.play()

    def _ensure_bin(self, j, cfg, variant="cpu"):
        from . import sdcpp
        b = sdcpp.find_binary(cfg.get("sdcpp_dir"), variant)
        if b: return b
        j.progress.emit(0, 0, f"Baixando stable-diffusion.cpp ({variant}, uma vez)…")
        return sdcpp.download_binary(cfg.get("sdcpp_dir"), lambda d, t: j.progress.emit(d, t or 1, ""), lambda: j.cancel, variant)

    def check_bin(self):
        from . import perf
        cfg = self.cfg(); vs = ["cpu"] + (["vulkan"] if perf.sdcpp_variant(cfg) == "vulkan" else [])
        self._start(lambda j: "\n".join(str(self._ensure_bin(j, cfg, v)) for v in vs),
                    done=lambda b: self.log.appendPlainText(f"sd-cli:\n{b}"))

    def generate(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Vídeo", "Escreva um prompt."); return
        cfg = dict(self.cfg()); vm = self.vmodel.currentData() or "wan21"
        if vm == "wan22" and not self.wan22_ok(cfg): vm = "wan21"
        cfg["video_modelo"] = vm; pre = "wan22_" if vm == "wan22" else "wan_"
        missing = [cfg.get(pre + k) or f"({pre + k} vazio)" for k in ("model", "t5", "vae") if not Path(cfg.get(pre + k) or "").is_file()]
        if missing:
            QMessageBox.warning(self, "Vídeo", "Arquivos não encontrados:\n" + "\n".join(missing)); return
        w, h = self.sizesel.plan()[:2]
        neg = self.neg.toPlainText().strip(); do_tr = self.tr_chk.isChecked(); self.tr_out.clear()
        params = dict(width=w, height=h, frames=self.frames.value(), steps=self.steps.value(), cfg_scale=self.cfgs.value(),
                      fps=self.fps.value(), seed=self.seed.value(), cfg_override=cfg, saida=str(config.output_dir("videos")))
        def go(pr, ng):
            params.update(prompt=pr, negative=ng)
            self.log.appendPlainText(f"Prompt usado: {pr}" + (f" | Negativo: {ng}" if ng else ""))
            self._enqueue("video", params)
        if not do_tr:
            go(prompt, neg); return
        self.gen_btn.setEnabled(False); self.bar.setRange(0, 0); self.bar.setFormat("Traduzindo prompt…")
        def err(msg):
            self._end(); self.bar.setFormat("%p%"); QMessageBox.warning(self, "Tradução", msg)
        self.tjob = Job(lambda j: translate_in_job(j, cfg, prompt, neg), self, on_info=self._info,
                        on_done=lambda r: go(r[0], r[1]), on_error=err)
        self.tjob.start()

    def on_result(self, path):
        self._done(path)

    def _start(self, fn, done):
        self.gen_btn.setEnabled(False); self.dl_btn.setEnabled(False); self.cancel_btn.setEnabled(True); self.bar.setRange(0, 0)
        def err(m):
            self._end(); self.log.appendPlainText(m)
            if m != "Cancelado.": QMessageBox.warning(self, "Erro", m)
        self.job = Job(fn, self, on_progress=self._prog, on_info=self._info,
                       on_done=lambda r: (self._end(), done(r)), on_error=err)
        self.job.start()

    def _info(self, kind, text):
        if kind == "translated": self.tr_out.setPlainText(text); self.log.appendPlainText("Tradução: " + text)
        elif kind == "warn": self.log.appendPlainText("AVISO: " + text); QMessageBox.warning(self, "Tradução", text)

    def _prog(self, i, n, msg):
        if i == -1:
            self.log.appendPlainText(msg); return
        if n <= 0: self.bar.setRange(0, 0)
        else: self.bar.setRange(0, n); self.bar.setValue(i)
        if msg: self.status.showMessage(msg)

    def _end(self):
        self.gen_btn.setEnabled(True); self.dl_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.bar.setRange(0, 100)

    def _done(self, path):
        self.bar.setValue(100); self.load_list(); self.preview(path); self.status.showMessage(f"Vídeo salvo: {path}", 10000)


    def cancel(self):
        if self.cancel_queue(): return
        if self.job:
            self.job.cancel = True; self.cancel_btn.setEnabled(False)
            self.status.showMessage("Cancelando… (termina o passo atual)")

class VoiceTab(QueueClient, QWidget):
    """Voz offline: transcrever (Whisper) e falar (Piper), ambos pela fila."""
    def __init__(self, cfg_getter, status):
        super().__init__(); self.cfg = cfg_getter; self.status = status; self.audio_path = None; self._tipo = None
        v = QVBoxLayout(self)
        # gen_btn é o contêiner dos dois botões: desabilitar ele trava ambos enquanto há tarefa
        self.gen_btn = QWidget(); bl = QHBoxLayout(self.gen_btn); bl.setContentsMargins(0, 0, 0, 0)
        g1 = QGroupBox("Transcrever áudio (Whisper, sem internet)"); f1 = QVBoxLayout(g1)
        h = QHBoxLayout(); pick = QPushButton("Escolher áudio…"); pick.clicked.connect(self.pick_audio)
        self.audio_lbl = QLabel("Nenhum arquivo escolhido", objectName="hint"); h.addWidget(pick); h.addWidget(self.audio_lbl, 1)
        f1.addLayout(h)
        self.tr_text = QPlainTextEdit(); self.tr_text.setReadOnly(True); self.tr_text.setPlaceholderText("O texto transcrito aparece aqui")
        f1.addWidget(self.tr_text, 1)
        cp = QPushButton("Copiar texto"); cp.clicked.connect(lambda: self._copy(self.tr_text.toPlainText())); f1.addWidget(cp)
        g2 = QGroupBox("Falar texto (Piper, voz pt-BR)"); f2 = QVBoxLayout(g2)
        self.say = QPlainTextEdit(); self.say.setPlaceholderText("Digite o texto para ser falado…"); f2.addWidget(self.say, 1)
        self.wav_lbl = QLabel("", objectName="hint"); f2.addWidget(self.wav_lbl)
        ph = QHBoxLayout(); self.play_btn = QPushButton("▶ Ouvir de novo"); self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.play); ph.addWidget(self.play_btn); ph.addStretch(); f2.addLayout(ph)
        self.t_btn = QPushButton("Transcrever"); self.t_btn.clicked.connect(self.transcribe)
        self.s_btn = QPushButton("Falar"); self.s_btn.clicked.connect(self.speak)
        bl.addWidget(self.t_btn); bl.addWidget(self.s_btn); bl.addStretch()
        self.cancel_btn = QPushButton("Cancelar"); self.cancel_btn.setObjectName("danger"); self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_queue)
        sp = QSplitter(); sp.addWidget(g1); sp.addWidget(g2); v.addWidget(sp, 1)
        # Cancelar fica FORA do contêiner gen_btn; senão desabilitar o contêiner travava o Cancelar junto (E13)
        bh = QHBoxLayout(); bh.addWidget(self.gen_btn, 1); bh.addWidget(self.cancel_btn); v.addLayout(bh)
        self.bar = QProgressBar(); self.bar.setValue(0); v.addWidget(self.bar)
        self.player = None; self.wav = None
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            self.player = QMediaPlayer(self); self.audio_out = QAudioOutput(self); self.player.setAudioOutput(self.audio_out)
        except Exception:
            pass

    def _copy(self, t):
        from PySide6.QtWidgets import QApplication
        if t: QApplication.clipboard().setText(t); self.status.showMessage("Copiado!", 3000)

    def pick_audio(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Áudio", str(Path.home()), "Áudio (*.wav *.mp3 *.m4a *.ogg *.flac *.opus *.webm)")
        if fn: self.audio_path = fn; self.audio_lbl.setText(Path(fn).name)

    def transcribe(self):
        if not self.audio_path:
            QMessageBox.information(self, "Voz", "Escolha um arquivo de áudio primeiro."); return
        self._tipo = "transcrever"; self.tr_text.clear()
        self._enqueue("transcrever", {"audio": self.audio_path, "cfg_override": self.cfg()})

    def speak(self):
        t = self.say.toPlainText().strip()
        if not t:
            QMessageBox.information(self, "Voz", "Digite um texto para falar."); return
        self._tipo = "falar"
        self._enqueue("falar", {"texto": t, "cfg_override": self.cfg()})

    def _q_progress(self, jid, passo, total, pct, eta_s):
        if not self._mine(jid) or jid in getattr(self, "_cancelando", ()): return
        if total <= 0: self.bar.setRange(0, 0); return
        self.bar.setRange(0, total); self.bar.setValue(passo)  # mesma escala das outras abas
        unidade = "s de áudio" if getattr(self, "_tipos", {}).get(jid, self._tipo) == "transcrever" else "frase(s)"
        txt = f"{passo} de {total} {unidade} · {int(pct)}% · falta {fmt_eta(eta_s)}"
        self.bar.setFormat(txt); self.status.showMessage(txt)

    def on_result(self, path):
        if self._tipo == "transcrever":
            try: self.tr_text.setPlainText(Path(path).read_text(encoding="utf-8"))
            except Exception as e: self.tr_text.setPlainText(f"Não consegui ler {path}: {e}")
            self.status.showMessage(f"Transcrição salva em {path}", 8000)
        else:
            self.wav = path; self.wav_lbl.setText(f"Salvo em {path}"); self.play_btn.setEnabled(bool(self.player)); self.play()

    def play(self):
        if self.player and self.wav:
            self.player.setSource(QUrl.fromLocalFile(str(self.wav))); self.player.play()
