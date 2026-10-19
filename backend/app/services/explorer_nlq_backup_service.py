import csv
import hashlib
import io
import json
import re
import shutil
import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.config import BACKUPS_DIR, DATA_DIR, EXPORTS_DIR, settings
from app.core.database import Base, engine
from app.models.entities import (
    ActivitySession,
    AppCategoryMapping,
    Budget,
    Category,
    FilterPreset,
    FinancialAccount,
    Goal,
    GoalHabitLink,
    GoalProgressEntry,
    Habit,
    HabitEntry,
    ImportJob,
    ImportResult,
    IntegrationConfig,
    JournalEntry,
    Milestone,
    RecurringTransactionRule,
    ScreenTimeSession,
    Transaction,
    UserPreference,
    WellbeingRecord,
)
from app.services.activity_service import calculate_unique_clock_minutes, serialize_activity
from app.services.finance_service import (
    compute_transaction_hash,
    evaluate_budget,
    get_finance_summary,
    serialize_account,
    serialize_transaction,
    to_decimal,
)
from app.services.goal_wellbeing_journal_service import (
    serialize_goal,
    serialize_journal,
    serialize_wellbeing,
)
from app.services.habit_service import serialize_habit
from app.services.screen_time_service import (
    compute_screen_time_hash,
    resolve_app_classification,
)

SCHEMA_VERSION = "1.0.0"


# ============================================================================
# 1. PERSONAL DATA EXPLORER & SCHEMA BROWSER
# ============================================================================
def get_schema_browser() -> Dict[str, Any]:
    """
    Documents canonical entities, fields, data types, and relationships without exposing raw SQL.
    """
    entities_docs = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = mapper.local_table
        if table.name in ("user_profiles", "api_tokens"):
            # Sensitive authentication tables are excluded from data explorer browsing
            continue
        columns = []
        for col in table.columns:
            fk_targets = [f"{fk.column.table.name}.{fk.column.name}" for fk in col.foreign_keys]
            columns.append(
                {
                    "name": col.name,
                    "type": str(col.type),
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                    "indexed": bool(col.index or col.primary_key),
                    "foreign_keys": fk_targets,
                }
            )
        entities_docs.append(
            {
                "entity": cls.__name__,
                "table_name": table.name,
                "columns": columns,
            }
        )
    entities_docs.sort(key=lambda x: x["table_name"])
    return {
        "schema_version": SCHEMA_VERSION,
        "entities": entities_docs,
    }


