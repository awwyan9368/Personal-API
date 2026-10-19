"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDuration, formatDate } from "@/lib/utils";
import {
  Timer,
  Play,
  Pause,
  Square,
  Plus,
  Trash2,
  AlertTriangle,
  Download,
  Clock,
  FolderKanban,
  Sparkles,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const COLORS = ["#8b5cf6", "#3b82f6", "#84cc16", "#f59e0b", "#06b6d4", "#ec4899"];

export default function ActivitiesPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [activeTimer, setActiveTimer] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Timer launch state
  const [timerName, setTimerName] = useState("Deep Work Session");
  const [timerCategory, setTimerCategory] = useState("Deep Work");
  const [timerProject, setTimerProject] = useState("Personal Life OS");
  const [timerPlannedMin, setTimerPlannedMin] = useState(50);

  // Manual entry modal
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualName, setManualName] = useState("");
  const [manualCategory, setManualCategory] = useState("Deep Work");
  const [manualProject, setManualProject] = useState("");
  const [manualDate, setManualDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [manualStartTime, setManualStartTime] = useState("09:00");
  const [manualDuration, setManualDuration] = useState(60);
  const [manualIsFocus, setManualIsFocus] = useState(true);
  const [manualNotes, setManualNotes] = useState("");

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [listData, sumData, timerRes] = await Promise.all([
        apiFetch("/activities"),
        apiFetch("/activities/summary"),
        apiFetch("/activities/timer/active"),
      ]);
      setSessions(listData || []);
      setSummary(sumData);
      setActiveTimer(timerRes?.active_timer || null);
    } catch (err: any) {
      setError(err.message || "Failed to load activity sessions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleStartTimer(e: React.FormEvent) {
    e.preventDefault();
    try {
      await apiFetch("/activities/timer/start", {
        method: "POST",
        body: JSON.stringify({
          activity_name: timerName.trim() || "Focus Session",
          category: timerCategory,
          project: timerProject.trim() || null,
          planned_duration_minutes: Number(timerPlannedMin),
          is_focus_session: true,
        }),
      });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to start timer");
    }
  }

  async function handleTimerControl(action: "pause" | "resume" | "stop") {
    try {
      await apiFetch(`/activities/timer/${action}`, { method: "POST" });
      await loadAll();
    } catch (err: any) {
      alert(err.message || `Failed to ${action} timer`);
    }
  }

  async function handleCreateManual(e: React.FormEvent) {
    e.preventDefault();
    if (!manualName.trim()) return;
    try {
      const isoStart = new Date(`${manualDate}T${manualStartTime || "09:00"}:00`).toISOString();
      await apiFetch("/activities", {
        method: "POST",
        body: JSON.stringify({
          activity_name: manualName.trim(),
          category: manualCategory,
          project: manualProject.trim() || null,
          session_date: manualDate,
          start_time: isoStart,
          duration_minutes: Number(manualDuration),
          planned_duration_minutes: Number(manualDuration),
          is_focus_session: manualIsFocus,
          notes: manualNotes.trim() || null,
        }),
      });
      setShowManualModal(false);
      setManualName("");
      setManualNotes("");
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to log activity");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this activity session?")) return;
    try {
      await apiFetch(`/activities/${id}`, { method: "DELETE" });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to delete session");
    }
  }

  const categoryAllocation = summary?.category_allocation || [];
  const projectAllocation = summary?.project_allocation || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Time & Activities</h1>
          <p className="text-sm text-muted-foreground">
            Persistent database-backed focus timer, time allocation, and overlap-aware clock accounting
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a
            href="/api/v1/export?format=csv&domain=activities"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-secondary"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </a>
          <button
            onClick={() => setShowManualModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Log Manual Session
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Persistent Focus Timer Studio */}
      <div className="rounded-xl border border-primary/30 bg-card p-5 shadow-sm">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div className="flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <Timer className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold">Persistent Focus Timer</h2>
                <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                  Survives Refresh
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Stored in SQLite so your active timer continues accurately even if you close or reload the browser tab.
              </p>
            </div>
          </div>

          {activeTimer ? (
            <div className="flex flex-wrap items-center gap-4 rounded-xl border border-primary/40 bg-primary/10 px-4 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
                  <span className="text-sm font-bold">{activeTimer.activity_name}</span>
                  <span className="rounded bg-background/60 px-2 py-0.5 text-[11px] text-muted-foreground">
                    {activeTimer.category}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Status: <strong className="uppercase text-foreground">{activeTimer.timer_status}</strong> · Target:{" "}
                  {activeTimer.planned_duration_minutes || 50}m
                </div>
              </div>
              <div className="flex items-center gap-2">
                {activeTimer.timer_status === "running" ? (
                  <button
                    onClick={() => handleTimerControl("pause")}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-secondary"
                  >
                    <Pause className="h-3.5 w-3.5" />
                    Pause
                  </button>
                ) : (
                  <button
                    onClick={() => handleTimerControl("resume")}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Resume
                  </button>
                )}
                <button
                  onClick={() => handleTimerControl("stop")}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-destructive px-3 py-1.5 text-xs font-semibold text-destructive-foreground"
                >
                  <Square className="h-3.5 w-3.5" />
                  Finish & Save
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleStartTimer} className="grid grid-cols-1 gap-2 sm:grid-cols-5">
              <input
                type="text"
                value={timerName}
                onChange={(e) => setTimerName(e.target.value)}
                placeholder="Session title..."
                className="rounded-lg border border-border bg-background px-3 py-2 text-xs sm:col-span-2"
                required
              />
              <select
                value={timerCategory}
                onChange={(e) => setTimerCategory(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-2 text-xs"
              >
                <option value="Deep Work">Deep Work</option>
                <option value="Coding">Coding</option>
                <option value="Writing">Writing</option>
                <option value="Study">Study</option>
                <option value="Planning">Planning</option>
                <option value="Reading">Reading</option>
              </select>
              <input
                type="number"
                min={5}
                max={480}
                value={timerPlannedMin}
                onChange={(e) => setTimerPlannedMin(Number(e.target.value))}
                className="rounded-lg border border-border bg-background px-3 py-2 text-xs"
                title="Planned duration (minutes)"
              />
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
              >
                <Play className="h-3.5 w-3.5" />
                Start Focus
              </button>
            </form>
          )}
        </div>
      </div>

      {/* KPI Cards showing Total Recorded vs Unique Clock Time */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Unique Clock Time (7d)</span>
            <Clock className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {formatDuration(summary?.unique_elapsed_clock_minutes || 0)}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            De-overlapped union of time intervals
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Total Recorded Time (7d)</span>
            <Sparkles className="h-4 w-4 text-sky-400" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {formatDuration(summary?.total_recorded_minutes || 0)}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {summary?.overlapping_sessions_count || 0} overlapping session(s) detected
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Deep Focus Time (7d)</span>
            <Timer className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {formatDuration(summary?.focus_unique_minutes || 0)}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {summary?.focus_sessions_count || 0} focus session(s)
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Overlap Deducted</span>
            <FolderKanban className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {formatDuration(summary?.overlap_minutes_deducted || 0)}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Simultaneous intervals merged automatically
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold">Time by Activity Category</h3>
          <p className="text-xs text-muted-foreground">Minutes invested across categories</p>
          {categoryAllocation.length === 0 ? (
            <div className="flex h-56 items-center justify-center text-xs text-muted-foreground">
              No completed activity sessions yet. Start a focus timer or log a manual block.
            </div>
          ) : (
            <div className="mt-4 h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryAllocation}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="category" tick={{ fontSize: 11, fill: "#9ca3af" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#11131a",
                      borderColor: "#262936",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="duration_minutes" name="Minutes" fill="#8b5cf6" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold">Project Time Allocation</h3>
          <p className="text-xs text-muted-foreground">Distribution across active projects</p>
          {projectAllocation.length === 0 ? (
            <div className="flex h-56 items-center justify-center text-xs text-muted-foreground">
              Assign a project name when logging sessions to see project allocation.
            </div>
          ) : (
            <div className="mt-4 h-60">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={projectAllocation}
                    dataKey="duration_minutes"
                    nameKey="project"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={3}
                  >
                    {projectAllocation.map((_: any, i: number) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#11131a",
                      borderColor: "#262936",
                      fontSize: "12px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Activity Session Log Table */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Recorded Activity & Focus Sessions</h3>
            <p className="text-xs text-muted-foreground">
              Overlapping intervals are flagged so total recorded time is never confused with unique clock time
            </p>
          </div>
          <span className="text-xs text-muted-foreground">{sessions.length} session(s)</span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-muted-foreground">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border py-12 text-center">
            <p className="text-sm font-medium">No activity or focus sessions recorded yet</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Use the persistent focus timer above or click &ldquo;Log Manual Session&rdquo;.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-2.5 font-medium">Date</th>
                  <th className="pb-2.5 font-medium">Activity</th>
                  <th className="pb-2.5 font-medium">Category</th>
                  <th className="pb-2.5 font-medium">Project</th>
                  <th className="pb-2.5 font-medium">Duration</th>
                  <th className="pb-2.5 font-medium">Source / Status</th>
                  <th className="pb-2.5 font-medium">Flags</th>
                  <th className="pb-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-secondary/30">
                    <td className="py-3 whitespace-nowrap">{formatDate(s.session_date)}</td>
                    <td className="py-3 font-medium">
                      <div>{s.activity_name}</div>
                      {s.notes && <div className="text-[11px] text-muted-foreground">{s.notes}</div>}
                    </td>
                    <td className="py-3">
                      <span className="rounded-md bg-secondary px-2 py-0.5 text-[11px]">
                        {s.category}
                      </span>
                    </td>
                    <td className="py-3 text-muted-foreground">{s.project || "—"}</td>
                    <td className="py-3 font-mono font-medium">
                      {formatDuration(s.duration_minutes)}
                      {s.planned_duration_minutes ? (
                        <span className="ml-1 text-[10px] text-muted-foreground">
                          / {s.planned_duration_minutes}m
                        </span>
                      ) : null}
                    </td>
                    <td className="py-3 text-muted-foreground">
                      {s.source} · {s.timer_status}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap items-center gap-1">
                        {s.is_focus_session && (
                          <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                            Focus
                          </span>
                        )}
                        {s.has_overlap && (
                          <span
                            title="This interval overlaps with another recorded session"
                            className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-400"
                          >
                            <AlertTriangle className="h-2.5 w-2.5" />
                            Overlap
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => handleDelete(s.id)}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                        title="Delete session"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Manual Activity Modal */}
      {showManualModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
            <h3 className="text-base font-semibold">Log Activity or Focus Session</h3>
            <form onSubmit={handleCreateManual} className="mt-4 space-y-3 text-xs">
              <div>
                <label className="mb-1 block font-medium">Activity Name</label>
                <input
                  type="text"
                  required
                  value={manualName}
                  onChange={(e) => setManualName(e.target.value)}
                  placeholder="e.g., Backend Schema Design"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Category</label>
                  <select
                    value={manualCategory}
                    onChange={(e) => setManualCategory(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  >
                    <option value="Deep Work">Deep Work</option>
                    <option value="Coding">Coding</option>
                    <option value="Study">Study</option>
                    <option value="Writing">Writing</option>
                    <option value="Exercise">Exercise</option>
                    <option value="Planning">Planning</option>
                    <option value="Reading">Reading</option>
                    <option value="Chores">Chores</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block font-medium">Project (Optional)</label>
                  <input
                    type="text"
                    value={manualProject}
                    onChange={(e) => setManualProject(e.target.value)}
                    placeholder="Personal Life OS"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Date</label>
                  <input
                    type="date"
                    required
                    value={manualDate}
                    onChange={(e) => setManualDate(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Start Time</label>
                  <input
                    type="time"
                    required
                    value={manualStartTime}
                    onChange={(e) => setManualStartTime(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Duration (mins)</label>
                  <input
                    type="number"
                    min={1}
                    max={1440}
                    required
                    value={manualDuration}
                    onChange={(e) => setManualDuration(Number(e.target.value))}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  checked={manualIsFocus}
                  onChange={(e) => setManualIsFocus(e.target.checked)}
                />
                <span>Count as Deep Focus Session</span>
              </label>
              <div>
                <label className="mb-1 block font-medium">Notes</label>
                <textarea
                  rows={2}
                  value={manualNotes}
                  onChange={(e) => setManualNotes(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="rounded-lg border border-border px-3 py-1.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-1.5 font-semibold text-primary-foreground"
                >
                  Save Session
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

