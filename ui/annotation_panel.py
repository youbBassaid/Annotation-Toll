"""
ui/annotation_panel.py
======================
Right-side panel for creating, editing, and listing annotations.
Fully decoupled from the video player — communicates via signals.
"""

from __future__ import annotations
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QLineEdit, QTextEdit, QMessageBox,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QColor, QBrush, QFont

from core.models import (
    Annotation, VideoInfo, ACTION_CLASSES,
    BODY_PARTS, INTENSITY_LEVELS, MODALITIES,
    _seconds_to_timecode
)
from core.annotation_io import save_annotations_xml, xml_path_for_video


# Colour map for action classes (displayed as coloured table rows)
CLASS_COLORS = {
    "arm_flapping":          "#3a5a7a",
    "hand_flapping":         "#3a6a5a",
    "spinning":              "#5a3a7a",
    "rocking":               "#7a5a3a",
    "headbanging":           "#7a3a3a",
    "mouthing":              "#6a5a3a",
    "toe_walking":           "#3a6a7a",
    "eye_contact_avoidance": "#5a4a7a",
    "repetitive_movement":   "#4a6a4a",
    "self_injurious":        "#7a3a4a",
    "neutral":               "#3a3a4a",
    "other":                 "#4a4a3a",
}


def _fmt(secs: float) -> str:
    return _seconds_to_timecode(secs)


