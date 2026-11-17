"""
AtomicDB Portable - Resource Management Subsystem
Monitors host CPU/RAM and implements Adaptive Allocation with Hysteresis.
"""

import os
import time
import logging
from typing import Dict, Any, Tuple

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("AtomicDB.ResourceManager")


class ResourceManager:
    """Calculates and monitors system load, managing worker thread and hash budgets."""

    RAM_PER_INSTANCE_OVERHEAD_MB = 300
    DEFAULT_RESERVED_RAM_MB = 1500

    def __init__(self, mode: str = "Adaptive", reserved_ram_mb: int = DEFAULT_RESERVED_RAM_MB):
        self.mode = mode
        self.reserved_ram_mb = reserved_ram_mb
        self.system_cpu_threshold_pct = 80.0
        self.hysteresis_target_cycles = 3
        self.cooldown_cycle_count = 0
        self.is_throttled = False
        self.adaptive_check_interval = 20.0
        self.last_adaptive_check = 0.0

        self.physical_cores = os.cpu_count() or 4
        self.logical_cores = os.cpu_count() or 4
        self.total_ram_mb = 8192
        self._detect_hardware()

    def _detect_hardware(self):
        if psutil:
            try:
                self.physical_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 4
                self.logical_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 4
                self.total_ram_mb = int(psutil.virtual_memory().total / (1024 * 1024))
            except Exception as e:
                logger.warning(f"Error querying psutil hardware info: {e}")

    def get_system_snapshot(self, worker_pid: int = None) -> Dict[str, Any]:
        """Returns current system CPU, available RAM, and worker process usage."""
        sys_cpu = 0.0
        avail_ram_mb = 4096
        worker_cpu = 0.0
        worker_ram_mb = 0

        if psutil:
            try:
                sys_cpu = psutil.cpu_percent(interval=None)
                avail_ram_mb = int(psutil.virtual_memory().available / (1024 * 1024))
                if worker_pid:
                    try:
                        proc = psutil.Process(worker_pid)
                        worker_cpu = proc.cpu_percent(interval=None)
                        worker_ram_mb = int(proc.memory_info().rss / (1024 * 1024))
                        for child in proc.children(recursive=True):
                            worker_ram_mb += int(child.memory_info().rss / (1024 * 1024))
                            worker_cpu += child.cpu_percent(interval=None)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                logger.debug(f"Snapshot sampling error: {e}")

        return {
            "physical_cores": self.physical_cores,
            "logical_cores": self.logical_cores,
            "total_ram_mb": self.total_ram_mb,
            "available_ram_mb": avail_ram_mb,
            "system_cpu_pct": round(sys_cpu, 1),
            "worker_cpu_pct": round(worker_cpu, 1),
            "worker_ram_mb": worker_ram_mb,
            "is_throttled": self.is_throttled,
            "mode": self.mode,
        }

    def compute_allocation(self, mode: str = None, custom_threads: int = None, custom_hash: int = None) -> Tuple[int, int]:
        """Computes recommended (threads, hash_mb) respecting host RAM safety reserve."""
        target_mode = mode or self.mode
        avail_ram = self.total_ram_mb
        if psutil:
            try:
                avail_ram = int(psutil.virtual_memory().available / (1024 * 1024))
            except Exception:
                pass

        usable_ram_mb = max(512, avail_ram - self.reserved_ram_mb)

        if target_mode == "Maximum":
            threads = max(1, self.logical_cores - 1) if self.logical_cores > 2 else 1
            hash_mb = self._clamp_to_power_of_two(min(4096, max(128, usable_ram_mb - self.RAM_PER_INSTANCE_OVERHEAD_MB)))
        elif target_mode == "Balanced":
            threads = max(1, int(self.logical_cores * 0.5))
            hash_mb = self._clamp_to_power_of_two(min(2048, max(128, int(usable_ram_mb * 0.6) - self.RAM_PER_INSTANCE_OVERHEAD_MB)))
        elif target_mode == "Custom":
            threads = max(1, min(self.logical_cores, custom_threads or 4))
            hash_mb = min(max(64, usable_ram_mb - self.RAM_PER_INSTANCE_OVERHEAD_MB), custom_hash or 1024)
        else:
            active_cores = self.logical_cores * 0.5
            threads = 1 if active_cores < 1.0 else max(1, int(round(active_cores)))
            if self.is_throttled:
                threads = max(1, threads // 2)
                hash_mb = min(512, self._clamp_to_power_of_two(max(128, int(usable_ram_mb * 0.25))))
            else:
                hash_mb = self._clamp_to_power_of_two(min(1024, max(128, int(usable_ram_mb * 0.5) - self.RAM_PER_INSTANCE_OVERHEAD_MB)))

        return threads, hash_mb

    def update_adaptive_state(self, current_system_cpu_pct: float, force: bool = False) -> bool:
        """Executes hysteresis evaluation every adaptive_check_interval seconds."""
        if self.mode != "Adaptive":
            return False

        now = time.time()
        if not force and self.adaptive_check_interval > 0 and (now - self.last_adaptive_check) < self.adaptive_check_interval:
            return False

        self.last_adaptive_check = now
        if current_system_cpu_pct > self.system_cpu_threshold_pct:
            self.cooldown_cycle_count = 0
            if not self.is_throttled:
                self.is_throttled = True
                logger.info(f"System CPU spike ({current_system_cpu_pct}% > {self.system_cpu_threshold_pct}%). Engaging throttle.")
                return True
        elif self.is_throttled:
            self.cooldown_cycle_count += 1
            if self.cooldown_cycle_count >= self.hysteresis_target_cycles:
                self.is_throttled = False
                self.cooldown_cycle_count = 0
                logger.info("Host load stabilized. Scaling back to nominal compute.")
                return True
        return False

    @staticmethod
    def _clamp_to_power_of_two(val: int) -> int:
        powers = (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384)
        clamped = powers[0]
        for p in powers:
            if p <= val:
                clamped = p
            else:
                break
        return clamped
