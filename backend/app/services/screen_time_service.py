import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AppCategoryMapping,
    IntegrationConfig,
    ScreenTimeSession,
    UserPreference,
)
from app.schemas.api_schemas import (
    ScreenTimeCreate,
    ScreenTimeResponse,
    ScreenTimeUpdate,
)

DEFAULT_APP_MAPPINGS: Dict[str, Tuple[str, str]] = {
    "vs code": ("work", "productive"),
    "visual studio code": ("work", "productive"),
    "cursor": ("work", "productive"),
    "antigravity": ("work", "productive"),
    "terminal": ("work", "productive"),
    "windows terminal": ("work", "productive"),
    "powershell": ("work", "productive"),
    "windows powershell": ("work", "productive"),
    "command prompt": ("work", "productive"),
    "github": ("work", "productive"),
    "figma": ("work", "productive"),
    "notion": ("work", "productive"),
    "obsidian": ("learning", "productive"),
    "anki": ("learning", "productive"),
    "coursera": ("learning", "productive"),
    "documentation": ("learning", "productive"),
    "google chrome": ("work", "neutral"),
    "chrome": ("work", "neutral"),
    "microsoft edge": ("work", "neutral"),
    "brave": ("work", "neutral"),
    "firefox": ("work", "neutral"),
    "file explorer": ("utilities", "neutral"),
    "slack": ("communication", "neutral"),
    "discord": ("communication", "neutral"),
    "telegram": ("communication", "neutral"),
    "zoom": ("communication", "productive"),
    "teams": ("communication", "productive"),
    "whatsapp": ("communication", "neutral"),
    "messages": ("communication", "neutral"),
    "phone": ("communication", "neutral"),
    "gmail": ("communication", "neutral"),
    "youtube": ("entertainment", "non_productive"),
    "netflix": ("entertainment", "non_productive"),
    "prime video": ("entertainment", "non_productive"),
    "spotify": ("entertainment", "neutral"),
    "instagram": ("social_media", "non_productive"),
    "twitter": ("social_media", "non_productive"),
    "x": ("social_media", "non_productive"),
    "reddit": ("social_media", "non_productive"),
    "facebook": ("social_media", "non_productive"),
    "snapchat": ("social_media", "non_productive"),
    "tiktok": ("social_media", "non_productive"),
    "linkedin": ("social_media", "neutral"),
    "steam": ("gaming", "non_productive"),
}


def resolve_app_classification(
    db: Session,
    app_name: str,
    explicit_category: Optional[str] = None,
    explicit_productivity: Optional[str] = None,
) -> Tuple[str, str]:
    mapping = db.execute(
        select(AppCategoryMapping).where(AppCategoryMapping.app_name.ilike(app_name.strip()))
    ).scalar_one_or_none()

    if mapping:
        cat = explicit_category or mapping.category
        prod = explicit_productivity or mapping.productivity_type
        return cat, prod

    lower_name = app_name.strip().lower()
    if lower_name in DEFAULT_APP_MAPPINGS:
        default_cat, default_prod = DEFAULT_APP_MAPPINGS[lower_name]
        return explicit_category or default_cat, explicit_productivity or default_prod

    cat = explicit_category or "other"
    if explicit_productivity:
        prod = explicit_productivity
    elif cat in ("work", "learning"):
        prod = "productive"
    elif cat in ("entertainment", "social_media", "gaming"):
        prod = "non_productive"
    else:
        prod = "neutral"
    return cat, prod


