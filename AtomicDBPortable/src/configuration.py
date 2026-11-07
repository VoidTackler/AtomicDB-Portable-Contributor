"""
AtomicDB Portable - Relocatable Configuration Manager
Ensures zero-footprint USB execution with drive-letter independence.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("AtomicDB.Config")

def get_base_dir() -> str:
    """
    Returns the absolute path to the portable application root.
    When running as a PyInstaller frozen binary, uses the directory containing the .exe.
    When running as a script, uses the parent directory of 'src'.
    """
    env_root = os.environ.get("ATOMICDB_PORTABLE_ROOT")
    if env_root and os.path.exists(env_root):
        return os.path.abspath(env_root)

    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(current_dir)

class PortableConfig:
    """Manages configuration file stored strictly on the portable storage device."""

    DEFAULT_CONFIG = {
        "client": {
            "device_name": "PortableWorker",
            "standalone": True
        },
        "openbench": {
            "server": "https://belzedar.duckdns.org",
            "username": "PortableExe",
            "password_encrypted": "TH9sV2h6en52eWs=",  # Caesar cipher encrypted "ExePassword"
            "jobs": 1,
            "engine_path": "",
            "syzygy_path": "",
            "no_fetch_syzygy": True,  # User requirement: no tablebase is always enabled by default
            "solve": False,
            "no_auto_update": False,
            "no_engine_update": False,
            "engine_update_minutes": 15.0,
            "once": False,
            "registered_url": "https://belzedar.duckdns.org/register/"
        },
        "resources": {
            "cpu_mode": "Adaptive",  # Default MUST be Adaptive per specifications
            "threads": 4,
            "hash_mb": 1024,
            "max_system_cpu_threshold_pct": 80,
            "hysteresis_cooldown_cycles": 3,
            "reserved_ram_mb": 1500
        },
        "engine": {
            "selected_binary": "atomic-stockfish-x64-avx2.exe",
            "verify_sha256": True,
            "auto_update": True,
            "known_good_binary": "atomic-stockfish-x64-modern.exe"
        },
        "safety": {
            "local_stop_active": False,
            "allow_remote_control": True
        }
    }

    def __init__(self, config_rel_path: str = "config/settings.json"):
        self.base_dir = get_base_dir()
        self.config_path = os.path.join(self.base_dir, config_rel_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.data: Dict[str, Any] = json.loads(json.dumps(self.DEFAULT_CONFIG))
        self.is_read_only = False
        self.load()

    def get_path(self, rel_path: str) -> str:
        """Resolve a path relative to the portable USB base directory."""
        return os.path.normpath(os.path.join(self.base_dir, rel_path))

    def load(self) -> bool:
        """Load configuration from disk. If not found, initializes default."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._deep_update(self.data, loaded)
                logger.info(f"Loaded portable configuration from: {self.config_path}")
                return True
            else:
                logger.info("Configuration file not found. Initializing defaults.")
                self.save()
                return True
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_path}: {e}")
            return False

    def save(self) -> bool:
        """Persist configuration to disk."""
        try:
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            return True
        except PermissionError:
            self.is_read_only = True
            logger.warning(f"Storage medium is read-only. Settings cannot be written to {self.config_path}")
            return False
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def _deep_update(self, target: dict, source: dict):
        for k, v in source.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                self._deep_update(target[k], v)
            else:
                target[k] = v

    def get(self, *keys, default=None):
        curr = self.data
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return default
        return curr

    def set(self, *keys_and_value):
        if len(keys_and_value) < 2:
            return
        keys = keys_and_value[:-1]
        val = keys_and_value[-1]
        curr = self.data
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = val
        self.save()
