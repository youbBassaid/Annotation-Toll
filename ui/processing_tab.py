"""
ui/processing_tab.py
====================
Tab widget housing:
  • Video Slicing panel  (annotation → clips)
  • Fragmentation panel  (clips → 3s windows)
  • Skeleton Extraction panel
"""

from __future__ import annotations
import os
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QProgressBar, QTextEdit, QDoubleSpinBox,
    QGroupBox, QCheckBox, QSpinBox, QFormLayout,
    QSizePolicy, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal

from core.models import VideoInfo
from core.workers import (
    SlicingWorker, BatchSlicingWorker,
    FragmentationWorker, SkeletonWorker, BatchSkeletonWorker
)
from core.skeleton_extractor import is_mediapipe_available


class ProcessingTab(QWidget):
    """
    Container for all post-annotation processing tools.

    Signals
    -------
    skeleton_extracted(str, list)   video_path, list[SkeletonFrame]
    log_message(str)
    """

    skeleton_extracted = Signal(str, list)
    log_message        = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._video_info: Optional[VideoInfo] = None
        self._library_videos: List[VideoInfo] = []
        self._last_clips: List[str] = []
        self._active_worker = None

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._wrap_scroll(self._build_slicing_tab()),  "🔪 Slicing")
        tabs.addTab(self._wrap_scroll(self._build_fragment_tab()), "🪟 Windowing")
        tabs.addTab(self._wrap_scroll(self._build_skeleton_tab()), "🦴 Skeleton")
        layout.addWidget(tabs)

    @staticmethod
    def _wrap_scroll(inner: QWidget) -> QScrollArea:
        """Wrap a tab's content in a vertical scroll area so nothing gets clipped."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sa.setWidget(inner)
        return sa

    # ── Slicing tab ────────────────────────────────────────────────────

    def _build_slicing_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        info = QLabel(
            "Slice each annotation segment into a separate video clip.\n"
            "Clips are saved in sub-folders named after the action class."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: rgb(140,140,165); font-size: 12px;")
        lay.addWidget(info)

        grp = QGroupBox("Output Directory")
        grp_lay = QHBoxLayout(grp)
        self._slice_out = QLineEdit()
        self._slice_out.setPlaceholderText("dataset_processed/")
        grp_lay.addWidget(self._slice_out)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_slice_output)
        grp_lay.addWidget(btn_browse)
        lay.addWidget(grp)

        self._btn_slice = QPushButton("▶  Slice Annotations → Clips  (Current Video)")
        self._btn_slice.setObjectName("accent_btn")
        self._btn_slice.setEnabled(False)
        self._btn_slice.clicked.connect(self._run_slicing)
        lay.addWidget(self._btn_slice)

        # ── Batch slicing across the whole loaded library ──────────────
        grp_batch = QGroupBox("Batch — All Annotated Videos in Library")
        gb_lay = QVBoxLayout(grp_batch)

        self._lbl_batch_info = QLabel("No videos loaded.")
        self._lbl_batch_info.setStyleSheet("color: #7dd3fc; font-size: 12px;")
        self._lbl_batch_info.setWordWrap(True)
        gb_lay.addWidget(self._lbl_batch_info)

        self._btn_batch_slice = QPushButton("🔪  Batch Slice All Annotated Videos")
        self._btn_batch_slice.setEnabled(False)
        self._btn_batch_slice.clicked.connect(self._run_batch_slicing)
        gb_lay.addWidget(self._btn_batch_slice)
        lay.addWidget(grp_batch)

        self._slice_progress = self._make_progress()
        lay.addWidget(self._slice_progress)
        self._slice_log = self._make_log()
        lay.addWidget(self._slice_log, stretch=1)
        return w

    # ── Windowing tab ──────────────────────────────────────────────────

    def _build_fragment_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        info = QLabel(
            "Split clips into fixed-size windows with overlap.\n"
            "Default: 3 s windows, 1 s overlap (2 s step)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: rgb(140,140,165); font-size: 12px;")
        lay.addWidget(info)

        params = QGroupBox("Window Parameters")
        form = QFormLayout(params)
        self._win_size = QDoubleSpinBox()
        self._win_size.setRange(0.5, 30.0)
        self._win_size.setValue(3.0)
        self._win_size.setSuffix(" s")
        form.addRow("Window size:", self._win_size)

        self._win_overlap = QDoubleSpinBox()
        self._win_overlap.setRange(0.0, 29.0)
        self._win_overlap.setValue(1.0)
        self._win_overlap.setSuffix(" s")
        form.addRow("Overlap:", self._win_overlap)
        lay.addWidget(params)

        grp2 = QGroupBox("Input Clips Folder")
        g2l = QHBoxLayout(grp2)
        self._frag_in = QLineEdit()
        self._frag_in.setPlaceholderText("Folder containing .mp4 clips")
        g2l.addWidget(self._frag_in)
        btn_b2 = QPushButton("Browse…")
        btn_b2.clicked.connect(self._browse_frag_input)
        g2l.addWidget(btn_b2)
        lay.addWidget(grp2)

        grp3 = QGroupBox("Output Folder")
        g3l = QHBoxLayout(grp3)
        self._frag_out = QLineEdit()
        self._frag_out.setPlaceholderText("dataset_windows/")
        g3l.addWidget(self._frag_out)
        btn_b3 = QPushButton("Browse…")
        btn_b3.clicked.connect(self._browse_frag_output)
        g3l.addWidget(btn_b3)
        lay.addWidget(grp3)

        self._btn_fragment = QPushButton("▶  Fragment Clips → Windows")
        self._btn_fragment.setObjectName("accent_btn")
        self._btn_fragment.clicked.connect(self._run_fragmentation)
        lay.addWidget(self._btn_fragment)

        self._frag_progress = self._make_progress()
        lay.addWidget(self._frag_progress)
        self._frag_log = self._make_log()
        lay.addWidget(self._frag_log, stretch=1)
        return w

    # ── Skeleton tab ───────────────────────────────────────────────────

    def _build_skeleton_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        if not is_mediapipe_available():
            warn = QLabel(
                "⚠  Ultralytics (YOLOv8) is not installed.\n\n"
                "Install it with:\n\n"
                "    pip install ultralytics\n\n"
                "Then restart the application."
            )
            warn.setStyleSheet(
                "color: #f6ad55; font-size: 13px; padding: 20px;"
            )
            warn.setAlignment(Qt.AlignCenter)
            lay.addWidget(warn)
            return w

        info = QLabel(
            "Extract YOLOv8-Pose keypoints (17 COCO joints) frame-by-frame.\n"
            "Results are saved as <video>_skeleton.json next to each video."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: rgb(140,140,165); font-size: 12px;")
        lay.addWidget(info)

        params = QGroupBox("Extraction Parameters")
        form = QFormLayout(params)
        self._skip_frames = QSpinBox()
        self._skip_frames.setRange(1, 10)
        self._skip_frames.setValue(1)
        self._skip_frames.setToolTip(
            "Process every N-th frame (1 = every frame, 2 = every other, …)")
        form.addRow("Frame skip:", self._skip_frames)
        lay.addWidget(params)

        # Single-video mode
        grp_single = QGroupBox("Current Video")
        gs_lay = QVBoxLayout(grp_single)
        self._lbl_skel_video = QLabel("No video loaded")
        self._lbl_skel_video.setStyleSheet("color: #7dd3fc; font-size: 12px;")
        gs_lay.addWidget(self._lbl_skel_video)
        self._btn_extract_single = QPushButton("🦴 Extract Skeleton (Current Video)")
        self._btn_extract_single.setObjectName("accent_btn")
        self._btn_extract_single.setEnabled(False)
        self._btn_extract_single.clicked.connect(self._extract_single)
        gs_lay.addWidget(self._btn_extract_single)
        lay.addWidget(grp_single)

        # Batch mode
        grp_batch = QGroupBox("Batch — All Videos in Folder")
        gb_lay = QHBoxLayout(grp_batch)
        self._batch_folder = QLineEdit()
        self._batch_folder.setPlaceholderText("Select folder with videos…")
        gb_lay.addWidget(self._batch_folder)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_batch_folder)
        gb_lay.addWidget(btn_browse)
        lay.addWidget(grp_batch)

        self._btn_extract_batch = QPushButton("🦴 Batch Extract Skeletons")
        self._btn_extract_batch.clicked.connect(self._extract_batch)
        lay.addWidget(self._btn_extract_batch)

        self._skel_progress = self._make_progress()
        lay.addWidget(self._skel_progress)
        self._skel_log = self._make_log()
        lay.addWidget(self._skel_log, stretch=1)
        return w

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def set_video(self, video_info: VideoInfo):
        self._video_info = video_info
        self._btn_slice.setEnabled(bool(video_info.annotations))
        if hasattr(self, "_lbl_skel_video"):
            self._lbl_skel_video.setText(
                os.path.basename(video_info.file_path))
        if hasattr(self, "_btn_extract_single"):
            self._btn_extract_single.setEnabled(True)

        # Default output path next to the video
        default_out = os.path.join(
            os.path.dirname(video_info.file_path), "dataset_processed"
        )
        self._slice_out.setText(default_out)

    def set_library_videos(self, videos: List[VideoInfo]):
        """Receive the full list of loaded videos (for batch operations)."""
        self._library_videos = list(videos)
        annotated = [v for v in self._library_videos if v.annotations]
        n_clips   = sum(len(v.annotations) for v in annotated)
        if hasattr(self, "_lbl_batch_info"):
            if not self._library_videos:
                self._lbl_batch_info.setText("No videos loaded.")
            else:
                self._lbl_batch_info.setText(
                    f"{len(self._library_videos)} video(s) loaded · "
                    f"{len(annotated)} annotated · "
                    f"{n_clips} total annotation(s) ready to slice."
                )
            self._btn_batch_slice.setEnabled(len(annotated) > 0)

        # Default batch output: sibling of the first video's folder
        if self._library_videos and not self._slice_out.text():
            first_dir = os.path.dirname(self._library_videos[0].file_path)
            self._slice_out.setText(os.path.join(first_dir, "dataset_processed"))

    # ──────────────────────────────────────────────────────────────────
    # Slicing
    # ──────────────────────────────────────────────────────────────────

    def _browse_slice_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._slice_out.setText(folder)

    def _run_slicing(self):
        if not self._video_info or not self._video_info.annotations:
            return
        out = self._slice_out.text() or "dataset_processed"
        self._slice_log.clear()
        self._slice_progress.setValue(0)

        worker = SlicingWorker(self._video_info, out)
        worker.progress.connect(lambda c, t, m: (
            self._slice_progress.setValue(
                int(c / max(1, t) * 100)),
            self._slice_log.append(m)
        ))
        worker.clips_created.connect(self._on_clips_created)
        worker.error.connect(lambda e: self._slice_log.append(f"❌ {e}"))
        worker.finished.connect(lambda: self._slice_progress.setValue(100))
        self._active_worker = worker
        worker.start()

    def _on_clips_created(self, clips: list):
        self._last_clips = clips
        self._slice_log.append(
            f"\n✅ {len(clips)} clip(s) created.\n"
            + "\n".join(f"  • {os.path.basename(c)}" for c in clips[:10])
            + ("  …" if len(clips) > 10 else "")
        )
        # Pre-fill fragmentation input
        if clips:
            self._frag_in.setText(os.path.dirname(clips[0]))

    def _run_batch_slicing(self):
        annotated = [v for v in self._library_videos if v.annotations]
        if not annotated:
            self._slice_log.append("⚠ No annotated videos in the library.")
            return

        out = self._slice_out.text() or "dataset_processed"
        self._slice_log.clear()
        self._slice_progress.setValue(0)
        n_clips = sum(len(v.annotations) for v in annotated)
        self._slice_log.append(
            f"Batch slicing {len(annotated)} video(s), "
            f"{n_clips} annotation(s) → {out}\n"
        )

        worker = BatchSlicingWorker(annotated, out)
        worker.progress.connect(lambda c, t, m: (
            self._slice_progress.setValue(int(c / max(1, t) * 100)),
            self._slice_log.append(m)
        ))
        worker.video_done.connect(lambda p, n: self._slice_log.append(
            f"  ✓ {os.path.basename(p)} — {n} clip(s)"
        ))
        worker.clips_created.connect(self._on_clips_created)
        worker.error.connect(lambda e: self._slice_log.append(f"❌ {e}"))
        worker.finished.connect(lambda: self._slice_progress.setValue(100))
        self._active_worker = worker
        worker.start()

    # ──────────────────────────────────────────────────────────────────
    # Fragmentation
    # ──────────────────────────────────────────────────────────────────

    def _browse_frag_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Clips Folder")
        if folder:
            self._frag_in.setText(folder)

    def _browse_frag_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._frag_out.setText(folder)

    def _run_fragmentation(self):
        in_folder  = self._frag_in.text()
        out_folder = self._frag_out.text() or "dataset_windows"
        win  = self._win_size.value()
        over = self._win_overlap.value()

        # Collect clips from the input folder
        clips = []
        if in_folder and os.path.isdir(in_folder):
            for root, _, files in os.walk(in_folder):
                for f in files:
                    if f.lower().endswith(".mp4"):
                        clips.append(os.path.join(root, f))
        elif self._last_clips:
            clips = self._last_clips

        if not clips:
            self._frag_log.append("⚠ No clips found. Run slicing first or select a folder.")
            return

        self._frag_log.clear()
        self._frag_log.append(f"Fragmenting {len(clips)} clip(s)…")
        self._frag_progress.setValue(0)

        worker = FragmentationWorker(clips, out_folder, win, over)
        worker.progress.connect(lambda c, t, m: (
            self._frag_progress.setValue(int(c / max(1, t) * 100)),
            self._frag_log.append(m)
        ))
        worker.windows_created.connect(
            lambda ws: self._frag_log.append(
                f"\n✅ {len(ws)} window(s) created."
            )
        )
        worker.error.connect(lambda e: self._frag_log.append(f"❌ {e}"))
        worker.finished.connect(lambda: self._frag_progress.setValue(100))
        self._active_worker = worker
        worker.start()

    # ──────────────────────────────────────────────────────────────────
    # Skeleton
    # ──────────────────────────────────────────────────────────────────

    def _extract_single(self):
        if not self._video_info:
            return
        self._skel_log.clear()
        self._skel_log.append(f"Extracting skeletons for:\n  {self._video_info.file_path}\n")
        self._skel_progress.setValue(0)

        worker = SkeletonWorker(
            self._video_info.file_path,
            skip_frames=self._skip_frames.value()
        )
        worker.progress.connect(lambda c, t, m: (
            self._skel_progress.setValue(int(c / max(1, t) * 100)),
        ))
        worker.skeleton_done.connect(self._on_skeleton_done)
        worker.error.connect(lambda e: self._skel_log.append(f"❌ {e}"))
        worker.finished.connect(lambda: self._skel_progress.setValue(100))
        self._active_worker = worker
        worker.start()

    def _on_skeleton_done(self, path: str, frames: list):
        json_path = path.replace(os.path.splitext(path)[1], "_skeleton.json")
        self._skel_log.append(
            f"✅ Extracted {len(frames)} skeleton frame(s).\n"
            f"Saved → {json_path}\n"
            f"Enable 'Show Skeleton' in the video player to visualise."
        )
        self.skeleton_extracted.emit(path, frames)

    def _browse_batch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Videos")
        if folder:
            self._batch_folder.setText(folder)

    def _extract_batch(self):
        folder = self._batch_folder.text()
        if not folder or not os.path.isdir(folder):
            self._skel_log.append("⚠ Please select a valid video folder.")
            return

        exts = {".mp4", ".mov", ".avi"}
        paths = []
        for root, _, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in exts:
                    paths.append(os.path.join(root, f))

        if not paths:
            self._skel_log.append("⚠ No video files found in that folder.")
            return

        self._skel_log.clear()
        self._skel_log.append(f"Batch extracting {len(paths)} videos…")
        self._skel_progress.setValue(0)

        worker = BatchSkeletonWorker(paths, self._skip_frames.value())
        worker.progress.connect(lambda c, t, m: (
            self._skel_progress.setValue(int(c / max(1, t) * 100)),
            self._skel_log.append(m)
        ))
        worker.video_done.connect(
            lambda p, fs: self._skel_log.append(
                f"  ✓ {os.path.basename(p)} — {len(fs)} frames"
            )
        )
        worker.error.connect(lambda e: self._skel_log.append(f"❌ {e}"))
        worker.finished.connect(lambda: (
            self._skel_progress.setValue(100),
            self._skel_log.append("\n✅ Batch skeleton extraction complete.")
        ))
        self._active_worker = worker
        worker.start()

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_progress() -> QProgressBar:
        pb = QProgressBar()
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setFixedHeight(6)
        pb.setTextVisible(False)
        return pb

    @staticmethod
    def _make_log() -> QTextEdit:
        te = QTextEdit()
        te.setReadOnly(True)
        te.setMinimumHeight(80)
        te.setPlaceholderText("Processing log…")
        return te
