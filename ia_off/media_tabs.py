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
         ("pix2pix", "Editar por instrução (InstructPix2Pix)"), ("flux2", "FLUX.2 Klein 4B (sd.cpp, melhor qualidade)")]

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

class ImageTab(QWidget):
    def __init__(self, cfg_getter, status, cfg_set=lambda **kw: None):
        super().__init__(); self.cfg = cfg_getter; self.status = status; self.engine = None; self.job = None
        self.init_image = None
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
        sp.addWidget(scroll); sp.addWidget(mid); sp.addWidget(right); sp.setSizes([380, 520, 300])
        self.load_gallery(); self._mode_changed()

    def _mode_changed(self, *_):
        m = self.mode.currentData()
        self.lcm.setEnabled(m in ("txt2img", "img2img", "inpaint"))
        self.img_guid.setEnabled(m == "pix2pix"); self.strength.setEnabled(m in ("img2img", "inpaint"))
        self.paint_chk.setEnabled(m == "inpaint"); self.neg.setEnabled(m != "flux2")
        self.tr_chk.setChecked(m != "flux2")  # padrão por motor: SD1.5/inpaint/pix2pix ON, FLUX.2 OFF
        if m == "flux2": self.steps.setValue(4); self.guid.setValue(1.0)
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
        p = dict(prompt=prompt, negative=self.neg.toPlainText().strip(), width=w, height=h, steps=self.steps.value(),
                 guidance=self.guid.value(), seed=self.seed.value(), batch=self.batch.value())
        out = config.output_dir("pictures"); init = self.init_image; do_tr = self.tr_chk.isChecked()
        self.tr_out.clear()
        p["final_w"], p["final_h"] = fw, fh
        strength, img_guid, use_lcm = self.strength.value(), self.img_guid.value(), self.lcm.isChecked()  # lidos na GUI
        def finish(im):
            if up:
                j_last[0].progress.emit(0, 0, f"Ampliando para {fw}×{fh} (Lanczos)…")
                from .sizing import upscale
                return upscale(im, fw, fh, sharpen)
            return im
        j_last = [None]
        def job(j):
            j_last[0] = j
            prog = lambda i, n, msg="": j.progress.emit(i, n, msg)
            p["prompt_original"], p["negative_original"] = p["prompt"], p["negative"]
            if do_tr:
                p["prompt"], p["negative"] = translate_in_job(j, cfg, p["prompt"], p["negative"])
            if m == "flux2":
                return self._flux2(j, cfg, p, out, finish)
            if self.engine is None:
                from .image_engine import ImageEngine
                self.engine = ImageEngine(cfg)
            self.engine.cfg = cfg
            j.progress.emit(0, 0, "Carregando modelo…")
            gp = {k: v for k, v in p.items() if not k.endswith("_original") and not k.startswith("final_")}
            imgs = self.engine.generate(m, log=lambda t: j.info.emit("log", t), init_image=init, mask=mask, strength=strength,
                                        image_guidance=img_guid, lcm=use_lcm,
                                        progress=lambda i, n: prog(i, n, f"Passo {i}/{n}"), cancelled=lambda: j.cancel, **gp)
            paths = []
            tag = "_en" if p["prompt"] != p["prompt_original"] else ""
            for seed, im in imgs:
                fp = out / f"{time.strftime('%Y%m%d_%H%M%S')}_{m}_{seed}{tag}.png"
                save_png(finish(im), fp, image_meta(p, m, seed)); paths.append(fp)
            return paths
        self._start(job)

    def _flux2(self, j, cfg, p, out, finish=lambda im: im):
        from . import sdcpp, perf
        variant = perf.sdcpp_variant(cfg)
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
        if self.job: self.job.cancel = True; self.status.showMessage("Cancelando… (termina o passo atual)")

