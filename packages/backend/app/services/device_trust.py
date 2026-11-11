"""
Device trust management & recognition service for FinMind (#125).
Computes deterministic device fingerprints, tracks trusted/revoked devices per user,
and recognises returning devices vs new unrecognized devices.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


class DeviceTrustManager:
    def __init__(self) -> None:
        self._devices_by_user: dict[str, dict[str, dict[str, Any]]] = {}

    @staticmethod
    def compute_device_id(user_id: int | str, user_agent: str, platform: str = "", accept_language: str = "") -> str:
        raw = f"{user_id}|{user_agent.strip().lower()}|{platform.strip().lower()}|{accept_language.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def register_or_recognize(
        self,
        user_id: int | str,
        user_agent: str,
        ip_address: str,
        platform: str = "web",
        device_name: str | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        uid = str(user_id)
        ts = time.time() if now is None else now
        device_id = self.compute_device_id(uid, user_agent, platform)
        user_devices = self._devices_by_user.setdefault(uid, {})

        if device_id in user_devices:
            record = user_devices[device_id]
            record["last_seen_at"] = ts
            record["last_ip"] = ip_address
            record["login_count"] += 1
            return {
                **record,
                "recognized": record["status"] == "trusted",
                "is_new_device": False,
            }

        record = {
            "device_id": device_id,
            "user_id": uid,
            "device_name": device_name or f"{platform.title()} Browser",
            "user_agent": user_agent,
            "platform": platform,
            "last_ip": ip_address,
            "status": "untrusted",
            "created_at": ts,
            "last_seen_at": ts,
            "login_count": 1,
        }
        user_devices[device_id] = record
        return {
            **record,
            "recognized": False,
            "is_new_device": True,
        }

    def trust_device(self, user_id: int | str, device_id: str, now: float | None = None) -> dict[str, Any]:
        uid = str(user_id)
        ts = time.time() if now is None else now
        record = self._devices_by_user.get(uid, {}).get(device_id)
        if not record:
            raise KeyError(f"Device {device_id} not found for user {uid}")
        if record["status"] == "revoked":
            raise PermissionError("Revoked device cannot be re-trusted without re-registration")
        record["status"] = "trusted"
        record["trusted_at"] = ts
        return record

    def revoke_device(self, user_id: int | str, device_id: str, now: float | None = None) -> dict[str, Any]:
        uid = str(user_id)
        ts = time.time() if now is None else now
        record = self._devices_by_user.get(uid, {}).get(device_id)
        if not record:
            raise KeyError(f"Device {device_id} not found for user {uid}")
        record["status"] = "revoked"
        record["revoked_at"] = ts
        return record

    def list_devices(self, user_id: int | str) -> list[dict[str, Any]]:
        uid = str(user_id)
        devices = list(self._devices_by_user.get(uid, {}).values())
        devices.sort(key=lambda d: d["last_seen_at"], reverse=True)
        return devices


device_trust_manager = DeviceTrustManager()
