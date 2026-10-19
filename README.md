# Personal Life OS

**Personal Life OS** is a 100% free, open-source, local-first personal life analytics application, command center, and REST API (`/api/v1`).

It allows you to track, analyze, visualize, and programmatically query your **habits, expenses, income, budgets, screen time, focus sessions, activities, goals, milestones, sleep, mood, energy, and private journal entries**—entirely on your own computer with zero cloud dependencies, zero subscriptions, and zero commercial AI API keys.

---

## Why Personal Life OS is 100% Free & Offline-Capable

1. **Zero Paid APIs or AI Keys**: All analytics, natural-language queries (`/api/v1/nlq`), pattern insights (`/api/v1/insights`), knowledge graphs (`/api/v1/constellation`), heatmaps (`/api/v1/rhythm`), and retrospectives (`/api/v1/wrapped`) are computed locally using deterministic Python algorithms.
2. **Local SQLite Database with WAL Mode**: Your personal records live in `data/personal_life_os.db` on your filesystem with foreign-key enforcement (`PRAGMA foreign_keys=ON`) and Write-Ahead Logging (`PRAGMA journal_mode=WAL`).
3. **No Remote Telemetry or Assets**: No external fonts, third-party trackers, or remote scripts are loaded. Once `pip` and `pnpm`/`npm` dependencies are installed, the entire application runs offline.
4. **Permissive Open-Source Stack**: Built with FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, Next.js App Router, React, TypeScript (strict mode), Tailwind CSS, Recharts, and React Flow (`@xyflow/react`).

---

## Project Architecture

```text
d:\MyAPI\
  backend/
    app/
      analytics/       # Dashboard, Timeline, Insights, Constellation, Rhythm, Life Wrapped engines
      api/             # FastAPI /api/v1 router with scope-enforced endpoints
      core/            # Config, SQLite WAL database engine, bcrypt + JWT + SHA-256 token security
      models/          # 21 normalized SQLAlchemy 2.x ORM models
      schemas/         # Pydantic v2 request/response validation schemas
      services/        # Habits, Finance (Decimal), Screen Time, Focus Timer, Goals, Wellbeing, Journal, NLQ, Backups
      tests/           # Automated pytest + HTTPX test suite
      main.py          # FastAPI application entrypoint
    migrations/        # Alembic schema migrations
    requirements.txt
  frontend/
    app/               # 16 App Router pages (Overview, Habits, Finance, Screen Time, Activities, Health, etc.)
    components/        # Persistent AppShell, Command Palette (Ctrl+K), Quick-Add Modal, Live Focus Timer Pill
    lib/               # API client & formatting utilities
  data/                # Persistent local SQLite database (gitignored)
  backups/             # Online SQLite backups + SHA-256 JSON manifests (gitignored)
  exports/             # Exported CSV/JSON snapshots (gitignored)
  scripts/             # Windows PowerShell setup/start scripts + optional local screen-time collector
  docs/                # Full REST API documentation & code examples
  .env.example
  README.md
  LICENSE
```

---

## Quick Start (Windows PowerShell)

### 1. One-Command Setup
From the repository root (`d:\MyAPI`), run:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```
This script:
- Creates `data/`, `backups/`, and `exports/` directories.
- Copies `.env.example` to `.env` if not already present.
- Sets up the Python virtual environment in `backend\.venv`, installs `backend\requirements.txt`, and runs `alembic upgrade head`.
- Installs frontend dependencies in `frontend/`.

### 2. Start Personal Life OS Locally
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```
- **Frontend UI**: `http://localhost:3000`
- **Backend REST API**: `http://localhost:8000/api/v1`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`

### Manual Startup (Two Terminals)
**Terminal 1 — FastAPI Backend:**
```powershell
cd d:\MyAPI\backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Next.js Frontend:**
```powershell
cd d:\MyAPI\frontend
pnpm run dev
```

---

## Running Automated Tests & Typechecks

**Backend Test Suite (`pytest` + `httpx`):**
```powershell
cd d:\MyAPI\backend
.\.venv\Scripts\pytest.exe -v
```

**Frontend TypeScript Strict Mode & Production Build:**
```powershell
cd d:\MyAPI\frontend
pnpm run typecheck
pnpm run build
```

---

## Personal REST API & Scoped Tokens (`plos_`)

1. Sign in to `http://localhost:3000` and open **API & Integrations** (`/api-console`).
2. Under **Create Personal API Token**, enter a label, choose granular scopes (e.g., `read:all`, `write:finance`, `write:screen_time`), and click **Generate Scoped Token**.
3. Copy your `plos_...` token immediately (it is shown only once and stored as a SHA-256 hash in SQLite).
4. See [`docs/API.md`](docs/API.md) for full `curl`, Python, JavaScript, and PowerShell examples.

