from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_fk(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, future=True)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def _setup_user(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/auth/setup",
        json={
            "username": "arjun",
            "display_name": "Arjun Mehta",
            "password": "StrongLocalPassword!2026",
            "preferred_name": "Arjun",
            "base_currency": "INR",
            "timezone": "Asia/Kolkata",
            "theme": "dark",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ============================================================================
# 1. AUTHENTICATION, SCOPES, AND PRIVACY TESTS
# ============================================================================
def test_auth_setup_login_scopes_and_revocation(client: TestClient):
    # Check uninitialized status
    st = client.get("/api/v1/auth/status")
    assert st.status_code == 200
    assert st.json()["is_initialized"] is False

    # Protected endpoint rejects unauthenticated call
    unauth = client.get("/api/v1/me")
    assert unauth.status_code == 401

    # Initial setup
    auth_data = _setup_user(client)
    jwt_token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # Duplicate setup must be rejected
    dup = client.post(
        "/api/v1/auth/setup",
        json={"username": "hacker", "display_name": "H", "password": "Password12345"},
    )
    assert dup.status_code == 400

    # Invalid login rejected
    bad_login = client.post("/api/v1/auth/login", json={"username": "arjun", "password": "WrongPassword"})
    assert bad_login.status_code == 401

    # Valid login succeeds
    good_login = client.post(
        "/api/v1/auth/login",
        json={"username": "arjun", "password": "StrongLocalPassword!2026"},
    )
    assert good_login.status_code == 200

    # Create a scoped read-only habits token
    tok_resp = client.post(
        "/api/v1/tokens",
        headers=headers,
        json={"name": "Habit Reader Script", "scopes": ["read:habits"], "expires_in_days": 30},
    )
    assert tok_resp.status_code == 201
    tok_json = tok_resp.json()
    raw_api_token = tok_json["raw_token"]
    token_id = tok_json["id"]
    assert raw_api_token.startswith("plos_")

    # Listing tokens must NEVER expose raw_token or token_hash
    list_toks = client.get("/api/v1/tokens", headers=headers)
    assert list_toks.status_code == 200
    for item in list_toks.json():
        assert "raw_token" not in item
        assert "token_hash" not in item

    # Use scoped API token with a clean client (no session cookie)
    client.cookies.clear()
    scoped_headers = {"Authorization": f"Bearer {raw_api_token}"}

    # Allowed: read:habits
    r_hab = client.get("/api/v1/habits", headers=scoped_headers)
    assert r_hab.status_code == 200

    # Forbidden: write:habits with read-only token
    w_hab = client.post(
        "/api/v1/habits",
        headers=scoped_headers,
        json={"name": "Unauthorized Habit", "category": "Health"},
    )
    assert w_hab.status_code == 403

    # Forbidden: read:finance with read:habits token
    r_fin = client.get("/api/v1/transactions", headers=scoped_headers)
    assert r_fin.status_code == 403

    # Revoke token
    rev = client.post(f"/api/v1/tokens/{token_id}/revoke", headers=headers)
    assert rev.status_code == 200
    assert rev.json()["is_revoked"] is True

    # Revoked token must be rejected with 401
    after_rev = client.get("/api/v1/habits", headers=scoped_headers)
    assert after_rev.status_code == 401


# ============================================================================
# 2. HABIT MANAGEMENT & STREAK ALGORITHM TESTS
# ============================================================================
def test_habit_streaks_schedules_and_quantitative_progress(client: TestClient):
    auth_data = _setup_user(client)
    headers = {"Authorization": f"Bearer {auth_data['access_token']}"}

    ref_today = date(2026, 10, 16)  # Friday (weekday=4)
    start_d = date(2026, 10, 12)  # Monday (weekday=0)

    # Create a habit scheduled ONLY on Monday (0), Wednesday (2), Friday (4)
    h_resp = client.post(
        "/api/v1/habits",
        headers=headers,
        json={
            "name": "Strength Training",
            "category": "Fitness",
            "frequency_type": "selected_weekdays",
            "selected_weekdays": [0, 2, 4],
            "target_value": "45",
            "unit": "mins",
            "is_quantitative": True,
            "start_date": start_d.isoformat(),
        },
    )
    assert h_resp.status_code == 201
    habit_id = h_resp.json()["id"]

    # Log Monday (Oct 12) and Wednesday (Oct 14). Tuesday (Oct 13) and Thursday (Oct 15) are unscheduled!
    for d in (date(2026, 10, 12), date(2026, 10, 14)):
        er = client.post(
            f"/api/v1/habits/{habit_id}/entries",
            headers=headers,
            json={"entry_date": d.isoformat(), "completed": True, "value": "45"},
        )
        assert er.status_code == 201

    # Check streak on Friday Oct 16 BEFORE Friday is completed:
    # Unscheduled Tuesday & Thursday must NOT break the streak, and ongoing Friday must preserve streak=2!
    g1 = client.get(f"/api/v1/habits/{habit_id}?ref_date={ref_today.isoformat()}", headers=headers)
    assert g1.status_code == 200
    assert g1.json()["current_streak"] == 2
    assert g1.json()["best_streak"] == 2
    assert g1.json()["missed_scheduled_days_30d"] == 0

    # Log partial progress on Friday Oct 16 (30 mins < 45 mins target) -> not yet completed
    client.post(
        f"/api/v1/habits/{habit_id}/entries",
        headers=headers,
        json={"entry_date": ref_today.isoformat(), "completed": True, "value": "30"},
    )
    g_partial = client.get(f"/api/v1/habits/{habit_id}?ref_date={ref_today.isoformat()}", headers=headers)
    assert g_partial.json()["completed_today"] is False
    assert Decimal(str(g_partial.json()["today_value"])) == Decimal("30.00")

    # Complete full 45 mins on Friday Oct 16 -> streak becomes 3!
    client.post(
        f"/api/v1/habits/{habit_id}/entries",
        headers=headers,
        json={"entry_date": ref_today.isoformat(), "completed": True, "value": "45"},
    )
    g_full = client.get(f"/api/v1/habits/{habit_id}?ref_date={ref_today.isoformat()}", headers=headers)
    assert g_full.json()["completed_today"] is True
    assert g_full.json()["current_streak"] == 3
    assert g_full.json()["completion_rate_30d"] == 100.0


# ============================================================================
# 3. PERSONAL FINANCE, DECIMAL PRECISION, TRANSFERS, BUDGETS & CSV IMPORT
# ============================================================================
def test_finance_decimal_precision_transfers_budgets_and_csv(client: TestClient):
    auth_data = _setup_user(client)
    headers = {"Authorization": f"Bearer {auth_data['access_token']}"}

    # Create two INR accounts
    acc1 = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "HDFC Checking", "account_type": "checking", "currency": "INR", "initial_balance": "10000.00"},
    ).json()
    acc2 = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Emergency Savings", "account_type": "savings", "currency": "INR", "initial_balance": "5000.00"},
    ).json()

    today = date.today()
    month_str = today.strftime("%Y-%m")

    # Create a monthly Food budget of INR 1000.00 with 80% alert threshold
    b_resp = client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "name": "Monthly Food Budget",
            "month": month_str,
            "category": "Food",
            "currency": "INR",
            "amount_limit": "1000.00",
            "alert_threshold_percent": 80,
        },
    )
    assert b_resp.status_code == 201

    # Record income of 50000.55
    client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "amount": "50000.55",
            "currency": "INR",
            "transaction_type": "income",
            "category": "Salary",
            "transaction_date": today.isoformat(),
            "account_id": acc1["id"],
        },
    )

    # Record three expenses testing exact Decimal addition: 333.33 + 333.33 + 183.34 = 850.00 (85% of 1000 budget!)
    for amt in ("333.33", "333.33", "183.34"):
        client.post(
            "/api/v1/transactions",
            headers=headers,
            json={
                "amount": amt,
                "currency": "INR",
                "transaction_type": "expense",
                "category": "Food",
                "merchant": "Fresh Mart",
                "transaction_date": today.isoformat(),
                "account_id": acc1["id"],
            },
        )

    # Record a transfer of 2000.00 from acc1 to acc2 (MUST NOT count as expense or income!)
    client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "amount": "2000.00",
            "currency": "INR",
            "transaction_type": "transfer",
            "category": "Transfer",
            "transaction_date": today.isoformat(),
            "account_id": acc1["id"],
            "to_account_id": acc2["id"],
        },
    )

    # Record a USD expense of $50.00 (MUST NOT be mixed into INR summary!)
    client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "amount": "50.00",
            "currency": "USD",
            "transaction_type": "expense",
            "category": "Software",
            "transaction_date": today.isoformat(),
        },
    )

    summary = client.get(
        f"/api/v1/finance/summary?start_date={today.isoformat()}&end_date={today.isoformat()}&currency=INR",
        headers=headers,
    ).json()

    assert summary["total_income"] == "50000.55"
    assert summary["total_expense"] == "850.00"
    assert summary["total_transfers_excluded"] == "2000.00"
    assert summary["net_savings"] == "49150.55"
    assert set(summary["currencies_present"]) == {"INR", "USD"}
    assert summary["by_currency_totals"]["USD"]["expense"] == "50.00"
    assert len(summary["budget_alerts"]) == 1
    assert summary["budget_alerts"][0]["utilization_percent"] == 85.0

    # Verify account balances reflect transfers accurately
    accs = {a["id"]: a for a in client.get("/api/v1/accounts", headers=headers).json()}
    # acc1: 10000.00 + 50000.55 - 850.00 - 2000.00 = 57150.55
    assert Decimal(str(accs[acc1["id"]]["current_balance"])) == Decimal("57150.55")
    # acc2: 5000.00 + 2000.00 = 7000.00
    assert Decimal(str(accs[acc2["id"]]["current_balance"])) == Decimal("7000.00")

    # Test CSV Import with duplicate detection
    csv_data = (
        "transaction_date,amount,currency,transaction_type,category,merchant\n"
        f"{today.isoformat()},333.33,INR,expense,Food,Fresh Mart\n"
        f"{today.isoformat()},125.50,INR,expense,Transport,Metro Card\n"
    )
    prev = client.post(
        "/api/v1/import/preview",
        headers=headers,
        json={"domain": "transactions", "filename": "bank.csv", "csv_content": csv_data},
    )
    assert prev.status_code == 200
    prev_json = prev.json()
    assert prev_json["total_rows"] == 2
    assert prev_json["duplicate_rows"] == 1
    assert prev_json["valid_rows"] == 1

    commit = client.post(
        "/api/v1/import/commit",
        headers=headers,
        json={"import_job_id": prev_json["import_job_id"], "skip_duplicates": True},
    )
    assert commit.status_code == 200
    assert commit.json()["imported_rows"] == 1


