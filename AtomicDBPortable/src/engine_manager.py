"""
AtomicDB Portable - Engine Manager
Verifies SHA256 checksums and manages Atomic-Stockfish backups on the portable drive.
"""

import os
import shutil
import hashlib
import logging
from typing import Optional, Tuple

logger = logging.getLogger("AtomicDB.EngineManager")


class EngineManager:
    """Manages Atomic-Stockfish binaries and known-good backups on the portable drive."""

    def __init__(self, engine_dir: str):
        self.engine_dir = engine_dir
        self.backup_dir = os.path.join(self.engine_dir, "backup")
        os.makedirs(self.backup_dir, exist_ok=True)

    def verify_binary(self, binary_path: str, expected_hash: Optional[str] = None) -> Tuple[bool, str]:
        """Validates SHA256 checksum (when provided) or sanity-checks engine file size."""
        if not os.path.exists(binary_path):
            return False, f"File does not exist: {binary_path}"

        target_hash = (expected_hash or "").strip().lower()
        try:
            sha = hashlib.sha256()
            with open(binary_path, "rb") as f:
                while chunk := f.read(65536):
                    sha.update(chunk)
            computed = sha.hexdigest().lower()

            if not target_hash:
                file_size = os.path.getsize(binary_path)
                if file_size < 100_000:
                    return False, f"Suspiciously small binary file ({file_size} bytes)"
                return True, f"Verified (SHA256: {computed[:16]}...)"

            if computed == target_hash:
                return True, f"Checksum match (SHA256: {computed[:16]}...)"
            return False, f"Checksum mismatch! Expected {target_hash[:12]}..., got {computed[:12]}..."
        except Exception as e:
            return False, f"Error computing checksum: {e}"

    def backup_known_good_binary(self, binary_name: str) -> bool:
        """Saves current verified binary as the last-known-good fallback."""
        src = os.path.join(self.engine_dir, binary_name)
        dst = os.path.join(self.backup_dir, f"last_good_{binary_name}")
        try:
            if os.path.exists(src):
                shutil.copy2(src, dst)
                logger.info(f"Saved last-known-good engine backup: {dst}")
                return True
        except Exception as e:
            logger.error(f"Failed to backup engine: {e}")
        return False

    def restore_known_good_binary(self, binary_name: str) -> bool:
        """Restores last-known-good binary if the current file is corrupted."""
        src = os.path.join(self.backup_dir, f"last_good_{binary_name}")
        dst = os.path.join(self.engine_dir, binary_name)
        try:
            if os.path.exists(src):
                shutil.copy2(src, dst)
                logger.warning(f"Restored last-known-good engine backup to {dst}")
                return True
        except Exception as e:
            logger.error(f"Failed to restore backup engine: {e}")
        return False
