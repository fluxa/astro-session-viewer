#!/usr/bin/env python3
"""
Astro Session Viewer - Main entry point.

A PyQt6 application for analyzing astrophotography imaging sessions
using NINA and PHD2 log files.
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

from main_window import MainWindow


def setup_style(app: QApplication):
    """Configure application style and palette."""
    # Use Fusion style for consistent cross-platform look
    app.setStyle("Fusion")

    # Create a light palette with subtle customizations
    palette = QPalette()

    # Base colors
    palette.setColor(QPalette.ColorRole.Window, QColor(248, 249, 250))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(33, 37, 41))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(248, 249, 250))
    palette.setColor(QPalette.ColorRole.Text, QColor(33, 37, 41))
    palette.setColor(QPalette.ColorRole.Button, QColor(233, 236, 239))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(33, 37, 41))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(13, 110, 253))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    # Disabled state
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(108, 117, 125))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(108, 117, 125))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(108, 117, 125))

    app.setPalette(palette)

    # Global stylesheet for fine-tuning
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            padding: 6px 16px;
            border-radius: 4px;
            background-color: #e9ecef;
            border: 1px solid #ced4da;
        }
        QPushButton:hover {
            background-color: #dee2e6;
        }
        QPushButton:pressed {
            background-color: #ced4da;
        }
        QPushButton:disabled {
            background-color: #f8f9fa;
            color: #6c757d;
        }
        QTableWidget {
            gridline-color: #dee2e6;
            selection-background-color: #cfe2ff;
            selection-color: #000000;
        }
        QTableWidget::item {
            padding: 4px;
        }
        QHeaderView::section {
            background-color: #e9ecef;
            padding: 6px;
            border: none;
            border-right: 1px solid #dee2e6;
            border-bottom: 1px solid #dee2e6;
            font-weight: bold;
        }
        QTabWidget::pane {
            border: 1px solid #dee2e6;
            border-radius: 4px;
        }
        QTabBar::tab {
            padding: 8px 16px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom: 1px solid #ffffff;
        }
        QTabBar::tab:hover:!selected {
            background-color: #e9ecef;
        }
        QStatusBar {
            background-color: #f8f9fa;
            border-top: 1px solid #dee2e6;
        }
        QSplitter::handle {
            background-color: #dee2e6;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }
    """)


def main():
    """Main entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Astro Session Viewer")
    app.setOrganizationName("AstroTools")
    app.setApplicationVersion("1.0.0")

    setup_style(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
