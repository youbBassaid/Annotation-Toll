"""
core/annotation_io.py
=====================
Load / save video annotations to the canonical XML format.

XML schema (canonical — exactly the dataset format)
---------------------------------------------------
<?xml version="1.0" encoding="utf-8"?>
<video id="..." keyword="...">
   <height>360</height>
   <width>480</width>
   <fps>29.97</fps>
   <frames>1365</frames>
   <duration>46s</duration>
   <behaviours count="2" id="b_Set_01">
      <behaviour id="b_01">
         <time>18:24</time>
         <bodypart>hand</bodypart>
         <category>armflapping</category>
         <intensity>high</intensity>
         <modality>video</modality>
      </behaviour>
   </behaviours>
</video>

Time format
-----------
The dataset uses two interchangeable encodings inside a single <time>
element. Both encode a START:END range:

  1. Plain seconds, 2-digit zero-padded:
        <time>18:24</time>     →  start=18s, end=24s
        <time>04:10</time>     →  start=4s,  end=10s

  2. Packed MMSS, 4-digit zero-padded (used in larger videos):
        <time>0001:0010</time> →  start=1s,   end=10s   (00:01 → 00:10)
        <time>0146:0159</time> →  start=106s, end=119s  (01:46 → 01:59)
        <time>0206:0211</time> →  start=126s, end=131s  (02:06 → 02:11)

The reader auto-detects the encoding by digit-width: a 4-digit numeric
value whose last two digits are < 60 is parsed as MMSS, otherwise as
plain seconds.

For backward compatibility the reader also accepts the legacy explicit
ranges 'MM:SS→MM:SS' / 'MM:SS->MM:SS' and the sibling
<start_sec>/<end_sec> elements.
"""

from __future__ import annotations
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

from core.models import VideoInfo, Annotation, _seconds_to_timecode


# Default behaviour-window duration when the canonical XML only carries
# a start time. Matches the windowing tab default.
DEFAULT_ANNOTATION_DURATION = 3.0   # seconds


# ──────────────────────────────────────────────
# Save
# ──────────────────────────────────────────────

def save_annotations_xml(video_info: VideoInfo, xml_path: str) -> None:
    """Serialise VideoInfo (including annotations) to the canonical XML format."""

    root = ET.Element("video", attrib={
        "id":      video_info.video_id,
        "keyword": video_info.keyword,
    })

    _text(root, "height",   str(video_info.height))
    _text(root, "width",    str(video_info.width))
    _text(root, "fps",      str(video_info.fps))
    _text(root, "frames",   str(video_info.frame_count))
    _text(root, "duration", _format_duration_seconds(video_info.duration))

    behaviours = ET.SubElement(root, "behaviours", attrib={
        "count": str(len(video_info.annotations)),
        "id":    "b_Set_01",
    })

    for idx, ann in enumerate(video_info.annotations, start=1):
        beh = ET.SubElement(behaviours, "behaviour", attrib={
            "id": f"b_{idx:02d}",
        })
        _text(beh, "time",      _format_time_range(ann.start_time, ann.end_time))
        _text(beh, "bodypart",  ann.body_part)
        _text(beh, "category",  ann.action_class)
        _text(beh, "intensity", ann.intensity)
        _text(beh, "modality",  ann.modality)

    os.makedirs(os.path.dirname(xml_path) or ".", exist_ok=True)

    raw_xml = ET.tostring(root, encoding="unicode")
    pretty  = minidom.parseString(raw_xml).toprettyxml(
        indent="   ", encoding="utf-8"
    )
    with open(xml_path, "wb") as fh:
        fh.write(pretty)


# ──────────────────────────────────────────────
# Load
# ──────────────────────────────────────────────

def load_annotations_xml(xml_path: str) -> list[Annotation]:
    """
    Parse an XML file in the canonical format and return a list of
    Annotation objects.

    Time resolution priority (per behaviour):
      1. <start_sec>/<end_sec>          (legacy, exact seconds)
      2. <time> as "MM:SS→MM:SS"        (legacy explicit range)
      3. <time> as "START_SEC:END_SEC"  (canonical — both in seconds)
      4. <time> as a single timecode    (start only; end defaults to
                                         start + DEFAULT_ANNOTATION_DURATION)
    """
    if not os.path.exists(xml_path):
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return []

    annotations: list[Annotation] = []
    behaviours = root.find("behaviours")
    if behaviours is None:
        return []

    for beh in behaviours.findall("behaviour"):
        # Time resolution
        start_sec_str = _find_text(beh, "start_sec", "")
        end_sec_str   = _find_text(beh, "end_sec",   "")
        if start_sec_str and end_sec_str:
            start_t = float(start_sec_str)
            end_t   = float(end_sec_str)
        else:
            time_text = _find_text(beh, "time", "")
            start_t, end_t_opt = _parse_time_field(time_text)
            end_t = (end_t_opt
                     if end_t_opt is not None
                     else start_t + DEFAULT_ANNOTATION_DURATION)

        ann = Annotation(
            annotation_id=_find_text(beh, "ann_id",
                                     beh.get("id", str(len(annotations)))),
            start_time=start_t,
            end_time=end_t,
            action_class=_find_text(beh, "category",  "neutral"),
            body_part=_find_text(beh, "bodypart",  "full_body"),
            intensity=_find_text(beh, "intensity",  "medium"),
            modality=_find_text(beh, "modality",   "video"),
            notes=_find_text(beh, "notes",     ""),
        )
        annotations.append(ann)

    return annotations


