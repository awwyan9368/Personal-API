import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ActivitySession,
    Goal,
    GoalHabitLink,
    GoalProgressEntry,
    HabitEntry,
    JournalEntry,
    Milestone,
    ScreenTimeSession,
    UserPreference,
    WellbeingRecord,
)
from app.schemas.api_schemas import (
    GoalCreate,
    GoalProgressCreate,
    GoalProgressResponse,
    GoalResponse,
    GoalUpdate,
    JournalCreate,
    JournalResponse,
    JournalUpdate,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    WellbeingCreate,
    WellbeingResponse,
)

TWO_PLACES = Decimal("0.01")


def _dec(val: Any) -> Decimal:
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ============================================================================
# GOALS & PROJECTS
# ============================================================================
def serialize_goal(goal: Goal, reference_today: Optional[date] = None) -> GoalResponse:
    today = reference_today or date.today()
    target = _dec(goal.target_value)
    current = _dec(goal.current_value)
    progress_pct = round(float((current / target) * Decimal("100.0")), 2) if target > Decimal("0.00") else 0.0
    progress_pct = min(100.0, max(0.0, progress_pct))

    days_remaining: Optional[int] = None
    expected_pace_pct: Optional[float] = None
    pace_status = "no_deadline"

    if goal.status == "completed" or current >= target:
        pace_status = "completed"
        if goal.target_date:
            days_remaining = (goal.target_date - today).days
    elif goal.target_date:
        days_remaining = (goal.target_date - today).days
        total_span = (goal.target_date - goal.start_date).days
        elapsed_span = (today - goal.start_date).days
        if total_span > 0:
            expected_pace_pct = round(min(100.0, max(0.0, (elapsed_span / total_span) * 100.0)), 2)
        else:
            expected_pace_pct = 100.0 if today >= goal.target_date else 0.0

        if days_remaining < 0 and progress_pct < 100.0:
            pace_status = "behind"
        elif expected_pace_pct is not None:
            diff = progress_pct - expected_pace_pct
            if diff >= 5.0:
                pace_status = "ahead"
            elif diff <= -10.0:
                pace_status = "behind"
            else:
                pace_status = "on_track"

    habit_ids = [h.strip() for h in (goal.related_habit_ids_csv or "").split(",") if h.strip()]
    milestones = [MilestoneResponse.model_validate(m) for m in goal.milestones]
    progress_entries = [GoalProgressResponse.model_validate(p) for p in goal.progress_entries]

    return GoalResponse(
        id=goal.id,
        name=goal.name,
        description=goal.description,
        category=goal.category,
        project=goal.project,
        target_value=target,
        current_value=current,
        progress_percent=progress_pct,
        unit=goal.unit,
        start_date=goal.start_date,
        target_date=goal.target_date,
        days_remaining=days_remaining,
        expected_pace_percent=expected_pace_pct,
        pace_status=pace_status,
        status=goal.status,
        notes=goal.notes,
        related_habit_ids=habit_ids,
        milestones=milestones,
        progress_entries=progress_entries,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def create_goal(db: Session, payload: GoalCreate) -> GoalResponse:
    habit_csv = ",".join(h.strip() for h in payload.related_habit_ids if h.strip()) or None
    status_val = payload.status
    if payload.current_value >= payload.target_value and status_val == "active":
        status_val = "completed"

    goal = Goal(
        name=payload.name.strip(),
        description=payload.description,
        category=payload.category.strip(),
        project=payload.project.strip() if payload.project else None,
        target_value=_dec(payload.target_value),
        current_value=_dec(payload.current_value),
        unit=payload.unit.strip(),
        start_date=payload.start_date,
        target_date=payload.target_date,
        status=status_val,
        notes=payload.notes,
        related_habit_ids_csv=habit_csv,
    )
    db.add(goal)
    db.flush()

    if payload.current_value > Decimal("0.00"):
        init_entry = GoalProgressEntry(
            goal_id=goal.id,
            entry_date=payload.start_date,
            value_delta=_dec(payload.current_value),
            new_total=_dec(payload.current_value),
            notes="Initial progress recorded on goal creation",
            source="manual",
        )
        db.add(init_entry)

    for idx, ms in enumerate(payload.milestones):
        milestone = Milestone(
            goal_id=goal.id,
            title=ms.title.strip(),
            target_value=_dec(ms.target_value) if ms.target_value is not None else None,
            target_date=ms.target_date,
            is_completed=ms.is_completed,
            completed_at=datetime.now(timezone.utc) if ms.is_completed else None,
            sort_order=ms.sort_order if ms.sort_order else idx,
        )
        db.add(milestone)

    for hid in payload.related_habit_ids:
        hid = hid.strip()
        if hid:
            link = GoalHabitLink(goal_id=goal.id, habit_id=hid)
            db.add(link)

    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)


