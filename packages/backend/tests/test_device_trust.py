import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.device_trust import DeviceTrustManager


def test_new_device_is_untrusted_until_explicitly_trusted():
    mgr = DeviceTrustManager()
    first = mgr.register_or_recognize(
        user_id=10,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0",
        ip_address="192.0.2.10",
        platform="windows",
        device_name="Work Laptop",
    )
    assert first["is_new_device"] is True
    assert first["recognized"] is False
    assert first["status"] == "untrusted"

    mgr.trust_device(10, first["device_id"])
    second = mgr.register_or_recognize(
        user_id=10,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0",
        ip_address="192.0.2.11",
        platform="windows",
    )
    assert second["is_new_device"] is False
    assert second["recognized"] is True
    assert second["login_count"] == 2


def test_revoke_device_blocks_recognition_and_retrust():
    mgr = DeviceTrustManager()
    dev = mgr.register_or_recognize(10, "Safari iOS", "198.51.100.4", platform="ios")
    mgr.trust_device(10, dev["device_id"])
    revoked = mgr.revoke_device(10, dev["device_id"])
    assert revoked["status"] == "revoked"

    again = mgr.register_or_recognize(10, "Safari iOS", "198.51.100.4", platform="ios")
    assert again["recognized"] is False

    with pytest.raises(PermissionError):
        mgr.trust_device(10, dev["device_id"])


def test_list_devices_orders_by_most_recently_seen():
    mgr = DeviceTrustManager()
    d1 = mgr.register_or_recognize(5, "Agent-A", "10.0.0.1", platform="mac", now=100.0)
    d2 = mgr.register_or_recognize(5, "Agent-B", "10.0.0.2", platform="linux", now=200.0)
    devices = mgr.list_devices(5)
    assert [d["device_id"] for d in devices] == [d2["device_id"], d1["device_id"]]


def test_unknown_device_raises_key_error():
    mgr = DeviceTrustManager()
    with pytest.raises(KeyError):
        mgr.trust_device(99, "nonexistent")


def test_fingerprint_is_deterministic_and_user_isolated():
    id_u1 = DeviceTrustManager.compute_device_id(1, "Firefox", "linux")
    id_u2 = DeviceTrustManager.compute_device_id(2, "Firefox", "linux")
    assert id_u1 != id_u2
