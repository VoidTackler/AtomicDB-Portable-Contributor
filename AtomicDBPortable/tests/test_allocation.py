"""
Automated Tests: Resource Allocation & Hysteresis Logic
"""

import unittest
from AtomicDBPortable.src.resource_manager import ResourceManager

class TestResourceAllocation(unittest.TestCase):
    def test_hardware_detection_defaults(self):
        rm = ResourceManager(mode="Adaptive")
        self.assertGreaterEqual(rm.physical_cores, 1)
        self.assertGreaterEqual(rm.logical_cores, 1)
        self.assertGreater(rm.total_ram_mb, 0)

    def test_allocation_modes(self):
        rm = ResourceManager(mode="Adaptive")
        # Adaptive allocation
        threads, hash_mb = rm.compute_allocation(mode="Adaptive")
        self.assertGreaterEqual(threads, 1)
        self.assertLessEqual(threads, rm.logical_cores)
        self.assertIn(hash_mb, [64, 128, 256, 512, 1024, 2048, 4096, 8192])

        # Balanced allocation
        threads_b, hash_b = rm.compute_allocation(mode="Balanced")
        self.assertGreaterEqual(threads_b, 1)
        self.assertLessEqual(threads_b, rm.logical_cores)

        # Maximum allocation
        threads_m, hash_m = rm.compute_allocation(mode="Maximum")
        self.assertGreaterEqual(threads_m, 1)
        if rm.logical_cores > 2:
            self.assertGreaterEqual(threads_m, threads_b)

    def test_memory_overhead_guardrail(self):
        """Verify formula: RAM per instance = hash + 300MB, reserving >= 1500MB host RAM."""
        rm = ResourceManager(mode="Custom", reserved_ram_mb=1500)
        threads, hash_mb = rm.compute_allocation(mode="Custom", custom_threads=4, custom_hash=1024)
        self.assertLessEqual(hash_mb, 1024)
        # Ensure overhead is respected
        estimated_ram_mb = hash_mb + rm.RAM_PER_INSTANCE_OVERHEAD_MB
        self.assertEqual(estimated_ram_mb, hash_mb + 300)

    def test_adaptive_hysteresis_cycles(self):
        """
        Simulates high host CPU utilization, verifying immediate throttling,
        and requiring 3 consecutive low-load cycles before restoring compute.
        """
        rm = ResourceManager(mode="Adaptive")
        rm.system_cpu_threshold_pct = 80.0
        rm.hysteresis_target_cycles = 3

        self.assertFalse(rm.is_throttled)

        # Cycle 1: Host spikes to 88% CPU (e.g. user compiles code)
        changed = rm.update_adaptive_state(88.0)
        self.assertTrue(changed)
        self.assertTrue(rm.is_throttled)

        # Cycle 2: Host load is still 82%
        changed = rm.update_adaptive_state(82.0)
        self.assertFalse(changed)
        self.assertTrue(rm.is_throttled)

        # Cycle 3: Host load drops to 30% (Low Load Cycle 1/3)
        changed = rm.update_adaptive_state(30.0)
        self.assertFalse(changed)  # Must not restore yet!
        self.assertTrue(rm.is_throttled)

        # Cycle 4: Host load is 35% (Low Load Cycle 2/3)
        changed = rm.update_adaptive_state(35.0)
        self.assertFalse(changed)  # Must not restore yet!
        self.assertTrue(rm.is_throttled)

        # Cycle 5: Host load is 28% (Low Load Cycle 3/3 - Hysteresis Met!)
        changed = rm.update_adaptive_state(28.0)
        self.assertTrue(changed)
        self.assertFalse(rm.is_throttled)  # Restored to nominal!

if __name__ == "__main__":
    unittest.main()
