"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  Download,
  Landmark,
  Plus,
  Repeat,
  Search,
  Trash2,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApp } from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { cn, formatCurrency, todayIso } from "@/lib/utils";

const CHART_COLORS = ["#8b5cf6", "#3b82f6", "#84cc16", "#06b6d4", "#f59e0b", "#f43f5e"];

export default function FinancePage() {
  const { user, notify, dataVersion, triggerRefresh } = useApp();

  const [activeTab, setActiveTab] = useState<
    "overview" | "transactions" | "budgets" | "accounts" | "recurring" | "import"
  >("overview");
  const [currency, setCurrency] = useState(
    user?.preferences.base_currency || "INR"
  );
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
  });
  const [endDate, setEndDate] = useState(todayIso());

  const [summary, setSummary] = useState<any | null>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [recurringRules, setRecurringRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [txTypeFilter, setTxTypeFilter] = useState("");
  const [search, setSearch] = useState("");

  // Modals
  const [txModalOpen, setTxModalOpen] = useState(false);
  const [txAmount, setTxAmount] = useState("");
  const [txType, setTxType] = useState<"expense" | "income" | "transfer">("expense");
  const [txCategory, setTxCategory] = useState("Food & Dining");
  const [txMerchant, setTxMerchant] = useState("");
  const [txDate, setTxDate] = useState(todayIso());
  const [txAccountId, setTxAccountId] = useState("");
  const [txToAccountId, setTxToAccountId] = useState("");
  const [txPaymentMethod, setTxPaymentMethod] = useState("UPI");
  const [txNotes, setTxNotes] = useState("");

  // Budget form
  const [budgetName, setBudgetName] = useState("Monthly Overall Budget");
  const [budgetMonth, setBudgetMonth] = useState(todayIso().slice(0, 7));
  const [budgetCategory, setBudgetCategory] = useState("ALL");
  const [budgetLimit, setBudgetLimit] = useState("25000");

  // Account form
  const [accName, setAccName] = useState("");
  const [accType, setAccType] = useState("checking");
  const [accInitial, setAccInitial] = useState("0.00");

  // Recurring rule form
  const [recTitle, setRecTitle] = useState("");
  const [recAmount, setRecAmount] = useState("");
  const [recCategory, setRecCategory] = useState("Subscriptions");
  const [recFreq, setRecFreq] = useState("monthly");

  // CSV Import state
  const [csvText, setCsvText] = useState(
    `transaction_date,amount,currency,transaction_type,category,merchant,payment_method,notes\n${todayIso()},320.00,INR,expense,Food & Dining,South Indian Cafe,UPI,Breakfast`
  );
  const [importPreview, setImportPreview] = useState<any | null>(null);

  const loadFinanceData = useCallback(async () => {
    try {
      setLoading(true);
      const [sumRes, txRes, accRes, budRes, recRes] = await Promise.all([
        apiFetch(
          `/finance/summary?start_date=${startDate}&end_date=${endDate}&currency=${currency}`
        ),
        apiFetch(
          `/transactions?start_date=${startDate}&end_date=${endDate}&currency=${currency}${
            txTypeFilter ? `&transaction_type=${txTypeFilter}` : ""
          }${search ? `&search=${encodeURIComponent(search)}` : ""}`
        ),
        apiFetch<any[]>("/accounts"),
        apiFetch<any[]>(`/budgets?currency=${currency}`),
        apiFetch<any[]>("/finance/recurring"),
      ]);
      setSummary(sumRes);
      setTransactions(txRes.items || []);
      setAccounts(accRes);
      if (accRes.length > 0 && !txAccountId) {
        setTxAccountId(accRes[0].id);
      }
      setBudgets(budRes);
      setRecurringRules(recRes);
    } catch (err: any) {
      notify("Failed to load finance data", err.message, "error");
    } finally {
      setLoading(false);
    }
  }, [currency, endDate, notify, search, startDate, txAccountId, txTypeFilter]);

  useEffect(() => {
    loadFinanceData();
  }, [loadFinanceData, dataVersion]);

  const handleSaveTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/transactions", {
        method: "POST",
        body: JSON.stringify({
          amount: txAmount,
          currency,
          transaction_type: txType,
          category: txType === "transfer" ? "Transfer" : txCategory,
          merchant: txMerchant || null,
          transaction_date: txDate,
          account_id: txAccountId || null,
          to_account_id: txType === "transfer" ? txToAccountId || null : null,
          payment_method: txPaymentMethod,
          notes: txNotes || null,
        }),
      });
      notify("Transaction saved", `${currency} ${txAmount}`, "success");
      setTxModalOpen(false);
      setTxAmount("");
      setTxMerchant("");
      setTxNotes("");
      triggerRefresh();
    } catch (err: any) {
      notify("Failed to save transaction", err.message, "error");
    }
  };

  const handleDeleteTransaction = async (id: string) => {
    try {
      await apiFetch(`/transactions/${id}`, { method: "DELETE" });
      notify("Transaction deleted", undefined, "info");
      triggerRefresh();
    } catch (err: any) {
      notify("Delete failed", err.message, "error");
    }
  };

  const handleCreateBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/budgets", {
        method: "POST",
        body: JSON.stringify({
          name: budgetName,
          month: budgetMonth,
          category: budgetCategory,
          currency,
          amount_limit: budgetLimit,
          alert_threshold_percent: 85,
        }),
      });
      notify("Budget saved", `${budgetName} (${budgetMonth})`, "success");
      triggerRefresh();
    } catch (err: any) {
      notify("Could not save budget", err.message, "error");
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/accounts", {
        method: "POST",
        body: JSON.stringify({
          name: accName,
          account_type: accType,
          currency,
          initial_balance: accInitial,
        }),
      });
      notify("Account created", accName, "success");
      setAccName("");
      triggerRefresh();
    } catch (err: any) {
      notify("Failed to create account", err.message, "error");
    }
  };

  const handleCreateRecurring = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/finance/recurring", {
        method: "POST",
        body: JSON.stringify({
          title: recTitle,
          amount: recAmount,
          currency,
          transaction_type: "expense",
          category: recCategory,
          frequency: recFreq,
          start_date: todayIso(),
          account_id: txAccountId || null,
        }),
      });
      notify("Recurring rule created & evaluated", recTitle, "success");
      setRecTitle("");
      setRecAmount("");
      triggerRefresh();
    } catch (err: any) {
      notify("Failed to create recurring rule", err.message, "error");
    }
  };

  const handlePreviewCsv = async () => {
    try {
      const res = await apiFetch("/import/preview", {
        method: "POST",
        body: JSON.stringify({
          domain: "transactions",
          filename: "finance_import.csv",
          csv_content: csvText,
          default_currency: currency,
        }),
      });
      setImportPreview(res);
      notify(
        "CSV Preview Ready",
        `${res.valid_rows} valid, ${res.duplicate_rows} duplicate, ${res.error_rows} error rows`,
        "info"
      );
    } catch (err: any) {
      notify("CSV preview failed", err.message, "error");
    }
  };

  const handleCommitCsv = async () => {
    if (!importPreview) return;
    try {
      const res = await apiFetch("/import/commit", {
        method: "POST",
        body: JSON.stringify({
          import_job_id: importPreview.import_job_id,
          skip_duplicates: true,
        }),
      });
      notify("CSV Import Committed", `Imported ${res.imported_rows} transaction(s)`, "success");
      setImportPreview(null);
      setActiveTab("transactions");
      triggerRefresh();
    } catch (err: any) {
      notify("CSV commit failed", err.message, "error");
    }
  };

  const handleExportCsv = async () => {
    try {
      const csvStr = await apiFetch<string>(
        "/export?format=csv&domain=transactions"
      );
      const blob = new Blob([csvStr], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `personal_life_os_transactions_${todayIso()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      notify("Export failed", err.message, "error");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Personal Finance</h1>
          <p className="text-xs text-muted mt-0.5">
            Exact Decimal ledger · Transfers excluded from income/expense totals · Multi-currency separation
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="rounded-xl bg-card border border-border px-3 py-2 text-xs font-medium"
          >
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
            <option value="EUR">EUR (€)</option>
            <option value="GBP">GBP (£)</option>
          </select>

          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-xl bg-card border border-border px-3 py-1.5 text-xs"
          />
          <span className="text-xs text-muted">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-xl bg-card border border-border px-3 py-1.5 text-xs"
          />

          <button
            onClick={handleExportCsv}
            className="flex items-center gap-1.5 rounded-xl bg-card border border-border px-3 py-2 text-xs text-muted hover:text-foreground"
          >
            <Download className="h-3.5 w-3.5" />
            <span>CSV Export</span>
          </button>

          <button
            onClick={() => setTxModalOpen(true)}
            className="flex items-center gap-1.5 rounded-xl bg-accent-violet hover:bg-accent-violet/90 text-white px-4 py-2 text-xs font-medium"
          >
            <Plus className="h-4 w-4" />
            <span>Add Transaction</span>
          </button>
        </div>
      </div>

      {/* Multi-Currency Separation Notice if multiple currencies exist in period */}
      {summary?.currencies_present?.length > 1 && (
        <div className="rounded-xl bg-accent-blue/10 border border-accent-blue/30 p-3.5 text-xs flex flex-wrap items-center justify-between gap-2">
          <span>
            <strong>Multi-Currency Isolation Active:</strong> Viewing{" "}
            <strong>{currency}</strong> records. Other currencies recorded in this period are never silently combined:
          </span>
          <div className="flex gap-2">
            {summary.currencies_present.map((c: string) => (
              <button
                key={c}
                onClick={() => setCurrency(c)}
                className={cn(
                  "px-2.5 py-1 rounded-lg font-mono text-[11px] border",
                  c === currency
                    ? "bg-accent-blue text-white border-accent-blue"
                    : "bg-surface border-border text-muted"
                )}
              >
                {c}: Exp {summary.by_currency_totals[c]?.expense}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Summary Metric Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl bg-card border border-border p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span>Total Expenses ({currency})</span>
              <ArrowDownRight className="h-4 w-4 text-accent-danger" />
            </div>
            <div className="text-2xl font-semibold">
              {formatCurrency(summary.total_expense, currency)}
            </div>
            <p className="text-[11px] text-muted mt-1">
              {summary.period_comparison?.explanation}
            </p>
          </div>

          <div className="rounded-xl bg-card border border-border p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span>Total Income ({currency})</span>
              <ArrowUpRight className="h-4 w-4 text-accent-lime" />
            </div>
            <div className="text-2xl font-semibold text-accent-lime">
              {formatCurrency(summary.total_income, currency)}
            </div>
            <p className="text-[11px] text-muted mt-1">
              Savings Rate:{" "}
              {summary.savings_rate_percent !== null
                ? `${summary.savings_rate_percent}%`
                : "N/A"}
            </p>
          </div>

          <div className="rounded-xl bg-card border border-border p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span>Net Cashflow ({currency})</span>
              <Wallet className="h-4 w-4 text-accent-violet" />
            </div>
            <div className="text-2xl font-semibold">
              {formatCurrency(summary.net_savings, currency)}
            </div>
            <p className="text-[11px] text-muted mt-1">
              Transfers excluded: {formatCurrency(summary.total_transfers_excluded, currency)}
            </p>
          </div>

          <div className="rounded-xl bg-card border border-border p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span>Active Accounts Balance</span>
              <Landmark className="h-4 w-4 text-accent-blue" />
            </div>
            <div className="text-2xl font-semibold">
              {formatCurrency(
                accounts
                  .filter((a) => a.currency === currency)
                  .reduce((acc, a) => acc + parseFloat(a.current_balance || "0"), 0),
                currency
              )}
            </div>
            <p className="text-[11px] text-muted mt-1">
              Across {accounts.filter((a) => a.currency === currency).length} {currency} account(s)
            </p>
          </div>
        </div>
      )}

      {/* Sub-navigation Tabs */}
      <div className="flex flex-wrap gap-1.5 border-b border-border pb-2 text-xs">
        {(
          [
            ["overview", "Analytics & Breakdowns"],
            ["transactions", `Transactions (${transactions.length})`],
            ["budgets", `Budgets (${budgets.length})`],
            ["accounts", `Accounts (${accounts.length})`],
            ["recurring", `Recurring Rules (${recurringRules.length})`],
            ["import", "CSV Import & Preview"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              "px-3.5 py-2 rounded-xl font-medium transition",
              activeTab === key
                ? "bg-accent-violet/15 text-accent-violet border border-accent-violet/30"
                : "text-muted hover:text-foreground hover:bg-card"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* TAB 1: OVERVIEW CHARTS & LARGEST EXPENSES */}
      {activeTab === "overview" && summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 rounded-2xl bg-card border border-border p-5">
              <h2 className="text-sm font-semibold mb-1">
                Income vs Expense Daily Timeline ({currency})
              </h2>
              <p className="text-xs text-muted mb-4">
                Transfers are automatically excluded from consolidated income and expense bars
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summary.daily_series || []}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#242b3a" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: "#8b9bb4" }}
                      tickFormatter={(v) => v.slice(5)}
                    />
                    <YAxis tick={{ fontSize: 11, fill: "#8b9bb4" }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#141821",
                        borderColor: "#242b3a",
                        borderRadius: "10px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="income" name="Income" fill="#84cc16" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="expense" name="Expense" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl bg-card border border-border p-5">
              <h2 className="text-sm font-semibold mb-1">Category Breakdown</h2>
              <p className="text-xs text-muted mb-4">Share of total expenses</p>
              {summary.category_breakdown?.length > 0 ? (
                <div className="space-y-2.5">
                  {summary.category_breakdown.map((cat: any, idx: number) => (
                    <div key={cat.category} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium">{cat.category}</span>
                        <span className="font-mono text-muted">
                          {formatCurrency(cat.amount, currency)} ({cat.percentage}%)
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-surface overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, cat.percentage)}%`,
                            backgroundColor: CHART_COLORS[idx % CHART_COLORS.length],
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted py-12 text-center">
                  No expense categories recorded in this period.
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl bg-card border border-border p-5">
              <h2 className="text-sm font-semibold mb-3">Top Merchants & Recipients</h2>
              {summary.merchant_breakdown?.length > 0 ? (
                <div className="space-y-2">
                  {summary.merchant_breakdown.map((m: any) => (
                    <div
                      key={m.merchant}
                      className="flex items-center justify-between rounded-xl bg-surface border border-border px-3.5 py-2 text-xs"
                    >
                      <span className="font-medium">{m.merchant}</span>
                      <span className="font-mono">
                        {formatCurrency(m.amount, currency)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted py-6 text-center">
                  No merchant records in this period.
                </p>
              )}
            </div>

            <div className="rounded-2xl bg-card border border-border p-5">
              <h2 className="text-sm font-semibold mb-3">Largest Individual Expenses</h2>
              {summary.largest_expenses?.length > 0 ? (
                <div className="space-y-2">
                  {summary.largest_expenses.map((t: any) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between rounded-xl bg-surface border border-border px-3.5 py-2 text-xs"
                    >
                      <div>
                        <p className="font-medium">
                          {t.merchant || t.category}{" "}
                          <span className="text-muted">({t.category})</span>
                        </p>
                        <p className="text-[11px] text-muted">{t.transaction_date}</p>
                      </div>
                      <span className="font-mono font-semibold text-accent-danger">
                        -{formatCurrency(t.amount, t.currency)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted py-6 text-center">
                  No expenses recorded in this period.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: TRANSACTIONS TABLE */}
      {activeTab === "transactions" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-card border border-border p-4">
            <div className="flex items-center gap-2">
              {(
                [
                  ["", "All Types"],
                  ["expense", "Expenses"],
                  ["income", "Income"],
                  ["transfer", "Transfers"],
                ] as const
              ).map(([val, label]) => (
                <button
                  key={val}
                  onClick={() => setTxTypeFilter(val)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium border",
                    txTypeFilter === val
                      ? "bg-accent-violet/15 border-accent-violet/40 text-accent-violet"
                      : "bg-surface border-border text-muted"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-surface border border-border px-3 py-1.5 w-full sm:w-64">
              <Search className="h-3.5 w-3.5 text-muted" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search category, merchant, notes..."
                className="bg-transparent text-xs text-foreground outline-none w-full"
              />
            </div>
          </div>

          <div className="rounded-2xl bg-card border border-border overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-surface text-muted">
                  <th className="text-left p-3.5">Date</th>
                  <th className="text-left p-3.5">Type</th>
                  <th className="text-left p-3.5">Category</th>
                  <th className="text-left p-3.5">Merchant / Notes</th>
                  <th className="text-left p-3.5">Account</th>
                  <th className="text-right p-3.5">Amount</th>
                  <th className="text-right p-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-muted">
                      No transactions match the selected filters.
                    </td>
                  </tr>
                ) : (
                  transactions.map((t) => (
                    <tr key={t.id} className="border-b border-border/60 hover:bg-surface/40">
                      <td className="p-3.5 font-mono">{t.transaction_date}</td>
                      <td className="p-3.5 capitalize">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-medium",
                            t.transaction_type === "expense" &&
                              "bg-accent-danger/15 text-accent-danger",
                            t.transaction_type === "income" &&
                              "bg-accent-lime/15 text-accent-lime",
                            t.transaction_type === "transfer" &&
                              "bg-accent-blue/15 text-accent-blue"
                          )}
                        >
                          {t.transaction_type}
                        </span>
                      </td>
                      <td className="p-3.5 font-medium">{t.category}</td>
                      <td className="p-3.5 text-muted">
                        {t.merchant || t.notes || "—"}
                      </td>
                      <td className="p-3.5 text-muted">
                        {t.account_name || "Unassigned"}
                        {t.to_account_name ? ` → ${t.to_account_name}` : ""}
                      </td>
                      <td className="p-3.5 text-right font-mono font-semibold">
                        {formatCurrency(t.amount, t.currency)}
                      </td>
                      <td className="p-3.5 text-right">
                        <button
                          onClick={() => handleDeleteTransaction(t.id)}
                          className="p-1 text-muted hover:text-accent-danger"
                          title="Delete transaction"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: BUDGETS */}
      {activeTab === "budgets" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <form
            onSubmit={handleCreateBudget}
            className="rounded-2xl bg-card border border-border p-5 space-y-4 text-xs h-fit"
          >
            <h3 className="text-sm font-semibold">Create / Update Monthly Budget</h3>
            <div>
              <label className="block text-muted mb-1">Budget Name</label>
              <input
                type="text"
                required
                value={budgetName}
                onChange={(e) => setBudgetName(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-muted mb-1">Month (YYYY-MM)</label>
                <input
                  type="month"
                  required
                  value={budgetMonth}
                  onChange={(e) => setBudgetMonth(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-muted mb-1">
                  Category (&apos;ALL&apos; for overall)
                </label>
                <input
                  type="text"
                  required
                  value={budgetCategory}
                  onChange={(e) => setBudgetCategory(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-muted mb-1">
                Monthly Limit ({currency})
              </label>
              <input
                type="number"
                step="0.01"
                min="1"
                required
                value={budgetLimit}
                onChange={(e) => setBudgetLimit(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-xl bg-accent-violet text-white py-2 font-medium"
            >
              Save Budget
            </button>
          </form>

          <div className="lg:col-span-2 space-y-3">
            {budgets.length === 0 ? (
              <div className="rounded-2xl bg-card border border-border p-8 text-center text-xs text-muted">
                No budgets configured yet. Create an overall monthly budget or category-specific budget on the left.
              </div>
            ) : (
              budgets.map((b) => (
                <div
                  key={b.id}
                  className="rounded-2xl bg-card border border-border p-5 space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold">
                        {b.name}{" "}
                        <span className="text-xs font-normal text-muted">
                          ({b.month} · Category: {b.category})
                        </span>
                      </h4>
                    </div>
                    <span
                      className={cn(
                        "font-mono text-xs font-semibold px-2.5 py-0.5 rounded-full",
                        b.is_over_budget
                          ? "bg-accent-danger/20 text-accent-danger"
                          : b.is_threshold_crossed
                          ? "bg-accent-amber/20 text-accent-amber"
                          : "bg-accent-lime/20 text-accent-lime"
                      )}
                    >
                      {b.utilization_percent}% used
                    </span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-surface overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        b.is_over_budget
                          ? "bg-accent-danger"
                          : b.is_threshold_crossed
                          ? "bg-accent-amber"
                          : "bg-accent-lime"
                      )}
                      style={{ width: `${Math.min(100, b.utilization_percent)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted">
                    <span>
                      Spent: {formatCurrency(b.spent_amount, b.currency)} of{" "}
                      {formatCurrency(b.amount_limit, b.currency)}
                    </span>
                    <span>
                      Remaining: {formatCurrency(b.remaining_amount, b.currency)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 4: ACCOUNTS */}
      {activeTab === "accounts" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <form
            onSubmit={handleCreateAccount}
            className="rounded-2xl bg-card border border-border p-5 space-y-4 text-xs h-fit"
          >
            <h3 className="text-sm font-semibold">Add Account or Wallet</h3>
            <div>
              <label className="block text-muted mb-1">Account Name</label>
              <input
                type="text"
                required
                value={accName}
                onChange={(e) => setAccName(e.target.value)}
                placeholder="e.g. SBI Savings, Cash Wallet"
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-muted mb-1">Account Type</label>
              <select
                value={accType}
                onChange={(e) => setAccType(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              >
                <option value="checking">Checking / Bank</option>
                <option value="savings">Savings</option>
                <option value="wallet">Digital Wallet / UPI</option>
                <option value="cash">Cash</option>
                <option value="credit_card">Credit Card</option>
                <option value="investment">Investment</option>
              </select>
            </div>
            <div>
              <label className="block text-muted mb-1">
                Opening Balance ({currency})
              </label>
              <input
                type="number"
                step="0.01"
                required
                value={accInitial}
                onChange={(e) => setAccInitial(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-xl bg-accent-violet text-white py-2 font-medium"
            >
              Create Account
            </button>
          </form>

          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {accounts.map((a) => (
              <div
                key={a.id}
                className="rounded-2xl bg-card border border-border p-5 flex flex-col justify-between"
              >
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-muted bg-surface px-2 py-0.5 rounded">
                    {a.account_type} · {a.currency}
                  </span>
                  <h4 className="text-base font-semibold mt-2">{a.name}</h4>
                </div>
                <div className="mt-4 pt-3 border-t border-border">
                  <span className="text-xs text-muted block">Current Computed Balance</span>
                  <span className="text-xl font-mono font-semibold text-accent-lime">
                    {formatCurrency(a.current_balance, a.currency)}
                  </span>
                  <span className="text-[11px] text-muted block mt-0.5">
                    Initial: {formatCurrency(a.initial_balance, a.currency)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: RECURRING TRANSACTION RULES */}
      {activeTab === "recurring" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <form
            onSubmit={handleCreateRecurring}
            className="rounded-2xl bg-card border border-border p-5 space-y-4 text-xs h-fit"
          >
            <h3 className="text-sm font-semibold">New Recurring Transaction Rule</h3>
            <p className="text-[11px] text-muted">
              Tracks each scheduled occurrence date so duplicate transactions are never created.
            </p>
            <div>
              <label className="block text-muted mb-1">Rule Title / Merchant</label>
              <input
                type="text"
                required
                value={recTitle}
                onChange={(e) => setRecTitle(e.target.value)}
                placeholder="e.g. Broadband Fiber Plan"
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-muted mb-1">Amount ({currency})</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={recAmount}
                  onChange={(e) => setRecAmount(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-muted mb-1">Frequency</label>
                <select
                  value={recFreq}
                  onChange={(e) => setRecFreq(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-muted mb-1">Category</label>
              <input
                type="text"
                required
                value={recCategory}
                onChange={(e) => setRecCategory(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-xl bg-accent-violet text-white py-2 font-medium"
            >
              Create Rule
            </button>
          </form>

          <div className="lg:col-span-2 space-y-3">
            {recurringRules.length === 0 ? (
              <div className="rounded-2xl bg-card border border-border p-8 text-center text-xs text-muted">
                No recurring transaction rules defined yet.
              </div>
            ) : (
              recurringRules.map((r) => (
                <div
                  key={r.id}
                  className="rounded-2xl bg-card border border-border p-4 flex items-center justify-between text-xs"
                >
                  <div>
                    <p className="font-semibold text-sm">{r.title}</p>
                    <p className="text-muted mt-0.5">
                      {r.category} · {r.frequency} · Next due: {r.next_due_date} (Last generated:{" "}
                      {r.last_generated_date || "—"})
                    </p>
                  </div>
                  <span className="font-mono font-semibold text-sm">
                    {formatCurrency(r.amount, r.currency)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 6: CSV IMPORT WIZARD WITH PREVIEW & DUPLICATE DETECTION */}
      {activeTab === "import" && (
        <div className="rounded-2xl bg-card border border-border p-6 space-y-4 text-xs">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">
                Local CSV Transaction Import & Duplicate Detection
              </h3>
              <p className="text-muted mt-0.5">
                Paste CSV rows or load a local CSV file. Duplicate hashes are automatically flagged before commit.
              </p>
            </div>
          </div>

          <textarea
            rows={6}
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            className="w-full rounded-xl bg-surface border border-border p-3 font-mono text-xs"
          />

          <div className="flex gap-2">
            <button
              onClick={handlePreviewCsv}
              className="rounded-xl bg-accent-violet text-white px-4 py-2 font-medium"
            >
              1. Preview & Validate CSV
            </button>
            {importPreview && (
              <button
                onClick={handleCommitCsv}
                className="rounded-xl bg-accent-lime text-black px-4 py-2 font-semibold"
              >
                2. Commit {importPreview.valid_rows} Valid Row(s)
              </button>
            )}
          </div>

          {importPreview && (
            <div className="space-y-3 pt-3 border-t border-border">
              <div className="flex gap-4 text-xs">
                <span>Total Rows: {importPreview.total_rows}</span>
                <span className="text-accent-lime">Valid: {importPreview.valid_rows}</span>
                <span className="text-accent-amber">
                  Duplicates: {importPreview.duplicate_rows}
                </span>
                <span className="text-accent-danger">Errors: {importPreview.error_rows}</span>
              </div>
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-surface border-b border-border text-muted">
                      <th className="p-2 text-left">Row</th>
                      <th className="p-2 text-left">Status</th>
                      <th className="p-2 text-left">Date</th>
                      <th className="p-2 text-left">Amount</th>
                      <th className="p-2 text-left">Category</th>
                      <th className="p-2 text-left">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importPreview.rows.map((r: any) => (
                      <tr key={r.row_number} className="border-b border-border/50">
                        <td className="p-2 font-mono">{r.row_number}</td>
                        <td className="p-2 font-semibold capitalize">{r.status}</td>
                        <td className="p-2">{r.normalized?.transaction_date}</td>
                        <td className="p-2 font-mono">{r.normalized?.amount}</td>
                        <td className="p-2">{r.normalized?.category}</td>
                        <td className="p-2 text-muted">{r.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Add Transaction Modal */}
      {txModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
            onClick={() => setTxModalOpen(false)}
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl bg-card border border-border p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold">Record Transaction</h2>
              <button
                onClick={() => setTxModalOpen(false)}
                className="p-1 rounded-lg text-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleSaveTransaction} className="space-y-4 text-xs">
              <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-surface border border-border">
                {(["expense", "income", "transfer"] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTxType(t)}
                    className={cn(
                      "py-1.5 rounded-lg font-medium capitalize",
                      txType === t
                        ? "bg-accent-violet text-white"
                        : "text-muted hover:text-foreground"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted mb-1">Amount ({currency})</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={txAmount}
                    onChange={(e) => setTxAmount(e.target.value)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-muted mb-1">Date</label>
                  <input
                    type="date"
                    required
                    value={txDate}
                    onChange={(e) => setTxDate(e.target.value)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {txType !== "transfer" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-muted mb-1">Category</label>
                    <input
                      type="text"
                      required
                      value={txCategory}
                      onChange={(e) => setTxCategory(e.target.value)}
                      className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-muted mb-1">Merchant / Source</label>
                    <input
                      type="text"
                      value={txMerchant}
                      onChange={(e) => setTxMerchant(e.target.value)}
                      className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted mb-1">
                    {txType === "transfer" ? "From Account" : "Account"}
                  </label>
                  <select
                    value={txAccountId}
                    onChange={(e) => setTxAccountId(e.target.value)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  >
                    <option value="">Unassigned</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.currency})
                      </option>
                    ))}
                  </select>
                </div>
                {txType === "transfer" ? (
                  <div>
                    <label className="block text-muted mb-1">To Account</label>
                    <select
                      value={txToAccountId}
                      onChange={(e) => setTxToAccountId(e.target.value)}
                      className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                    >
                      <option value="">Select target</option>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name} ({a.currency})
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div>
                    <label className="block text-muted mb-1">Payment Method</label>
                    <input
                      type="text"
                      value={txPaymentMethod}
                      onChange={(e) => setTxPaymentMethod(e.target.value)}
                      className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                    />
                  </div>
                )}
              </div>

              <div>
                <label className="block text-muted mb-1">Notes</label>
                <input
                  type="text"
                  value={txNotes}
                  onChange={(e) => setTxNotes(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setTxModalOpen(false)}
                  className="rounded-lg bg-surface border border-border px-4 py-2 text-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-accent-violet text-white px-4 py-2 font-medium"
                >
                  Save Transaction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

