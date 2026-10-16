import os, sys, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"; os.environ["IA_OFF_HOME"] = tempfile.mkdtemp()
from PySide6.QtWidgets import QApplication, QTabWidget
from PySide6.QtCore import QTimer, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent
from ia_off import app as A
qa = QApplication(sys.argv); qa.setStyleSheet(A.STYLE)
w = A.MainWindow(); w.show()
w.new_conv(); w.db.add_msg(w.conv_id, "user", "**oi**"); w.db.add_msg(w.conv_id, "assistant", "```py\nx=1\n```"); w.render()
tabs = w.findChild(QTabWidget)
names = [tabs.tabText(i) for i in range(tabs.count())]
assert names == ["Chat", "Documentos", "Imagem", "Vídeo", "Voz", "Configurações"], names
# imagem: carregar entrada e pintar máscara
from PIL import Image
p = os.path.join(os.environ["IA_OFF_HOME"], "in.png"); Image.new("RGB", (300, 200), "green").save(p)
it = w.image_tab; tabs.setCurrentWidget(it); qa.processEvents()
it.set_input(p); it.mode.setCurrentIndex(2); it.paint_chk.setChecked(True); qa.processEvents()
pm = it.painter.pixmap(); c = it.painter.rect().center()
it.painter.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(c), QPointF(c), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
assert it.painter.mask_pil().getbbox() is not None, "máscara não pintada"
for i in range(it.mode.count()): it.mode.setCurrentIndex(i)
it.mode.setCurrentIndex(it.mode.findData("flux2")); assert it.steps.value() == 4  # flux2 defaults
it.mode.setCurrentIndex(it.mode.findData("zimage")); assert it.steps.value() == 8 and not it.neg.isEnabled()  # zimage defaults
assert "sd15_path" in w.s_paths and w.video_tab.player is not None
QTimer.singleShot(1500, qa.quit); qa.exec()
print("SMOKE OK", names)
# tradução: padrões por motor
it.mode.setCurrentIndex(0); assert it.tr_chk.isChecked()
it.mode.setCurrentIndex(4); assert not it.tr_chk.isChecked()
it.mode.setCurrentIndex(3); assert it.tr_chk.isChecked()
assert not w.video_tab.tr_chk.isChecked() and w.tr_out if hasattr(w, "tr_out") else True
it._info("translated", "a cat"); assert it.tr_out.toPlainText() == "a cat"
print("TRANSLATE UI OK")
# seletores de tamanho
ss = it.sizesel; it.mode.setCurrentIndex(0)
ss.aspect.setCurrentText("16:9"); ss.res.setCurrentIndex(ss.res.findData(4320))
assert ss.target() == (7680, 4320) and "7680×4320" in ss.label.text() and "8K" in ss.warn.text()
assert ss.plan()[4] is True and max(ss.plan()[:2]) <= 768
ss.aspect.setCurrentText("Personalizado"); ss.w.setValue(640); ss.h.setValue(448)
assert ss.target() == (640, 448) and ss.w.isEnabled() and not ss.res.isEnabled()
assert w.cfg["image_w"] == 640 and w.cfg["image_aspect"] == "Personalizado"
import json; from ia_off import config as C
assert json.loads(C.CFG_FILE.read_text())["image_w"] == 640
vs = w.video_tab.sizesel; vs.aspect.setCurrentText("16:9"); vs.res.setCurrentIndex(2)
assert vs.res.count() == 3 and vs.plan()[:2] == (832, 480)
print("SIZE UI OK")
assert w.s_dev.currentData() == "auto" and w.s_max.isChecked() and not w.s_thr.isEnabled()
w.s_dev.setCurrentIndex(w.s_dev.findData("vulkan")); w.save_settings(); assert w.cfg["device"] == "vulkan"
from ia_off import perf; print("PERF UI OK", perf.benchmark_backends())
