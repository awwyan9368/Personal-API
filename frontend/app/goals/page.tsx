"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Target,
  Plus,
  CheckCircle2,
  Circle,
  TrendingUp,
  Trash2,
  Flag,
  Calendar,
} from "lucide-react";

export default function GoalsProjectsPage() {
  const [goals, setGoals] = useState<any[]>([]);
  const [habits, setHabits] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [progressGoal, setProgressGoal] = useState<any | null>(null);
  const [deltaValue, setDeltaValue] = useState("1");
  const [progressNotes, setProgressNotes] = useState("");
  const [newMilestoneTitle, setNewMilestoneTitle] = useState<Record<string, string>>({});

  // Create form matching GoalCreate
  const [name, setName] = useState("");
  const [category, setCategory] = useState("Career & Engineering");
  const [project, setProject] = useState("Personal Life OS");
  const [description, setDescription] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [targetValue, setTargetValue] = useState("100");
  const [unit, setUnit] = useState("hours");
  const [milestoneText, setMilestoneText] = useState("Design architecture\nBuild core engine\nShip v1.0");
  const [selectedHabits, setSelectedHabits] = useState<string[]>([]);

  async function loadAll() {
    setLoading(true);
    try {
      const [goalsData, habitsData] = await Promise.all([
        apiFetch("/goals"),
        apiFetch("/habits?include_archived=false"),
      ]);
      setGoals(goalsData || []);
      setHabits(habitsData || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleCreateGoal(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const milestones = milestoneText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((m, idx) => ({ title: m, sort_order: idx }));

    try {
      await apiFetch("/goals", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          category,
          project: project.trim() || null,
          description: description.trim() || null,
          target_date: targetDate || null,
          target_value: Number(targetValue || 100),
          current_value: 0,
          unit: unit.trim() || "units",
          milestones,
          related_habit_ids: selectedHabits,
        }),
      });
      setShowCreateModal(false);
      setName("");
      setDescription("");
      setSelectedHabits([]);
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to create goal");
    }
  }

  async function handleLogProgress(e: React.FormEvent) {
    e.preventDefault();
    if (!progressGoal) return;
    try {
      await apiFetch(`/goals/${progressGoal.id}/progress`, {
        method: "POST",
        body: JSON.stringify({
          value_delta: Number(deltaValue),
          notes: progressNotes.trim() || null,
        }),
      });
      setProgressGoal(null);
      setDeltaValue("1");
      setProgressNotes("");
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to log progress");
    }
  }

  async function handleToggleMilestone(goalId: string, ms: any) {
    try {
      await apiFetch(`/goals/${goalId}/milestones/${ms.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_completed: !ms.is_completed }),
      });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to update milestone");
    }
  }

  async function handleAddMilestone(goalId: string) {
    const t = (newMilestoneTitle[goalId] || "").trim();
    if (!t) return;
    try {
      await apiFetch(`/goals/${goalId}/milestones`, {
        method: "POST",
        body: JSON.stringify({ title: t }),
      });
      setNewMilestoneTitle((prev) => ({ ...prev, [goalId]: "" }));
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to add milestone");
    }
  }

  async function handleDeleteGoal(id: string) {
    if (!confirm("Delete this goal and its milestones?")) return;
    try {
      await apiFetch(`/goals/${id}`, { method: "DELETE" });
      await loadAll();
    } catch (err: any) {
      alert(err.message || "Failed to delete goal");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Goals, Projects & Milestones</h1>
          <p className="text-sm text-muted-foreground">
            Track long-term targets, milestone checklists, deadline pace, and linked daily habits
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Goal
        </button>
      </div>

      {loading ? (
        <div className="py-16 text-center text-xs text-muted-foreground">Loading goals...</div>
      ) : goals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card py-16 text-center">
          <Target className="mx-auto h-8 w-8 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">No goals created yet</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Break down your projects and personal ambitions into measurable targets and milestones.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground"
          >
            <Plus className="h-4 w-4" />
            Create Your First Goal
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {goals.map((g) => {
            const paceColors: Record<string, string> = {
              completed: "bg-accent/15 text-accent",
              ahead: "bg-emerald-500/15 text-emerald-400",
              on_track: "bg-emerald-500/15 text-emerald-400",
              behind: "bg-amber-500/15 text-amber-400",
            };
            const paceBadge = paceColors[g.pace_status] || "bg-secondary text-muted-foreground";

            return (
              <div
                key={g.id}
                className="flex flex-col justify-between rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                          {g.category}
                        </span>
                        {g.project && (
                          <span className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                            {g.project}
                          </span>
                        )}
                        <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${paceBadge}`}>
                          {(g.pace_status || "active").replace("_", " ")}
                        </span>
                      </div>
                      <h3 className="mt-2 text-base font-bold">{g.name}</h3>
                      {g.description && (
                        <p className="mt-1 text-xs text-muted-foreground">{g.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => setProgressGoal(g)}
                        className="inline-flex items-center gap-1 rounded-lg bg-primary/15 px-2.5 py-1.5 text-xs font-semibold text-primary hover:bg-primary/25"
                      >
                        <TrendingUp className="h-3.5 w-3.5" />
                        + Progress
                      </button>
                      <button
                        onClick={() => handleDeleteGoal(g.id)}
                        className="rounded p-1.5 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-4">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-semibold">
                        {g.current_value} / {g.target_value} {g.unit}
                      </span>
                      <span className="font-bold text-primary">{g.progress_percent}%</span>
                    </div>
                    <div className="mt-1.5 h-2.5 w-full overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${Math.min(100, g.progress_percent)}%` }}
                      />
                    </div>
                    {g.target_date && (
                      <div className="mt-1.5 flex items-center justify-between text-[11px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          Target: {formatDate(g.target_date)}
                        </span>
                        {g.expected_pace_percent != null && (
                          <span>Expected linear pace: {g.expected_pace_percent}%</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Milestones Checklist */}
                  <div className="mt-5 border-t border-border/60 pt-4">
                    <div className="mb-2 flex items-center justify-between text-xs font-semibold">
                      <span className="inline-flex items-center gap-1.5">
                        <Flag className="h-3.5 w-3.5 text-primary" />
                        Milestones ({g.milestones?.filter((m: any) => m.is_completed).length || 0}/
                        {g.milestones?.length || 0})
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {(g.milestones || []).map((ms: any) => (
                        <button
                          key={ms.id}
                          onClick={() => handleToggleMilestone(g.id, ms)}
                          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-secondary/50"
                        >
                          {ms.is_completed ? (
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-accent" />
                          ) : (
                            <Circle className="h-4 w-4 shrink-0 text-muted-foreground" />
                          )}
                          <span className={ms.is_completed ? "line-through text-muted-foreground" : ""}>
                            {ms.title}
                          </span>
                        </button>
                      ))}
                    </div>
                    <div className="mt-2 flex gap-2">
                      <input
                        type="text"
                        placeholder="Add milestone..."
                        value={newMilestoneTitle[g.id] || ""}
                        onChange={(e) =>
                          setNewMilestoneTitle((prev) => ({ ...prev, [g.id]: e.target.value }))
                        }
                        className="flex-1 rounded-lg border border-border bg-background px-2.5 py-1 text-xs"
                      />
                      <button
                        type="button"
                        onClick={() => handleAddMilestone(g.id)}
                        className="rounded-lg bg-secondary px-2.5 py-1 text-xs font-medium hover:bg-secondary/80"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Goal Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-xl border border-border bg-card p-5 shadow-xl">
            <h3 className="text-base font-semibold">Create New Goal</h3>
            <form onSubmit={handleCreateGoal} className="mt-4 space-y-3 text-xs">
              <div>
                <label className="mb-1 block font-medium">Goal Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Ship Personal Life OS & Master Rust"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Category</label>
                  <input
                    type="text"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Project</label>
                  <input
                    type="text"
                    value={project}
                    onChange={(e) => setProject(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="mb-1 block font-medium">Target Value</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Unit</label>
                  <input
                    type="text"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    placeholder="hours, pages, %"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label className="mb-1 block font-medium">Deadline</label>
                  <input
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block font-medium">Description</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-medium">Initial Milestones (one per line)</label>
                <textarea
                  rows={3}
                  value={milestoneText}
                  onChange={(e) => setMilestoneText(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              {habits.length > 0 && (
                <div>
                  <label className="mb-1 block font-medium">Link Supporting Habits</label>
                  <div className="max-h-28 space-y-1 overflow-y-auto rounded-lg border border-border bg-background p-2">
                    {habits.map((h) => (
                      <label key={h.id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={selectedHabits.includes(h.id)}
                          onChange={(e) =>
                            setSelectedHabits((prev) =>
                              e.target.checked ? [...prev, h.id] : prev.filter((id) => id !== h.id)
                            )
                          }
                        />
                        <span>{h.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg border border-border px-3 py-1.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-1.5 font-semibold text-primary-foreground"
                >
                  Create Goal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Log Progress Modal */}
      {progressGoal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-sm rounded-xl border border-border bg-card p-5 shadow-xl">
            <h3 className="text-base font-semibold">Log Progress: {progressGoal.name}</h3>
            <form onSubmit={handleLogProgress} className="mt-4 space-y-3 text-xs">
              <div>
                <label className="mb-1 block font-medium">
                  Increment ({progressGoal.unit || "units"})
                </label>
                <input
                  type="number"
                  step="any"
                  required
                  value={deltaValue}
                  onChange={(e) => setDeltaValue(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-medium">Progress Notes</label>
                <textarea
                  rows={2}
                  value={progressNotes}
                  onChange={(e) => setProgressNotes(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setProgressGoal(null)}
                  className="rounded-lg border border-border px-3 py-1.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-1.5 font-semibold text-primary-foreground"
                >
                  Record Progress
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

