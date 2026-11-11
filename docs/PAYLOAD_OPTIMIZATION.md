# API Response Compression & Payload Optimization (#129)

## Features
- **Gzip & Deflate Content Negotiation**: Compresses responses exceeding `min_size_bytes` (`256B` default) and sets `Content-Encoding` and `Vary: Accept-Encoding`.
- **JSON Payload Minification & Null Stripping**: Recursively omits `null` fields and supports sparse fieldsets (`?fields=id,amount,category`).
- **Weak ETag Generation**: Computes deterministic SHA-256 weak `ETag` headers for conditional `If-None-Match` caching.
