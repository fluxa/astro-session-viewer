"""
Log parsers for PHD2 and NINA log files.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import numpy as np


@dataclass
class GuidingFrame:
    """Single guiding frame data from PHD2."""
    frame: int
    time: float
    dx: float
    dy: float
    ra_raw: float
    dec_raw: float
    ra_guide: float
    dec_guide: float
    ra_duration: int
    dec_duration: int
    ra_direction: str
    dec_direction: str
    star_mass: float
    snr: float
    error_code: int


@dataclass
class GuidingSession:
    """A single guiding session from PHD2."""
    start_time: datetime
    end_time: Optional[datetime] = None
    equipment_profile: str = ""
    pixel_scale: float = 0.0
    focal_length: int = 0
    ra: float = 0.0
    dec: float = 0.0
    hour_angle: float = 0.0
    pier_side: str = ""
    altitude: float = 0.0
    azimuth: float = 0.0
    frames: list = field(default_factory=list)

    @property
    def ra_rms(self) -> float:
        """RA RMS in arcseconds."""
        if not self.frames:
            return 0.0
        ra_values = [f.ra_raw for f in self.frames]
        # Raw values are in pixels, multiply by pixel_scale to get arcseconds
        rms_px = float(np.sqrt(np.mean(np.square(ra_values))))
        return rms_px * self.pixel_scale if self.pixel_scale else rms_px

    @property
    def dec_rms(self) -> float:
        """Dec RMS in arcseconds."""
        if not self.frames:
            return 0.0
        dec_values = [f.dec_raw for f in self.frames]
        # Raw values are in pixels, multiply by pixel_scale to get arcseconds
        rms_px = float(np.sqrt(np.mean(np.square(dec_values))))
        return rms_px * self.pixel_scale if self.pixel_scale else rms_px

    @property
    def total_rms(self) -> float:
        """Total RMS in arcseconds."""
        if not self.frames:
            return 0.0
        return float(np.sqrt(self.ra_rms**2 + self.dec_rms**2))

    @property
    def duration_seconds(self) -> float:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


@dataclass
class AutofocusRun:
    """Autofocus run data from NINA."""
    timestamp: datetime
    trigger: str = ""
    filter_name: str = ""
    initial_position: int = 0
    final_position: int = 0
    final_hfr: float = 0.0
    temperature: Optional[float] = None


@dataclass
class Exposure:
    """Exposure data from NINA."""
    timestamp: datetime
    exposure_time: float
    filter_name: str
    gain: int
    offset: int
    binning: str
    image_type: str = "LIGHT"
    hfr: Optional[float] = None
    stars_detected: Optional[int] = None
    saved_path: Optional[str] = None
    # Guiding RMS during this exposure (populated by correlate_guiding_data)
    ra_rms: Optional[float] = None
    dec_rms: Optional[float] = None
    total_rms: Optional[float] = None
    guiding_frames: int = 0


@dataclass
class FilterChange:
    """Filter change event from NINA."""
    timestamp: datetime
    filter_name: str
    position: int


@dataclass
class MeridianFlip:
    """Meridian flip event from NINA."""
    timestamp: datetime
    from_pier_side: str
    to_pier_side: str


@dataclass
class RMSAlert:
    """RMS threshold alert from NINA."""
    timestamp: datetime
    total_rms: float
    ra_rms: float
    dec_rms: float
    threshold: float


@dataclass
class DitherEvent:
    """Dither event from NINA."""
    start_time: datetime
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class PHD2Parser:
    """Parser for PHD2 guide log files."""

    def __init__(self):
        self.sessions: list[GuidingSession] = []
        self.log_date: Optional[datetime] = None

    def parse(self, filepath: str | Path) -> list[GuidingSession]:
        """Parse a PHD2 guide log file."""
        self.sessions = []
        current_session: Optional[GuidingSession] = None

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()

                # Parse log start date
                if line.startswith("PHD2 version"):
                    match = re.search(r'Log enabled at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if match:
                        self.log_date = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")

                # Guiding session start
                elif line.startswith("Guiding Begins at"):
                    match = re.search(r'Guiding Begins at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if match:
                        current_session = GuidingSession(
                            start_time=datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                        )

                # Equipment profile
                elif line.startswith("Equipment Profile") and current_session:
                    match = re.search(r'Equipment Profile = (.+)', line)
                    if match:
                        current_session.equipment_profile = match.group(1)

                # Pixel scale and focal length
                elif line.startswith("Pixel scale") and current_session:
                    match = re.search(r'Pixel scale = ([\d.]+).*Focal length = (\d+)', line)
                    if match:
                        current_session.pixel_scale = float(match.group(1))
                        current_session.focal_length = int(match.group(2))

                # RA, Dec, Hour angle, Pier side
                elif line.startswith("RA =") and current_session:
                    match = re.search(
                        r'RA = ([\d.]+) hr, Dec = ([-\d.]+) deg, Hour angle = ([-\d.]+) hr, '
                        r'Pier side = (\w+).*Alt = ([\d.]+) deg, Az = ([\d.]+) deg',
                        line
                    )
                    if match:
                        current_session.ra = float(match.group(1))
                        current_session.dec = float(match.group(2))
                        current_session.hour_angle = float(match.group(3))
                        current_session.pier_side = match.group(4)
                        current_session.altitude = float(match.group(5))
                        current_session.azimuth = float(match.group(6))

                # Guiding frame data (CSV format)
                elif current_session and re.match(r'^\d+,', line):
                    frame = self._parse_frame(line)
                    if frame:
                        current_session.frames.append(frame)

                # Guiding session end
                elif line.startswith("Guiding Ends at"):
                    match = re.search(r'Guiding Ends at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if match and current_session:
                        current_session.end_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                        self.sessions.append(current_session)
                        current_session = None

        return self.sessions

    def _parse_frame(self, line: str) -> Optional[GuidingFrame]:
        """Parse a single guiding frame line."""
        parts = line.split(',')
        if len(parts) < 18:
            return None

        try:
            return GuidingFrame(
                frame=int(parts[0]),
                time=float(parts[1]),
                dx=float(parts[3]),
                dy=float(parts[4]),
                ra_raw=float(parts[5]),
                dec_raw=float(parts[6]),
                ra_guide=float(parts[7]),
                dec_guide=float(parts[8]),
                ra_duration=int(parts[9]) if parts[9] else 0,
                dec_duration=int(parts[11]) if parts[11] else 0,
                ra_direction=parts[10] if parts[10] else "",
                dec_direction=parts[12] if parts[12] else "",
                star_mass=float(parts[15]) if parts[15] else 0.0,
                snr=float(parts[16]) if parts[16] else 0.0,
                error_code=int(parts[17]) if parts[17] else 0,
            )
        except (ValueError, IndexError):
            return None

    def get_rms_over_time(
        self,
        interval_seconds: float = 60,
        dither_events: Optional[list] = None,
        dither_margin_seconds: float = 3.0
    ) -> list[tuple[datetime, float, float, float]]:
        """Calculate RMS values over time intervals across all sessions.

        Args:
            interval_seconds: Time interval for RMS buckets.
            dither_events: List of DitherEvent objects to exclude from calculations.
            dither_margin_seconds: Additional margin before/after dither to exclude.

        Returns list of (timestamp, ra_rms, dec_rms, total_rms) in arcseconds.
        """
        results = []

        for session in self.sessions:
            if not session.frames:
                continue

            pixel_scale = session.pixel_scale or 1.0
            current_bucket: list[GuidingFrame] = []
            bucket_start = session.start_time

            for frame in session.frames:
                frame_time = session.start_time.timestamp() + frame.time
                frame_dt = datetime.fromtimestamp(frame_time)

                # Check if frame is during a dither event (with margin)
                if dither_events and self._is_during_dither(frame_dt, dither_events, dither_margin_seconds):
                    continue  # Skip this frame

                if (frame_dt - bucket_start).total_seconds() >= interval_seconds:
                    if current_bucket:
                        ra_vals = [f.ra_raw for f in current_bucket]
                        dec_vals = [f.dec_raw for f in current_bucket]
                        # Convert from pixels to arcseconds
                        ra_rms = float(np.sqrt(np.mean(np.square(ra_vals)))) * pixel_scale
                        dec_rms = float(np.sqrt(np.mean(np.square(dec_vals)))) * pixel_scale
                        total_rms = float(np.sqrt(ra_rms**2 + dec_rms**2))
                        results.append((bucket_start, ra_rms, dec_rms, total_rms))

                    bucket_start = frame_dt
                    current_bucket = [frame]
                else:
                    current_bucket.append(frame)

            # Don't forget the last bucket
            if current_bucket:
                ra_vals = [f.ra_raw for f in current_bucket]
                dec_vals = [f.dec_raw for f in current_bucket]
                # Convert from pixels to arcseconds
                ra_rms = float(np.sqrt(np.mean(np.square(ra_vals)))) * pixel_scale
                dec_rms = float(np.sqrt(np.mean(np.square(dec_vals)))) * pixel_scale
                total_rms = float(np.sqrt(ra_rms**2 + dec_rms**2))
                results.append((bucket_start, ra_rms, dec_rms, total_rms))

        return results

    def _is_during_dither(
        self,
        timestamp: datetime,
        dither_events: list,
        margin_seconds: float
    ) -> bool:
        """Check if a timestamp falls within a dither event (with margin)."""
        from datetime import timedelta
        margin = timedelta(seconds=margin_seconds)

        for dither in dither_events:
            start = dither.start_time - margin
            end = (dither.end_time or dither.start_time) + margin
            if start <= timestamp <= end:
                return True
        return False

    def get_overall_rms(
        self,
        dither_events: Optional[list] = None,
        dither_margin_seconds: float = 3.0
    ) -> tuple[float, float, float]:
        """Calculate overall RMS across all sessions, excluding dither periods.

        Returns (ra_rms, dec_rms, total_rms) in arcseconds.
        """
        all_ra = []
        all_dec = []
        pixel_scale = 1.0

        for session in self.sessions:
            # Use the pixel scale from the first session that has one
            if session.pixel_scale:
                pixel_scale = session.pixel_scale

            for frame in session.frames:
                frame_time = session.start_time.timestamp() + frame.time
                frame_dt = datetime.fromtimestamp(frame_time)

                # Skip frames during dither
                if dither_events and self._is_during_dither(frame_dt, dither_events, dither_margin_seconds):
                    continue

                all_ra.append(frame.ra_raw)
                all_dec.append(frame.dec_raw)

        if not all_ra:
            return (0.0, 0.0, 0.0)

        # Convert from pixels to arcseconds
        ra_rms = float(np.sqrt(np.mean(np.square(all_ra)))) * pixel_scale
        dec_rms = float(np.sqrt(np.mean(np.square(all_dec)))) * pixel_scale
        total_rms = float(np.sqrt(ra_rms**2 + dec_rms**2))

        return (ra_rms, dec_rms, total_rms)


class NINAParser:
    """Parser for NINA log files."""

    def __init__(self):
        self.autofocus_runs: list[AutofocusRun] = []
        self.exposures: list[Exposure] = []
        self.filter_changes: list[FilterChange] = []
        self.meridian_flips: list[MeridianFlip] = []
        self.rms_alerts: list[RMSAlert] = []
        self.dither_events: list[DitherEvent] = []
        self.target_name: str = ""
        self.session_start: Optional[datetime] = None
        self.session_end: Optional[datetime] = None
        self._current_filter: str = ""
        self._current_pier_side: str = ""
        self._pending_af: Optional[AutofocusRun] = None
        self._pending_exposure: Optional[Exposure] = None
        self._pending_dither: Optional[DitherEvent] = None
        self._last_hfr: Optional[float] = None
        self._last_stars: Optional[int] = None

    def parse(self, filepath: str | Path) -> None:
        """Parse a NINA log file."""
        self.autofocus_runs = []
        self.exposures = []
        self.filter_changes = []
        self.meridian_flips = []
        self.rms_alerts = []

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                self._parse_line(line)

    def _parse_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from NINA log line."""
        match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)', line)
        if match:
            ts_str = match.group(1)[:23]  # Truncate to milliseconds
            try:
                return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                return datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
        return None

    def _parse_line(self, line: str) -> None:
        """Parse a single log line."""
        timestamp = self._parse_timestamp(line)
        if not timestamp:
            return

        if not self.session_start:
            self.session_start = timestamp
        self.session_end = timestamp

        # Target name from DeepSkyObjectContainer
        if "DeepSkyObjectContainer" in line and "Target:" in line:
            match = re.search(r'Target:\s*(.+?)\s+RA:', line)
            if match:
                self.target_name = match.group(1).strip()

        # Autofocus start
        if "RunAutofocus" in line and "Starting" in line:
            self._pending_af = AutofocusRun(
                timestamp=timestamp,
                filter_name=self._current_filter
            )

        # Autofocus initial position
        if "Starting AutoFocus with initial position" in line and self._pending_af:
            match = re.search(r'initial position (\d+)', line)
            if match:
                self._pending_af.initial_position = int(match.group(1))

        # Autofocus trigger reason
        if "AutofocusAfter" in line and "Starting Trigger" in line:
            match = re.search(r'Trigger: (AutofocusAfter\w+)', line)
            if match and self._pending_af:
                self._pending_af.trigger = match.group(1)

        # Autofocus completion
        if "BroadcastSuccessfulAutoFocusRun" in line:
            match = re.search(r'Temperature ([\d.]+)', line)
            if match and self._pending_af:
                self._pending_af.temperature = float(match.group(1))

        if "AutoFocus completed" in line and self._pending_af:
            match = re.search(r'ending at (\d+)', line)
            if match:
                self._pending_af.final_position = int(match.group(1))
                if self._last_hfr:
                    self._pending_af.final_hfr = self._last_hfr
                self.autofocus_runs.append(self._pending_af)
                self._pending_af = None

        # HFR detection (Hocus Focus)
        if "HocusFocusStarDetection" in line and "Average HFR:" in line:
            match = re.search(r'Average HFR: ([\d.]+).*Detected Stars (\d+)', line)
            if match:
                self._last_hfr = float(match.group(1))
                self._last_stars = int(match.group(2))

        # Filter change
        if "FilterWheelVM" in line and "Moving to Filter" in line:
            match = re.search(r'Moving to Filter (\w+) at Position (\d+)', line)
            if match:
                new_filter = match.group(1)
                position = int(match.group(2))
                self.filter_changes.append(FilterChange(
                    timestamp=timestamp,
                    filter_name=new_filter,
                    position=position
                ))
                self._current_filter = new_filter

        # Exposure start
        if "CameraVM" in line and "Starting Exposure" in line:
            match = re.search(
                r'Exposure Time: ([\d.]+)s; Filter: (\w*); Gain: (\d+); Offset (\d+); Binning: (\d+x\d+)',
                line
            )
            if match:
                filter_name = match.group(2) if match.group(2) else self._current_filter
                # Update current filter if captured from exposure
                if filter_name:
                    self._current_filter = filter_name
                self._pending_exposure = Exposure(
                    timestamp=timestamp,
                    exposure_time=float(match.group(1)),
                    filter_name=filter_name,
                    gain=int(match.group(3)),
                    offset=int(match.group(4)),
                    binning=match.group(5)
                )

        # Saved LIGHT image
        if "SaveToDisk" in line and "LIGHT" in line:
            match = re.search(r'Saved image to (.+\.fits)', line)
            if match and self._pending_exposure:
                self._pending_exposure.saved_path = match.group(1)
                if self._last_hfr:
                    self._pending_exposure.hfr = self._last_hfr
                if self._last_stars:
                    self._pending_exposure.stars_detected = self._last_stars
                self.exposures.append(self._pending_exposure)
                self._pending_exposure = None

        # Pier side detection
        if "MeridianFlipTrigger" in line and "pier side" in line:
            match = re.search(r'pier side pier(\w+)', line)
            if match:
                new_pier_side = match.group(1)
                if self._current_pier_side and self._current_pier_side != new_pier_side:
                    self.meridian_flips.append(MeridianFlip(
                        timestamp=timestamp,
                        from_pier_side=self._current_pier_side,
                        to_pier_side=new_pier_side
                    ))
                self._current_pier_side = new_pier_side

        # RMS threshold alert
        if "InterruptWhenRMSAbove" in line and "Total RMS above threshold" in line:
            match = re.search(r'Total RMS above threshold \(([\d.]+) / ([\d.]+)\)', line)
            if match:
                alert = RMSAlert(
                    timestamp=timestamp,
                    total_rms=float(match.group(1)),
                    ra_rms=0.0,
                    dec_rms=0.0,
                    threshold=float(match.group(2))
                )
                self.rms_alerts.append(alert)

        # Dither start
        if "SequenceItem" in line and "Starting" in line and "Item: Dither" in line:
            self._pending_dither = DitherEvent(start_time=timestamp)

        # Dither end
        if "SequenceItem" in line and "Finishing" in line and "Item: Dither" in line:
            if self._pending_dither:
                self._pending_dither.end_time = timestamp
                self.dither_events.append(self._pending_dither)
                self._pending_dither = None

    def get_hfr_over_time(self) -> list[tuple[datetime, float, str]]:
        """Get HFR values over time from saved exposures.

        Returns list of (timestamp, hfr, filter_name).
        """
        return [
            (exp.timestamp, exp.hfr, exp.filter_name)
            for exp in self.exposures
            if exp.hfr is not None
        ]


