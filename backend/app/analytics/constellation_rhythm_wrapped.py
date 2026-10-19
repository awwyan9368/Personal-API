import math
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ActivitySession,
    Budget,
    Goal,
    GoalHabitLink,
    Habit,
    HabitEntry,
    JournalEntry,
    Milestone,
    ScreenTimeSession,
    Transaction,
    UserPreference,
    WellbeingRecord,
)
from app.services.activity_service import calculate_unique_clock_minutes, compute_elapsed_seconds
from app.services.finance_service import evaluate_budget, get_finance_summary, to_decimal
from app.services.goal_wellbeing_journal_service import serialize_goal
from app.services.habit_service import serialize_habit

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

NODE_COLORS: Dict[str, str] = {
    "habit": "#8b5cf6",
    "goal": "#10b981",
    "project": "#06b6d4",
    "activity_category": "#3b82f6",
    "spending_category": "#f43f5e",
    "application": "#f59e0b",
    "time_period": "#64748b",
    "wellbeing_metric": "#14b8a6",
    "milestone": "#84cc16",
}


def _resolve_tz(db: Session) -> Tuple[ZoneInfo, str]:
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    tz_name = pref.timezone if pref else "Asia/Kolkata"
    try:
        return ZoneInfo(tz_name), tz_name
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC"), "UTC"


