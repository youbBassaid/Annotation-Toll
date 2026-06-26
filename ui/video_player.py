"""
ui/video_player.py
==================
A fully-featured video player widget built on OpenCV + QTimer.
Renders frames to a QLabel via QImage, so it works without
QtMultimedia codec dependencies.

Features
--------
• Play / Pause / Stop
• Frame-accurate seeking via slider
• Playback speed (0.25×, 0.5×, 1×, 2×, 4×)
• Current-time / total-time display
• Optional skeleton overlay (drawn via OpenCV)
• Emits: frame_changed(int), position_changed(float), playback_ended()
"""

from __future__ import annotations
import os
from typing import Optional, List

import cv2
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QImage, QPixmap, QFont, QColor

from core.models import SkeletonFrame
from core.skeleton_extractor import SkeletonExtractor, is_mediapipe_available


def _seconds_to_hms(secs: float) -> str:
    total = int(secs)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class VideoDisplay(QLabel):
    """QLabel that maintains aspect ratio and draws a 'no video' placeholder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 180)
        self.setStyleSheet("""
            QLabel {
                background-color: rgb(10,10,16);
                border: 1px solid rgb(40,40,60);
                border-radius: 4px;
            }
        """)
        self._show_placeholder()

    def _show_placeholder(self):
        self.setText("▶  No video loaded")
        self.setStyleSheet("""
            QLabel {
                background-color: rgb(10,10,16);
                color: rgb(70,70,100);
                font-size: 16px;
                border: 1px solid rgb(35,35,55);
                border-radius: 4px;
            }
        """)

    def display_frame(self, frame_bgr: np.ndarray):
        """Convert BGR numpy frame to QPixmap and display it."""
        h, w, ch = frame_bgr.shape
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix  = QPixmap.fromImage(qimg)

        # Scale while preserving aspect ratio
        label_size = self.size()
        pix = pix.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pix)
        self.setText("")
        self.setStyleSheet("""
            QLabel {
                background-color: rgb(10,10,16);
                border: 1px solid rgb(40,40,60);
                border-radius: 4px;
            }
        """)


class VideoPlayer(QWidget):
    """
    Full-featured video player widget.

    Signals
    -------
    frame_changed(int)       : emitted every frame with the frame index
    position_changed(float)  : emitted every frame with timestamp (seconds)
    playback_ended()         : emitted when the video reaches the last frame
    """

    frame_changed    = Signal(int)
    position_changed = Signal(float)
    playback_ended   = Signal()

    SPEED_OPTIONS = [("0.25×", 0.25), ("0.5×", 0.5),
                     ("1×",    1.0),  ("2×",   2.0), ("4×", 4.0)]

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── state ──────────────────────────────────────────────────────
        self._cap: Optional[cv2.VideoCapture] = None
        self._video_path: str = ""
        self._fps: float = 30.0
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._playing: bool = False
        self._speed: float = 1.0

        # skeleton overlay
        self._show_skeleton: bool = False
        self._skeleton_frames: List[SkeletonFrame] = []
        self._extractor: Optional[SkeletonExtractor] = None

        # ── timer ──────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        # ── UI ─────────────────────────────────────────────────────────
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Video display
        self._display = VideoDisplay()
        layout.addWidget(self._display, stretch=1)

        # Seek slider
        self._seek_slider = QSlider(Qt.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.setValue(0)
        self._seek_slider.sliderPressed.connect(self._slider_pressed)
        self._seek_slider.sliderReleased.connect(self._slider_released)
        self._seek_slider.sliderMoved.connect(self._slider_moved)
        layout.addWidget(self._seek_slider)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        self._btn_play  = QPushButton("▶")
        self._btn_play.setFixedSize(36, 36)
        self._btn_play.setToolTip("Play / Pause  (Space)")
        self._btn_play.clicked.connect(self.toggle_play)

        self._btn_stop = QPushButton("■")
        self._btn_stop.setFixedSize(36, 36)
        self._btn_stop.setToolTip("Stop")
        self._btn_stop.clicked.connect(self.stop)

        self._btn_prev = QPushButton("◀◀")
        self._btn_prev.setFixedSize(40, 36)
        self._btn_prev.setToolTip("Previous frame  (←)")
        self._btn_prev.clicked.connect(self.prev_frame)

        self._btn_next = QPushButton("▶▶")
        self._btn_next.setFixedSize(40, 36)
        self._btn_next.setToolTip("Next frame  (→)")
        self._btn_next.clicked.connect(self.next_frame)

        self._lbl_time = QLabel("00:00 / 00:00")
        self._lbl_time.setStyleSheet("color: rgb(160,160,185); font-size: 12px; "
                                     "font-family: monospace;")

        self._speed_combo = QComboBox()
        for label, _ in self.SPEED_OPTIONS:
            self._speed_combo.addItem(label)
        self._speed_combo.setCurrentIndex(2)  # 1×
        self._speed_combo.currentIndexChanged.connect(self._speed_changed)
        self._speed_combo.setFixedWidth(72)
        self._speed_combo.setToolTip("Playback speed")

        self._btn_skeleton = QPushButton("🦴 Skeleton")
        self._btn_skeleton.setCheckable(True)
        self._btn_skeleton.setToolTip("Toggle skeleton overlay")
        self._btn_skeleton.toggled.connect(self._toggle_skeleton)
        self._btn_skeleton.setEnabled(False)

        ctrl.addWidget(self._btn_stop)
        ctrl.addWidget(self._btn_prev)
        ctrl.addWidget(self._btn_play)
        ctrl.addWidget(self._btn_next)
        ctrl.addWidget(self._lbl_time)
        ctrl.addStretch()
        ctrl.addWidget(self._speed_combo)
        ctrl.addWidget(self._btn_skeleton)

        layout.addLayout(ctrl)

        # Keyboard shortcuts
        self.setFocusPolicy(Qt.StrongFocus)

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def load_video(self, path: str) -> bool:
        """Load a video file. Returns True on success."""
        self.stop()
        if self._cap:
            self._cap.release()
            self._cap = None

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return False

        self._cap          = cap
        self._video_path   = path
        self._fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._current_frame = 0

        # Reset skeleton
        self._skeleton_frames = []
        self._show_skeleton   = False
        self._btn_skeleton.setChecked(False)
        self._btn_skeleton.setEnabled(False)

        # Load skeleton JSON if it exists
        from core.skeleton_extractor import SkeletonExtractor
        json_path = SkeletonExtractor.json_path_for_video(path)
        if os.path.exists(json_path):
            try:
                self._skeleton_frames = SkeletonExtractor.load_json(json_path)
                self._btn_skeleton.setEnabled(True)
            except Exception:
                pass

        self._seek_to_frame(0)
        return True

    def set_skeleton_frames(self, frames: List[SkeletonFrame]):
        """Inject skeleton frames (e.g., from the extraction worker)."""
        self._skeleton_frames = frames
        self._btn_skeleton.setEnabled(bool(frames))

    def current_time(self) -> float:
        """Return current playback position in seconds."""
        if self._fps > 0:
            return self._current_frame / self._fps
        return 0.0

    def duration(self) -> float:
        if self._fps > 0:
            return self._total_frames / self._fps
        return 0.0

    def current_frame_index(self) -> int:
        return self._current_frame

    def seek_to_time(self, seconds: float):
        """Seek to a specific time in seconds."""
        frame = int(seconds * self._fps)
        self._seek_to_frame(frame)

    def toggle_play(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if self._cap is None:
            return
        self._playing = True
        self._btn_play.setText("⏸")
        interval = max(1, int(1000 / (self._fps * self._speed)))
        self._timer.start(interval)

    def pause(self):
        self._playing = False
        self._timer.stop()
        self._btn_play.setText("▶")

    def stop(self):
        self.pause()
        if self._cap:
            self._seek_to_frame(0)

    def next_frame(self):
        self._seek_to_frame(min(self._current_frame + 1, self._total_frames - 1))

    def prev_frame(self):
        self._seek_to_frame(max(self._current_frame - 1, 0))

    # ──────────────────────────────────────────────────────────────────
    # Internal slots
    # ──────────────────────────────────────────────────────────────────

    def _next_frame(self):
        if self._cap is None:
            return
        ret, frame = self._cap.read()
        if not ret:
            self.pause()
            self.playback_ended.emit()
            return

        self._current_frame += 1
        self._render_frame(frame)
        self._update_ui()

    def _seek_to_frame(self, frame_idx: int):
        if self._cap is None:
            return
        frame_idx = max(0, min(frame_idx, self._total_frames - 1))
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self._cap.read()
        if ret:
            self._current_frame = frame_idx
            self._render_frame(frame)
            self._update_ui()

    def _render_frame(self, frame: np.ndarray):
        """Apply optional skeleton overlay then display the frame."""
        if self._show_skeleton and self._skeleton_frames:
            # Find closest skeleton frame
            sf = self._get_skeleton_for_frame(self._current_frame)
            if sf:
                if self._extractor is None:
                    try:
                        self._extractor = SkeletonExtractor()
                    except Exception:
                        pass
                if self._extractor:
                    frame = self._extractor.draw_skeleton(frame, sf)

        self._display.display_frame(frame)
        self.frame_changed.emit(self._current_frame)
        self.position_changed.emit(self.current_time())

    def _get_skeleton_for_frame(self, frame_idx: int) -> Optional[SkeletonFrame]:
        """Binary-search the skeleton list for the nearest frame."""
        if not self._skeleton_frames:
            return None
        # simple linear scan on the sorted list
        best = None
        best_dist = float("inf")
        for sf in self._skeleton_frames:
            d = abs(sf.frame_id - frame_idx)
            if d < best_dist:
                best_dist = d
                best = sf
            if d == 0:
                break
        return best

    def _update_ui(self):
        """Sync slider and time label with current position."""
        total = max(1, self._total_frames - 1)
        slider_val = int(self._current_frame / total * 1000)
        self._seek_slider.blockSignals(True)
        self._seek_slider.setValue(slider_val)
        self._seek_slider.blockSignals(False)

        cur_lbl = _seconds_to_hms(self.current_time())
        tot_lbl = _seconds_to_hms(self.duration())
        self._lbl_time.setText(f"{cur_lbl} / {tot_lbl}")

    def _speed_changed(self, index: int):
        self._speed = self.SPEED_OPTIONS[index][1]
        if self._playing:
            interval = max(1, int(1000 / (self._fps * self._speed)))
            self._timer.setInterval(interval)

    def _toggle_skeleton(self, checked: bool):
        self._show_skeleton = checked
        # Refresh current frame
        if self._cap:
            self._seek_to_frame(self._current_frame)

    # seek slider interactions
    def _slider_pressed(self):
        self._timer.stop()

    def _slider_released(self):
        val = self._seek_slider.value()
        frame = int(val / 1000 * max(1, self._total_frames - 1))
        self._seek_to_frame(frame)
        if self._playing:
            interval = max(1, int(1000 / (self._fps * self._speed)))
            self._timer.start(interval)

    def _slider_moved(self, value: int):
        frame = int(value / 1000 * max(1, self._total_frames - 1))
        self._seek_to_frame(frame)

    # ──────────────────────────────────────────────────────────────────
    # Keyboard shortcuts
    # ──────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            self.toggle_play()
        elif key == Qt.Key_Left:
            self.prev_frame()
        elif key == Qt.Key_Right:
            self.next_frame()
        elif key == Qt.Key_Home:
            self._seek_to_frame(0)
        elif key == Qt.Key_End:
            self._seek_to_frame(self._total_frames - 1)
        else:
            super().keyPressEvent(event)

    # ──────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._timer.stop()
        if self._cap:
            self._cap.release()
        if self._extractor:
            self._extractor.close()
        super().closeEvent(event)
