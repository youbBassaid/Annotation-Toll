"""
core/skeleton_extractor.py
==========================
Skeleton extraction using YOLOv8-Pose (Ultralytics).

WHY YOLOv8-POSE?
----------------
Migrated from MediaPipe Pose because the latter has been unstable on
recent Windows + Python combinations (legacy `solutions.pose` API
breakage, native binding errors). YOLOv8-Pose:

  • One pip install: `pip install ultralytics`
  • Auto-downloads the model on first use (~6 MB for nano)
  • CPU-runnable, no GPU required
  • 17 anatomical keypoints in COCO format
  • Robust on Windows — no DLL drama

Trade-off vs MediaPipe: 17 keypoints instead of 33 — we lose per-finger
landmarks (pinky/index/thumb) and inner/outer eye points. All major
joints relevant to the autism behaviour categories (head, shoulders,
elbows, wrists, hips, knees, ankles) are still covered.
"""

from __future__ import annotations
import json
import os
from typing import Optional, Callable

import cv2
import numpy as np

from core.models import SkeletonFrame


# Ultralytics import — optional so the rest of the app still loads
# if it isn't installed.
try:
    from ultralytics import YOLO            # noqa: F401
    _YOLO_AVAILABLE = True
except ImportError as e:
    print(f"Ultralytics YOLO unavailable: {e}")
    _YOLO_AVAILABLE = False
    YOLO = None  # type: ignore


# ──────────────────────────────────────────────
# COCO 17 keypoint layout
# ──────────────────────────────────────────────

LANDMARK_NAMES = [
    "nose",            # 0
    "left_eye",        # 1
    "right_eye",       # 2
    "left_ear",        # 3
    "right_ear",       # 4
    "left_shoulder",   # 5
    "right_shoulder",  # 6
    "left_elbow",      # 7
    "right_elbow",     # 8
    "left_wrist",      # 9
    "right_wrist",     # 10
    "left_hip",        # 11
    "right_hip",       # 12
    "left_knee",       # 13
    "right_knee",      # 14
    "left_ankle",      # 15
    "right_ankle",     # 16
]

# Bones to draw between keypoints (COCO 17 skeleton)
SKELETON_CONNECTIONS = [
    # face
    (0, 1), (0, 2), (1, 3), (2, 4),
    # arms
    (5, 7), (7, 9),       # left
    (6, 8), (8, 10),      # right
    # torso
    (5, 6), (5, 11), (6, 12), (11, 12),
    # legs
    (11, 13), (13, 15),   # left
    (12, 14), (14, 16),   # right
]

# Indices < 5 are face/head landmarks (nose, eyes, ears)
_FACE_INDICES = {0, 1, 2, 3, 4}

JOINT_COLOR = (99, 235, 179)    # mint green  (BGR)
BONE_COLOR  = (99, 179, 237)    # steel blue  (BGR)
FACE_COLOR  = (200, 200, 100)   # yellow-ish  (BGR)


# ──────────────────────────────────────────────
# Core extractor class
# ──────────────────────────────────────────────

