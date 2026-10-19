import json
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ActivitySession,
    Budget,
    Goal,
    Habit,
    HabitEntry,
    InsightDismissal,
    JournalEntry,
    Milestone,
    ScreenTimeSession,
    Transaction,
    UserPreference,
    WellbeingRecord,
)
from app.services.activity_service import calculate_unique_clock_minutes, compute_elapsed_seconds, get_active_timer, serialize_activity
from app.services.finance_service import evaluate_budget, get_finance_summary, to_decimal
from app.services.goal_wellbeing_journal_service import serialize_goal, serialize_wellbeing
from app.services.habit_service import calculate_habit_metrics, is_date_scheduled, is_entry_Target_met, serialize_habit


def _get_tz(db: Session) -> Tuple[ZoneInfo, str]:
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    tz_name = pref.timezone if pref else "Asia/Kolkata"
    try:
        return ZoneInfo(tz_name), tz_name
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC"), "UTC"


def _build_comparison(
    current_val: float,
    prev_val: float,
    has_prev_records: bool,
    unit: str,
    label: str,
) -> Dict[str, Any]:
    abs_change = round(current_val - prev_val, 2)
    if not has_prev_records:
        return {
            "current_value": round(current_val, 2),
            "previous_value": None,
            "absolute_change": None,
            "percentage_change": None,
            "unit": unit,
            "comparison_label": label,
            "has_sufficient_previous_data": False,
            "explanation": f"No recorded data in the comparison period ({label}); percentage change omitted to avoid misleading metrics.",
        }
    if prev_val == 0:
        return {
            "current_value": round(current_val, 2),
            "previous_value": 0.0,
            "absolute_change": abs_change,
            "percentage_change": None,
            "unit": unit,
            "comparison_label": label,
            "has_sufficient_previous_data": False,
            "explanation": f"Previous period ({label}) recorded 0 {unit}; absolute change is {abs_change:+.2f} {unit} (percentage undefined from zero baseline).",
        }
    pct_change = round(((current_val - prev_val) / prev_val) * 100.0, 1)
    return {
        "current_value": round(current_val, 2),
        "previous_value": round(prev_val, 2),
        "absolute_change": abs_change,
        "percentage_change": pct_change,
        "unit": unit,
        "comparison_label": label,
        "has_sufficient_previous_data": True,
        "explanation": f"{abs_change:+.2f} {unit} ({pct_change:+.1f}%) compared with {label}.",
    }


