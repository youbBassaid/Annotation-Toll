"""
core/workers.py
===============
QThread-based workers for all heavy / blocking operations.
Each worker emits typed Qt signals so the UI can update progressively.
"""

from __future__ import annotations
from typing import Optional, List

from PySide6.QtCore import QThread, Signal

from core.models import VideoInfo, Annotation, SkeletonFrame
from core.video_processor import (
    extract_video_metadata,
    slice_all_annotations,
    fragment_all_clips,
)
from core.annotation_io import xml_path_for_video, load_annotations_xml
from core.skeleton_extractor import SkeletonExtractor, is_mediapipe_available


# ──────────────────────────────────────────────
# Generic base
# ──────────────────────────────────────────────

class BaseWorker(QThread):
    progress  = Signal(int, int, str)   # current, total, message
    finished  = Signal()
    error     = Signal(str)


# ──────────────────────────────────────────────
# Scan folder for videos
# ──────────────────────────────────────────────

class FolderScanWorker(BaseWorker):
    """Scans a root directory for video files and extracts metadata."""

    VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

    videos_found = Signal(list)   # list[VideoInfo]

    def __init__(self, root_path: str, parent=None):
        super().__init__(parent)
        self._root = root_path

    def run(self):
        import os
        videos: list[VideoInfo] = []
        all_files = []

        for dirpath, _, filenames in os.walk(self._root):
            for fname in filenames:
                if os.path.splitext(fname)[1].lower() in self.VIDEO_EXTS:
                    all_files.append(os.path.join(dirpath, fname))

        for idx, path in enumerate(all_files):
            self.progress.emit(idx, len(all_files),
                               f"Scanning {os.path.basename(path)}")
            try:
                meta = extract_video_metadata(path)
                info = VideoInfo(**{k: v for k, v in meta.items()
                                    if k != "annotations"})
                # Load existing annotations if present
                xml_path = xml_path_for_video(path)
                info.annotations = load_annotations_xml(xml_path)
                videos.append(info)
            except Exception as e:
                self.error.emit(f"Skipping {path}: {e}")

        self.videos_found.emit(videos)
        self.finished.emit()


# ──────────────────────────────────────────────
# Video slicing worker
# ──────────────────────────────────────────────

class SlicingWorker(BaseWorker):
    """Slices all annotated segments into individual clips."""

    clips_created = Signal(list)   # list[str] — output paths

    def __init__(self, video_info: VideoInfo, output_root: str, parent=None):
        super().__init__(parent)
        self._info   = video_info
        self._out    = output_root

    def run(self):
        try:
            clips = slice_all_annotations(
                self._info, self._out,
                progress_cb=lambda c, t, m: self.progress.emit(c, t, m),
            )
            self.clips_created.emit(clips)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────────────────────────
# Batch slicing worker (multiple annotated videos)
# ──────────────────────────────────────────────

class BatchSlicingWorker(BaseWorker):
    """Slices every annotation across a list of annotated videos."""

    clips_created = Signal(list)        # list[str] — every clip path
    video_done    = Signal(str, int)    # (video_path, n_clips)

    def __init__(self, videos: list[VideoInfo], output_root: str, parent=None):
        super().__init__(parent)
        self._videos = [v for v in videos if v.annotations]
        self._out    = output_root

    def run(self):
        import os
        if not self._videos:
            self.error.emit("No annotated videos found.")
            self.finished.emit()
            return

        all_clips: list[str] = []
        total = len(self._videos)

        for i, info in enumerate(self._videos):
            self.progress.emit(
                i, total,
                f"[{i+1}/{total}] {os.path.basename(info.file_path)} "
                f"— {len(info.annotations)} annotation(s)"
            )
            try:
                clips = slice_all_annotations(info, self._out, progress_cb=None)
                all_clips.extend(clips)
                self.video_done.emit(info.file_path, len(clips))
            except Exception as e:
                self.error.emit(f"Skip {info.filename}: {e}")

        self.progress.emit(total, total, "Batch slicing complete.")
        self.clips_created.emit(all_clips)
        self.finished.emit()


# ──────────────────────────────────────────────
# Fragmentation worker
# ──────────────────────────────────────────────

class FragmentationWorker(BaseWorker):
    """Fragments clip files into fixed-size windows."""

    windows_created = Signal(list)  # list[str]

    def __init__(self, clips: list[str], output_root: str,
                 window_sec: float = 3.0, overlap_sec: float = 1.0,
                 parent=None):
        super().__init__(parent)
        self._clips   = clips
        self._out     = output_root
        self._win     = window_sec
        self._overlap = overlap_sec

    def run(self):
        try:
            windows = fragment_all_clips(
                self._clips, self._out,
                self._win, self._overlap,
                progress_cb=lambda c, t, m: self.progress.emit(c, t, m),
            )
            self.windows_created.emit(windows)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────────────────────────
# Skeleton extraction worker
# ──────────────────────────────────────────────

class SkeletonWorker(BaseWorker):
    """Extracts skeleton keypoints for an entire video."""

    skeleton_done = Signal(str, list)   # (video_path, list[SkeletonFrame])

    def __init__(self, video_path: str, skip_frames: int = 1, parent=None):
        super().__init__(parent)
        self._path   = video_path
        self._skip   = skip_frames

    def run(self):
        if not is_mediapipe_available():
            self.error.emit(
                "Ultralytics (YOLOv8) is not installed.\n"
                "Run: pip install ultralytics"
            )
            return
        try:
            extractor = SkeletonExtractor(model_complexity=1)
            frames = extractor.process_video(
                self._path,
                progress_cb=lambda c, t, m: self.progress.emit(c, t, m),
                skip_frames=self._skip,
            )
            # Auto-save JSON sidecar
            json_path = SkeletonExtractor.json_path_for_video(self._path)
            SkeletonExtractor.save_json(frames, json_path)
            extractor.close()
            self.skeleton_done.emit(self._path, frames)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────────────────────────
# Batch skeleton worker (multiple videos)
# ──────────────────────────────────────────────

class BatchSkeletonWorker(BaseWorker):
    """Extracts skeletons for a list of video paths."""

    video_done = Signal(str, list)  # (video_path, frames)

    def __init__(self, video_paths: list[str], skip_frames: int = 2, parent=None):
        super().__init__(parent)
        self._paths = video_paths
        self._skip  = skip_frames

    def run(self):
        if not is_mediapipe_available():
            self.error.emit(
                "Ultralytics (YOLOv8) not installed. "
                "Run: pip install ultralytics"
            )
            return

        extractor = SkeletonExtractor(model_complexity=1)
        for i, path in enumerate(self._paths):
            import os
            self.progress.emit(i, len(self._paths),
                               f"Processing {os.path.basename(path)}")
            try:
                frames = extractor.process_video(path, skip_frames=self._skip)
                json_path = SkeletonExtractor.json_path_for_video(path)
                SkeletonExtractor.save_json(frames, json_path)
                self.video_done.emit(path, frames)
            except Exception as e:
                self.error.emit(f"Error in {path}: {e}")

        extractor.close()
        self.finished.emit()
