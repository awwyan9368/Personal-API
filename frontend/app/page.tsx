"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Eye,
  EyeOff,
  Flame,
  HeartPulse,
  MonitorSmartphone,
  Moon,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Target,
  Wallet,
} from "lucide-react";
import {
  Area,
  AreaChart,
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
import { cn, formatCurrency, formatMinutes, todayIso } from "@/lib/utils";

const ALL_WIDGET_IDS = [
  { id: "habits", label: "Today's Habit Completion" },
  { id: "streaks", label: "Active Habit Streaks" },
  { id: "expenses", label: "Monthly Expenses" },
  { id: "income", label: "Monthly Income & Net" },
  { id: "budget", label: "Budget Utilization" },
  { id: "screen_time", label: "Today's Screen Time" },
  { id: "focus_time", label: "Today's Focus Time" },
  { id: "activity_time", label: "Recorded Activity Time" },
  { id: "sleep", label: "Sleep Duration" },
  { id: "mood_energy", label: "Mood & Energy" },
  { id: "goals", label: "Active Goals Progress" },
];

const PIE_COLORS = ["#8b5cf6", "#3b82f6", "#84cc16", "#06b6d4", "#f59e0b", "#f43f5e"];

export default function OverviewPage() {
  const router = useRouter();
  const { user, refreshUser, openQuickAdd, notify, dataVersion, triggerRefresh } = useApp();

  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [intentionInput, setIntentionInput] = useState("");
  const [editingIntention, setEditingIntention] = useState(false);
  const [customizingWidgets, setCustomizingWidgets] = useState(false);

  // Local Natural Language Query tool state
  const [nlqInput, setNlqInput] = useState("");
  const [nlqResult, setNlqResult] = useState<any | null>(null);
  const [nlqLoading, setNlqLoading] = useState(false);

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiFetch("/dashboard");
      setData(res);
      setIntentionInput(res.today_intention || "");
    } catch (err: any) {
      notify("Failed to load dashboard", err.message, "error");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard, dataVersion]);

  const handleSaveIntention = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          today_intention: intentionInput,
          today_intention_date: todayIso(),
        }),
      });
      await refreshUser();
      await loadDashboard();
      setEditingIntention(false);
      notify("Today's intention updated", intentionInput, "success");
    } catch (err: any) {
      notify("Could not update intention", err.message, "error");
    }
  };

  const handleToggleWidget = async (widgetId: string) => {
    if (!data) return;
    const currentList: string[] = data.widgets_order || [];
    const nextList = currentList.includes(widgetId)
      ? currentList.filter((w) => w !== widgetId)
      : [...currentList, widgetId];
    try {
      await apiFetch("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ dashboard_widgets: nextList }),
      });
      setData({ ...data, widgets_order: nextList });
      await refreshUser();
    } catch (err: any) {
      notify("Failed to update widget visibility", err.message, "error");
    }
  };

  const handleQuickToggleHabit = async (habit: any) => {
    try {
      await apiFetch(`/habits/${habit.id}/entries`, {
        method: "POST",
        body: JSON.stringify({
          entry_date: todayIso(),
          completed: !habit.completed_today,
          value: habit.target_value || "1.00",
        }),
      });
      triggerRefresh();
      notify(
        !habit.completed_today ? `Completed '${habit.name}'` : `Unmarked '${habit.name}'`,
        undefined,
        "success"
      );
    } catch (err: any) {
      notify("Failed to update habit", err.message, "error");
    }
  };

  const handleRunNlq = async (queryText?: string) => {
    const q = (queryText ?? nlqInput).trim();
    if (!q) return;
    setNlqInput(q);
    setNlqLoading(true);
    try {
      const res = await apiFetch("/nlq", {
        method: "POST",
        body: JSON.stringify({ query: q }),
      });
      setNlqResult(res);
    } catch (err: any) {
      notify("Query failed", err.message, "error");
    } finally {
      setNlqLoading(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="h-32 rounded-2xl bg-card border border-border animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-32 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const visibleWidgets: string[] = data.widgets_order || ALL_WIDGET_IDS.map((w) => w.id);
  const m = data.metrics;
  const cmp = data.period_comparisons;
  const currency = data.currency || user?.preferences.base_currency || "INR";

  const renderComparisonBadge = (comp: any, invertColors = false) => {
    if (!comp) return null;
    if (!comp.has_sufficient_previous_data) {
      return (
        <span
          title={comp.explanation}
          className="text-[11px] text-muted block mt-1.5 truncate"
        >
          {comp.explanation}
        </span>
      );
    }
    const isPositive = (comp.absolute_change || 0) >= 0;
    const isGood = invertColors ? !isPositive : isPositive;
    return (
      <div className="flex items-center gap-1.5 mt-1.5 text-[11px]">
        <span
          className={cn(
            "inline-flex items-center gap-0.5 font-medium px-1.5 py-0.5 rounded",
            isGood
              ? "bg-accent-lime/15 text-accent-lime"
              : "bg-accent-amber/15 text-accent-amber"
          )}
        >
          {isPositive ? (
            <ArrowUpRight className="h-3 w-3" />
          ) : (
            <ArrowDownRight className="h-3 w-3" />
          )}
          {comp.percentage_change !== null ? `${comp.percentage_change > 0 ? "+" : ""}${comp.percentage_change}%` : ""}
        </span>
        <span className="text-muted truncate" title={comp.explanation}>
          ({comp.absolute_change > 0 ? "+" : ""}
          {comp.absolute_change} {comp.unit} vs {comp.comparison_label})
        </span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Command Banner */}
      <section className="rounded-2xl bg-card border border-border p-5 lg:p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-violet/15 border border-accent-violet/30 px-2.5 py-0.5 text-[11px] font-medium text-accent-violet">
                <Sparkles className="h-3 w-3" /> Local Command Center
              </span>
              <span className="text-xs text-muted">{data.current_date}</span>
            </div>
            <h1 className="text-2xl lg:text-3xl font-semibold tracking-tight">
              {data.greeting}
            </h1>

            {/* Today's Intention */}
            <div className="pt-1">
              {editingIntention ? (
                <form onSubmit={handleSaveIntention} className="flex items-center gap-2 max-w-xl">
                  <input
                    type="text"
                    autoFocus
                    value={intentionInput}
                    onChange={(e) => setIntentionInput(e.target.value)}
                    placeholder="Set your primary focus or intention for today..."
                    className="flex-1 rounded-lg bg-surface border border-border px-3 py-1.5 text-xs text-foreground"
                  />
                  <button
                    type="submit"
                    className="rounded-lg bg-accent-violet text-white px-3 py-1.5 text-xs font-medium"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingIntention(false)}
                    className="rounded-lg bg-surface border border-border px-2.5 py-1.5 text-xs text-muted"
                  >
                    Cancel
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setEditingIntention(true)}
                  className="text-left text-xs text-muted hover:text-foreground transition group flex items-center gap-2"
                >
                  <span className="font-medium text-accent-violet">Today&apos;s Intention:</span>
                  <span className="italic">
                    {data.today_intention || "Click to set a clear intention for today..."}
                  </span>
                </button>
              )}
            </div>
          </div>

          {/* Quick Check-in & Review Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => openQuickAdd("wellbeing")}
              className={cn(
                "flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition",
                data.has_daily_checkin_today
                  ? "bg-accent-lime/10 border-accent-lime/30 text-accent-lime"
                  : "bg-surface border-border text-foreground hover:border-accent-violet/50"
              )}
            >
              <HeartPulse className="h-4 w-4" />
              <span>
                {data.has_daily_checkin_today ? "Check-in Logged" : "Daily Check-in"}
              </span>
            </button>

            <Link
              href="/journal?review=1"
              className="flex items-center gap-2 rounded-xl bg-surface border border-border hover:border-accent-violet/50 px-3.5 py-2 text-xs font-medium transition"
            >
              <BookOpen className="h-4 w-4 text-accent-violet" />
              <span>{data.has_daily_review_today ? "View Daily Review" : "Daily Review"}</span>
            </Link>

            <button
              onClick={() => setCustomizingWidgets((v) => !v)}
              className="flex items-center gap-1.5 rounded-xl bg-surface border border-border px-3 py-2 text-xs text-muted hover:text-foreground transition"
              title="Customize visible dashboard cards"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              <span>Widgets</span>
            </button>
          </div>
        </div>

        {/* Widget Customizer Panel */}
        {customizingWidgets && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs font-medium text-muted mb-2.5">
              Toggle visible dashboard metric cards (persisted to your local database):
            </p>
            <div className="flex flex-wrap gap-2">
              {ALL_WIDGET_IDS.map((w) => {
                const active = visibleWidgets.includes(w.id);
                return (
                  <button
                    key={w.id}
                    onClick={() => handleToggleWidget(w.id)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition",
                      active
                        ? "bg-accent-violet/15 border-accent-violet/40 text-accent-violet"
                        : "bg-surface border-border text-muted"
                    )}
                  >
                    {active ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                    <span>{w.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {/* Budget Alert Banner if any budget crossed threshold */}
      {m.budget_utilization?.alerts?.length > 0 && (
        <div className="rounded-xl bg-accent-amber/10 border border-accent-amber/40 p-4 flex items-center justify-between gap-4">
          <div className="text-xs">
            <p className="font-semibold text-accent-amber">Budget Threshold Alert</p>
            <p className="text-muted mt-0.5">{m.budget_utilization.alerts[0].message}</p>
          </div>
          <Link
            href="/finance"
            className="shrink-0 rounded-lg bg-accent-amber/20 hover:bg-accent-amber/30 text-accent-amber px-3 py-1.5 text-xs font-medium"
          >
            Inspect Budgets
          </Link>
        </div>
      )}

      {/* Local Natural-Language Query Bar (Zero External AI) */}
      <section className="rounded-2xl bg-card border border-border p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleRunNlq();
          }}
          className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5"
        >
          <div className="flex-1 flex items-center gap-2.5 rounded-xl bg-surface border border-border px-3.5 py-2">
            <Search className="h-4 w-4 text-accent-violet shrink-0" />
            <input
              type="text"
              value={nlqInput}
              onChange={(e) => setNlqInput(e.target.value)}
              placeholder="Ask your local data: 'How much did I spend on food last month?' or 'Which habit had the best completion rate?'"
              className="w-full bg-transparent text-xs text-foreground outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={nlqLoading}
            className="rounded-xl bg-accent-violet hover:bg-accent-violet/90 text-white px-4 py-2 text-xs font-medium shrink-0"
          >
            {nlqLoading ? "Analyzing..." : "Ask Local Engine"}
          </button>
        </form>
        <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
          <span className="text-[11px] text-muted">Quick questions:</span>
          {[
            "Which category accounted for the largest expenses?",
            "Which habit had the best completion rate?",
            "How much focus time did I record this week?",
            "What was my average daily screen time this month?",
          ].map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => handleRunNlq(sample)}
              className="text-[11px] rounded-full bg-surface hover:bg-panel border border-border px-2.5 py-0.5 text-muted hover:text-foreground transition"
            >
              {sample}
            </button>
          ))}
        </div>

        {nlqResult && (
          <div className="mt-3 rounded-xl bg-surface border border-accent-violet/30 p-3.5 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground">{nlqResult.answer}</span>
              <button
                onClick={() => setNlqResult(null)}
                className="text-[11px] text-muted hover:text-foreground"
              >
                Dismiss
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted">
              <span>
                <strong>Date Range:</strong> {nlqResult.date_range}
              </span>
              <span>•</span>
              <span>
                <strong>Definition:</strong> {nlqResult.metric_definition}
              </span>
              {nlqResult.link && (
                <Link href={nlqResult.link} className="text-accent-violet hover:underline">
                  View Source Records →
                </Link>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Configurable Metric Cards Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {visibleWidgets.includes("habits") && (
          <div
            onClick={() => router.push("/habits")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Today&apos;s Habits</span>
              <CheckCircle2 className="h-4 w-4 text-accent-lime" />
            </div>
            <div className="text-2xl font-semibold">
              {m.habits_today.completion_rate_percent !== null
                ? `${m.habits_today.completion_rate_percent}%`
                : "No Schedule"}
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.habits_today.completed} of {m.habits_today.scheduled} scheduled today
            </p>
            {renderComparisonBadge(cmp.today_vs_yesterday_habits)}
          </div>
        )}

        {visibleWidgets.includes("streaks") && (
          <div
            onClick={() => router.push("/habits")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Current Habit Streaks</span>
              <Flame className="h-4 w-4 text-accent-amber" />
            </div>
            <div className="text-2xl font-semibold">
              {m.habit_streaks.best_active_streak} days
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.habit_streaks.active_streaks_count} of {m.habit_streaks.total_active_habits}{" "}
              habits on active streak
            </p>
          </div>
        )}

        {visibleWidgets.includes("expenses") && (
          <div
            onClick={() => router.push("/finance")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Monthly Expenses</span>
              <Wallet className="h-4 w-4 text-accent-danger" />
            </div>
            <div className="text-2xl font-semibold">
              {formatCurrency(m.monthly_expenses.amount, currency)}
            </div>
            {renderComparisonBadge(cmp.month_vs_last_month_expenses, true)}
          </div>
        )}

        {visibleWidgets.includes("income") && (
          <div
            onClick={() => router.push("/finance")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Monthly Income</span>
              <Wallet className="h-4 w-4 text-accent-lime" />
            </div>
            <div className="text-2xl font-semibold">
              {formatCurrency(m.monthly_income.amount, currency)}
            </div>
            <p className="text-xs text-muted mt-0.5">
              Net Savings: {formatCurrency(m.monthly_income.net_savings, currency)}
            </p>
            {renderComparisonBadge(cmp.month_vs_last_month_income)}
          </div>
        )}

        {visibleWidgets.includes("budget") && (
          <div
            onClick={() => router.push("/finance")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Budget Utilization</span>
              <Activity className="h-4 w-4 text-accent-blue" />
            </div>
            <div className="text-2xl font-semibold">
              {m.budget_utilization.has_configured_budget
                ? `${m.budget_utilization.utilization_percent}%`
                : "Unconfigured"}
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.budget_utilization.has_configured_budget
                ? `${formatCurrency(m.budget_utilization.spent_amount, currency)} / ${formatCurrency(
                    m.budget_utilization.limit_amount,
                    currency
                  )}`
                : "Click to set a monthly budget in Finance"}
            </p>
          </div>
        )}

        {visibleWidgets.includes("screen_time") && (
          <div
            onClick={() => router.push("/screen-time")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Today&apos;s Screen Time</span>
              <MonitorSmartphone className="h-4 w-4 text-accent-amber" />
            </div>
            <div className="text-2xl font-semibold">
              {m.screen_time_today.has_recorded_today
                ? formatMinutes(m.screen_time_today.minutes)
                : "Not Logged"}
            </div>
            <p className="text-xs text-muted mt-0.5">
              Daily target: {formatMinutes(m.screen_time_today.target_minutes)} (
              {m.screen_time_today.utilization_percent}%)
            </p>
            {renderComparisonBadge(cmp.today_vs_yesterday_screen_time, true)}
          </div>
        )}

        {visibleWidgets.includes("focus_time") && (
          <div
            onClick={() => router.push("/activities")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Today&apos;s Focus Time</span>
              <Clock className="h-4 w-4 text-accent-violet" />
            </div>
            <div className="text-2xl font-semibold">
              {formatMinutes(m.focus_time_today.minutes)}
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.focus_time_today.sessions_count} focus session(s) today
            </p>
            {renderComparisonBadge(cmp.today_vs_yesterday_focus)}
          </div>
        )}

        {visibleWidgets.includes("activity_time") && (
          <div
            onClick={() => router.push("/activities")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Recorded Activity Time</span>
              <Clock className="h-4 w-4 text-accent-blue" />
            </div>
            <div className="text-2xl font-semibold">
              {formatMinutes(m.activity_time_today.unique_clock_minutes)}
            </div>
            <p className="text-xs text-muted mt-0.5">
              Unique clock time ({m.activity_time_today.sessions_count} sessions)
            </p>
            {renderComparisonBadge(cmp.week_vs_last_week_focus)}
          </div>
        )}

        {visibleWidgets.includes("sleep") && (
          <div
            onClick={() => router.push("/health")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Sleep Duration</span>
              <Moon className="h-4 w-4 text-accent-blue" />
            </div>
            <div className="text-2xl font-semibold">
              {m.sleep.today_hours !== null
                ? `${m.sleep.today_hours}h`
                : m.sleep.latest_hours !== null
                ? `${m.sleep.latest_hours}h`
                : "No Data"}
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.sleep.status === "recorded_today"
                ? `Sleep quality: ${m.sleep.today_quality ?? "—"}/10`
                : m.sleep.status === "historical"
                ? `Latest logged on ${m.sleep.latest_date}`
                : "Log sleep in Health & Energy"}
            </p>
          </div>
        )}

        {visibleWidgets.includes("mood_energy") && (
          <div
            onClick={() => router.push("/health")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Mood & Energy</span>
              <HeartPulse className="h-4 w-4 text-accent-lime" />
            </div>
            <div className="text-2xl font-semibold">
              {m.mood_energy.today_mood !== null || m.mood_energy.today_energy !== null
                ? `${m.mood_energy.today_mood ?? "—"}/10 · ${
                    m.mood_energy.today_energy ?? "—"
                  }/10`
                : m.mood_energy.latest_mood !== null
                ? `${m.mood_energy.latest_mood}/10 · ${m.mood_energy.latest_energy ?? "—"}/10`
                : "No Data"}
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.mood_energy.status === "recorded_today"
                ? "Mood / Energy logged today"
                : m.mood_energy.status === "historical"
                ? `From ${m.mood_energy.latest_date}`
                : "Click to log today's check-in"}
            </p>
          </div>
        )}

        {visibleWidgets.includes("goals") && (
          <div
            onClick={() => router.push("/goals")}
            className="cursor-pointer rounded-xl bg-card border border-border hover:border-accent-violet/40 p-4 transition"
          >
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Active Goals</span>
              <Target className="h-4 w-4 text-accent-lime" />
            </div>
            <div className="text-2xl font-semibold">
              {m.goals.active_count} active
            </div>
            <p className="text-xs text-muted mt-0.5">
              {m.goals.average_progress_percent !== null
                ? `Avg progress: ${m.goals.average_progress_percent}% (${m.goals.completed_count} completed)`
                : "Click to create your first goal"}
            </p>
          </div>
        )}
      </section>

      {/* Interactive Visualizations Row */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 14-Day Focus, Activity & Screen-Time Trend */}
        <div className="lg:col-span-2 rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold">
                14-Day Focus, Activity & Screen-Time Trajectory
              </h2>
              <p className="text-xs text-muted">
                Daily minutes derived from canonical activity and screen-time records
              </p>
            </div>
            <Link
              href="/activities"
              className="text-xs text-accent-violet hover:underline flex items-center gap-1"
            >
              <span>Inspect Time</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.charts?.activity_trend_14d || []}>
                <defs>
                  <linearGradient id="gradFocus" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradScreen" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
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
                <Area
                  type="monotone"
                  dataKey="focus_minutes"
                  name="Focus (mins)"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  fill="url(#gradFocus)"
                />
                <Area
                  type="monotone"
                  dataKey="screen_time_minutes"
                  name="Screen Time (mins)"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fill="url(#gradScreen)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Expense Breakdown Pie / Empty State */}
        <div className="rounded-2xl bg-card border border-border p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold">Monthly Spending Breakdown</h2>
              <p className="text-xs text-muted">
                Exact Decimal category share ({currency})
              </p>
            </div>
            <Link
              href="/finance"
              className="text-xs text-accent-violet hover:underline"
            >
              Details →
            </Link>
          </div>

          {data.charts?.expense_categories?.length > 0 ? (
            <>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.charts.expense_categories}
                      dataKey="amount_numeric"
                      nameKey="category"
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={3}
                      onClick={(entry) =>
                        router.push(`/finance?category=${encodeURIComponent(entry.category)}`)
                      }
                    >
                      {data.charts.expense_categories.map((_: any, idx: number) => (
                        <Cell
                          key={idx}
                          fill={PIE_COLORS[idx % PIE_COLORS.length]}
                          className="cursor-pointer"
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#141821",
                        borderColor: "#242b3a",
                        borderRadius: "10px",
                        fontSize: "12px",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-1.5 mt-2">
                {data.charts.expense_categories.slice(0, 4).map((c: any, idx: number) => (
                  <div
                    key={c.category}
                    onClick={() =>
                      router.push(`/finance?category=${encodeURIComponent(c.category)}`)
                    }
                    className="flex items-center justify-between text-xs cursor-pointer hover:bg-surface px-2 py-1 rounded"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }}
                      />
                      <span>{c.category}</span>
                    </div>
                    <span className="font-mono text-muted">
                      {formatCurrency(c.amount, currency)} ({c.percentage}%)
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center py-8">
              <Wallet className="h-8 w-8 text-muted mb-2 opacity-60" />
              <p className="text-xs font-medium">No expenses recorded this month</p>
              <p className="text-[11px] text-muted mt-1 max-w-xs">
                Record an expense or import a CSV statement to see your category breakdown.
              </p>
              <button
                onClick={() => openQuickAdd("expense")}
                className="mt-3 rounded-lg bg-accent-violet/15 border border-accent-violet/40 text-accent-violet px-3 py-1.5 text-xs font-medium"
              >
                + Record Expense
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Bottom Row: Today's Habits Quick-Completion, Active Goals, and Recent Timeline Feed */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Today's Habits Checkoff */}
        <div className="rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold">Habit Check-Off</h2>
              <p className="text-xs text-muted">One-tap completion updates canonical streaks</p>
            </div>
            <Link href="/habits" className="text-xs text-accent-violet hover:underline">
              All Habits →
            </Link>
          </div>

          {data.charts?.habits?.length > 0 ? (
            <div className="space-y-2">
              {data.charts.habits.slice(0, 6).map((h: any) => (
                <div
                  key={h.id}
                  className="flex items-center justify-between rounded-xl bg-surface border border-border px-3.5 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{h.name}</p>
                    <p className="text-[11px] text-muted">
                      {h.category} · Streak: {h.current_streak}d ({h.completion_rate_30d}%)
                    </p>
                  </div>
                  <button
                    onClick={() => handleQuickToggleHabit(h)}
                    className={cn(
                      "px-3 py-1 rounded-lg text-xs font-medium border transition shrink-0",
                      h.completed_today
                        ? "bg-accent-lime/20 border-accent-lime/50 text-accent-lime"
                        : "bg-card border-border text-muted hover:text-foreground"
                    )}
                  >
                    {h.completed_today ? "Done ✓" : "Complete"}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <CheckCircle2 className="h-8 w-8 text-muted mx-auto mb-2 opacity-60" />
              <p className="text-xs font-medium">No active habits configured</p>
              <button
                onClick={() => openQuickAdd("habit")}
                className="mt-3 rounded-lg bg-accent-violet/15 border border-accent-violet/40 text-accent-violet px-3 py-1.5 text-xs font-medium"
              >
                + Create First Habit
              </button>
            </div>
          )}
        </div>

        {/* Active Goals Progress */}
        <div className="rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold">Goals & Milestones</h2>
              <p className="text-xs text-muted">Progress derived from recorded entries</p>
            </div>
            <Link href="/goals" className="text-xs text-accent-violet hover:underline">
              Manage Goals →
            </Link>
          </div>

          {m.goals?.items?.length > 0 ? (
            <div className="space-y-3.5">
              {m.goals.items.map((g: any) => (
                <div
                  key={g.id}
                  onClick={() => router.push(`/goals?highlight=${g.id}`)}
                  className="cursor-pointer rounded-xl bg-surface border border-border p-3 hover:border-accent-violet/40 transition"
                >
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium truncate">{g.name}</span>
                    <span className="font-mono text-accent-lime">{g.progress_percent}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-card overflow-hidden">
                    <div
                      className="h-full bg-accent-violet rounded-full transition-all"
                      style={{ width: `${Math.min(100, g.progress_percent)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-muted mt-1.5">
                    <span>
                      {g.current_value} / {g.target_value} {g.unit}
                    </span>
                    <span className="capitalize">{g.pace_status.replace("_", " ")}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Target className="h-8 w-8 text-muted mx-auto mb-2 opacity-60" />
              <p className="text-xs font-medium">No active goals yet</p>
              <Link
                href="/goals"
                className="inline-block mt-3 rounded-lg bg-accent-violet/15 border border-accent-violet/40 text-accent-violet px-3 py-1.5 text-xs font-medium"
              >
                + Define a Goal
              </Link>
            </div>
          )}
        </div>

        {/* Recent Activity Feed */}
        <div className="rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold">Recent Activity Stream</h2>
              <p className="text-xs text-muted">Live chronological events with record links</p>
            </div>
            <Link href="/timeline" className="text-xs text-accent-violet hover:underline">
              Full Timeline →
            </Link>
          </div>

          {data.recent_activity?.length > 0 ? (
            <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
              {data.recent_activity.map((ev: any) => (
                <Link
                  key={ev.id}
                  href={ev.link || "/timeline"}
                  className="block rounded-xl bg-surface border border-border hover:border-accent-violet/40 p-2.5 text-xs transition"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-foreground truncate">{ev.title}</span>
                    <span className="text-[10px] text-muted shrink-0">{ev.event_date}</span>
                  </div>
                  <p className="text-[11px] text-muted truncate mt-0.5">{ev.subtitle}</p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Activity className="h-8 w-8 text-muted mx-auto mb-2 opacity-60" />
              <p className="text-xs font-medium">Your timeline is currently empty</p>
              <p className="text-[11px] text-muted mt-1">
                Every habit, transaction, focus session, and journal entry you record will appear here.
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

