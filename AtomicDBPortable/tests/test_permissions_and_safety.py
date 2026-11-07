"""
Automated Tests: Zero-Privilege & Device Safety Verification
Confirms that the portable client operates strictly in standard unprivileged user space.
"""

import os
import sys
import unittest
from AtomicDBPortable.src.configuration import PortableConfig, get_base_dir
from AtomicDBPortable.src.resource_manager import ResourceManager
from AtomicDBPortable.src.worker_manager import WorkerManager

class TestZeroPrivilegeExecution(unittest.TestCase):
    def test_no_system_directory_mutation(self):
        """Verifies that all resolved application paths reside strictly within the portable folder."""
        config = PortableConfig()
        base_dir = os.path.abspath(config.base_dir)

        # Check critical paths
        config_path = os.path.abspath(config.config_path)
        engine_path = os.path.abspath(config.get_path("engine"))
        logs_path = os.path.abspath(config.get_path("logs"))
        worker_path = os.path.abspath(config.get_path("worker"))

        # Must never point to Windows system directories
        system_dirs = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "/etc", "/usr", "/var"]
        for p in [config_path, engine_path, logs_path, worker_path]:
            for sys_dir in system_dirs:
                self.assertFalse(p.lower().startswith(sys_dir.lower()), f"Path {p} leaks into system directory {sys_dir}!")
            # Must be inside portable root
            self.assertTrue(p.startswith(base_dir), f"Path {p} is outside portable base directory {base_dir}")

    def test_unprivileged_telemetry_access(self):
        """Verifies that hardware telemetry collection does not raise permission errors."""
        rm = ResourceManager()
        snapshot = rm.get_system_snapshot()
        self.assertIn("system_cpu_pct", snapshot)
        self.assertIn("available_ram_mb", snapshot)
        self.assertGreater(snapshot["physical_cores"], 0)

    def test_read_only_graceful_degradation(self):
        """Verifies that running from a write-protected USB drive does not crash the client."""
        config = PortableConfig()
        # Simulate read-only medium
        config.is_read_only = True
        success = config.save()
        # Should not raise uncaught exception
        self.assertIn(success, [True, False])

if __name__ == "__main__":
    unittest.main()
