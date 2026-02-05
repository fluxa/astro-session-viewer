"""
Configuration management for Astro Session Viewer.
"""
import json
from pathlib import Path
from typing import Optional
import sys


def get_config_dir() -> Path:
    """Get the configuration directory for the application."""
    if sys.platform == 'win32':
        # Windows: Use AppData/Local
        base = Path.home() / 'AppData' / 'Local'
    elif sys.platform == 'darwin':
        # macOS: Use Application Support
        base = Path.home() / 'Library' / 'Application Support'
    else:
        # Linux: Use .config
        base = Path.home() / '.config'

    config_dir = base / 'AstroSessionViewer'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / 'config.json'


class Config:
    """Application configuration with persistence."""

    def __init__(self):
        self._config = {
            'nina_folder': None,
            'phd2_folder': None,
            'dither_margin': 3.0,
            'exclude_dither': True,
            'granularity_minutes': 1,
            'window_geometry': None,
        }
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        config_path = get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self._config.update(saved)
            except (json.JSONDecodeError, IOError):
                # If config is corrupted, use defaults
                pass

    def save(self) -> None:
        """Save configuration to file."""
        config_path = get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2)
        except IOError:
            pass  # Silently fail if we can't write

    @property
    def nina_folder(self) -> Optional[Path]:
        """Get the NINA logs folder path."""
        path = self._config.get('nina_folder')
        return Path(path) if path else None

    @nina_folder.setter
    def nina_folder(self, value: Optional[Path]) -> None:
        """Set the NINA logs folder path."""
        self._config['nina_folder'] = str(value) if value else None
        self.save()

    @property
    def phd2_folder(self) -> Optional[Path]:
        """Get the PHD2 logs folder path."""
        path = self._config.get('phd2_folder')
        return Path(path) if path else None

    @phd2_folder.setter
    def phd2_folder(self, value: Optional[Path]) -> None:
        """Set the PHD2 logs folder path."""
        self._config['phd2_folder'] = str(value) if value else None
        self.save()

    @property
    def dither_margin(self) -> float:
        """Get the dither margin in seconds."""
        return self._config.get('dither_margin', 3.0)

    @dither_margin.setter
    def dither_margin(self, value: float) -> None:
        """Set the dither margin in seconds."""
        self._config['dither_margin'] = value
        self.save()

    @property
    def exclude_dither(self) -> bool:
        """Get whether to exclude dither from RMS calculations."""
        return self._config.get('exclude_dither', True)

    @exclude_dither.setter
    def exclude_dither(self, value: bool) -> None:
        """Set whether to exclude dither from RMS calculations."""
        self._config['exclude_dither'] = value
        self.save()

    @property
    def granularity_minutes(self) -> int:
        """Get the RMS chart granularity in minutes."""
        return self._config.get('granularity_minutes', 1)

    @granularity_minutes.setter
    def granularity_minutes(self, value: int) -> None:
        """Set the RMS chart granularity in minutes."""
        self._config['granularity_minutes'] = value
        self.save()

    @property
    def window_geometry(self) -> Optional[dict]:
        """Get the saved window geometry."""
        return self._config.get('window_geometry')

    @window_geometry.setter
    def window_geometry(self, value: Optional[dict]) -> None:
        """Set the window geometry."""
        self._config['window_geometry'] = value
        self.save()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
