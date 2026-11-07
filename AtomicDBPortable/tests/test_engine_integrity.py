"""
Automated Tests: Engine SHA256 Integrity & Instruction Set Detection
"""

import os
import shutil
import tempfile
import hashlib
import unittest
from AtomicDBPortable.src.engine_manager import EngineManager

class TestEngineIntegrity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_engine_sha256_verification_pass(self):
        em = EngineManager(self.test_dir)
        test_binary = os.path.join(self.test_dir, "test_engine.exe")
        content = b"AtomicStockfishBinaryMockContent" * 4000
        with open(test_binary, "wb") as f:
            f.write(content)

        expected_sha = hashlib.sha256(content).hexdigest()
        verified, msg = em.verify_binary(test_binary, expected_hash=expected_sha)
        self.assertTrue(verified)
        self.assertIn("match", msg.lower())

    def test_engine_sha256_verification_fail(self):
        em = EngineManager(self.test_dir)
        test_binary = os.path.join(self.test_dir, "test_engine.exe")
        with open(test_binary, "wb") as f:
            f.write(b"CompromisedEngineBinaryPayload" * 4000)

        mismatched_sha = "0000000000000000000000000000000000000000000000000000000000000000"
        verified, msg = em.verify_binary(test_binary, expected_hash=mismatched_sha)
        self.assertFalse(verified)
        self.assertIn("mismatch", msg.lower())

    def test_engine_backup_retention(self):
        em = EngineManager(self.test_dir)
        bin_name = "atomic-stockfish-x64-avx2.exe"
        src_bin = os.path.join(self.test_dir, bin_name)
        with open(src_bin, "wb") as f:
            f.write(b"GoodEngineBytes" * 4000)

        # Backup
        backed_up = em.backup_known_good_binary(bin_name)
        self.assertTrue(backed_up)
        backup_file = os.path.join(self.test_dir, "backup", f"last_good_{bin_name}")
        self.assertTrue(os.path.exists(backup_file))

        # Corrupt original
        with open(src_bin, "wb") as f:
            f.write(b"CorruptedFile")

        # Restore
        restored = em.restore_known_good_binary(bin_name)
        self.assertTrue(restored)
        with open(src_bin, "rb") as f:
            restored_content = f.read()
        self.assertEqual(restored_content, b"GoodEngineBytes" * 4000)

if __name__ == "__main__":
    unittest.main()
