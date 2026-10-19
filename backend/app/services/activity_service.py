from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import ActivitySession
from app.schemas.api_schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    TimerStartRequest,
)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_elapsed_seconds(session: ActivitySession, now_utc: Optional[datetime] = None) -> int:
    """
    Calculates exact elapsed seconds from persisted timestamps (never JS tick counts).
    """
    now = now_utc or datetime.now(timezone.utc)
    base = int(session.accumulated_seconds or 0)
    if session.timer_status == "running" and session.last_resumed_at:
        resumed = _ensure_utc(session.last_resumed_at)
        if resumed and now > resumed:
            base += int((now - resumed).total_seconds())
    elif session.timer_status == "completed" and base == 0 and session.duration_minutes > 0:
        base = session.duration_minutes * 60
    return max(0, base)


def detect_overlapping_session_ids(sessions: List[ActivitySession]) -> Set[str]:
    """
    Identifies sessions whose [start_time, end_time] intervals overlap.
    """
    overlapping: Set[str] = set()
    now_utc = datetime.now(timezone.utc)
    intervals: List[Tuple[str, datetime, datetime]] = []

    for s in sessions:
        st = _ensure_utc(s.start_time)
        if not st:
            continue
        et = _ensure_utc(s.end_time)
        if not et:
            if s.timer_status in ("running", "paused"):
                et = now_utc
            else:
                et = st + timedelta(minutes=max(1, s.duration_minutes))
        if et > st:
            intervals.append((s.id, st, et))

    intervals.sort(key=lambda x: x[1])
    for i in range(len(intervals)):
        id_a, start_a, end_a = intervals[i]
        for j in range(i + 1, len(intervals)):
            id_b, start_b, end_b = intervals[j]
            if start_b < end_a:
                overlapping.add(id_a)
                overlapping.add(id_b)
            else:
                break

    return overlapping


def calculate_unique_clock_minutes(sessions: List[ActivitySession]) -> int:
    """
    Computes unique non-overlapping elapsed clock minutes using interval merging,
    so overlapping sessions are NEVER double-counted in unique allocated time.
    """
    now_utc = datetime.now(timezone.utc)
    raw_intervals: List[Tuple[datetime, datetime]] = []

    for s in sessions:
        st = _ensure_utc(s.start_time)
        if not st:
            continue
        et = _ensure_utc(s.end_time)
        if not et:
            if s.timer_status in ("running", "paused"):
                elapsed = compute_elapsed_seconds(s, now_utc)
                et = st + timedelta(seconds=elapsed)
            else:
                et = st + timedelta(minutes=max(0, s.duration_minutes))
        if et > st:
            raw_intervals.append((st, et))

    if not raw_intervals:
        return 0

    raw_intervals.sort(key=lambda x: x[0])
    merged: List[Tuple[datetime, datetime]] = [raw_intervals[0]]
    for current_start, current_end in raw_intervals[1:]:
        prev_start, prev_end = merged[-1]
        if current_start < prev_end:
            merged[-1] = (prev_start, max(prev_end, current_end))
        else:
            merged.append((current_start, current_end))

    total_seconds = sum((end - start).total_seconds() for start, end in merged)
    return int(round(total_seconds / 60.0))


