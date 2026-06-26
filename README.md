# Autism Behavior Annotation Tool

[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/UI-PySide6%20%2F%20Qt6-green)](https://doc.qt.io/qtforpython-6/)
[![ML Framework](https://img.shields.io/badge/ML-MediaPipe%20%2F%20OpenCV-orange)](https://github.com/google-ai-edge/mediapipe)

A production-ready PySide6 desktop application specifically designed for preprocessing autism-behavior video datasets, automating annotation mapping, and pipelines for model training.

---

## 🏗️ Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          MainWindow (Qt)                            │
│  ┌──────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ VideoLibrary  │  │    VideoPlayer      │  │  AnnotationPanel    │ │
│  │  (sidebar)   │  │  (OpenCV+QTimer)    │  │  (create/edit/save) │ │
│  └──────────────┘  ├─────────────────────┤  └─────────────────────┘ │
│                    │   ProcessingTab     │                          │
│                    │ ┌────┬──────┬──────┐│                          │
│                    │ │Slic│Wind  │Skel  ││                          │
│                    │ │ing │owing │eton  ││                          │
│                    │ └────┴──────┴──────┘│                          │
│                    └─────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
         │ signals                            │ QThread workers
         ▼                                    ▼
┌────────────────────┐    ┌──────────────────────────────────┐
│  core/models.py    │    │  FolderScanWorker                │
│  (VideoInfo,       │    │  SlicingWorker                   │
│   Annotation,      │    │  FragmentationWorker             │
│   SkeletonFrame)   │    │  SkeletonWorker / BatchWorker    │
└────────────────────┘    └──────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌────────────────────┐    ┌──────────────────────────────────┐
│ annotation_io.py   │    │  video_processor.py              │
│ (XML read/write)   │    │  skeleton_extractor.py           │
└────────────────────┘    └──────────────────────────────────┘
Why MediaPipe Pose?
Model	Accuracy	Speed	Install	Qt Compat
OpenPose	★★★★★	★★★	★★ (C++)	★★
MMPose	★★★★★	★★★	★★	★★
MoveNet	★★★★	★★★★★	★★★★	★★★★
🚀 MediaPipe	★★★★	★★★★★	★★★★★	★★★★★
MediaPipe Pose is selected for this stack because:

Zero System Dependencies: Simple pip install mediapipe deployment.

CPU Optimized Performance: Real-time extraction (30+ FPS) on standard computer processors.

Rich Keypoint Matrix: 33 anatomically meaningful landmarks mapping coordinates alongside visibility metrics.

Clinical Focus: Captures critical upper/lower limb tracking landmarks vital for kinetic autism movement recognition profiles (wrists, elbows, shoulders, etc.).

Cross-Platform Delivery: Flawless runtime configurations across Windows, macOS, and Linux targets.

📁 Project Structure
Plaintext
autism_annotation_tool/
├── main.py                   # Main execution entry-point
├── requirements.txt          # Framework dependency definitions
├── README.md                 # Project documentation
│
├── core/
│   ├── __init__.py
│   ├── models.py             # Strongly typed core definitions (VideoInfo, Annotation, SkeletonFrame)
│   ├── annotation_io.py      # Serialization tier (Robust XML Parser read/write)
│   ├── video_processor.py    # Native clip slice, frame fragments, & technical metadata engine
│   ├── skeleton_extractor.py # Base abstraction wrapper tracking MediaPipe pipeline layers
│   └── workers.py            # Multithreaded QThread background worker implementation
│
└── ui/
    ├── __init__.py
    ├── main_window.py        # Central layout container and controller setup
    ├── video_player.py       # Custom asynchronous OpenCV playback viewer widget
    ├── video_library.py      # Local file matrix side navigation library interface
    ├── annotation_panel.py   # Dataset attribute mapping manager component
    └── processing_tab.py     # Functional controls window processing data actions
🛠️ Installation & Execution
1. Environment Setup
It is highly recommended to isolate the project within a dedicated Python virtual environment:

Bash
# Initialize target environment
python -m venv .venv

# Activate environment (Windows PowerShell)
.venv\Scripts\activate

# Activate environment (macOS / Linux terminal)
source .venv/bin/activate
2. Dependency Management
Install compiled framework requirements using the provided lock configuration file:

Bash
pip install -r requirements.txt
Alternatively, manually configure essential bindings via standard package indexing:

Bash
pip install PySide6 opencv-python mediapipe numpy
3. Application Launch
Bash
python main.py
📖 System Operational Manual
Loading Datasets
Access the menu bar tool section and choose 📂 Open Folder to scan structural dataset folders.

Select 🎞 Load Single Video to bypass automated file indexing workflows for immediate processing.

Successfully identified target segments generate clean indexed reference queues within the left-hand side Video Library.

Custom Media Controls
Key binding / Command	Action Profile Triggered
Spacebar	Play / Pause continuous viewport streaming
← / →	Incremental single-frame seek debugging adjustments
Home / End	Structural transition jumps to absolute start/end frame boundaries
Seek Slider	Synchronous random-access drag seeking track controls
Speed Selection Dropdown	Playback configuration changes ranging from 0.25× up to 4× normal rate
🦴 Skeleton Visualizer Toggle	Layer toggle projecting standard framework coordinate markers over video vectors
Creating Annotations
Scan streaming visual structures to identify the initial timestamp of a targeted movement behavior.

Press Mark Start to log the opening frame sequence boundaries.

Continue playback until the specified action behavior stops, then press Mark End.

Define target parameters using the dynamic input fields: Action Class, Body Part, Intensity level, and Modality type.

Log custom qualitative observations into the secondary notes text area if desired.

Commit actions using ＋ Add Annotation. Modifications automatically save locally to a structured XML document at <video_name>_annotations.xml.

Video Slicing Tools (Processing Tab → 🔪 Slicing)
Ensure the desired source file has active, saved annotation structures applied.

Open the processing configuration sub-tab and select the Slicing panel.

Choose your desired system export path location (defaults to a new directory beside your source).

Select ▶ Slice Annotations → Clips. The program isolates individual behavior events, exporting categorized datasets into clean sub-folders: dataset_processed/<action_class>/video_clip_001.mp4.

Window Fragmentation Pipeline (Processing Tab → 🪟 Windowing)
Configure frame sizing constraints (Default behavior bounds use 3.0s step duration configurations).

Assign overlap values depending on your model constraints (Default options use a standard 1.0s sliding configuration).

Set the target processing directory to point directly to the folder populated during the slicing step.

Execute processing tasks using ▶ Fragment Clips → Windows.

Keypoint Kinematic Extraction (Processing Tab → 🦴 Skeleton)
Select the active target data processing media record file.

Select 🦴 Extract Skeleton (Current Video).

The background multi-threaded asynchronous layer tracking workers process matrix positions without degrading main application interface performance.

Extracted structural positions save next to original resources as <video_name>_skeleton.json. Toggle the interface player's skeleton action checkbox overlay layer to see the keypoint tracking markers.

📊 Standard Schema Specifications
Structural Extracted Keypoint Blueprint (.json)
JSON
[
  {
    "frame_id": 0,
    "timestamp": 0.0,
    "keypoints": [x0, y0, x1, y1, "...", x32, y32],
    "visibility": [v0, v1, "...", v32]
  }
]
Dataset Attribute Annotation Blueprint (.xml)
XML
<?xml version="1.0" encoding="utf-8"?>
<video id="video_sample_01" keyword="Behavior Capture Session">
   <height>480</height>
   <width>640</width>
   <fps>30.0</fps>
   <frames>900</frames>
   <duration>30s</duration>
   <behaviours count="1" id="b_Set_01">
      <behaviour id="b_01">
         <time>00:05-->00:12</time>
         <bodypart>arms</bodypart>
         <category>arm_flapping</category>
         <intensity>high</intensity>
         <modality>video</modality>
         <start_sec>5.0</start_sec>
         <end_sec>12.0</end_sec>
      </behaviour>
   </behaviours>
</video>
🗂️ Outbound Dataset Architecture
After running videos through the full processing pipeline, files are organized into this clean format for direct training use:

Plaintext
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

# Core local tracker sidecar files saved beside source media:
video1_annotations.xml
video1_skeleton.json
🚀 Planned Roadmap & Feature Improvements
Advanced Multi-Person Matrix Tracking: Upgrade feature integration from simple standard Pose tracking libraries to full MediaPipe Holistic layouts for complete face, hand, and expression modeling tracking profiles.

Standard COCO JSON Interface Exporters: Build translation modules to seamlessly export annotation shapes into standard COCO formatting styles required by frameworks like MMPose and Detectron2.

Dynamic Visual Thumbnail Indexing: Introduce background frame rendering modules that display interactive hover thumbnails inside the sidebar library menu interface.

Interactive Analytical Reporting Dashboards: Build visual distribution charts inside the processing suite to review class balances across active open datasets.

Inter-Annotator Agreement Assessment Metrics: Build file reconciliation matching controls to cross-examine individual metadata outputs from multiple annotators and report real-time Cohen's Kappa score metrics.

Hardware-Accelerated Delegate Handlers: Expose internal configurations to allow users to switch processing loads from CPU limits to GPU-accelerated pipelines.

Automated Machine Learning Pre-Labeling Inference: Connect pre-trained classifications directly to the active video streaming pipe to generate automated placeholder event tags for human review.

Asynchronous Framework State Management: Introduce structural tracking models built with standard QUndoStack logic to allow developers to leverage full multi-tier undo/redo states across manual asset workflows.