def get_dashboard_overview(db: Session, ref_date: Optional[date] = None) -> Dict[str, Any]:
    tz, tz_name = _get_tz(db)
    now_local = datetime.now(tz)
    today = ref_date or now_local.date()
    yesterday = today - timedelta(days=1)

    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    preferred_name = pref.preferred_name if pref else "Builder"
    currency = (pref.base_currency if pref else "INR").upper()
    screen_target = pref.daily_screen_time_target_minutes if pref else 240

    hour = now_local.hour
    if hour < 12:
        greeting = f"Good morning, {preferred_name}"
    elif hour < 17:
        greeting = f"Good afternoon, {preferred_name}"
    else:
        greeting = f"Good evening, {preferred_name}"

    # Today's intention from preferences or today's journal entry
    today_journal = db.execute(
        select(JournalEntry).where(JournalEntry.entry_date == today).order_by(JournalEntry.created_at.desc())
    ).scalars().first()
    intention = (
        (today_journal.daily_intention if today_journal and today_journal.daily_intention else None)
        or (pref.today_intention if pref and pref.today_intention_date == today else None)
        or (pref.today_intention if pref else None)
    )

    # 1. Habits
    active_habits = db.execute(select(Habit).where(Habit.status == "active")).scalars().all()
    serialized_habits = [serialize_habit(db, h, today) for h in active_habits]
    scheduled_today = [h for h in active_habits if is_date_scheduled(h, today)]
    completed_today_count = sum(1 for sh in serialized_habits if sh.completed_today)
    scheduled_today_count = len(scheduled_today)
    today_habit_rate = (
        round((completed_today_count / scheduled_today_count) * 100.0, 1)
        if scheduled_today_count > 0
        else (100.0 if completed_today_count > 0 else None)
    )
    top_streak = max((sh.current_streak for sh in serialized_habits), default=0)
    active_streaks_count = sum(1 for sh in serialized_habits if sh.current_streak > 0)

    # Yesterday habit rate
    sched_yest = [h for h in active_habits if is_date_scheduled(h, yesterday)]
    comp_yest = 0
    for h in sched_yest:
        e_map = {e.entry_date: e for e in h.entries}
        if is_entry_Target_met(h, e_map.get(yesterday)):
            comp_yest += 1
    yest_habit_rate = round((comp_yest / len(sched_yest)) * 100.0, 1) if sched_yest else 0.0

    # 2. Finance (Current Month vs Last Month, This Year vs Last Year)
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    fin_summary = get_finance_summary(db, month_start, month_end, currency)

    last_month_end = month_start - timedelta(days=1)
    last_month_start = date(last_month_end.year, last_month_end.month, 1)
    prev_month_txs = db.execute(
        select(Transaction).where(
            Transaction.transaction_date >= last_month_start,
            Transaction.transaction_date <= last_month_end,
            Transaction.currency == currency,
        )
    ).scalars().all()
    prev_month_exp = float(
        sum((to_decimal(t.amount) for t in prev_month_txs if t.transaction_type == "expense"), Decimal("0.00"))
    )
    prev_month_inc = float(
        sum((to_decimal(t.amount) for t in prev_month_txs if t.transaction_type == "income"), Decimal("0.00"))
    )

    # Budget utilization
    budgets_list = fin_summary["budgets"]
    overall_budget = next((b for b in budgets_list if b["category"].upper() == "ALL"), None)
    if overall_budget:
        budget_util_pct = overall_budget["utilization_percent"]
        budget_limit_str = overall_budget["amount_limit"]
        budget_spent_str = overall_budget["spent_amount"]
    elif budgets_list:
        tot_lim = sum(Decimal(str(b["amount_limit"])) for b in budgets_list)
        tot_sp = sum(Decimal(str(b["spent_amount"])) for b in budgets_list)
        budget_util_pct = round(float((tot_sp / tot_lim) * Decimal("100.0")), 1) if tot_lim > 0 else 0.0
        budget_limit_str = str(tot_lim)
        budget_spent_str = str(tot_sp)
    else:
        budget_util_pct = None
        budget_limit_str = None
        budget_spent_str = fin_summary["total_expense"]

    # 3. Screen Time (Today vs Yesterday, This Week vs Last Week)
    today_st_sessions = db.execute(
        select(ScreenTimeSession).where(ScreenTimeSession.session_date == today)
    ).scalars().all()
    yest_st_sessions = db.execute(
        select(ScreenTimeSession).where(ScreenTimeSession.session_date == yesterday)
    ).scalars().all()
    today_screen_mins = sum(s.duration_minutes for s in today_st_sessions)
    yest_screen_mins = sum(s.duration_minutes for s in yest_st_sessions)

    # 4. Focus & Activity Time (Today vs Yesterday, This Week vs Last Week)
    today_acts = db.execute(
        select(ActivitySession).where(ActivitySession.session_date == today)
    ).scalars().all()
    yest_acts = db.execute(
        select(ActivitySession).where(ActivitySession.session_date == yesterday)
    ).scalars().all()
    today_focus_mins = calculate_unique_clock_minutes([a for a in today_acts if a.is_focus_session])
    yest_focus_mins = calculate_unique_clock_minutes([a for a in yest_acts if a.is_focus_session])
    today_activity_unique_mins = calculate_unique_clock_minutes(list(today_acts))
    today_activity_recorded_mins = sum(
        a.duration_minutes if a.timer_status == "completed" else max(0, int(round(compute_elapsed_seconds(a) / 60.0)))
        for a in today_acts
    )

    # Week vs Last Week comparisons (7-day rolling or current week)
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    week_acts = db.execute(
        select(ActivitySession).where(ActivitySession.session_date >= week_start, ActivitySession.session_date <= today)
    ).scalars().all()
    last_week_acts = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= last_week_start, ActivitySession.session_date <= last_week_end
        )
    ).scalars().all()
    week_focus_mins = calculate_unique_clock_minutes([a for a in week_acts if a.is_focus_session])
    last_week_focus_mins = calculate_unique_clock_minutes([a for a in last_week_acts if a.is_focus_session])

    # Year vs Last Year comparisons
    year_start = date(today.year, 1, 1)
    last_year_start = date(today.year - 1, 1, 1)
    last_year_end = date(today.year - 1, 12, 31)
    year_txs = db.execute(
        select(Transaction).where(
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= today,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
        )
    ).scalars().all()
    last_year_txs = db.execute(
        select(Transaction).where(
            Transaction.transaction_date >= last_year_start,
            Transaction.transaction_date <= last_year_end,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
        )
    ).scalars().all()
    year_exp = float(sum((to_decimal(t.amount) for t in year_txs), Decimal("0.00")))
    last_year_exp = float(sum((to_decimal(t.amount) for t in last_year_txs), Decimal("0.00")))

    # 5. Wellbeing (Sleep, Mood, Energy) — never silently convert missing data to 0!
    today_wb = db.execute(select(WellbeingRecord).where(WellbeingRecord.record_date == today)).scalar_one_or_none()
    latest_wb = db.execute(
        select(WellbeingRecord).order_by(WellbeingRecord.record_date.desc())
    ).scalars().first()

    # 6. Active Goals
    goals_db = db.execute(select(Goal).order_by(Goal.created_at.desc())).scalars().all()
    serialized_goals = [serialize_goal(g, today) for g in goals_db]
    active_goals = [g for g in serialized_goals if g.status == "active"]

    # 7. Recent Activity Feed (from timeline)
    timeline_preview = get_personal_timeline(db, limit=12)["events"]

    # 8. 14-day multi-metric chart series
    chart_start = today - timedelta(days=13)
    st_14d = db.execute(
        select(ScreenTimeSession).where(ScreenTimeSession.session_date >= chart_start, ScreenTimeSession.session_date <= today)
    ).scalars().all()
    act_14d = db.execute(
        select(ActivitySession).where(ActivitySession.session_date >= chart_start, ActivitySession.session_date <= today)
    ).scalars().all()
    wb_14d = db.execute(
        select(WellbeingRecord).where(WellbeingRecord.record_date >= chart_start, WellbeingRecord.record_date <= today)
    ).scalars().all()
    wb_map = {w.record_date: w for w in wb_14d}

    activity_trend_14d = []
    for i in range(14):
        d = chart_start + timedelta(days=i)
        d_iso = d.isoformat()
        day_acts = [a for a in act_14d if a.session_date == d]
        day_sts = [s for s in st_14d if s.session_date == d]
        wb_rec = wb_map.get(d)
        activity_trend_14d.append(
            {
                "date": d_iso,
                "focus_minutes": calculate_unique_clock_minutes([a for a in day_acts if a.is_focus_session]),
                "activity_minutes": calculate_unique_clock_minutes(day_acts),
                "screen_time_minutes": sum(s.duration_minutes for s in day_sts),
                "sleep_hours": float(wb_rec.sleep_duration_hours) if wb_rec and wb_rec.sleep_duration_hours is not None else None,
                "mood_score": wb_rec.mood_score if wb_rec else None,
                "energy_score": wb_rec.energy_score if wb_rec else None,
            }
        )

    widgets_order = [
        "habits",
        "streaks",
        "expenses",
        "income",
        "budget",
        "screen_time",
        "focus_time",
        "activity_time",
        "sleep",
        "mood_energy",
        "goals",
    ]
    if pref and pref.dashboard_widgets_json:
        try:
            parsed = json.loads(pref.dashboard_widgets_json)
            if isinstance(parsed, list) and parsed:
                widgets_order = parsed
        except Exception:
            pass

    active_timer = get_active_timer(db)

    return {
        "greeting": greeting,
        "current_date": today.isoformat(),
        "timezone": tz_name,
        "currency": currency,
        "today_intention": intention,
        "has_daily_checkin_today": today_wb is not None,
        "has_daily_review_today": bool(today_journal and today_journal.is_daily_review),
        "widgets_order": widgets_order,
        "active_timer": serialize_activity(active_timer).model_dump(mode="json") if active_timer else None,
        "metrics": {
            "habits_today": {
                "completed": completed_today_count,
                "scheduled": scheduled_today_count,
                "completion_rate_percent": today_habit_rate,
                "has_data": len(active_habits) > 0,
            },
            "habit_streaks": {
                "best_active_streak": top_streak,
                "active_streaks_count": active_streaks_count,
                "total_active_habits": len(active_habits),
            },
            "monthly_expenses": {
                "amount": fin_summary["total_expense"],
                "amount_numeric": fin_summary["total_expense_numeric"],
                "currency": currency,
            },
            "monthly_income": {
                "amount": fin_summary["total_income"],
                "amount_numeric": fin_summary["total_income_numeric"],
                "net_savings": fin_summary["net_savings"],
                "currency": currency,
            },
            "budget_utilization": {
                "utilization_percent": budget_util_pct,
                "spent_amount": budget_spent_str,
                "limit_amount": budget_limit_str,
                "alerts_count": len(fin_summary["budget_alerts"]),
                "alerts": fin_summary["budget_alerts"],
                "has_configured_budget": len(budgets_list) > 0,
            },
            "screen_time_today": {
                "minutes": today_screen_mins,
                "hours": round(today_screen_mins / 60.0, 2),
                "target_minutes": screen_target,
                "utilization_percent": round((today_screen_mins / screen_target) * 100.0, 1) if screen_target > 0 else 0.0,
                "has_recorded_today": len(today_st_sessions) > 0,
            },
            "focus_time_today": {
                "minutes": today_focus_mins,
                "hours": round(today_focus_mins / 60.0, 2),
                "sessions_count": sum(1 for a in today_acts if a.is_focus_session),
            },
            "activity_time_today": {
                "unique_clock_minutes": today_activity_unique_mins,
                "total_recorded_minutes": today_activity_recorded_mins,
                "sessions_count": len(today_acts),
            },
            "sleep": {
                "today_hours": float(today_wb.sleep_duration_hours) if today_wb and today_wb.sleep_duration_hours is not None else None,
                "today_quality": today_wb.sleep_quality if today_wb else None,
                "latest_hours": float(latest_wb.sleep_duration_hours) if latest_wb and latest_wb.sleep_duration_hours is not None else None,
                "latest_date": latest_wb.record_date.isoformat() if latest_wb else None,
                "status": "recorded_today" if (today_wb and today_wb.sleep_duration_hours is not None) else ("historical" if latest_wb else "no_data"),
            },
            "mood_energy": {
                "today_mood": today_wb.mood_score if today_wb else None,
                "today_energy": today_wb.energy_score if today_wb else None,
                "latest_mood": latest_wb.mood_score if latest_wb else None,
                "latest_energy": latest_wb.energy_score if latest_wb else None,
                "latest_date": latest_wb.record_date.isoformat() if latest_wb else None,
                "status": "recorded_today" if (today_wb and (today_wb.mood_score is not None or today_wb.energy_score is not None)) else ("historical" if latest_wb else "no_data"),
            },
            "goals": {
                "active_count": len(active_goals),
                "completed_count": sum(1 for g in serialized_goals if g.status == "completed"),
                "average_progress_percent": (
                    round(sum(g.progress_percent for g in active_goals) / len(active_goals), 1)
                    if active_goals
                    else None
                ),
                "items": [g.model_dump(mode="json") for g in active_goals[:5]],
            },
        },
        "period_comparisons": {
            "today_vs_yesterday_focus": _build_comparison(
                float(today_focus_mins),
                float(yest_focus_mins),
                len(yest_acts) > 0,
                "mins",
                "yesterday",
            ),
            "today_vs_yesterday_screen_time": _build_comparison(
                float(today_screen_mins),
                float(yest_screen_mins),
                len(yest_st_sessions) > 0,
                "mins",
                "yesterday",
            ),
            "today_vs_yesterday_habits": _build_comparison(
                float(today_habit_rate or 0.0),
                float(yest_habit_rate),
                len(sched_yest) > 0,
                "%",
                "yesterday",
            ),
            "week_vs_last_week_focus": _build_comparison(
                float(week_focus_mins),
                float(last_week_focus_mins),
                len(last_week_acts) > 0,
                "mins",
                "last week",
            ),
            "month_vs_last_month_expenses": _build_comparison(
                float(fin_summary["total_expense_numeric"]),
                prev_month_exp,
                len(prev_month_txs) > 0,
                currency,
                "last month",
            ),
            "month_vs_last_month_income": _build_comparison(
                float(fin_summary["total_income_numeric"]),
                prev_month_inc,
                len(prev_month_txs) > 0,
                currency,
                "last month",
            ),
            "year_vs_last_year_expenses": _build_comparison(
                year_exp,
                last_year_exp,
                len(last_year_txs) > 0,
                currency,
                "last year",
            ),
        },
        "charts": {
            "activity_trend_14d": activity_trend_14d,
            "finance_daily_series": fin_summary["daily_series"],
            "expense_categories": fin_summary["category_breakdown"],
            "habits": [h.model_dump(mode="json") for h in serialized_habits],
        },
        "recent_activity": timeline_preview,
    }


