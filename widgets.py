"""
Custom widgets for the Astro Session Viewer.
"""
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QComboBox,
    QSplitter, QFrame, QCheckBox, QSpinBox, QDoubleSpinBox,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QLineEdit, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from pathlib import Path
import pyqtgraph as pg
import numpy as np

from parsers import PHD2Parser, NINAParser, GuidingSession


class SessionSummaryWidget(QGroupBox):
    """Widget displaying session summary information."""

    def __init__(self, parent=None):
        super().__init__("Session Summary", parent)
        self._phd2: Optional[PHD2Parser] = None
        self._nina: Optional[NINAParser] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Create grid of labels
        self.target_label = QLabel("Target: -")
        self.date_label = QLabel("Date: -")
        self.duration_label = QLabel("Duration: -")
        self.subs_label = QLabel("Subs: -")
        self.integration_label = QLabel("Integration: -")

        layout.addWidget(self.target_label)
        layout.addWidget(self.date_label)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.subs_label)
        layout.addWidget(self.integration_label)

        # Guiding stats
        layout.addWidget(QLabel(""))  # Spacer
        layout.addWidget(QLabel("<b>Guiding Performance</b>"))

        # RMS with dither exclusion
        self.ra_rms_label = QLabel("RA RMS: -")
        self.dec_rms_label = QLabel("Dec RMS: -")
        self.total_rms_label = QLabel("Total RMS: -")

        layout.addWidget(self.ra_rms_label)
        layout.addWidget(self.dec_rms_label)
        layout.addWidget(self.total_rms_label)

        # RMS comparison (raw vs filtered)
        self.rms_comparison_label = QLabel("")
        self.rms_comparison_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.rms_comparison_label)

        layout.addStretch()

    def update_data(self, phd2: Optional[PHD2Parser], nina: Optional[NINAParser],
                    dither_margin: float = 3.0, exclude_dither: bool = True):
        """Update the summary with parsed data."""
        self._phd2 = phd2
        self._nina = nina

        if nina:
            self.target_label.setText(f"Target: {nina.target_name or 'Unknown'}")
            if nina.session_start:
                self.date_label.setText(f"Date: {nina.session_start.strftime('%Y-%m-%d')}")
            if nina.session_start and nina.session_end:
                duration = nina.session_end - nina.session_start
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                self.duration_label.setText(f"Duration: {int(hours)}h {int(minutes)}m")

            self.subs_label.setText(f"Subs: {len(nina.exposures)}")

            total_integration = sum(exp.exposure_time for exp in nina.exposures)
            int_hours, int_remainder = divmod(total_integration, 3600)
            int_minutes, _ = divmod(int_remainder, 60)
            self.integration_label.setText(f"Integration: {int(int_hours)}h {int(int_minutes)}m")

        if phd2 and phd2.sessions:
            dither_events = nina.dither_events if nina else None

            # Calculate RMS without dither exclusion (raw)
            ra_raw, dec_raw, total_raw = phd2.get_overall_rms(dither_events=None)

            # Calculate RMS with dither exclusion (filtered)
            if dither_events and exclude_dither:
                ra_filtered, dec_filtered, total_filtered = phd2.get_overall_rms(
                    dither_events=dither_events,
                    dither_margin_seconds=dither_margin
                )
                # Display filtered values
                ra_rms, dec_rms, total_rms = ra_filtered, dec_filtered, total_filtered
            else:
                ra_rms, dec_rms, total_rms = ra_raw, dec_raw, total_raw

            if ra_rms > 0:
                self.ra_rms_label.setText(f"RA RMS: {ra_rms:.2f}\"")
                self.dec_rms_label.setText(f"Dec RMS: {dec_rms:.2f}\"")
                self.total_rms_label.setText(f"Total RMS: {total_rms:.2f}\"")

                # Show comparison if dither events exist
                if dither_events and exclude_dither:
                    improvement = ((total_raw - total_rms) / total_raw) * 100 if total_raw > 0 else 0
                    self.rms_comparison_label.setText(
                        f"Raw: {total_raw:.2f}\" | Filtered: {total_rms:.2f}\" "
                        f"({improvement:+.1f}%)"
                    )
                    self.total_rms_label.setToolTip(
                        f"Excludes {len(dither_events)} dither events (±{dither_margin}s margin)"
                    )
                else:
                    self.rms_comparison_label.setText("")
                    self.total_rms_label.setToolTip("")


