import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.keyvault import KeyVault
from app.core.subtitle import SubtitleEntry
from app.ui.api_manager import ApiManagerDialog
from app.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def _rect_in(widget, root):
    return QRect(widget.mapTo(root, QPoint(0, 0)), widget.size())


def _assert_buttons_do_not_overlap(root):
    buttons = [b for b in root.findChildren(QPushButton) if b.isVisible()]
    for i, a in enumerate(buttons):
        ra = _rect_in(a, root)
        assert ra.width() > 0 and ra.height() > 0
        for b in buttons[i + 1 :]:
            rb = _rect_in(b, root)
            intersection = ra.intersected(rb)
            assert intersection.width() <= 1 or intersection.height() <= 1, (
                f"Tombol overlap: {a.text()!r} dan {b.text()!r}; "
                f"{ra.getRect()} vs {rb.getRect()}"
            )


def test_main_window_layout_no_button_overlap_at_laptop_size():
    app = _app()
    win = MainWindow()
    win.resize(1024, 700)
    win.show()
    app.processEvents()

    assert win.width() >= 980
    assert win.height() >= 650
    _assert_buttons_do_not_overlap(win)

    win.close()
    app.processEvents()


def test_two_line_subtitle_row_is_tall_enough():
    app = _app()
    win = MainWindow()
    win.project.entries = [
        SubtitleEntry(
            1,
            0,
            3000,
            "- Aku pulang.\n- Kenapa?",
            speaker="Speaker 1 | Speaker 2",
            original_text="Aku pulang Kenapa",
            source_index=1,
        )
    ]
    win.refresh_table()
    assert win.table.rowHeight(0) >= 46
    win.close()
    app.processEvents()


def test_long_file_names_are_elided_not_allowed_to_expand_layout():
    app = _app()
    win = MainWindow()
    win.resize(1024, 700)
    win.show()
    app.processEvents()

    name = "Film Indonesia Dengan Nama Yang Sangat Panjang Sekali Versi Final 2026 1080p WEB-DL.mp4"
    win._set_path_label(win.video_label, name, "C:/Film/" + name)
    app.processEvents()

    assert win.video_label.toolTip().endswith(name)
    assert win.video_label.text() != name
    assert win.video_label.width() < win.width()

    win.close()
    app.processEvents()


def test_api_manager_layout_no_button_overlap_at_small_size(tmp_path, monkeypatch):
    app = _app()
    vault = KeyVault()
    # Jangan membaca/menulis vault akun nyata ketika test.
    vault.path = tmp_path / "keys.json"
    vault.data = {"active": 0, "model": "gemini-3.8-flash", "keys": [""] * vault.MAX_KEYS}

    dlg = ApiManagerDialog(vault)
    dlg.resize(640, 500)
    dlg.show()
    app.processEvents()

    assert dlg.width() >= 620
    assert dlg.height() >= 460
    _assert_buttons_do_not_overlap(dlg)

    dlg.close()
    app.processEvents()
