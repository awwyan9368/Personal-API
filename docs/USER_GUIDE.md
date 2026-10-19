# Personal Life OS — Complete User & Feature Guide

This guide explains what every section in **Personal Life OS** (`http://localhost:3000`) does, how all 16 modules connect together, and **exactly what to enter into every "Add / Log / Create" form** with real-world examples.

---

## 0. Global Top Bar & Shortcuts (Available on Every Page)

Implemented in [`frontend/components/AppShell.tsx`](../frontend/components/AppShell.tsx).

1. **Command Palette (`Ctrl+K` / `Search or jump...`)**
   - **What it does**: Lets you jump to any of the 16 pages or trigger any Quick-Add modal from your keyboard.
   - **What to type**: Type a page name (e.g., `Finance`, `Constellation`, `Rhythm`) or an action (`Log Expense`, `Start Focus`, `Log Sleep`) and press `Enter`.
2. **`+ Quick Add` Button (Top-Right Violet Button)**
   - **What it does**: Opens a 5-tab modal from anywhere in the app so you can log records in 5 seconds without leaving your current page.
   - **What to add in each tab**:
     - **Expense tab**:
       - *Amount*: `250.00`
       - *Category*: `Food & Dining`
       - *Merchant*: `Third Wave Coffee`
     - **Habit tab**:
       - *Habit Name*: `Morning Mobility`
       - *Category*: `Health`
     - **Focus tab**:
       - *Session Title*: `API Integration Coding`
       - *Category*: `Deep Work`
       - *Project*: `Personal Life OS`
     - **Screen tab**:
       - *Application*: `VS Code` or `YouTube`
       - *Minutes*: `45`
     - **Wellbeing tab**:
       - *Sleep Hours*: `7.5`
       - *Mood (1–10)*: `8`
       - *Energy (1–10)*: `8`
3. **Live Focus Timer Pill (Top Center, appears when a timer is active)**
   - **What it does**: Shows your currently running or paused focus timer across all pages, counting up every second from the SQLite database timestamp.
   - **Controls**: Click **Pause**, **Resume**, or **Stop (Save)** directly from the header.

---

## 1. Overview (`/`)

Implemented in [`frontend/app/page.tsx`](../frontend/app/page.tsx).

- **What it does**: Your daily command center. Displays a time-aware greeting, **Today's Primary Intention**, 11 live domain KPI cards (with period-over-period comparisons against yesterday/last week/last month), a 14-day multi-metric chart (Focus vs Screen Time vs Sleep/Energy), and your recent cross-domain activity stream.
- **Interactive Inputs on This Page**:
  1. **Today's Intention Input / Edit**:
     - *What to enter*: A single sentence defining your main priority for the day—e.g., `"Finish backend API integration and complete 45m strength workout"`.
  2. **Local Natural-Language Query Bar (`Ask your local data...`)**:
     - *What it does*: Parses plain-English questions deterministically against your local SQLite database (zero external AI keys).
     - *Examples of what to type*:
       - `"How much did I spend on Food & Dining this month?"`
       - `"Which habits have the highest streak?"`
       - `"How many hours of focus time did I log this week?"`
       - `"What was my screen time this week?"`
       - `"Show my average sleep and energy this month"`

---

## 2. Habits (`/habits`)

Implemented in [`frontend/app/habits/page.tsx`](../frontend/app/habits/page.tsx).

