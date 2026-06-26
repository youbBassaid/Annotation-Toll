"""
core/models.py
==============
Pure-data models (dataclasses) for annotations and video metadata.
No Qt dependencies here — keeps processing logic portable.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import uuid


# ──────────────────────────────────────────────
# Behaviour / Annotation model
# ──────────────────────────────────────────────

ACTION_CLASSES = [
    "arm_flapping",
    "hand_flapping",
    "spinning",
    "rocking",
    "headbanging",
    "mouthing",
    "toe_walking",
    "eye_contact_avoidance",
    "repetitive_movement",
    "self_injurious",
    "neutral",
    "other",
]

BODY_PARTS = [
    "head",
    "arms",
    "hands",
    "legs",
    "full_body",
    "torso",
]

INTENSITY_LEVELS = ["low", "medium", "high"]
MODALITIES = ["video", "audio", "video+audio"]


@dataclass
class Annotation:
    """Represents a single labelled behaviour segment within a video."""

    annotation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    start_time: float = 0.0        # seconds
    end_time: float = 0.0          # seconds
    action_class: str = "neutral"
    body_part: str = "full_body"
    intensity: str = "medium"
    modality: str = "video"
    notes: str = ""

    # ── helpers ──────────────────────────────────────────────────────────
    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)

    def start_timecode(self) -> str:
        """Return start time as MM:SS string."""
        return _seconds_to_timecode(self.start_time)

    def end_timecode(self) -> str:
        return _seconds_to_timecode(self.end_time)

    def to_dict(self) -> dict:
        return {
            "annotation_id": self.annotation_id,
            "start_time":    self.start_time,
            "end_time":      self.end_time,
            "action_class":  self.action_class,
            "body_part":     self.body_part,
            "intensity":     self.intensity,
            "modality":      self.modality,
            "notes":         self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(
            annotation_id=d.get("annotation_id", str(uuid.uuid4())[:8]),
            start_time=float(d.get("start_time", 0)),
            end_time=float(d.get("end_time", 0)),
            action_class=d.get("action_class", "neutral"),
            body_part=d.get("body_part", "full_body"),
            intensity=d.get("intensity", "medium"),
            modality=d.get("modality", "video"),
            notes=d.get("notes", ""),
        )


# ──────────────────────────────────────────────
# Video metadata model
# ──────────────────────────────────────────────

@dataclass
class VideoInfo:
    """Metadata for a single video file."""

    file_path: str = ""
    video_id: str = ""
    keyword: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frame_count: int = 0
    duration: float = 0.0          # seconds
    annotations: List[Annotation] = field(default_factory=list)

    @property
    def duration_label(self) -> str:
        secs = int(self.duration)
        mins = secs // 60
        secs = secs % 60
        return f"{mins:02d}:{secs:02d}s" if mins else f"{secs}s"

    @property
    def filename(self) -> str:
        import os
        return os.path.basename(self.file_path)

    def to_dict(self) -> dict:
        return {
            "file_path":   self.file_path,
            "video_id":    self.video_id,
            "keyword":     self.keyword,
            "width":       self.width,
            "height":      self.height,
            "fps":         self.fps,
            "frame_count": self.frame_count,
            "duration":    self.duration,
            "annotations": [a.to_dict() for a in self.annotations],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VideoInfo":
        obj = cls(
            file_path=d.get("file_path", ""),
            video_id=d.get("video_id", ""),
            keyword=d.get("keyword", ""),
            width=d.get("width", 0),
            height=d.get("height", 0),
            fps=d.get("fps", 0.0),
            frame_count=d.get("frame_count", 0),
            duration=d.get("duration", 0.0),
        )
        obj.annotations = [Annotation.from_dict(a) for a in d.get("annotations", [])]
        return obj


# ──────────────────────────────────────────────
# Skeleton keypoint model
# ──────────────────────────────────────────────

@dataclass
class SkeletonFrame:
    """Keypoints for a single frame (MediaPipe Pose — 33 landmarks)."""

    frame_id: int = 0
    keypoints: List[float] = field(default_factory=list)   # flat [x,y, x,y, ...]
    visibility: List[float] = field(default_factory=list)  # per-landmark visibility
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "frame_id":   self.frame_id,
            "timestamp":  self.timestamp,
            "keypoints":  self.keypoints,
            "visibility": self.visibility,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkeletonFrame":
        return cls(
            frame_id=d.get("frame_id", 0),
            timestamp=d.get("timestamp", 0.0),
            keypoints=d.get("keypoints", []),
            visibility=d.get("visibility", []),
        )


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _seconds_to_timecode(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
