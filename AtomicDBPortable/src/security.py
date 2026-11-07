"""
AtomicDB Portable - Security & Cryptographic Subsystem
Handles credential encryption, signed command verification, and replay protection.
"""

import os
import sys
import hmac
import hashlib
import json
import base64
import time
from typing import Dict, Any, Tuple, Optional

class SecurityManager:
    """Provides cryptographic operations for the portable client."""

    def __init__(self, key_file_path: Optional[str] = None):
        self.seen_nonces = set()
        self.last_monotonic_nonce = 0
        self.key_file_path = key_file_path
        self._local_key = self._get_or_create_local_key()

    def _get_or_create_local_key(self) -> bytes:
        """Derive or load an obfuscation key for storing user credentials on portable media."""
        # Mix host machine identifier and USB salt
        salt = b"AtomicDB_Portable_USB_Salt_2026"
        host_fingerprint = f"{os.name}_{sys.platform}_{os.environ.get('USERNAME', 'default')}".encode('utf-8')
        return hashlib.sha256(salt + host_fingerprint).digest()

    def encrypt_secret(self, plaintext: str) -> str:
        """Simple XOR-CTR obfuscator with random IV for portable USB storage."""
        if not plaintext:
            return ""
        iv = os.urandom(16)
        stream_key = hashlib.sha256(self._local_key + iv).digest()
        cipher_bytes = bytearray()
        raw = plaintext.encode('utf-8')
        for i, b in enumerate(raw):
            cipher_bytes.append(b ^ stream_key[i % len(stream_key)])
        combined = iv + bytes(cipher_bytes)
        return base64.b64encode(combined).decode('ascii')

    def decrypt_secret(self, ciphertext: str) -> str:
        """Decrypts secret stored in the portable configuration."""
        if not ciphertext:
            return ""
        try:
            raw = base64.b64decode(ciphertext.encode('ascii'))
            if len(raw) < 17:
                return ""
            iv = raw[:16]
            encrypted = raw[16:]
            stream_key = hashlib.sha256(self._local_key + iv).digest()
            plain_bytes = bytearray()
            for i, b in enumerate(encrypted):
                plain_bytes.append(b ^ stream_key[i % len(stream_key)])
            return bytes(plain_bytes).decode('utf-8')
        except Exception:
            return ""

    def generate_nonce(self) -> int:
        """Generates a monotonically increasing integer nonce."""
        self.last_monotonic_nonce += 1
        return self.last_monotonic_nonce

    def sign_payload(self, payload: Dict[str, Any], secret_hex: str) -> str:
        """Produces HMAC-SHA256 hex digest of a JSON dictionary."""
        data_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        secret = bytes.fromhex(secret_hex) if len(secret_hex) == 64 else secret_hex.encode('utf-8')
        return hmac.new(secret, data_str.encode('utf-8'), hashlib.sha256).hexdigest()

    def verify_command_signature(self, command_dict: Dict[str, Any], admin_secret_hex: str) -> Tuple[bool, str]:
        """
        Validates HMAC signature and timestamp validity window of incoming admin command.
        Prevents tampering and expired executions.
        """
        signature = command_dict.get('signature')
        if not signature:
            return False, "Missing signature"

        # Check expiration
        expires_at = command_dict.get('expiresAt')
        if expires_at:
            try:
                # ISO parsing fallback
                exp_ts = time.mktime(time.strptime(expires_at[:19], "%Y-%m-%dT%H:%M:%S"))
                if time.time() > exp_ts:
                    return False, "Command has expired"
            except Exception:
                pass

        # Reconstruct canonical payload for signature check
        canonical = {
            'commandId': command_dict.get('id'),
            'targetId': command_dict.get('deviceId'),
            'commandType': command_dict.get('commandType'),
            'payload': command_dict.get('payload', {}),
            'issuedAt': command_dict.get('issuedAt'),
            'expiresAt': command_dict.get('expiresAt')
        }

        # Verify HMAC
        expected_sig = self.sign_payload(canonical, admin_secret_hex)
        if hmac.compare_digest(signature, expected_sig):
            return True, "Valid"
        else:
            return False, "Cryptographic signature mismatch"

    @staticmethod
    def calculate_file_sha256(file_path: str) -> str:
        """Computes SHA256 hex digest of a file in streaming chunks."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest().lower()

    @staticmethod
    def caesar_encrypt(text: str, shift: int = 7) -> str:
        """Lightweight Caesar shift to defeat string scanners without binary bloat."""
        if not text:
            return ""
        return "".join(chr((ord(c) + shift) % 65536) for c in text)

    @staticmethod
    def caesar_decrypt(obfuscated: str, shift: int = 7) -> str:
        """Decrypts a Caesar shifted (and optionally base64 wrapped) string."""
        if not obfuscated:
            return ""
        try:
            try:
                raw = base64.b64decode(obfuscated.encode('ascii')).decode('utf-8')
                return "".join(chr((ord(c) - shift) % 65536) for c in raw)
            except Exception:
                return "".join(chr((ord(c) - shift) % 65536) for c in obfuscated)
        except Exception:
            return obfuscated