def explore_records(
    db: Session,
    entity_type: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    et = entity_type.strip().lower()
    records: List[Dict[str, Any]] = []

    if et == "transactions":
        stmt = select(Transaction)
        if start_date:
            stmt = stmt.where(Transaction.transaction_date >= start_date)
        if end_date:
            stmt = stmt.where(Transaction.transaction_date <= end_date)
        if category:
            stmt = stmt.where(Transaction.category.ilike(f"%{category}%"))
        rows = db.execute(stmt).scalars().all()
        acc_map = {a.id: a.name for a in db.execute(select(FinancialAccount)).scalars().all()}
        for r in rows:
            item = serialize_transaction(db, r, acc_map).model_dump(mode="json")
            item["_relationships"] = [
                f"Account: {item.get('account_name') or 'Unassigned'}",
                f"Category: {item['category']}",
            ]
            records.append(item)

    elif et == "habits":
        rows = db.execute(select(Habit)).scalars().all()
        for r in rows:
            item = serialize_habit(db, r).model_dump(mode="json")
            item.pop("recent_entries", None)
            item["_relationships"] = [f"Category: {item['category']}", f"Streak: {item['current_streak']}d"]
            records.append(item)

    elif et == "habit_entries":
        stmt = select(HabitEntry, Habit).join(Habit, HabitEntry.habit_id == Habit.id)
        if start_date:
            stmt = stmt.where(HabitEntry.entry_date >= start_date)
        if end_date:
            stmt = stmt.where(HabitEntry.entry_date <= end_date)
        for entry, habit in db.execute(stmt).all():
            records.append(
                {
                    "id": entry.id,
                    "habit_id": entry.habit_id,
                    "habit_name": habit.name,
                    "category": habit.category,
                    "entry_date": entry.entry_date.isoformat(),
                    "completed": entry.completed,
                    "value": str(entry.value),
                    "unit": habit.unit,
                    "notes": entry.notes,
                    "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
                    "_relationships": [f"Habit: {habit.name} ({habit.id})"],
                }
            )

    elif et == "screen_time":
        stmt = select(ScreenTimeSession)
        if start_date:
            stmt = stmt.where(ScreenTimeSession.session_date >= start_date)
        if end_date:
            stmt = stmt.where(ScreenTimeSession.session_date <= end_date)
        if category:
            stmt = stmt.where(ScreenTimeSession.category.ilike(f"%{category}%"))
        for s in db.execute(stmt).scalars().all():
            records.append(
                {
                    "id": s.id,
                    "app_name": s.app_name,
                    "device": s.device,
                    "session_date": s.session_date.isoformat(),
                    "duration_minutes": s.duration_minutes,
                    "category": s.category,
                    "productivity_type": s.productivity_type,
                    "data_source": s.data_source,
                    "notes": s.notes,
                    "_relationships": [f"Application: {s.app_name}", f"Category: {s.category}"],
                }
            )

    elif et == "activities":
        stmt = select(ActivitySession)
        if start_date:
            stmt = stmt.where(ActivitySession.session_date >= start_date)
        if end_date:
            stmt = stmt.where(ActivitySession.session_date <= end_date)
        if category:
            stmt = stmt.where(ActivitySession.category.ilike(f"%{category}%"))
        for a in db.execute(stmt).scalars().all():
            item = serialize_activity(a).model_dump(mode="json")
            item["_relationships"] = [
                f"Category: {a.category}",
                f"Project: {a.project or 'None'}",
            ]
            records.append(item)

    elif et == "goals":
        for g in db.execute(select(Goal)).scalars().all():
            item = serialize_goal(g).model_dump(mode="json")
            item["_relationships"] = [
                f"Milestones: {len(g.milestones)}",
                f"Linked Habits: {len(item.get('related_habit_ids', []))}",
            ]
            records.append(item)

    elif et == "journal":
        stmt = select(JournalEntry)
        if start_date:
            stmt = stmt.where(JournalEntry.entry_date >= start_date)
        if end_date:
            stmt = stmt.where(JournalEntry.entry_date <= end_date)
        for j in db.execute(stmt).scalars().all():
            item = serialize_journal(j).model_dump(mode="json")
            item["_relationships"] = [f"Tags: {', '.join(item.get('tags', [])) or 'None'}"]
            records.append(item)

    elif et == "wellbeing":
        stmt = select(WellbeingRecord)
        if start_date:
            stmt = stmt.where(WellbeingRecord.record_date >= start_date)
        if end_date:
            stmt = stmt.where(WellbeingRecord.record_date <= end_date)
        for w in db.execute(stmt).scalars().all():
            item = serialize_wellbeing(w).model_dump(mode="json")
            item["_relationships"] = [f"Date: {w.record_date.isoformat()}"]
            records.append(item)

    elif et == "budgets":
        for b in db.execute(select(Budget)).scalars().all():
            item = evaluate_budget(db, b).model_dump(mode="json")
            item["_relationships"] = [f"Month: {b.month}", f"Category: {b.category}"]
            records.append(item)

    elif et == "accounts":
        for acc in db.execute(select(FinancialAccount)).scalars().all():
            item = serialize_account(db, acc).model_dump(mode="json")
            item["_relationships"] = [f"Currency: {acc.currency}"]
            records.append(item)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported entity_type '{entity_type}'. Supported types: transactions, habits, habit_entries, screen_time, activities, goals, journal, wellbeing, budgets, accounts.",
        )

    if search and search.strip():
        q = search.strip().lower()
        records = [
            r for r in records if q in json.dumps(r, default=str).lower()
        ]

    # Sort records deterministically
    reverse_flag = sort_order.lower() != "asc"
    date_keys = ("transaction_date", "session_date", "entry_date", "record_date", "start_date", "month", "created_at")

    def _sort_key(row: Dict[str, Any]) -> str:
        if sort_by and sort_by in row and row[sort_by] is not None:
            return str(row[sort_by])
        for dk in date_keys:
            if dk in row and row[dk] is not None:
                return str(row[dk])
        return str(row.get("id", ""))

    records.sort(key=_sort_key, reverse=reverse_flag)

    total = len(records)
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    start_idx = (page - 1) * page_size
    sliced = records[start_idx : start_idx + page_size]
    total_pages = max(1, (total + page_size - 1) // page_size)

    columns = list(sliced[0].keys()) if sliced else (list(records[0].keys()) if records else [])

    return {
        "entity_type": et,
        "items": sliced,
        "columns": columns,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ============================================================================
# 2. DETERMINISTIC LOCAL NATURAL-LANGUAGE QUERY PARSER
# ============================================================================
def _resolve_nlq_date_range(text: str, today: date) -> Tuple[date, date, str]:
    q = text.lower()
    if "last month" in q or "previous month" in q:
        first_this = date(today.year, today.month, 1)
        last_prev = first_this - timedelta(days=1)
        first_prev = date(last_prev.year, last_prev.month, 1)
        return first_prev, last_prev, f"Last Month ({first_prev.isoformat()} to {last_prev.isoformat()})"
    if "this week" in q:
        start_w = today - timedelta(days=today.weekday())
        return start_w, today, f"This Week ({start_w.isoformat()} to {today.isoformat()})"
    if "last week" in q:
        this_w = today - timedelta(days=today.weekday())
        end_lw = this_w - timedelta(days=1)
        start_lw = end_lw - timedelta(days=6)
        return start_lw, end_lw, f"Last Week ({start_lw.isoformat()} to {end_lw.isoformat()})"
    if "today" in q:
        return today, today, f"Today ({today.isoformat()})"
    if "yesterday" in q:
        yest = today - timedelta(days=1)
        return yest, yest, f"Yesterday ({yest.isoformat()})"
    if "this year" in q or "year" in q:
        y_start = date(today.year, 1, 1)
        return y_start, today, f"This Year ({y_start.isoformat()} to {today.isoformat()})"
    # Default: this month (or last 30 days)
    if "this month" in q or "month" in q:
        m_start = date(today.year, today.month, 1)
        return m_start, today, f"This Month ({m_start.isoformat()} to {today.isoformat()})"
    d_30 = today - timedelta(days=29)
    return d_30, today, f"Last 30 Days ({d_30.isoformat()} to {today.isoformat()})"


def execute_local_nl_query(db: Session, query_text: str) -> Dict[str, Any]:
    """
    Deterministic, zero-AI local natural-language query engine.
    Supports predefined analytical queries with explicit date-range, metric definition, and source citations.
    """
    q = query_text.strip()
    q_low = q.lower()
    today = date.today()
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    currency = (pref.base_currency if pref else "INR").upper()

    start_d, end_d, range_label = _resolve_nlq_date_range(q_low, today)

    # Pattern 1: Largest expense category / where did my money go
    if ("which category" in q_low or "largest expense" in q_low or "where does my money go" in q_low or "top spending" in q_low) and (
        "spend" in q_low or "expense" in q_low or "money" in q_low
    ):
        fin = get_finance_summary(db, start_d, end_d, currency)
        cats = fin["category_breakdown"]
        if not cats:
            return {
                "supported": True,
                "query": q,
                "answer": f"No expenses in {currency} were recorded during {range_label}.",
                "date_range": range_label,
                "metric_definition": f"Exact Decimal sum of expense transactions in {currency} grouped by category (excluding transfers).",
                "supporting_data": {"categories": [], "total_expense": fin["total_expense"]},
                "link": "/finance",
            }
        top = cats[0]
        return {
            "supported": True,
            "query": q,
            "answer": f"'{top['category']}' accounted for the largest share of expenses during {range_label}: {currency} {top['amount']} ({top['percentage']}% of {currency} {fin['total_expense']} total).",
            "date_range": range_label,
            "metric_definition": f"Exact Decimal sum of expense transactions in {currency} grouped by category (excluding transfers).",
            "supporting_data": {"top_category": top, "all_categories": cats[:5], "total_expense": fin["total_expense"]},
            "link": "/finance",
        }

    # Pattern 2: How much did I spend [on <category>]?
    if "spend" in q_low or "spent" in q_low or "expense" in q_low:
        fin = get_finance_summary(db, start_d, end_d, currency)
        # Check if "on <category>" is mentioned
        match_on = re.search(r"spend\s+on\s+([a-zA-Z0-9_&\s]+?)(?:\s+last|\s+this|\s+in|\?|$)", q_low) or re.search(
            r"spent\s+on\s+([a-zA-Z0-9_&\s]+?)(?:\s+last|\s+this|\s+in|\?|$)", q_low
        )
        if match_on:
            target_cat = match_on.group(1).strip()
            txs = db.execute(
                select(Transaction).where(
                    Transaction.transaction_date >= start_d,
                    Transaction.transaction_date <= end_d,
                    Transaction.currency == currency,
                    Transaction.transaction_type == "expense",
                    Transaction.category.ilike(f"%{target_cat}%"),
                )
            ).scalars().all()
            cat_sum = sum((to_decimal(t.amount) for t in txs), Decimal("0.00"))
            return {
                "supported": True,
                "query": q,
                "answer": f"You spent {currency} {cat_sum} on '{target_cat}' across {len(txs)} transaction(s) during {range_label}.",
                "date_range": range_label,
                "metric_definition": f"Exact Decimal sum of expense transactions matching category '{target_cat}' in {currency}.",
                "supporting_data": {"category_filter": target_cat, "amount": str(cat_sum), "transactions_count": len(txs)},
                "link": f"/finance?category={target_cat}",
            }

        return {
            "supported": True,
            "query": q,
            "answer": f"Your total expenses during {range_label} were {currency} {fin['total_expense']} (Income: {currency} {fin['total_income']}, Net: {currency} {fin['net_savings']}).",
            "date_range": range_label,
            "metric_definition": f"Exact Decimal sum of all expense transactions in {currency} (transfers excluded).",
            "supporting_data": {
                "total_expense": fin["total_expense"],
                "total_income": fin["total_income"],
                "categories": fin["category_breakdown"][:5],
            },
            "link": "/finance",
        }

    # Pattern 3: Which habit had the best completion rate / streak?
    if "habit" in q_low or "streak" in q_low or "completion rate" in q_low:
        habits = db.execute(select(Habit).where(Habit.status == "active")).scalars().all()
        if not habits:
            return {
                "supported": True,
                "query": q,
                "answer": "You do not have any active habits yet. Create a habit on the Habits page to start tracking completion rates.",
                "date_range": f"Up to {today.isoformat()}",
                "metric_definition": "30-day scheduled completion rate and consecutive scheduled-day streak.",
                "supporting_data": {"habits": []},
                "link": "/habits",
            }
        serialized = [serialize_habit(db, h, today) for h in habits]
        if "streak" in q_low:
            best_h = max(serialized, key=lambda x: (x.current_streak, x.best_streak))
            return {
                "supported": True,
                "query": q,
                "answer": f"'{best_h.name}' has the highest current streak at {best_h.current_streak} scheduled day(s) (all-time best streak: {best_h.best_streak} days).",
                "date_range": f"Up to {today.isoformat()}",
                "metric_definition": "Consecutive scheduled days completed without missing a scheduled day.",
                "supporting_data": {
                    "top_habit": best_h.name,
                    "current_streak": best_h.current_streak,
                    "best_streak": best_h.best_streak,
                },
                "link": "/habits",
            }
        best_h = max(serialized, key=lambda x: (x.completion_rate_30d, x.current_streak))
        return {
            "supported": True,
            "query": q,
            "answer": f"'{best_h.name}' had the best 30-day completion rate at {best_h.completion_rate_30d}% (current streak: {best_h.current_streak} days).",
            "date_range": f"30-day rolling window ending {today.isoformat()}",
            "metric_definition": "Completed scheduled days divided by total scheduled days over the last 30 days.",
            "supporting_data": {
                "top_habit": best_h.name,
                "completion_rate_30d": best_h.completion_rate_30d,
                "all_habits": [
                    {"name": h.name, "completion_rate_30d": h.completion_rate_30d, "current_streak": h.current_streak}
                    for h in serialized
                ],
            },
            "link": "/habits",
        }

    # Pattern 4: Focus time / activity time
    if "focus" in q_low or "deep work" in q_low or "activity time" in q_low:
        acts = db.execute(
            select(ActivitySession).where(
                ActivitySession.session_date >= start_d,
                ActivitySession.session_date <= end_d,
            )
        ).scalars().all()
        focus_acts = [a for a in acts if a.is_focus_session]
        uniq_focus = calculate_unique_clock_minutes(focus_acts)
        rec_focus = sum(a.duration_minutes for a in focus_acts)
        return {
            "supported": True,
            "query": q,
            "answer": f"You recorded {uniq_focus} unique focus minutes ({round(uniq_focus / 60.0, 2)} hours) across {len(focus_acts)} focus session(s) during {range_label}.",
            "date_range": range_label,
            "metric_definition": "Unique non-overlapping elapsed clock minutes across ActivitySession records marked as focus sessions.",
            "supporting_data": {
                "unique_focus_minutes": uniq_focus,
                "total_recorded_focus_minutes": rec_focus,
                "focus_sessions_count": len(focus_acts),
            },
            "link": "/activities",
        }

    # Pattern 5: Screen time
    if "screen time" in q_low or "phone" in q_low or "app" in q_low:
        sts = db.execute(
            select(ScreenTimeSession).where(
                ScreenTimeSession.session_date >= start_d,
                ScreenTimeSession.session_date <= end_d,
            )
        ).scalars().all()
        tot_mins = sum(s.duration_minutes for s in sts)
        rec_days = len(set(s.session_date for s in sts))
        span_days = max(1, (end_d - start_d).days + 1)
        avg_rec = round(tot_mins / rec_days, 1) if rec_days > 0 else 0.0
        avg_span = round(tot_mins / span_days, 1)
        return {
            "supported": True,
            "query": q,
            "answer": (
                f"During {range_label}, your total recorded screen time was {tot_mins} minutes ({round(tot_mins / 60.0, 2)}h). "
                f"Average across {rec_days} recorded day(s): {avg_rec}m/day (or {avg_span}m/day across all {span_days} calendar days)."
            ),
            "date_range": range_label,
            "metric_definition": "Sum and daily average of duration_minutes across ScreenTimeSession records.",
            "supporting_data": {
                "total_minutes": tot_mins,
                "recorded_days": rec_days,
                "avg_daily_recorded_minutes": avg_rec,
                "avg_daily_calendar_minutes": avg_span,
            },
            "link": "/screen-time",
        }

    # Pattern 6: Sleep / mood / energy
    if "sleep" in q_low or "mood" in q_low or "energy" in q_low:
        wbs = db.execute(
            select(WellbeingRecord).where(
                WellbeingRecord.record_date >= start_d,
                WellbeingRecord.record_date <= end_d,
            )
        ).scalars().all()
        slp = [float(w.sleep_duration_hours) for w in wbs if w.sleep_duration_hours is not None]
        md = [w.mood_score for w in wbs if w.mood_score is not None]
        en = [w.energy_score for w in wbs if w.energy_score is not None]
        if not wbs:
            return {
                "supported": True,
                "query": q,
                "answer": f"No wellbeing records were logged during {range_label}.",
                "date_range": range_label,
                "metric_definition": "Arithmetic mean of recorded sleep hours, mood (1-10), and energy (1-10).",
                "supporting_data": {"recorded_days": 0},
                "link": "/health",
            }
        avg_s = round(sum(slp) / len(slp), 2) if slp else "N/A"
        avg_m = round(sum(md) / len(md), 1) if md else "N/A"
        avg_e = round(sum(en) / len(en), 1) if en else "N/A"
        return {
            "supported": True,
            "query": q,
            "answer": f"Across {len(wbs)} logged day(s) in {range_label}: Avg Sleep = {avg_s}h, Avg Mood = {avg_m}/10, Avg Energy = {avg_e}/10.",
            "date_range": range_label,
            "metric_definition": "Arithmetic mean of non-null WellbeingRecord measurements within the date range.",
            "supporting_data": {"recorded_days": len(wbs), "avg_sleep": avg_s, "avg_mood": avg_m, "avg_energy": avg_e},
            "link": "/health",
        }

    # Pattern 7: Goals
    if "goal" in q_low:
        goals = [serialize_goal(g, today) for g in db.execute(select(Goal)).scalars().all()]
        active = [g for g in goals if g.status == "active"]
        return {
            "supported": True,
            "query": q,
            "answer": f"You have {len(active)} active goal(s) and {sum(1 for g in goals if g.status == 'completed')} completed goal(s).",
            "date_range": f"As of {today.isoformat()}",
            "metric_definition": "Count and progress percentage (current_value / target_value) of Goal records.",
            "supporting_data": {
                "active_goals": [{"name": g.name, "progress_percent": g.progress_percent} for g in active]
            },
            "link": "/goals",
        }

    # Unsupported query fallback — transparent explanation without hallucination
    return {
        "supported": False,
        "query": q,
        "answer": (
            "This local deterministic query parser could not safely map your question to a verified calculation. "
            "No external AI is used. Try one of the supported analytical questions below:"
        ),
        "supported_examples": [
            "How much did I spend on food last month?",
            "Which category accounted for the largest expenses?",
            "Which habit had the best completion rate?",
            "How much focus time did I record this week?",
            "What was my average daily screen time this month?",
            "How was my sleep and energy this month?",
            "Which goals are active?",
        ],
        "date_range": "N/A",
        "metric_definition": "Deterministic local rule matcher (no external LLM).",
        "supporting_data": {},
        "link": "/explorer",
    }


# ============================================================================
# 3. CSV IMPORT PREVIEW & COMMIT, CANONICAL EXPORT, BACKUP & RESTORE
# ============================================================================
def preview_csv_import(
    db: Session,
    domain: str,
    filename: str,
    csv_content: str,
    field_mapping: Optional[Dict[str, str]] = None,
    default_currency: str = "INR",
) -> Dict[str, Any]:
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty or missing headers.")

    mapping = field_mapping or {}

    def _get_val(row: Dict[str, Any], canonical_key: str, aliases: List[str], default: str = "") -> str:
        if canonical_key in mapping and mapping[canonical_key] in row:
            return str(row[mapping[canonical_key]] or "").strip()
        for k in [canonical_key] + aliases:
            for col in row:
                if col and col.strip().lower() == k.lower():
                    return str(row[col] or "").strip()
        return default

    job = ImportJob(
        domain=domain,
        filename=filename,
        status="previewed",
    )
    db.add(job)
    db.flush()

    preview_rows: List[Dict[str, Any]] = []
    seen_hashes_in_file = set()
    valid_count = 0
    dup_count = 0
    err_count = 0

    for idx, raw_row in enumerate(reader, start=1):
        row_status = "valid"
        row_msg = "Ready to import"
        normalized: Dict[str, Any] = {}

        try:
            if domain == "transactions":
                d_str = _get_val(raw_row, "transaction_date", ["date", "tx_date", "day"])
                tx_date = date.fromisoformat(d_str[:10]) if d_str else date.today()
                amt_str = _get_val(raw_row, "amount", ["value", "cost", "price"]).replace(",", "")
                amt = to_decimal(Decimal(amt_str))
                if amt <= Decimal("0.00"):
                    raise ValueError("Amount must be greater than zero.")
                curr = (_get_val(raw_row, "currency", ["curr"], default_currency) or default_currency).upper()
                tx_type = (_get_val(raw_row, "transaction_type", ["type"], "expense") or "expense").lower()
                if tx_type not in ("expense", "income", "transfer"):
                    tx_type = "expense"
                cat = _get_val(raw_row, "category", ["cat"], "General") or "General"
                merch = _get_val(raw_row, "merchant", ["payee", "vendor", "description", "recipient"], "")
                notes = _get_val(raw_row, "notes", ["memo", "note"], "")
                method = _get_val(raw_row, "payment_method", ["method"], "CSV Import")

                ext_hash = compute_transaction_hash(tx_date, amt, curr, tx_type, cat, merch)
                exists_db = db.execute(
                    select(Transaction.id).where(Transaction.external_hash == ext_hash)
                ).first()
                if exists_db or ext_hash in seen_hashes_in_file:
                    row_status = "duplicate"
                    row_msg = "Duplicate transaction detected (matches existing date, amount, currency, category, and merchant)."
                    dup_count += 1
                else:
                    seen_hashes_in_file.add(ext_hash)
                    valid_count += 1

                normalized = {
                    "transaction_date": tx_date.isoformat(),
                    "amount": str(amt),
                    "currency": curr,
                    "transaction_type": tx_type,
                    "category": cat,
                    "merchant": merch or None,
                    "payment_method": method,
                    "notes": notes or None,
                    "external_hash": ext_hash,
                }

            elif domain == "screen_time":
                d_str = _get_val(raw_row, "session_date", ["date", "day"])
                s_date = date.fromisoformat(d_str[:10]) if d_str else date.today()
                app_name = _get_val(raw_row, "app_name", ["application", "app", "website", "site"])
                if not app_name:
                    raise ValueError("Missing application or website name.")
                dur_str = _get_val(raw_row, "duration_minutes", ["duration", "minutes", "mins"])
                dur = int(float(dur_str))
                if dur <= 0:
                    raise ValueError("Duration minutes must be positive.")
                device = (_get_val(raw_row, "device", ["platform"], "desktop") or "desktop").lower()
                if device not in ("desktop", "phone", "tablet", "web", "other"):
                    device = "other"
                cat_in = _get_val(raw_row, "category", ["cat"], "") or None
                prod_in = _get_val(raw_row, "productivity_type", ["productivity"], "") or None
                cat, prod = resolve_app_classification(db, app_name, cat_in, prod_in)
                notes = _get_val(raw_row, "notes", ["note"], "")

                ext_hash = compute_screen_time_hash(s_date, app_name, device, dur, None)
                exists_db = db.execute(
                    select(ScreenTimeSession.id).where(ScreenTimeSession.external_hash == ext_hash)
                ).first()
                if exists_db or ext_hash in seen_hashes_in_file:
                    row_status = "duplicate"
                    row_msg = "Duplicate screen-time session detected."
                    dup_count += 1
                else:
                    seen_hashes_in_file.add(ext_hash)
                    valid_count += 1

                normalized = {
                    "session_date": s_date.isoformat(),
                    "app_name": app_name,
                    "device": device,
                    "duration_minutes": dur,
                    "category": cat,
                    "productivity_type": prod,
                    "notes": notes or None,
                    "external_hash": ext_hash,
                }

            elif domain == "activities":
                d_str = _get_val(raw_row, "session_date", ["date", "day"])
                s_date = date.fromisoformat(d_str[:10]) if d_str else date.today()
                act_name = _get_val(raw_row, "activity_name", ["activity", "title", "task"])
                if not act_name:
                    raise ValueError("Missing activity_name.")
                dur_str = _get_val(raw_row, "duration_minutes", ["duration", "minutes", "mins"], "30")
                dur = max(1, int(float(dur_str)))
                cat = _get_val(raw_row, "category", ["cat"], "Deep Work") or "Deep Work"
                proj = _get_val(raw_row, "project", ["proj"], "") or None
                is_foc = _get_val(raw_row, "is_focus_session", ["focus"], "false").lower() in ("true", "1", "yes")
                notes = _get_val(raw_row, "notes", ["note"], "") or None
                valid_count += 1
                normalized = {
                    "session_date": s_date.isoformat(),
                    "activity_name": act_name,
                    "duration_minutes": dur,
                    "category": cat,
                    "project": proj,
                    "is_focus_session": is_foc,
                    "notes": notes,
                }

            elif domain == "habits":
                h_name = _get_val(raw_row, "name", ["habit", "habit_name", "title"])
                if not h_name:
                    raise ValueError("Missing habit name.")
                cat = _get_val(raw_row, "category", ["cat"], "Health") or "Health"
                freq = _get_val(raw_row, "frequency_type", ["frequency"], "daily") or "daily"
                valid_count += 1
                normalized = {
                    "name": h_name,
                    "category": cat,
                    "frequency_type": freq if freq in ("daily", "selected_weekdays", "weekly_target") else "daily",
                }

        except (ValueError, InvalidOperation, Exception) as exc:
            row_status = "error"
            row_msg = str(exc)
            err_count += 1

        row_entry = {
            "row_number": idx,
            "status": row_status,
            "message": row_msg,
            "normalized": normalized,
            "raw": raw_row,
        }
        preview_rows.append(row_entry)

        db.add(
            ImportResult(
                import_job_id=job.id,
                row_number=idx,
                status=row_status,
                message=row_msg,
                raw_row_json=json.dumps(raw_row, default=str),
            )
        )

    job.total_rows = len(preview_rows)
    job.valid_rows = valid_count
    job.duplicate_rows = dup_count
    job.error_rows = err_count
    job.preview_payload_json = json.dumps(preview_rows, default=str)
    db.commit()
    db.refresh(job)

    return {
        "import_job_id": job.id,
        "domain": job.domain,
        "filename": job.filename,
        "status": job.status,
        "total_rows": job.total_rows,
        "valid_rows": job.valid_rows,
        "duplicate_rows": job.duplicate_rows,
        "error_rows": job.error_rows,
        "rows": preview_rows,
    }


def commit_csv_import(
    db: Session,
    import_job_id: str,
    skip_duplicates: bool = True,
    row_overrides: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    job = db.execute(select(ImportJob).where(ImportJob.id == import_job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found.")
    if job.status == "committed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This import job has already been committed.")

    preview_rows: List[Dict[str, Any]] = json.loads(job.preview_payload_json or "[]")
    overrides = row_overrides or {}
    imported_count = 0

    for row in preview_rows:
        rnum = int(row["row_number"])
        rstatus = row["status"]
        norm = dict(row.get("normalized") or {})
        if rnum in overrides:
            norm.update(overrides[rnum])
            if rstatus == "error":
                rstatus = "valid"

        if rstatus == "error":
            continue
        if rstatus == "duplicate" and skip_duplicates:
            continue

        if job.domain == "transactions":
            tx = Transaction(
                transaction_date=date.fromisoformat(norm["transaction_date"]),
                amount=to_decimal(norm["amount"]),
                currency=norm.get("currency", "INR").upper(),
                transaction_type=norm.get("transaction_type", "expense"),
                category=norm.get("category", "General"),
                merchant=norm.get("merchant"),
                payment_method=norm.get("payment_method", "CSV Import"),
                notes=norm.get("notes"),
                import_job_id=job.id,
                external_hash=norm.get("external_hash"),
            )
            db.add(tx)
            imported_count += 1

        elif job.domain == "screen_time":
            st = ScreenTimeSession(
                session_date=date.fromisoformat(norm["session_date"]),
                app_name=norm["app_name"],
                device=norm.get("device", "desktop"),
                duration_minutes=int(norm["duration_minutes"]),
                category=norm.get("category", "other"),
                productivity_type=norm.get("productivity_type", "neutral"),
                data_source="csv_import",
                notes=norm.get("notes"),
                import_job_id=job.id,
                external_hash=norm.get("external_hash"),
            )
            db.add(st)
            imported_count += 1

        elif job.domain == "activities":
            s_date = date.fromisoformat(norm["session_date"])
            dur = int(norm["duration_minutes"])
            start_dt = datetime.combine(s_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=9)
            end_dt = start_dt + timedelta(minutes=dur)
            act = ActivitySession(
                session_date=s_date,
                activity_name=norm["activity_name"],
                category=norm.get("category", "Deep Work"),
                project=norm.get("project"),
                start_time=start_dt,
                end_time=end_dt,
                duration_minutes=dur,
                accumulated_seconds=dur * 60,
                timer_status="completed",
                is_focus_session=bool(norm.get("is_focus_session", False)),
                notes=norm.get("notes"),
                source="csv_import",
            )
            db.add(act)
            imported_count += 1

        elif job.domain == "habits":
            h = Habit(
                name=norm["name"],
                category=norm.get("category", "Health"),
                frequency_type=norm.get("frequency_type", "daily"),
                start_date=date.today(),
            )
            db.add(h)
            imported_count += 1

    job.imported_rows = imported_count
    job.status = "committed"
    job.committed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    return {
        "import_job_id": job.id,
        "domain": job.domain,
        "status": job.status,
        "imported_rows": job.imported_rows,
        "total_rows": job.total_rows,
        "duplicate_rows_skipped": job.duplicate_rows if skip_duplicates else 0,
        "error_rows_skipped": job.error_rows,
        "committed_at": job.committed_at.isoformat() if job.committed_at else None,
    }


def export_all_personal_data(db: Session) -> Dict[str, Any]:
    """
    Exports all canonical personal records while preserving IDs, relationships, timestamps, and currencies.
    Never exposes password hashes or raw API tokens.
    """
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app_name": settings.APP_NAME,
        "preferences": {
            "preferred_name": pref.preferred_name if pref else "Builder",
            "timezone": pref.timezone if pref else "Asia/Kolkata",
            "base_currency": pref.base_currency if pref else "INR",
            "theme": pref.theme if pref else "dark",
            "daily_screen_time_target_minutes": pref.daily_screen_time_target_minutes if pref else 240,
            "focus_session_duration_minutes": pref.focus_session_duration_minutes if pref else 50,
        },
        "habits": [serialize_habit(db, h).model_dump(mode="json") for h in db.execute(select(Habit)).scalars().all()],
        "habit_entries": [
            {
                "id": e.id,
                "habit_id": e.habit_id,
                "entry_date": e.entry_date.isoformat(),
                "completed": e.completed,
                "value": str(e.value),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "notes": e.notes,
            }
            for e in db.execute(select(HabitEntry)).scalars().all()
        ],
        "accounts": [
            serialize_account(db, a).model_dump(mode="json")
            for a in db.execute(select(FinancialAccount)).scalars().all()
        ],
        "transactions": [
            serialize_transaction(db, t).model_dump(mode="json")
            for t in db.execute(select(Transaction)).scalars().all()
        ],
        "budgets": [
            evaluate_budget(db, b).model_dump(mode="json")
            for b in db.execute(select(Budget)).scalars().all()
        ],
        "screen_time_sessions": [
            {
                "id": s.id,
                "app_name": s.app_name,
                "device": s.device,
                "session_date": s.session_date.isoformat(),
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "duration_minutes": s.duration_minutes,
                "category": s.category,
                "productivity_type": s.productivity_type,
                "data_source": s.data_source,
                "notes": s.notes,
            }
            for s in db.execute(select(ScreenTimeSession)).scalars().all()
        ],
        "activity_sessions": [
            serialize_activity(a).model_dump(mode="json")
            for a in db.execute(select(ActivitySession)).scalars().all()
        ],
        "goals": [
            serialize_goal(g).model_dump(mode="json")
            for g in db.execute(select(Goal)).scalars().all()
        ],
        "journal_entries": [
            serialize_journal(j).model_dump(mode="json")
            for j in db.execute(select(JournalEntry)).scalars().all()
        ],
        "wellbeing_records": [
            serialize_wellbeing(w).model_dump(mode="json")
            for w in db.execute(select(WellbeingRecord)).scalars().all()
        ],
    }


def _get_sqlite_db_path() -> Path:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        raw_path = url.replace("sqlite:///", "", 1)
        return Path(raw_path).resolve()
    return (DATA_DIR / "personal_life_os.db").resolve()


def create_database_backup(db: Session, label: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a safe, consistent SQLite database backup + JSON manifest with SHA-256 verification.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", (label or "manual").strip())[:32]
    backup_filename = f"plos_backup_{ts}_{safe_label}.db"
    backup_path = BACKUPS_DIR / backup_filename

    src_db_path = _get_sqlite_db_path()
    if src_db_path.exists():
        # Use SQLite online backup API for transaction-safe copy even in WAL mode
        src_conn = sqlite3.connect(str(src_db_path))
        dst_conn = sqlite3.connect(str(backup_path))
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
    else:
        # Fallback for in-memory test DB: create file DB and dump JSON snapshot alongside
        dst_conn = sqlite3.connect(str(backup_path))
        dst_conn.execute("CREATE TABLE backup_meta (schema_version TEXT);")
        dst_conn.execute("INSERT INTO backup_meta VALUES (?);", (SCHEMA_VERSION,))
        dst_conn.commit()
        dst_conn.close()

    sha256_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    size_bytes = backup_path.stat().st_size

    # Also write a companion JSON snapshot for human-readable inspection & cross-version safety
    json_snapshot = export_all_personal_data(db)
    manifest = {
        "backup_filename": backup_filename,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": size_bytes,
        "sha256": sha256_hash,
        "record_counts": {
            "habits": len(json_snapshot["habits"]),
            "transactions": len(json_snapshot["transactions"]),
            "screen_time_sessions": len(json_snapshot["screen_time_sessions"]),
            "activity_sessions": len(json_snapshot["activity_sessions"]),
            "goals": len(json_snapshot["goals"]),
            "journal_entries": len(json_snapshot["journal_entries"]),
            "wellbeing_records": len(json_snapshot["wellbeing_records"]),
        },
    }
    manifest_path = BACKUPS_DIR / f"{backup_filename}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def list_database_backups() -> List[Dict[str, Any]]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for db_file in sorted(BACKUPS_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        manifest_file = BACKUPS_DIR / f"{db_file.name}.manifest.json"
        if manifest_file.exists():
            try:
                backups.append(json.loads(manifest_file.read_text(encoding="utf-8")))
                continue
            except Exception:
                pass
        backups.append(
            {
                "backup_filename": db_file.name,
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.fromtimestamp(db_file.stat().st_mtime, tz=timezone.utc).isoformat(),
                "size_bytes": db_file.stat().st_size,
                "sha256": hashlib.sha256(db_file.read_bytes()).hexdigest(),
                "record_counts": {},
            }
        )
    return backups


def validate_and_restore_backup(
    db: Session,
    backup_filename: str,
    confirm_overwrite: bool = False,
) -> Dict[str, Any]:
    if not confirm_overwrite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation (confirm_overwrite=true) is required before restoring a backup.",
        )

    clean_name = Path(backup_filename).name
    backup_path = BACKUPS_DIR / clean_name
    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup file '{clean_name}' not found.")

    # 1. Validate SQLite header and integrity check
    header = backup_path.read_bytes()[:16]
    if not header.startswith(b"SQLite format 3\x00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid backup file: Not a valid SQLite 3 database binary.",
        )

    manifest_file = BACKUPS_DIR / f"{clean_name}.manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        expected_hash = manifest.get("sha256")
        actual_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup file checksum mismatch! File may be corrupted.",
            )

    chk_conn = sqlite3.connect(str(backup_path))
    integrity = chk_conn.execute("PRAGMA integrity_check;").fetchone()
    chk_conn.close()
    if not integrity or integrity[0].lower() != "ok":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQLite integrity check failed: {integrity}",
        )

    # 2. Create automatic pre-restore safety snapshot first
    pre_restore = create_database_backup(db, label="pre_restore_safety")

    # 3. Restore into active SQLite file if file-backed
    target_db_path = _get_sqlite_db_path()
    db.close()
    engine.dispose()

    if target_db_path.exists():
        src_conn = sqlite3.connect(str(backup_path))
        dst_conn = sqlite3.connect(str(target_db_path))
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

    return {
        "status": "restored",
        "restored_from": clean_name,
        "pre_restore_safety_backup": pre_restore["backup_filename"],
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }

