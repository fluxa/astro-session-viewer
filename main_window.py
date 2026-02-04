"""
Main window for the Astro Session Viewer application.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QFileDialog, QPushButton, QLabel, QFrame,
    QStatusBar, QToolBar, QMessageBox, QGroupBox, QDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon

from parsers import PHD2Parser, NINAParser, match_session_logs, correlate_guiding_with_exposures
from widgets import (
    SessionSummaryWidget, GuidingChartWidget, HFRChartWidget,
    AutofocusTableWidget, ExposuresTableWidget, EventsListWidget,
    GuidingSessionsTableWidget, SessionSelectorDialog
)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Astro Session Viewer")
        self.setMinimumSize(1200, 800)

        self._phd2_parser: Optional[PHD2Parser] = None
        self._nina_parser: Optional[NINAParser] = None
        self._phd2_path: Optional[Path] = None
        self._nina_path: Optional[Path] = None

        # Remember folder paths for session finder
        self._nina_folder: Optional[Path] = None
        self._phd2_folder: Optional[Path] = None

        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()

    def _setup_ui(self):
        """Set up the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # File selection bar
        file_bar = self._create_file_bar()
        main_layout.addWidget(file_bar)

        # Main content splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Summary and events
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.summary_widget = SessionSummaryWidget()
        left_layout.addWidget(self.summary_widget)

        self.events_widget = EventsListWidget()
        left_layout.addWidget(self.events_widget, stretch=1)

        main_splitter.addWidget(left_panel)

        # Center panel - Charts and tables
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Charts in tabs
        charts_tabs = QTabWidget()

        # Guiding chart tab
        guiding_tab = QWidget()
        guiding_layout = QVBoxLayout(guiding_tab)
        guiding_layout.setContentsMargins(4, 4, 4, 4)
        self.guiding_chart = GuidingChartWidget()
        self.guiding_chart.ditherSettingsChanged.connect(self._on_dither_settings_changed)
        guiding_layout.addWidget(self.guiding_chart)
        charts_tabs.addTab(guiding_tab, "Guiding RMS")

        # HFR chart tab
        hfr_tab = QWidget()
        hfr_layout = QVBoxLayout(hfr_tab)
        hfr_layout.setContentsMargins(4, 4, 4, 4)
        self.hfr_chart = HFRChartWidget()
        hfr_layout.addWidget(self.hfr_chart)
        charts_tabs.addTab(hfr_tab, "HFR per Sub")

        center_layout.addWidget(charts_tabs, stretch=2)

        # Tables in tabs
        tables_tabs = QTabWidget()

        self.exposures_table = ExposuresTableWidget()
        tables_tabs.addTab(self.exposures_table, "Exposures")

        self.autofocus_table = AutofocusTableWidget()
        tables_tabs.addTab(self.autofocus_table, "Autofocus")

        self.guiding_sessions_table = GuidingSessionsTableWidget()
        tables_tabs.addTab(self.guiding_sessions_table, "Guiding Sessions")

        center_layout.addWidget(tables_tabs, stretch=1)

        main_splitter.addWidget(center_panel)

        # Set splitter proportions
        main_splitter.setSizes([300, 900])

        main_layout.addWidget(main_splitter, stretch=1)

    def _create_file_bar(self) -> QWidget:
        """Create the file selection bar."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)

        # Quick load button
        self.quick_load_btn = QPushButton("Load Session...")
        self.quick_load_btn.setMinimumHeight(40)
        self.quick_load_btn.setMinimumWidth(120)
        self.quick_load_btn.clicked.connect(self._show_session_selector)
        self.quick_load_btn.setToolTip("Scan folders and select a session to load")
        layout.addWidget(self.quick_load_btn)

        layout.addSpacing(10)

        # PHD2 log section
        phd2_group = QGroupBox("PHD2 Log")
        phd2_layout = QHBoxLayout(phd2_group)
        phd2_layout.setContentsMargins(8, 4, 8, 4)

        self.phd2_label = QLabel("No file selected")
        self.phd2_label.setMinimumWidth(180)
        phd2_layout.addWidget(self.phd2_label, stretch=1)

        self.phd2_browse_btn = QPushButton("Browse...")
        self.phd2_browse_btn.clicked.connect(self._browse_phd2)
        phd2_layout.addWidget(self.phd2_browse_btn)

        layout.addWidget(phd2_group, stretch=1)

        # NINA log section
        nina_group = QGroupBox("NINA Log")
        nina_layout = QHBoxLayout(nina_group)
        nina_layout.setContentsMargins(8, 4, 8, 4)

        self.nina_label = QLabel("No file selected")
        self.nina_label.setMinimumWidth(180)
        nina_layout.addWidget(self.nina_label, stretch=1)

        self.nina_browse_btn = QPushButton("Browse...")
        self.nina_browse_btn.clicked.connect(self._browse_nina)
        nina_layout.addWidget(self.nina_browse_btn)

        layout.addWidget(nina_group, stretch=1)

        # Load button for manual selection
        self.load_btn = QPushButton("Load")
        self.load_btn.setMinimumHeight(40)
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._load_session)
        self.load_btn.setToolTip("Load manually selected log files")
        layout.addWidget(self.load_btn)

        return frame

    def _setup_menubar(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        load_session_action = QAction("&Load Session...", self)
        load_session_action.setShortcut("Ctrl+O")
        load_session_action.triggered.connect(self._show_session_selector)
        file_menu.addAction(load_session_action)

        file_menu.addSeparator()

        open_phd2_action = QAction("Open PHD2 Log...", self)
        open_phd2_action.setShortcut("Ctrl+Shift+P")
        open_phd2_action.triggered.connect(self._browse_phd2)
        file_menu.addAction(open_phd2_action)

        open_nina_action = QAction("Open NINA Log...", self)
        open_nina_action.setShortcut("Ctrl+Shift+N")
        open_nina_action.triggered.connect(self._browse_nina)
        file_menu.addAction(open_nina_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready - Select PHD2 and NINA log files to begin")

    def _show_session_selector(self):
        """Show the session selector dialog."""
        dialog = SessionSelectorDialog(self)

        # Pre-populate with remembered folders
        dialog.set_folders(self._nina_folder, self._phd2_folder)

        # If folders are set, auto-scan
        if self._nina_folder or self._phd2_folder:
            dialog._scan_folders()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            nina_path, phd2_path = dialog.get_selected_logs()

            # Remember the folders for next time
            if nina_path:
                self._nina_folder = nina_path.parent
                self._nina_path = nina_path
                self.nina_label.setText(nina_path.name)
            if phd2_path:
                self._phd2_folder = phd2_path.parent
                self._phd2_path = phd2_path
                self.phd2_label.setText(phd2_path.name)

            self._update_load_button()
            if nina_path or phd2_path:
                self._load_session()

    def _browse_phd2(self):
        """Open file dialog for PHD2 log."""
        start_dir = str(self._phd2_folder) if self._phd2_folder else ""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select PHD2 Guide Log",
            start_dir,
            "PHD2 Log Files (PHD2_GuideLog*.txt);;All Files (*.*)"
        )
        if filepath:
            self._phd2_path = Path(filepath)
            self._phd2_folder = self._phd2_path.parent
            self.phd2_label.setText(self._phd2_path.name)
            self._update_load_button()

    def _browse_nina(self):
        """Open file dialog for NINA log."""
        start_dir = str(self._nina_folder) if self._nina_folder else ""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select NINA Log",
            start_dir,
            "NINA Log Files (*.log);;All Files (*.*)"
        )
        if filepath:
            self._nina_path = Path(filepath)
            self._nina_folder = self._nina_path.parent
            self.nina_label.setText(self._nina_path.name)
            self._update_load_button()

    def _update_load_button(self):
        """Enable load button if at least one file is selected."""
        self.load_btn.setEnabled(
            self._phd2_path is not None or self._nina_path is not None
        )

    def _load_session(self):
        """Load and parse the selected log files."""
        self.statusbar.showMessage("Loading session data...")

        try:
            # Parse PHD2 log
            if self._phd2_path:
                self._phd2_parser = PHD2Parser()
                self._phd2_parser.parse(self._phd2_path)
                self.statusbar.showMessage(
                    f"Loaded {len(self._phd2_parser.sessions)} guiding sessions"
                )

            # Parse NINA log
            if self._nina_path:
                self._nina_parser = NINAParser()
                self._nina_parser.parse(self._nina_path)
                self.statusbar.showMessage(
                    f"Loaded {len(self._nina_parser.exposures)} exposures, "
                    f"{len(self._nina_parser.autofocus_runs)} autofocus runs"
                )

            # Update all widgets
            self._update_widgets()

            self.statusbar.showMessage("Session loaded successfully")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Session",
                f"Failed to parse log files:\n\n{str(e)}"
            )
            self.statusbar.showMessage("Error loading session")

    def _update_widgets(self):
        """Update all widgets with parsed data."""
        # Get current dither settings from chart widget
        dither_margin = self.guiding_chart.get_dither_margin()
        exclude_dither = self.guiding_chart.is_dither_excluded()

        # Correlate guiding data with exposures if both datasets available
        if self._phd2_parser and self._nina_parser:
            dither_events = self._nina_parser.dither_events if exclude_dither else None
            correlate_guiding_with_exposures(
                self._phd2_parser, self._nina_parser,
                dither_events=dither_events,
                dither_margin_seconds=dither_margin
            )

        # Summary
        self.summary_widget.update_data(
            self._phd2_parser, self._nina_parser,
            dither_margin=dither_margin, exclude_dither=exclude_dither
        )

        # Events
        self.events_widget.set_data(self._phd2_parser, self._nina_parser)

        # Charts
        if self._phd2_parser:
            self.guiding_chart.set_data(self._phd2_parser, self._nina_parser)
            self.guiding_sessions_table.set_data(self._phd2_parser)

        if self._nina_parser:
            self.hfr_chart.set_data(self._nina_parser)
            self.exposures_table.set_data(self._nina_parser)
            self.autofocus_table.set_data(self._nina_parser)

    def _on_dither_settings_changed(self, margin: float, exclude: bool):
        """Handle dither settings change from chart widget."""
        if self._phd2_parser and self._nina_parser:
            # Recorrelate guiding data with new dither settings
            dither_events = self._nina_parser.dither_events if exclude else None
            correlate_guiding_with_exposures(
                self._phd2_parser, self._nina_parser,
                dither_events=dither_events,
                dither_margin_seconds=margin
            )
            # Update exposures table
            self.exposures_table.set_data(self._nina_parser)

        # Update summary with new settings
        if self._phd2_parser or self._nina_parser:
            self.summary_widget.update_data(
                self._phd2_parser, self._nina_parser,
                dither_margin=margin, exclude_dither=exclude
            )

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Astro Session Viewer",
            "<h3>Astro Session Viewer</h3>"
            "<p>Version 1.0.0</p>"
            "<p>A tool for analyzing astrophotography imaging sessions "
            "using NINA and PHD2 log files.</p>"
            "<p>Displays guiding performance, autofocus runs, "
            "image quality metrics, and session events.</p>"
        )
