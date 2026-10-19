"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Award,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Command,
  Compass,
  Database,
  HeartPulse,
  History,
  KeyRound,
  LayoutDashboard,
  Lightbulb,
  LogOut,
  Menu,
  MonitorSmartphone,
  Moon,
  Network,
  Pause,
  Play,
  Plus,
  Search,
  Settings,
  Sparkles,
  Square,
  Sun,
  Target,
  Wallet,
  X,
} from "lucide-react";
import { apiFetch, setStoredToken } from "@/lib/api";
import { cn, formatSecondsClock, todayIso } from "@/lib/utils";

export interface UserPreferences {
  preferred_name: string;
  timezone: string;
  base_currency: string;
  date_format: string;
  number_format: string;
  week_start_day: string;
  theme: "dark" | "light";
  daily_screen_time_target_minutes: number;
  focus_session_duration_minutes: number;
  break_duration_minutes: number;
  break_reminders_enabled: boolean;
  habit_reminders_enabled: boolean;
  budget_alert_threshold_percent: number;
  dashboard_widgets: string[];
  external_integrations_enabled: boolean;
  today_intention?: string | null;
  today_intention_date?: string | null;
}

export interface UserProfile {
  id: string;
  username: string;
  display_name: string;
  email?: string | null;
  bio?: string | null;
  created_at: string;
  preferences: UserPreferences;
}

export interface ActiveTimer {
  id: string;
  activity_name: string;
  category: string;
  project?: string | null;
  start_time: string;
  elapsed_seconds: number;
  timer_status: "running" | "paused" | "completed";
  last_resumed_at?: string | null;
  planned_duration_minutes?: number | null;
}

interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  type: "success" | "warning" | "error" | "info";
}

interface AppContextValue {
  user: UserProfile | null;
  refreshUser: () => Promise<void>;
  activeTimer: ActiveTimer | null;
  liveTimerSeconds: number;
  refreshTimer: () => Promise<void>;
  notify: (
    title: string,
    description?: string,
    type?: "success" | "warning" | "error" | "info"
  ) => void;
  openQuickAdd: (tab?: "expense" | "habit" | "focus" | "screen" | "wellbeing") => void;
  openCommandPalette: () => void;
  dataVersion: number;
  triggerRefresh: () => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppShell");
  return ctx;
}

export const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, group: "Core" },
  { href: "/habits", label: "Habits", icon: CheckCircle2, group: "Core" },
  { href: "/finance", label: "Finance", icon: Wallet, group: "Core" },
  { href: "/screen-time", label: "Screen Time", icon: MonitorSmartphone, group: "Core" },
  { href: "/activities", label: "Time & Activities", icon: Clock, group: "Core" },
  { href: "/health", label: "Health & Energy", icon: HeartPulse, group: "Core" },
  { href: "/goals", label: "Goals & Projects", icon: Target, group: "Core" },
  { href: "/journal", label: "Journal", icon: BookOpen, group: "Core" },
  { href: "/insights", label: "Insights", icon: Lightbulb, group: "Intelligence" },
  { href: "/timeline", label: "Personal Timeline", icon: History, group: "Intelligence" },
  {
    href: "/constellation",
    label: "Data Constellation",
    icon: Network,
    group: "Intelligence",
  },
  { href: "/rhythm", label: "Personal Rhythm", icon: CalendarClock, group: "Intelligence" },
  { href: "/wrapped", label: "Life Wrapped", icon: Award, group: "Intelligence" },
  { href: "/explorer", label: "Data Explorer", icon: Database, group: "Platform" },
  { href: "/api-console", label: "API & Integrations", icon: KeyRound, group: "Platform" },
  { href: "/settings", label: "Settings", icon: Settings, group: "Platform" },
];