- **What it does**: Tracks daily, weekday-specific, or weekly habits, calculates your **current streak**, **best streak**, **30-day completion rate**, and renders a **14-Day Completion Matrix** where you can toggle any day (including historical corrections). Unscheduled days never break your streak, and future dates are blocked.
- **Where & What to Add**:
  1. **`+ New Habit` Button**:
     - **Habit Name**: Clear action name—e.g., `"Read 30 Pages"`, `"No Sugar"`, `"Strength Training"`, or `"LeetCode / System Design"`.
     - **Category**: Group label—e.g., `"Learning"`, `"Health"`, `"Career"`, `"Mindfulness"`. (Tip: If this matches a Goal category, **Data Constellation** automatically links them!)
     - **Frequency Type**:
       - `daily`: Every day of the week.
       - `weekdays`: Select specific days (`Mon`, `Wed`, `Fri`, etc.).
       - `weekly_target`: Flexible days, e.g., `4` times per week.
     - **Quantitative Toggle (`Track numeric target`)**:
       - Leave **unchecked** for simple Yes/No habits (e.g., `"Meditate"`).
       - Check **on** for measurable habits—set **Target Value** = `30`, **Unit** = `pages` (or `8` `glasses`, `45` `minutes`).
  2. **14-Day Matrix Cells / `Complete Today` Button**:
     - Click any cell in a habit's row to mark that date completed or uncompleted.
  3. **`Log Custom Value / Backfill` Action**:
     - Use this when you want to log partial progress (e.g., `15` out of `30` pages) or add a note for a past date.

---

## 3. Finance (`/finance`)

Implemented in [`frontend/app/finance/page.tsx`](../frontend/app/finance/page.tsx).

- **What it does**: Manages your personal cash flow using exact `Decimal` arithmetic (`INR` default). Separates **Expenses**, **Income**, and **Account-to-Account Transfers** (transfers update account balances without inflating income or expense totals), tracks **Monthly Budgets** with threshold alerts, manages **Recurring Rules**, and includes a **CSV Bank Statement Import Wizard** with SHA-256 duplicate detection.
- **Where & What to Add**:
  1. **`+ Add Transaction` Form**:
     - **Type**:
       - `expense`: Money spent (e.g., groceries, rent, coffee).
       - `income`: Money earned (e.g., salary, freelance payout, interest).
       - `transfer`: Moving money between two of your own accounts (e.g., Checking → Savings).
     - **Amount**: Exact number, e.g., `450.00` or `85000.00`.
     - **Category**:
       - For expenses: `Food & Dining`, `Rent & Housing`, `Transport`, `Subscriptions`, `Shopping`, `Utilities`, `Health`.
       - For income: `Salary`, `Freelance`, `Investments`.
     - **Merchant / Payee**: Where the money went or came from—e.g., `"Swiggy"`, `"Amazon"`, `"Landlord"`, `"Employer"`.
     - **Account**: Select which account paid or received the funds (e.g., `Primary Account`). If `transfer`, also pick **To Account**.
     - **Payment Method**: `UPI`, `Credit Card`, `Debit Card`, `Bank Transfer`, `Cash`.
     - **Tags & Notes**: Optional comma-separated tags (e.g., `work, reimbursable`) and context notes.
  2. **`+ New Budget` (Budgets Tab / Section)**:
     - **Budget Name**: e.g., `"October Dining Cap"` or `"Monthly Total Budget"`.
     - **Month**: `YYYY-MM` (e.g., `2026-10`).
     - **Category**: Enter `"ALL"` to cap total monthly spending across all categories, or enter a specific category like `"Food & Dining"` to cap just that category.
     - **Amount Limit**: e.g., `15000` (for a category) or `60000` (for `ALL`).
     - **Alert Threshold (%)**: e.g., `85` (warns you in amber when you cross 85% of your limit).
  3. **`+ New Account` (Accounts Section)**:
     - **Account Name**: e.g., `"HDFC Checking"`, `"ICICI Credit Card"`, `"Emergency Savings"`.
     - **Account Type**: `checking`, `savings`, `credit_card`, `wallet`, `cash`, or `investment`.
     - **Initial Balance**: Starting balance before your logged transactions, e.g., `50000.00`.
  4. **`+ Recurring Rule` (Recurring Section)**:
     - **Title**: e.g., `"House Rent"`, `"Internet Fiber Bill"`, `"Gym Membership"`.
     - **Amount & Category**: e.g., `18000` · `Rent & Housing`.
     - **Frequency**: `monthly`, `weekly`, `daily`, or `yearly`.
     - **Click `Process Due Rules`**: Automatically generates transactions for any recurring rules whose `next_due_date` has arrived.
  5. **`Import CSV` Button**:
     - Paste CSV text or upload a `.csv` file with columns like `date,amount,type,category,merchant,notes`. Click **Preview Import** to inspect parsed rows and duplicate flags, then click **Commit Import**.

