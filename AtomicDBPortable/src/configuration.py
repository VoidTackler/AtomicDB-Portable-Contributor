"""
AtomicDB Portable - Relocatable Configuration Manager
Ensures zero-footprint USB execution with drive-letter independence.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("AtomicDB.Config")

_BUILTIN_USER_BYTES = (10, 53, 40, 46, 59, 56, 54, 63, 31, 34, 63)
_BUILTIN_PASS_BYTES = (31, 34, 63, 10, 59, 41, 41, 45, 53, 40, 62)


def get_builtin_credentials() -> Tuple[str, str]:
    return (
        bytes(b ^ 0x5A for b in _BUILTIN_USER_BYTES).decode("ascii"),
        bytes(b ^ 0x5A for b in _BUILTIN_PASS_BYTES).decode("ascii"),
    )


ACCOUNT_CONFIG_FILENAME = "account.txt"
DEFAULT_ACCOUNT_TEMPLATE = "USERNAME=\nPASSWORD=\n"


def get_base_dir() -> str:
    """Returns the portable application root directory."""
    env_root = os.environ.get("ATOMICDB_PORTABLE_ROOT")
    if env_root and os.path.exists(env_root):
        return os.path.abspath(env_root)
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PortableConfig:
    """Manages configuration stored strictly on the portable storage device."""

    DEFAULT_CONFIG = {
        "client": {"device_name": "PortableWorker", "standalone": True},
        "openbench": {
            "server": "https://belzedar.duckdns.org",
            "username": "",
            "password_encrypted": "",
            "jobs": 1,
            "engine_path": "",
            "syzygy_path": "",
            "no_fetch_syzygy": True,
            "solve": False,
            "no_auto_update": False,
            "no_engine_update": False,
            "engine_update_minutes": 15.0,
            "once": False,
        },
        "resources": {
            "cpu_mode": "Adaptive",
            "threads": 4,
            "hash_mb": 1024,
            "max_system_cpu_threshold_pct": 80,
            "hysteresis_cooldown_cycles": 3,
            "reserved_ram_mb": 1500,
        },
        "engine": {
            "selected_binary": "atomic-stockfish-x64-avx2.exe",
            "verify_sha256": True,
            "auto_update": True,
            "known_good_binary": "atomic-stockfish-x64-modern.exe",
        },
        "safety": {"local_stop_active": False},
    }

    def __init__(self, config_rel_path: str = "config/settings.json"):
        self.base_dir = get_base_dir()
        self.config_path = os.path.join(self.base_dir, config_rel_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.account_file_path = os.path.join(self.base_dir, ACCOUNT_CONFIG_FILENAME)
        self.data: Dict[str, Any] = json.loads(json.dumps(self.DEFAULT_CONFIG))
        self.is_read_only = False
        self.load()
        self.ensure_account_file()

    def get_path(self, rel_path: str) -> str:
        return os.path.normpath(os.path.join(self.base_dir, rel_path))

    def ensure_account_file(self) -> str:
        """Creates blank account.txt in the portable base directory if missing."""
        try:
            if not os.path.exists(self.account_file_path):
                with open(self.account_file_path, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_ACCOUNT_TEMPLATE)
        except PermissionError:
            self.is_read_only = True
        except Exception as e:
            logger.debug(f"Could not create account file at {self.account_file_path}: {e}")
        return self.account_file_path

    @staticmethod
    def _read_account_lines(path: str):
        with open(path, "rb") as fb:
            raw = fb.read()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        elif raw.startswith(b"\xef\xbb\xbf"):
            text = raw.decode("utf-8-sig")
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("cp1252", errors="replace")
        return text.splitlines()

    def _parse_account_file(self, path: str) -> Tuple[Optional[str], Optional[str]]:
        parsed_user: Optional[str] = None
        parsed_pass: Optional[str] = None
        if not os.path.exists(path):
            return parsed_user, parsed_pass
        for raw_line in self._read_account_lines(path):
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            sep = "=" if "=" in line else (":" if ":" in line else None)
            if not sep:
                continue
            key, val = (p.strip() for p in line.split(sep, 1))
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1].strip()
            key = key.upper()
            if key in ("USERNAME", "USER", "ACCOUNT") and val:
                parsed_user = val
            elif key in ("PASSWORD", "PASS") and val:
                parsed_pass = val
        return parsed_user, parsed_pass

    def get_account_credentials(self) -> Tuple[str, str]:
        """Reads USERNAME/PASSWORD from account.txt, falling back to built-in defaults when blank."""
        username, password = get_builtin_credentials()
        self.ensure_account_file()
        parsed_user: Optional[str] = None
        parsed_pass: Optional[str] = None
        try:
            parsed_user, parsed_pass = self._parse_account_file(self.account_file_path)
            if parsed_user is None and parsed_pass is None:
                cwd_account = os.path.abspath(os.path.join(os.getcwd(), ACCOUNT_CONFIG_FILENAME))
                if os.path.normcase(cwd_account) != os.path.normcase(os.path.abspath(self.account_file_path)):
                    parsed_user, parsed_pass = self._parse_account_file(cwd_account)
        except Exception as e:
            logger.warning(f"Failed to read {self.account_file_path}; using defaults: {e}")

        return parsed_user or username, parsed_pass or password

    def load(self) -> bool:
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._deep_update(self.data, json.load(f))
                logger.info(f"Loaded portable configuration from: {self.config_path}")
                return True
            logger.info("Configuration file not found. Initializing defaults.")
            self.save()
            return True
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_path}: {e}")
            return False

    def save(self) -> bool:
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            return True
        except PermissionError:
            self.is_read_only = True
            logger.warning(f"Storage medium is read-only: {self.config_path}")
            return False
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def _deep_update(self, target: dict, source: dict):
        for k, v in source.items():
            if isinstance(v, dict) and isinstance(target.get(k), dict):
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
        curr = self.data
        for k in keys_and_value[:-2]:
            if not isinstance(curr.get(k), dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys_and_value[-2]] = keys_and_value[-1]
        self.save()
