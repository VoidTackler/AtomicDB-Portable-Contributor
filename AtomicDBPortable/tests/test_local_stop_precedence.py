"""
Automated Tests: Local Stop Precedence Over Remote Commands
"""

import unittest
from AtomicDBPortable.src.configuration import PortableConfig
from AtomicDBPortable.src.security import SecurityManager
from AtomicDBPortable.src.management_client import ManagementClient

class TestLocalStopPrecedence(unittest.TestCase):
    def test_local_stop_precedence_over_remote_resume(self):
        config = PortableConfig()
        security = SecurityManager()
        client = ManagementClient(config, security)

        resume_executed = False

        def on_resume():
            nonlocal resume_executed
            resume_executed = True

        client.on_resume_requested = on_resume

        # Case 1: Local stop NOT active -> Remote resume succeeds
        config.set("safety", "local_stop_active", False)
        commands = [{
            "id": "CMD-RESUME-01",
            "commandType": "RESUME",
            "payload": {}
        }]
        client._handle_commands(commands)
        self.assertTrue(resume_executed)

        # Case 2: Local stop IS engaged by host owner -> Remote resume MUST BE REJECTED!
        resume_executed = False
        config.set("safety", "local_stop_active", True)
        client._handle_commands(commands)
        self.assertFalse(resume_executed, "CRITICAL VIOLATION: Remote resume succeeded despite local stop override!")

if __name__ == "__main__":
    unittest.main()
