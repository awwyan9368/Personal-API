"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  Sparkles,
  CheckCircle2,
  EyeOff,
  ExternalLink,
  AlertTriangle,
  Info,
  TrendingUp,
  RefreshCw,
} from "lucide-react";

export default function InsightsPage() {
  const [data, setData] = useState<any>(null);
  const [includeDismissed, setIncludeDismissed] = useState(false);
  const [loading, setLoading] = useState(true);

  async function loadInsights() {
    setLoading(true);
    try {
      const res = await apiFetch(`/insights?include_dismissed=${includeDismissed}`);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadInsights();
  }, [includeDismissed]);

  async function handleStatusChange(insightKey: string, status: "dismissed" | "reviewed" | "active") {
    try {
      await apiFetch("/insights/status", {
        method: "POST",
        body: JSON.stringify({ insight_key: insightKey, status }),
      });
      await loadInsights();
    } catch (err: any) {
      alert(err.message || "Failed to update insight status");
    }
  }

  const insights = data?.insights || [];
  const diagnostics = data?.sufficiency_diagnostics || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Local Deterministic Insights Engine</h1>
          <p className="text-sm text-muted-foreground">
            Transparent, statistical pattern discovery across your local SQLite records — zero external AI APIs
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={includeDismissed}
              onChange={(e) => setIncludeDismissed(e.target.checked)}
            />
            <span>Show dismissed</span>
          </label>
          <button
            onClick={loadInsights}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-secondary"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Recompute
          </button>
        </div>
      </div>

      {/* Sufficiency Diagnostics Banner */}
      {diagnostics.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Data Sufficiency Status
          </h3>
          <div className="mt-2.5 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {diagnostics.map((d: any, idx: number) => (
              <div
                key={idx}
                className="flex items-start gap-2 rounded-lg border border-border/60 bg-secondary/20 p-3 text-xs"
              >
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                <div>
                  <div className="font-semibold capitalize">{d.domain}</div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{d.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Insights Grid */}
      {loading ? (
        <div className="py-16 text-center text-xs text-muted-foreground">
          Running local deterministic analytics...
        </div>
      ) : insights.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card py-16 text-center">
          <Sparkles className="mx-auto h-8 w-8 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">No active insights triggered yet</h3>
          <p className="mt-1 max-w-md mx-auto text-xs text-muted-foreground">
            Insights are generated strictly when sufficient supporting records exist in your local database. Log habits, expenses, focus sessions, or wellbeing entries to unlock deterministic observations.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {insights.map((ins: any) => {
            const sevStyles: Record<string, string> = {
              positive: "border-accent/40 bg-accent/10 text-accent",
              warning: "border-amber-500/40 bg-amber-500/10 text-amber-400",
              info: "border-primary/40 bg-primary/10 text-primary",
            };
            const badgeStyle = sevStyles[ins.severity] || sevStyles.info;

            return (
              <div
                key={ins.key}
                className="flex flex-col justify-between rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase ${badgeStyle}`}
                      >
                        {ins.category}
                      </span>
                      <span className="text-[11px] text-muted-foreground">{ins.date_range}</span>
                      {ins.status === "reviewed" && (
                        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
                          Reviewed
                        </span>
                      )}
                      {ins.status === "dismissed" && (
                        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          Dismissed
                        </span>
                      )}
                    </div>
                    {ins.severity === "warning" ? (
                      <AlertTriangle className="h-4 w-4 text-amber-400" />
                    ) : (
                      <TrendingUp className="h-4 w-4 text-primary" />
                    )}
                  </div>

                  <h3 className="mt-3 text-base font-bold">{ins.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                    {ins.explanation}
                  </p>

                  {/* Supporting Metrics */}
                  {ins.supporting_metrics && (
                    <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg border border-border/60 bg-secondary/30 p-3 text-xs sm:grid-cols-3">
                      {Object.entries(ins.supporting_metrics).map(([k, v]) => (
                        <div key={k}>
                          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                            {k.replace(/_/g, " ")}
                          </div>
                          <div className="mt-0.5 font-mono font-semibold">{String(v)}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-border/60 pt-3 text-xs">
                  <Link
                    href={ins.link || "/"}
                    className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                  >
                    <span>Inspect Source Records</span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>

                  <div className="flex items-center gap-2">
                    {ins.status !== "reviewed" && (
                      <button
                        onClick={() => handleStatusChange(ins.key, "reviewed")}
                        className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-[11px] hover:bg-secondary"
                      >
                        <CheckCircle2 className="h-3 w-3 text-accent" />
                        Mark Reviewed
                      </button>
                    )}
                    {ins.status !== "dismissed" ? (
                      <button
                        onClick={() => handleStatusChange(ins.key, "dismissed")}
                        className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-secondary"
                      >
                        <EyeOff className="h-3 w-3" />
                        Dismiss
                      </button>
                    ) : (
                      <button
                        onClick={() => handleStatusChange(ins.key, "active")}
                        className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-[11px] hover:bg-secondary"
                      >
                        Restore
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

