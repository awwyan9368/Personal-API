"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Clock,
  MonitorSmartphone,
  Moon,
  Plus,
  Settings2,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApp } from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { cn, formatMinutes, todayIso } from "@/lib/utils";

export default function ScreenTimePage() {
  const { notify, dataVersion, triggerRefresh } = useApp();

  const [summary, setSummary] = useState<any | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [mappings, setMappings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 13);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(todayIso());

  // Log session form
  const [appName, setAppName] = useState("");
  const [device, setDevice] = useState("desktop");
  const [sessionDate, setSessionDate] = useState(todayIso());
  const [durationMinutes, setDurationMinutes] = useState("45");
  const [notes, setNotes] = useState("");

  // App category mapping form
  const [mapApp, setMapApp] = useState("");
  const [mapCat, setMapCat] = useState("work");
  const [mapProd, setMapProd] = useState("productive");

  const loadScreenTime = useCallback(async () => {
    try {
      setLoading(true);
      const [sumRes, sessRes, mapRes] = await Promise.all([
        apiFetch(`/screen-time/summary?start_date=${startDate}&end_date=${endDate}`),
        apiFetch<any[]>(`/screen-time?start_date=${startDate}&end_date=${endDate}`),
        apiFetch<any[]>("/screen-time/mappings"),
      ]);
      setSummary(sumRes);
      setSessions(sessRes);
      setMappings(mapRes);
    } catch (err: any) {
      notify("Failed to load screen-time analytics", err.message, "error");
    } finally {
      setLoading(false);
    }
  }, [endDate, notify, startDate]);

  useEffect(() => {
    loadScreenTime();
  }, [loadScreenTime, dataVersion]);

  const handleLogSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/screen-time", {
        method: "POST",
        body: JSON.stringify({
          app_name: appName,
          device,
          session_date: sessionDate,
          duration_minutes: parseInt(durationMinutes, 10),
          notes: notes || null,
          data_source: "manual",
        }),
      });
      notify("Screen-time session logged", `${appName} (${durationMinutes}m)`, "success");
      setAppName("");
      setNotes("");
      triggerRefresh();
    } catch (err: any) {
      notify("Failed to log session", err.message, "error");
    }
  };

  const handleSaveMapping = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/screen-time/mappings", {
        method: "POST",
        body: JSON.stringify({
          app_name: mapApp,
          category: mapCat,
          productivity_type: mapProd,
        }),
      });
      notify("App classification saved", `${mapApp} → ${mapCat} (${mapProd})`, "success");
      setMapApp("");
      triggerRefresh();
    } catch (err: any) {
      notify("Failed to save mapping", err.message, "error");
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await apiFetch(`/screen-time/${id}`, { method: "DELETE" });
      triggerRefresh();
    } catch (err: any) {
      notify("Delete failed", err.message, "error");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Screen-Time Analytics</h1>
          <p className="text-xs text-muted mt-0.5">
            App rankings, work vs entertainment breakdown, late-night analysis, and configurable app classifications
          </p>
        </div>
        <div className="flex items-center gap-2">
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
        </div>
      </div>

      {/* Honest Data Collector Status Banner */}
      {summary?.automatic_collector_status && (
        <div className="rounded-xl bg-card border border-border p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "h-2.5 w-2.5 rounded-full shrink-0",
                summary.automatic_collector_status.is_active
                  ? "bg-accent-lime"
                  : "bg-accent-amber"
              )}
            />
            <div>
              <p className="font-semibold text-foreground">
                {summary.automatic_collector_status.label}
              </p>
              <p className="text-muted mt-0.5">
                {summary.automatic_collector_status.explanation}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Top Metric Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl bg-card border border-border p-4">
            <span className="text-xs text-muted block">Total Screen Time</span>
            <span className="text-2xl font-semibold block mt-1">
              {formatMinutes(summary.total_minutes)}
            </span>
            <span className="text-[11px] text-muted block mt-1">
              Across {summary.recorded_days_count} recorded day(s)
            </span>
          </div>

          <div className="rounded-xl bg-card border border-border p-4">
            <span className="text-xs text-muted block">Daily Average (Recorded Days)</span>
            <span className="text-2xl font-semibold block mt-1">
              {formatMinutes(summary.average_daily_minutes_recorded_days)}
            </span>
            <span className="text-[11px] text-muted block mt-1">
              Target: {formatMinutes(summary.daily_target_minutes)} / day
            </span>
          </div>

          <div className="rounded-xl bg-card border border-border p-4">
            <span className="text-xs text-muted block">Work vs Entertainment</span>
            <span className="text-2xl font-semibold text-accent-lime block mt-1">
              {summary.work_vs_entertainment.productive_percentage}% Productive
            </span>
            <span className="text-[11px] text-muted block mt-1">
              {formatMinutes(summary.work_vs_entertainment.productive_minutes)} work ·{" "}
              {formatMinutes(summary.work_vs_entertainment.non_productive_minutes)} leisure
            </span>
          </div>

          <div className="rounded-xl bg-card border border-border p-4">
            <span className="text-xs text-muted block">Late-Night Usage (22:00–05:00)</span>
            <span className="text-2xl font-semibold text-accent-amber block mt-1">
              {formatMinutes(summary.late_night_usage.total_minutes)}
            </span>
            <span className="text-[11px] text-muted block mt-1">
              {summary.late_night_usage.sessions_count} late-night session(s)
            </span>
          </div>
        </div>
      )}

      {/* Charts & Logger Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <form
          onSubmit={handleLogSession}
          className="rounded-2xl bg-card border border-border p-5 space-y-4 text-xs h-fit"
        >
          <h2 className="text-sm font-semibold">Log Screen-Time Session</h2>
          <div>
            <label className="block text-muted mb-1">Application or Website</label>
            <input
              type="text"
              required
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="e.g. VS Code, YouTube, GitHub, Instagram"
              className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-muted mb-1">Device</label>
              <select
                value={device}
                onChange={(e) => setDevice(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              >
                <option value="desktop">Desktop / Laptop</option>
                <option value="phone">Phone</option>
                <option value="tablet">Tablet</option>
                <option value="web">Web Browser</option>
              </select>
            </div>
            <div>
              <label className="block text-muted mb-1">Duration (Mins)</label>
              <input
                type="number"
                min="1"
                max="1440"
                required
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-muted mb-1">Date</label>
            <input
              type="date"
              required
              value={sessionDate}
              onChange={(e) => setSessionDate(e.target.value)}
              className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-muted mb-1">Notes</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-xl bg-accent-violet text-white py-2 font-medium"
          >
            Save Session
          </button>
        </form>

        <div className="lg:col-span-2 rounded-2xl bg-card border border-border p-5">
          <h2 className="text-sm font-semibold mb-1">Daily Screen-Time vs Target</h2>
          <p className="text-xs text-muted mb-4">
            Daily recorded minutes compared against your {summary?.daily_target_minutes}m target
          </p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary?.daily_series || []}>
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
                <Bar
                  dataKey="duration_minutes"
                  name="Screen Time (mins)"
                  fill="#3b82f6"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* App Rankings & Configurable App-Category Mapping */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-card border border-border p-5">
          <h2 className="text-sm font-semibold mb-3">Application Rankings</h2>
          {summary?.app_rankings?.length > 0 ? (
            <div className="space-y-2.5">
              {summary.app_rankings.map((app: any) => (
                <div key={app.app_name} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium">{app.app_name}</span>
                    <span className="font-mono text-muted">
                      {formatMinutes(app.duration_minutes)} ({app.percentage}%)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface overflow-hidden">
                    <div
                      className="h-full bg-accent-blue rounded-full"
                      style={{ width: `${Math.min(100, app.percentage)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted py-8 text-center">
              No screen-time sessions recorded in this date range.
            </p>
          )}
        </div>

        <div className="rounded-2xl bg-card border border-border p-5 space-y-4">
          <h2 className="text-sm font-semibold">
            Configurable Application-Category Mapping
          </h2>
          <form onSubmit={handleSaveMapping} className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
            <input
              type="text"
              required
              value={mapApp}
              onChange={(e) => setMapApp(e.target.value)}
              placeholder="App name (e.g. Figma)"
              className="rounded-lg bg-surface border border-border px-3 py-1.5"
            />
            <select
              value={mapCat}
              onChange={(e) => setMapCat(e.target.value)}
              className="rounded-lg bg-surface border border-border px-2 py-1.5"
            >
              <option value="work">Work</option>
              <option value="learning">Learning</option>
              <option value="communication">Communication</option>
              <option value="entertainment">Entertainment</option>
              <option value="social_media">Social Media</option>
              <option value="gaming">Gaming</option>
              <option value="other">Other</option>
            </select>
            <div className="flex gap-1.5">
              <select
                value={mapProd}
                onChange={(e) => setMapProd(e.target.value)}
                className="flex-1 rounded-lg bg-surface border border-border px-2 py-1.5"
              >
                <option value="productive">Productive</option>
                <option value="neutral">Neutral</option>
                <option value="non_productive">Non-Productive</option>
              </select>
              <button
                type="submit"
                className="rounded-lg bg-accent-violet text-white px-3 py-1.5 font-medium"
              >
                Save
              </button>
            </div>
          </form>

          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {mappings.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between rounded-lg bg-surface border border-border px-3 py-1.5 text-xs"
              >
                <span className="font-medium">{m.app_name}</span>
                <span className="text-muted">
                  {m.category} · {m.productivity_type}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recorded Sessions Table */}
      <div className="rounded-2xl bg-card border border-border overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-surface text-muted">
              <th className="p-3 text-left">Date</th>
              <th className="p-3 text-left">App / Website</th>
              <th className="p-3 text-left">Device</th>
              <th className="p-3 text-left">Category</th>
              <th className="p-3 text-left">Classification</th>
              <th className="p-3 text-left">Source</th>
              <th className="p-3 text-right">Duration</th>
              <th className="p-3 text-right">Delete</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id} className="border-b border-border/50">
                <td className="p-3 font-mono">{s.session_date}</td>
                <td className="p-3 font-medium">{s.app_name}</td>
                <td className="p-3 capitalize text-muted">{s.device}</td>
                <td className="p-3 capitalize">{s.category}</td>
                <td className="p-3 capitalize text-muted">{s.productivity_type}</td>
                <td className="p-3 font-mono text-[11px] text-muted">{s.data_source}</td>
                <td className="p-3 text-right font-mono font-semibold">
                  {formatMinutes(s.duration_minutes)}
                </td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => handleDeleteSession(s.id)}
                    className="p-1 text-muted hover:text-accent-danger"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