def load_video_info_from_xml(xml_path: str, video_file_path: str) -> VideoInfo | None:
    """Load full VideoInfo (including metadata) from XML."""
    if not os.path.exists(xml_path):
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    info = VideoInfo(
        file_path=video_file_path,
        video_id=root.get("id", ""),
        keyword=root.get("keyword", ""),
        height=int(_find_text(root, "height",   "0")),
        width=int(_find_text(root, "width",    "0")),
        fps=float(_find_text(root, "fps",      "0")),
        frame_count=int(_find_text(root, "frames",  "0")),
    )
    info.annotations = load_annotations_xml(xml_path)
    return info


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _find_text(parent: ET.Element, tag: str, default: str = "") -> str:
    el = parent.find(tag)
    return el.text.strip() if (el is not None and el.text) else default


def _format_duration_seconds(seconds: float) -> str:
    """Render a duration in the canonical 'Ns' form (e.g. '16s', '90s')."""
    return f"{int(round(seconds))}s"


def _timecode_to_seconds(tc: str) -> float:
    """
    Parse a timecode string into seconds.
    Accepts: 'SS', 'MM:SS', 'HH:MM:SS', and tolerates fractional seconds.
    Returns 0.0 on failure.
    """
    if not tc:
        return 0.0
    tc = tc.strip()
    parts = tc.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    return 0.0


def _format_time_range(start_sec: float, end_sec: float) -> str:
    """
    Render a behaviour time as 'START:END' in whole seconds, zero-padded
    to two digits each (matches the canonical dataset format).
    Example: (18.0, 24.0) -> '18:24'
    """
    return f"{int(round(start_sec)):02d}:{int(round(end_sec)):02d}"


def _parse_one_value(s: str) -> float:
    """
    Parse a single <time> sub-value (one side of the START:END pair).

    Detection:
      • All digits, exactly 4 chars, last two < 60   → packed MMSS
            '0146' → 1*60 + 46 = 106s
      • All digits, exactly 6 chars, mid two < 60
        and last two < 60                            → packed HHMMSS
            '010146' → 1*3600 + 1*60 + 46 = 3706s
      • Otherwise                                    → plain seconds (float)
    Returns 0.0 on failure.
    """
    s = s.strip()
    if not s:
        return 0.0

    if s.isdigit():
        if len(s) == 4:
            mm = int(s[:2]); ss = int(s[2:])
            if ss < 60:
                return mm * 60 + ss
        elif len(s) == 6:
            hh = int(s[:2]); mm = int(s[2:4]); ss = int(s[4:])
            if mm < 60 and ss < 60:
                return hh * 3600 + mm * 60 + ss

    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_time_field(text: str) -> tuple[float, float | None]:
    """
    Parse a <time> element value as a START:END range.

    Forms (all return start, end in seconds):
      • 'SS:EE'         plain-seconds, 2-digit zero-padded
            '18:24' → (18.0, 24.0)
      • 'MMSS:MMSS'     packed MMSS, 4-digit zero-padded
            '0206:0211' → (126.0, 131.0)
      • 'MMSSss:...'    packed HHMMSS, 6-digit
            '010100:010130' → (3660.0, 3690.0)
      • 'MM:SS→MM:SS' / 'MM:SS->MM:SS'   legacy explicit-range
      • Single value (no range) → (start, None)

    If the first parsed value is greater than the second (impossible for
    a real range), falls back to minutes:seconds interpretation of the
    raw string and returns end=None.
    """
    if not text:
        return 0.0, None
    text = text.strip()

    # Legacy explicit-range separators
    for sep in ("→", "->"):
        if sep in text:
            left, right = text.split(sep, 1)
            return _timecode_to_seconds(left), _timecode_to_seconds(right)

    parts = text.split(":")
    if len(parts) == 2:
        a = _parse_one_value(parts[0])
        b = _parse_one_value(parts[1])
        if a <= b:
            return a, b
        # Backstop — looks like a single MM:SS timecode that got
        # misread as a range. Re-parse as minutes:seconds.
        try:
            return float(parts[0]) * 60 + float(parts[1]), None
        except ValueError:
            return 0.0, None

    if len(parts) == 3:
        try:
            return (int(parts[0]) * 3600 + int(parts[1]) * 60
                    + float(parts[2]), None)
        except ValueError:
            return 0.0, None

    try:
        return float(text), None
    except ValueError:
        return 0.0, None


def xml_path_for_video(video_path: str) -> str:
    """Return the sidecar XML path for a given video path."""
    base, _ = os.path.splitext(video_path)
    return base + "_annotations.xml"


def find_annotation_xml(annotations_folder: str, video_path: str) -> str | None:
    """
    Look up an XML annotation file inside `annotations_folder` that matches
    the given video file by stem.

    Match order:
      1. <stem>_annotations.xml
      2. <stem>.xml
      3. case-insensitive scan, with optional trailing "_annotations"

    Returns the matched path or None.
    """
    if not annotations_folder or not os.path.isdir(annotations_folder):
        return None

    stem = os.path.splitext(os.path.basename(video_path))[0]

    for cand in (f"{stem}_annotations.xml", f"{stem}.xml"):
        p = os.path.join(annotations_folder, cand)
        if os.path.exists(p):
            return p

    try:
        stem_lower = stem.lower()
        for entry in os.listdir(annotations_folder):
            if not entry.lower().endswith(".xml"):
                continue
            entry_stem = os.path.splitext(entry)[0]
            if entry_stem.lower().endswith("_annotations"):
                entry_stem = entry_stem[: -len("_annotations")]
            if entry_stem.lower() == stem_lower:
                return os.path.join(annotations_folder, entry)
    except OSError:
        pass

    return None
