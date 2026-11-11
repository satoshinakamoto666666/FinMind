# Smart Caching Strategy for Dashboard & Analytics (#127)

## Architecture
- **Cache-Aside with Deterministic Fingerprinting**: Keys are scoped by `user_id`, `namespace` (`dashboard`, `analytics`, `digest`, `budgets`, `savings`), and SHA-256 query parameter digest.
- **Mutation-Driven Tag Invalidation**: Expense, income, budget, and account mutations automatically evict only the affected user's dependent analytical namespaces without flushing unrelated users.
