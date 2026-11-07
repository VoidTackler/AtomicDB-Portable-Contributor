"""
AtomicDB Portable - Resource Management Subsystem
Dynamically monitors host CPU/RAM and implements Adaptive Allocation with Hysteresis.
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

    RAM_PER_INSTANCE_OVERHEAD_MB = 300  # Upstream documentation estimate: hash + 300 MB
    DEFAULT_RESERVED_RAM_MB = 1500      # Preserve at least 1.5GB for host OS & user apps

    def __init__(self, mode: str = "Adaptive", reserved_ram_mb: int = 1500):
        self.mode = mode  # Adaptive (Default), Balanced, Maximum, Custom
        self.reserved_ram_mb = reserved_ram_mb
        self.system_cpu_threshold_pct = 80.0
        self.hysteresis_target_cycles = 3
        self.cooldown_cycle_count = 0
        self.is_throttled = False

        # Hardware inventory
        self.physical_cores = os.cpu_count() or 4
        self.logical_cores = os.cpu_count() or 4
        self.total_ram_mb = 8192

        self._detect_hardware()

    def _detect_hardware(self):
        """Discovers host hardware specs using psutil."""
        if psutil:
            try:
                self.physical_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 4
                self.logical_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 4
                mem = psutil.virtual_memory()
                self.total_ram_mb = int(mem.total / (1024 * 1024))
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
                        # Include child processes (Stockfish engine instances)
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
            "mode": self.mode
        }

    def compute_allocation(self, mode: str = None, custom_threads: int = None, custom_hash: int = None) -> Tuple[int, int]:
        """
        Computes recommended (threads, hash_mb) based on active profile and memory safety.
        RAM per instance formula: hash + 300 MB.
        Total engine allocation must not exceed available RAM minus reserved host RAM.
        """
        target_mode = mode or self.mode
        avail_ram = self.total_ram_mb
        if psutil:
            try:
                avail_ram = int(psutil.virtual_memory().available / (1024 * 1024))
            except Exception:
                pass

        usable_ram_mb = max(512, avail_ram - self.reserved_ram_mb)

        if target_mode == "Maximum":
            # Leave at most 1 or 2 threads for OS
            threads = max(1, self.logical_cores - 1) if self.logical_cores > 2 else 1
            # Maximum hash clamped by safe memory
            max_hash_possible = max(128, usable_ram_mb - self.RAM_PER_INSTANCE_OVERHEAD_MB)
            hash_mb = self._clamp_to_power_of_two(min(4096, max_hash_possible))

        elif target_mode == "Balanced":
            # Use ~50% - 60% of logical cores
            threads = max(1, int(self.logical_cores * 0.5))
            max_hash_possible = max(128, int(usable_ram_mb * 0.6) - self.RAM_PER_INSTANCE_OVERHEAD_MB)
            hash_mb = self._clamp_to_power_of_two(min(2048, max_hash_possible))

        elif target_mode == "Custom":
            threads = max(1, min(self.logical_cores, custom_threads or 4))
            max_hash = max(64, usable_ram_mb - self.RAM_PER_INSTANCE_OVERHEAD_MB)
            hash_mb = min(max_hash, custom_hash or 1024)

        else: # "Adaptive" (Default)
            # Normal adaptive operating point
            if self.is_throttled:
                # Stepped-down state during host load
                threads = max(1, int(self.logical_cores * 0.25))
                hash_mb = min(512, self._clamp_to_power_of_two(max(128, int(usable_ram_mb * 0.3))))
            else:
                # Nominal adaptive state
                threads = max(1, int(self.logical_cores * 0.75))
                if threads == self.logical_cores and self.logical_cores > 2:
                    threads = self.logical_cores - 1
                max_hash_possible = max(128, int(usable_ram_mb * 0.75) - self.RAM_PER_INSTANCE_OVERHEAD_MB)
                hash_mb = self._clamp_to_power_of_two(min(2048, max_hash_possible))

        return threads, hash_mb

    def update_adaptive_state(self, current_system_cpu_pct: float) -> bool:
        """
        Executes hysteresis evaluation loop.
        Returns True if allocation state changed (requires restart or throttle signal).
        """
        if self.mode != "Adaptive":
            return False

        state_changed = False

        if current_system_cpu_pct > self.system_cpu_threshold_pct:
            # Immediate throttle if host CPU usage spikes above threshold
            self.cooldown_cycle_count = 0
            if not self.is_throttled:
                self.is_throttled = True
                state_changed = True
                logger.info(f"System CPU spike detected ({current_system_cpu_pct}% > {self.system_cpu_threshold_pct}%). Engaging adaptive throttle.")
        else:
            # System CPU is comfortable; require N consecutive cycles before scaling back up
            if self.is_throttled:
                self.cooldown_cycle_count += 1
                if self.cooldown_cycle_count >= self.hysteresis_target_cycles:
                    self.is_throttled = False
                    self.cooldown_cycle_count = 0
                    state_changed = True
                    logger.info("Host system load stabilized for required hysteresis window. Scaling back to nominal compute.")

        return state_changed

    @staticmethod
    def _clamp_to_power_of_two(val: int) -> int:
        """Standard chess engine hash tables perform best in powers of 2."""
        powers = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]
        clamped = powers[0]
        for p in powers:
            if p <= val:
                clamped = p
            else:
                break
        return clamped
