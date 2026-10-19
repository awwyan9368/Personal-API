from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Habit, HabitEntry, HabitSchedule, UserPreference
from app.schemas.api_schemas import HabitCreate, HabitEntryCreate, HabitEntryResponse, HabitResponse, HabitUpdate


def get_user_local_today(db: Session, override_tz: Optional[str] = None) -> date:
    tz_name = override_tz
    if not tz_name:
        pref = db.execute(select(UserPreference)).scalar_one_or_none()
        tz_name = pref.timezone if pref else "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        tz = timezone.utc
    return datetime.now(tz).date()


def parse_weekdays(weekdays_csv: str) -> Set[int]:
    if not weekdays_csv:
        return {0, 1, 2, 3, 4, 5, 6}
    result = set()
    for part in weekdays_csv.split(","):
        part = part.strip()
        if part.isdigit():
            val = int(part)
            if 0 <= val <= 6:
                result.add(val)
    return result or {0, 1, 2, 3, 4, 5, 6}


def is_date_scheduled(habit: Habit, check_date: date) -> bool:
    if check_date < habit.start_date:
        return False
    if habit.end_date and check_date > habit.end_date:
        return False
    if habit.frequency_type == "daily":
        return True
    if habit.frequency_type == "selected_weekdays":
        allowed = parse_weekdays(habit.selected_weekdays)
        return check_date.weekday() in allowed
    if habit.frequency_type == "weekly_target":
        # For weekly_target, any day in the week can contribute, or selected weekdays if restricted
        allowed = parse_weekdays(habit.selected_weekdays)
        return check_date.weekday() in allowed
    return True


def is_entry_Target_met(habit: Habit, entry: Optional[HabitEntry]) -> bool:
    if not entry:
        return False
    if habit.is_quantitative:
        return bool(entry.completed and Decimal(str(entry.value)) >= Decimal(str(habit.target_value)))
    return bool(entry.completed)


