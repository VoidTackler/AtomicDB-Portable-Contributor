"""
AtomicDB Portable - Security & Cryptographic Subsystem
Handles credential obfuscation, monotonic nonces, and SHA256 file integrity checks.
"""

import os
import sys
import hashlib
import base64


class SecurityManager:
    """Provides lightweight cryptographic helpers for the portable client."""

    def __init__(self):
        self.last_monotonic_nonce = 0
        salt = b"AtomicDB_Portable_USB_Salt_2026"
        host_fp = f"{os.name}_{sys.platform}_{os.environ.get('USERNAME', 'default')}".encode("utf-8")
        self._local_key = hashlib.sha256(salt + host_fp).digest()

    def _xor_stream(self, data: bytes, iv: bytes) -> bytes:
        stream_key = hashlib.sha256(self._local_key + iv).digest()
        return bytes(b ^ stream_key[i % len(stream_key)] for i, b in enumerate(data))

    def encrypt_secret(self, plaintext: str) -> str:
        """XOR-CTR obfuscator with random 16-byte IV for portable storage."""
        if not plaintext:
            return ""
        iv = os.urandom(16)
        return base64.b64encode(iv + self._xor_stream(plaintext.encode("utf-8"), iv)).decode("ascii")

    def decrypt_secret(self, ciphertext: str) -> str:
        """Decrypts a secret obfuscated with encrypt_secret."""
        if not ciphertext:
            return ""
        try:
            raw = base64.b64decode(ciphertext.encode("ascii"))
            if len(raw) < 17:
                return ""
            return self._xor_stream(raw[16:], raw[:16]).decode("utf-8")
        except Exception:
            return ""

    def generate_nonce(self) -> int:
        """Generates a monotonically increasing integer nonce."""
        self.last_monotonic_nonce += 1
        return self.last_monotonic_nonce

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
        """Lightweight Caesar shift without external dependencies."""
        return "".join(chr((ord(c) + shift) % 65536) for c in text) if text else ""

    @staticmethod
    def caesar_decrypt(obfuscated: str, shift: int = 7) -> str:
        """Decrypts a Caesar-shifted (and optionally base64-wrapped) string."""
        if not obfuscated:
            return ""
        try:
            if obfuscated.endswith("=") or (len(obfuscated) % 4 == 0 and not any(c in obfuscated for c in ":<>~")):
                try:
                    raw = base64.b64decode(obfuscated.encode("ascii")).decode("utf-8")
                    cand = "".join(chr((ord(c) - shift) % 65536) for c in raw)
                    if all(32 <= ord(c) <= 126 for c in cand):
                        return cand
                except Exception:
                    pass
            return "".join(chr((ord(c) - shift) % 65536) for c in obfuscated)
        except Exception:
            return obfuscated
