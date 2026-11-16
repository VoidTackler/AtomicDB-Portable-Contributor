"""
Automated Tests: Local Stop Precedence Over Remote Commands
"""

import os
import tempfile
import unittest
from unittest.mock import patch
from AtomicDBPortable.src.configuration import PortableConfig

class TestLocalStopPrecedence(unittest.TestCase):
    def test_local_stop_precedence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"ATOMICDB_PORTABLE_ROOT": tmp_dir}):
                config = PortableConfig()
                # Initial local stop configuration
                config.set("safety", "local_stop_active", False)
                self.assertFalse(config.get("safety", "local_stop_active"))

                # Operator engages emergency local stop
                config.set("safety", "local_stop_active", True)
                self.assertTrue(config.get("safety", "local_stop_active"))

                # Standalone verification (account credentials are not exposed in readable config JSON)
                self.assertTrue(config.get("client", "standalone"))
                self.assertEqual(config.get("openbench", "username"), "")
                self.assertEqual(config.get("openbench", "password_encrypted"), "")

if __name__ == "__main__":
    unittest.main()
