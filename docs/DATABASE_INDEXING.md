# Database Indexing Optimization for Financial Queries (#128)

## Summary
Adds composite and partial indexes across `expenses`, `incomes`, `budgets`, and `recurring_expenses` to eliminate full-table scans on dashboard, digest, and multi-account queries.