def calculate_habit_metrics(
    habit: Habit,
    entries: List[HabitEntry],
    reference_today: date,
) -> Dict[str, Any]:
    """
    Deterministic, timezone-aware habit streak and completion calculator.
    Rules:
    1. Only scheduled days (within start_date..end_date and matching frequency_type) are required.
    2. Unscheduled days do NOT break a streak; completions on unscheduled days still count as bonus if completed.
    3. Future dates (> reference_today) are NEVER treated as missed days.
    4. If reference_today is scheduled and not yet completed, current streak is preserved from yesterday.
    5. For weekly_target habits, a week meets its target if completed_days_in_week >= weekly_target.
    """
    entry_map: Dict[date, HabitEntry] = {e.entry_date: e for e in entries}
    completed_dates: Set[date] = {
        d for d, e in entry_map.items() if is_entry_Target_met(habit, e) and d <= reference_today
    }

    if reference_today < habit.start_date:
        return {
            "current_streak": 0,
            "best_streak": 0,
            "completion_rate_30d": 0.0,
            "completed_today": False,
            "today_value": Decimal("0.00"),
            "missed_scheduled_days_30d": 0,
            "missed_dates_30d": [],
        }

    effective_end = min(reference_today, habit.end_date) if habit.end_date else reference_today

    if habit.frequency_type == "weekly_target" and habit.weekly_target:
        # Weekly target streak: consecutive weeks meeting weekly_target or consecutive completed days
        # We compute scheduled-day streak where up to (7 - weekly_target) days per ISO week can be skipped without breaking streak
        current_streak = 0
        best_streak = 0
        running_streak = 0

        # Group dates by ISO year-week from start_date to effective_end
        total_days = (effective_end - habit.start_date).days + 1
        all_dates = [habit.start_date + timedelta(days=i) for i in range(max(0, total_days))]

        # Evaluate day by day with weekly allowance
        week_counts: Dict[Tuple[int, int], int] = {}
        for d in all_dates:
            if d in completed_dates:
                iso_yw = d.isocalendar()[:2]
                week_counts[iso_yw] = week_counts.get(iso_yw, 0) + 1

        for d in all_dates:
            iso_yw = d.isocalendar()[:2]
            if d in completed_dates:
                running_streak += 1
                best_streak = max(best_streak, running_streak)
            else:
                # Does this week still meet the weekly target, or is this the current ongoing week?
                current_iso = effective_end.isocalendar()[:2]
                if week_counts.get(iso_yw, 0) >= habit.weekly_target:
                    # Unscheduled rest day in a target-met week does not break streak
                    continue
                elif iso_yw == current_iso:
                    # Check if remaining days in the current week + completed days can still meet weekly_target
                    days_left_in_week = 6 - d.weekday() + (1 if d == effective_end else 0)
                    if week_counts.get(iso_yw, 0) + days_left_in_week >= habit.weekly_target:
                        continue
                    else:
                        running_streak = 0
                else:
                    running_streak = 0
        current_streak = running_streak
    else:
        # Standard daily or selected_weekdays schedule
        total_days = (effective_end - habit.start_date).days + 1
        all_dates = [habit.start_date + timedelta(days=i) for i in range(max(0, total_days))]

        best_streak = 0
        running_streak = 0
        for d in all_dates:
            scheduled = is_date_scheduled(habit, d)
            completed = d in completed_dates
            if completed:
                running_streak += 1
                best_streak = max(best_streak, running_streak)
            elif scheduled:
                if d == reference_today:
                    # Today is not over yet; don't break running streak if yesterday was intact
                    continue
                running_streak = 0
            else:
                # Unscheduled day: does not break streak
                continue

        current_streak = running_streak

    # 30-day window completion rate and missed days (excluding today if not completed yet for missed_dates,
    # or computing rate over scheduled days up to effective_end)
    window_start = max(habit.start_date, effective_end - timedelta(days=29))
    scheduled_in_window = 0
    completed_in_window = 0
    missed_dates_30d: List[str] = []

    if window_start <= effective_end:
        win_days = (effective_end - window_start).days + 1
        for i in range(win_days):
            d = window_start + timedelta(days=i)
            sched = is_date_scheduled(habit, d)
            comp = d in completed_dates
            if sched:
                if d == reference_today and not comp:
                    # Don't penalize today as missed before the day ends unless it's the only day
                    continue
                scheduled_in_window += 1
                if comp:
                    completed_in_window += 1
                else:
                    missed_dates_30d.append(d.isoformat())

    if habit.frequency_type == "weekly_target" and habit.weekly_target:
        # Adjust completion rate relative to weekly target over the window
        weeks_in_window = max(1.0, ((effective_end - window_start).days + 1) / 7.0)
        expected_completions = min(scheduled_in_window or 1, int(round(weeks_in_window * habit.weekly_target)))
        completion_rate = min(100.0, round(( len([d for d in completed_dates if window_start <= d <= effective_end]) / max(1, expected_completions)) * 100.0, 1))
    else:
        if scheduled_in_window > 0:
            completion_rate = round((completed_in_window / scheduled_in_window) * 100.0, 1)
        elif reference_today in completed_dates:
            completion_rate = 100.0
        else:
            completion_rate = 0.0

    today_entry = entry_map.get(reference_today)
    completed_today = is_entry_Target_met(habit, today_entry)
    today_value = Decimal(str(today_entry.value)) if today_entry else Decimal("0.00")

    return {
        "current_streak": current_streak,
        "best_streak": best_streak,
        "completion_rate_30d": completion_rate,
        "completed_today": completed_today,
        "today_value": today_value,
        "missed_scheduled_days_30d": len(missed_dates_30d),
        "missed_dates_30d": missed_dates_30d,
    }