# ============================================================================
# 4. PERSISTENT FOCUS TIMER & OVERLAP INTERVAL UNION TESTS
# ============================================================================
def test_focus_timer_persistence_and_overlap_deduction(client: TestClient):
    auth_data = _setup_user(client)
    headers = {"Authorization": f"Bearer {auth_data['access_token']}"}

    # Start focus timer
    start_resp = client.post(
        "/api/v1/activities/timer/start",
        headers=headers,
        json={
            "activity_name": "System Architecture",
            "category": "Deep Work",
            "project": "Personal Life OS",
            "planned_duration_minutes": 50,
            "is_focus_session": True,
        },
    )
    assert start_resp.status_code == 201
    timer_id = start_resp.json()["id"]
    assert start_resp.json()["timer_status"] == "running"

    # Starting a second timer while one is running must return 409 Conflict
    dup_timer = client.post(
        "/api/v1/activities/timer/start",
        headers=headers,
        json={"activity_name": "Second Timer", "category": "Deep Work"},
    )
    assert dup_timer.status_code == 409

    # Pause, resume, and stop timer
    paused = client.post(f"/api/v1/activities/timer/pause?session_id={timer_id}", headers=headers)
    assert paused.status_code == 200
    assert paused.json()["timer_status"] == "paused"

    resumed = client.post(f"/api/v1/activities/timer/resume?session_id={timer_id}", headers=headers)
    assert resumed.status_code == 200
    assert resumed.json()["timer_status"] == "running"

    stopped = client.post(f"/api/v1/activities/timer/stop?session_id={timer_id}", headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()["timer_status"] == "completed"

    # Test overlapping manual sessions on a specific date:
    # Session A: 10:00 to 11:00 (60m)
    # Session B: 10:30 to 11:30 (60m)
    # Total recorded = 120m, Unique elapsed clock time = 90m!
    test_day = date(2026, 10, 10)
    client.post(
        "/api/v1/activities",
        headers=headers,
        json={
            "activity_name": "Session A",
            "category": "Coding",
            "session_date": test_day.isoformat(),
            "start_time": "2026-10-10T10:00:00Z",
            "end_time": "2026-10-10T11:00:00Z",
            "duration_minutes": 60,
            "is_focus_session": True,
        },
    )
    client.post(
        "/api/v1/activities",
        headers=headers,
        json={
            "activity_name": "Session B",
            "category": "Coding",
            "session_date": test_day.isoformat(),
            "start_time": "2026-10-10T10:30:00Z",
            "end_time": "2026-10-10T11:30:00Z",
            "duration_minutes": 60,
            "is_focus_session": True,
        },
    )

    act_sum = client.get(
        f"/api/v1/activities/summary?start_date={test_day.isoformat()}&end_date={test_day.isoformat()}",
        headers=headers,
    ).json()
    assert act_sum["total_recorded_minutes"] == 120
    assert act_sum["unique_elapsed_clock_minutes"] == 90
    assert act_sum["overlap_minutes_deducted"] == 30
    assert act_sum["overlapping_sessions_count"] == 2


# ============================================================================
# 5. SCREEN TIME, GOALS, WELLBEING, JOURNAL, CONSTELLATION, RHYTHM, WRAPPED, NLQ
# ============================================================================
def test_end_to_end_analytics_constellation_rhythm_wrapped_and_nlq(client: TestClient):
    auth_data = _setup_user(client)
    headers = {"Authorization": f"Bearer {auth_data['access_token']}"}
    today = date.today()

    # Verify empty-state resilience first
    empty_dash = client.get("/api/v1/dashboard", headers=headers)
    assert empty_dash.status_code == 200
    assert empty_dash.json()["metrics"]["sleep"]["status"] == "no_data"

    # Log screen time (including late-night session at 23:30 IST = 18:00 UTC)
    st_resp = client.post(
        "/api/v1/screen-time",
        headers=headers,
        json={
            "app_name": "VS Code",
            "device": "desktop",
            "session_date": today.isoformat(),
            "start_time": datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).replace(hour=18, minute=0).isoformat(),
            "duration_minutes": 120,
        },
    )
    assert st_resp.status_code == 201
    assert st_resp.json()["category"] == "work"
    assert st_resp.json()["productivity_type"] == "productive"

    st_sum = client.get("/api/v1/screen-time/summary", headers=headers).json()
    assert st_sum["total_minutes"] == 120
    assert st_sum["late_night_usage"]["sessions_count"] == 1

    # Create a Goal with milestones and log progress
    goal_resp = client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "name": "Read 12 Engineering Books",
            "category": "Learning",
            "project": "Mastery",
            "target_value": "12",
            "current_value": "3",
            "unit": "books",
            "start_date": (today - timedelta(days=30)).isoformat(),
            "target_date": (today + timedelta(days=60)).isoformat(),
            "milestones": [{"title": "Read 4 Books", "target_value": "4"}],
        },
    )
    assert goal_resp.status_code == 201
    goal_id = goal_resp.json()["id"]

    # Log +1 book -> reaches 4 books -> milestone auto-completes!
    prog_resp = client.post(
        f"/api/v1/goals/{goal_id}/progress",
        headers=headers,
        json={"value_delta": "1", "notes": "Finished Designing Data-Intensive Applications"},
    )
    assert prog_resp.status_code == 201
    assert prog_resp.json()["milestones"][0]["is_completed"] is True

    # Log Wellbeing & Journal
    wb_resp = client.post(
        "/api/v1/wellbeing",
        headers=headers,
        json={
            "record_date": today.isoformat(),
            "sleep_duration_hours": "7.5",
            "sleep_quality": 8,
            "mood_score": 8,
            "energy_score": 9,
            "exercise_duration_minutes": 40,
            "exercise_type": "Running",
            "water_intake_ml": 2500,
        },
    )
    assert wb_resp.status_code == 201

    jr_resp = client.post(
        "/api/v1/journal",
        headers=headers,
        json={
            "entry_date": today.isoformat(),
            "title": "Evening Reflection",
            "content": "Completed core architecture and automated test suite.",
            "daily_intention": "Ship clean, local-first code",
            "review_accomplishments": "Built backend services",
            "tags": ["architecture", "milestone"],
            "is_daily_review": True,
        },
    )
    assert jr_resp.status_code == 201

    # Check Constellation Graph
    const_resp = client.get("/api/v1/constellation", headers=headers)
    assert const_resp.status_code == 200
    assert const_resp.json()["summary"]["total_nodes"] >= 4
    assert const_resp.json()["summary"]["total_edges"] >= 2

    # Check Personal Rhythm Heatmap
    rhythm_resp = client.get("/api/v1/rhythm", headers=headers)
    assert rhythm_resp.status_code == 200
    assert len(rhythm_resp.json()["heatmap_cells"]) == 168
    assert rhythm_resp.json()["total_events"] >= 3

    # Check Life Wrapped Report
    wrapped_resp = client.get(f"/api/v1/wrapped?period_type=month&month={today.strftime('%Y-%m')}", headers=headers)
    assert wrapped_resp.status_code == 200
    assert wrapped_resp.json()["highlights"]["total_screen_time_minutes"] == 120
    assert wrapped_resp.json()["highlights"]["milestones_reached_count"] == 1

    # Check Data Explorer & Schema Browser
    schema_resp = client.get("/api/v1/explorer/schema", headers=headers)
    assert schema_resp.status_code == 200
    assert len(schema_resp.json()["entities"]) >= 12

    exp_resp = client.get("/api/v1/explorer/records?entity_type=goals", headers=headers)
    assert exp_resp.status_code == 200
    assert exp_resp.json()["total"] == 1

    # Check Local Natural-Language Query Engine
    nlq_resp = client.post(
        "/api/v1/nlq",
        headers=headers,
        json={"query": "What was my average daily screen time this month?"},
    )
    assert nlq_resp.status_code == 200
    assert nlq_resp.json()["supported"] is True
    assert "120 minutes" in nlq_resp.json()["answer"]

    # Check Export & Backup
    export_resp = client.get("/api/v1/export?format=json", headers=headers)
    assert export_resp.status_code == 200
    assert export_resp.json()["schema_version"] == "1.0.0"

    bkp_resp = client.post("/api/v1/backups?label=pytest_run", headers=headers)
    assert bkp_resp.status_code == 201
    bkp_name = bkp_resp.json()["backup_filename"]

    # Restore without confirm_overwrite=true must fail with 400
    bad_restore = client.post(
        "/api/v1/backups/restore",
        headers=headers,
        json={"backup_filename": bkp_name, "confirm_overwrite": False},
    )
    assert bad_restore.status_code == 400

