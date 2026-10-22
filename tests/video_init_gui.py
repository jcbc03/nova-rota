import tempfile, os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QStatusBar
app = QApplication([])
from ia_off import media_tabs as M
d = Path(tempfile.mkdtemp())
for k in ("m", "t", "v", "m1", "t1", "v1"): (d / k).write_bytes(b"x")
img = d / "ref.png"; img.write_bytes(b"x")
cfg = {"wan22_model": str(d/"m"), "wan22_t5": str(d/"t"), "wan22_vae": str(d/"v"),
       "wan_model": str(d/"m1"), "wan_t5": str(d/"t1"), "wan_vae": str(d/"v1"), "video_modelo": "wan21"}
t = M.VideoTab(lambda: cfg, QStatusBar(), lambda **k: cfg.update(k)); t.show(); app.processEvents()
pegou = []
t._enqueue = lambda tipo, p: pegou.append(p)
t.vmodel.setCurrentIndex(t.vmodel.findData("wan21")); app.processEvents()
assert not t.init_box.isVisible(), "campo não deve aparecer no Wan 2.1"
t.vmodel.setCurrentIndex(t.vmodel.findData("wan22")); app.processEvents()
assert t.init_box.isVisible(), "campo deve aparecer no Wan 2.2"
t.prompt.setPlainText("um gato"); t.tr_chk.setChecked(False)
t.generate(); assert "init_image" not in pegou[-1], "sem imagem é só texto"
t.set_init(str(img)); t.generate(); assert pegou[-1]["init_image"] == str(img)
t.vmodel.setCurrentIndex(t.vmodel.findData("wan21")); app.processEvents()
t.generate(); assert "init_image" not in pegou[-1], "Wan 2.1 não manda imagem"
print("INIT OK")
