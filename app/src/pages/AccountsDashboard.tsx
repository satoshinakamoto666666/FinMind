import React, { useEffect, useState } from "react";
import {
  MultiAccountOverview,
  createFinancialAccount,
  fetchMultiAccountOverview,
} from "../api/accounts";

export default function AccountsDashboard() {
  const [overview, setOverview] = useState<MultiAccountOverview | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined);
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState("CHECKING");
  const [initialBalance, setInitialBalance] = useState("0");

  const load = async (accId?: number) => {
    const data = await fetchMultiAccountOverview(undefined, accId);
    setOverview(data);
  };

  useEffect(() => {
    load(selectedAccountId);
  }, [selectedAccountId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createFinancialAccount({
      name: name.trim(),
      account_type: accountType,
      initial_balance: parseFloat(initialBalance || "0"),
    });
    setName("");
    setInitialBalance("0");
    await load(selectedAccountId);
  };

  if (!overview) {
    return <div className="p-6">Loading multi-account overview...</div>;
  }

  const { consolidated, base_currency, accounts, recent_transactions } = overview;

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Multi-Account Financial Overview</h1>
          <p className="text-sm text-gray-500">
            Consolidated net worth, account balances, and cross-account cashflow in {base_currency}
          </p>
        </div>
        <select
          value={selectedAccountId ?? ""}
          onChange={(e) =>
            setSelectedAccountId(e.target.value ? Number(e.target.value) : undefined)
          }
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All Accounts ({consolidated.account_count})</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.account_type})
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded border bg-white">
          <div className="text-xs text-gray-500">Consolidated Net Worth</div>
          <div className="text-xl font-bold">
            {base_currency} {consolidated.net_worth.toLocaleString()}
          </div>
        </div>
        <div className="p-4 rounded border bg-white">
          <div className="text-xs text-gray-500">Total Assets</div>
          <div className="text-xl font-semibold text-emerald-600">
            {base_currency} {consolidated.total_assets.toLocaleString()}
          </div>
        </div>
        <div className="p-4 rounded border bg-white">
          <div className="text-xs text-gray-500">Total Liabilities</div>
          <div className="text-xl font-semibold text-red-600">
            {base_currency} {consolidated.total_liabilities.toLocaleString()}
          </div>
        </div>
        <div className="p-4 rounded border bg-white">
          <div className="text-xs text-gray-500">Monthly Net Flow</div>
          <div className="text-xl font-semibold">
            {base_currency} {consolidated.monthly_net_flow.toLocaleString()}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {accounts.map((acc) => (
          <div key={acc.id} className="p-4 rounded border bg-white space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{acc.name}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-gray-100">{acc.account_type}</span>
            </div>
            <div className="text-2xl font-bold">
              {acc.currency} {acc.current_balance.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 flex justify-between">
              <span>Share: {acc.share_pct}%</span>
              <span>Txns: {acc.transaction_count}</span>
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={handleCreate} className="p-4 rounded border bg-white flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500">Account Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. HDFC Savings"
            className="border rounded px-3 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Type</label>
          <select
            value={accountType}
            onChange={(e) => setAccountType(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm"
          >
            <option value="CHECKING">Checking</option>
            <option value="SAVINGS">Savings</option>
            <option value="CREDIT_CARD">Credit Card</option>
            <option value="WALLET">Wallet</option>
            <option value="INVESTMENT">Investment</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Initial Balance</label>
          <input
            type="number"
            value={initialBalance}
            onChange={(e) => setInitialBalance(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm w-32"
          />
        </div>
        <button type="submit" className="px-4 py-1.5 rounded bg-indigo-600 text-white text-sm">
          Add Account
        </button>
      </form>

      <div className="p-4 rounded border bg-white">
        <h2 className="font-semibold mb-3">Recent Multi-Account Transactions</h2>
        <div className="space-y-2 text-sm">
          {recent_transactions.map((tx) => (
            <div key={tx.id} className="flex justify-between border-b pb-2">
              <div>
                <span className="font-medium">{tx.description}</span>
                <span className="ml-2 text-xs text-gray-500">[{tx.account_name}]</span>
              </div>
              <div className={tx.type === "INCOME" ? "text-emerald-600 font-medium" : "text-gray-900"}>
                {tx.type === "INCOME" ? "+" : "-"}
                {tx.currency} {tx.amount}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