class SkeletonExtractor:
    """
    Wraps YOLOv8-Pose for video-level skeleton extraction.

    Usage::

        extractor = SkeletonExtractor()
        frames = extractor.process_video("clip.mp4", progress_cb=cb)
        extractor.save_json(frames, "clip_skeleton.json")

    `model_complexity` is mapped to a YOLO size for legacy compatibility
    with the previous MediaPipe-based extractor:
        0 → yolov8n-pose.pt   (nano,  fastest, smallest model)
        1 → yolov8s-pose.pt   (small, default)
        2 → yolov8m-pose.pt   (medium, slower / more accurate)
    """

    _SIZE_MAP = {0: "n", 1: "s", 2: "m", 3: "l", 4: "x"}

    def __init__(self, model_complexity: int = 1,
                 min_detection_confidence: float = 0.5):
        if not _YOLO_AVAILABLE:
            raise ImportError(
                "ultralytics is not installed. Run: pip install ultralytics"
            )
        size = self._SIZE_MAP.get(model_complexity, "n")
        self._model_name = f"yolov8{size}-pose.pt"
        self._min_conf   = float(min_detection_confidence)
        self._model: Optional["YOLO"] = None  # lazy

    def _get_model(self):
        if self._model is None:
            # Ultralytics auto-downloads the weights on first use.
            self._model = YOLO(self._model_name)
        return self._model

    def process_frame(self, frame_bgr: np.ndarray, frame_id: int = 0,
                      timestamp: float = 0.0) -> Optional[SkeletonFrame]:
        """
        Extract skeleton from a single BGR frame.
        Returns the most-confident detection as a SkeletonFrame, or
        None if no person is detected.
        """
        model = self._get_model()
        results = model.predict(
            frame_bgr,
            verbose=False,
            conf=self._min_conf,
            imgsz=640,
        )
        if not results:
            return None
        r = results[0]
        if r.keypoints is None or r.keypoints.xy is None:
            return None
        xy = r.keypoints.xy
        if xy.shape[0] == 0:
            return None

        # Pick the highest-confidence person
        person_idx = 0
        if r.boxes is not None and r.boxes.conf is not None and len(r.boxes.conf) > 0:
            person_idx = int(r.boxes.conf.argmax().item())

        kpts_xy   = xy[person_idx].cpu().numpy()              # (17, 2)
        if r.keypoints.conf is not None:
            kpts_conf = r.keypoints.conf[person_idx].cpu().numpy()  # (17,)
        else:
            kpts_conf = np.ones(kpts_xy.shape[0], dtype=np.float32)

        kps: list[float] = []
        vis: list[float] = []
        for (x, y), c in zip(kpts_xy, kpts_conf):
            kps.extend([float(x), float(y)])
            vis.append(float(c))

        return SkeletonFrame(
            frame_id=frame_id,
            timestamp=timestamp,
            keypoints=kps,
            visibility=vis,
        )

    def draw_skeleton(self, frame_bgr: np.ndarray,
                      skeleton: Optional[SkeletonFrame]) -> np.ndarray:
        """Draw skeleton overlay on a copy of frame_bgr."""
        out = frame_bgr.copy()
        if skeleton is None or not skeleton.keypoints:
            return out

        kps = skeleton.keypoints
        vis = skeleton.visibility

        points = []
        for i in range(0, len(kps), 2):
            points.append((int(kps[i]), int(kps[i + 1])))

        # Bones
        for (a, b) in SKELETON_CONNECTIONS:
            if a >= len(points) or b >= len(points):
                continue
            va = vis[a] if a < len(vis) else 0
            vb = vis[b] if b < len(vis) else 0
            if va < 0.3 or vb < 0.3:
                continue
            color = FACE_COLOR if (a in _FACE_INDICES and b in _FACE_INDICES) else BONE_COLOR
            cv2.line(out, points[a], points[b], color, 2, cv2.LINE_AA)

        # Joints
        for i, (px, py) in enumerate(points):
            v = vis[i] if i < len(vis) else 0
            if v < 0.3:
                continue
            radius = 3 if i in _FACE_INDICES else 5
            cv2.circle(out, (px, py), radius, JOINT_COLOR, -1, cv2.LINE_AA)
            cv2.circle(out, (px, py), radius + 1, (0, 0, 0), 1, cv2.LINE_AA)

        return out

    def process_video(
        self,
        video_path: str,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        skip_frames: int = 1,
    ) -> list[SkeletonFrame]:
        """
        Process an entire video file.
        skip_frames=N processes every N-th frame for speed.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise IOError(f"Cannot open: {video_path}")

        fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        results: list[SkeletonFrame] = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % skip_frames == 0:
                ts = frame_idx / fps
                sf = self.process_frame(frame, frame_id=frame_idx, timestamp=ts)
                if sf:
                    results.append(sf)
                if progress_cb and frame_idx % (skip_frames * 10) == 0:
                    progress_cb(frame_idx, total,
                                f"Extracting skeletons {frame_idx}/{total}")
            frame_idx += 1

        cap.release()
        return results

    def close(self):
        # YOLO has no explicit close; drop the reference so the next call
        # would re-instantiate cleanly.
        self._model = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ── JSON I/O ──────────────────────────────────────────────────────

    @staticmethod
    def save_json(frames: list[SkeletonFrame], json_path: str) -> None:
        """Save a list of SkeletonFrame to a JSON file."""
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        data = [f.to_dict() for f in frames]
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    @staticmethod
    def load_json(json_path: str) -> list[SkeletonFrame]:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [SkeletonFrame.from_dict(d) for d in data]

    @staticmethod
    def json_path_for_video(video_path: str) -> str:
        base, _ = os.path.splitext(video_path)
        return base + "_skeleton.json"


# ──────────────────────────────────────────────
# Availability helpers (kept named like the legacy MediaPipe API so
# call sites elsewhere in the app don't have to change).
# ──────────────────────────────────────────────

def is_skeleton_model_available() -> bool:
    return _YOLO_AVAILABLE


def is_mediapipe_available() -> bool:
    """Backward-compat alias — now reports YOLOv8 (ultralytics) availability."""
    return _YOLO_AVAILABLE