# ============================================================================
# 1. PERSONAL DATA CONSTELLATION (INTERACTIVE KNOWLEDGE GRAPH)
# ============================================================================
def build_personal_data_constellation(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    entity_types: Optional[List[str]] = None,
    search: Optional[str] = None,
    max_nodes: int = 120,
) -> Dict[str, Any]:
    """
    Constructs a real, deterministic personal knowledge graph across:
    habits, goals, projects, activity_categories, spending_categories,
    applications, time_periods, wellbeing_metrics, and milestones.
    """
    tz, _ = _resolve_tz(db)
    today = datetime.now(tz).date()
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    currency = (pref.base_currency if pref else "INR").upper()

    allowed_types: Set[str] = (
        set(entity_types)
        if entity_types
        else {
            "habit",
            "goal",
            "project",
            "activity_category",
            "spending_category",
            "application",
            "time_period",
            "wellbeing_metric",
            "milestone",
        }
    )

    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges_list: List[Dict[str, Any]] = []
    seen_edges: Set[Tuple[str, str, str]] = set()

    def _add_node(
        node_id: str,
        label: str,
        entity_type: str,
        metrics: Dict[str, Any],
        link: str,
        subtitle: str = "",
    ):
        if entity_type not in allowed_types:
            return
        if len(nodes_map) >= max_nodes and node_id not in nodes_map:
            return
        nodes_map[node_id] = {
            "id": node_id,
            "label": label,
            "entity_type": entity_type,
            "subtitle": subtitle,
            "color": NODE_COLORS.get(entity_type, "#8b5cf6"),
            "metrics": metrics,
            "link": link,
        }

    def _add_edge(
        source: str,
        target: str,
        relationship_type: str,
        explanation: str,
        weight: float = 1.0,
    ):
        if source not in nodes_map or target not in nodes_map:
            return
        key = (source, target, relationship_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges_list.append(
            {
                "id": f"edge:{source}->{target}:{relationship_type}",
                "source": source,
                "target": target,
                "relationship_type": relationship_type,
                "label": relationship_type.replace("_", " "),
                "explanation": explanation,
                "weight": round(weight, 2),
            }
        )

    # Load domain records within date range
    habits = db.execute(select(Habit)).scalars().all()
    goals = db.execute(select(Goal)).scalars().all()

    tx_stmt = select(Transaction).where(Transaction.currency == currency)
    if start_date:
        tx_stmt = tx_stmt.where(Transaction.transaction_date >= start_date)
    if end_date:
        tx_stmt = tx_stmt.where(Transaction.transaction_date <= end_date)
    txs = db.execute(tx_stmt).scalars().all()

    act_stmt = select(ActivitySession)
    if start_date:
        act_stmt = act_stmt.where(ActivitySession.session_date >= start_date)
    if end_date:
        act_stmt = act_stmt.where(ActivitySession.session_date <= end_date)
    activities = db.execute(act_stmt).scalars().all()

    st_stmt = select(ScreenTimeSession)
    if start_date:
        st_stmt = st_stmt.where(ScreenTimeSession.session_date >= start_date)
    if end_date:
        st_stmt = st_stmt.where(ScreenTimeSession.session_date <= end_date)
    screen_sessions = db.execute(st_stmt).scalars().all()

    wb_stmt = select(WellbeingRecord)
    if start_date:
        wb_stmt = wb_stmt.where(WellbeingRecord.record_date >= start_date)
    if end_date:
        wb_stmt = wb_stmt.where(WellbeingRecord.record_date <= end_date)
    wellbeing_records = db.execute(wb_stmt).scalars().all()

    # 1. Time Periods (YYYY-MM nodes from recorded data)
    periods_seen: Dict[str, int] = {}
    for t in txs:
        ym = t.transaction_date.strftime("%Y-%m")
        periods_seen[ym] = periods_seen.get(ym, 0) + 1
    for a in activities:
        ym = a.session_date.strftime("%Y-%m")
        periods_seen[ym] = periods_seen.get(ym, 0) + 1
    for s in screen_sessions:
        ym = s.session_date.strftime("%Y-%m")
        periods_seen[ym] = periods_seen.get(ym, 0) + 1
    for h in habits:
        for e in h.entries:
            if start_date and e.entry_date < start_date:
                continue
            if end_date and e.entry_date > end_date:
                continue
            ym = e.entry_date.strftime("%Y-%m")
            periods_seen[ym] = periods_seen.get(ym, 0) + 1

    for ym, count in sorted(periods_seen.items(), reverse=True)[:6]:
        _add_node(
            node_id=f"period:{ym}",
            label=f"Period {ym}",
            entity_type="time_period",
            subtitle=f"{count} recorded events",
            metrics={"month": ym, "recorded_events": count},
            link=f"/wrapped?month={ym}",
        )

    # 2. Habits
    for h in habits:
        sh = serialize_habit(db, h, today)
        entries_in_range = [
            e
            for e in h.entries
            if e.completed
            and (not start_date or e.entry_date >= start_date)
            and (not end_date or e.entry_date <= end_date)
        ]
        _add_node(
            node_id=f"habit:{h.id}",
            label=h.name,
            entity_type="habit",
            subtitle=f"Streak: {sh.current_streak}d · {h.category}",
            metrics={
                "category": h.category,
                "current_streak": sh.current_streak,
                "best_streak": sh.best_streak,
                "completion_rate_30d": f"{sh.completion_rate_30d}%",
                "completions_in_period": len(entries_in_range),
            },
            link=f"/habits?highlight={h.id}",
        )
        # Connect habit to time periods where it was completed
        habit_months = set(e.entry_date.strftime("%Y-%m") for e in entries_in_range)
        for ym in habit_months:
            _add_edge(
                source=f"habit:{h.id}",
                target=f"period:{ym}",
                relationship_type="active_in_period",
                explanation=f"Habit '{h.name}' has recorded completions in {ym}.",
            )

    # 3. Goals, Milestones, and Projects
    projects_seen: Dict[str, Dict[str, Any]] = {}
    for g in goals:
        sg = serialize_goal(g, today)
        _add_node(
            node_id=f"goal:{g.id}",
            label=g.name,
            entity_type="goal",
            subtitle=f"{sg.progress_percent}% ({g.current_value}/{g.target_value} {g.unit})",
            metrics={
                "category": g.category,
                "progress_percent": f"{sg.progress_percent}%",
                "current_value": str(g.current_value),
                "target_value": str(g.target_value),
                "unit": g.unit,
                "status": g.status,
            },
            link=f"/goals?highlight={g.id}",
        )

        # Link habits to goal via explicit GoalHabitLink or related_habit_ids
        linked_hids = set(sg.related_habit_ids)
        for link_obj in g.habit_links:
            linked_hids.add(link_obj.habit_id)
        for hid in linked_hids:
            _add_edge(
                source=f"habit:{hid}",
                target=f"goal:{g.id}",
                relationship_type="contributes_to_goal",
                explanation=f"Habit is explicitly linked to goal '{g.name}'.",
                weight=2.0,
            )

        # Also link habits sharing the same category name as the goal
        for h in habits:
            if h.category.strip().lower() == g.category.strip().lower() and h.id not in linked_hids:
                _add_edge(
                    source=f"habit:{h.id}",
                    target=f"goal:{g.id}",
                    relationship_type="shares_category",
                    explanation=f"Both habit '{h.name}' and goal '{g.name}' belong to category '{g.category}'.",
                )

        if g.project:
            proj_key = g.project.strip()
            projects_seen.setdefault(proj_key, {"minutes": 0, "sessions": 0, "goals": 0})
            projects_seen[proj_key]["goals"] += 1

        for ms in g.milestones:
            _add_node(
                node_id=f"milestone:{ms.id}",
                label=ms.title,
                entity_type="milestone",
                subtitle="Completed" if ms.is_completed else "Pending milestone",
                metrics={
                    "goal": g.name,
                    "is_completed": ms.is_completed,
                    "target_value": str(ms.target_value) if ms.target_value is not None else "N/A",
                },
                link=f"/goals?highlight={g.id}",
            )
            _add_edge(
                source=f"goal:{g.id}",
                target=f"milestone:{ms.id}",
                relationship_type="has_milestone",
                explanation=f"Milestone '{ms.title}' is a defined checkpoint for goal '{g.name}'.",
            )

    # 4. Activity Categories & Projects
    act_cat_stats: Dict[str, Dict[str, Any]] = {}
    for a in activities:
        cat = a.category.strip()
        act_cat_stats.setdefault(cat, {"minutes": 0, "sessions": 0, "projects": set(), "periods": set()})
        act_cat_stats[cat]["minutes"] += a.duration_minutes
        act_cat_stats[cat]["sessions"] += 1
        act_cat_stats[cat]["periods"].add(a.session_date.strftime("%Y-%m"))
        if a.project:
            proj_key = a.project.strip()
            act_cat_stats[cat]["projects"].add(proj_key)
            projects_seen.setdefault(proj_key, {"minutes": 0, "sessions": 0, "goals": 0})
            projects_seen[proj_key]["minutes"] += a.duration_minutes
            projects_seen[proj_key]["sessions"] += 1

    for proj_name, p_meta in projects_seen.items():
        _add_node(
            node_id=f"project:{proj_name.lower()}",
            label=proj_name,
            entity_type="project",
            subtitle=f"{p_meta['minutes']}m logged · {p_meta['sessions']} sessions",
            metrics={
                "total_minutes": p_meta["minutes"],
                "total_hours": round(p_meta["minutes"] / 60.0, 2),
                "sessions_count": p_meta["sessions"],
                "linked_goals": p_meta["goals"],
            },
            link=f"/activities?project={proj_name}",
        )

    for g in goals:
        if g.project:
            _add_edge(
                source=f"project:{g.project.strip().lower()}",
                target=f"goal:{g.id}",
                relationship_type="supports_goal",
                explanation=f"Project '{g.project}' is directly associated with goal '{g.name}'.",
            )

    for cat_name, c_meta in act_cat_stats.items():
        node_key = f"activity_cat:{cat_name.lower()}"
        _add_node(
            node_id=node_key,
            label=cat_name,
            entity_type="activity_category",
            subtitle=f"{c_meta['minutes']}m ({c_meta['sessions']} sessions)",
            metrics={
                "total_minutes": c_meta["minutes"],
                "total_hours": round(c_meta["minutes"] / 60.0, 2),
                "sessions_count": c_meta["sessions"],
            },
            link=f"/activities?category={cat_name}",
        )
        for proj_name in c_meta["projects"]:
            _add_edge(
                source=node_key,
                target=f"project:{proj_name.lower()}",
                relationship_type="allocated_to_project",
                explanation=f"Activities in category '{cat_name}' were logged under project '{proj_name}'.",
            )
        for ym in c_meta["periods"]:
            _add_edge(
                source=node_key,
                target=f"period:{ym}",
                relationship_type="logged_in_period",
                explanation=f"Activity category '{cat_name}' has time entries in {ym}.",
            )

    # 5. Spending Categories
    spend_cats: Dict[str, Dict[str, Any]] = {}
    for t in txs:
        if t.transaction_type != "expense":
            continue
        cat = t.category.strip()
        spend_cats.setdefault(cat, {"amount": Decimal("0.00"), "count": 0, "periods": set()})
        spend_cats[cat]["amount"] += to_decimal(t.amount)
        spend_cats[cat]["count"] += 1
        spend_cats[cat]["periods"].add(t.transaction_date.strftime("%Y-%m"))

    for cat_name, s_meta in spend_cats.items():
        node_key = f"spend_cat:{cat_name.lower()}"
        amt_str = str(s_meta["amount"].quantize(Decimal("0.01")))
        _add_node(
            node_id=node_key,
            label=f"{cat_name} (Spend)",
            entity_type="spending_category",
            subtitle=f"{currency} {amt_str} · {s_meta['count']} txns",
            metrics={
                "total_spent": f"{currency} {amt_str}",
                "transactions_count": s_meta["count"],
                "currency": currency,
            },
            link=f"/finance?category={cat_name}",
        )
        for ym in s_meta["periods"]:
            _add_edge(
                source=node_key,
                target=f"period:{ym}",
                relationship_type="spent_in_period",
                explanation=f"Expenses in '{cat_name}' totaling {currency} {amt_str} were recorded in {ym}.",
            )

    # 6. Applications (Screen Time)
    app_stats: Dict[str, Dict[str, Any]] = {}
    for s in screen_sessions:
        app = s.app_name.strip()
        app_stats.setdefault(
            app,
            {"minutes": 0, "sessions": 0, "category": s.category, "productivity": s.productivity_type, "periods": set()},
        )
        app_stats[app]["minutes"] += s.duration_minutes
        app_stats[app]["sessions"] += 1
        app_stats[app]["periods"].add(s.session_date.strftime("%Y-%m"))

    for app_name, a_meta in sorted(app_stats.items(), key=lambda x: x[1]["minutes"], reverse=True)[:15]:
        node_key = f"app:{app_name.lower()}"
        _add_node(
            node_id=node_key,
            label=app_name,
            entity_type="application",
            subtitle=f"{a_meta['minutes']}m · {a_meta['category']}",
            metrics={
                "total_minutes": a_meta["minutes"],
                "total_hours": round(a_meta["minutes"] / 60.0, 2),
                "sessions_count": a_meta["sessions"],
                "category": a_meta["category"],
                "productivity_type": a_meta["productivity"],
            },
            link=f"/screen-time?app={app_name}",
        )
        for ym in a_meta["periods"]:
            _add_edge(
                source=node_key,
                target=f"period:{ym}",
                relationship_type="used_in_period",
                explanation=f"Application '{app_name}' was used for {a_meta['minutes']}m in {ym}.",
            )
        # Connect productive work apps to Deep Work / Work activity categories if present
        if a_meta["category"] in ("work", "learning"):
            for act_cat in act_cat_stats:
                if act_cat.lower() in ("deep work", "work", "coding", "learning", "research"):
                    _add_edge(
                        source=node_key,
                        target=f"activity_cat:{act_cat.lower()}",
                        relationship_type="shares_work_domain",
                        explanation=f"Application '{app_name}' ({a_meta['category']}) aligns with activity category '{act_cat}'.",
                    )

    # 7. Wellbeing Measurements
    if wellbeing_records:
        sleep_days = [r for r in wellbeing_records if r.sleep_duration_hours is not None]
        energy_days = [r for r in wellbeing_records if r.energy_score is not None]
        if sleep_days:
            avg_slp = round(sum(float(r.sleep_duration_hours) for r in sleep_days) / len(sleep_days), 2)
            _add_node(
                node_id="wellbeing:sleep",
                label="Sleep Duration",
                entity_type="wellbeing_metric",
                subtitle=f"Avg {avg_slp}h ({len(sleep_days)} days)",
                metrics={"average_hours": avg_slp, "recorded_days": len(sleep_days)},
                link="/health",
            )
        if energy_days:
            avg_eng = round(sum(r.energy_score for r in energy_days) / len(energy_days), 1)
            _add_node(
                node_id="wellbeing:energy",
                label="Daily Energy & Mood",
                entity_type="wellbeing_metric",
                subtitle=f"Avg Energy {avg_eng}/10 ({len(energy_days)} days)",
                metrics={"average_energy": avg_eng, "recorded_days": len(energy_days)},
                link="/health",
            )
            wb_dates = {r.record_date for r in energy_days}
            for h in habits:
                co_days = sum(1 for e in h.entries if e.completed and e.entry_date in wb_dates)
                if co_days >= 1:
                    _add_edge(
                        source=f"habit:{h.id}",
                        target="wellbeing:energy",
                        relationship_type="co_recorded_days",
                        explanation=f"Habit '{h.name}' was completed on {co_days} day(s) where Daily Energy was also logged (observational co-occurrence).",
                    )

    # Filter by search if provided (keep matching nodes and their immediate 1-hop neighbors)
    if search and search.strip():
        q = search.strip().lower()
        matched_ids = {
            nid
            for nid, nd in nodes_map.items()
            if q in nd["label"].lower() or q in nd["subtitle"].lower() or q in nd["entity_type"].lower()
        }
        neighbor_ids = set(matched_ids)
        for e in edges_list:
            if e["source"] in matched_ids:
                neighbor_ids.add(e["target"])
            if e["target"] in matched_ids:
                neighbor_ids.add(e["source"])
        nodes_map = {nid: nd for nid, nd in nodes_map.items() if nid in neighbor_ids}
        edges_list = [
            e for e in edges_list if e["source"] in nodes_map and e["target"] in nodes_map
        ]

    # Compute concentric / radial coordinates by entity_type group so the graph looks clean and structured
    type_order = [
        "time_period",
        "goal",
        "project",
        "habit",
        "activity_category",
        "spending_category",
        "application",
        "wellbeing_metric",
        "milestone",
    ]
    grouped_nodes: Dict[str, List[Dict[str, Any]]] = {}
    for nd in nodes_map.values():
        grouped_nodes.setdefault(nd["entity_type"], []).append(nd)

    positioned_nodes: List[Dict[str, Any]] = []
    ring_radii = {
        "time_period": 110,
        "goal": 250,
        "project": 250,
        "habit": 390,
        "activity_category": 390,
        "spending_category": 520,
        "application": 520,
        "wellbeing_metric": 390,
        "milestone": 640,
    }

    all_nodes_list = list(nodes_map.values())
    total_n = len(all_nodes_list)
    for idx, nd in enumerate(all_nodes_list):
        etype = nd["entity_type"]
        group_list = grouped_nodes.get(etype, [nd])
        pos_in_group = group_list.index(nd)
        group_len = max(1, len(group_list))
        type_offset = (type_order.index(etype) if etype in type_order else 0) * 0.55
        angle = (2 * math.pi * pos_in_group / group_len) + type_offset
        radius = ring_radii.get(etype, 350)
        nd["position"] = {
            "x": round(600 + radius * math.cos(angle), 1),
            "y": round(420 + radius * math.sin(angle), 1),
        }
        # Count degree (connected edges)
        degree = sum(1 for e in edges_list if e["source"] == nd["id"] or e["target"] == nd["id"])
        nd["degree"] = degree
        positioned_nodes.append(nd)

    counts_by_type: Dict[str, int] = {}
    for nd in positioned_nodes:
        t = nd["entity_type"]
        counts_by_type[t] = counts_by_type.get(t, 0) + 1

    return {
        "nodes": positioned_nodes,
        "edges": edges_list,
        "summary": {
            "total_nodes": total_n,
            "total_edges": len(edges_list),
            "counts_by_type": counts_by_type,
            "is_empty": total_n == 0,
            "empty_state_explanation": (
                "Your Personal Data Constellation will automatically emerge as you record habits, goals, projects, transactions, focus sessions, and wellbeing logs."
                if total_n == 0
                else None
            ),
        },
    }


# ============================================================================
# 2. PERSONAL RHYTHM (WEEKDAY VS HOUR HEATMAP & TEMPORAL ANALYTICS)
# ============================================================================
def _compute_rhythm_window(
    db: Session,
    tz: ZoneInfo,
    start_date: date,
    end_date: date,
    allowed_types: Set[str],
) -> Dict[str, Any]:
    # 7 weekdays (0=Mon..6=Sun) x 24 hours (0..23)
    grid: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for wd in range(7):
        for hr in range(24):
            grid[(wd, hr)] = {
                "weekday": wd,
                "weekday_name": WEEKDAY_NAMES[wd],
                "hour": hr,
                "hour_label": f"{hr:02d}:00",
                "total_minutes": 0,
                "events_count": 0,
                "breakdown": {
                    "focus": 0,
                    "activity": 0,
                    "screen_time": 0,
                    "habit": 0,
                    "exercise": 0,
                    "journal": 0,
                },
                "records": [],
            }

    recorded_dates: Set[date] = set()

    def _add_to_cell(
        dt: Optional[datetime],
        fallback_date: date,
        r_type: str,
        minutes: int,
        title: str,
        record_id: str,
        link: str,
    ):
        if r_type not in allowed_types:
            return
        recorded_dates.add(fallback_date)
        if dt is None:
            # If no explicit timestamp was recorded, we do not fabricate an hour-of-day bin
            return
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone(tz)
        wd = local_dt.weekday()
        hr = local_dt.hour
        cell = grid[(wd, hr)]
        cell["total_minutes"] += max(1, minutes)
        cell["events_count"] += 1
        cell["breakdown"][r_type] = cell["breakdown"].get(r_type, 0) + max(1, minutes)
        if len(cell["records"]) < 15:
            cell["records"].append(
                {
                    "id": record_id,
                    "type": r_type,
                    "title": title,
                    "date": fallback_date.isoformat(),
                    "local_time": local_dt.strftime("%H:%M"),
                    "duration_minutes": minutes,
                    "link": link,
                }
            )

    # 1. Focus & Activities
    if "focus" in allowed_types or "activity" in allowed_types:
        acts = db.execute(
            select(ActivitySession).where(
                ActivitySession.session_date >= start_date,
                ActivitySession.session_date <= end_date,
            )
        ).scalars().all()
        for a in acts:
            rtype = "focus" if a.is_focus_session else "activity"
            mins = a.duration_minutes if a.timer_status == "completed" else max(1, int(round(compute_elapsed_seconds(a) / 60.0)))
            _add_to_cell(
                a.start_time,
                a.session_date,
                rtype,
                mins,
                f"{a.activity_name} ({a.category})",
                a.id,
                f"/activities?highlight={a.id}",
            )

    # 2. Screen Time
    if "screen_time" in allowed_types:
        sts = db.execute(
            select(ScreenTimeSession).where(
                ScreenTimeSession.session_date >= start_date,
                ScreenTimeSession.session_date <= end_date,
            )
        ).scalars().all()
        for s in sts:
            _add_to_cell(
                s.start_time or s.created_at,
                s.session_date,
                "screen_time",
                s.duration_minutes,
                f"{s.app_name} ({s.device})",
                s.id,
                f"/screen-time?highlight={s.id}",
            )

    # 3. Habit Completions
    if "habit" in allowed_types:
        hentries = db.execute(
            select(HabitEntry, Habit)
            .join(Habit, HabitEntry.habit_id == Habit.id)
            .where(
                HabitEntry.entry_date >= start_date,
                HabitEntry.entry_date <= end_date,
                HabitEntry.completed == True,  # noqa: E712
            )
        ).all()
        for he, h in hentries:
            _add_to_cell(
                he.completed_at,
                he.entry_date,
                "habit",
                15,  # Nominal 15m weight for habit completion event visualization
                f"Habit: {h.name}",
                he.id,
                f"/habits?highlight={h.id}",
            )

    # 4. Exercise (from Wellbeing records)
    if "exercise" in allowed_types:
        wbs = db.execute(
            select(WellbeingRecord).where(
                WellbeingRecord.record_date >= start_date,
                WellbeingRecord.record_date <= end_date,
            )
        ).scalars().all()
        for wb in wbs:
            if wb.exercise_duration_minutes and wb.exercise_duration_minutes > 0:
                _add_to_cell(
                    wb.recorded_at,
                    wb.record_date,
                    "exercise",
                    wb.exercise_duration_minutes,
                    f"Exercise: {wb.exercise_type or 'Workout'}",
                    wb.id,
                    f"/health?highlight={wb.id}",
                )

    # 5. Journal Entries
    if "journal" in allowed_types:
        jes = db.execute(
            select(JournalEntry).where(
                JournalEntry.entry_date >= start_date,
                JournalEntry.entry_date <= end_date,
            )
        ).scalars().all()
        for je in jes:
            _add_to_cell(
                je.recorded_at,
                je.entry_date,
                "journal",
                15,
                je.title or "Journal Entry",
                je.id,
                f"/journal?highlight={je.id}",
            )

    cells_list = []
    hourly_totals = [
        {"hour": h, "hour_label": f"{h:02d}:00", "total_minutes": 0, "focus_minutes": 0, "screen_time_minutes": 0, "activity_minutes": 0, "habit_events": 0}
        for h in range(24)
    ]
    weekday_totals = [
        {"weekday": w, "weekday_name": WEEKDAY_NAMES[w], "total_minutes": 0, "focus_minutes": 0, "screen_time_minutes": 0, "events_count": 0}
        for w in range(7)
    ]

    for (wd, hr), cell in sorted(grid.items()):
        cell["data_status"] = "recorded" if cell["events_count"] > 0 else "no_recorded_events"
        cells_list.append(cell)
        hourly_totals[hr]["total_minutes"] += cell["total_minutes"]
        hourly_totals[hr]["focus_minutes"] += cell["breakdown"]["focus"]
        hourly_totals[hr]["screen_time_minutes"] += cell["breakdown"]["screen_time"]
        hourly_totals[hr]["activity_minutes"] += cell["breakdown"]["activity"] + cell["breakdown"]["exercise"]
        hourly_totals[hr]["habit_events"] += 1 if cell["breakdown"]["habit"] > 0 else 0

        weekday_totals[wd]["total_minutes"] += cell["total_minutes"]
        weekday_totals[wd]["focus_minutes"] += cell["breakdown"]["focus"]
        weekday_totals[wd]["screen_time_minutes"] += cell["breakdown"]["screen_time"]
        weekday_totals[wd]["events_count"] += cell["events_count"]

    # Time of day blocks
    tod_blocks = {
        "Morning (05:00-11:59)": {"minutes": 0, "focus_minutes": 0, "screen_time_minutes": 0, "events": 0},
        "Afternoon (12:00-16:59)": {"minutes": 0, "focus_minutes": 0, "screen_time_minutes": 0, "events": 0},
        "Evening (17:00-21:59)": {"minutes": 0, "focus_minutes": 0, "screen_time_minutes": 0, "events": 0},
        "Night (22:00-04:59)": {"minutes": 0, "focus_minutes": 0, "screen_time_minutes": 0, "events": 0},
    }
    for cell in cells_list:
        h = cell["hour"]
        if 5 <= h < 12:
            bkey = "Morning (05:00-11:59)"
        elif 12 <= h < 17:
            bkey = "Afternoon (12:00-16:59)"
        elif 17 <= h < 22:
            bkey = "Evening (17:00-21:59)"
        else:
            bkey = "Night (22:00-04:59)"
        tod_blocks[bkey]["minutes"] += cell["total_minutes"]
        tod_blocks[bkey]["focus_minutes"] += cell["breakdown"]["focus"]
        tod_blocks[bkey]["screen_time_minutes"] += cell["breakdown"]["screen_time"]
        tod_blocks[bkey]["events"] += cell["events_count"]

    weekday_mins = sum(w["total_minutes"] for w in weekday_totals[:5])
    weekend_mins = sum(w["total_minutes"] for w in weekday_totals[5:])
    weekday_focus = sum(w["focus_minutes"] for w in weekday_totals[:5])
    weekend_focus = sum(w["focus_minutes"] for w in weekday_totals[5:])

    total_period_days = max(1, (end_date - start_date).days + 1)
    total_events = sum(c["events_count"] for c in cells_list)
    total_focus_events = sum(1 for c in cells_list if c["breakdown"]["focus"] > 0)

    peak_focus_window = None
    if total_focus_events >= 2:
        best_tod = max(tod_blocks.items(), key=lambda x: x[1]["focus_minutes"])
        if best_tod[1]["focus_minutes"] > 0:
            peak_focus_window = {
                "window": best_tod[0],
                "focus_minutes": best_tod[1]["focus_minutes"],
                "basis": "Derived strictly from recorded focus session timestamps in local time.",
            }

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "period_days": total_period_days,
        "recorded_days": len(recorded_dates),
        "unrecorded_days": max(0, total_period_days - len(recorded_dates)),
        "total_events": total_events,
        "total_minutes": sum(c["total_minutes"] for c in cells_list),
        "heatmap_cells": cells_list,
        "hourly_distribution": hourly_totals,
        "day_of_week_distribution": weekday_totals,
        "time_of_day_comparison": [
            {"window": k, **v} for k, v in tod_blocks.items()
        ],
        "weekday_vs_weekend": {
            "weekday_total_minutes": weekday_mins,
            "weekend_total_minutes": weekend_mins,
            "weekday_avg_minutes_per_day_of_week": round(weekday_mins / 5.0, 1),
            "weekend_avg_minutes_per_day_of_week": round(weekend_mins / 2.0, 1),
            "weekday_focus_minutes": weekday_focus,
            "weekend_focus_minutes": weekend_focus,
        },
        "peak_focus_observation": peak_focus_window,
    }


