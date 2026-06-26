"""
ui/main_window.py
=================
Main application window.

Layout
------
┌─────────────────────────────────────────────────────────────────┐
│ MenuBar + ToolBar                                               │
├──────────┬──────────────────────────┬──────────────────────────┤
│  Video   │   Video Player           │  Annotation Panel        │
│ Library  │                          │                          │
│ (left)   │   ─────────────────────  │  ─────────────────────── │
│          │   Processing Tools Tab   │                          │
└──────────┴──────────────────────────┴──────────────────────────┘
│ Status bar                                                      │
└─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations
import os
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QStatusBar,
    QToolBar, QLabel, QProgressBar, QTabWidget,
    QDialog, QListWidget, QListWidgetItem, QPushButton
)
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction, QIcon, QKeySequence

from core.models import VideoInfo
from core.workers import FolderScanWorker
from core.annotation_io import (
    xml_path_for_video, load_annotations_xml, find_annotation_xml
)
from core.video_processor import extract_video_metadata

from ui.video_library  import VideoLibraryPanel
from ui.video_player   import VideoPlayer
from ui.annotation_panel import AnnotationPanel
from ui.processing_tab import ProcessingTab


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self._current_video: Optional[VideoInfo] = None
        self._scan_worker: Optional[FolderScanWorker] = None

        self.setWindowTitle("Autism Behavior Annotation Tool  v1.0")
        self.setMinimumSize(1280, 780)
        self.resize(1440, 880)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Outer horizontal splitter (library | main area)
        self._outer_split = QSplitter(Qt.Horizontal)
        self._outer_split.setHandleWidth(2)
        root_lay.addWidget(self._outer_split)

        # ── Left: Video library ────────────────────────────────────────
        self._library = VideoLibraryPanel()
        self._library.video_selected.connect(self._on_video_selected)
        self._library.load_folder_requested.connect(self._open_folder)
        self._outer_split.addWidget(self._library)

        # ── Centre: player + processing tabs ──────────────────────────
        centre_widget = QWidget()
        centre_lay = QVBoxLayout(centre_widget)
        centre_lay.setContentsMargins(0, 0, 0, 0)
        centre_lay.setSpacing(0)

        centre_split = QSplitter(Qt.Vertical)
        centre_split.setHandleWidth(2)

        # Video player
        self._player = VideoPlayer()
        self._player.position_changed.connect(self._on_player_position_changed)
        self._player.playback_ended.connect(
            lambda: self._status("Playback finished"))
        centre_split.addWidget(self._player)

        # Processing tabs below the player
        self._processing = ProcessingTab()
        self._processing.skeleton_extracted.connect(self._on_skeleton_extracted)
        self._processing.log_message.connect(self._status)
        centre_split.addWidget(self._processing)

        centre_split.setStretchFactor(0, 3)
        centre_split.setStretchFactor(1, 2)
        centre_lay.addWidget(centre_split)
        self._outer_split.addWidget(centre_widget)

        # ── Right: Annotation panel ────────────────────────────────────
        self._ann_panel = AnnotationPanel()
        self._ann_panel.annotation_added.connect(self._on_annotation_changed)
        self._ann_panel.annotation_removed.connect(self._on_annotation_changed)
        self._ann_panel.seek_requested.connect(self._player.seek_to_time)
        self._ann_panel.annotations_saved.connect(
            lambda p: self._status(f"Saved: {os.path.basename(p)}"))
        self._outer_split.addWidget(self._ann_panel)

        # Splitter proportions
        self._outer_split.setStretchFactor(0, 0)
        self._outer_split.setStretchFactor(1, 1)
        self._outer_split.setStretchFactor(2, 0)
        self._outer_split.setSizes([240, 760, 320])

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")

        act_open = QAction("📂  Open Folder…", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._open_folder)
        file_menu.addAction(act_open)

        act_load_video = QAction("🎞  Load Single Video…", self)
        act_load_video.setShortcut("Ctrl+Shift+O")
        act_load_video.triggered.connect(self._load_single_video)
        file_menu.addAction(act_load_video)

        act_load_ann = QAction("📑  Load Annotations Folder…", self)
        act_load_ann.setShortcut("Ctrl+Shift+A")
        act_load_ann.triggered.connect(self._open_annotations_folder)
        file_menu.addAction(act_load_ann)

        file_menu.addSeparator()

        act_save = QAction("💾  Save Annotations", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_current)
        file_menu.addAction(act_save)

        file_menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # View
        view_menu = mb.addMenu("&View")
        act_full = QAction("Fullscreen", self)
        act_full.setCheckable(True)
        act_full.setShortcut(QKeySequence.FullScreen)
        act_full.toggled.connect(
            lambda on: self.showFullScreen() if on else self.showNormal())
        view_menu.addAction(act_full)

        # Help
        help_menu = mb.addMenu("&Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(tb)

        act_open = QAction("📂 Open Folder", self)
        act_open.triggered.connect(self._open_folder)
        tb.addAction(act_open)

        act_video = QAction("🎞 Load Video", self)
        act_video.triggered.connect(self._load_single_video)
        tb.addAction(act_video)

        act_load_ann_tb = QAction("📑 Load Annotations", self)
        act_load_ann_tb.triggered.connect(self._open_annotations_folder)
        tb.addAction(act_load_ann_tb)

        tb.addSeparator()

        act_save = QAction("💾 Save Annotations", self)
        act_save.triggered.connect(self._save_current)
        tb.addAction(act_save)

        tb.addSeparator()

        self._lbl_toolbar = QLabel("  No video loaded")
        self._lbl_toolbar.setStyleSheet("color: rgb(130,130,155);")
        tb.addWidget(self._lbl_toolbar)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, 1)

        self._status_progress = QProgressBar()
        self._status_progress.setFixedWidth(180)
        self._status_progress.setFixedHeight(14)
        self._status_progress.setRange(0, 100)
        self._status_progress.hide()
        sb.addPermanentWidget(self._status_progress)

        self._frame_label = QLabel("Frame: —")
        self._frame_label.setStyleSheet("color: rgb(100,100,125);")
        sb.addPermanentWidget(self._frame_label)

    # ──────────────────────────────────────────────────────────────────
    # File / Folder actions
    # ──────────────────────────────────────────────────────────────────

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Open Video Dataset Folder",
            os.path.expanduser("~")
        )
        if not folder:
            return

        self._status(f"Scanning {folder}…")
        self._status_progress.show()
        self._status_progress.setValue(0)

        worker = FolderScanWorker(folder)
        worker.progress.connect(self._on_scan_progress)
        worker.videos_found.connect(self._on_videos_found)
        worker.error.connect(lambda e: self._status(f"Warning: {e}"))
        worker.finished.connect(self._on_scan_finished)

        self._scan_worker = worker
        worker.start()

    def _load_single_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Video",
            os.path.expanduser("~"),
            "Video Files (*.mp4 *.mov *.avi *.mkv *.webm)"
        )
        if not path:
            return
        try:
            meta = extract_video_metadata(path)
            info = VideoInfo(**{k: v for k, v in meta.items()
                                if k != "annotations"})
            xml_path = xml_path_for_video(path)
            info.annotations = load_annotations_xml(xml_path)
            self._library.set_videos([info])
            self._processing.set_library_videos([info])
            self._select_video(info)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _save_current(self):
        if self._current_video:
            self._ann_panel._save_xml()

    def _open_annotations_folder(self):
        videos = self._library._videos
        if not videos:
            QMessageBox.information(
                self, "No Videos Loaded",
                "Load a video folder first — annotations are matched to "
                "videos by filename."
            )
            return

        folder = QFileDialog.getExistingDirectory(
            self, "Open Annotations Folder",
            os.path.expanduser("~")
        )
        if not folder:
            return

        matched = 0
        total_anns = 0
        for info in videos:
            xml_path = find_annotation_xml(folder, info.file_path)
            if xml_path:
                anns = load_annotations_xml(xml_path)
                if anns:
                    info.annotations = anns
                    matched += 1
                    total_anns += len(anns)
                    self._library.update_annotation_count(info)

        # Refresh processing tab counts
        self._processing.set_library_videos(videos)

        # Refresh panels for current video if it got updated annotations
        if self._current_video and self._current_video in videos:
            self._ann_panel.load_video(self._current_video)
            self._processing.set_video(self._current_video)

        msg = (f"Annotations: matched {matched}/{len(videos)} video(s) "
               f"({total_anns} annotation(s)) from {os.path.basename(folder)}")
        self._status(msg)

        if matched == 0:
            QMessageBox.warning(
                self, "No Matches",
                f"No XML files in {folder} matched any loaded video by name.\n\n"
                f"Expected names: <video_stem>_annotations.xml or <video_stem>.xml"
            )
            return

        unannotated = [v for v in videos if not v.annotations]
        if unannotated:
            self._show_unannotated_dialog(unannotated, matched, len(videos))

    def _show_unannotated_dialog(self, unannotated: list,
                                 matched: int, total: int):
        """Show a scrollable list of videos that have no annotations."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Videos Without Annotations — {len(unannotated)}")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)

        header = QLabel(
            f"<b>{matched}</b> of <b>{total}</b> videos got annotations. "
            f"<b>{len(unannotated)}</b> still have none — listed below. "
            f"Double-click a row to load that video."
        )
        header.setWordWrap(True)
        lay.addWidget(header)

        lst = QListWidget()
        for v in unannotated:
            item = QListWidgetItem(v.filename)
            item.setToolTip(v.file_path)
            item.setData(Qt.UserRole, v)
            lst.addItem(item)
        lst.itemDoubleClicked.connect(
            lambda it: (self._select_video(it.data(Qt.UserRole)),
                        self._library.select_video(it.data(Qt.UserRole)))
        )
        lay.addWidget(lst, stretch=1)

        # Buttons
        btns = QHBoxLayout()
        btn_copy = QPushButton("Copy filenames")
        btn_copy.clicked.connect(
            lambda: self._copy_to_clipboard(
                "\n".join(v.filename for v in unannotated)
            )
        )
        btns.addWidget(btn_copy)

        btn_save = QPushButton("Save list to .txt…")
        btn_save.clicked.connect(
            lambda: self._save_unannotated_list(unannotated)
        )
        btns.addWidget(btn_save)

        btns.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setDefault(True)
        btn_close.clicked.connect(dlg.accept)
        btns.addWidget(btn_close)

        lay.addLayout(btns)
        dlg.exec()

    def _copy_to_clipboard(self, text: str):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(text)
        self._status("Filenames copied to clipboard.")

    def _save_unannotated_list(self, unannotated: list):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Un-annotated Videos List",
            "unannotated_videos.txt",
            "Text files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                for v in unannotated:
                    fh.write(f"{v.filename}\t{v.file_path}\n")
            self._status(f"Saved list of {len(unannotated)} video(s) → "
                         f"{os.path.basename(path)}")
        except OSError as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    # ──────────────────────────────────────────────────────────────────
    # Worker callbacks
    # ──────────────────────────────────────────────────────────────────

    def _on_scan_progress(self, current: int, total: int, message: str):
        self._library.show_progress(current, total, message)
        if total > 0:
            self._status_progress.setValue(int(current / total * 100))

    def _on_videos_found(self, videos: list):
        self._library.set_videos(videos)
        self._processing.set_library_videos(videos)

    def _on_scan_finished(self):
        self._library.hide_progress()
        self._status_progress.hide()
        n = len(self._library._videos)
        self._status(f"Loaded {n} video(s)")

    # ──────────────────────────────────────────────────────────────────
    # Video selection
    # ──────────────────────────────────────────────────────────────────

    def _on_video_selected(self, video_info: VideoInfo):
        self._select_video(video_info)

    def _select_video(self, video_info: VideoInfo):
        self._current_video = video_info

        # Load into player
        ok = self._player.load_video(video_info.file_path)
        if not ok:
            QMessageBox.warning(
                self, "Load Error",
                f"Cannot open video:\n{video_info.file_path}"
            )
            return

        # Update annotation panel
        self._ann_panel.load_video(video_info)

        # Update processing tab
        self._processing.set_video(video_info)

        # Update toolbar
        self._lbl_toolbar.setText(
            f"  {os.path.basename(video_info.file_path)}"
            f"  {video_info.width}×{video_info.height}"
            f"  {video_info.fps} fps"
            f"  {video_info.duration_label}"
        )

        self._status(f"Loaded: {video_info.filename}")

    # ──────────────────────────────────────────────────────────────────
    # Player callbacks
    # ──────────────────────────────────────────────────────────────────

    def _on_player_position_changed(self, seconds: float):
        self._ann_panel.update_current_time(seconds)
        frame = self._player.current_frame_index()
        self._frame_label.setText(f"Frame: {frame:06d}")

    # ──────────────────────────────────────────────────────────────────
    # Annotation callbacks
    # ──────────────────────────────────────────────────────────────────

    def _on_annotation_changed(self, *args):
        if self._current_video:
            self._library.update_annotation_count(self._current_video)
            # Keep processing tab in sync (slice button enable state)
            self._processing.set_video(self._current_video)

    # ──────────────────────────────────────────────────────────────────
    # Skeleton callback
    # ──────────────────────────────────────────────────────────────────

    def _on_skeleton_extracted(self, video_path: str, frames: list):
        if (self._current_video and
                self._current_video.file_path == video_path):
            self._player.set_skeleton_frames(frames)
            self._status(f"Skeleton ready ({len(frames)} frames) — "
                         "enable overlay in the player.")

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._status_label.setText(msg)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About — Autism Behavior Annotation Tool",
            "<h3>Autism Behavior Annotation Tool</h3>"
            "<p>Version 1.0 — NeuroVision Lab</p>"
            "<p>A production-ready desktop application for preprocessing "
            "autism-behavior video datasets.</p>"
            "<p><b>Pipeline:</b></p>"
            "<ul>"
            "<li>Video loading &amp; browsing</li>"
            "<li>Behaviour annotation with XML export</li>"
            "<li>Clip slicing by annotation class</li>"
            "<li>3-second windowing with overlap</li>"
            "<li>MediaPipe Pose skeleton extraction</li>"
            "</ul>"
            "<p><b>Stack:</b> PySide6 · OpenCV · MediaPipe</p>"
        )

    def closeEvent(self, event):
        # Save current annotations before exit
        if self._current_video and self._current_video.annotations:
            self._ann_panel._auto_save()
        super().closeEvent(event)
