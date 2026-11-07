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

    def test_hmac_signature_verification_success(self):
        sec = SecurityManager()
        secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

        now = datetime.datetime.now()
        issued = now.strftime("%Y-%m-%dT%H:%M:%S")
        expires = (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

        command = {
            "id": "CMD-001",
            "deviceId": "node-test-1",
            "commandType": "PAUSE",
            "payload": {},
            "issuedAt": issued,
            "expiresAt": expires
        }

        canonical = {
            'commandId': command['id'],
            'targetId': command['deviceId'],
            'commandType': command['commandType'],
            'payload': command['payload'],
            'issuedAt': command['issuedAt'],
            'expiresAt': command['expiresAt']
        }

        sig = sec.sign_payload(canonical, secret)
        command["signature"] = sig

        valid, reason = sec.verify_command_signature(command, secret)
        self.assertTrue(valid, f"Signature validation failed: {reason}")
        self.assertEqual(reason, "Valid")

    def test_tampered_command_signature_rejection(self):
        sec = SecurityManager()
        secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

        now = datetime.datetime.now()
        issued = now.strftime("%Y-%m-%dT%H:%M:%S")
        expires = (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

        command = {
            "id": "CMD-001",
            "deviceId": "node-test-1",
            "commandType": "PAUSE",
            "payload": {},
            "issuedAt": issued,
            "expiresAt": expires
        }

        canonical = {
            'commandId': command['id'],
            'targetId': command['deviceId'],
            'commandType': command['commandType'],
            'payload': command['payload'],
            'issuedAt': command['issuedAt'],
            'expiresAt': command['expiresAt']
        }

        sig = sec.sign_payload(canonical, secret)
        # Attacker tries to alter command type to REVOKE
        command["commandType"] = "REVOKE"
        command["signature"] = sig

        valid, reason = sec.verify_command_signature(command, secret)
        self.assertFalse(valid)
        self.assertIn("mismatch", reason.lower())

if __name__ == "__main__":
    unittest.main()
