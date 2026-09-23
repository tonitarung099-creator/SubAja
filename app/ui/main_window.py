from __future__ import annotations

from pathlib import Path
import traceback

from PySide6.QtCore import Qt, QUrl, Signal, QObject, QThread
from PySide6.QtGui import QAction, QBrush, QColor, QFontMetrics
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QCheckBox, QDoubleSpinBox, QSpinBox, QSplitter, QSlider,
    QAbstractItemView, QGridLayout, QSizePolicy
)

from app.core.gemini import GeminiPunctuator, GeminiQuotaError, estimate_gemini_work
from app.core.keyvault import KeyVault
from app.core.qc import audit_entries, changed_source_indices, source_group_is_safe
from app.core.project import SubtitleProject
from app.core.speaker import SpeakerDiarizer, apply_speaker_segments
from app.core.style import apply_reference_film_style
from app.core.subtitle import ms_to_timestamp, renumber
from app.core.verbatim import is_verbatim_safe, tidy_entries, visible_length
from .api_manager import ApiManagerDialog


class FunctionWorker(QObject):
    progress = Signal(int, str)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            result = self.fn(lambda p, m="": self.progress.emit(int(p), str(m)))
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(f"{exc}\n\n{traceback.format_exc(limit=4)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SubAja - Subtitle Film Verbatim")
        self.resize(1180, 760)
        self.setMinimumSize(980, 650)
        self.project = SubtitleProject()
        self.vault = KeyVault()
        self._thread = None
        self._worker = None
        self._worker_done_callback = None
        self._worker_title = ""
        self._updating_table = False
        self._qc_results = []
        self._last_autosave_error = ""

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self._build_ui()
        self._build_menu()
        self.statusBar().showMessage("Siap. Masukkan video film dan SRT hasil CapCut.")

    def _build_menu(self):
        menu = self.menuBar().addMenu("File")
        open_video = QAction("Buka Video", self)
        open_video.triggered.connect(self.load_video)
        menu.addAction(open_video)
        open_srt = QAction("Buka SRT CapCut", self)
        open_srt.triggered.connect(self.load_srt)
        menu.addAction(open_srt)
        open_project = QAction("Buka Project SubAja", self)
        open_project.triggered.connect(self.load_project)
        menu.addAction(open_project)
        save_project = QAction("Simpan Project SubAja", self)
        save_project.triggered.connect(self.save_project)
        menu.addAction(save_project)
        menu.addSeparator()
        export_action = QAction("Export SRT", self)
        export_action.triggered.connect(self.export_srt)
        menu.addAction(export_action)

        settings = self.menuBar().addMenu("Pengaturan")
        api_action = QAction("Gemini API Manager (100)", self)
        api_action.triggered.connect(self.open_api_manager)
        settings.addAction(api_action)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        file_row = QGridLayout()
        file_row.setColumnStretch(1, 1)
        file_row.setColumnStretch(3, 1)
        self.video_label = QLabel("Video: belum dipilih")
        self.srt_label = QLabel("SRT: belum dipilih")
        for label in (self.video_label, self.srt_label):
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            label.setMinimumWidth(120)
        btn_video = QPushButton("Pilih Video")
        btn_srt = QPushButton("Pilih SRT CapCut")
        btn_video.clicked.connect(self.load_video)
        btn_srt.clicked.connect(self.load_srt)
        file_row.addWidget(btn_video, 0, 0)
        file_row.addWidget(self.video_label, 0, 1)
        file_row.addWidget(btn_srt, 0, 2)
        file_row.addWidget(self.srt_label, 0, 3)
        layout.addLayout(file_row)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        layout.addWidget(splitter, 1)

        video_wrap = QWidget()
        video_layout = QVBoxLayout(video_wrap)
        video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(180)
        self.player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget)
        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_btn)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(self.seek_slider)
        controls.addWidget(self.position_slider, 1)
        self.time_label = QLabel("00:00:00 / 00:00:00")
        controls.addWidget(self.time_label)
        video_layout.addLayout(controls)
        splitter.addWidget(video_wrap)

        table_wrap = QWidget()
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "Mulai", "Selesai", "Speaker", "Teks", "QC"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.verticalHeader().setMinimumSectionSize(30)
        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.cellDoubleClicked.connect(self.seek_to_row)
        self.table.cellChanged.connect(self.cell_changed)
        table_layout.addWidget(self.table)

        review_row = QGridLayout()
        review_row.setColumnStretch(3, 1)
        self.only_issues = QCheckBox("Hanya yang perlu dicek")
        self.only_issues.stateChanged.connect(self.apply_qc_filter)
        review_row.addWidget(self.only_issues, 0, 0)
        next_review = QPushButton("Berikutnya yang Perlu Dicek")
        next_review.clicked.connect(self.next_review_issue)
        review_row.addWidget(next_review, 0, 1)
        mark_reviewed = QPushButton("Tandai Sudah Dicek")
        mark_reviewed.clicked.connect(self.mark_selected_reviewed)
        review_row.addWidget(mark_reviewed, 0, 2)
        self.qc_label = QLabel("QC: belum dianalisis")
        self.qc_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        review_row.addWidget(self.qc_label, 0, 3)
        table_layout.addLayout(review_row)
        splitter.addWidget(table_wrap)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 360])

        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(6)
        actions.setColumnStretch(5, 1)

        self.speaker_btn = QPushButton("1. Analisis Speaker Lokal")
        self.speaker_btn.clicked.connect(self.analyze_speakers)
        actions.addWidget(self.speaker_btn, 0, 0)

        actions.addWidget(QLabel("Jumlah speaker:"), 0, 1)
        self.num_speakers = QSpinBox()
        self.num_speakers.setRange(0, 30)
        self.num_speakers.setValue(0)
        self.num_speakers.setToolTip("0 = otomatis")
        actions.addWidget(self.num_speakers, 0, 2)

        actions.addWidget(QLabel("Threshold:"), 0, 3)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.45, 0.95)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.75)
        actions.addWidget(self.threshold, 0, 4)

        self.split_changes = QCheckBox("Pisahkan saat speaker berganti")
        self.split_changes.setChecked(True)
        actions.addWidget(self.split_changes, 0, 5)

        self.local_btn = QPushButton("2. Rapikan + Gaya Film")
        self.local_btn.clicked.connect(self.tidy_local)
        actions.addWidget(self.local_btn, 1, 0)

        self.api_btn = QPushButton("Gemini API (100)")
        self.api_btn.clicked.connect(self.open_api_manager)
        actions.addWidget(self.api_btn, 1, 1, 1, 2)

        self.gemini_btn = QPushButton("3. Gemini Hemat: Tanda Baca")
        self.gemini_btn.clicked.connect(self.run_gemini)
        actions.addWidget(self.gemini_btn, 1, 3, 1, 2)

        self.gemini_usage_label = QLabel("Gemini: belum dihitung")
        self.gemini_usage_label.setToolTip(
            "Perkiraan caption yang dikirim ke Gemini dan jumlah request batch."
        )
        self.gemini_usage_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        actions.addWidget(self.gemini_usage_label, 1, 5)

        self.include_speaker = QCheckBox("Label speaker di SRT")
        self.include_speaker.setChecked(False)
        actions.addWidget(self.include_speaker, 2, 0, 1, 2)

        self.export_btn = QPushButton("Export SRT")
        self.export_btn.clicked.connect(self.export_srt)
        actions.addWidget(self.export_btn, 2, 4)

        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._playback_state)

    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih film", "", "Video (*.mp4 *.mkv *.mov *.avi *.m4v *.webm);;Semua file (*)"
        )
        if not path:
            return
        try:
            self.project.load_video(path)
            self._set_path_label(self.video_label, Path(path).name, path)
            self.player.setSource(QUrl.fromLocalFile(path))
            self.statusBar().showMessage("Video dimuat.")
        except Exception as exc:
            QMessageBox.critical(self, "Video", str(exc))

    def load_srt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih SRT CapCut", "", "Subtitle SRT (*.srt)")
        if not path:
            return
        try:
            self.project.load_srt(path)
            self._set_path_label(self.srt_label, Path(path).name, path)
            self.refresh_table()
            self.statusBar().showMessage(f"{len(self.project.entries)} subtitle dimuat.")
        except Exception as exc:
            QMessageBox.critical(self, "SRT", str(exc))

    def save_project(self):
        if not self.project.entries:
            QMessageBox.warning(self, "Project", "Belum ada subtitle untuk disimpan.")
            return
        default_name = "project.subaja.json"
        if self.project.srt_path:
            default_name = self.project.srt_path.with_suffix(".subaja.json").name
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Project SubAja", default_name, "SubAja Project (*.subaja.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".subaja.json"):
            path += ".subaja.json"
        try:
            self.project.save_session(path)
            self.statusBar().showMessage(f"Project tersimpan: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Project", str(exc))

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Buka Project SubAja", "", "SubAja Project (*.subaja.json);;JSON (*.json)"
        )
        if not path:
            return
        try:
            self.project.load_session(path)

            # Selalu bersihkan state project sebelumnya agar video lama tidak
            # tetap tampil ketika file sumber project baru sudah dipindah/hilang.
            self.player.stop()
            self.player.setSource(QUrl())
            self.video_label.setProperty("full_name", "")
            self.video_label.setText("Video: belum tersedia")
            self.video_label.setToolTip("")
            self.srt_label.setProperty("full_name", "")
            self.srt_label.setText("SRT: data tersimpan di project")
            self.srt_label.setToolTip("")

            missing: list[str] = []
            if self.project.video_path:
                self._set_path_label(
                    self.video_label, self.project.video_path.name, str(self.project.video_path)
                )
                if self.project.video_path.is_file():
                    self.player.setSource(QUrl.fromLocalFile(str(self.project.video_path)))
                else:
                    missing.append(f"Video tidak ditemukan: {self.project.video_path}")

            if self.project.srt_path:
                self._set_path_label(
                    self.srt_label, self.project.srt_path.name, str(self.project.srt_path)
                )
                if not self.project.srt_path.is_file():
                    missing.append(f"SRT sumber tidak ditemukan: {self.project.srt_path}")

            self.refresh_table()
            if missing:
                QMessageBox.warning(
                    self,
                    "File sumber project tidak ditemukan",
                    "\n".join(missing)
                    + "\n\nData subtitle hasil kerja tetap dimuat. Pilih video lagi sebelum analisis/review audio.",
                )
                self.statusBar().showMessage("Project dimuat, tetapi ada file sumber yang tidak ditemukan.")
            else:
                self.statusBar().showMessage(f"Project dilanjutkan: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Project", str(exc))

    def _autosave_project(self):
        if not self.project.project_path:
            return
        try:
            self.project.save_session(self.project.project_path)
            self._last_autosave_error = ""
        except Exception as exc:
            message = f"Autosave gagal: {exc}"
            self._last_autosave_error = message
            self.statusBar().showMessage(message)

    @staticmethod
    def _set_path_label(label: QLabel, name: str, full_path: str):
        label.setProperty("full_name", name)
        label.setToolTip(full_path)
        width = max(120, label.width() or 260)
        label.setText(QFontMetrics(label.font()).elidedText(name, Qt.ElideMiddle, width))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for label in (getattr(self, "video_label", None), getattr(self, "srt_label", None)):
            if label is None:
                continue
            name = label.property("full_name")
            if name:
                width = max(120, label.width())
                label.setText(QFontMetrics(label.font()).elidedText(str(name), Qt.ElideMiddle, width))

    def refresh_table(self):
        self._qc_results = audit_entries(self.project.entries)
        review_count = sum(1 for q in self._qc_results if q.level != "ok")
        critical_count = sum(1 for q in self._qc_results if q.level == "critical")
        self.qc_label.setText(
            f"QC: {review_count} perlu dicek" + (f" • {critical_count} kritis" if critical_count else "")
        )
        gemini_count, gemini_requests = estimate_gemini_work(self.project.entries, batch_size=60)
        if hasattr(self, "gemini_usage_label"):
            self.gemini_usage_label.setText(
                f"Gemini: {gemini_count}/{len(self.project.entries)} caption • ±{gemini_requests} request"
            )

        self._updating_table = True
        try:
            self.table.setRowCount(len(self.project.entries))
            for row, e in enumerate(self.project.entries):
                qc = self._qc_results[row]
                vals = [
                    str(row + 1),
                    ms_to_timestamp(e.start_ms),
                    ms_to_timestamp(e.end_ms),
                    e.speaker,
                    e.text,
                    qc.label,
                ]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    if col in (0, 1, 2, 5):
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if col == 3:
                        if e.speaker:
                            hue = sum((i + 1) * ord(ch) for i, ch in enumerate(e.speaker)) % 360
                            item.setBackground(QBrush(QColor.fromHsv(hue, 55, 255)))
                        if e.speaker_confidence:
                            item.setToolTip(
                                f"Confidence speaker: {e.speaker_confidence:.0%}. "
                                "Warna yang sama = speaker yang sama. Bisa diedit manual jika salah."
                            )
                    if col == 5:
                        item.setToolTip(qc.message)
                    self.table.setItem(row, col, item)
                needs_two_lines = "\n" in e.text or visible_length(e.text) > 55
                self.table.setRowHeight(row, 48 if needs_two_lines else 34)
        finally:
            self._updating_table = False
        self.apply_qc_filter()

    def apply_qc_filter(self):
        issues_only = self.only_issues.isChecked() if hasattr(self, "only_issues") else False
        for row, qc in enumerate(self._qc_results):
            self.table.setRowHidden(row, issues_only and qc.level == "ok")

    def next_review_issue(self):
        if not self._qc_results:
            return
        current = self.table.currentRow()
        total = len(self._qc_results)
        for step in range(1, total + 1):
            row = (current + step) % total
            if self._qc_results[row].level != "ok":
                self.table.setRowHidden(row, False)
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 4))
                if 0 <= row < len(self.project.entries):
                    self.player.setPosition(self.project.entries[row].start_ms)
                return
        self.statusBar().showMessage("QC bersih: tidak ada subtitle yang perlu dicek.")

    def mark_selected_reviewed(self):
        row = self.table.currentRow()
        if not (0 <= row < len(self.project.entries)):
            QMessageBox.information(self, "QC", "Pilih satu baris subtitle terlebih dahulu.")
            return
        entry = self.project.entries[row]
        if entry.review_reason:
            entry.review_reason = ""
        if entry.speaker:
            entry.speaker_confidence = 1.0
        self.refresh_table()
        self._autosave_project()
        self.statusBar().showMessage("Baris ditandai sudah dicek. QC teknis lain tetap dipertahankan.")

    def cell_changed(self, row: int, col: int):
        if self._updating_table or not (0 <= row < len(self.project.entries)):
            return
        entry = self.project.entries[row]
        if col == 3:
            entry.speaker = self.table.item(row, col).text().strip()
            entry.speaker_confidence = 1.0 if entry.speaker else 0.0
            # Jangan hapus review_reason di sini: peringatan bisa terkait batas
            # kata, overlap, atau tag format, bukan hanya nama speaker.
            self.refresh_table()
            self._autosave_project()
            return
        if col != 4:
            return

        old_text = entry.text
        new_text = self.table.item(row, col).text()
        if not is_verbatim_safe(old_text, new_text):
            self._updating_table = True
            try:
                self.table.item(row, col).setText(old_text)
            finally:
                self._updating_table = False
            self.statusBar().showMessage(
                "Word Lock: edit ditolak karena mengubah kata, tag format, atau struktur dialog dua speaker."
            )
            return

        entry.text = new_text
        if not source_group_is_safe(self.project.entries, entry.source_index):
            entry.text = old_text
            self._updating_table = True
            try:
                self.table.item(row, col).setText(old_text)
            finally:
                self._updating_table = False
            self.statusBar().showMessage(
                "Word Lock: edit ditolak karena menambah, menghapus, mengganti, atau mengubah urutan kata CapCut."
            )
            return
        self.refresh_table()
        self._autosave_project()

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _playback_state(self, state):
        self.play_btn.setText("⏸ Pause" if state == QMediaPlayer.PlayingState else "▶ Play")

    def _duration_changed(self, duration: int):
        self.position_slider.setRange(0, max(1, duration))
        self._position_changed(self.player.position())

    def _position_changed(self, position: int):
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self.time_label.setText(f"{self._short_time(position)} / {self._short_time(self.player.duration())}")

    @staticmethod
    def _short_time(ms: int) -> str:
        s = max(0, ms // 1000)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def seek_slider(self, value: int):
        self.player.setPosition(value)

    def seek_to_row(self, row: int, col: int):
        if 0 <= row < len(self.project.entries):
            self.player.setPosition(self.project.entries[row].start_ms)
            self.player.play()

    def _set_busy(self, busy: bool, message: str = ""):
        self.centralWidget().setEnabled(not busy)
        self.menuBar().setEnabled(not busy)
        if message:
            self.statusBar().showMessage(message)

    def _worker_running(self) -> bool:
        if self._thread is None:
            return False
        try:
            return self._thread.isRunning()
        except RuntimeError:
            self._thread = None
            self._worker = None
            self._worker_done_callback = None
            return False

    def _run_worker(self, fn, on_done, title: str):
        if self._worker_running():
            QMessageBox.information(self, "SubAja", "Masih ada proses yang berjalan.")
            return

        self.progress.setValue(0)
        self._worker_done_callback = on_done
        self._worker_title = title
        self._set_busy(True, title)

        self._thread = QThread(self)
        self._worker = FunctionWorker(fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.done.connect(self._on_worker_done)
        self._worker.done.connect(self._thread.quit)
        self._worker.done.connect(self._worker.deleteLater)
        self._worker.error.connect(self._on_worker_error)
        self._worker.error.connect(self._thread.quit)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._worker_thread_finished)
        self._thread.start()

    def _on_worker_progress(self, percent: int, message: str):
        self.progress.setValue(max(0, min(100, int(percent))))
        self.statusBar().showMessage(message or self._worker_title)

    def _on_worker_done(self, value):
        callback = self._worker_done_callback
        if callback is None:
            return
        try:
            callback(value)
        except Exception as exc:
            self.progress.setValue(0)
            QMessageBox.critical(self, "Proses gagal", str(exc))
            self.statusBar().showMessage("Hasil proses gagal diterapkan.")

    def _worker_thread_finished(self):
        thread = self._thread
        self._set_busy(False)
        self._worker = None
        self._thread = None
        self._worker_done_callback = None
        self._worker_title = ""
        if thread is not None:
            try:
                thread.deleteLater()
            except RuntimeError:
                pass

    def _on_worker_error(self, message: str):
        self._worker_done_callback = None
        self.progress.setValue(0)
        QMessageBox.critical(self, "Proses gagal", message)
        self.statusBar().showMessage("Proses gagal.")

    def closeEvent(self, event):
        if self._worker_running():
            QMessageBox.information(
                self,
                "SubAja",
                "Proses masih berjalan. Tunggu sampai selesai sebelum menutup aplikasi.",
            )
            event.ignore()
            return
        super().closeEvent(event)

    def analyze_speakers(self):
        if not self.project.video_path or not self.project.entries:
            QMessageBox.warning(self, "Speaker", "Masukkan video dan SRT CapCut terlebih dahulu.")
            return
        video = str(self.project.video_path)
        entries = [e.clone() for e in self.project.entries]
        threshold = self.threshold.value()
        n = self.num_speakers.value()
        split = self.split_changes.isChecked()

        def task(progress):
            diarizer = SpeakerDiarizer(cluster_threshold=threshold, num_speakers=n)
            segments = diarizer.analyze_video(video, progress=lambda p: progress(p, f"Analisis speaker {p}%"))
            result = apply_speaker_segments(entries, segments, split_on_change=split)
            return result, len({s.speaker for s in segments})

        def done(value):
            result, count = value
            self.project.entries = result
            self.refresh_table()
            self._autosave_project()
            self.progress.setValue(100)
            self.statusBar().showMessage(f"Speaker selesai. Terdeteksi sekitar {count} speaker.")

        self._run_worker(task, done, "Menganalisis pergantian speaker secara lokal...")

    def tidy_local(self):
        if not self.project.entries:
            return
        self.project.entries = tidy_entries(self.project.entries)
        self.project.entries = apply_reference_film_style(self.project.entries)
        self.refresh_table()
        self._autosave_project()
        self.statusBar().showMessage(
            "Gaya film diterapkan: maks. 2 baris, 42 karakter/baris, dialog dua speaker memakai tanda -."
        )

    def open_api_manager(self):
        dlg = ApiManagerDialog(self.vault, self)
        dlg.exec()

    def run_gemini(self):
        if not self.project.entries:
            QMessageBox.warning(self, "Gemini", "Masukkan SRT terlebih dahulu.")
            return
        self.vault.load()
        if not self.vault.active_key:
            QMessageBox.warning(self, "Gemini", "Belum ada API key aktif. Buka Gemini API Manager terlebih dahulu.")
            return
        entries = [e.clone() for e in self.project.entries]
        key = self.vault.active_key
        model = self.vault.model

        def task(progress):
            punct = GeminiPunctuator(key, model)
            return punct.process(entries, batch_size=60, progress=lambda p, m: progress(p, m))

        def done(value):
            result, stats = value
            self.project.entries = result
            self.refresh_table()
            self._autosave_project()
            self.progress.setValue(100)
            self.statusBar().showMessage(
                f"Gemini hemat selesai. Dikirim {stats.processed}, dilewati {stats.skipped_clean}, "
                f"cache {stats.cached}, ditolak Word Lock {stats.rejected_word_changes}, "
                f"respons hilang {stats.missing_results}."
            )

        self._run_worker(task, done, "Gemini hemat: hanya caption yang masih perlu tanda baca...")

    def export_srt(self):
        if not self.project.entries:
            QMessageBox.warning(self, "Export", "Belum ada subtitle untuk diekspor.")
            return
        default_name = "subtitle_final.srt"
        if self.project.srt_path:
            default_name = self.project.srt_path.with_name(self.project.srt_path.stem + "_SubAja.srt").name
        path, _ = QFileDialog.getSaveFileName(self, "Export SRT", default_name, "Subtitle SRT (*.srt)")
        if not path:
            return
        if not path.lower().endswith(".srt"):
            path += ".srt"
        changed = changed_source_indices(self.project.entries)
        if changed:
            QMessageBox.critical(
                self,
                "Word Lock",
                f"Export diblokir karena kata berubah pada {len(changed)} caption sumber CapCut. "
                "Perbaiki baris bertanda KRITIS terlebih dahulu.",
            )
            return
        try:
            self.project.entries = renumber(self.project.entries)
            self.project.export(path, include_speaker=self.include_speaker.isChecked())
            self.statusBar().showMessage(f"SRT tersimpan: {path}")
            QMessageBox.information(self, "Export", "Subtitle berhasil diekspor.")
        except Exception as exc:
            QMessageBox.critical(self, "Export", str(exc))
