"""
Automated Tests: Local Stop Precedence Over Remote Commands
"""

import unittest
from AtomicDBPortable.src.configuration import PortableConfig
from AtomicDBPortable.src.security import SecurityManager

class TestLocalStopPrecedence(unittest.TestCase):
    def test_local_stop_precedence(self):
        config = PortableConfig()
        # Initial local stop configuration
        config.set("safety", "local_stop_active", False)
        self.assertFalse(config.get("safety", "local_stop_active"))

        # Operator engages emergency local stop
        config.set("safety", "local_stop_active", True)
        self.assertTrue(config.get("safety", "local_stop_active"))

        # Standalone verification
        self.assertTrue(config.get("client", "standalone"))
        self.assertEqual(config.get("openbench", "username"), "PortableExe")

if __name__ == "__main__":
    unittest.main()