def update_goal(db: Session, goal: Goal, payload: GoalUpdate) -> GoalResponse:
    data = payload.model_dump(exclude_unset=True)
    if "related_habit_ids" in data:
        hids = data.pop("related_habit_ids") or []
        goal.related_habit_ids_csv = ",".join(h.strip() for h in hids if h.strip()) or None
        # Sync GoalHabitLink records
        for link in list(goal.habit_links):
            db.delete(link)
        db.flush()
        for hid in hids:
            if hid.strip():
                db.add(GoalHabitLink(goal_id=goal.id, habit_id=hid.strip()))

    if "target_value" in data and data["target_value"] is not None:
        data["target_value"] = _dec(data["target_value"])
    if "current_value" in data and data["current_value"] is not None:
        data["current_value"] = _dec(data["current_value"])

    for k, v in data.items():
        setattr(goal, k, v)

    if _dec(goal.current_value) >= _dec(goal.target_value) and goal.status == "active":
        goal.status = "completed"

    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)


def log_goal_progress(db: Session, goal: Goal, payload: GoalProgressCreate) -> GoalResponse:
    current = _dec(goal.current_value)
    if payload.new_total is not None:
        new_tot = _dec(payload.new_total)
        delta = (new_tot - current).quantize(TWO_PLACES)
    elif payload.value_delta is not None:
        delta = _dec(payload.value_delta)
        new_tot = max(Decimal("0.00"), (current + delta).quantize(TWO_PLACES))
    else:
        delta = Decimal("1.00")
        new_tot = (current + delta).quantize(TWO_PLACES)

    entry = GoalProgressEntry(
        goal_id=goal.id,
        entry_date=payload.entry_date,
        value_delta=delta,
        new_total=new_tot,
        notes=payload.notes,
        source=payload.source,
    )
    db.add(entry)
    goal.current_value = new_tot

    # Auto-complete milestones whose target_value is reached
    now_utc = datetime.now(timezone.utc)
    for ms in goal.milestones:
        if not ms.is_completed and ms.target_value is not None and new_tot >= _dec(ms.target_value):
            ms.is_completed = True
            ms.completed_at = now_utc

    if new_tot >= _dec(goal.target_value) and goal.status == "active":
        goal.status = "completed"

    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)


def add_goal_milestone(db: Session, goal: Goal, payload: MilestoneCreate) -> MilestoneResponse:
    ms = Milestone(
        goal_id=goal.id,
        title=payload.title.strip(),
        target_value=_dec(payload.target_value) if payload.target_value is not None else None,
        target_date=payload.target_date,
        is_completed=payload.is_completed,
        completed_at=datetime.now(timezone.utc) if payload.is_completed else None,
        sort_order=payload.sort_order,
    )
    db.add(ms)
    db.commit()
    db.refresh(ms)
    return MilestoneResponse.model_validate(ms)


def update_goal_milestone(db: Session, ms: Milestone, payload: MilestoneUpdate) -> MilestoneResponse:
    data = payload.model_dump(exclude_unset=True)
    if "is_completed" in data and data["is_completed"] is not None:
        if data["is_completed"] and not ms.is_completed:
            ms.completed_at = datetime.now(timezone.utc)
        elif not data["is_completed"]:
            ms.completed_at = None

    for k, v in data.items():
        setattr(ms, k, v)

    db.commit()
    db.refresh(ms)
    return MilestoneResponse.model_validate(ms)


