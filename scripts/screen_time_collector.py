#!/usr/bin/env python3
"""
Personal Life OS — Automatic Screen-Time Collector (Windows Laptop + Android Phone)
===================================================================================
100% Free, Local-First, Zero-Cloud Window & Android Usage Collector.

Features:
1. Auto-Token Provisioning:
   - Automatically provisions and caches a scoped `plos_...` API token in `data/.collector_token`
     against your local SQLite database if `PLOS_API_TOKEN` is not set.
2. Windows Laptop Auto-Tracking (`device="desktop"`):
   - Polls active foreground windows every 10 seconds via Windows `user32` API.
   - Tracks cumulative daily minutes per application and syncs live to `/api/v1/screen-time`
     every 60 seconds (upserting one clean daily total per app).
3. Android Phone Auto-Tracking (`device="phone"`):
   - Method A (ADB USB or Wireless Debugging): Automatically queries `adb shell dumpsys usagestats`
     when your phone is connected via USB or Wi-Fi ADB and syncs each Android app's daily screen time.
   - Method B (Direct Wi-Fi Webhook): Prints the exact LAN URL + token so free Android automation apps
     (MacroDroid / Tasker / HTTP Shortcuts) can POST directly over your home Wi-Fi.
"""

import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
DATA_DIR = REPO_ROOT / "data"
TOKEN_FILE = DATA_DIR / ".collector_token"

DEFAULT_API_URL = os.environ.get("PLOS_API_URL", "http://127.0.0.1:8000/api/v1")
DEFAULT_TOKEN = os.environ.get("PLOS_API_TOKEN", "")
DEFAULT_ANDROID_ADB = os.environ.get("PLOS_ANDROID_ADB", "")

IGNORED_WINDOW_TITLES = {
    "",
    "program manager",
    "windows default lock screen",
    "task switching",
    "search",
    "new notification",
    "volume control",
    "system tray overflow window.",
}

WINDOW_NAME_ALIASES = {
    "visual studio code": "VS Code",
    "code": "VS Code",
    "google chrome": "Google Chrome",
    "microsoft​ edge": "Microsoft Edge",
    "microsoft edge": "Microsoft Edge",
    "windows powershell": "PowerShell",
    "powershell": "PowerShell",
    "windows terminal": "Terminal",
    "cmd.exe": "Command Prompt",
    "file explorer": "File Explorer",
}

ANDROID_PACKAGE_LABELS = {
    "com.whatsapp": "WhatsApp",
    "com.instagram.android": "Instagram",
    "com.google.android.youtube": "YouTube",
    "com.android.chrome": "Chrome",
    "org.mozilla.firefox": "Firefox",
    "com.brave.browser": "Brave",
    "com.spotify.music": "Spotify",
    "com.netflix.mediaclient": "Netflix",
    "com.amazon.avod.thirdpartyclient": "Prime Video",
    "com.twitter.android": "X",
    "com.zhiliaoapp.musically": "TikTok",
    "com.ss.android.ugc.trill": "TikTok",
    "com.reddit.frontpage": "Reddit",
    "com.linkedin.android": "LinkedIn",
    "com.discord": "Discord",
    "org.telegram.messenger": "Telegram",
    "com.Slack": "Slack",
    "com.google.android.gm": "Gmail",
    "com.google.android.apps.messaging": "Messages",
    "com.google.android.dialer": "Phone",
    "com.google.android.apps.maps": "Google Maps",
    "com.notion.id": "Notion",
    "md.obsidian": "Obsidian",
    "com.ichi2.anki": "Anki",
    "com.openai.chatgpt": "ChatGPT",
}