---

## Imports, Exports, Backups & Recovery Procedure

### CSV Import
- Navigate to **Finance → Import CSV** (or use `POST /api/v1/import/preview` and `POST /api/v1/import/commit`).
- Preview parsed rows, inspect validation warnings, and automatically skip duplicate records via SHA-256 content hashes.

### Full Data Export
- Download your entire personal dataset as structured JSON (`GET /api/v1/export?format=json`) or domain CSV (`GET /api/v1/export?format=csv&domain=transactions`) from **Settings** or **Data Explorer**.

### Creating & Restoring Verified SQLite Backups
- Navigate to **Settings → SQLite Online Backup & Validated Restore**.
- Clicking **Create Backup** uses SQLite's native online backup API (`sqlite3.Connection.backup`) to create a transaction-consistent `.db` copy in `backups/` alongside a `.manifest.json` file containing the schema version, record counts, and SHA-256 checksum.
- Clicking **Restore** verifies the SQLite binary header, validates the SHA-256 checksum against the manifest, runs `PRAGMA integrity_check`, automatically creates a `pre_restore_safety` snapshot of your current database, and restores the selected backup.

---

## Optional Self-Hosting Guide (100% Free Options)

Personal Life OS requires **no hosting** for normal desktop use. If you wish to access it from your phone on your home network:
1. **Local Wi-Fi / LAN (Free)**: Run `uvicorn app.main:app --host 0.0.0.0 --port 8000` and `pnpm run start` bound to `0.0.0.0`, then open your computer's LAN IP (`http://192.168.x.x:3000`) from your phone on the same Wi-Fi.
2. **Private Mesh VPN (Free Personal Tier)**: Use WireGuard or Tailscale on your computer and phone to access your local instance securely without exposing ports to the public internet.
3. **Hardware / Electricity / Domain Transparency**: Running on your existing PC costs $0 in software. Leaving a dedicated home mini-PC/Raspberry Pi running 24/7 incurs only your local household electricity usage, and purchasing a public custom domain is optional and never required.

---

## Feature Status & Transparency

### 1. Implemented Features (100% Complete & Local)
- **Authentication & Security**: First-run local account setup, `bcrypt` password hashing, HTTP-only session cookies, and SHA-256 hashed `plos_` personal API tokens with scope enforcement.
- **Overview Dashboard**: Live KPIs across all 11 life domains, period-over-period comparisons, 14-day multi-metric charts, Today's Intention banner, and deterministic Natural-Language Query bar.
- **Habits**: Daily/weekday/weekly habits, quantitative targets, timezone-aware streak calculator (unscheduled days do not break streaks, future dates rejected), and 14-day completion matrix.
- **Personal Finance**: Exact `Decimal` arithmetic, multi-account balance tracking, transfer exclusion from income/expense totals, multi-currency isolation, monthly budgets with alerts, recurring transaction rules, and CSV import wizard.
- **Screen Time**: App/device sessions, configurable app-to-category mappings, productive vs non-productive split, and late-night (`22:00–05:00`) usage detection.
- **Time & Activities**: Persistent SQLite-backed Focus Timer (survives browser reloads), overlap detection, interval-union unique clock time vs total recorded time, and category/project charts.
- **Health & Wellbeing**: Sleep duration/quality, mood, energy, exercise, hydration, weight, custom measurements, and observational cross-domain comparisons.
- **Goals & Projects**: Quantitative goals, deadline linear pace status (`ahead`, `on_track`, `behind`), milestone checklists, and habit links.
- **Private Journal**: Free-form markdown reflections, tag filtering, full-text search, and guided 7-Question Daily Review.
- **Insights, Timeline, Constellation, Rhythm & Life Wrapped**: All 5 advanced analytical and visualization engines backed by canonical SQLite records.
- **Data Explorer, Schema Browser & API Playground**: Interactive record inspection, filter presets, live endpoint testing, and verified SQLite backup/restore.

### 2. Optional / Unconfigured Integrations
- **Local OS Screen-Time Companion Script (`scripts/screen_time_collector.py`)**: Included and ready to run locally with a `plos_` token; disabled by default so the app never polls OS window titles without your explicit launch.

### 3. Known Limitations
- Browsers cannot automatically read mobile iOS/Android OS-level screen time or bank accounts without third-party cloud aggregators; mobile screen time and bank statements are ingested via the built-in CSV importer, manual logging, or the local REST API.

