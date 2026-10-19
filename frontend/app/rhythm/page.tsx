"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import {
  Activity,
  Clock,
  Info,
  Sparkles,
  ExternalLink,
  X,
} from "lucide-react";

const ACTIVITY_TYPES = [
  { key: "focus", label: "Focus Sessions" },
  { key: "activity", label: "Activities" },
  { key: "screen_time", label: "Screen Time" },
  { key: "habit", label: "Habits" },
  { key: "exercise", label: "Exercise" },
  { key: "journal", label: "Journal" },
];

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function PersonalRhythmPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [selectedCell, setSelectedCell] = useState<any | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  async function loadRhythm() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedTypes.length > 0) params.set("activity_types", selectedTypes.join(","));
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      params.set("compare_previous", "true");
      const res = await apiFetch(`/rhythm?${params.toString()}`);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRhythm();
  }, [selectedTypes, startDate, endDate]);

  function toggleType(t: string) {
    setSelectedTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  }

  const cells = data?.heatmap_cells || [];
  const maxCellMins = Math.max(1, ...cells.map((c: any) => c.total_minutes || 0));

  function getCell(wd: number, hr: number) {
    return cells.find((c: any) => c.weekday === wd && c.hour === hr);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Personal Rhythm</h1>
          <p className="text-sm text-muted-foreground">
            7×24 Weekday-vs-Hour activity heatmap, time-of-day blocks, and period comparison
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5"
          />
          <span className="text-muted-foreground">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5"
          />
        </div>
      </div>

      {/* Data Integrity Note */}
      <div className="flex items-start gap-2.5 rounded-xl border border-primary/25 bg-primary/5 p-3.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div>
          <strong className="text-foreground">Recorded vs Unrecorded Transparency:</strong>{" "}
          {data?.data_interpretation_note ||
            "Blank cells indicate zero recorded events during that weekday/hour slot, not necessarily inactivity."}{" "}
          ({data?.recorded_days || 0} recorded day(s), {data?.unrecorded_days || 0} unrecorded day(s) in current {data?.period_days || 30}-day window).
        </div>
      </div>

      {/* Filter Pills */}
      <div className="flex flex-wrap items-center gap-2">
        {ACTIVITY_TYPES.map((t) => {
          const active = selectedTypes.includes(t.key);
          return (
            <button
              key={t.key}
              onClick={() => toggleType(t.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                active
                  ? "bg-primary text-primary-foreground"
                  : "bg-card border border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          );
        })}
        {selectedTypes.length > 0 && (
          <button
            onClick={() => setSelectedTypes([])}
            className="text-xs text-primary hover:underline"
          >
            Show All
          </button>
        )}
      </div>

      {/* 7x24 Weekday-vs-Hour Interactive Heatmap */}
      <div className="rounded-xl border border-border bg-card p-5 overflow-x-auto">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Weekday × Hour-of-Day Heatmap ({data?.timezone || "Local Time"})</h3>
            <p className="text-xs text-muted-foreground">
              Click any cell to inspect the underlying timestamped records
            </p>
          </div>
          {data?.peak_focus_observation && (
            <div className="inline-flex items-center gap-1.5 rounded-lg bg-primary/15 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Peak Focus: {data.peak_focus_observation.window} ({data.peak_focus_observation.focus_minutes}m)
            </div>
          )}
        </div>

        {loading ? (
          <div className="py-16 text-center text-xs text-muted-foreground">
            Computing 7×24 rhythm matrix...
          </div>
        ) : (
          <div className="min-w-[760px]">
            {/* Hour Header */}
            <div className="grid grid-cols-[100px_repeat(24,minmax(0,1fr))] gap-1 text-[10px] text-muted-foreground mb-1">
              <div />
              {Array.from({ length: 24 }, (_, hr) => (
                <div key={hr} className="text-center font-mono">
                  {String(hr).padStart(2, "0")}
                </div>
              ))}
            </div>

            {/* 7 Weekday Rows */}
            <div className="space-y-1">
              {WEEKDAYS.map((dayName, wd) => (
                <div
                  key={dayName}
                  className="grid grid-cols-[100px_repeat(24,minmax(0,1fr))] gap-1 items-center"
                >
                  <div className="text-xs font-medium text-muted-foreground pr-2 truncate">
                    {dayName}
                  </div>
                  {Array.from({ length: 24 }, (_, hr) => {
                    const cell = getCell(wd, hr);
                    const mins = cell?.total_minutes || 0;
                    const ratio = mins > 0 ? Math.max(0.2, Math.min(1, mins / maxCellMins)) : 0;
                    return (
                      <button
                        key={hr}
                        onClick={() => cell && setSelectedCell(cell)}
                        title={`${dayName} ${String(hr).padStart(2, "0")}:00 — ${mins}m (${
                          cell?.events_count || 0
                        } events)`}
                        className="h-7 rounded transition border border-border/40 hover:ring-2 hover:ring-primary"
                        style={{
                          backgroundColor:
                            mins > 0
                              ? `rgba(139, 92, 246, ${ratio})`
                              : "rgba(255, 255, 255, 0.02)",
                        }}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Time-of-Day Blocks & Weekday vs Weekend & Period Comparison */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold">Time-of-Day Windows</h3>
          <p className="text-xs text-muted-foreground">Morning, Afternoon, Evening & Night</p>
          <div className="mt-4 space-y-3">
            {(data?.time_of_day_comparison || []).map((w: any) => (
              <div
                key={w.window}
                className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/20 p-3 text-xs"
              >
                <div>
                  <div className="font-semibold">{w.window}</div>
                  <div className="text-[11px] text-muted-foreground">
                    Focus: {formatDuration(w.focus_minutes)} · Screen: {formatDuration(w.screen_time_minutes)}
                  </div>
                </div>
                <div className="text-right font-mono font-bold text-primary">
                  {formatDuration(w.minutes)}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold">Weekday vs Weekend Rhythm</h3>
          <p className="text-xs text-muted-foreground">Comparative intensity across the week</p>
          <div className="mt-4 space-y-3 text-xs">
            <div className="rounded-lg border border-border/60 bg-secondary/20 p-3.5">
              <div className="text-muted-foreground">Mon–Fri Total Logged</div>
              <div className="mt-1 text-xl font-bold">
                {formatDuration(data?.weekday_vs_weekend?.weekday_total_minutes || 0)}
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                Focus: {formatDuration(data?.weekday_vs_weekend?.weekday_focus_minutes || 0)}
              </div>
            </div>
            <div className="rounded-lg border border-border/60 bg-secondary/20 p-3.5">
              <div className="text-muted-foreground">Sat–Sun Total Logged</div>
              <div className="mt-1 text-xl font-bold">
                {formatDuration(data?.weekday_vs_weekend?.weekend_total_minutes || 0)}
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                Focus: {formatDuration(data?.weekday_vs_weekend?.weekend_focus_minutes || 0)}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold">Two-Period Rhythm Comparison</h3>
          <p className="text-xs text-muted-foreground">Current window vs preceding period</p>
          {data?.period_comparison ? (
            <div className="mt-4 space-y-3 text-xs">
              <div className="rounded-lg border border-border/60 bg-secondary/20 p-3.5">
                <div className="text-muted-foreground">
                  Previous ({data.period_comparison.previous_start_date} to{" "}
                  {data.period_comparison.previous_end_date})
                </div>
                <div className="mt-1 text-lg font-bold">
                  {formatDuration(data.period_comparison.previous_total_minutes)} (
                  {data.period_comparison.previous_total_events} events)
                </div>
              </div>
              <div className="rounded-lg border border-border/60 bg-secondary/20 p-3.5">
                <div className="text-muted-foreground">Net Rhythm Volume Delta</div>
                <div className="mt-1 text-lg font-bold text-primary">
                  {data.period_comparison.minutes_delta >= 0 ? "+" : ""}
                  {data.period_comparison.minutes_delta} mins
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-4 text-xs text-muted-foreground">No comparison data available.</div>
          )}
        </div>
      </div>

      {/* Cell Drill-down Modal */}
      {selectedCell && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-xl border border-border bg-card p-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="text-base font-bold">
                  {selectedCell.weekday_name} · {selectedCell.hour_label}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {selectedCell.total_minutes} total minutes across {selectedCell.events_count} event(s)
                </p>
              </div>
              <button
                onClick={() => setSelectedCell(null)}
                className="rounded p-1 text-muted-foreground hover:bg-secondary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 space-y-2.5 text-xs">
              {(selectedCell.records || []).length === 0 ? (
                <p className="py-6 text-center text-muted-foreground">
                  No timestamped records logged during this weekday/hour slot.
                </p>
              ) : (
                selectedCell.records.map((rec: any, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/30 p-3"
                  >
                    <div>
                      <div className="font-semibold">{rec.title}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {rec.date} at {rec.local_time} · {rec.duration_minutes}m ({rec.type})
                      </div>
                    </div>
                    {rec.link && (
                      <Link
                        href={rec.link}
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        <span>Open</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