def match_session_logs(phd2_path: str | Path, nina_path: str | Path) -> tuple[PHD2Parser, NINAParser]:
    """Parse and return both PHD2 and NINA parsers for a session."""
    phd2_parser = PHD2Parser()
    phd2_parser.parse(phd2_path)

    nina_parser = NINAParser()
    nina_parser.parse(nina_path)

    return phd2_parser, nina_parser


@dataclass
class DiscoveredSession:
    """A discovered session with matching log files."""
    session_date: date
    nina_logs: list[Path] = field(default_factory=list)
    phd2_logs: list[Path] = field(default_factory=list)

    @property
    def has_both(self) -> bool:
        """Check if session has both NINA and PHD2 logs."""
        return bool(self.nina_logs and self.phd2_logs)

    @property
    def display_name(self) -> str:
        """Get display name for session."""
        nina_count = len(self.nina_logs)
        phd2_count = len(self.phd2_logs)
        return f"{self.session_date.strftime('%Y-%m-%d')} ({nina_count} NINA, {phd2_count} PHD2)"


class SessionFinder:
    """Finds and matches NINA and PHD2 log files by date."""

    # Regex patterns for extracting dates from filenames
    NINA_PATTERN = re.compile(r'^(\d{4})(\d{2})(\d{2})-\d{6}.*\.log$')
    PHD2_PATTERN = re.compile(r'^PHD2_GuideLog_(\d{4})-(\d{2})-(\d{2})_\d{6}\.txt$')

    def __init__(self, nina_folder: Optional[Path] = None, phd2_folder: Optional[Path] = None):
        self.nina_folder = Path(nina_folder) if nina_folder else None
        self.phd2_folder = Path(phd2_folder) if phd2_folder else None
        self._sessions: dict[date, DiscoveredSession] = {}

    def set_nina_folder(self, folder: str | Path) -> None:
        """Set the NINA logs folder."""
        self.nina_folder = Path(folder)

    def set_phd2_folder(self, folder: str | Path) -> None:
        """Set the PHD2 logs folder."""
        self.phd2_folder = Path(folder)

    def scan(self) -> list[DiscoveredSession]:
        """Scan folders and find matching sessions."""
        self._sessions = {}

        # Scan NINA logs
        if self.nina_folder and self.nina_folder.exists():
            for log_file in self.nina_folder.glob('*.log'):
                session_date = self._extract_nina_date(log_file.name)
                if session_date:
                    if session_date not in self._sessions:
                        self._sessions[session_date] = DiscoveredSession(session_date=session_date)
                    self._sessions[session_date].nina_logs.append(log_file)

        # Scan PHD2 logs
        if self.phd2_folder and self.phd2_folder.exists():
            for log_file in self.phd2_folder.glob('PHD2_GuideLog_*.txt'):
                session_date = self._extract_phd2_date(log_file.name)
                if session_date:
                    if session_date not in self._sessions:
                        self._sessions[session_date] = DiscoveredSession(session_date=session_date)
                    self._sessions[session_date].phd2_logs.append(log_file)

        # Sort by date descending (newest first)
        return sorted(self._sessions.values(), key=lambda s: s.session_date, reverse=True)

    def get_matching_sessions(self) -> list[DiscoveredSession]:
        """Get only sessions that have both NINA and PHD2 logs."""
        return [s for s in self.scan() if s.has_both]

    def _extract_nina_date(self, filename: str) -> Optional[date]:
        """Extract date from NINA log filename."""
        match = self.NINA_PATTERN.match(filename)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                return None
        return None

    def _extract_phd2_date(self, filename: str) -> Optional[date]:
        """Extract date from PHD2 log filename."""
        match = self.PHD2_PATTERN.match(filename)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                return None
        return None


