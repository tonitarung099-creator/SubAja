from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QHeaderView, QMessageBox, QComboBox
)

from app.core.gemini import GeminiPunctuator, GeminiError
from app.core.keyvault import KeyVault


class TestWorker(QObject):
    done = Signal(bool, str)

    def __init__(self, key: str, model: str):
        super().__init__()
        self.key = key
        self.model = model

    def run(self):
        try:
            answer = GeminiPunctuator(self.key, self.model).test()
            self.done.emit(True, answer or "OK")
        except Exception as exc:
            self.done.emit(False, str(exc))


class ApiManagerDialog(QDialog):
    def __init__(self, vault: KeyVault, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gemini API Manager - 100 Slot")
        self.resize(760, 620)
        self.vault = vault
        self.thread = None
        self.worker = None

        root = QVBoxLayout(self)
        note = QLabel(
            "Simpan hingga 100 API key. Hanya SATU key aktif yang dipakai. "
            "Aplikasi tidak melakukan rotasi otomatis untuk melewati rate limit. "
            "Masukkan API key Gemini yang dibuat untuk project Google AI Studio/Google Cloud milikmu."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model Gemini:"))
        self.model_edit = QLineEdit(self.vault.model)
        self.model_edit.setPlaceholderText("gemini-3.8-flash")
        model_row.addWidget(self.model_edit, 1)
        root.addLayout(model_row)

        self.table = QTableWidget(KeyVault.MAX_KEYS, 3)
        self.table.setHorizontalHeaderLabels(["Slot", "API Key", "Aktif"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        self.key_edits: list[QLineEdit] = []
        for i in range(KeyVault.MAX_KEYS):
            slot_item = QTableWidgetItem(f"#{i+1:03d}")
            slot_item.setFlags(slot_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, slot_item)

            edit = QLineEdit(self.vault.keys[i])
            edit.setEchoMode(QLineEdit.Password)
            edit.setPlaceholderText("Kosong")
            self.table.setCellWidget(i, 1, edit)
            self.key_edits.append(edit)

            active = QTableWidgetItem("✓" if i == self.vault.active_index else "")
            active.setTextAlignment(Qt.AlignCenter)
            active.setFlags(active.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 2, active)

        self.table.cellClicked.connect(self._choose_active)

        buttons = QHBoxLayout()
        self.test_btn = QPushButton("Test Key Aktif")
        self.test_btn.clicked.connect(self.test_active)
        buttons.addWidget(self.test_btn)
        buttons.addStretch(1)
        self.save_btn = QPushButton("Simpan")
        self.save_btn.clicked.connect(self.save_and_accept)
        self.cancel_btn = QPushButton("Batal")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        root.addLayout(buttons)

    def _choose_active(self, row: int, col: int):
        if col != 2:
            return
        for i in range(KeyVault.MAX_KEYS):
            self.table.item(i, 2).setText("✓" if i == row else "")
        self.vault.active_index = row

    def _sync(self):
        self.vault.data["keys"] = [e.text().strip() for e in self.key_edits]
        self.vault.model = self.model_edit.text().strip()

    def save_and_accept(self):
        self._sync()
        self.vault.save()
        self.accept()

    def _test_running(self) -> bool:
        if self.thread is None:
            return False
        try:
            return self.thread.isRunning()
        except RuntimeError:
            self.thread = None
            self.worker = None
            return False

    def reject(self):
        if self._test_running():
            QMessageBox.information(self, "Gemini", "Tunggu test API key selesai sebelum menutup jendela ini.")
            return
        super().reject()

    def closeEvent(self, event):
        if self._test_running():
            QMessageBox.information(self, "Gemini", "Tunggu test API key selesai sebelum menutup jendela ini.")
            event.ignore()
            return
        super().closeEvent(event)

    def test_active(self):
        if self._test_running():
            return
        self._sync()
        key = self.vault.active_key
        if not key:
            QMessageBox.warning(self, "Gemini", "Slot aktif belum berisi API key.")
            return
        self.test_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.test_btn.setText("Menguji...")
        self.thread = QThread(self)
        self.worker = TestWorker(key, self.vault.model)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        thread = self.thread
        worker = self.worker
        worker.done.connect(self._test_done)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._test_thread_finished(thread))
        thread.start()

    def _test_thread_finished(self, thread: QThread):
        self.test_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.test_btn.setText("Test Key Aktif")
        if self.thread is thread:
            self.thread = None
            self.worker = None
        thread.deleteLater()

    def _test_done(self, ok: bool, message: str):
        if ok:
            QMessageBox.information(self, "Gemini", f"Key aktif berhasil. Respons: {message[:80]}")
        else:
            QMessageBox.critical(self, "Gemini", f"Test gagal:\n{message}")
