import json
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.encrypted_backup import (
    create_encrypted_backup,
    restore_encrypted_backup,
)


SAMPLE_RECORDS = [
    {"id": 1, "date": "2026-11-01", "category": "Groceries", "amount": 84.50},
    {"id": 2, "date": "2026-11-03", "category": "Utilities", "amount": 120.00},
]


def test_json_encrypted_backup_and_restore_roundtrip():
    env = create_encrypted_backup(SAMPLE_RECORDS, passphrase="correct-horse-battery-staple", fmt="json")
    assert env["header"] == "FMENC1"
    assert env["record_count"] == 2
    restored = json.loads(restore_encrypted_backup(env, passphrase="correct-horse-battery-staple").decode("utf-8"))
    assert restored["records"] == SAMPLE_RECORDS


def test_csv_encrypted_backup_and_restore_roundtrip():
    env = create_encrypted_backup(SAMPLE_RECORDS, passphrase="super-secret-password", fmt="csv")
    restored_csv = restore_encrypted_backup(env, passphrase="super-secret-password").decode("utf-8")
    assert "Groceries" in restored_csv
    assert "Utilities" in restored_csv


def test_wrong_passphrase_raises_permission_error():
    env = create_encrypted_backup(SAMPLE_RECORDS, passphrase="strong-passphrase-123", fmt="json")
    with pytest.raises(PermissionError):
        restore_encrypted_backup(env, passphrase="wrong-passphrase-999")


def test_tampered_ciphertext_is_rejected():
    env = create_encrypted_backup(SAMPLE_RECORDS, passphrase="strong-passphrase-123", fmt="json")
    env["ciphertext_b64"] = "AAAA" + env["ciphertext_b64"][4:]
    with pytest.raises(PermissionError):
        restore_encrypted_backup(env, passphrase="strong-passphrase-123")


def test_weak_passphrase_rejected():
    with pytest.raises(ValueError):
        create_encrypted_backup(SAMPLE_RECORDS, passphrase="short", fmt="json")