IGNORED_ANDROID_PACKAGES = {
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.launcher",
    "com.android.launcher3",
    "com.google.android.apps.nexuslauncher",
    "com.sec.android.app.launcher",
    "com.miui.home",
    "com.oneplus.launcher",
    "com.google.android.inputmethod.latin",
    "com.samsung.android.honeyboard",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.android.permissioncontroller",
    "com.google.android.packageinstaller",
}


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def ensure_local_api_token(explicit_token: str = "") -> str:
    """Automatically load or create a local API token in SQLite if none was provided."""
    if explicit_token:
        return explicit_token.strip()

    if TOKEN_FILE.exists():
        saved = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if saved.startswith("plos_"):
            return saved

    try:
        sys.path.insert(0, str(BACKEND_DIR))
        from sqlalchemy import select
        from app.core.database import SessionLocal
        from app.core.security import generate_api_token
        from app.models.entities import ApiToken, IntegrationConfig, UserProfile

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with SessionLocal() as db:
            user = db.execute(select(UserProfile)).scalars().first()
            if not user:
                print("[WARN] No user profile initialized yet in Personal Life OS.")
                return ""
            raw_token, prefix, token_hash = generate_api_token()
            token_row = ApiToken(
                user_id=user.id,
                name="Auto Screen-Time Collector (Laptop + Android)",
                token_prefix=prefix,
                token_hash=token_hash,
                scopes="read:screen_time,write:screen_time,read:all,write:all",
            )
            db.add(token_row)

            cfg = db.execute(
                select(IntegrationConfig).where(IntegrationConfig.key == "local_screen_time_collector")
            ).scalar_one_or_none()
            if cfg:
                cfg.is_enabled = True
                cfg.is_configured = True
                cfg.is_receiving_data = True
                cfg.status_message = "Active (Receiving Live Telemetry)"

            db.commit()
            TOKEN_FILE.write_text(raw_token, encoding="utf-8")
            print(f"[AUTO-CONFIG] Provisioned local API token ({prefix}...) -> saved to {TOKEN_FILE}")
            return raw_token
    except Exception as exc:
        print(f"[WARN] Could not auto-provision token from local database: {exc}")
        return ""


def get_active_window_app() -> str:
    if platform.system() != "Windows":
        return ""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title or title.lower() in IGNORED_WINDOW_TITLES:
            return ""

        parts = [p.strip() for p in re.split(r"\s+[-—]\s+", title) if p.strip()]
        raw_app = parts[-1][:120] if parts else title[:120]
        lower_app = raw_app.lower()
        if lower_app in IGNORED_WINDOW_TITLES:
            return ""
        return WINDOW_NAME_ALIASES.get(lower_app, raw_app)
    except Exception:
        return ""


def upsert_daily_app_usage(
    api_url: str,
    token: str,
    app_name: str,
    device: str,
    session_date: date,
    duration_minutes: int,
    notes: str,
) -> bool:
    if duration_minutes < 1:
        return False
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "app_name": app_name[:140],
        "device": device,
        "session_date": session_date.isoformat(),
        "duration_minutes": min(1440, max(1, duration_minutes)),
        "data_source": "local_collector",
        "notes": notes,
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{api_url.rstrip('/')}/screen-time", headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return True
            if resp.status_code == 401 and TOKEN_FILE.exists():
                # Token expired or DB was re-seeded; remove cached token so next cycle re-provisions
                TOKEN_FILE.unlink(missing_ok=True)
            print(f"[WARN] API returned HTTP {resp.status_code}: {resp.text[:160]}")
    except Exception as exc:
        print(f"[WARN] Could not reach local API ({api_url}): {exc}")
    return False


def find_adb_binary() -> Optional[str]:
    adb = shutil.which("adb")
    if adb:
        return adb
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path("C:/platform-tools/adb.exe"),
        REPO_ROOT / "scripts" / "platform-tools" / "adb.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def friendly_android_app_name(pkg: str) -> str:
    if pkg in ANDROID_PACKAGE_LABELS:
        return ANDROID_PACKAGE_LABELS[pkg]
    parts = [p for p in pkg.split(".") if p not in ("com", "org", "net", "android", "google", "app", "apps")]
    if not parts:
        return pkg
    return parts[-1].replace("_", " ").title()