class AnnotationPanel(QWidget):
    """
    Widget that lets the user create and manage annotations.

    Signals
    -------
    annotation_added(Annotation)
    annotation_removed(str)          annotation_id
    annotation_selected(Annotation)  user clicked a row
    annotations_saved(str)           xml_path
    seek_requested(float)            user wants player to seek (seconds)
    """

    annotation_added    = Signal(object)
    annotation_removed  = Signal(str)
    annotation_selected = Signal(object)
    annotations_saved   = Signal(str)
    seek_requested      = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._video_info: Optional[VideoInfo] = None
        self._pending_start: Optional[float] = None
        self._current_time: float = 0.0

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Title ──────────────────────────────────────────────────────
        title = QLabel("ANNOTATIONS")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # ── New annotation form ─────────────────────────────────────────
        form_group = QGroupBox("New Annotation")
        form_layout = QGridLayout(form_group)
        form_layout.setHorizontalSpacing(8)
        form_layout.setVerticalSpacing(6)

        # Start / End time capture
        form_layout.addWidget(QLabel("Start:"), 0, 0)
        self._lbl_start = QLabel("—")
        self._lbl_start.setStyleSheet(
            "color: #63b3ed; font-family: monospace; font-weight: bold;")
        form_layout.addWidget(self._lbl_start, 0, 1)

        self._btn_mark_start = QPushButton("Mark Start")
        self._btn_mark_start.setObjectName("accent_btn")
        self._btn_mark_start.clicked.connect(self._mark_start)
        self._btn_mark_start.setEnabled(False)
        form_layout.addWidget(self._btn_mark_start, 0, 2)

        form_layout.addWidget(QLabel("End:"), 1, 0)
        self._lbl_end = QLabel("—")
        self._lbl_end.setStyleSheet(
            "color: #63b3ed; font-family: monospace; font-weight: bold;")
        form_layout.addWidget(self._lbl_end, 1, 1)

        self._btn_mark_end = QPushButton("Mark End")
        self._btn_mark_end.setObjectName("accent_btn")
        self._btn_mark_end.clicked.connect(self._mark_end)
        self._btn_mark_end.setEnabled(False)
        form_layout.addWidget(self._btn_mark_end, 1, 2)

        # Action class
        form_layout.addWidget(QLabel("Class:"), 2, 0)
        self._combo_class = QComboBox()
        self._combo_class.addItems(ACTION_CLASSES)
        form_layout.addWidget(self._combo_class, 2, 1, 1, 2)

        # Body part
        form_layout.addWidget(QLabel("Body Part:"), 3, 0)
        self._combo_body = QComboBox()
        self._combo_body.addItems(BODY_PARTS)
        form_layout.addWidget(self._combo_body, 3, 1, 1, 2)

        # Intensity
        form_layout.addWidget(QLabel("Intensity:"), 4, 0)
        self._combo_intensity = QComboBox()
        self._combo_intensity.addItems(INTENSITY_LEVELS)
        self._combo_intensity.setCurrentIndex(1)  # medium
        form_layout.addWidget(self._combo_intensity, 4, 1, 1, 2)

        # Modality
        form_layout.addWidget(QLabel("Modality:"), 5, 0)
        self._combo_modality = QComboBox()
        self._combo_modality.addItems(MODALITIES)
        form_layout.addWidget(self._combo_modality, 5, 1, 1, 2)

        # Notes
        form_layout.addWidget(QLabel("Notes:"), 6, 0, Qt.AlignTop)
        self._edit_notes = QTextEdit()
        self._edit_notes.setFixedHeight(54)
        self._edit_notes.setPlaceholderText("Optional notes…")
        form_layout.addWidget(self._edit_notes, 6, 1, 1, 2)

        # Add button
        self._btn_add = QPushButton("＋ Add Annotation")
        self._btn_add.setObjectName("accent_btn")
        self._btn_add.clicked.connect(self._add_annotation)
        self._btn_add.setEnabled(False)
        form_layout.addWidget(self._btn_add, 7, 0, 1, 3)

        layout.addWidget(form_group)

        # ── Annotation table ───────────────────────────────────────────
        tbl_group = QGroupBox("Annotation List")
        tbl_layout = QVBoxLayout(tbl_group)
        tbl_layout.setSpacing(6)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Start", "End", "Class", "Intensity", "Body Part"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._table_selection_changed)
        self._table.itemChanged.connect(self._table_item_changed)
        tbl_layout.addWidget(self._table)

        # Table action buttons
        btn_row = QHBoxLayout()
        self._btn_delete = QPushButton("🗑 Delete")
        self._btn_delete.setObjectName("danger_btn")
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_delete.setEnabled(False)

        self._btn_goto = QPushButton("⏩ Go to")
        self._btn_goto.clicked.connect(self._goto_selected)
        self._btn_goto.setEnabled(False)
        self._btn_goto.setToolTip("Seek video to annotation start time")

        self._btn_save = QPushButton("💾 Save XML")
        self._btn_save.setObjectName("accent_btn")
        self._btn_save.clicked.connect(self._save_xml)
        self._btn_save.setEnabled(False)

        btn_row.addWidget(self._btn_goto)
        btn_row.addWidget(self._btn_delete)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)
        tbl_layout.addLayout(btn_row)

        # Stats
        self._lbl_stats = QLabel("0 annotations")
        self._lbl_stats.setStyleSheet("color: rgb(120,120,145); font-size: 11px;")
        tbl_layout.addWidget(self._lbl_stats)

        layout.addWidget(tbl_group, stretch=1)

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def load_video(self, video_info: VideoInfo):
        """Called when a new video is selected."""
        self._video_info = video_info
        self._pending_start = None
        self._lbl_start.setText("—")
        self._lbl_end.setText("—")
        self._btn_mark_start.setEnabled(True)
        self._btn_mark_end.setEnabled(True)
        self._btn_add.setEnabled(False)
        self._btn_save.setEnabled(True)
        self._refresh_table()

    def update_current_time(self, seconds: float):
        """Keep track of the player's current position."""
        self._current_time = seconds

    def set_annotations(self, annotations: List[Annotation]):
        """Replace the annotation list (e.g., after loading XML)."""
        if self._video_info:
            self._video_info.annotations = annotations
            self._refresh_table()

    # ──────────────────────────────────────────────────────────────────
    # Private slots
    # ──────────────────────────────────────────────────────────────────

    def _mark_start(self):
        self._pending_start = self._current_time
        self._lbl_start.setText(_fmt(self._current_time))
        self._lbl_end.setText("—")
        self._btn_add.setEnabled(False)

    def _mark_end(self):
        if self._pending_start is None:
            return
        end = self._current_time
        if end <= self._pending_start:
            QMessageBox.warning(self, "Invalid Range",
                                "End time must be after start time.")
            return
        self._lbl_end.setText(_fmt(end))
        self._btn_add.setEnabled(True)

    def _add_annotation(self):
        if self._video_info is None or self._pending_start is None:
            return

        end_str = self._lbl_end.text()
        if end_str == "—":
            return

        # Parse end from label
        parts = end_str.split(":")
        try:
            if len(parts) == 2:
                end_sec = int(parts[0]) * 60 + float(parts[1])
            else:
                end_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except ValueError:
            return

        ann = Annotation(
            start_time=self._pending_start,
            end_time=end_sec,
            action_class=self._combo_class.currentText(),
            body_part=self._combo_body.currentText(),
            intensity=self._combo_intensity.currentText(),
            modality=self._combo_modality.currentText(),
            notes=self._edit_notes.toPlainText().strip(),
        )

        self._video_info.annotations.append(ann)
        self._refresh_table()
        self._auto_save()
        self.annotation_added.emit(ann)

        # Reset form
        self._pending_start = None
        self._lbl_start.setText("—")
        self._lbl_end.setText("—")
        self._btn_add.setEnabled(False)
        self._edit_notes.clear()

    def _delete_selected(self):
        if self._video_info is None:
            return
        row = self._table.currentRow()
        if row < 0 or row >= len(self._video_info.annotations):
            return
        ann = self._video_info.annotations[row]
        reply = QMessageBox.question(
            self, "Delete Annotation",
            f"Delete annotation at {ann.start_timecode()} → {ann.end_timecode()}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._video_info.annotations.pop(row)
            self._refresh_table()
            self._auto_save()
            self.annotation_removed.emit(ann.annotation_id)

    def _goto_selected(self):
        if self._video_info is None:
            return
        row = self._table.currentRow()
        if 0 <= row < len(self._video_info.annotations):
            ann = self._video_info.annotations[row]
            self.seek_requested.emit(ann.start_time)

    def _save_xml(self):
        if self._video_info is None:
            return
        xml_path = xml_path_for_video(self._video_info.file_path)
        save_annotations_xml(self._video_info, xml_path)
        self.annotations_saved.emit(xml_path)

    def _auto_save(self):
        if self._video_info:
            xml_path = xml_path_for_video(self._video_info.file_path)
            save_annotations_xml(self._video_info, xml_path)

    def _table_selection_changed(self):
        has_sel = len(self._table.selectedItems()) > 0
        self._btn_delete.setEnabled(has_sel)
        self._btn_goto.setEnabled(has_sel)
        if self._video_info and has_sel:
            row = self._table.currentRow()
            if 0 <= row < len(self._video_info.annotations):
                self.annotation_selected.emit(self._video_info.annotations[row])

    def _table_item_changed(self, item: QTableWidgetItem):
        """Propagate inline edits back to the model."""
        if self._video_info is None:
            return
        row = item.row()
        col = item.column()
        if row >= len(self._video_info.annotations):
            return
        ann = self._video_info.annotations[row]

        # Only the class column (2) is user-editable inline
        if col == 2:
            val = item.text().strip()
            if val in ACTION_CLASSES:
                ann.action_class = val
                self._auto_save()

    # ──────────────────────────────────────────────────────────────────
    # Table rendering
    # ──────────────────────────────────────────────────────────────────

    def _refresh_table(self):
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        if self._video_info is None:
            self._table.blockSignals(False)
            return

        for ann in self._video_info.annotations:
            row = self._table.rowCount()
            self._table.insertRow(row)

            items = [
                QTableWidgetItem(_fmt(ann.start_time)),
                QTableWidgetItem(_fmt(ann.end_time)),
                QTableWidgetItem(ann.action_class),
                QTableWidgetItem(ann.intensity),
                QTableWidgetItem(ann.body_part),
            ]

            color_hex = CLASS_COLORS.get(ann.action_class, "#3a3a4a")
            bg = QColor(color_hex)

            for col, item in enumerate(items):
                item.setBackground(QBrush(bg))
                item.setForeground(QBrush(QColor("#d0d0e8")))
                if col != 2:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(row, col, item)

        count = len(self._video_info.annotations)
        self._lbl_stats.setText(
            f"{count} annotation{'s' if count != 1 else ''}"
        )
        self._table.blockSignals(False)
