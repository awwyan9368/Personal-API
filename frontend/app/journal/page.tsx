"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  BookOpen,
  Sparkles,
  Plus,
  Search,
  Tag,
  Trash2,
  Smile,
  Zap,
  CheckCircle2,
} from "lucide-react";

export default function JournalPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [mode, setMode] = useState<"list" | "freeform" | "review">("list");

  // Shared entry fields matching JournalCreate
  const [entryDate, setEntryDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [dailyIntention, setDailyIntention] = useState("");
  const [moodScore, setMoodScore] = useState("8");
  const [energyScore, setEnergyScore] = useState("8");
  const [tagsInput, setTagsInput] = useState("reflection, personal");

  // 7-Question Daily Review fields mapped to JournalCreate
  const [qWentWell, setQWentWell] = useState("");
  const [qEnergyNotes, setQEnergyNotes] = useState("");
  const [qAccomplishments, setQAccomplishments] = useState("");
  const [qMoneySpent, setQMoneySpent] = useState("");
  const [qTimeSpent, setQTimeSpent] = useState("");
  const [qCouldImprove, setQCouldImprove] = useState("");
  const [qTomorrowFocus, setQTomorrowFocus] = useState("");

  async function loadEntries() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (tagFilter.trim()) params.set("tag", tagFilter.trim());
      const data = await apiFetch(`/journal?${params.toString()}`);
      setEntries(data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadEntries();
  }, [search, tagFilter]);

  async function handleSaveEntry(e: React.FormEvent) {
    e.preventDefault();
    const isReview = mode === "review";
    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    try {
      await apiFetch("/journal", {
        method: "POST",
        body: JSON.stringify({
          entry_date: entryDate,
          title: title.trim() || (isReview ? `Daily Review — ${entryDate}` : "Journal Reflection"),
          content: content.trim() || "",
          daily_intention: dailyIntention.trim() || null,
          mood_reference: moodScore ? Number(moodScore) : null,
          energy_reference: energyScore ? Number(energyScore) : null,
          tags,
          is_daily_review: isReview,
          review_went_well: isReview ? qWentWell.trim() || null : null,
          review_energy_notes: isReview ? qEnergyNotes.trim() || null : null,
          review_accomplishments: isReview ? qAccomplishments.trim() || null : null,
          review_money_spent: isReview ? qMoneySpent.trim() || null : null,
          review_time_spent: isReview ? qTimeSpent.trim() || null : null,
          review_could_improve: isReview ? qCouldImprove.trim() || null : null,
          tomorrow_focus: isReview ? qTomorrowFocus.trim() || null : null,
        }),
      });
      setMode("list");
      setTitle("");
      setContent("");
      setDailyIntention("");
      setQWentWell("");
      setQEnergyNotes("");
      setQAccomplishments("");
      setQMoneySpent("");
      setQTimeSpent("");
      setQCouldImprove("");
      setQTomorrowFocus("");
      await loadEntries();
    } catch (err: any) {
      alert(err.message || "Failed to save journal entry");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this private journal entry?")) return;
    try {
      await apiFetch(`/journal/${id}`, { method: "DELETE" });
      await loadEntries();
    } catch (err: any) {
      alert(err.message || "Failed to delete entry");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Private Journal & Daily Review</h1>
          <p className="text-sm text-muted-foreground">
            100% local private reflections and structured 7-question evening review
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setMode(mode === "review" ? "list" : "review")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/15 px-3.5 py-2 text-xs font-semibold text-primary hover:bg-primary/25"
          >
            <Sparkles className="h-4 w-4" />
            7-Question Daily Review
          </button>
          <button
            onClick={() => setMode(mode === "freeform" ? "list" : "freeform")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            New Free-form Entry
          </button>
        </div>
      </div>

      {/* Editor Panel */}
      {mode !== "list" && (
        <form
          onSubmit={handleSaveEntry}
          className="rounded-xl border border-primary/30 bg-card p-5 shadow-md space-y-4 text-xs"
        >
          <div className="flex items-center justify-between border-b border-border pb-3">
            <h2 className="text-base font-bold">
              {mode === "review" ? "Guided 7-Question Daily Review" : "New Private Journal Entry"}
            </h2>
            <button
              type="button"
              onClick={() => setMode("list")}
              className="text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <div>
              <label className="mb-1 block font-medium">Date</label>
              <input
                type="date"
                required
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Mood (1–10)</label>
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
              <label className="mb-1 block font-medium">Energy (1–10)</label>
              <input
                type="number"
                min="1"
                max="10"
                value={energyScore}
                onChange={(e) => setEnergyScore(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Tags (comma-separated)</label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block font-medium">Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={
                  mode === "review" ? "Evening Daily Review" : "Thoughts, reflections, or milestones..."
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Daily Intention</label>
              <input
                type="text"
                value={dailyIntention}
                onChange={(e) => setDailyIntention(e.target.value)}
                placeholder="Primary intention for the day..."
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
          </div>

          {mode === "review" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block font-semibold text-foreground">
                  1. What went well today?
                </label>
                <textarea
                  rows={2}
                  value={qWentWell}
                  onChange={(e) => setQWentWell(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-foreground">
                  2. What drained or boosted my energy?
                </label>
                <textarea
                  rows={2}
                  value={qEnergyNotes}
                  onChange={(e) => setQEnergyNotes(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-foreground">
                  3. What did I accomplish?
                </label>
                <textarea
                  rows={2}
                  value={qAccomplishments}
                  onChange={(e) => setQAccomplishments(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-foreground">
                  4. How did I spend money today?
                </label>
                <textarea
                  rows={2}
                  value={qMoneySpent}
                  onChange={(e) => setQMoneySpent(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-foreground">
                  5. How did I invest my time & habits?
                </label>
                <textarea
                  rows={2}
                  value={qTimeSpent}
                  onChange={(e) => setQTimeSpent(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-foreground">
                  6. What could I improve?
                </label>
                <textarea
                  rows={2}
                  value={qCouldImprove}
                  onChange={(e) => setQCouldImprove(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block font-semibold text-foreground">
                  7. Focus & note for tomorrow
                </label>
                <textarea
                  rows={2}
                  value={qTomorrowFocus}
                  onChange={(e) => setQTomorrowFocus(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                />
              </div>
            </div>
          ) : (
            <div>
              <label className="mb-1 block font-medium">Reflection / Notes (Markdown supported)</label>
              <textarea
                rows={6}
                required
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Write freely..."
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setMode("list")}
              className="rounded-lg border border-border px-3 py-1.5"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-lg bg-primary px-4 py-1.5 font-semibold text-primary-foreground"
            >
              Save to Local Database
            </button>
          </div>
        </form>
      )}

      {/* Search & Filter */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search journal titles, reflections, or daily review answers..."
            className="w-full rounded-lg border border-border bg-card pl-9 pr-3 py-2 text-xs"
          />
        </div>
        <div className="relative w-full sm:w-56">
          <Tag className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            placeholder="Filter by tag..."
            className="w-full rounded-lg border border-border bg-card pl-9 pr-3 py-2 text-xs"
          />
        </div>
      </div>

      {/* Entries Feed */}
      {loading ? (
        <div className="py-12 text-center text-xs text-muted-foreground">Loading journal entries...</div>
      ) : entries.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card py-14 text-center">
          <BookOpen className="mx-auto h-8 w-8 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">Your private journal is empty</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Start a free-form journal entry or complete the 7-Question Daily Review.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="rounded-xl border border-border bg-card p-5 shadow-sm transition hover:border-border/90"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-primary">
                      {formatDate(entry.entry_date)}
                    </span>
                    {entry.is_daily_review && (
                      <span className="inline-flex items-center gap-1 rounded bg-primary/15 px-2 py-0.5 text-[10px] font-semibold text-primary">
                        <CheckCircle2 className="h-3 w-3" />
                        7-Question Daily Review
                      </span>
                    )}
                    {entry.mood_reference != null && (
                      <span className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-[10px]">
                        <Smile className="h-3 w-3 text-accent" />
                        Mood {entry.mood_reference}/10
                      </span>
                    )}
                    {entry.energy_reference != null && (
                      <span className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-[10px]">
                        <Zap className="h-3 w-3 text-sky-400" />
                        Energy {entry.energy_reference}/10
                      </span>
                    )}
                  </div>
                  <h3 className="mt-1.5 text-base font-bold">{entry.title || "Untitled Reflection"}</h3>
                  {entry.daily_intention && (
                    <p className="mt-0.5 text-xs text-primary">Intention: {entry.daily_intention}</p>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(entry.id)}
                  className="rounded p-1.5 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>

              {entry.content && (
                <p className="mt-3 whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">
                  {entry.content}
                </p>
              )}

              {entry.is_daily_review && (
                <div className="mt-4 grid grid-cols-1 gap-3 rounded-lg border border-border/60 bg-secondary/20 p-3.5 text-xs sm:grid-cols-2">
                  {entry.review_went_well && (
                    <div>
                      <div className="font-semibold text-muted-foreground">What went well</div>
                      <div className="mt-0.5">{entry.review_went_well}</div>
                    </div>
                  )}
                  {entry.review_energy_notes && (
                    <div>
                      <div className="font-semibold text-muted-foreground">Energy notes</div>
                      <div className="mt-0.5">{entry.review_energy_notes}</div>
                    </div>
                  )}
                  {entry.review_accomplishments && (
                    <div>
                      <div className="font-semibold text-muted-foreground">Accomplishments</div>
                      <div className="mt-0.5">{entry.review_accomplishments}</div>
                    </div>
                  )}
                  {entry.review_money_spent && (
                    <div>
                      <div className="font-semibold text-muted-foreground">Money spent</div>
                      <div className="mt-0.5">{entry.review_money_spent}</div>
                    </div>
                  )}
                  {entry.review_time_spent && (
                    <div>
                      <div className="font-semibold text-muted-foreground">Time & habits</div>
                      <div className="mt-0.5">{entry.review_time_spent}</div>
                    </div>
                  )}
                  {entry.review_could_improve && (
                    <div>
                      <div className="font-semibold text-muted-foreground">Could improve</div>
                      <div className="mt-0.5">{entry.review_could_improve}</div>
                    </div>
                  )}
                  {entry.tomorrow_focus && (
                    <div className="sm:col-span-2">
                      <div className="font-semibold text-primary">Focus for tomorrow</div>
                      <div className="mt-0.5">{entry.tomorrow_focus}</div>
                    </div>
                  )}
                </div>
              )}

              {(entry.tags || []).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {entry.tags.map((t: string) => (
                    <span
                      key={t}
                      className="rounded-full bg-secondary px-2.5 py-0.5 text-[10px] text-muted-foreground"
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

