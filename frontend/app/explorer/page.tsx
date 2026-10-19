"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
  Database,
  Search,
  Download,
  BookmarkPlus,
  Trash2,
  Eye,
  Table,
  Layers,
  X,
} from "lucide-react";

const ENTITY_OPTIONS = [
  { value: "transactions", label: "Financial Transactions" },
  { value: "habits", label: "Habits" },
  { value: "habit_entries", label: "Habit Completion Entries" },
  { value: "screen_time", label: "Screen-Time Sessions" },
  { value: "activities", label: "Activity & Focus Sessions" },
  { value: "goals", label: "Goals & Milestones" },
  { value: "journal", label: "Private Journal & Daily Reviews" },
  { value: "wellbeing", label: "Wellbeing & Sleep Logs" },
  { value: "budgets", label: "Monthly Budgets" },
  { value: "accounts", label: "Financial Accounts" },
];

export default function DataExplorerPage() {
  const [activeTab, setActiveTab] = useState<"explorer" | "schema">("explorer");
  const [entityType, setEntityType] = useState("transactions");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(1);

  const [recordsData, setRecordsData] = useState<any>(null);
  const [schemaData, setSchemaData] = useState<any>(null);
  const [presets, setPresets] = useState<any[]>([]);
  const [presetName, setPresetName] = useState("");
  const [hiddenColumns, setHiddenColumns] = useState<string[]>([]);
  const [inspectedRecord, setInspectedRecord] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadExplorer() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("entity_type", entityType);
      if (search.trim()) params.set("search", search.trim());
      if (category.trim()) params.set("category", category.trim());
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      params.set("sort_order", sortOrder);
      params.set("page", String(page));
      params.set("page_size", "25");

      const [recRes, presetRes] = await Promise.all([
        apiFetch(`/explorer/records?${params.toString()}`),
        apiFetch("/explorer/presets"),
      ]);
      setRecordsData(recRes);
      setPresets(presetRes || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadSchema() {
    try {
      const res = await apiFetch("/explorer/schema");
      setSchemaData(res);
    } catch (err) {
      console.error(err);
    }
  }

  useEffect(() => {
    loadExplorer();
  }, [entityType, search, category, startDate, endDate, sortOrder, page]);

  useEffect(() => {
    loadSchema();
  }, []);

  async function handleSavePreset() {
    if (!presetName.trim()) return;
    try {
      await apiFetch("/explorer/presets", {
        method: "POST",
        body: JSON.stringify({
          name: presetName.trim(),
          entity_type: entityType,
          filters: { search, category, startDate, endDate, sortOrder },
        }),
      });
      setPresetName("");
      await loadExplorer();
    } catch (err: any) {
      alert(err.message || "Failed to save preset");
    }
  }

  function applyPreset(p: any) {
    setEntityType(p.entity_type);
    setSearch(p.filters?.search || "");
    setCategory(p.filters?.category || "");
    setStartDate(p.filters?.startDate || "");
    setEndDate(p.filters?.endDate || "");
    setSortOrder(p.filters?.sortOrder || "desc");
    setPage(1);
  }

  async function handleDeletePreset(id: string) {
    try {
      await apiFetch(`/explorer/presets/${id}`, { method: "DELETE" });
      await loadExplorer();
    } catch (err) {
      console.error(err);
    }
  }

  function exportFilteredJson() {
    if (!recordsData?.items) return;
    const blob = new Blob([JSON.stringify(recordsData.items, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `explorer_${entityType}_export.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const allColumns: string[] = (recordsData?.columns || []).filter(
    (c: string) => c !== "_relationships"
  );
  const visibleColumns = allColumns.filter((c) => !hiddenColumns.includes(c));

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Personal Data Explorer & Schema Browser
          </h1>
          <p className="text-sm text-muted-foreground">
            Inspect canonical database records, relationships, and normalized SQLite schema definitions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("explorer")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold ${
              activeTab === "explorer"
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-card text-muted-foreground"
            }`}
          >
            <Table className="h-3.5 w-3.5" />
            Record Explorer
          </button>
          <button
            onClick={() => setActiveTab("schema")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold ${
              activeTab === "schema"
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-card text-muted-foreground"
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            Schema Browser ({schemaData?.entities?.length || 0} tables)
          </button>
        </div>
      </div>

      {activeTab === "explorer" ? (
        <>
          {/* Filter & Preset Controls */}
          <div className="rounded-xl border border-border bg-card p-4 space-y-3 text-xs">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
              <select
                value={entityType}
                onChange={(e) => {
                  setEntityType(e.target.value);
                  setHiddenColumns([]);
                  setPage(1);
                }}
                className="rounded-lg border border-border bg-background px-3 py-2 font-semibold sm:col-span-2"
              >
                {ENTITY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>

              <div className="relative sm:col-span-2">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Full-text filter..."
                  className="w-full rounded-lg border border-border bg-background pl-8 pr-3 py-2"
                />
              </div>

              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-2"
              />
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-2"
              />
            </div>

            {/* Saved Presets & Export */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-3">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  placeholder="Save current filter preset..."
                  className="rounded-lg border border-border bg-background px-2.5 py-1.5"
                />
                <button
                  onClick={handleSavePreset}
                  className="inline-flex items-center gap-1 rounded-lg bg-secondary px-2.5 py-1.5 font-medium hover:bg-secondary/80"
                >
                  <BookmarkPlus className="h-3.5 w-3.5" />
                  Save Preset
                </button>
                {presets.map((p) => (
                  <div
                    key={p.id}
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2.5 py-1"
                  >
                    <button
                      onClick={() => applyPreset(p)}
                      className="font-medium text-primary hover:underline"
                    >
                      {p.name}
                    </button>
                    <button
                      onClick={() => handleDeletePreset(p.id)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={exportFilteredJson}
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-3 py-1.5 font-medium hover:bg-secondary"
                >
                  <Download className="h-3.5 w-3.5" />
                  Export JSON
                </button>
                <a
                  href={`/api/v1/export?format=csv&domain=${entityType}`}
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-3 py-1.5 font-medium hover:bg-secondary"
                >
                  <Download className="h-3.5 w-3.5" />
                  Export CSV
                </a>
              </div>
            </div>

            {/* Column Visibility Toggles */}
            {allColumns.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[11px] text-muted-foreground mr-1">Columns:</span>
                {allColumns.slice(0, 12).map((col) => {
                  const isVisible = !hiddenColumns.includes(col);
                  return (
                    <button
                      key={col}
                      onClick={() =>
                        setHiddenColumns((prev) =>
                          prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
                        )
                      }
                      className={`rounded px-2 py-0.5 text-[10px] font-mono ${
                        isVisible
                          ? "bg-primary/15 text-primary"
                          : "bg-secondary text-muted-foreground line-through"
                      }`}
                    >
                      {col}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Records Table */}
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Total matching records: <strong>{recordsData?.total || 0}</strong>
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded border border-border px-2 py-1 disabled:opacity-40"
                >
                  Prev
                </button>
                <span>
                  Page {recordsData?.page || 1} of {recordsData?.total_pages || 1}
                </span>
                <button
                  disabled={page >= (recordsData?.total_pages || 1)}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded border border-border px-2 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>

            {loading ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                Querying local SQLite records...
              </div>
            ) : (recordsData?.items || []).length === 0 ? (
              <div className="rounded-lg border border-dashed border-border py-12 text-center text-xs text-muted-foreground">
                No records found for {entityType}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      {visibleColumns.slice(0, 7).map((col) => (
                        <th key={col} className="pb-2.5 pr-4 font-mono font-medium">
                          {col}
                        </th>
                      ))}
                      <th className="pb-2.5 text-right font-medium">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {recordsData.items.map((row: any, i: number) => (
                      <tr key={row.id || i} className="hover:bg-secondary/30">
                        {visibleColumns.slice(0, 7).map((col) => (
                          <td key={col} className="py-2.5 pr-4 max-w-[200px] truncate">
                            {typeof row[col] === "object"
                              ? JSON.stringify(row[col])
                              : String(row[col] ?? "—")}
                          </td>
                        ))}
                        <td className="py-2.5 text-right">
                          <button
                            onClick={() => setInspectedRecord(row)}
                            className="inline-flex items-center gap-1 rounded bg-primary/15 px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/25"
                          >
                            <Eye className="h-3 w-3" />
                            JSON
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Schema Browser Tab */
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {(schemaData?.entities || []).map((ent: any) => (
            <div key={ent.table_name} className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between border-b border-border pb-2.5">
                <div>
                  <h3 className="text-sm font-bold">{ent.entity}</h3>
                  <p className="font-mono text-[11px] text-primary">Table: {ent.table_name}</p>
                </div>
                <span className="rounded bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                  {ent.columns.length} columns
                </span>
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="text-muted-foreground">
                      <th className="pb-1.5 font-medium">Column</th>
                      <th className="pb-1.5 font-medium">Type</th>
                      <th className="pb-1.5 font-medium">Constraints & FKs</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {ent.columns.map((c: any) => (
                      <tr key={c.name}>
                        <td className="py-1.5 font-semibold text-foreground">{c.name}</td>
                        <td className="py-1.5 text-muted-foreground">{c.type}</td>
                        <td className="py-1.5 text-[10px] text-muted-foreground">
                          {c.primary_key ? "PK " : ""}
                          {c.indexed ? "INDEX " : ""}
                          {!c.nullable ? "NOT NULL " : ""}
                          {(c.foreign_keys || []).length > 0
                            ? `→ ${c.foreign_keys.join(", ")}`
                            : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Record JSON Inspector Modal */}
      {inspectedRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-border bg-card p-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-base font-bold">Canonical Record Inspector</h3>
              <button
                onClick={() => setInspectedRecord(null)}
                className="rounded p-1 text-muted-foreground hover:bg-secondary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {(inspectedRecord._relationships || []).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {inspectedRecord._relationships.map((rel: string, i: number) => (
                  <span
                    key={i}
                    className="rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary"
                  >
                    {rel}
                  </span>
                ))}
              </div>
            )}
            <pre className="mt-4 overflow-x-auto rounded-lg border border-border bg-[#0b0d13] p-4 font-mono text-xs text-gray-200">
              {JSON.stringify(inspectedRecord, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

