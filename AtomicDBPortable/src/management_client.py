"""
AtomicDB Portable - Central Management Client
Conducts secure HTTPS polling, sends signed telemetry, and processes remote admin commands.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Callable
try:
    import requests
except ImportError:
    requests = None

try:
    from .security import SecurityManager
    from .configuration import PortableConfig
except (ImportError, ValueError):
    from security import SecurityManager
    from configuration import PortableConfig

logger = logging.getLogger("AtomicDB.ManagementClient")

class ManagementClient:
    """Interacts with the central administrator management server."""

    def __init__(self, config: PortableConfig, security: SecurityManager):
        self.config = config
        self.security = security
        self.is_connected = False
        self.last_poll_time = 0.0
        self.is_revoked = False

        # Callbacks for application actions
        self.on_pause_requested: Optional[Callable[[], None]] = None
        self.on_resume_requested: Optional[Callable[[], None]] = None
        self.on_config_updated: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_revocation_triggered: Optional[Callable[[], None]] = None
        self.on_terminate_requested: Optional[Callable[[], None]] = None

    @property
    def server_url(self) -> str:
        return self.config.get("client", "management_server_url", default="http://localhost:3000").rstrip("/")

    @property
    def device_id(self) -> str:
        return self.config.get("client", "device_id", default="")

    @property
    def client_secret(self) -> str:
        return self.config.get("client", "client_secret", default="")

    def send_heartbeat(self, current_status: str, metrics: Dict[str, Any], current_task: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Submits telemetry heartbeat to central dashboard and receives pending admin commands.
        Enforces monotonic nonce and cryptographic signatures.
        """
        if not requests:
            logger.warning("Requests library not available for heartbeat.")
            return []

        if not self.device_id or self.is_revoked:
            return []

        nonce = self.security.generate_nonce()
        local_stop = bool(self.config.get("safety", "local_stop_active", default=False))

        payload = {
            "deviceId": self.device_id,
            "nonce": nonce,
            "status": "LOCAL_STOP" if local_stop else current_status,
            "localStopActive": local_stop,
            "metrics": metrics,
            "currentTask": current_task,
            "clientTimestamp": time.time()
        }

        # Calculate HMAC signature
        signature = self.security.sign_payload(payload, self.client_secret)
        payload["signature"] = signature

        endpoint = f"{self.server_url}/api/client/heartbeat"

        try:
            resp = requests.post(endpoint, json=payload, timeout=6.0)
            self.last_poll_time = time.time()

            if resp.status_code == 200:
                self.is_connected = True
                data = resp.json()
                commands = data.get("commands", [])
                self._handle_commands(commands)
                return commands
            elif resp.status_code == 403:
                # Device was revoked by software owner
                self.is_revoked = True
                logger.warning("Device authorization has been revoked by central administrator.")
                if self.on_revocation_triggered:
                    self.on_revocation_triggered()
                return []
            else:
                self.is_connected = False
                logger.debug(f"Heartbeat server returned HTTP {resp.status_code}")
                return []
        except Exception as e:
            self.is_connected = False
            logger.debug(f"Heartbeat network poll failed: {e}")
            return []

    def _handle_commands(self, commands: List[Dict[str, Any]]):
        """Processes authenticated commands received from central administrator."""
        for cmd in commands:
            cmd_id = cmd.get("id")
            cmd_type = cmd.get("commandType")
            payload = cmd.get("payload", {})
            logger.info(f"Received remote command: {cmd_type} (ID: {cmd_id})")

            # Local stop safety rule: local stop takes absolute precedence!
            local_stop_active = self.config.get("safety", "local_stop_active", default=False)

            outcome = "ACKNOWLEDGED"
            details = "Command executed"

            if cmd_type == "PAUSE":
                if self.on_pause_requested:
                    self.on_pause_requested()
                details = "Worker paused by remote administrator"

            elif cmd_type == "RESUME":
                if local_stop_active:
                    # LOCAL STOP PRECEDENCE ENFORCEMENT
                    outcome = "REJECTED"
                    details = "Remote RESUME rejected: Local machine operator has engaged local stop precedence."
                    logger.warning(details)
                else:
                    if self.on_resume_requested:
                        self.on_resume_requested()
                    details = "Worker resumed by remote administrator"

            elif cmd_type == "UPDATE_CONFIG":
                new_threads = payload.get("threads")
                new_hash = payload.get("hash")
                new_mode = payload.get("cpuMode")

                if new_threads:
                    self.config.set("resources", "threads", int(new_threads))
                if new_hash:
                    self.config.set("resources", "hash_mb", int(new_hash))
                if new_mode:
                    self.config.set("resources", "cpu_mode", str(new_mode))

                if self.on_config_updated:
                    self.on_config_updated(payload)
                details = f"Applied updated config: threads={new_threads}, hash={new_hash}, mode={new_mode}"

            elif cmd_type == "REVOKE":
                self.is_revoked = True
                self.config.set("client", "enrolled", False)
                if self.on_revocation_triggered:
                    self.on_revocation_triggered()
                details = "Device credentials revoked"

            elif cmd_type == "TERMINATE":
                self.is_revoked = True
                details = "Device execution terminated by Master Control kill command"
                logger.warning(details)
                self._acknowledge_command(cmd_id, outcome, details)
                if self.on_terminate_requested:
                    self.on_terminate_requested()
                import sys
                sys.exit(0)

            # Send acknowledgment back to server
            self._acknowledge_command(cmd_id, outcome, details)

    def _acknowledge_command(self, command_id: str, outcome: str, details: str):
        """Notifies management backend that command was received and executed."""
        try:
            endpoint = f"{self.server_url}/api/client/ack-command"
            requests.post(endpoint, json={
                "deviceId": self.device_id,
                "commandId": command_id,
                "outcome": outcome,
                "details": details
            }, timeout=4.0)
        except Exception as e:
            logger.debug(f"Failed to submit command ack: {e}")