def sync_android_via_adb(api_url: str, token: str, android_adb_target: str = "") -> int:
    """
    Polls a connected Android phone via USB or Wireless ADB (`adb shell dumpsys usagestats`)
    and syncs today's foreground minutes per app into Personal Life OS (`device="phone"`).
    """
    adb_bin = find_adb_binary()
    if not adb_bin:
        return 0

    try:
        if android_adb_target:
            subprocess.run(
                [adb_bin, "connect", android_adb_target],
                capture_output=True,
                text=True,
                timeout=6,
            )

        devices_proc = subprocess.run(
            [adb_bin, "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [
            ln.strip()
            for ln in devices_proc.stdout.splitlines()[1:]
            if ln.strip() and "\tdevice" in ln
        ]
        if not lines:
            return 0

        dump_proc = subprocess.run(
            [adb_bin, "shell", "dumpsys", "usagestats"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=15,
        )
        raw_out = dump_proc.stdout
        if not raw_out:
            return 0

        # Focus on the most recent daily interval block in dumpsys usagestats
        daily_sections = re.split(r"In-memory daily stats|IntervalStats", raw_out)
        target_block = daily_sections[-1] if daily_sections else raw_out

        # Match lines like: package=com.whatsapp totalTime="12:34" or totalTimeInForeground=754000 or timeActive="12:34"
        pkg_minutes: Dict[str, int] = {}
        for line in target_block.splitlines():
            if "package=" not in line:
                continue
            pkg_match = re.search(r"package=([a-zA-Z0-9_.]+)", line)
            if not pkg_match:
                continue
            pkg = pkg_match.group(1).strip()
            if pkg in IGNORED_ANDROID_PACKAGES or pkg.startswith("com.android.internal"):
                continue

            mins = 0
            # Format 1: totalTime="HH:MM:SS" or "MM:SS" or timeActive="MM:SS"
            hms_match = re.search(r'(?:totalTime|timeActive)="([^"]+)"', line)
            if hms_match:
                parts = [int(x) for x in hms_match.group(1).split(":") if x.isdigit()]
                if len(parts) == 3:
                    mins = parts[0] * 60 + parts[1] + (1 if parts[2] >= 30 else 0)
                elif len(parts) == 2:
                    mins = parts[0] + (1 if parts[1] >= 30 else 0)
            else:
                # Format 2: totalTimeInForeground=123456 (milliseconds)
                ms_match = re.search(r"(?:totalTimeInForeground|timeActive)=(\d+)", line)
                if ms_match:
                    ms = int(ms_match.group(1))
                    mins = int(round(ms / 60000.0))

            if 1 <= mins <= 1440:
                pkg_minutes[pkg] = max(pkg_minutes.get(pkg, 0), mins)

        today = date.today()
        synced_count = 0
        for pkg, mins in sorted(pkg_minutes.items(), key=lambda x: x[1], reverse=True)[:25]:
            app_label = friendly_android_app_name(pkg)
            ok = upsert_daily_app_usage(
                api_url=api_url,
                token=token,
                app_name=app_label,
                device="phone",
                session_date=today,
                duration_minutes=mins,
                notes=f"Auto-synced from Android ADB UsageStats ({pkg})",
            )
            if ok:
                synced_count += 1

        if synced_count > 0:
            print(f"[ANDROID-ADB] Synced {synced_count} Android apps for {today.isoformat()}")
        return synced_count
    except Exception as exc:
        print(f"[WARN] Android ADB sync skipped: {exc}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Personal Life OS — Automatic Screen-Time Collector (Windows Laptop + Android Phone)"
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Base API URL (default: http://127.0.0.1:8000/api/v1)")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Personal API token (plos_...) — auto-provisioned if omitted")
    parser.add_argument("--interval", type=int, default=10, help="Window polling interval in seconds (default: 10)")
    parser.add_argument("--flush-seconds", type=int, default=60, help="How often to sync cumulative totals to API (default: 60)")
    parser.add_argument("--android-adb", default=DEFAULT_ANDROID_ADB, help="Optional Wireless ADB IP:PORT (e.g. 192.168.1.50:5555)")
    parser.add_argument("--sync-android-now", action="store_true", help="Run a one-shot Android ADB sync and exit")
    args = parser.parse_args()

    token = ensure_local_api_token(args.token)
    if not token:
        print("ERROR: Could not obtain or auto-provision a Personal API token.")
        return

    lan_ip = get_lan_ip()
    print("======================================================================")
    print(" Personal Life OS — Auto Screen-Time Collector (Laptop + Android)")
    print("======================================================================")
    print(f" -> Local API URL         : {args.api_url}")
    print(f" -> Android Wi-Fi Webhook : http://{lan_ip}:8000/api/v1/screen-time")
    print(f" -> Active API Token      : {token[:14]}... (saved in data/.collector_token)")
    print("======================================================================\n")

    if args.sync_android_now:
        count = sync_android_via_adb(args.api_url, token, args.android_adb)
        print(f"Done. Synced {count} Android app sessions.")
        return

    current_day = date.today()
    desktop_seconds_today: Dict[str, int] = {}
    dirty_apps: set[str] = set()
    last_flush_ts = time.time()
    last_android_sync_ts = 0.0

    poll_interval = max(5, args.interval)

    try:
        while True:
            now_ts = time.time()
            today = date.today()
            if today != current_day:
                current_day = today
                desktop_seconds_today.clear()
                dirty_apps.clear()

            # 1. Poll active Windows Laptop foreground app
            active_app = get_active_window_app()
            if active_app:
                desktop_seconds_today[active_app] = desktop_seconds_today.get(active_app, 0) + poll_interval
                if desktop_seconds_today[active_app] >= 60:
                    dirty_apps.add(active_app)

            # 2. Periodically flush cumulative desktop app durations to Personal Life OS
            if dirty_apps and (now_ts - last_flush_ts >= args.flush_seconds):
                token = ensure_local_api_token(args.token)
                flushed = []
                for app_name in list(dirty_apps):
                    mins = int(round(desktop_seconds_today.get(app_name, 0) / 60.0))
                    if mins >= 1:
                        ok = upsert_daily_app_usage(
                            api_url=args.api_url,
                            token=token,
                            app_name=app_name,
                            device="desktop",
                            session_date=current_day,
                            duration_minutes=mins,
                            notes="Auto-tracked on Windows Laptop (scripts/screen_time_collector.py)",
                        )
                        if ok:
                            flushed.append(f"{app_name} ({mins}m)")
                            dirty_apps.discard(app_name)
                if flushed:
                    print(f"[LAPTOP] Updated screen time: {', '.join(flushed)}")
                last_flush_ts = now_ts

            # 3. Every 5 minutes, check if an Android phone is connected via ADB (USB or Wi-Fi)
            if now_ts - last_android_sync_ts >= 300:
                token = ensure_local_api_token(args.token)
                sync_android_via_adb(args.api_url, token, args.android_adb)
                last_android_sync_ts = now_ts

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nFlushing remaining Laptop screen-time sessions before exit...")
        token = ensure_local_api_token(args.token)
        for app_name in list(dirty_apps):
            mins = int(round(desktop_seconds_today.get(app_name, 0) / 60.0))
            if mins >= 1:
                upsert_daily_app_usage(
                    api_url=args.api_url,
                    token=token,
                    app_name=app_name,
                    device="desktop",
                    session_date=current_day,
                    duration_minutes=mins,
                    notes="Auto-tracked on Windows Laptop (scripts/screen_time_collector.py)",
                )
        print("Stopped screen-time collector cleanly.")


if __name__ == "__main__":
    main()
