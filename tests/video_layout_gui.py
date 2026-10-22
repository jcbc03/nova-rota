from PySide6.QtWidgets import QApplication, QStatusBar
app = QApplication([])
from ia_off import media_tabs as M
cfg = {}
t = M.VideoTab(lambda: cfg, QStatusBar(), lambda **k: cfg.update(k))
t.resize(1100, 420); t.show(); app.processEvents()
s = t.sizesel
assert s.height() >= s.minimumSizeHint().height(), (s.height(), s.minimumSizeHint().height())
assert t.left_scroll.verticalScrollBar().maximum() > 0
print("LAYOUT OK")