# ============================================================================
# WELLBEING (HEALTH, SLEEP, MOOD, ENERGY)
# ============================================================================
def serialize_wellbeing(record: WellbeingRecord) -> WellbeingResponse:
    custom: Dict[str, Any] = {}
    if record.custom_measurements_json:
        try:
            custom = json.loads(record.custom_measurements_json)
        except Exception:
            custom = {}
    return WellbeingResponse(
        id=record.id,
        record_date=record.record_date,
        sleep_duration_hours=_dec(record.sleep_duration_hours) if record.sleep_duration_hours is not None else None,
        bedtime=record.bedtime,
        wake_time=record.wake_time,
        sleep_quality=record.sleep_quality,
        mood_score=record.mood_score,
        energy_score=record.energy_score,
        exercise_duration_minutes=record.exercise_duration_minutes,
        exercise_type=record.exercise_type,
        water_intake_ml=record.water_intake_ml,
        weight_kg=_dec(record.weight_kg) if record.weight_kg is not None else None,
        custom_measurements=custom,
        notes=record.notes,
        recorded_at=record.recorded_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def upsert_wellbeing_record(db: Session, payload: WellbeingCreate) -> WellbeingResponse:
    existing = db.execute(
        select(WellbeingRecord).where(WellbeingRecord.record_date == payload.record_date)
    ).scalar_one_or_none()

    custom_json = json.dumps(payload.custom_measurements) if payload.custom_measurements is not None else None

    if existing:
        data = payload.model_dump(exclude_unset=True, exclude={"custom_measurements"})
        for k, v in data.items():
            if v is not None:
                setattr(existing, k, v)
        if custom_json is not None:
            existing.custom_measurements_json = custom_json
        existing.updated_at = datetime.now(timezone.utc)
        rec = existing
    else:
        rec = WellbeingRecord(
            record_date=payload.record_date,
            sleep_duration_hours=payload.sleep_duration_hours,
            bedtime=payload.bedtime,
            wake_time=payload.wake_time,
            sleep_quality=payload.sleep_quality,
            mood_score=payload.mood_score,
            energy_score=payload.energy_score,
            exercise_duration_minutes=payload.exercise_duration_minutes,
            exercise_type=payload.exercise_type,
            water_intake_ml=payload.water_intake_ml,
            weight_kg=payload.weight_kg,
            custom_measurements_json=custom_json,
            notes=payload.notes,
        )
        db.add(rec)

    db.commit()
    db.refresh(rec)
    return serialize_wellbeing(rec)


def get_wellbeing_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    today = date.today()
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=29)

    records = db.execute(
        select(WellbeingRecord)
        .where(
            WellbeingRecord.record_date >= start_date,
            WellbeingRecord.record_date <= end_date,
        )
        .order_by(WellbeingRecord.record_date.asc())
    ).scalars().all()

    sleep_vals = [float(r.sleep_duration_hours) for r in records if r.sleep_duration_hours is not None]
    quality_vals = [r.sleep_quality for r in records if r.sleep_quality is not None]
    mood_vals = [r.mood_score for r in records if r.mood_score is not None]
    energy_vals = [r.energy_score for r in records if r.energy_score is not None]
    exercise_vals = [r.exercise_duration_minutes for r in records if r.exercise_duration_minutes is not None]
    water_vals = [r.water_intake_ml for r in records if r.water_intake_ml is not None]

    # Empirical cross-domain associations (Focus time & Screen time on high vs low sleep/energy days)
    focus_sessions = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= start_date,
            ActivitySession.session_date <= end_date,
            ActivitySession.is_focus_session == True,  # noqa: E712
        )
    ).scalars().all()
    focus_by_date: Dict[date, int] = {}
    for fs in focus_sessions:
        focus_by_date[fs.session_date] = focus_by_date.get(fs.session_date, 0) + fs.duration_minutes

    screen_sessions = db.execute(
        select(ScreenTimeSession).where(
            ScreenTimeSession.session_date >= start_date,
            ScreenTimeSession.session_date <= end_date,
        )
    ).scalars().all()
    screen_by_date: Dict[date, int] = {}
    for ss in screen_sessions:
        screen_by_date[ss.session_date] = screen_by_date.get(ss.session_date, 0) + ss.duration_minutes

    habit_entries = db.execute(
        select(HabitEntry).where(
            HabitEntry.entry_date >= start_date,
            HabitEntry.entry_date <= end_date,
            HabitEntry.completed == True,  # noqa: E712
        )
    ).scalars().all()
    habits_by_date: Dict[date, int] = {}
    for he in habit_entries:
        habits_by_date[he.entry_date] = habits_by_date.get(he.entry_date, 0) + 1

    daily_series = []
    for r in records:
        d = r.record_date
        daily_series.append(
            {
                "date": d.isoformat(),
                "sleep_hours": float(r.sleep_duration_hours) if r.sleep_duration_hours is not None else None,
                "sleep_quality": r.sleep_quality,
                "mood_score": r.mood_score,
                "energy_score": r.energy_score,
                "exercise_minutes": r.exercise_duration_minutes,
                "water_ml": r.water_intake_ml,
                "weight_kg": float(r.weight_kg) if r.weight_kg is not None else None,
                "focus_minutes": focus_by_date.get(d, 0),
                "screen_time_minutes": screen_by_date.get(d, 0),
                "habits_completed": habits_by_date.get(d, 0),
            }
        )

    # Compute transparent observation when >= 3 days exist in both buckets
    rested_focus = [
        focus_by_date.get(r.record_date, 0)
        for r in records
        if r.sleep_duration_hours is not None and float(r.sleep_duration_hours) >= 7.0
    ]
    short_sleep_focus = [
        focus_by_date.get(r.record_date, 0)
        for r in records
        if r.sleep_duration_hours is not None and float(r.sleep_duration_hours) < 7.0
    ]

    correlations = []
    if len(rested_focus) >= 2 and len(short_sleep_focus) >= 2:
        avg_rested = round(sum(rested_focus) / len(rested_focus), 1)
        avg_short = round(sum(short_sleep_focus) / len(short_sleep_focus), 1)
        correlations.append(
            {
                "metric_a": "Sleep Duration (>= 7h vs < 7h)",
                "metric_b": "Daily Focus Minutes",
                "avg_when_high": avg_rested,
                "avg_when_low": avg_short,
                "sample_days": len(rested_focus) + len(short_sleep_focus),
                "note": "Observational association in your local records; correlation does not imply causation.",
            }
        )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "recorded_days": len(records),
        "averages": {
            "sleep_duration_hours": round(sum(sleep_vals) / len(sleep_vals), 2) if sleep_vals else None,
            "sleep_quality": round(sum(quality_vals) / len(quality_vals), 1) if quality_vals else None,
            "mood_score": round(sum(mood_vals) / len(mood_vals), 1) if mood_vals else None,
            "energy_score": round(sum(energy_vals) / len(energy_vals), 1) if energy_vals else None,
            "exercise_duration_minutes": round(sum(exercise_vals) / len(exercise_vals), 1) if exercise_vals else None,
            "water_intake_ml": round(sum(water_vals) / len(water_vals), 0) if water_vals else None,
        },
        "total_exercise_minutes": sum(exercise_vals) if exercise_vals else 0,
        "daily_series": daily_series,
        "correlations": correlations,
        "disclaimer": "Wellbeing metrics are for personal self-reflection only and do not constitute medical advice.",
    }


