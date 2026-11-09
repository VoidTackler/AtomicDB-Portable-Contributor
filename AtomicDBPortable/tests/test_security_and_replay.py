"""
Automated Tests: Security, Cryptography, Nonces & Replay Prevention
"""

import time
import datetime
import unittest
from AtomicDBPortable.src.security import SecurityManager

class TestSecurityAndReplay(unittest.TestCase):
    def test_credential_encryption_roundtrip(self):
        sec = SecurityManager()
        plain = "SuperSecretOpenBenchPassword123!"
        encrypted = sec.encrypt_secret(plain)
        self.assertNotEqual(encrypted, plain)
        self.assertGreater(len(encrypted), 0)

        decrypted = sec.decrypt_secret(encrypted)
        self.assertEqual(decrypted, plain)

    def test_monotonic_nonce_generation(self):
        sec = SecurityManager()
        n1 = sec.generate_nonce()
        n2 = sec.generate_nonce()
        n3 = sec.generate_nonce()
        self.assertLess(n1, n2)
        self.assertLess(n2, n3)

    def test_file_hash_verification(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"Test binary data for portable hash check")
            temp_name = tf.name

        try:
            sec = SecurityManager()
            file_hash = sec.calculate_file_sha256(temp_name)
            self.assertEqual(len(file_hash), 64)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)

if __name__ == "__main__":
    unittest.main()