def compute_screen_time_hash(
    session_date: date,
    app_name: str,
    device: str,
    duration_minutes: int,
    start_time: Optional[datetime],
) -> str:
    start_iso = start_time.isoformat() if start_time else "none"
    raw = f"{session_date.isoformat()}|{app_name.strip().lower()}|{device.lower()}|{duration_minutes}|{start_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_screen_time_session(db: Session, payload: ScreenTimeCreate) -> ScreenTimeResponse:
    duration = payload.duration_minutes
    if duration is None:
        if payload.start_time and payload.end_time and payload.end_time > payload.start_time:
            duration = max(1, int(round((payload.end_time - payload.start_time).total_seconds() / 60.0)))
        else:
            duration = 30

    category, productivity = resolve_app_classification(
        db, payload.app_name, payload.category, payload.productivity_type
    )
    ext_hash = compute_screen_time_hash(
        payload.session_date, payload.app_name, payload.device, duration, payload.start_time
    )

    if payload.data_source in ("local_collector", "api"):
        collector_cfg = db.execute(
            select(IntegrationConfig).where(IntegrationConfig.key == "local_screen_time_collector")
        ).scalar_one_or_none()
        if collector_cfg:
            collector_cfg.is_enabled = True
            collector_cfg.is_configured = True
            collector_cfg.is_receiving_data = True
            collector_cfg.status_message = "Active (Receiving Live Telemetry)"

    # If start_time is omitted for a local_collector sync (e.g., cumulative daily total per app on Laptop or Android),
    # upsert today's record for (session_date, app_name, device, data_source) to avoid duplicate rows.
    if payload.data_source == "local_collector" and payload.start_time is None:
        existing = db.execute(
            select(ScreenTimeSession).where(
                ScreenTimeSession.session_date == payload.session_date,
                ScreenTimeSession.app_name.ilike(payload.app_name.strip()),
                ScreenTimeSession.device == payload.device,
                ScreenTimeSession.data_source == "local_collector",
                ScreenTimeSession.start_time.is_(None),
            )
        ).scalars().first()
        if existing:
            existing.duration_minutes = duration
            existing.category = category
            existing.productivity_type = productivity
            existing.notes = payload.notes or existing.notes
            existing.external_hash = ext_hash
            db.commit()
            db.refresh(existing)
            return ScreenTimeResponse.model_validate(existing)

    session = ScreenTimeSession(
        app_name=payload.app_name.strip(),
        device=payload.device,
        session_date=payload.session_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=duration,
        category=category,
        productivity_type=productivity,
        data_source=payload.data_source,
        notes=payload.notes,
        is_historical_correction=payload.is_historical_correction,
        external_hash=ext_hash,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ScreenTimeResponse.model_validate(session)


def update_screen_time_session(
    db: Session, session: ScreenTimeSession, payload: ScreenTimeUpdate
) -> ScreenTimeResponse:
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(session, k, v)

    if session.start_time and session.end_time and "duration_minutes" not in data:
        if session.end_time > session.start_time:
            session.duration_minutes = max(
                1, int(round((session.end_time - session.start_time).total_seconds() / 60.0))
            )

    session.external_hash = compute_screen_time_hash(
        session.session_date,
        session.app_name,
        session.device,
        session.duration_minutes,
        session.start_time,
    )
    db.commit()
    db.refresh(session)
    return ScreenTimeResponse.model_validate(session)


def _is_late_night(dt: Optional[datetime], tz: ZoneInfo) -> bool:
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(tz)
    return local_dt.hour >= 22 or local_dt.hour < 5


def get_screen_time_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    daily_target = pref.daily_screen_time_target_minutes if pref else 240
    tz_name = pref.timezone if pref else "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    today = datetime.now(tz).date()
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=6)

    sessions = db.execute(
        select(ScreenTimeSession).where(
            ScreenTimeSession.session_date >= start_date,
            ScreenTimeSession.session_date <= end_date,
        )
    ).scalars().all()

    total_minutes = sum(s.duration_minutes for s in sessions)
    period_days = max(1, (end_date - start_date).days + 1)
    recorded_dates = sorted(set(s.session_date for s in sessions))
    avg_daily_recorded = round(total_minutes / len(recorded_dates), 1) if recorded_dates else 0.0
    avg_daily_period = round(total_minutes / period_days, 1)

    app_totals: Dict[str, int] = {}
    category_totals: Dict[str, int] = {}
    productivity_totals: Dict[str, int] = {"productive": 0, "neutral": 0, "non_productive": 0}
    source_totals: Dict[str, int] = {}
    daily_totals: Dict[str, int] = {}
    late_night_sessions: List[Dict[str, Any]] = []

    for s in sessions:
        app_totals[s.app_name] = app_totals.get(s.app_name, 0) + s.duration_minutes
        category_totals[s.category] = category_totals.get(s.category, 0) + s.duration_minutes
        prod_key = s.productivity_type if s.productivity_type in productivity_totals else "neutral"
        productivity_totals[prod_key] += s.duration_minutes
        source_totals[s.data_source] = source_totals.get(s.data_source, 0) + s.duration_minutes
        d_iso = s.session_date.isoformat()
        daily_totals[d_iso] = daily_totals.get(d_iso, 0) + s.duration_minutes

        if _is_late_night(s.start_time, tz) or _is_late_night(s.end_time, tz):
            late_night_sessions.append(
                {
                    "id": s.id,
                    "app_name": s.app_name,
                    "session_date": s.session_date.isoformat(),
                    "duration_minutes": s.duration_minutes,
                    "start_time": s.start_time.isoformat() if s.start_time else None,
                    "category": s.category,
                }
            )

    app_rankings = [
        {
            "app_name": app,
            "duration_minutes": mins,
            "hours": round(mins / 60.0, 2),
            "percentage": round((mins / total_minutes) * 100.0, 1) if total_minutes > 0 else 0.0,
        }
        for app, mins in sorted(app_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    category_breakdown = [
        {
            "category": cat,
            "duration_minutes": mins,
            "hours": round(mins / 60.0, 2),
            "percentage": round((mins / total_minutes) * 100.0, 1) if total_minutes > 0 else 0.0,
        }
        for cat, mins in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    longest_sessions = [
        ScreenTimeResponse.model_validate(s).model_dump(mode="json")
        for s in sorted(sessions, key=lambda x: x.duration_minutes, reverse=True)[:5]
    ]

    daily_series = []
    for i in range(period_days):
        d = start_date + timedelta(days=i)
        d_iso = d.isoformat()
        mins = daily_totals.get(d_iso, 0)
        daily_series.append(
            {
                "date": d_iso,
                "duration_minutes": mins,
                "target_minutes": daily_target,
                "exceeded_target": mins > daily_target,
                "has_recorded_data": d in recorded_dates,
            }
        )

    # Previous period comparison
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)
    prev_sessions = db.execute(
        select(ScreenTimeSession).where(
            ScreenTimeSession.session_date >= prev_start,
            ScreenTimeSession.session_date <= prev_end,
        )
    ).scalars().all()
    prev_total = sum(s.duration_minutes for s in prev_sessions)
    abs_change = total_minutes - prev_total
    pct_change = round((abs_change / prev_total) * 100.0, 1) if prev_total > 0 else None

    # Collector integration status
    collector_cfg = db.execute(
        select(IntegrationConfig).where(IntegrationConfig.key == "local_screen_time_collector")
    ).scalar_one_or_none()
    collector_active = bool(
        collector_cfg and collector_cfg.is_enabled and collector_cfg.is_configured and collector_cfg.is_receiving_data
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60.0, 2),
        "daily_target_minutes": daily_target,
        "average_daily_minutes_recorded_days": avg_daily_recorded,
        "average_daily_minutes_full_period": avg_daily_period,
        "recorded_days_count": len(recorded_dates),
        "period_days_count": period_days,
        "app_rankings": app_rankings,
        "category_breakdown": category_breakdown,
        "work_vs_entertainment": {
            "productive_minutes": productivity_totals["productive"],
            "neutral_minutes": productivity_totals["neutral"],
            "non_productive_minutes": productivity_totals["non_productive"],
            "productive_percentage": (
                round((productivity_totals["productive"] / total_minutes) * 100.0, 1) if total_minutes > 0 else 0.0
            ),
        },
        "late_night_usage": {
            "window": "22:00 - 05:00 local time",
            "total_minutes": sum(x["duration_minutes"] for x in late_night_sessions),
            "sessions_count": len(late_night_sessions),
            "sessions": late_night_sessions[:10],
        },
        "longest_sessions": longest_sessions,
        "daily_series": daily_series,
        "data_sources": source_totals,
        "automatic_collector_status": {
            "is_active": collector_active,
            "label": "Active Local Companion Collector" if collector_active else "Manual & CSV Mode (Automatic Collector Unconfigured)",
            "explanation": (
                "Local OS companion script is configured and sending window telemetry."
                if collector_active
                else "Browsers cannot directly inspect OS window activity. Use Manual Entry, CSV Import, or start scripts/screen_time_collector.py."
            ),
        },
        "period_comparison": {
            "previous_start_date": prev_start.isoformat(),
            "previous_end_date": prev_end.isoformat(),
            "previous_total_minutes": prev_total,
            "absolute_change_minutes": abs_change,
            "percentage_change": pct_change,
            "has_sufficient_previous_data": len(prev_sessions) > 0 and prev_total > 0,
        },
    }

