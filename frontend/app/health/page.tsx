"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Moon,
  Smile,
  Activity,
  Droplets,
  Plus,
  Trash2,
  Info,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

export default function HealthWellbeingPage() {
  const [records, setRecords] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  // Form state matching WellbeingCreate
  const [recordDate, setRecordDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [sleepHours, setSleepHours] = useState("7.5");
  const [sleepQuality, setSleepQuality] = useState("8");
  const [bedtime, setBedtime] = useState("23:00");
  const [wakeTime, setWakeTime] = useState("06:30");
  const [moodScore, setMoodScore] = useState("8");
  const [energyScore, setEnergyScore] = useState("8");
  const [exerciseMinutes, setExerciseMinutes] = useState("45");
  const [exerciseType, setExerciseType] = useState("Strength & Walk");
  const [waterIntakeMl, setWaterIntakeMl] = useState("2500");
  const [weightKg, setWeightKg] = useState("");
  const [steps, setSteps] = useState("8500");
  const [notes, setNotes] = useState("");

  async function loadAll() {
    setLoading(true);
    try {
      const [recList, sumData] = await Promise.all([
        apiFetch("/wellbeing"),
        apiFetch("/wellbeing/summary"),
      ]);
      setRecords(recList || []);
      setSummary(sumData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleSaveWellbeing(e: React.FormEvent) {
    e.preventDefault();
    try {
      await apiFetch("/wellbeing", {
        method: "POST",
        body: JSON.stringify({
          record_date: recordDate,
          sleep_duration_hours: sleepHours ? Number(sleepHours) : null,
          sleep_quality: sleepQuality ? Number(sleepQuality) : null,
          bedtime: bedtime || null,
          wake_time: wakeTime || null,
          mood_score: moodScore ? Number(moodScore) : null,
          energy_score: energyScore ? Number(energyScore) : null,
          exercise_duration_minutes: exerciseMinutes ? Number(exerciseMinutes) : null,
          exercise_type: exerciseType.trim() || null,
          water_intake_ml: waterIntakeMl ? Number(waterIntakeMl) : null,
          weight_kg: weightKg ? Number(weightKg) : null,
          custom_measurements: steps ? { steps: Number(steps) } : {},
          notes: notes.trim() || null,
        }),
      });
      setShowModal(false);
      setNotes("");
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to save wellbeing record");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this wellbeing log?")) return;
    try {
      await apiFetch(`/wellbeing/${id}`, { method: "DELETE" });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to delete wellbeing log");
    }
  }

  const chartData = (summary?.daily_series || []).map((r: any) => ({
    date: r.date.slice(5),
    sleep_hours: r.sleep_hours,
    mood: r.mood_score,
    energy: r.energy_score,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Health, Sleep, Mood & Energy</h1>
          <p className="text-sm text-muted-foreground">
            Self-reported daily wellbeing metrics and observational relationships with habits and focus
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Log Daily Check-in
        </button>
      </div>

      {/* Non-Medical Observational Banner */}
      <div className="flex items-start gap-2.5 rounded-xl border border-primary/25 bg-primary/5 p-3.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div>
          <strong className="text-foreground">Personal Observational Analytics Only:</strong>{" "}
          {summary?.disclaimer ||
            "All sleep, mood, energy, and exercise patterns are observational summaries of your self-reported records and do not constitute medical advice."}
        </div>
      </div>

      {/* KPI Averages */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Avg Sleep Duration</span>
            <Moon className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {summary?.averages?.sleep_duration_hours != null
              ? `${summary.averages.sleep_duration_hours} hrs`
              : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Quality: {summary?.averages?.sleep_quality ?? "—"} / 10
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Avg Mood & Energy</span>
            <Smile className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {summary?.averages?.mood_score != null ? `${summary.averages.mood_score} / 10` : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Energy: {summary?.averages?.energy_score ?? "—"} / 10
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Exercise & Movement</span>
            <Activity className="h-4 w-4 text-sky-400" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {summary?.averages?.exercise_duration_minutes != null
              ? `${summary.averages.exercise_duration_minutes}m / day`
              : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Total logged: {summary?.total_exercise_minutes || 0} mins
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Hydration & Days Logged</span>
            <Droplets className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold">
            {summary?.averages?.water_intake_ml != null
              ? `${summary.averages.water_intake_ml} ml`
              : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {summary?.recorded_days || 0} day(s) recorded in window
          </p>
        </div>
      </div>

      {/* Trends Chart & Observational Correlations */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold">Sleep, Mood & Energy Trends</h3>
          <p className="text-xs text-muted-foreground">
            Missing days are preserved cleanly rather than fabricated as zeros
          </p>
          {chartData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-xs text-muted-foreground">
              Log your first daily wellbeing check-in to visualize longitudinal trends.
            </div>
          ) : (
            <div className="mt-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} />
                  <YAxis domain={[0, 12]} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#11131a",
                      borderColor: "#262936",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px" }} />
                  <Line
                    type="monotone"
                    dataKey="sleep_hours"
                    name="Sleep (hrs)"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="mood"
                    name="Mood (1-10)"
                    stroke="#84cc16"
                    strokeWidth={2}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="energy"
                    name="Energy (1-10)"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-semibold">Observational Relationships</h3>
          <p className="text-xs text-muted-foreground">
            Deterministic cross-domain comparisons from your local history
          </p>
          <div className="mt-4 space-y-3">
            {(summary?.correlations || []).length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-4 text-xs text-muted-foreground">
                Log at least 4 days of sleep/energy alongside focus sessions to compute observational comparisons.
              </div>
            ) : (
              summary.correlations.map((rel: any, idx: number) => (
                <div
                  key={idx}
                  className="rounded-lg border border-border bg-secondary/30 p-3.5 text-xs"
                >
                  <div className="font-semibold text-foreground">
                    {rel.metric_a} → {rel.metric_b}
                  </div>
                  <p className="mt-1 leading-relaxed text-muted-foreground">
                    Avg when ≥7h: <strong>{rel.avg_when_high}m</strong> vs &lt;7h:{" "}
                    <strong>{rel.avg_when_low}m</strong> ({rel.note})
                  </p>
                  <div className="mt-2 text-[10px] text-primary">
                    Sample size: {rel.sample_days} recorded day(s)
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Historical Wellbeing Records */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold">Daily Wellbeing Log History</h3>
        {loading ? (
          <div className="py-10 text-center text-xs text-muted-foreground">Loading records...</div>
        ) : records.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border py-10 text-center text-xs text-muted-foreground">
            No wellbeing records yet. Click &ldquo;Log Daily Check-in&rdquo; to record today&apos;s metrics.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-2.5 font-medium">Date</th>
                  <th className="pb-2.5 font-medium">Sleep</th>
                  <th className="pb-2.5 font-medium">Mood</th>
                  <th className="pb-2.5 font-medium">Energy</th>
                  <th className="pb-2.5 font-medium">Exercise</th>
                  <th className="pb-2.5 font-medium">Hydration / Weight</th>
                  <th className="pb-2.5 font-medium">Notes</th>
                  <th className="pb-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {records.map((r) => (
                  <tr key={r.id} className="hover:bg-secondary/30">
                    <td className="py-3 font-medium">{formatDate(r.record_date)}</td>
                    <td className="py-3">
                      {r.sleep_duration_hours != null ? `${r.sleep_duration_hours}h` : "—"}
                      {r.sleep_quality != null ? (
                        <span className="ml-1 text-[10px] text-muted-foreground">
                          (Q:{r.sleep_quality}/10)
                        </span>
                      ) : null}
                    </td>
                    <td className="py-3">{r.mood_score != null ? `${r.mood_score}/10` : "—"}</td>
                    <td className="py-3">{r.energy_score != null ? `${r.energy_score}/10` : "—"}</td>
                    <td className="py-3">
                      {r.exercise_duration_minutes != null
                        ? `${r.exercise_duration_minutes}m (${r.exercise_type || "Workout"})`
                        : "—"}
                    </td>
                    <td className="py-3 text-muted-foreground">
                      {r.water_intake_ml != null ? `${r.water_intake_ml}ml` : "—"}
                      {r.weight_kg != null ? ` · ${r.weight_kg}kg` : ""}
                    </td>
                    <td className="py-3 max-w-xs truncate text-muted-foreground">
                      {r.notes || "—"}
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => handleDelete(r.id)}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
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

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-card p-5 shadow-xl">
            <h3 className="text-base font-semibold">Log Daily Wellbeing Check-in</h3>
            <form onSubmit={handleSaveWellbeing} className="mt-4 space-y-3 text-xs">
              <div>
                <label className="mb-1 block font-medium">Date</label>
                <input
                  type="date"
                  required
                  value={recordDate}
                  onChange={(e) => setRecordDate(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <label className="mb-1 block font-medium">Sleep Hours</label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    max="24"
                    value={sleepHours}
                    onChange={(e) => setSleepHours(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Sleep Quality (1-10)</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={sleepQuality}
                    onChange={(e) => setSleepQuality(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Bedtime</label>
                  <input
                    type="time"
                    value={bedtime}
                    onChange={(e) => setBedtime(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Wake Time</label>
                  <input
                    type="time"
                    value={wakeTime}
                    onChange={(e) => setWakeTime(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Mood (1-10)</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={moodScore}
                    onChange={(e) => setMoodScore(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Energy (1-10)</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={energyScore}
                    onChange={(e) => setEnergyScore(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Exercise (mins)</label>
                  <input
                    type="number"
                    min="0"
                    value={exerciseMinutes}
                    onChange={(e) => setExerciseMinutes(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Exercise Type</label>
                  <input
                    type="text"
                    value={exerciseType}
                    onChange={(e) => setExerciseType(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Water (ml)</label>
                  <input
                    type="number"
                    min="0"
                    value={waterIntakeMl}
                    onChange={(e) => setWaterIntakeMl(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Weight kg (optional)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={weightKg}
                    onChange={(e) => setWeightKg(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Steps (custom metric)</label>
                  <input
                    type="number"
                    value={steps}
                    onChange={(e) => setSteps(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block font-medium">Notes</label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="How did you feel today?"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-border px-3 py-1.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-1.5 font-semibold text-primary-foreground"
                >
                  Save Check-in
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