def correlate_guiding_with_exposures(
    phd2: PHD2Parser,
    nina: NINAParser,
    dither_events: Optional[list] = None,
    dither_margin_seconds: float = 3.0
) -> None:
    """Correlate PHD2 guiding data with NINA exposures.

    Calculates and populates RMS values (in arcseconds) for each exposure
    based on guiding frames that occurred during that exposure.

    Args:
        phd2: Parsed PHD2 data
        nina: Parsed NINA data (exposures will be modified in place)
        dither_events: Optional list of dither events to exclude
        dither_margin_seconds: Margin around dither events to exclude
    """
    from datetime import timedelta

    # Get pixel scale from PHD2 sessions (use first session that has one)
    pixel_scale = 1.0
    for session in phd2.sessions:
        if session.pixel_scale:
            pixel_scale = session.pixel_scale
            break

    for exposure in nina.exposures:
        # Calculate exposure time window
        exp_start = exposure.timestamp
        exp_end = exp_start + timedelta(seconds=exposure.exposure_time)

        # Collect guiding frames during this exposure
        ra_values = []
        dec_values = []

        for session in phd2.sessions:
            for frame in session.frames:
                # Calculate absolute time of this frame
                frame_time = session.start_time.timestamp() + frame.time
                frame_dt = datetime.fromtimestamp(frame_time)

                # Check if frame is within exposure window
                if exp_start <= frame_dt <= exp_end:
                    # Check if frame is during dither (skip if so)
                    if dither_events:
                        is_dither = False
                        margin = timedelta(seconds=dither_margin_seconds)
                        for dither in dither_events:
                            d_start = dither.start_time - margin
                            d_end = (dither.end_time or dither.start_time) + margin
                            if d_start <= frame_dt <= d_end:
                                is_dither = True
                                break
                        if is_dither:
                            continue

                    ra_values.append(frame.ra_raw)
                    dec_values.append(frame.dec_raw)

        # Calculate RMS for this exposure (in arcseconds)
        if ra_values:
            ra_rms_px = float(np.sqrt(np.mean(np.square(ra_values))))
            dec_rms_px = float(np.sqrt(np.mean(np.square(dec_values))))
            exposure.ra_rms = ra_rms_px * pixel_scale
            exposure.dec_rms = dec_rms_px * pixel_scale
            exposure.total_rms = float(np.sqrt(exposure.ra_rms**2 + exposure.dec_rms**2))
            exposure.guiding_frames = len(ra_values)