def serialize_habit(db: Session, habit: Habit, reference_today: Optional[date] = None) -> HabitResponse:
    local_today = reference_today or get_user_local_today(db)
    entries = list(habit.entries)
    entries.sort(key=lambda e: e.entry_date, reverse=True)
    metrics = calculate_habit_metrics(habit, entries, local_today)
    weekdays_list = sorted(parse_weekdays(habit.selected_weekdays))

    recent_entries = [HabitEntryResponse.model_validate(e) for e in entries[:60]]

    return HabitResponse(
        id=habit.id,
        name=habit.name,
        description=habit.description,
        category=habit.category,
        icon=habit.icon,
        accent_color=habit.accent_color,
        frequency_type=habit.frequency_type,
        selected_weekdays=weekdays_list,
        weekly_target=habit.weekly_target,
        target_value=Decimal(str(habit.target_value)),
        unit=habit.unit,
        is_quantitative=habit.is_quantitative,
        start_date=habit.start_date,
        end_date=habit.end_date,
        reminder_preference=habit.reminder_preference,
        status=habit.status,
        current_streak=metrics["current_streak"],
        best_streak=metrics["best_streak"],
        completion_rate_30d=metrics["completion_rate_30d"],
        completed_today=metrics["completed_today"],
        today_value=metrics["today_value"],
        missed_scheduled_days_30d=metrics["missed_scheduled_days_30d"],
        recent_entries=recent_entries,
        created_at=habit.created_at,
        updated_at=habit.updated_at,
    )


def create_habit(db: Session, payload: HabitCreate) -> HabitResponse:
    weekdays_str = ",".join(str(d) for d in sorted(set(payload.selected_weekdays)))
    habit = Habit(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        icon=payload.icon,
        accent_color=payload.accent_color,
        frequency_type=payload.frequency_type,
        selected_weekdays=weekdays_str,
        weekly_target=payload.weekly_target,
        target_value=payload.target_value,
        unit=payload.unit,
        is_quantitative=payload.is_quantitative,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reminder_preference=payload.reminder_preference,
        status=payload.status,
    )
    db.add(habit)
    db.flush()

    schedule = HabitSchedule(
        habit_id=habit.id,
        frequency_type=habit.frequency_type,
        selected_weekdays=weekdays_str,
        weekly_target=habit.weekly_target,
        effective_from=habit.start_date,
        effective_to=habit.end_date,
    )
    db.add(schedule)
    db.commit()
    db.refresh(habit)
    return serialize_habit(db, habit)


def update_habit(db: Session, habit: Habit, payload: HabitUpdate) -> HabitResponse:
    data = payload.model_dump(exclude_unset=True)
    if "selected_weekdays" in data and data["selected_weekdays"] is not None:
        data["selected_weekdays"] = ",".join(str(d) for d in sorted(set(data["selected_weekdays"])))

    for k, v in data.items():
        setattr(habit, k, v)

    db.commit()
    db.refresh(habit)
    return serialize_habit(db, habit)


def log_habit_entry(db: Session, habit: Habit, payload: HabitEntryCreate) -> HabitEntry:
    local_today = get_user_local_today(db)
    is_historical = payload.is_historical_correction or (payload.entry_date < local_today)

    # Determine completion based on quantitative target if applicable
    completed = payload.completed
    if habit.is_quantitative:
        if payload.value >= habit.target_value and payload.completed:
            completed = True
        elif payload.value < habit.target_value:
            completed = False

    stmt = select(HabitEntry).where(
        HabitEntry.habit_id == habit.id,
        HabitEntry.entry_date == payload.entry_date,
    )
    existing = db.execute(stmt).scalar_one_or_none()

    now_utc = datetime.now(timezone.utc)
    if existing:
        existing.completed = completed
        existing.value = payload.value
        existing.notes = payload.notes if payload.notes is not None else existing.notes
        existing.is_historical_correction = is_historical
        if payload.completed_at:
            existing.completed_at = payload.completed_at
        existing.updated_at = now_utc
        entry = existing
    else:
        entry = HabitEntry(
            habit_id=habit.id,
            entry_date=payload.entry_date,
            completed=completed,
            value=payload.value,
            completed_at=payload.completed_at or now_utc,
            notes=payload.notes,
            is_historical_correction=is_historical,
        )
        db.add(entry)

    db.commit()
    db.refresh(entry)
    return entry