def serialize_activity(
    session: ActivitySession,
    overlapping_ids: Optional[Set[str]] = None,
    now_utc: Optional[datetime] = None,
) -> ActivityResponse:
    elapsed = compute_elapsed_seconds(session, now_utc)
    duration_mins = (
        session.duration_minutes
        if session.timer_status == "completed" and session.duration_minutes > 0
        else max(0, int(round(elapsed / 60.0)))
    )
    tags = [t.strip() for t in (session.tags_csv or "").split(",") if t.strip()]
    return ActivityResponse(
        id=session.id,
        activity_name=session.activity_name,
        category=session.category,
        project=session.project,
        session_date=session.session_date,
        start_time=session.start_time,
        end_time=session.end_time,
        duration_minutes=duration_mins,
        elapsed_seconds=elapsed,
        timer_status=session.timer_status,
        last_resumed_at=session.last_resumed_at,
        planned_duration_minutes=session.planned_duration_minutes,
        is_focus_session=session.is_focus_session,
        has_overlap=(session.id in overlapping_ids) if overlapping_ids else False,
        notes=session.notes,
        tags=tags,
        source=session.source,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def get_active_timer(db: Session) -> Optional[ActivitySession]:
    stmt = (
        select(ActivitySession)
        .where(ActivitySession.timer_status.in_(["running", "paused"]))
        .order_by(ActivitySession.start_time.desc())
    )
    return db.execute(stmt).scalars().first()


def start_focus_timer(db: Session, payload: TimerStartRequest) -> ActivityResponse:
    existing = get_active_timer(db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active timer ('{existing.activity_name}') is already {existing.timer_status}. Stop or complete it before starting a new timer.",
        )

    now_utc = datetime.now(timezone.utc)
    tags_csv = ",".join(t.strip() for t in payload.tags if t.strip()) or None
    session = ActivitySession(
        activity_name=payload.activity_name.strip(),
        category=payload.category.strip(),
        project=payload.project.strip() if payload.project else None,
        session_date=now_utc.date(),
        start_time=now_utc,
        end_time=None,
        duration_minutes=0,
        accumulated_seconds=0,
        timer_status="running",
        last_resumed_at=now_utc,
        planned_duration_minutes=payload.planned_duration_minutes,
        is_focus_session=payload.is_focus_session,
        notes=payload.notes,
        tags_csv=tags_csv,
        source="focus_timer",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return serialize_activity(session, now_utc=now_utc)


def pause_focus_timer(db: Session, session_id: Optional[str] = None) -> ActivityResponse:
    session = (
        db.execute(select(ActivitySession).where(ActivitySession.id == session_id)).scalar_one_or_none()
        if session_id
        else get_active_timer(db)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active timer found to pause.")
    if session.timer_status != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Timer cannot be paused because its status is '{session.timer_status}'.",
        )

    now_utc = datetime.now(timezone.utc)
    elapsed = compute_elapsed_seconds(session, now_utc)
    session.accumulated_seconds = elapsed
    session.duration_minutes = max(0, int(round(elapsed / 60.0)))
    session.last_resumed_at = None
    session.timer_status = "paused"
    db.commit()
    db.refresh(session)
    return serialize_activity(session, now_utc=now_utc)


def resume_focus_timer(db: Session, session_id: Optional[str] = None) -> ActivityResponse:
    session = (
        db.execute(select(ActivitySession).where(ActivitySession.id == session_id)).scalar_one_or_none()
        if session_id
        else get_active_timer(db)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No paused timer found to resume.")
    if session.timer_status != "paused":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Timer cannot be resumed because its status is '{session.timer_status}'.",
        )

    now_utc = datetime.now(timezone.utc)
    session.last_resumed_at = now_utc
    session.timer_status = "running"
    db.commit()
    db.refresh(session)
    return serialize_activity(session, now_utc=now_utc)


def stop_focus_timer(db: Session, session_id: Optional[str] = None, notes: Optional[str] = None) -> ActivityResponse:
    session = (
        db.execute(select(ActivitySession).where(ActivitySession.id == session_id)).scalar_one_or_none()
        if session_id
        else get_active_timer(db)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active timer found to stop.")
    if session.timer_status == "completed":
        return serialize_activity(session)

    now_utc = datetime.now(timezone.utc)
    elapsed = compute_elapsed_seconds(session, now_utc)
    session.accumulated_seconds = elapsed
    session.duration_minutes = max(1, int(round(elapsed / 60.0)))
    session.end_time = now_utc
    session.last_resumed_at = None
    session.timer_status = "completed"
    if notes is not None:
        session.notes = notes
    db.commit()
    db.refresh(session)
    return serialize_activity(session, now_utc=now_utc)


def create_manual_activity(db: Session, payload: ActivityCreate) -> ActivityResponse:
    st = _ensure_utc(payload.start_time) or datetime.now(timezone.utc)
    et = _ensure_utc(payload.end_time)
    duration = payload.duration_minutes
    if duration is None:
        if et and et > st:
            duration = max(1, int(round((et - st).total_seconds() / 60.0)))
        else:
            duration = 30
            et = st + timedelta(minutes=duration)
    elif et is None:
        et = st + timedelta(minutes=duration)

    tags_csv = ",".join(t.strip() for t in payload.tags if t.strip()) or None
    session = ActivitySession(
        activity_name=payload.activity_name.strip(),
        category=payload.category.strip(),
        project=payload.project.strip() if payload.project else None,
        session_date=payload.session_date,
        start_time=st,
        end_time=et,
        duration_minutes=duration,
        accumulated_seconds=duration * 60,
        timer_status="completed",
        planned_duration_minutes=payload.planned_duration_minutes,
        is_focus_session=payload.is_focus_session,
        notes=payload.notes,
        tags_csv=tags_csv,
        source=payload.source,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    day_sessions = db.execute(
        select(ActivitySession).where(ActivitySession.session_date == session.session_date)
    ).scalars().all()
    overlaps = detect_overlapping_session_ids(list(day_sessions))
    return serialize_activity(session, overlapping_ids=overlaps)


def update_activity_session(
    db: Session, session: ActivitySession, payload: ActivityUpdate
) -> ActivityResponse:
    data = payload.model_dump(exclude_unset=True)
    if "tags" in data:
        tags_list = data.pop("tags") or []
        session.tags_csv = ",".join(t.strip() for t in tags_list if t.strip()) or None

    for k, v in data.items():
        setattr(session, k, v)

    if session.start_time and session.end_time and "duration_minutes" not in data:
        st = _ensure_utc(session.start_time)
        et = _ensure_utc(session.end_time)
        if st and et and et > st:
            session.duration_minutes = max(1, int(round((et - st).total_seconds() / 60.0)))
            session.accumulated_seconds = session.duration_minutes * 60
    elif "duration_minutes" in data and data["duration_minutes"] is not None:
        session.accumulated_seconds = int(data["duration_minutes"]) * 60

    db.commit()
    db.refresh(session)

    day_sessions = db.execute(
        select(ActivitySession).where(ActivitySession.session_date == session.session_date)
    ).scalars().all()
    overlaps = detect_overlapping_session_ids(list(day_sessions))
    return serialize_activity(session, overlapping_ids=overlaps)


def get_activities_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    today = date.today()
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=6)

    sessions = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= start_date,
            ActivitySession.session_date <= end_date,
        )
    ).scalars().all()

    overlaps = detect_overlapping_session_ids(list(sessions))
    total_recorded_minutes = sum(
        s.duration_minutes if s.timer_status == "completed" else max(0, int(round(compute_elapsed_seconds(s) / 60.0)))
        for s in sessions
    )
    unique_clock_minutes = calculate_unique_clock_minutes(list(sessions))
    focus_sessions = [s for s in sessions if s.is_focus_session]
    focus_recorded_minutes = sum(
        s.duration_minutes if s.timer_status == "completed" else max(0, int(round(compute_elapsed_seconds(s) / 60.0)))
        for s in focus_sessions
    )
    focus_unique_minutes = calculate_unique_clock_minutes(focus_sessions)

    category_totals: Dict[str, int] = {}
    project_totals: Dict[str, int] = {}
    daily_map: Dict[str, List[ActivitySession]] = {}

    for s in sessions:
        mins = (
            s.duration_minutes
            if s.timer_status == "completed"
            else max(0, int(round(compute_elapsed_seconds(s) / 60.0)))
        )
        category_totals[s.category] = category_totals.get(s.category, 0) + mins
        proj = s.project or "Unassigned"
        project_totals[proj] = project_totals.get(proj, 0) + mins
        d_iso = s.session_date.isoformat()
        daily_map.setdefault(d_iso, []).append(s)

    category_allocation = [
        {
            "category": cat,
            "duration_minutes": mins,
            "hours": round(mins / 60.0, 2),
            "percentage": round((mins / total_recorded_minutes) * 100.0, 1) if total_recorded_minutes > 0 else 0.0,
        }
        for cat, mins in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    project_allocation = [
        {
            "project": proj,
            "duration_minutes": mins,
            "hours": round(mins / 60.0, 2),
            "percentage": round((mins / total_recorded_minutes) * 100.0, 1) if total_recorded_minutes > 0 else 0.0,
        }
        for proj, mins in sorted(project_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    period_days = max(1, (end_date - start_date).days + 1)
    daily_series = []
    for i in range(period_days):
        d_iso = (start_date + timedelta(days=i)).isoformat()
        day_list = daily_map.get(d_iso, [])
        rec_mins = sum(
            s.duration_minutes if s.timer_status == "completed" else max(0, int(round(compute_elapsed_seconds(s) / 60.0)))
            for s in day_list
        )
        uniq_mins = calculate_unique_clock_minutes(day_list)
        foc_mins = calculate_unique_clock_minutes([s for s in day_list if s.is_focus_session])
        daily_series.append(
            {
                "date": d_iso,
                "recorded_minutes": rec_mins,
                "unique_clock_minutes": uniq_mins,
                "focus_minutes": foc_mins,
            }
        )

    active = get_active_timer(db)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_recorded_minutes": total_recorded_minutes,
        "unique_elapsed_clock_minutes": unique_clock_minutes,
        "overlap_minutes_deducted": max(0, total_recorded_minutes - unique_clock_minutes),
        "overlapping_sessions_count": len(overlaps),
        "focus_recorded_minutes": focus_recorded_minutes,
        "focus_unique_minutes": focus_unique_minutes,
        "focus_sessions_count": len(focus_sessions),
        "category_allocation": category_allocation,
        "project_allocation": project_allocation,
        "daily_series": daily_series,
        "active_timer": serialize_activity(active).model_dump(mode="json") if active else None,
    }