def get_personal_rhythm(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    activity_types: Optional[List[str]] = None,
    compare_previous: bool = True,
) -> Dict[str, Any]:
    tz, tz_name = _resolve_tz(db)
    today = datetime.now(tz).date()
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=29)

    allowed = (
        set(activity_types)
        if activity_types
        else {"focus", "activity", "screen_time", "habit", "exercise", "journal"}
    )

    primary = _compute_rhythm_window(db, tz, start_date, end_date, allowed)

    comparison = None
    if compare_previous:
        span = max(1, (end_date - start_date).days + 1)
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span - 1)
        prev_win = _compute_rhythm_window(db, tz, prev_start, prev_end, allowed)
        comparison = {
            "previous_start_date": prev_start.isoformat(),
            "previous_end_date": prev_end.isoformat(),
            "previous_total_minutes": prev_win["total_minutes"],
            "previous_total_events": prev_win["total_events"],
            "minutes_delta": primary["total_minutes"] - prev_win["total_minutes"],
            "has_previous_data": prev_win["total_events"] > 0,
            "previous_time_of_day": prev_win["time_of_day_comparison"],
        }

    return {
        "timezone": tz_name,
        "selected_types": sorted(allowed),
        "data_interpretation_note": (
            "Blank cells indicate zero recorded events during that weekday/hour slot, not necessarily inactivity. "
            "All hours are bucketed in your configured local timezone."
        ),
        **primary,
        "period_comparison": comparison,
    }


