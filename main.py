"""
Autism Behavior Annotation Tool - Main Entry Point
===================================================
A production-ready PySide6 desktop application for preprocessing
autism-behavior video datasets.
"""

import sys
import os

# Ensure the package root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from ui.main_window import MainWindow


def apply_dark_theme(app: QApplication) -> None:
    """Apply a professional dark theme to the application."""
    app.setStyle("Fusion")
    palette = QPalette()

    # Base colors
    dark_bg     = QColor(18, 18, 24)
    mid_bg      = QColor(28, 28, 38)
    panel_bg    = QColor(36, 36, 50)
    border      = QColor(55, 55, 75)
    text_main   = QColor(220, 220, 235)
    text_dim    = QColor(130, 130, 155)
    accent      = QColor(99, 179, 237)   # calm blue
    accent_dark = QColor(66, 140, 200)
    highlight   = QColor(99, 179, 237, 60)

    palette.setColor(QPalette.Window,          mid_bg)
    palette.setColor(QPalette.WindowText,      text_main)
    palette.setColor(QPalette.Base,            dark_bg)
    palette.setColor(QPalette.AlternateBase,   panel_bg)
    palette.setColor(QPalette.ToolTipBase,     panel_bg)
    palette.setColor(QPalette.ToolTipText,     text_main)
    palette.setColor(QPalette.Text,            text_main)
    palette.setColor(QPalette.Button,          panel_bg)
    palette.setColor(QPalette.ButtonText,      text_main)
    palette.setColor(QPalette.BrightText,      Qt.white)
    palette.setColor(QPalette.Link,            accent)
    palette.setColor(QPalette.Highlight,       accent)
    palette.setColor(QPalette.HighlightedText, dark_bg)
    palette.setColor(QPalette.Disabled, QPalette.Text,       text_dim)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, text_dim)
    palette.setColor(QPalette.Mid,             border)
    palette.setColor(QPalette.Dark,            dark_bg)
    palette.setColor(QPalette.Shadow,          QColor(0, 0, 0))

    app.setPalette(palette)

    app.setStyleSheet(f"""
        QMainWindow {{
            background-color: rgb(18,18,24);
        }}
        QWidget {{
            font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif;
            font-size: 13px;
        }}
        QSplitter::handle {{
            background-color: rgb(55,55,75);
            width: 1px;
            height: 1px;
        }}
        QToolBar {{
            background-color: rgb(28,28,38);
            border-bottom: 1px solid rgb(55,55,75);
            spacing: 4px;
            padding: 4px 8px;
        }}
        QPushButton {{
            background-color: rgb(44,44,62);
            color: rgb(220,220,235);
            border: 1px solid rgb(65,65,90);
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: rgb(60,60,85);
            border-color: rgb(99,179,237);
        }}
        QPushButton:pressed {{
            background-color: rgb(36,36,52);
        }}
        QPushButton:disabled {{
            color: rgb(100,100,120);
            border-color: rgb(45,45,60);
        }}
        QPushButton#accent_btn {{
            background-color: rgb(99,179,237);
            color: rgb(12,12,20);
            border: none;
            font-weight: 600;
        }}
        QPushButton#accent_btn:hover {{
            background-color: rgb(130,200,255);
        }}
        QPushButton#danger_btn {{
            background-color: rgb(220,80,80);
            color: white;
            border: none;
        }}
        QPushButton#danger_btn:hover {{
            background-color: rgb(240,100,100);
        }}
        QListWidget {{
            background-color: rgb(22,22,32);
            border: 1px solid rgb(50,50,70);
            border-radius: 6px;
            outline: none;
            padding: 4px;
        }}
        QListWidget::item {{
            padding: 8px 10px;
            border-radius: 4px;
            color: rgb(200,200,220);
        }}
        QListWidget::item:selected {{
            background-color: rgb(99,179,237,80);
            color: white;
        }}
        QListWidget::item:hover:!selected {{
            background-color: rgb(45,45,65);
        }}
        QTableWidget {{
            background-color: rgb(22,22,32);
            border: 1px solid rgb(50,50,70);
            border-radius: 6px;
            gridline-color: rgb(45,45,65);
            outline: none;
        }}
        QTableWidget::item {{
            padding: 6px 10px;
            border: none;
        }}
        QTableWidget::item:selected {{
            background-color: rgba(99,179,237,100);
        }}
        QHeaderView::section {{
            background-color: rgb(32,32,48);
            color: rgb(160,160,185);
            border: none;
            border-bottom: 1px solid rgb(55,55,75);
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        QComboBox {{
            background-color: rgb(36,36,52);
            border: 1px solid rgb(65,65,90);
            border-radius: 6px;
            padding: 5px 10px;
            color: rgb(220,220,235);
            min-width: 140px;
        }}
        QComboBox:hover {{
            border-color: rgb(99,179,237);
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: rgb(36,36,52);
            border: 1px solid rgb(65,65,90);
            selection-background-color: rgb(99,179,237);
            selection-color: rgb(12,12,20);
            outline: none;
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            background-color: rgb(55,55,75);
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background-color: rgb(99,179,237);
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::sub-page:horizontal {{
            background-color: rgb(99,179,237);
            border-radius: 2px;
        }}
        QLabel {{
            color: rgb(200,200,220);
        }}
        QLabel#section_title {{
            color: rgb(160,160,185);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
        }}
        QGroupBox {{
            border: 1px solid rgb(50,50,70);
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
            font-size: 11px;
            font-weight: 600;
            color: rgb(150,150,175);
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
        }}
        QScrollBar:vertical {{
            background-color: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: rgb(70,70,100);
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: rgb(99,179,237);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background-color: transparent;
            height: 8px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: rgb(70,70,100);
            border-radius: 4px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QTabWidget::pane {{
            border: 1px solid rgb(50,50,70);
            border-radius: 6px;
            background-color: rgb(22,22,32);
        }}
        QTabBar::tab {{
            background-color: rgb(32,32,48);
            color: rgb(150,150,175);
            padding: 8px 18px;
            border: none;
            border-bottom: 2px solid transparent;
            font-size: 12px;
        }}
        QTabBar::tab:selected {{
            color: rgb(99,179,237);
            border-bottom: 2px solid rgb(99,179,237);
            background-color: rgb(22,22,32);
        }}
        QTabBar::tab:hover:!selected {{
            color: rgb(200,200,220);
            background-color: rgb(36,36,52);
        }}
        QStatusBar {{
            background-color: rgb(20,20,30);
            color: rgb(130,130,155);
            border-top: 1px solid rgb(45,45,65);
            font-size: 11px;
        }}
        QProgressBar {{
            background-color: rgb(36,36,52);
            border: 1px solid rgb(55,55,75);
            border-radius: 4px;
            text-align: center;
            color: white;
            font-size: 11px;
        }}
        QProgressBar::chunk {{
            background-color: rgb(99,179,237);
            border-radius: 3px;
        }}
        QLineEdit {{
            background-color: rgb(28,28,40);
            border: 1px solid rgb(55,55,75);
            border-radius: 6px;
            padding: 5px 10px;
            color: rgb(220,220,235);
        }}
        QLineEdit:focus {{
            border-color: rgb(99,179,237);
        }}
        QSpinBox, QDoubleSpinBox {{
            background-color: rgb(28,28,40);
            border: 1px solid rgb(55,55,75);
            border-radius: 6px;
            padding: 4px 8px;
            color: rgb(220,220,235);
        }}
        QTextEdit {{
            background-color: rgb(22,22,32);
            border: 1px solid rgb(50,50,70);
            border-radius: 6px;
            color: rgb(200,200,220);
            font-family: 'Consolas', 'JetBrains Mono', monospace;
            font-size: 12px;
        }}
        QCheckBox {{
            color: rgb(200,200,220);
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid rgb(65,65,90);
            border-radius: 3px;
            background-color: rgb(36,36,52);
        }}
        QCheckBox::indicator:checked {{
            background-color: rgb(99,179,237);
            border-color: rgb(99,179,237);
        }}
        QToolTip {{
            background-color: rgb(36,36,52);
            color: rgb(220,220,235);
            border: 1px solid rgb(65,65,90);
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        }}
        QMenu {{
            background-color: rgb(32,32,48);
            border: 1px solid rgb(55,55,75);
            border-radius: 6px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
            color: rgb(200,200,220);
        }}
        QMenu::item:selected {{
            background-color: rgb(50,50,75);
        }}
        QSplitter::handle:horizontal {{
            background-color: rgb(45,45,65);
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            background-color: rgb(45,45,65);
            height: 2px;
        }}
    """)


def main():
    # Enable HiDPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Autism Behavior Annotation Tool")
    app.setOrganizationName("NeuroVision Lab")
    app.setApplicationVersion("1.0.0")

    apply_dark_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
