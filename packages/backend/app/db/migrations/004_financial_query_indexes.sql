-- Migration 004: Composite & Partial Indexes for High-Frequency Financial Queries (#128)
CREATE INDEX IF NOT EXISTS idx_expenses_user_date_category
    ON expenses (user_id, date DESC, category);

CREATE INDEX IF NOT EXISTS idx_expenses_user_account_date
    ON expenses (user_id, account_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_incomes_user_date
    ON incomes (user_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_budgets_user_category_period
    ON budgets (user_id, category, period);

CREATE INDEX IF NOT EXISTS idx_recurring_expenses_active_next_due
    ON recurring_expenses (user_id, next_due_date)
    WHERE active = 1;
