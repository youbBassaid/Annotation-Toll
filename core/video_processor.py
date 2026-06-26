"""
core/video_processor.py
=======================
Video slicing, clip fragmentation, and related processing utilities.
All heavy work runs in worker threads — this module is Qt-free and
uses only OpenCV + standard library so it can be unit-tested standalone.
"""

from __future__ import annotations
import os
import math
from typing import Callable, Optional

import cv2

from core.models import VideoInfo, Annotation


# ──────────────────────────────────────────────
# Progress callback type alias
# ──────────────────────────────────────────────
ProgressCB = Callable[[int, int, str], None]   # (current, total, message)


# ──────────────────────────────────────────────
# Video metadata extraction
# ──────────────────────────────────────────────

def extract_video_metadata(video_path: str) -> dict:
    """Return basic metadata dict from a video file using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    try:
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps    = cap.get(cv2.CAP_PROP_FPS)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frames / fps if fps > 0 else 0.0
    finally:
        cap.release()

    stem = os.path.splitext(os.path.basename(video_path))[0]
    return {
        "file_path":   video_path,
        "video_id":    stem,
        "keyword":     stem.replace("_", " "),
        "width":       width,
        "height":      height,
        "fps":         round(fps, 2),
        "frame_count": frames,
        "duration":    round(duration, 3),
    }


# ──────────────────────────────────────────────
# Clip extraction
# ──────────────────────────────────────────────

def slice_annotation_clip(
    video_path: str,
    annotation: Annotation,
    output_path: str,
    progress_cb: Optional[ProgressCB] = None,
) -> str:
    """
    Cut a single annotation segment from a video and write to output_path.
    Returns the output path on success, raises on failure.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")

    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    start_frame = int(annotation.start_time * fps)
    end_frame   = int(annotation.end_time   * fps)
    total_frames = max(1, end_frame - start_frame)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    written = 0
    for frame_idx in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)
        written += 1
        if progress_cb and frame_idx % 30 == 0:
            progress_cb(frame_idx, total_frames,
                        f"Slicing frame {frame_idx}/{total_frames}")

    cap.release()
    writer.release()

    if written == 0:
        raise RuntimeError(f"No frames written for annotation {annotation.annotation_id}")

    return output_path


def slice_all_annotations(
    video_info: VideoInfo,
    output_root: str,
    progress_cb: Optional[ProgressCB] = None,
) -> list[str]:
    """
    Slice all annotations from video_info into labelled sub-folders.
    Returns list of created clip paths.
    """
    clips = []
    stem  = os.path.splitext(os.path.basename(video_info.file_path))[0]

    for idx, ann in enumerate(video_info.annotations, start=1):
        class_dir   = os.path.join(output_root, ann.action_class)
        clip_name   = f"{stem}_clip_{idx:03d}.mp4"
        output_path = os.path.join(class_dir, clip_name)

        if progress_cb:
            progress_cb(idx - 1, len(video_info.annotations),
                        f"Slicing clip {idx}/{len(video_info.annotations)}: {clip_name}")

        slice_annotation_clip(video_info.file_path, ann, output_path, progress_cb)
        clips.append(output_path)

    return clips


# ──────────────────────────────────────────────
# Window fragmentation
# ──────────────────────────────────────────────

def fragment_clip_into_windows(
    clip_path: str,
    output_dir: str,
    window_sec: float = 3.0,
    overlap_sec: float = 1.0,
    progress_cb: Optional[ProgressCB] = None,
) -> list[str]:
    """
    Split a clip into fixed-length windows with overlap.

    Parameters
    ----------
    clip_path   : Path to the input clip (.mp4)
    output_dir  : Directory to write window files
    window_sec  : Window duration in seconds (default 3 s)
    overlap_sec : Overlap between consecutive windows (default 1 s)
    progress_cb : Optional progress callback

    Returns
    -------
    List of created window file paths.
    """
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open clip: {clip_path}")

    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    step_sec   = window_sec - overlap_sec
    win_frames = int(window_sec * fps)
    step_frames = int(step_sec * fps)
    if step_frames <= 0:
        step_frames = 1

    stem = os.path.splitext(os.path.basename(clip_path))[0]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    os.makedirs(output_dir, exist_ok=True)
    created: list[str] = []

    starts = list(range(0, max(1, total_frames - win_frames + 1), step_frames))
    if not starts:
        starts = [0]

    for win_idx, start in enumerate(starts, start=1):
        end = min(start + win_frames, total_frames)
        out_name = f"{stem}_window{win_idx:03d}.mp4"
        out_path = os.path.join(output_dir, out_name)

        cap = cv2.VideoCapture(clip_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

        for _ in range(end - start):
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)

        cap.release()
        writer.release()
        created.append(out_path)

        if progress_cb:
            progress_cb(win_idx, len(starts),
                        f"Window {win_idx}/{len(starts)}: {out_name}")

    return created


def fragment_all_clips(
    clips: list[str],
    output_root: str,
    window_sec: float = 3.0,
    overlap_sec: float = 1.0,
    progress_cb: Optional[ProgressCB] = None,
) -> list[str]:
    """
    Fragment every clip in the list into windows.

    Output layout mirrors the slicing layout — windows are pooled by
    action class instead of one folder per clip:

        output_root/<action_class>/<clip_stem>_windowNNN.mp4

    The action class is inferred from each clip's immediate parent
    folder name (slicing writes clips to
    `output_root/<action_class>/<clip>.mp4`). When a clip has no parent
    folder name, windows fall back to `output_root/unsorted/`.
    """
    all_windows: list[str] = []
    for i, clip in enumerate(clips):
        class_name = os.path.basename(os.path.dirname(clip)) or "unsorted"
        out_dir    = os.path.join(output_root, class_name)
        if progress_cb:
            progress_cb(i, len(clips),
                        f"Fragmenting {os.path.basename(clip)} → {class_name}/")
        windows = fragment_clip_into_windows(
            clip, out_dir, window_sec, overlap_sec, progress_cb
        )
        all_windows.extend(windows)
    return all_windows


# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

def read_frame_at(video_path: str, frame_idx: int):
    """Read a single frame (BGR numpy array) from a video by frame index."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def read_frame_at_time(video_path: str, timestamp: float):
    """Read frame closest to a given timestamp (seconds)."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_idx = int(timestamp * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None
