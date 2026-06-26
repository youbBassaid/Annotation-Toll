"""
ui/video_library.py
===================
Left sidebar panel showing the loaded video library.
Allows browsing, filtering, and selecting videos.
"""

from __future__ import annotations
from typing import List, Optional
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QLineEdit,
    QProgressBar, QFrame, QSizePolicy, QToolButton
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

from core.models import VideoInfo


class VideoLibraryPanel(QWidget):
    """
    Panel listing all loaded videos.

    Signals
    -------
    video_selected(VideoInfo)
    load_folder_requested()
    """

    video_selected       = Signal(object)   # VideoInfo
    load_folder_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._videos: List[VideoInfo] = []
        self._filtered: List[VideoInfo] = []
        self._current_video: Optional[VideoInfo] = None

        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("VIDEO LIBRARY")
        title.setObjectName("section_title")
        header.addWidget(title)
        header.addStretch()

        self._btn_load = QToolButton()
        self._btn_load.setText("📂")
        self._btn_load.setToolTip("Open folder…")
        self._btn_load.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                font-size: 18px;
                padding: 2px;
            }
            QToolButton:hover { color: #63b3ed; }
        """)
        self._btn_load.clicked.connect(self.load_folder_requested)
        header.addWidget(self._btn_load)
        layout.addLayout(header)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter videos…")
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        # Video list
        self._list = QListWidget()
        self._list.setSpacing(2)
        self._list.currentItemChanged.connect(self._item_changed)
        layout.addWidget(self._list, stretch=1)

        # Stats bar
        self._lbl_count = QLabel("No videos loaded")
        self._lbl_count.setStyleSheet(
            "color: rgb(100,100,125); font-size: 11px;")
        layout.addWidget(self._lbl_count)

        # Progress bar (shown during scanning)
        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.hide()
        layout.addWidget(self._progress)

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def set_videos(self, videos: List[VideoInfo]):
        self._videos = videos
        self._apply_filter()

    def show_progress(self, current: int, total: int, message: str):
        self._progress.show()
        if total > 0:
            self._progress.setValue(int(current / total * 100))
        self._lbl_count.setText(message[:50])

    def hide_progress(self):
        self._progress.hide()
        n = len(self._videos)
        self._lbl_count.setText(f"{n} video{'s' if n != 1 else ''} loaded")

    def select_video(self, video_info: VideoInfo):
        """Highlight a specific video in the list."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole) is video_info:
                self._list.setCurrentItem(item)
                break

    def update_annotation_count(self, video_info: VideoInfo):
        """Refresh the annotation badge on a list item."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole) is video_info:
                item.setText(self._format_label(video_info))
                break

    # ──────────────────────────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────────────────────────

    def _apply_filter(self, query: str = ""):
        query = self._search.text().lower()
        self._filtered = [
            v for v in self._videos
            if not query or query in v.filename.lower()
        ]
        self._rebuild_list()

    def _rebuild_list(self):
        prev_path = (self._current_video.file_path
                     if self._current_video else None)
        self._list.clear()
        for info in self._filtered:
            item = QListWidgetItem(self._format_label(info))
            item.setData(Qt.UserRole, info)
            item.setToolTip(info.file_path)

            # Annotated videos get a tint
            if info.annotations:
                item.setForeground(QBrush(QColor("#7dd3fc")))

            self._list.addItem(item)

            # Restore selection
            if prev_path and info.file_path == prev_path:
                self._list.setCurrentItem(item)

    def _item_changed(self, current, previous):
        if current is None:
            return
        info: VideoInfo = current.data(Qt.UserRole)
        self._current_video = info
        self.video_selected.emit(info)

    @staticmethod
    def _format_label(info: VideoInfo) -> str:
        ann_badge = f" [{len(info.annotations)}]" if info.annotations else ""
        dur = f"  {info.duration_label}" if info.duration else ""
        name = os.path.splitext(info.filename)[0]
        return f"{name}{ann_badge}{dur}"