# ============================================================================
# PRIVATE JOURNAL & DAILY REVIEW
# ============================================================================
def serialize_journal(entry: JournalEntry) -> JournalResponse:
    tags = [t.strip() for t in (entry.tags_csv or "").split(",") if t.strip()]
    return JournalResponse(
        id=entry.id,
        entry_date=entry.entry_date,
        title=entry.title,
        content=entry.content,
        daily_intention=entry.daily_intention,
        highlights=entry.highlights,
        lessons_learned=entry.lessons_learned,
        areas_to_improve=entry.areas_to_improve,
        tomorrow_focus=entry.tomorrow_focus,
        review_accomplishments=entry.review_accomplishments,
        review_time_spent=entry.review_time_spent,
        review_money_spent=entry.review_money_spent,
        review_energy_notes=entry.review_energy_notes,
        review_went_well=entry.review_went_well,
        review_could_improve=entry.review_could_improve,
        mood_reference=entry.mood_reference,
        energy_reference=entry.energy_reference,
        tags=tags,
        is_daily_review=entry.is_daily_review,
        recorded_at=entry.recorded_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def create_journal_entry(db: Session, payload: JournalCreate) -> JournalResponse:
    tags_csv = ",".join(t.strip() for t in payload.tags if t.strip()) or None
    is_review = payload.is_daily_review or any(
        [
            payload.review_accomplishments,
            payload.review_time_spent,
            payload.review_money_spent,
            payload.review_went_well,
            payload.review_could_improve,
        ]
    )
    entry = JournalEntry(
        entry_date=payload.entry_date,
        title=payload.title,
        content=payload.content,
        daily_intention=payload.daily_intention,
        highlights=payload.highlights,
        lessons_learned=payload.lessons_learned,
        areas_to_improve=payload.areas_to_improve,
        tomorrow_focus=payload.tomorrow_focus,
        review_accomplishments=payload.review_accomplishments,
        review_time_spent=payload.review_time_spent,
        review_money_spent=payload.review_money_spent,
        review_energy_notes=payload.review_energy_notes,
        review_went_well=payload.review_went_well,
        review_could_improve=payload.review_could_improve,
        mood_reference=payload.mood_reference,
        energy_reference=payload.energy_reference,
        tags_csv=tags_csv,
        is_daily_review=is_review,
    )
    db.add(entry)

    # Sync today's intention to UserPreference if set for today
    if payload.daily_intention and payload.entry_date == date.today():
        pref = db.execute(select(UserPreference)).scalar_one_or_none()
        if pref:
            pref.today_intention = payload.daily_intention
            pref.today_intention_date = payload.entry_date

    db.commit()
    db.refresh(entry)
    return serialize_journal(entry)


def update_journal_entry(db: Session, entry: JournalEntry, payload: JournalUpdate) -> JournalResponse:
    data = payload.model_dump(exclude_unset=True)
    if "tags" in data:
        tags_list = data.pop("tags") or []
        entry.tags_csv = ",".join(t.strip() for t in tags_list if t.strip()) or None

    for k, v in data.items():
        setattr(entry, k, v)

    db.commit()
    db.refresh(entry)
    return serialize_journal(entry)

