# Secure Backup & Encrypted Export Options (#126)

## Overview
Provides authenticated Encrypt-then-MAC (`PBKDF2-HMAC-SHA256` with `600,000` iterations + `HMAC-SHA256` tag + `SHA-256` plaintext checksum) backup envelopes for JSON and CSV financial exports.
