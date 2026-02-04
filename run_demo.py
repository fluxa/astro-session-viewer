#!/usr/bin/env python3
"""
Demo script that loads sample files automatically for testing.
"""
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from main import setup_style
from main_window import MainWindow


def main():
    """Run demo with sample files pre-loaded."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Astro Session Viewer")
    setup_style(app)

    window = MainWindow()

    # Pre-configure sample folders for session selector
    sample_dir = Path(__file__).parent / "sample_files"
    window._nina_folder = sample_dir / "NINA"
    window._phd2_folder = sample_dir / "PHD2"

    # Pre-load the 2026-01-22 session
    phd2_file = sample_dir / "PHD2" / "PHD2_GuideLog_2026-01-22_220606.txt"
    nina_file = sample_dir / "NINA" / "20260122-220419-3.2.0.9001.4256-202601.log"

    if phd2_file.exists():
        window._phd2_path = phd2_file
        window.phd2_label.setText(phd2_file.name)

    if nina_file.exists():
        window._nina_path = nina_file
        window.nina_label.setText(nina_file.name)

    window._update_load_button()

    # Auto-load after window is shown
    def auto_load():
        window._load_session()

    QTimer.singleShot(500, auto_load)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