class VideoTab(QWidget):
    def __init__(self, cfg_getter, status, cfg_set=lambda **kw: None):
        super().__init__(); self.cfg = cfg_getter; self.status = status; self.job = None
        root = QHBoxLayout(self); sp = QSplitter(); root.addWidget(sp)
        left = QWidget(); f = QFormLayout(left)
        warn = QLabel("⚠ Geração de vídeo na CPU é MUITO lenta: 17 quadros em 480×272 podem levar de 20 a 60+ minutos. "
                      "Comece pequeno.", objectName="hint"); warn.setWordWrap(True); warn.setStyleSheet("color:#ffb347;")
        f.addRow(warn)
        self.prompt = QPlainTextEdit(); self.prompt.setPlaceholderText("Descreva o vídeo (inglês funciona melhor)…"); self.prompt.setMaximumHeight(90)
        self.neg = QPlainTextEdit(); self.neg.setPlaceholderText("Negativo (vazio = padrão do Wan)"); self.neg.setMaximumHeight(50)
        from .sizing import VIDEO_RESOLUTIONS
        self.sizesel = SizeSelector(VIDEO_RESOLUTIONS, lambda: "wan", cfg_getter, cfg_set, "video_", 256, mult=16, max_custom=832)
        if "video_aspect" not in cfg_getter(): self.sizesel.aspect.setCurrentText("16:9")
        self.frames = QSpinBox(); self.frames.setRange(5, 81); self.frames.setSingleStep(4); self.frames.setValue(17)
        self.steps = QSpinBox(); self.steps.setRange(4, 50); self.steps.setValue(20)
        self.cfgs = QDoubleSpinBox(); self.cfgs.setRange(1, 15); self.cfgs.setValue(6.0)
        self.fps = QSpinBox(); self.fps.setRange(4, 30); self.fps.setValue(16)
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
        self.cancel_btn.clicked.connect(lambda: self.job and setattr(self.job, "cancel", True))
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
        sp.addWidget(left); sp.addWidget(right); sp.setSizes([420, 700]); self.load_list()

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
        from . import sdcpp
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Vídeo", "Escreva um prompt."); return
        cfg = self.cfg()
        missing = [cfg[k] for k in ("wan_model", "wan_t5", "wan_vae") if not Path(cfg[k]).is_file()]
        if missing:
            QMessageBox.warning(self, "Vídeo", "Arquivos não encontrados:\n" + "\n".join(missing)); return
        w, h = self.sizesel.plan()[:2]; frames = sdcpp.wan_frames(self.frames.value())
        seed = self.seed.value() if self.seed.value() >= 0 else int(time.time()) % (2**31)
        out = config.output_dir("videos"); stem = f"{time.strftime('%Y%m%d_%H%M%S')}_wan_{seed}"
        neg, steps, cfgs, fps = self.neg.toPlainText().strip(), self.steps.value(), self.cfgs.value(), self.fps.value()
        do_tr = self.tr_chk.isChecked(); self.tr_out.clear()
        def job(j):
            pr_en, neg_en = translate_in_job(j, cfg, prompt, neg) if do_tr else (prompt, neg)
            j.progress.emit(-1, -1, f"Prompt usado: {pr_en}" + (f" | Negativo: {neg_en}" if neg_en else ""))
            from . import perf
            avi = out / f"{stem}.avi"
            mk = lambda b: sdcpp.build_wan_args(b, cfg, pr_en, avi, neg_en, w, h, frames, steps, cfgs, seed, fps)
            (out / f"{stem}.txt").write_text(f"prompt: {pr_en}\nnegative: {neg_en}\nprompt_original: {prompt}\n"
                f"negative_original: {neg}\nseed: {seed}\nsize: {w}x{h}\nframes: {frames}\nsteps: {steps}\ncfg: {cfgs}\nfps: {fps}\n",
                encoding="utf-8")
            j.progress.emit(0, 0, "Carregando modelos Wan…")
            def line(s):
                pr = sdcpp.parse_progress(s)
                if pr: j.progress.emit(pr[0], pr[1], f"Vídeo: passo {pr[0]}/{pr[1]}")
                else: j.progress.emit(-1, -1, s)
            sdcpp.run_with_fallback(cfg.get("sdcpp_dir"), perf.sdcpp_variant(cfg), mk, line, lambda: j.cancel,
                                    log=lambda m: j.progress.emit(-1, -1, m),
                                    progress=lambda d, t: j.progress.emit(d, t or 1, "Baixando sd.cpp…"))
            mp4 = out / f"{stem}.mp4"
            try:
                sdcpp.to_mp4(avi, mp4, fps); avi.unlink(missing_ok=True); return str(mp4)
            except Exception as e:
                j.progress.emit(-1, -1, f"Aviso: {e}"); return str(avi)
        self._start(job, done=self._done)

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