---

## 4. Screen Time (`/screen-time`)

Implemented in [`frontend/app/screen-time/page.tsx`](../frontend/app/screen-time/page.tsx).

- **What it does**: Tracks how much time you spend across applications and devices (`desktop`, `phone`, `tablet`, `web`), separates **Productive** vs **Neutral** vs **Non-Productive** usage, flags **Late-Night Screen Time (`22:00–05:00`)**, and compares your daily total against your configured Screen-Time Target.
- **Where & What to Add**:
  1. **`+ Log Screen Time` Form**:
     - **Application Name**: e.g., `"VS Code"`, `"Terminal"`, `"YouTube"`, `"Instagram"`, `"Chrome"`, `"Figma"`.
     - **Device**: `desktop`, `phone`, `tablet`, or `web`.
     - **Duration (Minutes)**: e.g., `90` (for 1.5 hours).
     - **Start / End Time (Optional)**: If you include a start time between `22:00` and `05:00`, the engine automatically counts it in **Late-Night Screen Time** and plots it on your **Personal Rhythm** heatmap!
     - **Category**: `work`, `learning`, `communication`, `entertainment`, `social_media`, `gaming`, `utilities`.
     - **Productivity Classification**: `productive`, `neutral`, or `non_productive`.
  2. **`App Category Mappings` Section**:
     - **What to add**: Define permanent rules so you don't have to classify apps manually every time—e.g.:
       - *App Name*: `VS Code` → *Category*: `work` → *Productivity*: `productive`
       - *App Name*: `Instagram` → *Category*: `social_media` → *Productivity*: `non_productive`
       - *App Name*: `Obsidian` → *Category*: `learning` → *Productivity*: `productive`

---

## 5. Time & Activities (`/activities`)

Implemented in [`frontend/app/activities/page.tsx`](../frontend/app/activities/page.tsx).

- **What it does**: Provides two ways to track how you invest your time:
  1. **Persistent Focus Timer**: Stored in SQLite so it keeps running accurately even if you refresh the page or close the browser.
  2. **Manual Activity Sessions**: Log completed blocks of work, study, reading, or chores.
  - Automatically computes both **Total Recorded Time** and **Unique Clock Time** (merging overlapping intervals so double-logged hours never inflate your clock total).
- **Where & What to Add**:
  1. **Persistent Focus Timer Bar**:
     - **Session Title**: Specific task you are focusing on right now—e.g., `"Write Database Migration Tests"`.
     - **Category**: `Deep Work`, `Coding`, `Writing`, `Study`, `Planning`, `Reading`.
     - **Planned Duration (mins)**: e.g., `50` (for a 50-minute deep work block) or `25` (Pomodoro).
     - Click **`Start Focus`**. When done, click **`Finish & Save`**.
  2. **`+ Log Manual Session` Button**:
     - **Activity Name**: e.g., `"System Architecture Review"` or `"Evening Book Reading"`.
     - **Category**: e.g., `Deep Work`, `Coding`, `Study`, `Exercise`, `Reading`.
     - **Project (Optional — highly recommended!)**: Enter a project name like `"Personal Life OS"`, `"Thesis"`, or `"Client Portal"`. This populates the **Project Time Allocation** pie chart and creates a **Project Node** in **Data Constellation**!
     - **Date, Start Time & Duration (mins)**: e.g., `2026-10-18`, `09:30`, `60` mins.
     - **Count as Deep Focus Session**: Check this box if the session was distraction-free focus work.

