import gzip
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.payload_optimizer import (
    compress_payload,
    compute_etag,
    negotiate_encoding,
    optimize_json_payload,
    serialize_minified_json,
)


def test_strip_nulls_and_sparse_fields():
    raw = [
        {"id": 1, "amount": 45.0, "category": "Food", "notes": None, "metadata": {"tag": None, "source": "card"}},
        {"id": 2, "amount": 120.0, "category": "Utilities", "notes": "Monthly bill", "extra": None},
    ]
    cleaned = optimize_json_payload(raw, strip_nulls=True, fields=["id", "amount", "category"])
    assert cleaned == [
        {"id": 1, "amount": 45.0, "category": "Food"},
        {"id": 2, "amount": 120.0, "category": "Utilities"},
    ]


def test_gzip_and_deflate_compression_above_threshold():
    large_obj = {"items": [{"id": i, "description": "recurring financial expense record" * 4} for i in range(40)]}
    raw_bytes = serialize_minified_json(large_obj)

    gz_bytes, gz_headers = compress_payload(raw_bytes, accept_encoding="gzip, deflate", min_size_bytes=200)
    assert gz_headers["Content-Encoding"] == "gzip"
    assert len(gz_bytes) < len(raw_bytes)
    assert json.loads(gzip.decompress(gz_bytes).decode("utf-8")) == large_obj

    df_bytes, df_headers = compress_payload(raw_bytes, accept_encoding="deflate", min_size_bytes=200)
    assert df_headers["Content-Encoding"] == "deflate"
    assert json.loads(zlib.decompress(df_bytes).decode("utf-8")) == large_obj


def test_small_payload_skips_compression_and_preserves_etag():
    small_bytes = serialize_minified_json({"ok": True})
    out_bytes, headers = compress_payload(small_bytes, accept_encoding="gzip", min_size_bytes=512)
    assert out_bytes == small_bytes
    assert "Content-Encoding" not in headers
    assert headers["ETag"] == compute_etag(small_bytes)
    assert headers["Vary"] == "Accept-Encoding"


def test_encoding_negotiation():
    assert negotiate_encoding("br, gzip;q=0.8") == "gzip"
    assert negotiate_encoding("deflate") == "deflate"
    assert negotiate_encoding("identity") is None
    assert negotiate_encoding(None) is None
