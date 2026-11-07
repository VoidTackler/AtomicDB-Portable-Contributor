"""
AtomicDB Portable - Device Registration & Enrollment
Exchanges a one-time enrollment token with the central administrator server for device credentials.
"""

import os
import platform
import logging
from typing import Dict, Any, Tuple
try:
    import requests
except ImportError:
    requests = None

try:
    from .configuration import PortableConfig
    from .resource_manager import ResourceManager
except (ImportError, ValueError):
    from configuration import PortableConfig
    from resource_manager import ResourceManager

logger = logging.getLogger("AtomicDB.Registration")

class DeviceRegistration:
    """Handles enrollment authorization for new USB client instances."""

    def __init__(self, config: PortableConfig, resource_mgr: ResourceManager):
        self.config = config
        self.resource_mgr = resource_mgr

    def enroll_device(self, token: str, custom_device_name: str = "") -> Tuple[bool, str]:
        """
        Submits the one-time enrollment token to the central management backend.
        Returns (success, message).
        """
        if not requests:
            return False, "Requests library not installed."

        clean_token = token.strip()
        if not clean_token:
            return False, "Enrollment token cannot be empty."

        server_url = self.config.get("client", "management_server_url", default="http://localhost:3000").rstrip("/")
        endpoint = f"{server_url}/api/client/enroll"

        device_name = custom_device_name.strip() or f"WIN-{platform.node()}"

        hardware_info = {
            "cpuModel": platform.processor() or "x86_64 Processor",
            "physicalCores": self.resource_mgr.physical_cores,
            "logicalCores": self.resource_mgr.logical_cores,
            "ramTotalMb": self.resource_mgr.total_ram_mb,
            "instructions": ["AVX2", "BMI2", "POPCNT", "SSE4.2"]
        }

        versions_info = {
            "worker": "atomicdb_worker.py (Belzedar/OpenBench)",
            "engine": "Atomic-Stockfish 16",
            "python": platform.python_version()
        }

        payload = {
            "token": clean_token,
            "deviceName": device_name,
            "hardware": hardware_info,
            "versions": versions_info
        }

        try:
            resp = requests.post(endpoint, json=payload, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                device_id = data.get("deviceId")
                client_secret = data.get("clientSecret")

                # Save to configuration
                self.config.set("client", "enrolled", True)
                self.config.set("client", "device_name", device_name)
                self.config.set("client", "device_id", device_id)
                self.config.set("client", "client_secret", client_secret)

                # Apply policy limits if specified by server
                policy = data.get("policy", {})
                if policy.get("maxThreads"):
                    self.config.set("resources", "threads", min(self.resource_mgr.logical_cores, policy["maxThreads"]))
                if policy.get("maxHashMb"):
                    self.config.set("resources", "hash_mb", policy["maxHashMb"])

                logger.info(f"Device successfully enrolled as {device_name} (ID: {device_id})")
                return True, f"Successfully enrolled as {device_name} (ID: {device_id})"
            else:
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("error", f"HTTP {resp.status_code}")
                return False, f"Enrollment rejected: {err_msg}"
        except Exception as e:
            return False, f"Connection failed to management server: {e}"
