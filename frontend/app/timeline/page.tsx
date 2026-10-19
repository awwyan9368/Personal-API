"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Clock,
  Search,
  ExternalLink,
  Calendar,
  Filter,
} from "lucide-react";

const EVENT_TYPES = [
  { key: "habit", label: "Habits" },
  { key: "transaction", label: "Finance" },
  { key: "focus", label: "Focus" },
  { key: "activity", label: "Activities" },
  { key: "screen_time", label: "Screen Time" },
  { key: "goal", label: "Goals" },
  { key: "milestone", label: "Milestones" },
  { key: "journal", label: "Journal" },
  { key: "wellbeing", label: "Wellbeing" },
];

export default function PersonalTimelinePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  async function loadTimeline() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedTypes.length > 0) params.set("event_types", selectedTypes.join(","));
      if (search.trim()) params.set("search", search.trim());
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      params.set("limit", "200");
      const res = await apiFetch(`/timeline?${params.toString()}`);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTimeline();
  }, [selectedTypes, search, startDate, endDate]);

  function toggleType(t: string) {
    setSelectedTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  }

  const grouped = data?.grouped_by_date || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Personal Timeline</h1>
          <p className="text-sm text-muted-foreground">
            Unified chronological stream constructed directly from canonical database records without duplication
          </p>
        </div>
        <div className="text-xs text-muted-foreground">
          Showing <strong>{data?.events?.length || 0}</strong> of{" "}
          <strong>{data?.total || 0}</strong> matching events
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div className="relative sm:col-span-2">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search across all timeline events, notes, categories..."
              className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-xs"
            />
          </div>
          <div>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
              title="Start Date"
            />
          </div>
          <div>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
              title="End Date"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="mr-1 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Filter className="h-3 w-3" />
            Domains:
          </span>
          {EVENT_TYPES.map((et) => {
            const active = selectedTypes.includes(et.key);
            return (
              <button
                key={et.key}
                onClick={() => toggleType(et.key)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                }`}
              >
                {et.label}
              </button>
            );
          })}
          {selectedTypes.length > 0 && (
            <button
              onClick={() => setSelectedTypes([])}
              className="ml-2 text-[11px] text-primary hover:underline"
            >
              Reset filters
            </button>
          )}
        </div>
      </div>

      {/* Chronological Feed */}
      {loading ? (
        <div className="py-16 text-center text-xs text-muted-foreground">
          Assembling chronological timeline...
        </div>
      ) : grouped.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card py-16 text-center">
          <Clock className="mx-auto h-8 w-8 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">No timeline events match your filters</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Log habits, transactions, focus sessions, journal reflections, or wellbeing check-ins to populate your timeline.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map((group: any) => (
            <div key={group.date} className="rounded-xl border border-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between border-b border-border/60 pb-2.5">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-bold">{formatDate(group.date)}</h2>
                </div>
                <span className="rounded-full bg-secondary px-2.5 py-0.5 text-[11px] text-muted-foreground">
                  {group.events.length} event(s)
                </span>
              </div>

              <div className="relative ml-3 space-y-4 border-l-2 border-border/70 pl-5">
                {group.events.map((ev: any) => (
                  <div key={ev.id} className="relative flex items-start justify-between gap-4">
                    <span
                      className="absolute -left-[27px] top-1.5 h-3 w-3 rounded-full ring-4 ring-card"
                      style={{ backgroundColor: ev.color || "#8b5cf6" }}
                    />
                    <div className="space-y-0.5 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          {ev.event_type.replace("_", " ")}
                        </span>
                        <span className="font-semibold text-foreground">{ev.title}</span>
                      </div>
                      {ev.subtitle && (
                        <div className="text-muted-foreground">{ev.subtitle}</div>
                      )}
                      {ev.notes && (
                        <div className="mt-1 rounded bg-secondary/30 px-2.5 py-1 text-[11px] text-muted-foreground">
                          {ev.notes}
                        </div>
                      )}
                    </div>
                    {ev.link && (
                      <Link
                        href={ev.link}
                        className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-secondary hover:text-foreground"
                      >
                        <span>View</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