class GuidingChartWidget(QWidget):
    """Widget displaying guiding RMS chart over time."""

    # Signal emitted when dither settings change
    ditherSettingsChanged = pyqtSignal(float, bool)  # margin, exclude

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with controls
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Guiding RMS</b>"))
        header.addStretch()

        # Granularity selector
        header.addWidget(QLabel("Granularity:"))
        self.granularity_combo = QComboBox()
        self.granularity_combo.addItems(["1 min", "5 min", "10 min", "30 min"])
        self.granularity_combo.setCurrentIndex(1)  # Default to 5 min
        self.granularity_combo.currentIndexChanged.connect(self._on_settings_changed)
        header.addWidget(self.granularity_combo)

        header.addSpacing(20)

        # Dither exclusion toggle
        self.exclude_dither_cb = QCheckBox("Exclude dither")
        self.exclude_dither_cb.setChecked(True)
        self.exclude_dither_cb.setToolTip("Exclude guiding data during dither settling")
        self.exclude_dither_cb.stateChanged.connect(self._on_settings_changed)
        header.addWidget(self.exclude_dither_cb)

        # Dither margin spinbox
        header.addWidget(QLabel("Margin:"))
        self.dither_margin_spin = QDoubleSpinBox()
        self.dither_margin_spin.setRange(0.0, 10.0)
        self.dither_margin_spin.setValue(3.0)
        self.dither_margin_spin.setSuffix(" s")
        self.dither_margin_spin.setSingleStep(0.5)
        self.dither_margin_spin.setToolTip("Seconds before/after dither to exclude")
        self.dither_margin_spin.valueChanged.connect(self._on_settings_changed)
        header.addWidget(self.dither_margin_spin)

        layout.addLayout(header)

        # PyQtGraph plot with custom time axis
        time_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': time_axis})
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'RMS (arcsec)')
        self.plot_widget.setLabel('bottom', 'Time')
        # Disable SI prefix auto-scaling on Y axis
        self.plot_widget.getAxis('left').enableAutoSIPrefix(False)
        self.plot_widget.addLegend()

        layout.addWidget(self.plot_widget)

        self._phd2_parser: Optional[PHD2Parser] = None
        self._nina_parser: Optional[NINAParser] = None
        self._event_markers: list = []

    def set_data(self, phd2: PHD2Parser, nina: Optional[NINAParser] = None):
        """Set the PHD2 data to display."""
        self._phd2_parser = phd2
        self._nina_parser = nina
        self._update_chart()
        # Reset zoom/pan to show all data
        self.plot_widget.enableAutoRange()
        self.plot_widget.autoRange()

    def _get_granularity_seconds(self) -> int:
        """Get the selected granularity in seconds."""
        text = self.granularity_combo.currentText()
        mapping = {"1 min": 60, "5 min": 300, "10 min": 600, "30 min": 1800}
        return mapping.get(text, 60)

    def get_dither_margin(self) -> float:
        """Get the current dither margin in seconds."""
        return self.dither_margin_spin.value()

    def is_dither_excluded(self) -> bool:
        """Check if dither exclusion is enabled."""
        return self.exclude_dither_cb.isChecked()

    def _on_settings_changed(self):
        """Handle any settings change."""
        self._update_chart()
        # Emit signal so other widgets can update
        self.ditherSettingsChanged.emit(
            self.get_dither_margin(),
            self.is_dither_excluded()
        )

    def _update_chart(self):
        """Update the chart with current data and granularity."""
        self.plot_widget.clear()

        if not self._phd2_parser:
            return

        interval = self._get_granularity_seconds()
        dither_margin = self.get_dither_margin()
        exclude_dither = self.is_dither_excluded()

        # Get dither events if NINA data available and exclusion is enabled
        dither_events = None
        if self._nina_parser and exclude_dither:
            dither_events = self._nina_parser.dither_events

        # Get RMS data, optionally excluding dither periods
        rms_data = self._phd2_parser.get_rms_over_time(
            interval,
            dither_events=dither_events,
            dither_margin_seconds=dither_margin
        )

        if not rms_data:
            return

        # Convert to arrays for plotting - use actual timestamps
        times = [d[0].timestamp() for d in rms_data]  # Unix timestamps
        ra_rms = [d[1] for d in rms_data]
        dec_rms = [d[2] for d in rms_data]
        total_rms = [d[3] for d in rms_data]

        min_time = min(times) if times else 0
        max_time = max(times) if times else 1

        # Plot lines
        pen_ra = pg.mkPen(color='#2196F3', width=2)
        pen_dec = pg.mkPen(color='#4CAF50', width=2)
        pen_total = pg.mkPen(color='#F44336', width=2)

        self.plot_widget.plot(times, ra_rms, pen=pen_ra, name='RA RMS')
        self.plot_widget.plot(times, dec_rms, pen=pen_dec, name='Dec RMS')
        self.plot_widget.plot(times, total_rms, pen=pen_total, name='Total RMS')

        # Add event markers if NINA data available
        if self._nina_parser:
            # Dither markers (shaded regions) - only show if exclusion is enabled
            if exclude_dither:
                for dither in self._nina_parser.dither_events:
                    dither_start = dither.start_time.timestamp() - dither_margin
                    dither_end = (dither.end_time or dither.start_time).timestamp() + dither_margin

                    if min_time <= dither_start <= max_time or min_time <= dither_end <= max_time:
                        # Create a shaded region for dither
                        region = pg.LinearRegionItem(
                            values=[dither_start, dither_end],
                            brush=pg.mkBrush(255, 193, 7, 50),  # Yellow with transparency
                            pen=pg.mkPen(None),
                            movable=False
                        )
                        self.plot_widget.addItem(region)

            # Autofocus markers
            for af in self._nina_parser.autofocus_runs:
                af_time = af.timestamp.timestamp()
                if min_time <= af_time <= max_time:
                    line = pg.InfiniteLine(
                        pos=af_time, angle=90,
                        pen=pg.mkPen('#9C27B0', width=1, style=Qt.PenStyle.DashLine)
                    )
                    self.plot_widget.addItem(line)

            # Meridian flip markers
            for flip in self._nina_parser.meridian_flips:
                flip_time = flip.timestamp.timestamp()
                if min_time <= flip_time <= max_time:
                    line = pg.InfiniteLine(
                        pos=flip_time, angle=90,
                        pen=pg.mkPen('#FF9800', width=2, style=Qt.PenStyle.DashLine)
                    )
                    self.plot_widget.addItem(line)


