"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDuration } from "@/lib/utils";
import {
  Sparkles,
  Printer,
  Download,
  CheckCircle2,
  Wallet,
  Timer,
  Monitor,
  HeartPulse,
  Award,
  AlertCircle,
} from "lucide-react";

export default function LifeWrappedPage() {
  const [periodType, setPeriodType] = useState<"month" | "year" | "custom">("month");
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function loadWrapped() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("period_type", periodType);
      if (periodType === "month" && month) params.set("month", month);
      if (periodType === "year" && year) params.set("year", String(year));
      if (periodType === "custom" && startDate && endDate) {
        params.set("start_date", startDate);
        params.set("end_date", endDate);
      }
      const res = await apiFetch(`/wrapped?${params.toString()}`);
      setReport(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWrapped();
  }, [periodType, month, year, startDate, endDate]);

  function handleDownloadJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `life_wrapped_${report.start_date}_to_${report.end_date}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const hl = report?.highlights || {};
  const sec = report?.sections || {};
  const currency = report?.currency || "INR";

  return (
    <div className="space-y-6">
      {/* Control Bar (Hidden when printing to PDF) */}
      <div className="no-print flex flex-col justify-between gap-4 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            onClick={() => setPeriodType("month")}
            className={`rounded-lg px-3 py-1.5 font-semibold ${
              periodType === "month"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground"
            }`}
          >
            Monthly Report
          </button>
          <button
            onClick={() => setPeriodType("year")}
            className={`rounded-lg px-3 py-1.5 font-semibold ${
              periodType === "year"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground"
            }`}
          >
            Annual Wrapped
          </button>
          <button
            onClick={() => setPeriodType("custom")}
            className={`rounded-lg px-3 py-1.5 font-semibold ${
              periodType === "custom"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground"
            }`}
          >
            Custom Date Range
          </button>

          {periodType === "month" && (
            <input
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="ml-2 rounded-lg border border-border bg-background px-3 py-1.5"
            />
          )}
          {periodType === "year" && (
            <input
              type="number"
              min={2020}
              max={2035}
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="ml-2 w-24 rounded-lg border border-border bg-background px-3 py-1.5"
            />
          )}
          {periodType === "custom" && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-1.5"
              />
              <span>to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-1.5"
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadJson}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-secondary"
          >
            <Download className="h-3.5 w-3.5" />
            Export JSON
          </button>
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90"
          >
            <Printer className="h-3.5 w-3.5" />
            Print / Save as PDF
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-xs text-muted-foreground">
          Generating editorial Life Wrapped retrospective...
        </div>
      ) : !report ? null : (
        <div className="space-y-6">
          {/* Editorial Hero Card */}
          <div className="relative overflow-hidden rounded-2xl border border-primary/35 bg-gradient-to-br from-primary/20 via-card to-card p-8 shadow-lg">
            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/20 px-3 py-1 text-xs font-semibold text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                  Personal Life OS · Retrospective Edition
                </div>
                <h1 className="mt-3 text-3xl font-extrabold tracking-tight">{report.title}</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {report.start_date} to {report.end_date} · {report.span_days} days ·{" "}
                  {report.timezone}
                </p>
              </div>
              <div className="max-w-md rounded-xl border border-border/70 bg-background/60 p-4 text-xs leading-relaxed text-muted-foreground">
                {report.concluding_summary}
              </div>
            </div>
          </div>

          {/* 6 Highlight Metric Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Habit Consistency</span>
                <CheckCircle2 className="h-4 w-4 text-accent" />
              </div>
              <div className="mt-2 text-2xl font-bold">
                {hl.total_habit_completions || 0} completions
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Best streak: <strong>{hl.best_habit_streak || 0}d</strong>{" "}
                {hl.best_streak_habit ? `(${hl.best_streak_habit})` : ""}
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Financial Flow</span>
                <Wallet className="h-4 w-4 text-primary" />
              </div>
              <div className="mt-2 text-2xl font-bold">
                {formatCurrency(hl.total_expenses || 0, currency)}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Income: {formatCurrency(hl.total_income || 0, currency)} · Net:{" "}
                {formatCurrency(hl.net_savings || 0, currency)}
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Deep Focus & Projects</span>
                <Timer className="h-4 w-4 text-sky-400" />
              </div>
              <div className="mt-2 text-2xl font-bold">
                {formatDuration(hl.total_focus_minutes || 0)}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Total unique activity: {formatDuration(hl.total_activity_minutes || 0)}
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Digital Screen Time</span>
                <Monitor className="h-4 w-4 text-amber-400" />
              </div>
              <div className="mt-2 text-2xl font-bold">
                {formatDuration(hl.total_screen_time_minutes || 0)}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {hl.total_screen_time_hours || 0} hours recorded in period
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Wellbeing & Sleep</span>
                <HeartPulse className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="mt-2 text-2xl font-bold">
                {sec.wellbeing?.average_sleep_hours != null
                  ? `${sec.wellbeing.average_sleep_hours}h avg sleep`
                  : "No sleep logs"}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Mood: {sec.wellbeing?.average_mood_score ?? "—"}/10 · Energy:{" "}
                {sec.wellbeing?.average_energy_score ?? "—"}/10
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Goals & Milestones</span>
                <Award className="h-4 w-4 text-accent" />
              </div>
              <div className="mt-2 text-2xl font-bold">
                {hl.milestones_reached_count || 0} milestones
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {hl.completed_goals_count || 0} goal(s) completed
              </p>
            </div>
          </div>

          {/* Domain Breakdown Grid */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Most Consistent Habits */}
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="text-sm font-bold">Most Consistent Habits</h3>
              <p className="text-[11px] text-muted-foreground">
                {sec.habits?.calculation_note}
              </p>
              <div className="mt-4 space-y-2.5 text-xs">
                {(sec.habits?.most_consistent_habits || []).length === 0 ? (
                  <p className="text-muted-foreground">No habits logged in this period.</p>
                ) : (
                  sec.habits.most_consistent_habits.map((h: any) => (
                    <div
                      key={h.id}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/20 p-3"
                    >
                      <div>
                        <div className="font-semibold">{h.name}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {h.category} · Best streak {h.best_streak}d
                        </div>
                      </div>
                      <div className="text-right font-mono font-bold text-accent">
                        {h.completions_in_period} days ({h.completion_rate_percent}%)
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Largest Spending Categories */}
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="text-sm font-bold">Largest Spending Categories</h3>
              <p className="text-[11px] text-muted-foreground">
                {sec.finance?.calculation_note}
              </p>
              <div className="mt-4 space-y-2.5 text-xs">
                {(sec.finance?.largest_spending_categories || []).length === 0 ? (
                  <p className="text-muted-foreground">No expenses recorded in this period.</p>
                ) : (
                  sec.finance.largest_spending_categories.map((c: any) => (
                    <div
                      key={c.category}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/20 p-3"
                    >
                      <div>
                        <div className="font-semibold">{c.category}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {c.count} transaction(s) · {c.percentage}% of total
                        </div>
                      </div>
                      <div className="font-mono font-bold">
                        {formatCurrency(c.amount, currency)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Top Projects & Focus Allocation */}
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="text-sm font-bold">Focus & Project Time Allocation</h3>
              <p className="text-[11px] text-muted-foreground">
                {sec.focus_and_projects?.calculation_note}
              </p>
              <div className="mt-4 space-y-2.5 text-xs">
                {(sec.focus_and_projects?.project_allocation || []).length === 0 ? (
                  <p className="text-muted-foreground">No project sessions logged in this period.</p>
                ) : (
                  sec.focus_and_projects.project_allocation.map((p: any) => (
                    <div
                      key={p.project}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/20 p-3"
                    >
                      <span className="font-semibold">{p.project}</span>
                      <span className="font-mono font-bold text-primary">
                        {formatDuration(p.minutes)} ({p.hours}h)
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Most Used Applications */}
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="text-sm font-bold">Most Used Applications</h3>
              <p className="text-[11px] text-muted-foreground">
                {sec.screen_time?.calculation_note}
              </p>
              <div className="mt-4 space-y-2.5 text-xs">
                {(sec.screen_time?.most_used_applications || []).length === 0 ? (
                  <p className="text-muted-foreground">No screen-time sessions logged in this period.</p>
                ) : (
                  sec.screen_time.most_used_applications.map((app: any) => (
                    <div
                      key={app.app_name}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/20 p-3"
                    >
                      <span className="font-semibold">{app.app_name}</span>
                      <span className="font-mono font-bold text-amber-400">
                        {formatDuration(app.minutes)} ({app.hours}h)
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Traceable Observations & Missing Data Transparency */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="text-sm font-bold">Key Traceable Observations</h3>
              <ul className="mt-3 space-y-2 text-xs text-muted-foreground">
                {(report.observations || []).length === 0 ? (
                  <li>Log records in this date window to generate traceable observations.</li>
                ) : (
                  report.observations.map((obs: string, idx: number) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                      <span>{obs}</span>
                    </li>
                  ))
                )}
              </ul>
            </div>

            {(report.unavailable_sections || []).length > 0 && (
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center gap-2 text-sm font-bold">
                  <AlertCircle className="h-4 w-4 text-amber-400" />
                  <span>Unrecorded Sections in This Window</span>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Personal Life OS never fabricates metrics when a domain has no records in the selected period:
                </p>
                <ul className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                  {report.unavailable_sections.map((u: string, i: number) => (
                    <li key={i}>• {u}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

