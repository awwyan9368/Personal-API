"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Calendar,
  Check,
  CheckCircle2,
  Edit3,
  Flame,
  Plus,
  Search,
  Trash2,
  TrendingUp,
  X,
} from "lucide-react";
import { useApp } from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { cn, todayIso } from "@/lib/utils";

const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function HabitsPage() {
  const { notify, dataVersion, triggerRefresh } = useApp();

  const [habits, setHabits] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"cards" | "matrix">("cards");

  // Modal state for Create / Edit Habit
  const [modalOpen, setModalOpen] = useState(false);
  const [editingHabit, setEditingHabit] = useState<any | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("Health");
  const [accentColor, setAccentColor] = useState("#8b5cf6");
  const [frequencyType, setFrequencyType] = useState<
    "daily" | "selected_weekdays" | "weekly_target"
  >("daily");
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [weeklyTarget, setWeeklyTarget] = useState("4");
  const [isQuantitative, setIsQuantitative] = useState(false);
  const [targetValue, setTargetValue] = useState("1");
  const [unit, setUnit] = useState("completion");
  const [startDate, setStartDate] = useState(todayIso());

  // Historical / Custom Entry Log Modal
  const [entryModalHabit, setEntryModalHabit] = useState<any | null>(null);
  const [entryDate, setEntryDate] = useState(todayIso());
  const [entryValue, setEntryValue] = useState("1");
  const [entryNotes, setEntryNotes] = useState("");

  const loadHabits = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (search.trim()) params.set("search", search.trim());
      const res = await apiFetch<any[]>(`/habits?${params.toString()}`);
      setHabits(res);
    } catch (err: any) {
      notify("Failed to load habits", err.message, "error");
    } finally {
      setLoading(false);
    }
  }, [notify, statusFilter, search]);

  useEffect(() => {
    loadHabits();
  }, [loadHabits, dataVersion]);

  const openCreateModal = () => {
    setEditingHabit(null);
    setName("");
    setDescription("");
    setCategory("Health");
    setAccentColor("#8b5cf6");
    setFrequencyType("daily");
    setSelectedWeekdays([0, 1, 2, 3, 4, 5, 6]);
    setWeeklyTarget("4");
    setIsQuantitative(false);
    setTargetValue("1");
    setUnit("completion");
    setStartDate(todayIso());
    setModalOpen(true);
  };

  const openEditModal = (h: any) => {
    setEditingHabit(h);
    setName(h.name);
    setDescription(h.description || "");
    setCategory(h.category);
    setAccentColor(h.accent_color || "#8b5cf6");
    setFrequencyType(h.frequency_type);
    setSelectedWeekdays(h.selected_weekdays || [0, 1, 2, 3, 4, 5, 6]);
    setWeeklyTarget(String(h.weekly_target || 4));
    setIsQuantitative(h.is_quantitative);
    setTargetValue(String(h.target_value || 1));
    setUnit(h.unit || "completion");
    setStartDate(h.start_date);
    setModalOpen(true);
  };

  const handleSaveHabit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        name,
        description: description || null,
        category,
        accent_color: accentColor,
        frequency_type: frequencyType,
        selected_weekdays: selectedWeekdays,
        weekly_target:
          frequencyType === "weekly_target" ? parseInt(weeklyTarget, 10) : null,
        is_quantitative: isQuantitative,
        target_value: isQuantitative ? targetValue : "1.00",
        unit: isQuantitative ? unit : "completion",
        start_date: startDate,
      };
      if (editingHabit) {
        await apiFetch(`/habits/${editingHabit.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        notify("Habit updated", name, "success");
      } else {
        await apiFetch("/habits", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        notify("Habit created", name, "success");
      }
      setModalOpen(false);
      triggerRefresh();
    } catch (err: any) {
      notify("Could not save habit", err.message, "error");
    }
  };

  const handleDeleteHabit = async (habit: any) => {
    if (!window.confirm(`Delete habit '${habit.name}' and all its recorded entries?`)) return;
    try {
      await apiFetch(`/habits/${habit.id}`, { method: "DELETE" });
      notify("Habit deleted", habit.name, "info");
      triggerRefresh();
    } catch (err: any) {
      notify("Delete failed", err.message, "error");
    }
  };

  const handleToggleDate = async (habit: any, dateStr: string, currentlyCompleted: boolean) => {
    try {
      await apiFetch(`/habits/${habit.id}/entries`, {
        method: "POST",
        body: JSON.stringify({
          entry_date: dateStr,
          completed: !currentlyCompleted,
          value: !currentlyCompleted ? String(habit.target_value || "1.00") : "0.00",
          is_historical_correction: dateStr !== todayIso(),
        }),
      });
      triggerRefresh();
    } catch (err: any) {
      notify("Could not log habit entry", err.message, "error");
    }
  };

  const handleLogCustomEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!entryModalHabit) return;
    try {
      await apiFetch(`/habits/${entryModalHabit.id}/entries`, {
        method: "POST",
        body: JSON.stringify({
          entry_date: entryDate,
          completed: true,
          value: entryValue,
          notes: entryNotes || null,
          is_historical_correction: entryDate !== todayIso(),
        }),
      });
      notify("Habit entry saved", `${entryModalHabit.name} on ${entryDate}`, "success");
      setEntryModalHabit(null);
      triggerRefresh();
    } catch (err: any) {
      notify("Failed to log entry", err.message, "error");
    }
  };

  // Generate last 14 days for the calendar matrix
  const last14Days = Array.from({ length: 14 }).map((_, idx) => {
    const d = new Date();
    d.setDate(d.getDate() - (13 - idx));
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return {
      iso: `${y}-${m}-${day}`,
      label: `${d.toLocaleDateString("en-US", { weekday: "short" })} ${day}`,
    };
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Habit Tracker</h1>
          <p className="text-xs text-muted mt-0.5">
            Timezone-aware streaks, flexible schedules, quantitative progress, and historical corrections
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-card border border-border p-1 flex text-xs">
            <button
              onClick={() => setViewMode("cards")}
              className={cn(
                "px-3 py-1 rounded-lg font-medium transition",
                viewMode === "cards" ? "bg-accent-violet text-white" : "text-muted"
              )}
            >
              Cards View
            </button>
            <button
              onClick={() => setViewMode("matrix")}
              className={cn(
                "px-3 py-1 rounded-lg font-medium transition",
                viewMode === "matrix" ? "bg-accent-violet text-white" : "text-muted"
              )}
            >
              14-Day Matrix
            </button>
          </div>
          <button
            onClick={openCreateModal}
            className="flex items-center gap-1.5 rounded-xl bg-accent-violet hover:bg-accent-violet/90 text-white px-4 py-2 text-xs font-medium"
          >
            <Plus className="h-4 w-4" />
            <span>New Habit</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-card border border-border p-4">
        <div className="flex items-center gap-2">
          {(["active", "archived", "all"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition",
                statusFilter === st
                  ? "bg-accent-violet/15 border-accent-violet/40 text-accent-violet"
                  : "bg-surface border-border text-muted hover:text-foreground"
              )}
            >
              {st}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 rounded-xl bg-surface border border-border px-3 py-1.5 w-full sm:w-64">
          <Search className="h-3.5 w-3.5 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter habits..."
            className="bg-transparent text-xs text-foreground outline-none w-full"
          />
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-44 rounded-2xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : habits.length === 0 ? (
        <div className="rounded-2xl bg-card border border-border p-12 text-center">
          <CheckCircle2 className="h-10 w-10 text-accent-violet mx-auto mb-3 opacity-80" />
          <h3 className="text-base font-semibold">No habits found</h3>
          <p className="text-xs text-muted mt-1 max-w-md mx-auto">
            Create daily, selected-weekday, or weekly-target habits. Unscheduled days never break your streak, and future dates are never counted as missed.
          </p>
          <button
            onClick={openCreateModal}
            className="mt-4 rounded-xl bg-accent-violet text-white px-4 py-2 text-xs font-medium"
          >
            + Create Your First Habit
          </button>
        </div>
      ) : viewMode === "cards" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {habits.map((h) => {
            const entryByDate: Record<string, any> = {};
            (h.recent_entries || []).forEach((e: any) => {
              entryByDate[e.entry_date] = e;
            });

            return (
              <div
                key={h.id}
                className="rounded-2xl bg-card border border-border p-5 flex flex-col justify-between gap-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <span
                      className="h-3.5 w-3.5 rounded-full mt-1 shrink-0"
                      style={{ backgroundColor: h.accent_color || "#8b5cf6" }}
                    />
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold">{h.name}</h3>
                        <span className="text-[10px] rounded bg-surface border border-border px-2 py-0.5 text-muted">
                          {h.category}
                        </span>
                      </div>
                      {h.description && (
                        <p className="text-xs text-muted mt-0.5">{h.description}</p>
                      )}
                      <p className="text-[11px] text-muted mt-1">
                        Schedule:{" "}
                        {h.frequency_type === "daily"
                          ? "Every day"
                          : h.frequency_type === "weekly_target"
                          ? `${h.weekly_target}x per week`
                          : (h.selected_weekdays || [])
                              .map((d: number) => WEEKDAY_SHORT[d])
                              .join(", ")}
                        {h.is_quantitative &&
                          ` · Target: ${h.target_value} ${h.unit}`}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => {
                        setEntryModalHabit(h);
                        setEntryDate(todayIso());
                        setEntryValue(String(h.target_value || "1"));
                        setEntryNotes("");
                      }}
                      title="Log custom value / historical correction"
                      className="p-1.5 rounded-lg bg-surface border border-border text-muted hover:text-foreground"
                    >
                      <Calendar className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => openEditModal(h)}
                      title="Edit habit"
                      className="p-1.5 rounded-lg bg-surface border border-border text-muted hover:text-foreground"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteHabit(h)}
                      title="Delete habit"
                      className="p-1.5 rounded-lg bg-surface border border-border text-muted hover:text-accent-danger"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Metrics Strip */}
                <div className="grid grid-cols-4 gap-2 rounded-xl bg-surface border border-border p-3 text-center">
                  <div>
                    <span className="text-[10px] text-muted block">Current Streak</span>
                    <span className="text-sm font-semibold text-accent-amber flex items-center justify-center gap-1 mt-0.5">
                      <Flame className="h-3.5 w-3.5" /> {h.current_streak}d
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted block">Best Streak</span>
                    <span className="text-sm font-semibold block mt-0.5">
                      {h.best_streak}d
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted block">30d Rate</span>
                    <span className="text-sm font-semibold text-accent-lime block mt-0.5">
                      {h.completion_rate_30d}%
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted block">Missed (30d)</span>
                    <span className="text-sm font-semibold block mt-0.5">
                      {h.missed_scheduled_days_30d}d
                    </span>
                  </div>
                </div>

                {/* Last 7 Days Interactive Strip + Today Button */}
                <div className="flex items-center justify-between gap-3 pt-1">
                  <div className="flex items-center gap-1.5">
                    {last14Days.slice(7).map((d) => {
                      const entry = entryByDate[d.iso];
                      const done = entry?.completed;
                      const partial =
                        !done && entry && parseFloat(entry.value) > 0;
                      return (
                        <button
                          key={d.iso}
                          onClick={() => handleToggleDate(h, d.iso, !!done)}
                          title={`${d.iso}: ${
                            done
                              ? `Completed (${entry.value} ${h.unit})`
                              : partial
                              ? `Partial (${entry.value}/${h.target_value} ${h.unit})`
                              : "Click to mark completed"
                          }`}
                          className={cn(
                            "h-8 w-8 rounded-lg text-[10px] font-medium border flex flex-col items-center justify-center transition",
                            done
                              ? "bg-accent-lime/20 border-accent-lime text-accent-lime"
                              : partial
                              ? "bg-accent-amber/20 border-accent-amber text-accent-amber"
                              : "bg-surface border-border text-muted hover:border-accent-violet/40"
                          )}
                        >
                          <span>{d.iso.slice(8)}</span>
                        </button>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => handleToggleDate(h, todayIso(), h.completed_today)}
                    className={cn(
                      "px-4 py-2 rounded-xl text-xs font-medium border transition flex items-center gap-1.5",
                      h.completed_today
                        ? "bg-accent-lime text-black border-accent-lime font-semibold"
                        : "bg-accent-violet/15 border-accent-violet/40 text-accent-violet hover:bg-accent-violet hover:text-white"
                    )}
                  >
                    <Check className="h-3.5 w-3.5" />
                    <span>{h.completed_today ? "Completed Today" : "Mark Today"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* 14-Day Calendar Matrix View */
        <div className="rounded-2xl bg-card border border-border overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b border-border bg-surface text-muted">
                <th className="text-left p-3.5 font-medium min-w-[180px]">Habit</th>
                <th className="text-center p-2 font-medium">Streak</th>
                <th className="text-center p-2 font-medium">30d Rate</th>
                {last14Days.map((d) => (
                  <th key={d.iso} className="text-center p-2 font-mono text-[10px]">
                    {d.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {habits.map((h) => {
                const map: Record<string, any> = {};
                (h.recent_entries || []).forEach((e: any) => {
                  map[e.entry_date] = e;
                });
                return (
                  <tr key={h.id} className="border-b border-border/60 hover:bg-surface/50">
                    <td className="p-3.5 font-medium">{h.name}</td>
                    <td className="p-2 text-center font-mono text-accent-amber">
                      {h.current_streak}d
                    </td>
                    <td className="p-2 text-center font-mono text-accent-lime">
                      {h.completion_rate_30d}%
                    </td>
                    {last14Days.map((d) => {
                      const entry = map[d.iso];
                      const done = entry?.completed;
                      return (
                        <td key={d.iso} className="p-1.5 text-center">
                          <button
                            onClick={() => handleToggleDate(h, d.iso, !!done)}
                            className={cn(
                              "h-7 w-7 rounded-md border inline-flex items-center justify-center transition",
                              done
                                ? "bg-accent-lime/25 border-accent-lime text-accent-lime"
                                : "bg-surface border-border text-transparent hover:border-accent-violet"
                            )}
                          >
                            ✓
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Habit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
            onClick={() => setModalOpen(false)}
          />
          <div className="relative z-10 w-full max-w-lg rounded-2xl bg-card border border-border p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold">
                {editingHabit ? "Edit Habit" : "Create New Habit"}
              </h2>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1 rounded-lg text-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSaveHabit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-muted mb-1">Habit Name</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Deep Work Block, Read 30 Pages"
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-muted mb-1">Category</label>
                  <input
                    type="text"
                    required
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-muted mb-1">Description (Optional)</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Why does this habit matter?"
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted mb-1">Schedule Type</label>
                  <select
                    value={frequencyType}
                    onChange={(e) => setFrequencyType(e.target.value as any)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  >
                    <option value="daily">Daily</option>
                    <option value="selected_weekdays">Selected Weekdays</option>
                    <option value="weekly_target">Weekly Target (N days/week)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-muted mb-1">Start Date</label>
                  <input
                    type="date"
                    required
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {frequencyType === "selected_weekdays" && (
                <div>
                  <label className="block text-muted mb-1.5">
                    Scheduled Weekdays (Unscheduled days won&apos;t break your streak)
                  </label>
                  <div className="flex gap-1.5">
                    {WEEKDAY_SHORT.map((label, idx) => {
                      const active = selectedWeekdays.includes(idx);
                      return (
                        <button
                          key={label}
                          type="button"
                          onClick={() =>
                            setSelectedWeekdays((prev) =>
                              prev.includes(idx)
                                ? prev.filter((d) => d !== idx)
                                : [...prev, idx]
                            )
                          }
                          className={cn(
                            "flex-1 py-1.5 rounded-lg border font-medium",
                            active
                              ? "bg-accent-violet text-white border-accent-violet"
                              : "bg-surface border-border text-muted"
                          )}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {frequencyType === "weekly_target" && (
                <div>
                  <label className="block text-muted mb-1">
                    Weekly Completions Target (1–7 days/week)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="7"
                    value={weeklyTarget}
                    onChange={(e) => setWeeklyTarget(e.target.value)}
                    className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                  />
                </div>
              )}

              <div className="rounded-xl bg-surface border border-border p-3 space-y-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isQuantitative}
                    onChange={(e) => setIsQuantitative(e.target.checked)}
                  />
                  <span className="font-medium">
                    Quantitative Habit (Track numerical target & partial progress)
                  </span>
                </label>
                {isQuantitative && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-muted mb-1">Daily Target Value</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        value={targetValue}
                        onChange={(e) => setTargetValue(e.target.value)}
                        className="w-full rounded-lg bg-card border border-border px-3 py-1.5 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-muted mb-1">Unit</label>
                      <input
                        type="text"
                        value={unit}
                        onChange={(e) => setUnit(e.target.value)}
                        placeholder="pages, mins, km, liters"
                        className="w-full rounded-lg bg-card border border-border px-3 py-1.5 text-sm"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="rounded-lg bg-surface border border-border px-4 py-2 text-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-accent-violet text-white px-4 py-2 font-medium"
                >
                  {editingHabit ? "Save Changes" : "Create Habit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Custom / Historical Entry Modal */}
      {entryModalHabit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
            onClick={() => setEntryModalHabit(null)}
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl bg-card border border-border p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold">
                Log Entry / Historical Correction: {entryModalHabit.name}
              </h2>
              <button
                onClick={() => setEntryModalHabit(null)}
                className="p-1 rounded-lg text-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleLogCustomEntry} className="space-y-4 text-xs">
              <div>
                <label className="block text-muted mb-1">Entry Date</label>
                <input
                  type="date"
                  required
                  max={todayIso()}
                  value={entryDate}
                  onChange={(e) => setEntryDate(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-muted mb-1">
                  Recorded Value ({entryModalHabit.unit} — target: {entryModalHabit.target_value})
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={entryValue}
                  onChange={(e) => setEntryValue(e.target.value)}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-muted mb-1">Notes (Optional)</label>
                <input
                  type="text"
                  value={entryNotes}
                  onChange={(e) => setEntryNotes(e.target.value)}
                  placeholder="Context or note for this entry..."
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEntryModalHabit(null)}
                  className="rounded-lg bg-surface border border-border px-4 py-2 text-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-accent-violet text-white px-4 py-2 font-medium"
                >
                  Save Entry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

