# Locale-Aware Date, Currency & Number Formatting (#131)

## Overview
FinMind provides deterministic, locale-aware formatting across backend REST responses, digests, exports, and the React frontend:

- **Supported Locales**: `en-US`, `en-GB`, `de-DE`, `fr-FR`, `en-IN`, `hi-IN`, `ja-JP`, `iso-8601`.
- **Indian Numbering System (`en-IN` / `hi-IN`)**: Supports lakh/crore grouping (`₹12,34,567.89`).
- **Currency Precision**: Automatically handles 0-decimal (`JPY`), 2-decimal (`USD`, `EUR`, `GBP`, `INR`), and 3-decimal (`BHD`) currencies, plus accounting negative notation (`($250.50)`).
