"""
Automated Tests: Official Worker Command Construction & Genuine Upstream Flag Verification
"""

import unittest
from AtomicDBPortable.src.worker_manager import WorkerManager

class TestWorkerCLI(unittest.TestCase):
    def test_command_line_argument_fidelity(self):
        wm = WorkerManager("python", "worker/atomicdb_worker.py")

        cmd = wm.build_command_args(
            username="TestContributor",
            password="ValidPassword123",
            server_url="https://belzedar.duckdns.org",
            threads=8,
            hash_mb=1024
        )

        # Verify exact upstream arguments
        self.assertIn("-U", cmd)
        self.assertEqual(cmd[cmd.index("-U") + 1], "TestContributor")

        self.assertIn("-P", cmd)
        self.assertEqual(cmd[cmd.index("-P") + 1], "ValidPassword123")

        self.assertIn("-S", cmd)
        self.assertEqual(cmd[cmd.index("-S") + 1], "https://belzedar.duckdns.org")

        self.assertIn("-T", cmd)
        self.assertEqual(cmd[cmd.index("-T") + 1], "8")

        self.assertIn("--hash", cmd)
        self.assertEqual(cmd[cmd.index("--hash") + 1], "1024")

        # Verify no tablebase is always enabled by default
        self.assertIn("--no-fetch-syzygy", cmd)

    def test_command_line_missing_credentials_rejection(self):
        wm = WorkerManager("python", "worker/atomicdb_worker.py")
        with self.assertRaises(ValueError):
            wm.build_command_args(username="", password="123")

        with self.assertRaises(ValueError):
            wm.build_command_args(username="user", password="")

    def test_master_password_caesar_obfuscation(self):
        from AtomicDBPortable.src.security import SecurityManager
        plaintext = "Pineapple2357"
        encrypted = SecurityManager.caesar_encrypt(plaintext, shift=7)
        self.assertEqual(encrypted, "Wpulhwwsl9:<>")
        decrypted = SecurityManager.caesar_decrypt(encrypted, shift=7)
        self.assertEqual(decrypted, plaintext)

if __name__ == "__main__":
    unittest.main()
