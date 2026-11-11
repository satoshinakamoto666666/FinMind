"""
Secure backup & authenticated encrypted export service for FinMind (#126).
Supports JSON and CSV financial exports encrypted with PBKDF2-HMAC-SHA256 (600,000 iterations),
deterministic counter-mode keystream encryption, and HMAC-SHA256 authentication (Encrypt-then-MAC).
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
from typing import Any

MAGIC_HEADER = "FMENC1"
PBKDF2_ITERATIONS = 600_000


def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    if not passphrase or len(passphrase.strip()) < 8:
        raise ValueError("Encryption passphrase must be at least 8 characters")
    dk = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=64)
    return dk[:32], dk[32:]


def _xor_keystream(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    out = bytearray(len(data))
    block_count = (len(data) + 31) // 32
    for counter in range(block_count):
        counter_bytes = counter.to_bytes(8, "big")
        keystream_block = hmac.new(enc_key, nonce + counter_bytes, hashlib.sha256).digest()
        start = counter * 32
        end = min(start + 32, len(data))
        for i in range(start, end):
            out[i] = data[i] ^ keystream_block[i - start]
    return bytes(out)


def serialize_export_data(records: list[dict[str, Any]], fmt: str = "json") -> bytes:
    fmt_clean = fmt.strip().lower()
    if fmt_clean == "json":
        return json.dumps({"version": "1.0", "records": records}, indent=2, sort_keys=True).encode("utf-8")
    if fmt_clean == "csv":
        buf = io.StringIO()
        fieldnames = sorted({k for r in records for k in r.keys()}) if records else ["id", "amount", "category", "date"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)
        return buf.getvalue().encode("utf-8")
    raise ValueError(f"Unsupported export format: {fmt}")


def create_encrypted_backup(
    records: list[dict[str, Any]],
    passphrase: str,
    fmt: str = "json",
) -> dict[str, Any]:
    plaintext = serialize_export_data(records, fmt=fmt)
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_keys(passphrase, salt)

    ciphertext = _xor_keystream(plaintext, enc_key, nonce)
    associated = f"{MAGIC_HEADER}:{fmt.lower()}".encode("utf-8")
    tag = hmac.new(mac_key, associated + salt + nonce + ciphertext, hashlib.sha256).digest()
    checksum = hashlib.sha256(plaintext).hexdigest()

    return {
        "header": MAGIC_HEADER,
        "format": fmt.lower(),
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": PBKDF2_ITERATIONS,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "tag_b64": base64.b64encode(tag).decode("ascii"),
        "plaintext_sha256": checksum,
        "record_count": len(records),
    }


def restore_encrypted_backup(envelope: dict[str, Any], passphrase: str) -> bytes:
    if envelope.get("header") != MAGIC_HEADER:
        raise ValueError("Invalid backup header")
    fmt = str(envelope.get("format", "json")).lower()
    salt = base64.b64decode(envelope["salt_b64"])
    nonce = base64.b64decode(envelope["nonce_b64"])
    ciphertext = base64.b64decode(envelope["ciphertext_b64"])
    expected_tag = base64.b64decode(envelope["tag_b64"])

    enc_key, mac_key = _derive_keys(passphrase, salt)
    associated = f"{MAGIC_HEADER}:{fmt}".encode("utf-8")
    computed_tag = hmac.new(mac_key, associated + salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_tag, computed_tag):
        raise PermissionError("Backup authentication failed: wrong passphrase or tampered ciphertext")

    plaintext = _xor_keystream(ciphertext, enc_key, nonce)
    if "plaintext_sha256" in envelope:
        if hashlib.sha256(plaintext).hexdigest() != envelope["plaintext_sha256"]:
            raise ValueError("Plaintext SHA-256 integrity mismatch")
    return plaintext
