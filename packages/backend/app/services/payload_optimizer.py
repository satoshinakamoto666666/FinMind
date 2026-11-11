"""
API response compression & JSON payload optimization service for FinMind (#129).
Supports Gzip & Deflate negotiation, configurable byte thresholds, ETag 304 caching,
recursive null stripping, and sparse fieldset projection (?fields=id,amount,category).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import zlib
from typing import Any


def optimize_json_payload(
    data: Any,
    strip_nulls: bool = True,
    strip_empty_collections: bool = False,
    fields: list[str] | set[str] | None = None,
) -> Any:
    allowed_fields = {f.strip() for f in fields if f and f.strip()} if fields else None

    def _clean(node: Any, is_record: bool = False) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if is_record and allowed_fields and k not in allowed_fields:
                    continue
                if strip_nulls and v is None:
                    continue
                cleaned_v = _clean(v, is_record=False)
                if strip_empty_collections and cleaned_v in ([], {}):
                    continue
                out[k] = cleaned_v
            return out
        if isinstance(node, list):
            return [_clean(item, is_record=isinstance(item, dict)) for item in node]
        return node

    return _clean(data, is_record=isinstance(data, dict))


def serialize_minified_json(data: Any) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")


def compute_etag(payload_bytes: bytes) -> str:
    digest = hashlib.sha256(payload_bytes).hexdigest()[:24]
    return f'W/"{digest}"'


def negotiate_encoding(accept_encoding_header: str | None) -> str | None:
    if not accept_encoding_header:
        return None
    lower = accept_encoding_header.lower()
    if "gzip" in lower:
        return "gzip"
    if "deflate" in lower:
        return "deflate"
    return None


def compress_payload(
    raw_bytes: bytes,
    accept_encoding: str | None = "gzip",
    min_size_bytes: int = 256,
    compression_level: int = 6,
) -> tuple[bytes, dict[str, str]]:
    etag = compute_etag(raw_bytes)
    headers: dict[str, str] = {
        "ETag": etag,
        "Vary": "Accept-Encoding",
        "X-Original-Size": str(len(raw_bytes)),
    }

    if len(raw_bytes) < min_size_bytes:
        headers["X-Compressed-Size"] = str(len(raw_bytes))
        return raw_bytes, headers

    encoding = negotiate_encoding(accept_encoding)
    if encoding == "gzip":
        compressed = gzip.compress(raw_bytes, compresslevel=compression_level)
    elif encoding == "deflate":
        compressed = zlib.compress(raw_bytes, level=compression_level)
    else:
        headers["X-Compressed-Size"] = str(len(raw_bytes))
        return raw_bytes, headers

    if len(compressed) >= len(raw_bytes):
        headers["X-Compressed-Size"] = str(len(raw_bytes))
        return raw_bytes, headers

    headers["Content-Encoding"] = encoding
    headers["X-Compressed-Size"] = str(len(compressed))
    ratio = round((1.0 - (len(compressed) / max(len(raw_bytes), 1))) * 100.0, 2)
    headers["X-Compression-Ratio-Pct"] = str(ratio)
    return compressed, headers
