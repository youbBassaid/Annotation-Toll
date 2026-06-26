# Autism Behavior Annotation Tool

A production-ready PySide6 desktop application for preprocessing autism-behavior video datasets.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MainWindow (Qt)                             │
│  ┌──────────────┐  ┌─────────────────────┐  ┌─────────────────────┐│
│  │ VideoLibrary  │  │    VideoPlayer      │  │  AnnotationPanel   ││
│  │  (sidebar)   │  │  (OpenCV+QTimer)    │  │  (create/edit/save)││
│  └──────────────┘  ├─────────────────────┤  └─────────────────────┘│
│                    │   ProcessingTab     │                           │
│                    │ ┌────┬──────┬──────┐│                           │
│                    │ │Slic│Wind  │Skel  ││                           │
│                    │ │ing │owing │eton  ││                           │
│                    │ └────┴──────┴──────┘│                           │
│                    └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
         │ signals                    │ QThread workers
         ▼                            ▼
┌────────────────────┐    ┌──────────────────────────────────┐
│  core/models.py    │    │  FolderScanWorker                │
│  (VideoInfo,       │    │  SlicingWorker                   │
│   Annotation,      │    │  FragmentationWorker             │
│   SkeletonFrame)   │    │  SkeletonWorker / BatchWorker    │
└────────────────────┘    └──────────────────────────────────┘
         │                            │
         ▼                            ▼
┌────────────────────┐    ┌──────────────────────────────────┐
│ annotation_io.py   │    │  video_processor.py              │
│ (XML read/write)   │    │  skeleton_extractor.py           │
└────────────────────┘    └──────────────────────────────────┘
```

### Why MediaPipe Pose?

| Model      | Accuracy | Speed  | Install  | Qt Compat |
|------------|----------|--------|----------|-----------|
| OpenPose   | ★★★★★   | ★★★    | ★★ (C++) | ★★        |
| MMPose     | ★★★★★   | ★★★    | ★★       | ★★        |
| MoveNet    | ★★★★    | ★★★★★  | ★★★★     | ★★★★      |
| **MediaPipe** | ★★★★ | ★★★★★ | **★★★★★** | **★★★★★** |

**MediaPipe Pose** is selected because:
- `pip install mediapipe` — zero system dependencies
- Real-time on CPU (30+ FPS on a mid-range laptop)
- 33 anatomically meaningful landmarks with visibility scores
- Covers all joints relevant for autism movement analysis (wrists, elbows, shoulders, hips, knees, ankles + face)
- Cross-platform (Windows, macOS, Linux)
- Native NumPy / OpenCV integration

---

## Project Structure

```
autism_annotation_tool/
├── main.py                   # Entry point
├── requirements.txt
├── README.md
│
├── core/
│   ├── __init__.py
│   ├── models.py             # Data classes (VideoInfo, Annotation, SkeletonFrame)
│   ├── annotation_io.py      # XML read / write
│   ├── video_processor.py    # Slicing, fragmentation, metadata extraction
│   ├── skeleton_extractor.py # MediaPipe Pose wrapper
│   └── workers.py            # QThread workers for all heavy processing
│
└── ui/
    ├── __init__.py
    ├── main_window.py        # Top-level window
    ├── video_player.py       # OpenCV-based player widget
    ├── video_library.py      # Left sidebar (video list)
    ├── annotation_panel.py   # Right panel (annotation editor)
    └── processing_tab.py     # Processing tools (slice/window/skeleton)
```

---

## Installation

### 1. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install PySide6 opencv-python mediapipe numpy
```

### 3. Run the application

```bash
python main.py
```

---

## Usage Guide

### Loading Videos
1. Click **📂 Open Folder** (toolbar or File menu) to load an entire dataset folder
2. Or use **🎞 Load Single Video** for a quick single-file load
3. Videos appear in the left **Video Library** panel
4. Click any video to load it into the player

### Player Controls
| Key / Button | Action |
|---|---|
| `Space` | Play / Pause |
| `←` / `→` | Previous / Next frame |
| `Home` / `End` | Jump to start / end |
| Seek slider | Drag to any position |
| Speed combo | 0.25× → 4× playback |
| 🦴 Skeleton button | Toggle skeleton overlay (requires extraction) |

### Creating Annotations
1. Play/seek to the **start** of a behaviour
2. Click **Mark Start**
3. Seek to the **end** of the behaviour
4. Click **Mark End**
5. Choose Action Class, Body Part, Intensity, Modality
6. Add optional notes
7. Click **＋ Add Annotation**
8. Annotations auto-save to `<video>_annotations.xml`

### Video Slicing (Processing Tab → 🔪 Slicing)
1. With a video loaded and annotated, open **Processing → Slicing**
2. Choose an output directory (default next to the video)
3. Click **▶ Slice Annotations → Clips**
4. Clips appear in `dataset_processed/<action_class>/video_clip_001.mp4`

### Window Fragmentation (Processing Tab → 🪟 Windowing)
1. Set window size (default 3 s) and overlap (default 1 s)
2. Select input folder (auto-filled from slicing step)
3. Click **▶ Fragment Clips → Windows**

### Skeleton Extraction (Processing Tab → 🦴 Skeleton)
1. With a video loaded, click **🦴 Extract Skeleton (Current Video)**
2. Wait for extraction to complete
3. Keypoints saved as `<video>_skeleton.json`
4. Enable **🦴 Skeleton** button in the player to see overlay

### Skeleton JSON Format

```json
[
  {
    "frame_id": 0,
    "timestamp": 0.0,
    "keypoints": [x0, y0, x1, y1, ..., x32, y32],
    "visibility": [v0, v1, ..., v32]
  }
]
```

### Annotation XML Format

```xml
<?xml version="1.0" encoding="utf-8"?>
<video id="video_name" keyword="Video Name">
   <height>480</height>
   <width>640</width>
   <fps>30.0</fps>
   <frames>900</frames>
   <duration>30s</duration>
   <behaviours count="2" id="b_Set_01">
      <behaviour id="b_01">
         <time>00:05→00:12</time>
         <bodypart>arms</bodypart>
         <category>arm_flapping</category>
         <intensity>high</intensity>
         <modality>video</modality>
         <start_sec>5.0</start_sec>
         <end_sec>12.0</end_sec>
      </behaviour>
   </behaviours>
</video>
```

---

## Output Dataset Structure

After full pipeline processing:

```
dataset_processed/
├── arm_flapping/
│   ├── video1_clip_001.mp4
│   └── video1_clip_001_windows/
│       ├── video1_clip_001_window001.mp4
│       ├── video1_clip_001_window002.mp4
│       └── ...
├── headbanging/
│   └── ...
└── neutral/
    └── ...

# Sidecar files next to originals:
video1_annotations.xml
video1_skeleton.json
```

---

## Optional Improvements

1. **Multi-person tracking** — upgrade to MediaPipe Holistic for face/hand landmarks
2. **Export to COCO JSON** — add an exporter for use with MMPose/detectron2
3. **Clip preview thumbnails** — generate JPG thumbnails in the library panel
4. **Annotation statistics dashboard** — class distribution charts per video
5. **Inter-annotator agreement** — load two XML files and compute Cohen's κ
6. **GPU acceleration** — MediaPipe supports GPU delegates on supported hardware
7. **Auto-labelling** — integrate a pre-trained classifier to suggest action classes
8. **Undo / Redo stack** — QUndoStack for annotation operations