def get_personal_timeline(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    event_types: Optional[List[str]] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Constructs a chronological timeline directly from canonical database records without duplication.
    """
    tz, tz_name = _get_tz(db)
    allowed_types = set(event_types) if event_types else {
        "habit",
        "transaction",
        "screen_time",
        "focus",
        "activity",
        "goal",
        "milestone",
        "journal",
        "wellbeing",
    }

    events: List[Dict[str, Any]] = []

    def _to_local_iso(dt: Optional[datetime], fallback_date: date) -> str:
        if dt is None:
            dt = datetime.combine(fallback_date, time(12, 0), tzinfo=timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).isoformat()

    # 1. Habit Entries
    if "habit" in allowed_types:
        stmt = select(HabitEntry, Habit).join(Habit, HabitEntry.habit_id == Habit.id)
        if start_date:
            stmt = stmt.where(HabitEntry.entry_date >= start_date)
        if end_date:
            stmt = stmt.where(HabitEntry.entry_date <= end_date)
        for entry, habit in db.execute(stmt).all():
            if not entry.completed:
                continue
            events.append(
                {
                    "id": f"habit_entry:{entry.id}",
                    "source_id": entry.id,
                    "parent_id": habit.id,
                    "event_type": "habit",
                    "event_date": entry.entry_date.isoformat(),
                    "timestamp": _to_local_iso(entry.completed_at, entry.entry_date),
                    "title": f"Completed habit: {habit.name}",
                    "subtitle": f"{entry.value} {habit.unit} · {habit.category}",
                    "notes": entry.notes,
                    "color": habit.accent_color,
                    "link": f"/habits?highlight={habit.id}",
                }
            )

    # 2. Financial Transactions
    if "transaction" in allowed_types:
        stmt = select(Transaction)
        if start_date:
            stmt = stmt.where(Transaction.transaction_date >= start_date)
        if end_date:
            stmt = stmt.where(Transaction.transaction_date <= end_date)
        for tx in db.execute(stmt).scalars().all():
            prefix = "-" if tx.transaction_type == "expense" else ("+" if tx.transaction_type == "income" else "⇄")
            events.append(
                {
                    "id": f"transaction:{tx.id}",
                    "source_id": tx.id,
                    "event_type": "transaction",
                    "event_date": tx.transaction_date.isoformat(),
                    "timestamp": _to_local_iso(tx.recorded_at, tx.transaction_date),
                    "title": f"{tx.transaction_type.capitalize()}: {prefix}{tx.currency} {to_decimal(tx.amount)} ({tx.category})",
                    "subtitle": tx.merchant or tx.payment_method or tx.category,
                    "notes": tx.notes,
                    "color": "#ef4444" if tx.transaction_type == "expense" else ("#84cc16" if tx.transaction_type == "income" else "#3b82f6"),
                    "link": f"/finance?highlight={tx.id}",
                }
            )

    # 3. Screen Time Sessions
    if "screen_time" in allowed_types:
        stmt = select(ScreenTimeSession)
        if start_date:
            stmt = stmt.where(ScreenTimeSession.session_date >= start_date)
        if end_date:
            stmt = stmt.where(ScreenTimeSession.session_date <= end_date)
        for st in db.execute(stmt).scalars().all():
            events.append(
                {
                    "id": f"screen_time:{st.id}",
                    "source_id": st.id,
                    "event_type": "screen_time",
                    "event_date": st.session_date.isoformat(),
                    "timestamp": _to_local_iso(st.start_time or st.created_at, st.session_date),
                    "title": f"Screen Time: {st.app_name} ({st.duration_minutes}m)",
                    "subtitle": f"{st.device.capitalize()} · {st.category} ({st.productivity_type})",
                    "notes": st.notes,
                    "color": "#f59e0b" if st.productivity_type == "non_productive" else "#3b82f6",
                    "link": f"/screen-time?highlight={st.id}",
                }
            )

    # 4. Activities & Focus Sessions
    if "focus" in allowed_types or "activity" in allowed_types:
        stmt = select(ActivitySession)
        if start_date:
            stmt = stmt.where(ActivitySession.session_date >= start_date)
        if end_date:
            stmt = stmt.where(ActivitySession.session_date <= end_date)
        for act in db.execute(stmt).scalars().all():
            ev_type = "focus" if act.is_focus_session else "activity"
            if ev_type not in allowed_types:
                continue
            events.append(
                {
                    "id": f"activity:{act.id}",
                    "source_id": act.id,
                    "event_type": ev_type,
                    "event_date": act.session_date.isoformat(),
                    "timestamp": _to_local_iso(act.start_time, act.session_date),
                    "title": f"{'Focus Session' if act.is_focus_session else 'Activity'}: {act.activity_name} ({act.duration_minutes}m)",
                    "subtitle": f"{act.category}" + (f" · Project: {act.project}" if act.project else ""),
                    "notes": act.notes,
                    "color": "#8b5cf6" if act.is_focus_session else "#06b6d4",
                    "link": f"/activities?highlight={act.id}",
                }
            )

    # 5. Goals & Milestones
    if "goal" in allowed_types:
        stmt = select(Goal)
        if start_date:
            stmt = stmt.where(Goal.start_date >= start_date)
        if end_date:
            stmt = stmt.where(Goal.start_date <= end_date)
        for g in db.execute(stmt).scalars().all():
            events.append(
                {
                    "id": f"goal:{g.id}",
                    "source_id": g.id,
                    "event_type": "goal",
                    "event_date": g.start_date.isoformat(),
                    "timestamp": _to_local_iso(g.created_at, g.start_date),
                    "title": f"Goal: {g.name} ({g.current_value}/{g.target_value} {g.unit})",
                    "subtitle": f"Status: {g.status} · Category: {g.category}",
                    "notes": g.description,
                    "color": "#10b981",
                    "link": f"/goals?highlight={g.id}",
                }
            )

    if "milestone" in allowed_types:
        stmt = select(Milestone, Goal).join(Goal, Milestone.goal_id == Goal.id).where(Milestone.is_completed == True)  # noqa: E712
        for ms, goal in db.execute(stmt).all():
            ms_date = ms.completed_at.date() if ms.completed_at else (ms.target_date or goal.start_date)
            if start_date and ms_date < start_date:
                continue
            if end_date and ms_date > end_date:
                continue
            events.append(
                {
                    "id": f"milestone:{ms.id}",
                    "source_id": ms.id,
                    "parent_id": goal.id,
                    "event_type": "milestone",
                    "event_date": ms_date.isoformat(),
                    "timestamp": _to_local_iso(ms.completed_at or ms.created_at, ms_date),
                    "title": f"Milestone Reached: {ms.title}",
                    "subtitle": f"Goal: {goal.name}",
                    "notes": None,
                    "color": "#84cc16",
                    "link": f"/goals?highlight={goal.id}",
                }
            )

    # 6. Journal Entries
    if "journal" in allowed_types:
        stmt = select(JournalEntry)
        if start_date:
            stmt = stmt.where(JournalEntry.entry_date >= start_date)
        if end_date:
            stmt = stmt.where(JournalEntry.entry_date <= end_date)
        for je in db.execute(stmt).scalars().all():
            events.append(
                {
                    "id": f"journal:{je.id}",
                    "source_id": je.id,
                    "event_type": "journal",
                    "event_date": je.entry_date.isoformat(),
                    "timestamp": _to_local_iso(je.recorded_at, je.entry_date),
                    "title": je.title or ("Daily Review" if je.is_daily_review else f"Journal Entry ({je.entry_date.isoformat()})"),
                    "subtitle": je.daily_intention or (je.content[:90] + "..." if len(je.content) > 90 else je.content),
                    "notes": je.highlights,
                    "color": "#a855f7",
                    "link": f"/journal?highlight={je.id}",
                }
            )

    # 7. Wellbeing Records
    if "wellbeing" in allowed_types:
        stmt = select(WellbeingRecord)
        if start_date:
            stmt = stmt.where(WellbeingRecord.record_date >= start_date)
        if end_date:
            stmt = stmt.where(WellbeingRecord.record_date <= end_date)
        for wb in db.execute(stmt).scalars().all():
            parts = []
            if wb.sleep_duration_hours is not None:
                parts.append(f"Sleep: {wb.sleep_duration_hours}h")
            if wb.mood_score is not None:
                parts.append(f"Mood: {wb.mood_score}/10")
            if wb.energy_score is not None:
                parts.append(f"Energy: {wb.energy_score}/10")
            if wb.exercise_duration_minutes:
                parts.append(f"Exercise: {wb.exercise_duration_minutes}m")
            events.append(
                {
                    "id": f"wellbeing:{wb.id}",
                    "source_id": wb.id,
                    "event_type": "wellbeing",
                    "event_date": wb.record_date.isoformat(),
                    "timestamp": _to_local_iso(wb.recorded_at, wb.record_date),
                    "title": f"Wellbeing Log ({wb.record_date.isoformat()})",
                    "subtitle": " · ".join(parts) if parts else "Wellbeing check-in",
                    "notes": wb.notes,
                    "color": "#14b8a6",
                    "link": f"/health?highlight={wb.id}",
                }
            )

    if search:
        q = search.strip().lower()
        events = [
            e
            for e in events
            if q in (e["title"] or "").lower()
            or q in (e["subtitle"] or "").lower()
            or q in (e["notes"] or "").lower()
            or q in e["event_type"].lower()
        ]

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    total_count = len(events)
    sliced = events[:limit]

    # Group by date for chronological rendering
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for ev in sliced:
        grouped.setdefault(ev["event_date"], []).append(ev)

    return {
        "timezone": tz_name,
        "total": total_count,
        "events": sliced,
        "grouped_by_date": [
            {"date": d, "events": evs}
            for d, evs in sorted(grouped.items(), key=lambda x: x[0], reverse=True)
        ],
    }


def generate_deterministic_insights(
    db: Session,
    include_dismissed: bool = False,
) -> Dict[str, Any]:
    """
    Local, deterministic insights engine.
    Produces insights only when sufficient supporting data exists, and clearly distinguishes
    correlation from causation.
    """
    tz, _ = _get_tz(db)
    today = datetime.now(tz).date()
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    currency = (pref.base_currency if pref else "INR").upper()
    screen_target = pref.daily_screen_time_target_minutes if pref else 240

    dismissals = {
        d.insight_key: d.status
        for d in db.execute(select(InsightDismissal)).scalars().all()
    }

    insights: List[Dict[str, Any]] = []

    def _add_insight(
        key: str,
        category: str,
        severity: str,
        title: str,
        explanation: str,
        metrics: Dict[str, Any],
        date_range: str,
        sufficiency: str,
        link: str,
    ):
        st = dismissals.get(key, "active")
        if st == "dismissed" and not include_dismissed:
            return
        insights.append(
            {
                "key": key,
                "category": category,
                "severity": severity,
                "title": title,
                "explanation": explanation,
                "supporting_metrics": metrics,
                "date_range": date_range,
                "data_sufficiency_status": sufficiency,
                "link": link,
                "status": st,
            }
        )

    # 1 & 2. Finance insights (Last 30 days vs prior 30 days)
    cur_start = today - timedelta(days=29)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=29)
    fin_cur = get_finance_summary(db, cur_start, today, currency)

    cur_exp = Decimal(fin_cur["total_expense"])
    prev_exp = Decimal(fin_cur["period_comparison"]["previous_expense"])
    has_prev_exp = fin_cur["period_comparison"]["has_sufficient_previous_data"]

    if cur_exp > Decimal("0.00") and has_prev_exp:
        pct = fin_cur["period_comparison"]["expense_percentage_change"]
        diff = cur_exp - prev_exp
        if pct is not None and abs(pct) >= 10.0:
            direction = "increased" if diff > 0 else "decreased"
            _add_insight(
                key=f"finance_spending_change_{today.strftime('%Y_%m')}",
                category="finance",
                severity="warning" if diff > 0 else "positive",
                title=f"Spending {direction} by {abs(pct):.1f}% over the last 30 days",
                explanation=f"Your recorded expenses in {currency} were {cur_exp} between {cur_start.isoformat()} and {today.isoformat()}, compared with {prev_exp} in the preceding 30-day window ({diff:+.2f} {currency}).",
                metrics={
                    "current_period_expense": f"{currency} {cur_exp}",
                    "previous_period_expense": f"{currency} {prev_exp}",
                    "absolute_change": f"{currency} {diff:+.2f}",
                    "percentage_change": f"{pct:+.1f}%",
                },
                date_range=f"{cur_start.isoformat()} to {today.isoformat()}",
                sufficiency="sufficient",
                link="/finance",
            )

    if fin_cur["category_breakdown"]:
        top_cat = fin_cur["category_breakdown"][0]
        if top_cat["percentage"] >= 30.0 and cur_exp > Decimal("0.00"):
            _add_insight(
                key=f"finance_top_category_{top_cat['category'].lower()}_{today.strftime('%Y_%m')}",
                category="finance",
                severity="info",
                title=f"'{top_cat['category']}' accounts for {top_cat['percentage']}% of recent spending",
                explanation=f"Out of {currency} {cur_exp} in total expenses over the last 30 days, {currency} {top_cat['amount']} was spent on {top_cat['category']}.",
                metrics={
                    "category": top_cat["category"],
                    "category_spend": f"{currency} {top_cat['amount']}",
                    "total_spend": f"{currency} {cur_exp}",
                    "share_percent": f"{top_cat['percentage']}%",
                },
                date_range=f"{cur_start.isoformat()} to {today.isoformat()}",
                sufficiency="sufficient",
                link=f"/finance?category={top_cat['category']}",
            )

    # 3 & 4. Habit completion & streak milestones
    active_habits = db.execute(select(Habit).where(Habit.status == "active")).scalars().all()
    for h in active_habits:
        sh = serialize_habit(db, h, today)
        if sh.current_streak in (3, 5, 6, 7, 13, 14, 20, 21, 29, 30, 50, 100) or sh.current_streak >= 5:
            next_milestone = next((m for m in (7, 14, 21, 30, 50, 100, 365) if m >= sh.current_streak), 365)
            _add_insight(
                key=f"habit_streak_{h.id}_{sh.current_streak}",
                category="habits",
                severity="positive",
                title=f"'{h.name}' is on a {sh.current_streak}-day streak",
                explanation=f"You have maintained '{h.name}' for {sh.current_streak} scheduled days in a row (30-day completion rate: {sh.completion_rate_30d}%). Next milestone: {next_milestone} days.",
                metrics={
                    "habit": h.name,
                    "current_streak": sh.current_streak,
                    "best_streak": sh.best_streak,
                    "completion_rate_30d": f"{sh.completion_rate_30d}%",
                },
                date_range=f"Up to {today.isoformat()}",
                sufficiency="sufficient",
                link=f"/habits?highlight={h.id}",
            )

    # 5. Screen time target threshold check
    st_week_start = today - timedelta(days=6)
    st_sessions = db.execute(
        select(ScreenTimeSession).where(
            ScreenTimeSession.session_date >= st_week_start,
            ScreenTimeSession.session_date <= today,
        )
    ).scalars().all()
    if st_sessions:
        by_day: Dict[date, int] = {}
        for s in st_sessions:
            by_day[s.session_date] = by_day.get(s.session_date, 0) + s.duration_minutes
        exceeded_days = [d for d, mins in by_day.items() if mins > screen_target]
        if exceeded_days:
            max_day = max(by_day.items(), key=lambda x: x[1])
            _add_insight(
                key=f"screen_time_target_exceeded_{today.isoformat()}",
                category="screen_time",
                severity="warning",
                title=f"Screen time exceeded your {screen_target}m target on {len(exceeded_days)} day(s) this week",
                explanation=f"Across {len(by_day)} recorded day(s) in the last 7 days, daily screen time crossed {screen_target} minutes on {len(exceeded_days)} day(s), peaking at {max_day[1]} minutes on {max_day[0].isoformat()}.",
                metrics={
                    "daily_target_minutes": screen_target,
                    "days_exceeded": len(exceeded_days),
                    "recorded_days": len(by_day),
                    "peak_minutes": max_day[1],
                },
                date_range=f"{st_week_start.isoformat()} to {today.isoformat()}",
                sufficiency="sufficient",
                link="/screen-time",
            )

    # 6. Focus time week-over-week change
    prev_w_end = st_week_start - timedelta(days=1)
    prev_w_start = prev_w_end - timedelta(days=6)
    cur_focus_acts = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= st_week_start,
            ActivitySession.session_date <= today,
            ActivitySession.is_focus_session == True,  # noqa: E712
        )
    ).scalars().all()
    prev_focus_acts = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= prev_w_start,
            ActivitySession.session_date <= prev_w_end,
            ActivitySession.is_focus_session == True,  # noqa: E712
        )
    ).scalars().all()
    cur_f_mins = calculate_unique_clock_minutes(list(cur_focus_acts))
    prev_f_mins = calculate_unique_clock_minutes(list(prev_focus_acts))
    if cur_f_mins > 0 and prev_f_mins > 0:
        f_diff = cur_f_mins - prev_f_mins
        f_pct = round((f_diff / prev_f_mins) * 100.0, 1)
        _add_insight(
            key=f"focus_wow_change_{today.strftime('%Y_%W')}",
            category="activities",
            severity="positive" if f_diff >= 0 else "info",
            title=f"Focus time {'increased' if f_diff >= 0 else 'decreased'} by {abs(f_pct)}% week over week",
            explanation=f"You logged {cur_f_mins} unique focus minutes over the last 7 days compared with {prev_f_mins} minutes in the prior 7-day period ({f_diff:+d} mins).",
            metrics={
                "current_7d_focus_minutes": cur_f_mins,
                "previous_7d_focus_minutes": prev_f_mins,
                "change_minutes": f_diff,
                "change_percent": f"{f_pct:+.1f}%",
            },
            date_range=f"{st_week_start.isoformat()} to {today.isoformat()}",
            sufficiency="sufficient",
            link="/activities",
        )

    # 7. Goals behind expected deadline pace
    goals = db.execute(select(Goal).where(Goal.status == "active")).scalars().all()
    for g in goals:
        sg = serialize_goal(g, today)
        if sg.pace_status == "behind" and sg.expected_pace_percent is not None:
            _add_insight(
                key=f"goal_behind_pace_{g.id}",
                category="goals",
                severity="warning",
                title=f"Goal '{g.name}' is behind expected schedule pace",
                explanation=f"Current progress is {sg.progress_percent}% ({sg.current_value}/{sg.target_value} {sg.unit}), whereas linear schedule pace toward {sg.target_date.isoformat() if sg.target_date else 'deadline'} is {sg.expected_pace_percent}%.",
                metrics={
                    "goal": g.name,
                    "current_progress": f"{sg.progress_percent}%",
                    "expected_pace": f"{sg.expected_pace_percent}%",
                    "days_remaining": sg.days_remaining,
                },
                date_range=f"{g.start_date.isoformat()} to {g.target_date.isoformat() if g.target_date else today.isoformat()}",
                sufficiency="sufficient",
                link=f"/goals?highlight={g.id}",
            )

    # 8. Time-of-day concentration for activities
    all_recent_acts = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= cur_start,
            ActivitySession.session_date <= today,
        )
    ).scalars().all()
    if len(all_recent_acts) >= 3:
        buckets = {"Morning (05:00-11:59)": 0, "Afternoon (12:00-16:59)": 0, "Evening (17:00-21:59)": 0, "Night (22:00-04:59)": 0}
        for a in all_recent_acts:
            st = a.start_time
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            hr = st.astimezone(tz).hour
            if 5 <= hr < 12:
                buckets["Morning (05:00-11:59)"] += a.duration_minutes
            elif 12 <= hr < 17:
                buckets["Afternoon (12:00-16:59)"] += a.duration_minutes
            elif 17 <= hr < 22:
                buckets["Evening (17:00-21:59)"] += a.duration_minutes
            else:
                buckets["Night (22:00-04:59)"] += a.duration_minutes
        tot_b = sum(buckets.values())
        if tot_b > 0:
            top_b = max(buckets.items(), key=lambda x: x[1])
            share_b = round((top_b[1] / tot_b) * 100.0, 1)
            if share_b >= 40.0:
                _add_insight(
                    key=f"rhythm_concentration_{today.strftime('%Y_%m')}",
                    category="rhythm",
                    severity="info",
                    title=f"{share_b}% of recorded activity occurs during {top_b[0]}",
                    explanation=f"Based on {len(all_recent_acts)} activity sessions over the last 30 days ({tot_b} total minutes), your highest concentration of recorded work is in the {top_b[0]} window.",
                    metrics={
                        "dominant_window": top_b[0],
                        "window_minutes": top_b[1],
                        "total_minutes": tot_b,
                        "concentration_share": f"{share_b}%",
                    },
                    date_range=f"{cur_start.isoformat()} to {today.isoformat()}",
                    sufficiency="sufficient",
                    link="/rhythm",
                )

    # 9. Habit & Wellbeing empirical association (Observational only, never causal)
    wb_records = db.execute(
        select(WellbeingRecord).where(
            WellbeingRecord.record_date >= cur_start,
            WellbeingRecord.record_date <= today,
        )
    ).scalars().all()
    if len(wb_records) >= 4 and active_habits:
        wb_by_date = {w.record_date: w for w in wb_records if w.energy_score is not None}
        for h in active_habits:
            completed_dates = {e.entry_date for e in h.entries if e.completed and e.entry_date in wb_by_date}
            non_completed_dates = set(wb_by_date.keys()) - completed_dates
            if len(completed_dates) >= 2 and len(non_completed_dates) >= 2:
                avg_with = round(sum(wb_by_date[d].energy_score for d in completed_dates) / len(completed_dates), 1)
                avg_without = round(sum(wb_by_date[d].energy_score for d in non_completed_dates) / len(non_completed_dates), 1)
                diff_e = round(avg_with - avg_without, 1)
                if abs(diff_e) >= 0.8:
                    _add_insight(
                        key=f"wellbeing_habit_assoc_{h.id}",
                        category="wellbeing",
                        severity="info",
                        title=f"Observational pattern: '{h.name}' & Daily Energy ({diff_e:+.1f} pts)",
                        explanation=f"On days when '{h.name}' was completed (n={len(completed_dates)}), average recorded energy was {avg_with}/10 versus {avg_without}/10 on other logged days (n={len(non_completed_dates)}). Note: Observational association only — correlation does not imply causation.",
                        metrics={
                            "habit": h.name,
                            "avg_energy_when_completed": f"{avg_with}/10 (n={len(completed_dates)})",
                            "avg_energy_when_not_completed": f"{avg_without}/10 (n={len(non_completed_dates)})",
                            "difference": f"{diff_e:+.1f} pts",
                        },
                        date_range=f"{cur_start.isoformat()} to {today.isoformat()}",
                        sufficiency="sufficient",
                        link="/health",
                    )
                    break

    # Data sufficiency diagnostics when records are sparse
    diagnostics = []
    if cur_exp == Decimal("0.00"):
        diagnostics.append(
            {
                "domain": "finance",
                "status": "insufficient_data",
                "message": "Log at least 2 periods of expenses to unlock spending trend comparisons.",
            }
        )
    if not active_habits:
        diagnostics.append(
            {
                "domain": "habits",
                "status": "insufficient_data",
                "message": "Create and log a habit to unlock streak and consistency insights.",
            }
        )
    if len(wb_records) < 4:
        diagnostics.append(
            {
                "domain": "wellbeing",
                "status": "insufficient_data",
                "message": f"Logged {len(wb_records)}/4 required wellbeing days in the last 30 days for cross-domain association checks.",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_insights": len(insights),
        "insights": insights,
        "sufficiency_diagnostics": diagnostics,
    }
