"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Settings,
  Save,
  HardDriveDownload,
  RotateCcw,
  Trash2,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";

export default function SettingsPage() {
  const [profile, setProfile] = useState<any>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Preferences state
  const [displayName, setDisplayName] = useState("");
  const [preferredName, setPreferredName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [baseCurrency, setBaseCurrency] = useState("INR");
  const [theme, setTheme] = useState("dark");
  const [screenTarget, setScreenTarget] = useState(240);
  const [focusDuration, setFocusDuration] = useState(50);
  const [budgetThreshold, setBudgetThreshold] = useState(85);
  const [todayIntention, setTodayIntention] = useState("");

  // Backup label
  const [backupLabel, setBackupLabel] = useState("manual_snapshot");

  async function loadSettings() {
    setLoading(true);
    try {
      const [meRes, bkpRes] = await Promise.all([
        apiFetch("/me"),
        apiFetch("/backups"),
      ]);
      setProfile(meRes);
      setBackups(bkpRes?.backups || []);
      if (meRes) {
        setDisplayName(meRes.display_name || "");
        const p = meRes.preferences || {};
        setPreferredName(p.preferred_name || "");
        setTimezone(p.timezone || "Asia/Kolkata");
        setBaseCurrency(p.base_currency || "INR");
        setTheme(p.theme || "dark");
        setScreenTarget(p.daily_screen_time_target_minutes ?? 240);
        setFocusDuration(p.focus_session_duration_minutes ?? 50);
        setBudgetThreshold(p.budget_alert_threshold_percent ?? 85);
        setTodayIntention(p.today_intention || "");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

  async function handleSavePreferences(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setStatusMsg(null);
    try {
      await apiFetch("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          display_name: displayName.trim(),
          preferred_name: preferredName.trim(),
          timezone,
          base_currency: baseCurrency.toUpperCase(),
          theme,
          daily_screen_time_target_minutes: Number(screenTarget),
          focus_session_duration_minutes: Number(focusDuration),
          budget_alert_threshold_percent: Number(budgetThreshold),
          today_intention: todayIntention.trim() || null,
        }),
      });
      if (typeof document !== "undefined") {
        document.documentElement.classList.toggle("light", theme === "light");
        document.documentElement.classList.toggle("dark", theme !== "light");
      }
      setStatusMsg("Preferences saved to local SQLite database.");
      await loadSettings();
    } catch (err: any) {
      alert(err.message || "Failed to update settings");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateBackup() {
    try {
      await apiFetch(`/backups?label=${encodeURIComponent(backupLabel || "manual")}`, {
        method: "POST",
      });
      setStatusMsg("Consistent SQLite online backup + SHA-256 manifest created.");
      await loadSettings();
    } catch (err: any) {
      alert(err.message || "Backup creation failed");
    }
  }

  async function handleRestoreBackup(filename: string) {
    if (
      !confirm(
        `Restore database from '${filename}'? An automatic pre-restore safety snapshot will be created first.`
      )
    )
      return;
    try {
      const res = await apiFetch("/backups/restore", {
        method: "POST",
        body: JSON.stringify({
          backup_filename: filename,
          confirm_overwrite: true,
        }),
      });
      setStatusMsg(
        `Restored from ${res.restored_from}. Safety backup saved as ${res.pre_restore_safety_backup}.`
      );
      await loadSettings();
    } catch (err: any) {
      alert(err.message || "Failed to restore backup");
    }
  }

  async function handleResetAllRecords() {
    if (
      !confirm(
        "Are you sure you want to permanently delete all personal activity, habit, finance, journal, and wellbeing records? Your account & preferences will be preserved."
      )
    )
      return;
    try {
      await apiFetch("/data/records?confirm=true", { method: "DELETE" });
      setStatusMsg("All personal domain records have been cleared.");
      await loadSettings();
    } catch (err: any) {
      alert(err.message || "Failed to clear records");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings, Personalization & Backups</h1>
        <p className="text-sm text-muted-foreground">
          Configure timezone, currency, targets, theme, and manage verified SQLite database backups
        </p>
      </div>

      {statusMsg && (
        <div className="rounded-xl border border-accent/40 bg-accent/10 p-3.5 text-xs font-medium text-accent">
          {statusMsg}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Profile & Personalization Form */}
        <form
          onSubmit={handleSavePreferences}
          className="rounded-xl border border-border bg-card p-5 space-y-4 text-xs"
        >
          <div className="flex items-center gap-2 text-sm font-bold">
            <Settings className="h-4 w-4 text-primary" />
            <span>Personal Profile & Regional Preferences</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block font-medium">Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Preferred Greeting Name</label>
              <input
                type="text"
                value={preferredName}
                onChange={(e) => setPreferredName(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block font-medium">Timezone</label>
              <input
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Base Currency</label>
              <input
                type="text"
                value={baseCurrency}
                onChange={(e) => setBaseCurrency(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 uppercase"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Theme</label>
              <select
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              >
                <option value="dark">Deep Charcoal (Dark)</option>
                <option value="light">Clean Daylight (Light)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block font-medium">Screen-Time Target (m)</label>
              <input
                type="number"
                min={30}
                max={1440}
                value={screenTarget}
                onChange={(e) => setScreenTarget(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Default Focus Block (m)</label>
              <input
                type="number"
                min={5}
                max={300}
                value={focusDuration}
                onChange={(e) => setFocusDuration(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
            <div>
              <label className="mb-1 block font-medium">Budget Alert (%)</label>
              <input
                type="number"
                min={10}
                max={100}
                value={budgetThreshold}
                onChange={(e) => setBudgetThreshold(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block font-medium">Today&apos;s Primary Intention</label>
            <input
              type="text"
              value={todayIntention}
              onChange={(e) => setTodayIntention(e.target.value)}
              placeholder="Displayed at the top of your Overview Dashboard..."
              className="w-full rounded-lg border border-border bg-background px-3 py-2"
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground hover:opacity-90"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? "Saving..." : "Save Preferences"}
          </button>
        </form>

        {/* SQLite Backup & Validated Restore Center */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4 text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold">
              <ShieldCheck className="h-4 w-4 text-accent" />
              <span>SQLite Online Backup & Validated Restore</span>
            </div>
            <a
              href="/api/v1/export?format=json"
              className="rounded-lg border border-border px-2.5 py-1 text-[11px] hover:bg-secondary"
            >
              Download Full JSON Snapshot
            </a>
          </div>

          <p className="text-muted-foreground">
            Backups use the native SQLite online backup API (safe with WAL mode) and generate a companion{" "}
            <code>.manifest.json</code> with SHA-256 checksums and <code>PRAGMA integrity_check</code> verification.
          </p>

          <div className="flex gap-2">
            <input
              type="text"
              value={backupLabel}
              onChange={(e) => setBackupLabel(e.target.value)}
              placeholder="Backup label..."
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2"
            />
            <button
              onClick={handleCreateBackup}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 font-semibold text-primary-foreground"
            >
              <HardDriveDownload className="h-3.5 w-3.5" />
              Create Backup
            </button>
          </div>

          <div className="max-h-60 space-y-2 overflow-y-auto pr-1">
            {backups.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border py-8 text-center text-muted-foreground">
                No local database backups created yet.
              </div>
            ) : (
              backups.map((b) => (
                <div
                  key={b.backup_filename}
                  className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/20 p-3"
                >
                  <div>
                    <div className="font-mono font-semibold">{b.backup_filename}</div>
                    <div className="mt-0.5 text-[10px] text-muted-foreground">
                      Created: {formatDate(b.created_at)} · Size:{" "}
                      {Math.round((b.size_bytes || 0) / 1024)} KB · SHA-256:{" "}
                      {(b.sha256 || "").slice(0, 12)}...
                    </div>
                  </div>
                  <button
                    onClick={() => handleRestoreBackup(b.backup_filename)}
                    className="inline-flex items-center gap-1 rounded-lg border border-primary/40 bg-primary/15 px-2.5 py-1.5 font-semibold text-primary hover:bg-primary/25"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Restore
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Danger Zone */}
          <div className="border-t border-border/60 pt-4">
            <div className="flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/10 p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                <div>
                  <div className="font-bold text-destructive">Reset Personal Domain Records</div>
                  <div className="text-[11px] text-muted-foreground">
                    Deletes all logged habits, transactions, sessions, and journal entries while keeping your user account.
                  </div>
                </div>
              </div>
              <button
                onClick={handleResetAllRecords}
                className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-destructive px-3 py-1.5 font-semibold text-destructive-foreground"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear Data
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