function LiveHeaderClock() {
  const [timeStr, setTimeStr] = useState("");
  useEffect(() => {
    const update = () => {
      setTimeStr(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="font-mono text-[11px] bg-card border border-border px-2 py-0.5 rounded">
      {timeStr}
    </span>
  );
}

function prefetchRouteData(href: string) {
  switch (href) {
    case "/":
      apiFetch("/dashboard").catch(() => {});
      break;
    case "/habits":
      apiFetch("/habits?include_archived=false").catch(() => {});
      break;
    case "/finance":
      apiFetch("/finance/summary").catch(() => {});
      apiFetch("/transactions?limit=150").catch(() => {});
      break;
    case "/screen-time":
      apiFetch("/screen-time/summary").catch(() => {});
      apiFetch("/screen-time?limit=150").catch(() => {});
      break;
    case "/activities":
      apiFetch("/activities").catch(() => {});
      apiFetch("/activities/summary").catch(() => {});
      break;
    case "/health":
      apiFetch("/wellbeing").catch(() => {});
      apiFetch("/wellbeing/summary").catch(() => {});
      break;
    case "/goals":
      apiFetch("/goals").catch(() => {});
      break;
    case "/journal":
      apiFetch("/journal?").catch(() => {});
      break;
    case "/insights":
      apiFetch("/insights?include_dismissed=false").catch(() => {});
      break;
    case "/timeline":
      apiFetch("/timeline?limit=200").catch(() => {});
      break;
    case "/constellation":
      apiFetch("/constellation?").catch(() => {});
      break;
    case "/rhythm":
      apiFetch("/rhythm?compare_previous=true").catch(() => {});
      break;
  }
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const [authChecking, setAuthChecking] = useState(true);
  const [isInitialized, setIsInitialized] = useState(true);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [sidebarCompact, setSidebarCompact] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [quickAddTab, setQuickAddTab] = useState<
    "expense" | "habit" | "focus" | "screen" | "wellbeing"
  >("expense");

  const [activeTimer, setActiveTimer] = useState<ActiveTimer | null>(null);
  const [liveTimerSeconds, setLiveTimerSeconds] = useState(0);
  const [localTimeStr, setLocalTimeStr] = useState("");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [dataVersion, setDataVersion] = useState(0);

  // Auth form states
  const [authUsername, setAuthUsername] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authCurrency, setAuthCurrency] = useState("INR");
  const [authTimezone, setAuthTimezone] = useState("Asia/Kolkata");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Quick-add form states
  const [qaExpenseAmount, setQaExpenseAmount] = useState("");
  const [qaExpenseCategory, setQaExpenseCategory] = useState("Food & Dining");
  const [qaExpenseMerchant, setQaExpenseMerchant] = useState("");
  const [qaHabitName, setQaHabitName] = useState("");
  const [qaHabitCategory, setQaHabitCategory] = useState("Health");
  const [qaFocusName, setQaFocusName] = useState("");
  const [qaFocusCategory, setQaFocusCategory] = useState("Deep Work");
  const [qaFocusProject, setQaFocusProject] = useState("");
  const [qaScreenApp, setQaScreenApp] = useState("");
  const [qaScreenMinutes, setQaScreenMinutes] = useState("45");
  const [qaSleepHours, setQaSleepHours] = useState("7.5");
  const [qaMood, setQaMood] = useState("8");
  const [qaEnergy, setQaEnergy] = useState("8");
  const [qaSubmitting, setQaSubmitting] = useState(false);

  const notify = useCallback(
    (
      title: string,
      description?: string,
      type: "success" | "warning" | "error" | "info" = "info"
    ) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((prev) => [...prev, { id, title, description, type }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4500);
    },
    []
  );

  const triggerRefresh = useCallback(() => {
    setDataVersion((v) => v + 1);
  }, []);

  const applyTheme = useCallback((theme: "dark" | "light") => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    root.classList.remove("dark", "light");
    root.classList.add(theme);
  }, []);

  const refreshTimer = useCallback(async () => {
    try {
      const res = await apiFetch<{ active_timer: ActiveTimer | null }>(
        "/activities/timer/active"
      );
      setActiveTimer(res.active_timer);
      if (res.active_timer) {
        setLiveTimerSeconds(res.active_timer.elapsed_seconds);
      } else {
        setLiveTimerSeconds(0);
      }
    } catch {
      // Ignore if unauthenticated
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const statusRes = await apiFetch<{ is_initialized: boolean }>("/auth/status");
      setIsInitialized(statusRes.is_initialized);
      if (!statusRes.is_initialized) {
        setUser(null);
        setAuthChecking(false);
        return;
      }
      const me = await apiFetch<UserProfile>("/me");
      setUser(me);
      applyTheme(me.preferences.theme || "dark");
      await refreshTimer();
    } catch {
      setUser(null);
    } finally {
      setAuthChecking(false);
    }
  }, [applyTheme, refreshTimer]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // Only tick liveTimerSeconds when an active timer is actually running
  useEffect(() => {
    if (!activeTimer || activeTimer.timer_status !== "running") return;
    const interval = setInterval(() => {
      setLiveTimerSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [activeTimer]);

  // Global keyboard shortcut: Cmd/Ctrl + K for Command Palette
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        setCommandOpen(false);
        setQuickAddOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleToggleTheme = async () => {
    if (!user) return;
    const nextTheme = user.preferences.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    try {
      const updated = await apiFetch<UserProfile>("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ theme: nextTheme }),
      });
      setUser(updated);
      notify(`Switched to ${nextTheme} theme`, undefined, "info");
    } catch (err: any) {
      notify("Failed to save theme preference", err.message, "error");
    }
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSubmitting(true);
    try {
      if (!isInitialized) {
        const res = await apiFetch<{ access_token: string; user: UserProfile }>(
          "/auth/setup",
          {
            method: "POST",
            body: JSON.stringify({
              username: authUsername,
              display_name: authDisplayName || authUsername,
              password: authPassword,
              preferred_name: authDisplayName || authUsername,
              base_currency: authCurrency,
              timezone: authTimezone,
              theme: "dark",
            }),
          }
        );
        setStoredToken(res.access_token);
        setUser(res.user);
        setIsInitialized(true);
        applyTheme(res.user.preferences.theme);
        notify("Welcome to Personal Life OS", "Your local database is initialized.", "success");
      } else {
        const res = await apiFetch<{ access_token: string; user: UserProfile }>(
          "/auth/login",
          {
            method: "POST",
            body: JSON.stringify({
              username: authUsername,
              password: authPassword,
            }),
          }
        );
        setStoredToken(res.access_token);
        setUser(res.user);
        applyTheme(res.user.preferences.theme);
        await refreshTimer();
        notify(`Welcome back, ${res.user.preferences.preferred_name}`, undefined, "success");
      }
    } catch (err: any) {
      setAuthError(err.message || "Authentication failed");
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }
    setStoredToken(null);
    setUser(null);
  };

  const handleTimerAction = async (action: "pause" | "resume" | "stop") => {
    if (!activeTimer) return;
    try {
      await apiFetch(`/activities/timer/${action}?session_id=${activeTimer.id}`, {
        method: "POST",
      });
      await refreshTimer();
      triggerRefresh();
      notify(
        action === "stop"
          ? "Focus session completed and saved"
          : `Timer ${action === "pause" ? "paused" : "resumed"}`,
        activeTimer.activity_name,
        "success"
      );
    } catch (err: any) {
      notify("Timer action failed", err.message, "error");
    }
  };

  const handleQuickAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setQaSubmitting(true);
    try {
      if (quickAddTab === "expense") {
        const res = await apiFetch("/transactions", {
          method: "POST",
          body: JSON.stringify({
            amount: qaExpenseAmount,
            currency: user?.preferences.base_currency || "INR",
            transaction_type: "expense",
            category: qaExpenseCategory,
            merchant: qaExpenseMerchant || undefined,
            transaction_date: todayIso(),
          }),
        });
        notify(
          "Expense recorded",
          `${res.currency} ${res.amount} in ${res.category}`,
          "success"
        );
        setQaExpenseAmount("");
        setQaExpenseMerchant("");
      } else if (quickAddTab === "habit") {
        const res = await apiFetch("/habits", {
          method: "POST",
          body: JSON.stringify({
            name: qaHabitName,
            category: qaHabitCategory,
            frequency_type: "daily",
            selected_weekdays: [0, 1, 2, 3, 4, 5, 6],
            start_date: todayIso(),
          }),
        });
        notify("Habit created", res.name, "success");
        setQaHabitName("");
      } else if (quickAddTab === "focus") {
        await apiFetch("/activities/timer/start", {
          method: "POST",
          body: JSON.stringify({
            activity_name: qaFocusName,
            category: qaFocusCategory,
            project: qaFocusProject || undefined,
            planned_duration_minutes:
              user?.preferences.focus_session_duration_minutes || 50,
            is_focus_session: true,
          }),
        });
        await refreshTimer();
        notify("Focus timer started", qaFocusName, "success");
        setQaFocusName("");
      } else if (quickAddTab === "screen") {
        await apiFetch("/screen-time", {
          method: "POST",
          body: JSON.stringify({
            app_name: qaScreenApp,
            device: "desktop",
            session_date: todayIso(),
            duration_minutes: parseInt(qaScreenMinutes, 10) || 30,
          }),
        });
        notify("Screen-time session logged", `${qaScreenApp} (${qaScreenMinutes}m)`, "success");
        setQaScreenApp("");
      } else if (quickAddTab === "wellbeing") {
        await apiFetch("/wellbeing", {
          method: "POST",
          body: JSON.stringify({
            record_date: todayIso(),
            sleep_duration_hours: qaSleepHours,
            mood_score: parseInt(qaMood, 10),
            energy_score: parseInt(qaEnergy, 10),
          }),
        });
        notify("Daily wellbeing logged", `Sleep: ${qaSleepHours}h · Energy: ${qaEnergy}/10`, "success");
      }
      setQuickAddOpen(false);
      triggerRefresh();
    } catch (err: any) {
      notify("Quick action failed", err.message, "error");
    } finally {
      setQaSubmitting(false);
    }
  };

  const openQuickAdd = useCallback(
    (tab: "expense" | "habit" | "focus" | "screen" | "wellbeing" = "expense") => {
      setQuickAddTab(tab);
      setQuickAddOpen(true);
    },
    []
  );

  const openCommandPalette = useCallback(() => {
    setCommandOpen(true);
  }, []);

  const commandActions = useMemo(
    () => [
      {
        id: "qa-expense",
        label: "Quick Action: Record an Expense",
        group: "Actions",
        onSelect: () => {
          setCommandOpen(false);
          openQuickAdd("expense");
        },
      },
      {
        id: "qa-focus",
        label: "Quick Action: Start a Focus Timer",
        group: "Actions",
        onSelect: () => {
          setCommandOpen(false);
          openQuickAdd("focus");
        },
      },
      {
        id: "qa-habit",
        label: "Quick Action: Create a New Habit",
        group: "Actions",
        onSelect: () => {
          setCommandOpen(false);
          openQuickAdd("habit");
        },
      },
      {
        id: "qa-screen",
        label: "Quick Action: Log Screen-Time Session",
        group: "Actions",
        onSelect: () => {
          setCommandOpen(false);
          openQuickAdd("screen");
        },
      },
      {
        id: "qa-wellbeing",
        label: "Quick Action: Log Today's Sleep, Mood & Energy",
        group: "Actions",
        onSelect: () => {
          setCommandOpen(false);
          openQuickAdd("wellbeing");
        },
      },
      ...NAV_ITEMS.map((item) => ({
        id: `nav-${item.href}`,
        label: `Go to ${item.label}`,
        group: "Navigation",
        onSelect: () => {
          setCommandOpen(false);
          router.push(item.href);
        },
      })),
    ],
    [openQuickAdd, router]
  );

  const filteredCommands = useMemo(() => {
    if (!commandQuery.trim()) return commandActions;
    const q = commandQuery.toLowerCase();
    return commandActions.filter(
      (c) => c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q)
    );
  }, [commandActions, commandQuery]);

  if (authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-accent-violet/20 border border-accent-violet/40 flex items-center justify-center animate-pulse">
            <Compass className="h-5 w-5 text-accent-violet" />
          </div>
          <p className="text-sm text-muted">Loading Personal Life OS...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground p-4">
        <div className="w-full max-w-md rounded-2xl bg-card border border-border p-8 shadow-2xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="h-11 w-11 rounded-xl bg-accent-violet/15 border border-accent-violet/40 flex items-center justify-center">
              <Compass className="h-6 w-6 text-accent-violet" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Personal Life OS</h1>
              <p className="text-xs text-muted">
                {isInitialized
                  ? "Local-First Personal Analytics & API Command Center"
                  : "First-Run Local Workspace Initialization"}
              </p>
            </div>
          </div>

          {!isInitialized && (
            <div className="mb-5 rounded-xl bg-accent-violet/10 border border-accent-violet/30 p-3.5 text-xs text-muted leading-relaxed">
              <strong className="text-foreground block mb-1">
                100% Local, Free & Private
              </strong>
              Create your local owner account to initialize the SQLite database in{" "}
              <code className="text-accent-violet">data/personal_life_os.db</code>. No cloud
              account or external API key is ever required.
            </div>
          )}

          {authError && (
            <div className="mb-4 rounded-lg bg-accent-danger/15 border border-accent-danger/40 p-3 text-xs text-accent-danger">
              {authError}
            </div>
          )}

          <form onSubmit={handleAuthSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">
                Username
              </label>
              <input
                type="text"
                required
                value={authUsername}
                onChange={(e) => setAuthUsername(e.target.value)}
                placeholder="e.g. arjun"
                className="w-full rounded-lg bg-surface border border-border px-3.5 py-2 text-sm text-foreground focus:border-accent-violet outline-none"
              />
            </div>

            {!isInitialized && (
              <>
                <div>
                  <label className="block text-xs font-medium text-muted mb-1.5">
                    Preferred Display Name
                  </label>
                  <input
                    type="text"
                    required
                    value={authDisplayName}
                    onChange={(e) => setAuthDisplayName(e.target.value)}
                    placeholder="How should the dashboard greet you?"
                    className="w-full rounded-lg bg-surface border border-border px-3.5 py-2 text-sm text-foreground focus:border-accent-violet outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-muted mb-1.5">
                      Base Currency
                    </label>
                    <select
                      value={authCurrency}
                      onChange={(e) => setAuthCurrency(e.target.value)}
                      className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm text-foreground"
                    >
                      <option value="INR">INR (₹)</option>
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted mb-1.5">
                      Local Timezone
                    </label>
                    <input
                      type="text"
                      value={authTimezone}
                      onChange={(e) => setAuthTimezone(e.target.value)}
                      className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm text-foreground"
                    />
                  </div>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">
                Password (min 8 characters)
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-lg bg-surface border border-border px-3.5 py-2 text-sm text-foreground focus:border-accent-violet outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={authSubmitting}
              className="w-full rounded-lg bg-accent-violet hover:bg-accent-violet/90 text-white font-medium py-2.5 text-sm transition disabled:opacity-50"
            >
              {authSubmitting
                ? "Initializing..."
                : isInitialized
                ? "Unlock Personal Life OS"
                : "Initialize Local Account"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const todayFormatted = new Date().toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <AppContext.Provider
      value={{
        user,
        refreshUser,
        activeTimer,
        liveTimerSeconds,
        refreshTimer,
        notify,
        openQuickAdd,
        openCommandPalette,
        dataVersion,
        triggerRefresh,
      }}
    >
      <div className="min-h-screen flex bg-background text-foreground">
        {/* Desktop Persistent Sidebar */}
        <aside
          className={cn(
            "no-print hidden lg:flex flex-col border-r border-border bg-surface transition-all duration-200 shrink-0 select-none",
            sidebarCompact ? "w-20" : "w-64"
          )}
        >
          <div className="h-16 flex items-center justify-between px-4 border-b border-border">
            <Link href="/" className="flex items-center gap-3 overflow-hidden">
              <div className="h-9 w-9 rounded-xl bg-accent-violet/15 border border-accent-violet/40 flex items-center justify-center shrink-0">
                <Compass className="h-5 w-5 text-accent-violet" />
              </div>
              {!sidebarCompact && (
                <div className="truncate">
                  <span className="font-semibold text-sm tracking-tight block">
                    Personal Life OS
                  </span>
                  <span className="text-[11px] text-muted block">Local Command Center</span>
                </div>
              )}
            </Link>
            <button
              onClick={() => setSidebarCompact((c) => !c)}
              title={sidebarCompact ? "Expand sidebar" : "Compact sidebar"}
              className="p-1.5 rounded-lg text-muted hover:text-foreground hover:bg-card"
            >
              {sidebarCompact ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronLeft className="h-4 w-4" />
              )}
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto py-3 px-2.5 space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  prefetch={true}
                  onMouseEnter={() => prefetchRouteData(item.href)}
                  title={sidebarCompact ? item.label : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-accent-violet/15 text-accent-violet border border-accent-violet/30"
                      : "text-muted hover:text-foreground hover:bg-card"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!sidebarCompact && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </nav>

          <div className="p-3 border-t border-border">
            {!sidebarCompact ? (
              <div className="flex items-center justify-between text-xs text-muted">
                <div className="truncate">
                  <p className="font-medium text-foreground truncate">
                    {user.preferences.preferred_name}
                  </p>
                  <p className="text-[11px] truncate">
                    {user.preferences.base_currency} · {user.preferences.timezone}
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  title="Lock session"
                  className="p-1.5 rounded-lg hover:bg-card hover:text-foreground"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={handleLogout}
                title="Lock session"
                className="w-full flex justify-center p-1.5 rounded-lg text-muted hover:bg-card hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
              </button>
            )}
          </div>
        </aside>

        {/* Main Content Column */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Global Header */}
          <header className="no-print h-16 border-b border-border bg-surface/90 backdrop-blur sticky top-0 z-30 px-4 lg:px-6 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden p-2 rounded-lg bg-card border border-border text-muted hover:text-foreground"
                aria-label="Open navigation menu"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="hidden sm:flex items-center gap-2.5 text-xs text-muted">
                <span className="font-medium text-foreground">{todayFormatted}</span>
                <span>•</span>
                <LiveHeaderClock />
              </div>
            </div>

            {/* Active Focus Timer Pill (Persistent DB-backed) */}
            {activeTimer && (
              <div className="flex items-center gap-2.5 rounded-full bg-accent-violet/15 border border-accent-violet/40 px-3.5 py-1 text-xs">
                <span className="h-2 w-2 rounded-full bg-accent-lime animate-ping" />
                <span className="font-medium text-foreground truncate max-w-[140px]">
                  {activeTimer.activity_name}
                </span>
                <span className="font-mono font-semibold text-accent-violet">
                  {formatSecondsClock(liveTimerSeconds)}
                </span>
                {activeTimer.timer_status === "running" ? (
                  <button
                    onClick={() => handleTimerAction("pause")}
                    title="Pause timer"
                    className="p-1 rounded hover:bg-accent-violet/20 text-foreground"
                  >
                    <Pause className="h-3.5 w-3.5" />
                  </button>
                ) : (
                  <button
                    onClick={() => handleTimerAction("resume")}
                    title="Resume timer"
                    className="p-1 rounded hover:bg-accent-violet/20 text-accent-lime"
                  >
                    <Play className="h-3.5 w-3.5" />
                  </button>
                )}
                <button
                  onClick={() => handleTimerAction("stop")}
                  title="Complete & save session"
                  className="p-1 rounded hover:bg-accent-danger/20 text-accent-danger"
                >
                  <Square className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            {/* Right Controls: Command Palette, Quick Add, Theme, Settings */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCommandOpen(true)}
                className="flex items-center gap-2 rounded-lg bg-card border border-border px-3 py-1.5 text-xs text-muted hover:text-foreground transition"
              >
                <Search className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Search or jump...</span>
                <kbd className="hidden sm:inline-block rounded bg-surface px-1.5 py-0.5 font-mono text-[10px] border border-border">
                  Ctrl+K
                </kbd>
              </button>

              <button
                onClick={() => openQuickAdd("expense")}
                className="flex items-center gap-1.5 rounded-lg bg-accent-violet hover:bg-accent-violet/90 text-white px-3 py-1.5 text-xs font-medium transition shadow-sm"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Quick Add</span>
              </button>

              <button
                onClick={handleToggleTheme}
                title={`Switch to ${
                  user.preferences.theme === "dark" ? "light" : "dark"
                } theme`}
                className="p-2 rounded-lg bg-card border border-border text-muted hover:text-foreground transition"
              >
                {user.preferences.theme === "dark" ? (
                  <Sun className="h-4 w-4 text-accent-amber" />
                ) : (
                  <Moon className="h-4 w-4 text-accent-violet" />
                )}
              </button>

              <Link
                href="/settings"
                title="Settings & Preferences"
                className="p-2 rounded-lg bg-card border border-border text-muted hover:text-foreground transition"
              >
                <Settings className="h-4 w-4" />
              </Link>
            </div>
          </header>

          {/* Main View Container */}
          <main className="flex-1 p-4 lg:p-6 pb-20 lg:pb-8 max-w-[1600px] w-full mx-auto">
            {children}
          </main>

          {/* Mobile Bottom Navigation Bar */}
          <div className="no-print lg:hidden fixed bottom-0 left-0 right-0 h-14 bg-surface border-t border-border z-20 flex items-center justify-around px-2">
            {[
              NAV_ITEMS[0],
              NAV_ITEMS[1],
              NAV_ITEMS[2],
              NAV_ITEMS[4],
              NAV_ITEMS[10],
            ].map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex flex-col items-center gap-0.5 px-2 py-1 rounded-lg text-[10px] font-medium",
                    isActive ? "text-accent-violet" : "text-muted"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label.split(" ")[0]}</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Mobile Drawer */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 lg:hidden flex">
            <div
              className="fixed inset-0 bg-black/60"
              onClick={() => setMobileMenuOpen(false)}
            />
            <div className="relative w-72 max-w-[85vw] bg-surface border-r border-border h-full flex flex-col z-10">
              <div className="h-16 px-4 flex items-center justify-between border-b border-border">
                <div className="flex items-center gap-2.5">
                  <Compass className="h-5 w-5 text-accent-violet" />
                  <span className="font-semibold text-sm">Personal Life OS</span>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1.5 rounded-lg text-muted hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-1">
                {NAV_ITEMS.map((item) => {
                  const Icon = item.icon;
                  const isActive =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-xs font-medium",
                        isActive
                          ? "bg-accent-violet/15 text-accent-violet border border-accent-violet/30"
                          : "text-muted hover:text-foreground hover:bg-card"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Command Palette Modal (Ctrl+K / Cmd+K) */}
        {commandOpen && (
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4">
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-xs"
              onClick={() => setCommandOpen(false)}
            />
            <div className="relative z-10 w-full max-w-lg rounded-2xl bg-card border border-border shadow-2xl overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                <Command className="h-4 w-4 text-accent-violet" />
                <input
                  type="text"
                  autoFocus
                  value={commandQuery}
                  onChange={(e) => setCommandQuery(e.target.value)}
                  placeholder="Type a command or page name (e.g. 'expense', 'constellation', 'rhythm')..."
                  className="w-full bg-transparent text-sm text-foreground outline-none"
                />
                <button
                  onClick={() => setCommandOpen(false)}
                  className="text-xs text-muted hover:text-foreground"
                >
                  ESC
                </button>
              </div>
              <div className="max-h-80 overflow-y-auto p-2 space-y-1">
                {filteredCommands.length === 0 ? (
                  <p className="text-xs text-muted text-center py-6">
                    No matching commands or pages found.
                  </p>
                ) : (
                  filteredCommands.map((cmd) => (
                    <button
                      key={cmd.id}
                      onClick={cmd.onSelect}
                      className="w-full flex items-center justify-between rounded-lg px-3 py-2 text-left text-xs hover:bg-surface transition"
                    >
                      <span className="font-medium text-foreground">{cmd.label}</span>
                      <span className="text-[10px] uppercase tracking-wider text-muted bg-panel px-2 py-0.5 rounded">
                        {cmd.group}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Global Quick-Add Modal */}
        {quickAddOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-xs"
              onClick={() => setQuickAddOpen(false)}
            />
            <div className="relative z-10 w-full max-w-md rounded-2xl bg-card border border-border p-6 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold">Quick Log Action</h2>
                <button
                  onClick={() => setQuickAddOpen(false)}
                  className="p-1 rounded-lg text-muted hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="grid grid-cols-5 gap-1 p-1 rounded-xl bg-surface border border-border mb-5 text-xs">
                {(
                  [
                    ["expense", "Expense"],
                    ["habit", "Habit"],
                    ["focus", "Focus"],
                    ["screen", "Screen"],
                    ["wellbeing", "Health"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setQuickAddTab(key)}
                    className={cn(
                      "py-1.5 rounded-lg font-medium transition",
                      quickAddTab === key
                        ? "bg-accent-violet text-white"
                        : "text-muted hover:text-foreground"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <form onSubmit={handleQuickAddSubmit} className="space-y-4">
                {quickAddTab === "expense" && (
                  <>
                    <div>
                      <label className="block text-xs text-muted mb-1">
                        Amount ({user.preferences.base_currency})
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        value={qaExpenseAmount}
                        onChange={(e) => setQaExpenseAmount(e.target.value)}
                        placeholder="e.g. 250.00"
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted mb-1">Category</label>
                      <input
                        type="text"
                        required
                        value={qaExpenseCategory}
                        onChange={(e) => setQaExpenseCategory(e.target.value)}
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted mb-1">
                        Merchant / Recipient
                      </label>
                      <input
                        type="text"
                        value={qaExpenseMerchant}
                        onChange={(e) => setQaExpenseMerchant(e.target.value)}
                        placeholder="Optional merchant name"
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                  </>
                )}

                {quickAddTab === "habit" && (
                  <>
                    <div>
                      <label className="block text-xs text-muted mb-1">Habit Name</label>
                      <input
                        type="text"
                        required
                        value={qaHabitName}
                        onChange={(e) => setQaHabitName(e.target.value)}
                        placeholder="e.g. Morning Mobility & Hydration"
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted mb-1">Category</label>
                      <input
                        type="text"
                        required
                        value={qaHabitCategory}
                        onChange={(e) => setQaHabitCategory(e.target.value)}
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                  </>
                )}

                {quickAddTab === "focus" && (
                  <>
                    <div>
                      <label className="block text-xs text-muted mb-1">
                        Focus Session Activity
                      </label>
                      <input
                        type="text"
                        required
                        value={qaFocusName}
                        onChange={(e) => setQaFocusName(e.target.value)}
                        placeholder="What are you focusing on right now?"
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-muted mb-1">Category</label>
                        <input
                          type="text"
                          required
                          value={qaFocusCategory}
                          onChange={(e) => setQaFocusCategory(e.target.value)}
                          className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-muted mb-1">Project</label>
                        <input
                          type="text"
                          value={qaFocusProject}
                          onChange={(e) => setQaFocusProject(e.target.value)}
                          placeholder="Optional"
                          className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  </>
                )}

                {quickAddTab === "screen" && (
                  <>
                    <div>
                      <label className="block text-xs text-muted mb-1">
                        Application or Website
                      </label>
                      <input
                        type="text"
                        required
                        value={qaScreenApp}
                        onChange={(e) => setQaScreenApp(e.target.value)}
                        placeholder="e.g. VS Code, YouTube, Browser"
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-muted mb-1">
                        Duration (Minutes)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="1440"
                        required
                        value={qaScreenMinutes}
                        onChange={(e) => setQaScreenMinutes(e.target.value)}
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                  </>
                )}

                {quickAddTab === "wellbeing" && (
                  <>
                    <div>
                      <label className="block text-xs text-muted mb-1">
                        Sleep Duration (Hours)
                      </label>
                      <input
                        type="number"
                        step="0.25"
                        min="0"
                        max="24"
                        required
                        value={qaSleepHours}
                        onChange={(e) => setQaSleepHours(e.target.value)}
                        className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-muted mb-1">
                          Mood Score (1–10)
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          required
                          value={qaMood}
                          onChange={(e) => setQaMood(e.target.value)}
                          className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-muted mb-1">
                          Energy Score (1–10)
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          required
                          value={qaEnergy}
                          onChange={(e) => setQaEnergy(e.target.value)}
                          className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  </>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setQuickAddOpen(false)}
                    className="rounded-lg bg-surface border border-border px-4 py-2 text-xs font-medium text-muted hover:text-foreground"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={qaSubmitting}
                    className="rounded-lg bg-accent-violet hover:bg-accent-violet/90 text-white px-4 py-2 text-xs font-medium"
                  >
                    {qaSubmitting ? "Saving..." : "Save Record"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Toast Notifications */}
        <div className="no-print fixed bottom-16 lg:bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={cn(
                "pointer-events-auto rounded-xl border p-3.5 shadow-xl bg-card text-xs transition-all",
                t.type === "success" && "border-accent-lime/50",
                t.type === "warning" && "border-accent-amber/50",
                t.type === "error" && "border-accent-danger/50",
                t.type === "info" && "border-accent-violet/50"
              )}
            >
              <p className="font-semibold text-foreground">{t.title}</p>
              {t.description && (
                <p className="text-muted mt-0.5 leading-relaxed">{t.description}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </AppContext.Provider>
  );
}

