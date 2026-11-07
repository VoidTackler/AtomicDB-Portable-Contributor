"""
Automated Tests: Portable Path Handling & Relative USB Anchoring
"""

import os
import unittest
from AtomicDBPortable.src.configuration import PortableConfig, get_base_dir

class TestPortablePaths(unittest.TestCase):
    def test_relative_base_dir_resolution(self):
        base_dir = get_base_dir()
        self.assertTrue(os.path.isabs(base_dir))
        self.assertTrue(os.path.exists(base_dir))

    def test_config_path_resolution(self):
        config = PortableConfig()
        engine_path = config.get_path("engine")
        logs_path = config.get_path("logs")

        self.assertTrue(os.path.isabs(engine_path))
        self.assertTrue(os.path.isabs(logs_path))
        # Check that paths are relative to base_dir
        self.assertTrue(engine_path.startswith(config.base_dir))
        self.assertTrue(logs_path.startswith(config.base_dir))

    def test_read_only_medium_fallback(self):
        config = PortableConfig()
        config.set("test_key", "test_val")
        self.assertEqual(config.get("test_key"), "test_val")

    def test_worker_syzygy_anchored_to_portable_root(self):
        from AtomicDBPortable.worker.atomicdb_worker import syzygy_dir
        test_root = "/tmp/fake_usb_drive"
        os.environ["ATOMICDB_PORTABLE_ROOT"] = test_root
        try:
            resolved = syzygy_dir()
            self.assertTrue(str(resolved).startswith(test_root))
            self.assertTrue(str(resolved).endswith("syzygy-345"))
        finally:
            os.environ.pop("ATOMICDB_PORTABLE_ROOT", None)

    def test_worker_syzygy_explicit_env_override(self):
        from AtomicDBPortable.worker.atomicdb_worker import syzygy_dir
        custom_syzygy = "/tmp/usb_drive/custom_syzygy_tb"
        os.environ["ATOMICDB_SYZYGY_DIR"] = custom_syzygy
        try:
            resolved = syzygy_dir()
            self.assertEqual(str(resolved), custom_syzygy)
        finally:
            os.environ.pop("ATOMICDB_SYZYGY_DIR", None)

if __name__ == "__main__":
    unittest.main()