# ============================================================================
# 3. LIFE WRAPPED (MONTHLY, ANNUAL & CUSTOM RETROSPECTIVE GENERATOR)
# ============================================================================
def generate_life_wrapped(
    db: Session,
    period_type: str = "month",  # month | year | custom
    month: Optional[str] = None,  # YYYY-MM
    year: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    tz, tz_name = _resolve_tz(db)
    today = datetime.now(tz).date()
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    currency = (pref.base_currency if pref else "INR").upper()

    if period_type == "year" or year is not None:
        yr = year or today.year
        p_start = date(yr, 1, 1)
        p_end = min(today, date(yr, 12, 31)) if yr == today.year else date(yr, 12, 31)
        period_label = f"{yr} Annual Life Wrapped"
    elif period_type == "custom" and start_date and end_date:
        p_start = start_date
        p_end = end_date
        period_label = f"Life Retrospective ({p_start.isoformat()} to {p_end.isoformat()})"
    else:
        ym = month or today.strftime("%Y-%m")
        y_str, m_str = ym.split("-")
        yr, mo = int(y_str), int(m_str)
        p_start = date(yr, mo, 1)
        last_d = date(yr, mo, monthrange(yr, mo)[1])
        p_end = min(today, last_d) if (yr == today.year and mo == today.month) else last_d
        period_label = f"{p_start.strftime('%B %Y')} Life Wrapped"

    span_days = max(1, (p_end - p_start).days + 1)

    # 1. Habits Section
    habits = db.execute(select(Habit)).scalars().all()
    habit_stats = []
    total_completions = 0
    best_streak_overall = 0
    best_streak_habit_name = None

    for h in habits:
        entries_in_p = [e for e in h.entries if p_start <= e.entry_date <= p_end and e.completed]
        metrics = calculate_habit_metrics(h, list(h.entries), p_end)
        comp_count = len(entries_in_p)
        total_completions += comp_count
        if metrics["best_streak"] > best_streak_overall:
            best_streak_overall = metrics["best_streak"]
            best_streak_habit_name = h.name
        if comp_count > 0 or h.status == "active":
            habit_stats.append(
                {
                    "id": h.id,
                    "name": h.name,
                    "category": h.category,
                    "completions_in_period": comp_count,
                    "completion_rate_percent": metrics["completion_rate_30d"],
                    "best_streak": metrics["best_streak"],
                    "current_streak": metrics["current_streak"],
                }
            )
    habit_stats.sort(key=lambda x: (x["completions_in_period"], x["completion_rate_percent"]), reverse=True)
    avg_habit_rate = (
        round(sum(h["completion_rate_percent"] for h in habit_stats) / len(habit_stats), 1)
        if habit_stats
        else None
    )

    # 2. Finance Section
    fin = get_finance_summary(db, p_start, p_end, currency)

    # 3. Screen Time Section
    st_sessions = db.execute(
        select(ScreenTimeSession).where(
            ScreenTimeSession.session_date >= p_start,
            ScreenTimeSession.session_date <= p_end,
        )
    ).scalars().all()
    total_screen_mins = sum(s.duration_minutes for s in st_sessions)
    app_usage: Dict[str, int] = {}
    for s in st_sessions:
        app_usage[s.app_name] = app_usage.get(s.app_name, 0) + s.duration_minutes
    most_used_apps = [
        {"app_name": k, "minutes": v, "hours": round(v / 60.0, 2)}
        for k, v in sorted(app_usage.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # 4. Focus & Projects Section
    act_sessions = db.execute(
        select(ActivitySession).where(
            ActivitySession.session_date >= p_start,
            ActivitySession.session_date <= p_end,
        )
    ).scalars().all()
    focus_acts = [a for a in act_sessions if a.is_focus_session]
    total_focus_mins = calculate_unique_clock_minutes(focus_acts)
    total_activity_mins = calculate_unique_clock_minutes(list(act_sessions))
    project_mins: Dict[str, int] = {}
    for a in act_sessions:
        proj = a.project or "General / Unassigned"
        project_mins[proj] = project_mins.get(proj, 0) + a.duration_minutes
    top_projects = [
        {"project": k, "minutes": v, "hours": round(v / 60.0, 2)}
        for k, v in sorted(project_mins.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # 5. Goals & Milestones Section
    all_goals = db.execute(select(Goal)).scalars().all()
    serialized_goals = [serialize_goal(g, p_end) for g in all_goals]
    completed_goals = [g.model_dump(mode="json") for g in serialized_goals if g.status == "completed"]

    milestones_db = db.execute(
        select(Milestone, Goal).join(Goal, Milestone.goal_id == Goal.id).where(Milestone.is_completed == True)  # noqa: E712
    ).all()
    major_milestones = []
    for ms, g in milestones_db:
        ms_d = ms.completed_at.date() if ms.completed_at else (ms.target_date or g.start_date)
        if p_start <= ms_d <= p_end:
            major_milestones.append(
                {
                    "id": ms.id,
                    "title": ms.title,
                    "goal_name": g.name,
                    "date": ms_d.isoformat(),
                }
            )

    # 6. Wellbeing Trends Section
    wb_records = db.execute(
        select(WellbeingRecord).where(
            WellbeingRecord.record_date >= p_start,
            WellbeingRecord.record_date <= p_end,
        )
    ).scalars().all()
    sleep_list = [float(w.sleep_duration_hours) for w in wb_records if w.sleep_duration_hours is not None]
    mood_list = [w.mood_score for w in wb_records if w.mood_score is not None]
    energy_list = [w.energy_score for w in wb_records if w.energy_score is not None]
    exercise_mins = sum(w.exercise_duration_minutes or 0 for w in wb_records)

    # 7. Rhythm Summary
    rhythm = _compute_rhythm_window(
        db, tz, p_start, p_end, {"focus", "activity", "screen_time", "habit", "exercise", "journal"}
    )

    # Build traceable observations
    observations: List[str] = []
    if habit_stats and habit_stats[0]["completions_in_period"] > 0:
        top_h = habit_stats[0]
        observations.append(
            f"Your most consistent habit was '{top_h['name']}' with {top_h['completions_in_period']} completions in this period."
        )
    if Decimal(fin["total_expense"]) > Decimal("0.00"):
        observations.append(
            f"Total recorded spending was {currency} {fin['total_expense']} against {currency} {fin['total_income']} in recorded income."
        )
    if total_focus_mins > 0:
        observations.append(
            f"You dedicated {round(total_focus_mins / 60.0, 1)} hours ({total_focus_mins} unique minutes) across {len(focus_acts)} focus session(s)."
        )
    if sleep_list:
        observations.append(
            f"Across {len(sleep_list)} logged sleep nights, your average sleep duration was {round(sum(sleep_list) / len(sleep_list), 2)} hours."
        )

    unavailable_sections = []
    if total_completions == 0:
        unavailable_sections.append("Habits (no habit completions logged in this date range)")
    if Decimal(fin["total_expense"]) == Decimal("0.00") and Decimal(fin["total_income"]) == Decimal("0.00"):
        unavailable_sections.append("Finance (no income or expense transactions recorded in this date range)")
    if total_screen_mins == 0:
        unavailable_sections.append("Screen Time (no screen-time sessions recorded in this date range)")
    if total_activity_mins == 0:
        unavailable_sections.append("Focus & Activities (no activity sessions recorded in this date range)")
    if not wb_records:
        unavailable_sections.append("Wellbeing (no sleep, mood, or energy logs recorded in this date range)")

    return {
        "title": period_label,
        "period_type": period_type,
        "start_date": p_start.isoformat(),
        "end_date": p_end.isoformat(),
        "span_days": span_days,
        "timezone": tz_name,
        "currency": currency,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "highlights": {
            "total_habit_completions": total_completions,
            "best_habit_streak": best_streak_overall,
            "best_streak_habit": best_streak_habit_name,
            "average_habit_completion_rate_percent": avg_habit_rate,
            "total_expenses": fin["total_expense"],
            "total_income": fin["total_income"],
            "net_savings": fin["net_savings"],
            "total_screen_time_minutes": total_screen_mins,
            "total_screen_time_hours": round(total_screen_mins / 60.0, 2),
            "total_focus_minutes": total_focus_mins,
            "total_focus_hours": round(total_focus_mins / 60.0, 2),
            "total_activity_minutes": total_activity_mins,
            "completed_goals_count": len(completed_goals),
            "milestones_reached_count": len(major_milestones),
        },
        "sections": {
            "habits": {
                "has_data": total_completions > 0,
                "most_consistent_habits": habit_stats[:5],
                "calculation_note": "Count of completed HabitEntry records within start_date..end_date.",
            },
            "finance": {
                "has_data": Decimal(fin["total_expense"]) > Decimal("0.00") or Decimal(fin["total_income"]) > Decimal("0.00"),
                "total_expense": fin["total_expense"],
                "total_income": fin["total_income"],
                "net_savings": fin["net_savings"],
                "largest_spending_categories": fin["category_breakdown"][:5],
                "budgets": fin["budgets"],
                "period_comparison": fin["period_comparison"],
                "calculation_note": f"Exact Decimal sum of {currency} transactions excluding transfers.",
            },
            "screen_time": {
                "has_data": total_screen_mins > 0,
                "total_minutes": total_screen_mins,
                "most_used_applications": most_used_apps,
                "calculation_note": "Sum of duration_minutes across ScreenTimeSession records in period.",
            },
            "focus_and_projects": {
                "has_data": total_activity_mins > 0,
                "total_focus_minutes": total_focus_mins,
                "total_activity_minutes": total_activity_mins,
                "project_allocation": top_projects,
                "calculation_note": "Unique non-overlapping elapsed clock minutes across ActivitySession records.",
            },
            "goals_and_milestones": {
                "has_data": len(completed_goals) > 0 or len(major_milestones) > 0 or len(serialized_goals) > 0,
                "completed_goals": completed_goals,
                "major_milestones": major_milestones,
                "active_goals": [g.model_dump(mode="json") for g in serialized_goals if g.status == "active"],
            },
            "wellbeing": {
                "has_data": len(wb_records) > 0,
                "recorded_days": len(wb_records),
                "average_sleep_hours": round(sum(sleep_list) / len(sleep_list), 2) if sleep_list else None,
                "average_mood_score": round(sum(mood_list) / len(mood_list), 1) if mood_list else None,
                "average_energy_score": round(sum(energy_list) / len(energy_list), 1) if energy_list else None,
                "total_exercise_minutes": exercise_mins,
            },
            "activity_patterns": {
                "has_data": rhythm["total_events"] > 0,
                "time_of_day_comparison": rhythm["time_of_day_comparison"],
                "weekday_vs_weekend": rhythm["weekday_vs_weekend"],
                "peak_focus_observation": rhythm["peak_focus_observation"],
            },
        },
        "observations": observations,
        "unavailable_sections": unavailable_sections,
        "concluding_summary": (
            f"Between {p_start.isoformat()} and {p_end.isoformat()}, you logged {total_completions} habit completions, "
            f"{round(total_focus_mins / 60.0, 1)}h of focus work, and {currency} {fin['total_expense']} in expenses."
            if (total_completions > 0 or total_focus_mins > 0 or Decimal(fin["total_expense"]) > Decimal("0.00"))
            else f"No records were found between {p_start.isoformat()} and {p_end.isoformat()}. Log habits, focus sessions, or expenses to populate this retrospective."
        ),
    }