class HFRChartWidget(QWidget):
    """Widget displaying HFR per sub chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.addWidget(QLabel("HFR per Sub"))
        header.addStretch()
        layout.addLayout(header)

        # PyQtGraph plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'HFR', units='px')
        self.plot_widget.setLabel('bottom', 'Sub #')

        layout.addWidget(self.plot_widget)

    def set_data(self, nina: NINAParser):
        """Set the NINA data to display."""
        self.plot_widget.clear()

        hfr_data = nina.get_hfr_over_time()
        if not hfr_data:
            # Reset view even if no data
            self.plot_widget.enableAutoRange()
            return

        # Group by filter
        filters: dict[str, list[tuple[int, float]]] = {}
        for i, (ts, hfr, filter_name) in enumerate(hfr_data):
            if filter_name not in filters:
                filters[filter_name] = []
            filters[filter_name].append((i + 1, hfr))

        # Color palette for filters
        colors = ['#2196F3', '#4CAF50', '#F44336', '#FF9800', '#9C27B0', '#00BCD4']

        for idx, (filter_name, data) in enumerate(filters.items()):
            x = [d[0] for d in data]
            y = [d[1] for d in data]
            color = colors[idx % len(colors)]

            self.plot_widget.plot(
                x, y,
                pen=None,
                symbol='o',
                symbolSize=8,
                symbolBrush=color,
                name=filter_name or 'Unknown'
            )

        self.plot_widget.addLegend()
        # Reset zoom/pan to show all data
        self.plot_widget.enableAutoRange()
        self.plot_widget.autoRange()


class AutofocusTableWidget(QGroupBox):
    """Table widget displaying autofocus runs."""

    def __init__(self, parent=None):
        super().__init__("Autofocus Runs", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Time", "Trigger", "Filter", "Position", "HFR", "Temp"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def set_data(self, nina: NINAParser):
        """Set the NINA data to display."""
        if not nina.autofocus_runs:
            self.table.setRowCount(1)
            no_data_item = QTableWidgetItem("No autofocus runs in this session")
            no_data_item.setForeground(QBrush(QColor("#999")))
            self.table.setItem(0, 0, no_data_item)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            return

        self.table.setRowCount(len(nina.autofocus_runs))
        self.table.setSpan(0, 0, 1, 1)

        for row, af in enumerate(nina.autofocus_runs):
            self.table.setItem(row, 0, QTableWidgetItem(af.timestamp.strftime("%H:%M:%S")))
            self.table.setItem(row, 1, QTableWidgetItem(af.trigger.replace("AutofocusAfter", "")))
            self.table.setItem(row, 2, QTableWidgetItem(af.filter_name))
            self.table.setItem(row, 3, QTableWidgetItem(str(af.final_position)))
            self.table.setItem(row, 4, QTableWidgetItem(f"{af.final_hfr:.2f}" if af.final_hfr else "-"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{af.temperature:.1f}°" if af.temperature else "-"))


class ExposuresTableWidget(QGroupBox):
    """Table widget displaying exposures/subs."""

    def __init__(self, parent=None):
        super().__init__("Exposures", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Time", "Filter", "Exp", "HFR", "Stars",
            "RA RMS", "Dec RMS", "Total RMS", "Frames"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def set_data(self, nina: NINAParser):
        """Set the NINA data to display."""
        if not nina.exposures:
            self.table.setRowCount(1)
            no_data_item = QTableWidgetItem("No LIGHT frames saved in this session")
            no_data_item.setForeground(QBrush(QColor("#999")))
            self.table.setItem(0, 0, no_data_item)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            return

        self.table.setRowCount(len(nina.exposures))
        # Clear any previous span
        self.table.setSpan(0, 0, 1, 1)

        for row, exp in enumerate(nina.exposures):
            self.table.setItem(row, 0, QTableWidgetItem(exp.timestamp.strftime("%H:%M:%S")))
            self.table.setItem(row, 1, QTableWidgetItem(exp.filter_name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{exp.exposure_time:.0f}s"))

            hfr_item = QTableWidgetItem(f"{exp.hfr:.2f}" if exp.hfr else "-")
            if exp.hfr and exp.hfr > 3.0:  # Highlight high HFR
                hfr_item.setBackground(QBrush(QColor("#FFCDD2")))
            self.table.setItem(row, 3, hfr_item)

            self.table.setItem(row, 4, QTableWidgetItem(str(exp.stars_detected) if exp.stars_detected else "-"))

            # Guiding RMS columns
            ra_item = QTableWidgetItem(f"{exp.ra_rms:.2f}\"" if exp.ra_rms else "-")
            dec_item = QTableWidgetItem(f"{exp.dec_rms:.2f}\"" if exp.dec_rms else "-")
            total_item = QTableWidgetItem(f"{exp.total_rms:.2f}\"" if exp.total_rms else "-")
            frames_item = QTableWidgetItem(str(exp.guiding_frames) if exp.guiding_frames else "-")

            # Highlight poor guiding
            if exp.total_rms and exp.total_rms > 1.0:
                for item in [ra_item, dec_item, total_item]:
                    item.setBackground(QBrush(QColor("#FFCDD2")))
            elif exp.total_rms and exp.total_rms > 0.6:
                for item in [ra_item, dec_item, total_item]:
                    item.setBackground(QBrush(QColor("#FFF9C4")))

            self.table.setItem(row, 5, ra_item)
            self.table.setItem(row, 6, dec_item)
            self.table.setItem(row, 7, total_item)
            self.table.setItem(row, 8, frames_item)


class EventsListWidget(QGroupBox):
    """Widget displaying session events in chronological order."""

    def __init__(self, parent=None):
        super().__init__("Events", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Time", "Type", "Details"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def set_data(self, phd2: Optional[PHD2Parser], nina: Optional[NINAParser]):
        """Set the data to display."""
        events: list[tuple[datetime, str, str, str]] = []  # (time, type, details, color)

        if nina:
            # Autofocus events
            for af in nina.autofocus_runs:
                events.append((
                    af.timestamp,
                    "Autofocus",
                    f"{af.filter_name} - HFR: {af.final_hfr:.2f}" if af.final_hfr else af.filter_name,
                    "#E1BEE7"
                ))

            # Filter changes
            for fc in nina.filter_changes:
                events.append((
                    fc.timestamp,
                    "Filter",
                    f"Changed to {fc.filter_name}",
                    "#B3E5FC"
                ))

            # Meridian flips
            for flip in nina.meridian_flips:
                events.append((
                    flip.timestamp,
                    "Meridian Flip",
                    f"{flip.from_pier_side} -> {flip.to_pier_side}",
                    "#FFE0B2"
                ))

            # RMS alerts
            for alert in nina.rms_alerts:
                events.append((
                    alert.timestamp,
                    "RMS Alert",
                    f"Total: {alert.total_rms:.2f}\" (threshold: {alert.threshold}\")",
                    "#FFCDD2"
                ))

            # Dither events
            for dither in nina.dither_events:
                duration = dither.duration_seconds
                events.append((
                    dither.start_time,
                    "Dither",
                    f"Duration: {duration:.1f}s",
                    "#FFF9C4"  # Light yellow
                ))

        if phd2:
            # Guiding session start/end
            for session in phd2.sessions:
                events.append((
                    session.start_time,
                    "Guiding Start",
                    f"Pier: {session.pier_side}, Alt: {session.altitude:.1f}°",
                    "#C8E6C9"
                ))
                if session.end_time:
                    events.append((
                        session.end_time,
                        "Guiding End",
                        f"RMS: {session.total_rms:.2f}\"",
                        "#FFCCBC"
                    ))

        # Sort by time
        events.sort(key=lambda x: x[0])

        self.table.setRowCount(len(events))
        for row, (time, event_type, details, color) in enumerate(events):
            time_item = QTableWidgetItem(time.strftime("%H:%M:%S"))
            type_item = QTableWidgetItem(event_type)
            details_item = QTableWidgetItem(details)

            bg = QBrush(QColor(color))
            time_item.setBackground(bg)
            type_item.setBackground(bg)
            details_item.setBackground(bg)

            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, type_item)
            self.table.setItem(row, 2, details_item)


class GuidingSessionsTableWidget(QGroupBox):
    """Table widget displaying guiding sessions from PHD2."""

    def __init__(self, parent=None):
        super().__init__("Guiding Sessions", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Start", "Duration", "Pier", "RA RMS", "Dec RMS", "Total RMS", "Frames"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def set_data(self, phd2: PHD2Parser):
        """Set the PHD2 data to display."""
        self.table.setRowCount(len(phd2.sessions))

        for row, session in enumerate(phd2.sessions):
            self.table.setItem(row, 0, QTableWidgetItem(session.start_time.strftime("%H:%M:%S")))

            duration_mins = session.duration_seconds / 60
            self.table.setItem(row, 1, QTableWidgetItem(f"{duration_mins:.1f}m"))

            self.table.setItem(row, 2, QTableWidgetItem(session.pier_side))

            ra_item = QTableWidgetItem(f"{session.ra_rms:.2f}\"")
            if session.ra_rms > 1.0:
                ra_item.setBackground(QBrush(QColor("#FFCDD2")))
            self.table.setItem(row, 3, ra_item)

            dec_item = QTableWidgetItem(f"{session.dec_rms:.2f}\"")
            if session.dec_rms > 1.0:
                dec_item.setBackground(QBrush(QColor("#FFCDD2")))
            self.table.setItem(row, 4, dec_item)

            total_item = QTableWidgetItem(f"{session.total_rms:.2f}\"")
            if session.total_rms > 1.5:
                total_item.setBackground(QBrush(QColor("#FFCDD2")))
            self.table.setItem(row, 5, total_item)

            self.table.setItem(row, 6, QTableWidgetItem(str(len(session.frames))))


class SessionSelectorDialog(QDialog):
    """Dialog for selecting a session from discovered log files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Session")
        self.setMinimumSize(600, 500)

        self._nina_folder: Optional[Path] = None
        self._phd2_folder: Optional[Path] = None
        self._sessions: list = []
        self._selected_session = None
        self._selected_nina_log: Optional[Path] = None
        self._selected_phd2_log: Optional[Path] = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Folder configuration
        folders_group = QGroupBox("Log Folders")
        folders_layout = QFormLayout(folders_group)

        # NINA folder
        nina_row = QHBoxLayout()
        self.nina_folder_edit = QLineEdit()
        self.nina_folder_edit.setPlaceholderText("Select NINA logs folder...")
        self.nina_folder_edit.setReadOnly(True)
        nina_row.addWidget(self.nina_folder_edit)
        nina_browse_btn = QPushButton("Browse...")
        nina_browse_btn.clicked.connect(self._browse_nina_folder)
        nina_row.addWidget(nina_browse_btn)
        folders_layout.addRow("NINA Logs:", nina_row)

        # PHD2 folder
        phd2_row = QHBoxLayout()
        self.phd2_folder_edit = QLineEdit()
        self.phd2_folder_edit.setPlaceholderText("Select PHD2 logs folder...")
        self.phd2_folder_edit.setReadOnly(True)
        phd2_row.addWidget(self.phd2_folder_edit)
        phd2_browse_btn = QPushButton("Browse...")
        phd2_browse_btn.clicked.connect(self._browse_phd2_folder)
        phd2_row.addWidget(phd2_browse_btn)
        folders_layout.addRow("PHD2 Logs:", phd2_row)

        # Scan button
        self.scan_btn = QPushButton("Scan for Sessions")
        self.scan_btn.clicked.connect(self._scan_folders)
        folders_layout.addRow("", self.scan_btn)

        layout.addWidget(folders_group)

        # Sessions list
        sessions_group = QGroupBox("Available Sessions")
        sessions_layout = QVBoxLayout(sessions_group)

        self.sessions_list = QListWidget()
        self.sessions_list.itemSelectionChanged.connect(self._on_session_selected)
        self.sessions_list.itemDoubleClicked.connect(self._on_session_double_clicked)
        sessions_layout.addWidget(self.sessions_list)

        # Log file details
        details_layout = QHBoxLayout()

        # NINA log selector
        nina_details = QVBoxLayout()
        nina_details.addWidget(QLabel("NINA Log:"))
        self.nina_log_combo = QComboBox()
        self.nina_log_combo.setMinimumWidth(200)
        nina_details.addWidget(self.nina_log_combo)
        details_layout.addLayout(nina_details)

        # PHD2 log selector
        phd2_details = QVBoxLayout()
        phd2_details.addWidget(QLabel("PHD2 Log:"))
        self.phd2_log_combo = QComboBox()
        self.phd2_log_combo.setMinimumWidth(200)
        phd2_details.addWidget(self.phd2_log_combo)
        details_layout.addLayout(phd2_details)

        sessions_layout.addLayout(details_layout)
        layout.addWidget(sessions_group, stretch=1)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.ok_button.setText("Load Session")
        layout.addWidget(button_box)

    def _browse_nina_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select NINA Logs Folder",
            str(self._nina_folder) if self._nina_folder else ""
        )
        if folder:
            self._nina_folder = Path(folder)
            self.nina_folder_edit.setText(str(self._nina_folder))

    def _browse_phd2_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select PHD2 Logs Folder",
            str(self._phd2_folder) if self._phd2_folder else ""
        )
        if folder:
            self._phd2_folder = Path(folder)
            self.phd2_folder_edit.setText(str(self._phd2_folder))

    def _scan_folders(self):
        from parsers import SessionFinder

        if not self._nina_folder and not self._phd2_folder:
            QMessageBox.warning(
                self, "No Folders Selected",
                "Please select at least one log folder to scan."
            )
            return

        finder = SessionFinder(self._nina_folder, self._phd2_folder)
        self._sessions = finder.get_matching_sessions()

        self.sessions_list.clear()
        self.nina_log_combo.clear()
        self.phd2_log_combo.clear()

        if not self._sessions:
            self.sessions_list.addItem("No matching sessions found")
            self.ok_button.setEnabled(False)
            return

        for session in self._sessions:
            item = QListWidgetItem(session.display_name)
            item.setData(Qt.ItemDataRole.UserRole, session)
            self.sessions_list.addItem(item)

    def _on_session_selected(self):
        selected_items = self.sessions_list.selectedItems()
        if not selected_items:
            self.ok_button.setEnabled(False)
            return

        session = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if not session:
            self.ok_button.setEnabled(False)
            return

        self._selected_session = session

        # Populate NINA log combo
        self.nina_log_combo.clear()
        for log in sorted(session.nina_logs):
            self.nina_log_combo.addItem(log.name, log)

        # Populate PHD2 log combo
        self.phd2_log_combo.clear()
        for log in sorted(session.phd2_logs):
            self.phd2_log_combo.addItem(log.name, log)

        self.ok_button.setEnabled(True)

    def _on_session_double_clicked(self, item):
        self._on_accept()

    def _on_accept(self):
        if self.nina_log_combo.currentIndex() >= 0:
            self._selected_nina_log = self.nina_log_combo.currentData()
        if self.phd2_log_combo.currentIndex() >= 0:
            self._selected_phd2_log = self.phd2_log_combo.currentData()
        self.accept()

    def get_selected_logs(self) -> tuple[Optional[Path], Optional[Path]]:
        """Get the selected log files (nina_path, phd2_path)."""
        return self._selected_nina_log, self._selected_phd2_log

    def set_folders(self, nina_folder: Optional[Path], phd2_folder: Optional[Path]):
        """Pre-set the log folders."""
        if nina_folder:
            self._nina_folder = nina_folder
            self.nina_folder_edit.setText(str(nina_folder))
        if phd2_folder:
            self._phd2_folder = phd2_folder
            self.phd2_folder_edit.setText(str(phd2_folder))