---

## 6. Health, Sleep, Mood & Energy (`/health`)

Implemented in [`frontend/app/health/page.tsx`](../frontend/app/health/page.tsx).

- **What it does**: Tracks your daily self-reported physical and mental wellbeing metrics. Missing days are preserved as clean gaps rather than fake zeros, and once you log 4+ days alongside habits or focus sessions, the engine computes **Observational Relationships** (e.g., comparing your average focus minutes on days with `≥ 7h` sleep vs `< 7h` sleep).
- **Where & What to Add**:
  1. **`+ Log Daily Check-in` Button** (Upserts 1 record per date—logging again on the same date updates that day's record):
     - **Date**: Today's date (or a past date you want to backfill).
     - **Sleep Hours**: e.g., `7.5` or `8.0`.
     - **Sleep Quality (1–10)**: e.g., `8`.
     - **Bedtime & Wake Time**: e.g., `23:00` and `06:30`.
     - **Mood (1–10)** & **Energy (1–10)**: e.g., `8` and `8`.
     - **Exercise (mins)** & **Exercise Type**: e.g., `45` and `"Strength & Mobility"` or `"5km Run"`.
     - **Water (ml)**: e.g., `2500`.
     - **Weight kg (Optional)**: e.g., `71.5`.
     - **Steps (Custom Metric)**: e.g., `9200`.
     - **Notes**: Brief context, e.g., `"Felt well-rested after early sleep"`.

---

## 7. Goals, Projects & Milestones (`/goals`)

Implemented in [`frontend/app/goals/page.tsx`](../frontend/app/goals/page.tsx).

- **What it does**: Tracks medium- and long-term quantitative goals, calculates whether your progress is **`ahead`**, **`on_track`**, or **`behind`** linear deadline pace, manages **Milestone Checklists** (which also auto-complete if their target value is reached), and links goals to supporting daily habits.
- **Where & What to Add**:
  1. **`+ New Goal` Button**:
     - **Goal Name**: e.g., `"Read 24 Books This Year"`, `"Save ₹2,00,000 Emergency Fund"`, or `"Complete 100 Hours of Rust Study"`.
     - **Category**: e.g., `"Learning"`, `"Finance"`, `"Career & Engineering"`, `"Health"`.
     - **Project**: e.g., `"Personal Life OS"` or `"Rust Mastery"` (links your activity sessions under that project to this goal in **Data Constellation**!).
     - **Target Value & Unit**: e.g., Target = `24`, Unit = `books` (or Target = `100`, Unit = `hours`).
     - **Deadline (`Target Date`)**: Pick a target completion date so the engine can calculate your expected linear pace percentage.
     - **Initial Milestones (one per line)**:
       ```text
       Finish first 5 books
       Reach halfway mark (12 books)
       Complete all 24 books
       ```
     - **Link Supporting Habits**: Check any daily habits that contribute to this goal (e.g., link `"Read 30 Pages"` to `"Read 24 Books"`).
  2. **`+ Progress` Button on Any Goal Card**:
     - **Increment**: Enter how much progress to add (e.g., `1` book or `2.5` hours) and optional notes (e.g., `"Finished Designing Data-Intensive Applications"`).
  3. **`Add milestone...` Input Inside Any Goal Card**:
     - Type a new checkpoint title and click **Add**, or click any existing milestone circle to toggle it completed.

---

## 8. Private Journal & Daily Review (`/journal`)

Implemented in [`frontend/app/journal/page.tsx`](../frontend/app/journal/page.tsx).

- **What it does**: A 100% local, private reflection space with two modes: **Free-form Journal Entries** and a guided **7-Question Evening Daily Review**. If you enter a **Daily Intention** for today's date, it automatically syncs to your **Overview Dashboard** header!
- **Where & What to Add**:
  1. **`+ New Free-form Entry` Button**:
     - **Date, Mood (1–10), Energy (1–10)**: Context for the entry.
     - **Tags (comma-separated)**: e.g., `reflection, architecture, gratitude`.
     - **Title & Daily Intention**: e.g., Title = `"Mid-week engineering reflection"`, Daily Intention = `"Ship clean, well-tested code"`.
     - **Reflection / Notes**: Write freely in plain text or Markdown.
  2. **`7-Question Daily Review` Button**:
     - Guides you through 7 structured prompts at the end of the day:
       1. *What went well today?*
       2. *What drained or boosted my energy?*
       3. *What did I accomplish?*
       4. *How did I spend money today?*
       5. *How did I invest my time & habits?*
       6. *What could I improve?*
       7. *Focus & note for tomorrow*

---

## 9. Insights (`/insights`)

Implemented in [`frontend/app/insights/page.tsx`](../frontend/app/insights/page.tsx).

- **What it does**: Runs deterministic statistical rules across your local SQLite database to surface actionable patterns (spending spikes/drops, top expense category shares, habit streak milestones, screen-time target breaches, week-over-week focus changes, goals behind schedule pace, time-of-day activity concentration, and habit-vs-energy observational associations).
- **What to interact with**:
  - **Data Sufficiency Diagnostics**: Tells you exactly how many more records are needed in any domain that doesn't yet have enough data to trigger statistical insights.
  - **`Mark Reviewed` / `Dismiss` Buttons**: Acknowledge an insight or hide it from active view (toggle **Show dismissed** to restore dismissed insights).

---

## 10. Personal Timeline (`/timeline`)

Implemented in [`frontend/app/timeline/page.tsx`](../frontend/app/timeline/page.tsx).

- **What it does**: Assembles a unified, chronological feed of every event across all 9 domains (habit completions, financial transactions, focus blocks, activities, screen-time sessions, goals, milestones, journal reflections, and wellbeing check-ins) grouped by date without duplicating records.
- **What to use**:
  - Use the **Search box**, **Start/End Date pickers**, and **Domain Filter Pills** (`Habits`, `Finance`, `Focus`, etc.) to slice your life history, and click **`View`** on any event to jump to its source domain.

---

## 11. Personal Data Constellation (`/constellation`)

Implemented in [`frontend/app/constellation/page.tsx`](../frontend/app/constellation/page.tsx).

- **What it does**: Renders an interactive `@xyflow/react` knowledge graph showing how your **Habits**, **Goals**, **Projects**, **Activity Categories**, **Spending Categories**, **Applications**, **Time Periods (`YYYY-MM`)**, **Wellbeing Metrics**, and **Milestones** connect to one another.
- **How to make the graph rich & connected**:
  - Link a **Habit** to a **Goal** (in `/goals`), or give them the same **Category** name.
  - Assign the same **Project** name (e.g., `"Personal Life OS"`) to both a **Goal** and your **Activity / Focus Sessions**.
  - Click any node in the graph to inspect its live metrics and read plain-English explanations of every relationship edge in the right-hand inspector panel.

---

## 12. Personal Rhythm (`/rhythm`)

Implemented in [`frontend/app/rhythm/page.tsx`](../frontend/app/rhythm/page.tsx).

- **What it does**: Visualizes your weekly biological and productive clock as an interactive **7 Weekday × 24 Hour Heatmap**, alongside **Morning / Afternoon / Evening / Night** comparisons, **Weekday vs Weekend** volume, and **Two-Period Delta** comparisons.
- **How to interact**:
  - Click **any cell** in the `7×24` grid (e.g., `Monday · 09:00`) to open a drill-down modal listing the exact timestamped focus sessions, activities, habits, or screen-time logs that occurred during that weekday/hour slot.

---

## 13. Life Wrapped (`/wrapped`)

Implemented in [`frontend/app/wrapped/page.tsx`](../frontend/app/wrapped/page.tsx).

- **What it does**: Generates a magazine-style **Monthly Report**, **Annual Wrapped**, or **Custom Date Range Retrospective** summarizing your habit consistency, financial net savings, focus hours, top projects, most-used apps, wellbeing averages, and traceable observations.
- **Actions**:
  - Switch between **Monthly Report**, **Annual Wrapped**, and **Custom Date Range**.
  - Click **`Export JSON`** to save the report data, or click **`Print / Save as PDF`** to generate a clean printable PDF (navigation and buttons are automatically hidden in print layout).

---

## 14. Personal Data Explorer & Schema Browser (`/explorer`)

Implemented in [`frontend/app/explorer/page.tsx`](../frontend/app/explorer/page.tsx).

- **What it does**:
  - **Record Explorer Tab**: Browse, search, filter by date, toggle visible columns, export CSV/JSON, and inspect the raw canonical JSON + foreign-key relationships of any record across all 10 tables.
  - **Schema Browser Tab**: Inspect all SQLite tables, column types, primary keys, indexes, and foreign-key relationships.
- **Where & What to Add**:
  - **`Save current filter preset...` Input**: Enter a preset name (e.g., `"High Food Spend"` or `"Deep Work Logs"`) and click **`Save Preset`** to save your current table + search + date filter as a one-click pill.

---

## 15. API & Integrations Center (`/api-console`)

Implemented in [`frontend/app/api-console/page.tsx`](../frontend/app/api-console/page.tsx).

- **What it does**: Your developer console for automating Personal Life OS with scripts, shortcuts, or companion tools.
- **Where & What to Add**:
  1. **`Create Personal API Token` Form**:
     - **Token Label**: e.g., `"Local Screen-Time Collector"` or `"My Python CLI"`.
     - **Expiration (Days)**: e.g., `90` or `365`.
     - **Granted Scopes**: Check only the scopes that script needs (e.g., `write:screen_time`, or `read:all` + `write:all`).
     - Click **`Generate Scoped Token`** and copy the `plos_...` token shown in the green banner.
  2. **Endpoint Catalog & Interactive Local API Playground**:
     - Click any endpoint in the left catalog (e.g., `POST /api/v1/transactions` or `GET /api/v1/dashboard`) to auto-fill the method, path, and sample JSON body, then click **`Send Request`** to execute it live against your local FastAPI backend and inspect the HTTP status, latency (ms), and formatted JSON response.
     - Switch between the **Python**, **curl**, **JS**, and **PowerShell** tabs at the bottom to copy ready-to-run code snippets.

---

## 16. Settings, Personalization & Backups (`/settings`)

Implemented in [`frontend/app/settings/page.tsx`](../frontend/app/settings/page.tsx).

- **What it does**: Manages your profile, regional formatting, daily targets, theme (`dark` / `light`), verified SQLite online backups, and data reset.
- **Where & What to Add / Configure**:
  1. **Personal Profile & Regional Preferences**:
     - **Display Name & Preferred Greeting Name**: e.g., `"Minhaj"`.
     - **Timezone**: IANA timezone string, e.g., `"Asia/Kolkata"`, `"UTC"`, `"America/New_York"`.
     - **Base Currency**: 3-letter ISO currency code, e.g., `"INR"`, `"USD"`, `"EUR"`.
     - **Screen-Time Target (m)**: Daily cap in minutes, e.g., `240` (4 hours).
     - **Default Focus Block (m)**: Default timer length in minutes, e.g., `50`.
     - **Budget Alert (%)**: Default warning threshold, e.g., `85`.
     - **Today's Primary Intention**: Syncs with the Overview Dashboard intention banner.
  2. **SQLite Online Backup & Validated Restore**:
     - **Backup Label Input**: Enter a label like `"before_csv_import"` or `"weekly_backup"` and click **`Create Backup`**.
     - **Restore Button**: Click **`Restore`** next to any backup to verify its SHA-256 checksum and `PRAGMA integrity_check`, automatically create a pre-restore safety snapshot, and restore your database.

