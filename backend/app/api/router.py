import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.constellation_rhythm_wrapped import (
    build_personal_data_constellation,
    generate_life_wrapped,
    get_personal_rhythm,
)
from app.analytics.dashboard_timeline_insights import (
    generate_deterministic_insights,
    get_dashboard_overview,
    get_personal_timeline,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    SUPPORTED_SCOPES,
    AuthContext,
    create_access_token,
    generate_api_token,
    get_auth_context,
    hash_password,
    require_scopes,
    verify_password,
)
from app.models.entities import (
    ActivitySession,
    ApiToken,
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
    HabitSchedule,
    ImportJob,
    ImportResult,
    InsightDismissal,
    IntegrationConfig,
    JournalEntry,
    Milestone,
    RecurringTransactionRule,
    ScreenTimeSession,
    Transaction,
    UserPreference,
    UserProfile,
    WellbeingRecord,
)
from app.schemas.api_schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    ApiTokenCreate,
    ApiTokenCreatedResponse,
    ApiTokenResponse,
    AppCategoryMappingCreate,
    AppCategoryMappingResponse,
    AuthResponse,
    BackupRestoreRequest,
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
    FilterPresetCreate,
    GoalCreate,
    GoalProgressCreate,
    GoalResponse,
    GoalUpdate,
    HabitCreate,
    HabitEntryCreate,
    HabitEntryResponse,
    HabitResponse,
    HabitUpdate,
    ImportCommitRequest,
    ImportPreviewRequest,
    InsightStatusUpdate,
    JournalCreate,
    JournalResponse,
    JournalUpdate,
    LoginRequest,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    NLQueryRequest,
    PasswordChangeRequest,
    RecurringRuleCreate,
    RecurringRuleResponse,
    ScreenTimeCreate,
    ScreenTimeResponse,
    ScreenTimeUpdate,
    SetupRequest,
    SetupStatusResponse,
    TimerStartRequest,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    UserPreferenceSchema,
    UserPreferenceUpdate,
    UserProfileResponse,
    WellbeingCreate,
    WellbeingResponse,
    WellbeingUpdate,
)
from app.services.activity_service import (
    create_manual_activity,
    detect_overlapping_session_ids,
    get_active_timer,
    get_activities_summary,
    pause_focus_timer,
    resume_focus_timer,
    serialize_activity,
    start_focus_timer,
    stop_focus_timer,
    update_activity_session,
)
from app.services.explorer_nlq_backup_service import (
    commit_csv_import,
    create_database_backup,
    execute_local_nl_query,
    explore_records,
    export_all_personal_data,
    get_schema_browser,
    list_database_backups,
    preview_csv_import,
    validate_and_restore_backup,
)
from app.services.finance_service import (
    create_transaction,
    evaluate_budget,
    get_finance_summary,
    process_recurring_rules,
    serialize_account,
    serialize_transaction,
    to_decimal,
    update_transaction,
)
from app.services.goal_wellbeing_journal_service import (
    add_goal_milestone,
    create_goal,
    create_journal_entry,
     get_wellbeing_summary,
    log_goal_progress,
    serialize_goal,
    serialize_journal,
    serialize_wellbeing,
    update_goal,
    update_goal_milestone,
    update_journal_entry,
    upsert_wellbeing_record,
)
from app.services.habit_service import (
    create_habit,
    log_habit_entry,
    serialize_habit,
    update_habit,
)
from app.services.screen_time_service import (
    create_screen_time_session,
    get_screen_time_summary,
    update_screen_time_session,
)

api_router = APIRouter()


def _serialize_user(user: UserProfile) -> UserProfileResponse:
    pref = user.preferences
    widgets = [
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
            if isinstance(parsed, list):
                widgets = parsed
        except Exception:
            pass

    pref_schema = (
        UserPreferenceSchema(
            preferred_name=pref.preferred_name,
            timezone=pref.timezone,
            base_currency=pref.base_currency,
            date_format=pref.date_format,
            number_format=pref.number_format,
            week_start_day=pref.week_start_day,
            theme=pref.theme,
            daily_screen_time_target_minutes=pref.daily_screen_time_target_minutes,
            focus_session_duration_minutes=pref.focus_session_duration_minutes,
            break_duration_minutes=pref.break_duration_minutes,
            break_reminders_enabled=pref.break_reminders_enabled,
            habit_reminders_enabled=pref.habit_reminders_enabled,
            budget_alert_threshold_percent=pref.budget_alert_threshold_percent,
            dashboard_widgets=widgets,
            external_integrations_enabled=pref.external_integrations_enabled,
            today_intention=pref.today_intention,
            today_intention_date=pref.today_intention_date,
        )
        if pref
        else UserPreferenceSchema()
    )
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        bio=user.bio,
        created_at=user.created_at,
        preferences=pref_schema,
    )


def _ensure_default_integrations(db: Session):
    defaults = [
        (
            "local_screen_time_collector",
            "Local OS Screen-Time Collector",
            "companion_script",
            "Optional Python script (scripts/screen_time_collector.py) that polls active window titles locally and posts to /api/v1/screen-time.",
        ),
        (
            "csv_bank_importer",
            "Local CSV Bank & Expense Importer",
            "file_adapter",
            "Built-in zero-cloud CSV parser with duplicate hash detection and field mapping.",
        ),
        (
            "local_rest_webhooks",
            "Personal Automation Scripts (Python / PowerShell)",
            "rest_api",
            "Direct local REST API access using scoped plos_ personal tokens.",
        ),
    ]
    existing_keys = set(db.execute(select(IntegrationConfig.key)).scalars().all())
    added = False
    for key, name, itype, desc in defaults:
        if key not in existing_keys:
            is_cfg = key == "csv_bank_importer" or key == "local_rest_webhooks"
            db.add(
                IntegrationConfig(
                    key=key,
                    name=name,
                    integration_type=itype,
                    is_enabled=is_cfg,
                    is_configured=is_cfg,
                    is_receiving_data=is_cfg,
                    config_json=json.dumps({"description": desc, "requires_internet": False}),
                    status_message="Ready (Local Built-in)" if is_cfg else "Unconfigured (Manual/Companion Script)",
                )
            )
            added = True
    if added:
        db.commit()


# ============================================================================
# HEALTH, AUTHENTICATION & PROFILE
# ============================================================================
@api_router.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    user_count = db.execute(select(UserProfile)).scalars().all()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "local_first": True,
        "is_initialized": len(user_count) > 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/auth/status", response_model=SetupStatusResponse, tags=["Authentication"])
def auth_setup_status(db: Session = Depends(get_db)):
    user = db.execute(select(UserProfile)).scalars().first()
    return SetupStatusResponse(
        is_initialized=user is not None,
        has_user=user is not None,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
    )


@api_router.post("/auth/setup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def initial_account_setup(payload: SetupRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.execute(select(UserProfile)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Personal Life OS is already initialized. Please sign in with your existing credentials.",
        )

    user = UserProfile(
        username=payload.username.strip(),
        display_name=payload.display_name.strip(),
        email=payload.email.strip() if payload.email else None,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    pref = UserPreference(
        user_id=user.id,
        preferred_name=(payload.preferred_name or payload.display_name).strip(),
        base_currency=payload.base_currency.upper(),
        timezone=payload.timezone,
        theme=payload.theme,
    )
    db.add(pref)

    # Create a default primary financial account in the user's base currency
    default_acc = FinancialAccount(
        name="Primary Account",
        account_type="checking",
        currency=payload.base_currency.upper(),
        initial_balance=to_decimal(0),
        color="#8b5cf6",
        icon="landmark",
    )
    db.add(default_acc)
    db.commit()
    db.refresh(user)
    _ensure_default_integrations(db)

    token = create_access_token(subject=user.id, scopes=["read:all", "write:all"])
    response.set_cookie(
        key="plos_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return AuthResponse(access_token=token, user=_serialize_user(user))


@api_router.post("/auth/login", response_model=AuthResponse, tags=["Authentication"])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.execute(
        select(UserProfile).where(UserProfile.username == payload.username.strip())
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(subject=user.id, scopes=["read:all", "write:all"])
    response.set_cookie(
        key="plos_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return AuthResponse(access_token=token, user=_serialize_user(user))


@api_router.post("/auth/logout", tags=["Authentication"])
def logout(response: Response):
    response.delete_cookie("plos_session")
    return {"status": "logged_out"}


@api_router.post("/auth/change-password", tags=["Authentication"])
def change_password(
    payload: PasswordChangeRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    user = db.execute(select(UserProfile).where(UserProfile.id == auth.user_id)).scalar_one_or_none()
    if not user or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"status": "password_updated"}


@api_router.get("/me", response_model=UserProfileResponse, tags=["Profile & Settings"])
def get_me(auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    user = db.execute(select(UserProfile).where(UserProfile.id == auth.user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _serialize_user(user)


@api_router.patch("/me/preferences", response_model=UserProfileResponse, tags=["Profile & Settings"])
def update_preferences(
    payload: UserPreferenceUpdate,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    user = db.execute(select(UserProfile).where(UserProfile.id == auth.user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    pref = user.preferences
    if not pref:
        pref = UserPreference(user_id=user.id)
        db.add(pref)
        db.flush()

    data = payload.model_dump(exclude_unset=True)
    for user_field in ("display_name", "email", "bio"):
        if user_field in data:
            setattr(user, user_field, data.pop(user_field))

    if "dashboard_widgets" in data and data["dashboard_widgets"] is not None:
        pref.dashboard_widgets_json = json.dumps(data.pop("dashboard_widgets"))

    if "base_currency" in data and data["base_currency"] is not None:
        data["base_currency"] = data["base_currency"].upper()

    for k, v in data.items():
        if hasattr(pref, k):
            setattr(pref, k, v)

    db.commit()
    db.refresh(user)
    return _serialize_user(user)


# ============================================================================
# API TOKENS & INTEGRATIONS CONSOLE
# ============================================================================
@api_router.get("/tokens", response_model=List[ApiTokenResponse], tags=["API & Integrations"])
def list_api_tokens(auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    tokens = db.execute(
        select(ApiToken).where(ApiToken.user_id == auth.user_id).order_by(ApiToken.created_at.desc())
    ).scalars().all()
    return [
        ApiTokenResponse(
            id=t.id,
            name=t.name,
            token_prefix=t.token_prefix,
            scopes=[s.strip() for s in t.scopes.split(",") if s.strip()],
            expires_at=t.expires_at,
            last_used_at=t.last_used_at,
            is_revoked=t.is_revoked,
            revoked_at=t.revoked_at,
            created_at=t.created_at,
        )
        for t in tokens
    ]


@api_router.post(
    "/tokens",
    response_model=ApiTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["API & Integrations"],
)
def create_personal_api_token(
    payload: ApiTokenCreate,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    invalid_scopes = [s for s in payload.scopes if s not in SUPPORTED_SCOPES]
    if invalid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported scope(s): {invalid_scopes}. Supported scopes: {SUPPORTED_SCOPES}",
        )

    raw_token, prefix, token_hash = generate_api_token()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days
        else None
    )

    token_obj = ApiToken(
        user_id=auth.user_id,
        name=payload.name.strip(),
        token_prefix=prefix,
        token_hash=token_hash,
        scopes=",".join(payload.scopes),
        expires_at=expires_at,
    )
    db.add(token_obj)
    db.commit()
    db.refresh(token_obj)

    return ApiTokenCreatedResponse(
        id=token_obj.id,
        name=token_obj.name,
        token_prefix=token_obj.token_prefix,
        scopes=payload.scopes,
        expires_at=token_obj.expires_at,
        last_used_at=token_obj.last_used_at,
        is_revoked=token_obj.is_revoked,
        revoked_at=token_obj.revoked_at,
        created_at=token_obj.created_at,
        raw_token=raw_token,
    )


@api_router.post("/tokens/{token_id}/revoke", response_model=ApiTokenResponse, tags=["API & Integrations"])
def revoke_api_token(
    token_id: str,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    token_obj = db.execute(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == auth.user_id)
    ).scalar_one_or_none()
    if not token_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found.")
    token_obj.is_revoked = True
    token_obj.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(token_obj)
    return ApiTokenResponse(
        id=token_obj.id,
        name=token_obj.name,
        token_prefix=token_obj.token_prefix,
        scopes=[s.strip() for s in token_obj.scopes.split(",") if s.strip()],
        expires_at=token_obj.expires_at,
        last_used_at=token_obj.last_used_at,
        is_revoked=token_obj.is_revoked,
        revoked_at=token_obj.revoked_at,
        created_at=token_obj.created_at,
    )


@api_router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["API & Integrations"])
def delete_api_token(
    token_id: str,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    token_obj = db.execute(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == auth.user_id)
    ).scalar_one_or_none()
    if not token_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found.")
    db.delete(token_obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/integrations", tags=["API & Integrations"])
def list_integrations(auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    _ensure_default_integrations(db)
    items = db.execute(select(IntegrationConfig).order_by(IntegrationConfig.name.asc())).scalars().all()
    return {
        "external_integrations_enabled_globally": settings.ENABLE_EXTERNAL_INTEGRATIONS,
        "integrations": [
            {
                "id": i.id,
                "key": i.key,
                "name": i.name,
                "integration_type": i.integration_type,
                "is_enabled": i.is_enabled,
                "is_configured": i.is_configured,
                "is_receiving_data": i.is_receiving_data,
                "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
                "status_message": i.status_message,
                "config": json.loads(i.config_json or "{}"),
            }
            for i in items
        ],
    }


@api_router.get("/catalog", tags=["API & Integrations"])
def get_api_catalog(auth: AuthContext = Depends(get_auth_context)):
    """
    Returns documented endpoints, scopes, and sample request payloads for the interactive API Playground.
    """
    return {
        "base_url": "/api/v1",
        "supported_scopes": SUPPORTED_SCOPES,
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/v1/health",
                "scope": "public",
                "summary": "Check local backend health and initialization state",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/me",
                "scope": "authenticated",
                "summary": "Retrieve current user profile and preferences",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/dashboard",
                "scope": "read:analytics",
                "summary": "Get Overview Dashboard metrics, comparisons, and charts",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/habits",
                "scope": "read:habits",
                "summary": "List all tracked habits with streaks and 30d completion rates",
                "sample_body": None,
            },
            {
                "method": "POST",
                "path": "/api/v1/habits",
                "scope": "write:habits",
                "summary": "Create a new habit",
                "sample_body": {
                    "name": "Deep Reading",
                    "category": "Learning",
                    "frequency_type": "daily",
                    "selected_weekdays": [0, 1, 2, 3, 4, 5, 6],
                    "target_value": "30",
                    "unit": "pages",
                    "is_quantitative": True,
                },
            },
            {
                "method": "GET",
                "path": "/api/v1/transactions",
                "scope": "read:finance",
                "summary": "List financial transactions with optional filters",
                "sample_body": None,
            },
            {
                "method": "POST",
                "path": "/api/v1/transactions",
                "scope": "write:finance",
                "summary": "Record a new expense, income, or transfer",
                "sample_body": {
                    "amount": "450.00",
                    "currency": "INR",
                    "transaction_type": "expense",
                    "category": "Food & Dining",
                    "merchant": "Filter Coffee House",
                    "payment_method": "UPI",
                    "notes": "Morning coffee and breakfast",
                },
            },
            {
                "method": "GET",
                "path": "/api/v1/finance/summary",
                "scope": "read:finance",
                "summary": "Get consolidated Decimal financial summary and category breakdown",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/screen-time",
                "scope": "read:screen_time",
                "summary": "List screen-time sessions",
                "sample_body": None,
            },
            {
                "method": "POST",
                "path": "/api/v1/screen-time",
                "scope": "write:screen_time",
                "summary": "Log a screen-time session",
                "sample_body": {
                    "app_name": "VS Code",
                    "device": "desktop",
                    "duration_minutes": 95,
                    "category": "work",
                    "productivity_type": "productive",
                    "data_source": "api",
                },
            },
            {
                "method": "GET",
                "path": "/api/v1/activities",
                "scope": "read:activities",
                "summary": "List activity and focus sessions",
                "sample_body": None,
            },
            {
                "method": "POST",
                "path": "/api/v1/activities/timer/start",
                "scope": "write:activities",
                "summary": "Start a persistent focus timer session",
                "sample_body": {
                    "activity_name": "Architecture & Coding",
                    "category": "Deep Work",
                    "project": "Personal Life OS",
                    "planned_duration_minutes": 50,
                    "is_focus_session": True,
                },
            },
            {
                "method": "GET",
                "path": "/api/v1/goals",
                "scope": "read:goals",
                "summary": "List goals, milestones, and progress",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/journal",
                "scope": "read:journal",
                "summary": "List private journal entries and daily reviews",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/wellbeing",
                "scope": "read:wellbeing",
                "summary": "List sleep, mood, energy, and exercise records",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/insights",
                "scope": "read:analytics",
                "summary": "Generate deterministic local insights",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/timeline",
                "scope": "read:all",
                "summary": "Get unified chronological personal timeline",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/constellation",
                "scope": "read:all",
                "summary": "Get Personal Data Constellation knowledge graph nodes and edges",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/rhythm",
                "scope": "read:all",
                "summary": "Get Personal Rhythm 7x24 weekday-vs-hour heatmap",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/wrapped",
                "scope": "read:all",
                "summary": "Generate Life Wrapped monthly or annual retrospective report",
                "sample_body": None,
            },
            {
                "method": "GET",
                "path": "/api/v1/export",
                "scope": "read:exports",
                "summary": "Export complete personal dataset as JSON or CSV",
                "sample_body": None,
            },
        ],
    }


# ============================================================================
# DASHBOARD, INSIGHTS, TIMELINE, CONSTELLATION, RHYTHM, WRAPPED, EXPLORER, NLQ
# ============================================================================
@api_router.get("/dashboard", tags=["Analytics & Overview"])
def api_get_dashboard(
    ref_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:analytics")),
    db: Session = Depends(get_db),
):
    return get_dashboard_overview(db, ref_date=ref_date)


@api_router.get("/insights", tags=["Analytics & Overview"])
def api_get_insights(
    include_dismissed: bool = False,
    auth: AuthContext = Depends(require_scopes("read:analytics")),
    db: Session = Depends(get_db),
):
    return generate_deterministic_insights(db, include_dismissed=include_dismissed)


@api_router.post("/insights/status", tags=["Analytics & Overview"])
def api_update_insight_status(
    payload: InsightStatusUpdate,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(InsightDismissal).where(InsightDismissal.insight_key == payload.insight_key)
    ).scalar_one_or_none()
    if payload.status == "active":
        if existing:
            db.delete(existing)
            db.commit()
        return {"insight_key": payload.insight_key, "status": "active"}

    if existing:
        existing.status = payload.status
    else:
        db.add(InsightDismissal(insight_key=payload.insight_key, status=payload.status))
    db.commit()
    return {"insight_key": payload.insight_key, "status": payload.status}


@api_router.get("/timeline", tags=["Analytics & Overview"])
def api_get_timeline(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    event_types: Optional[str] = Query(default=None, description="Comma-separated event types"),
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(require_scopes("read:all")),
    db: Session = Depends(get_db),
):
    types_list = [t.strip() for t in event_types.split(",") if t.strip()] if event_types else None
    return get_personal_timeline(
        db,
        start_date=start_date,
        end_date=end_date,
        event_types=types_list,
        search=search,
        limit=limit,
    )


@api_router.get("/constellation", tags=["Advanced Visualizations"])
def api_get_constellation(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    entity_types: Optional[str] = Query(default=None, description="Comma-separated entity types"),
    search: Optional[str] = None,
    max_nodes: int = Query(default=120, ge=10, le=300),
    auth: AuthContext = Depends(require_scopes("read:all")),
    db: Session = Depends(get_db),
):
    types_list = [t.strip() for t in entity_types.split(",") if t.strip()] if entity_types else None
    return build_personal_data_constellation(
        db,
        start_date=start_date,
        end_date=end_date,
        entity_types=types_list,
        search=search,
        max_nodes=max_nodes,
    )


@api_router.get("/rhythm", tags=["Advanced Visualizations"])
def api_get_personal_rhythm(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    activity_types: Optional[str] = Query(default=None, description="Comma-separated activity types"),
    compare_previous: bool = True,
    auth: AuthContext = Depends(require_scopes("read:all")),
    db: Session = Depends(get_db),
):
    types_list = [t.strip() for t in activity_types.split(",") if t.strip()] if activity_types else None
    return get_personal_rhythm(
        db,
        start_date=start_date,
        end_date=end_date,
        activity_types=types_list,
        compare_previous=compare_previous,
    )


@api_router.get("/wrapped", tags=["Advanced Visualizations"])
def api_get_life_wrapped(
    period_type: str = Query(default="month", pattern="^(month|year|custom)$"),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:all")),
    db: Session = Depends(get_db),
):
    return generate_life_wrapped(
        db,
        period_type=period_type,
        month=month,
        year=year,
        start_date=start_date,
        end_date=end_date,
    )


@api_router.get("/explorer/schema", tags=["Data Explorer"])
def api_get_schema_browser(auth: AuthContext = Depends(require_scopes("read:all"))):
    return get_schema_browser()


@api_router.get("/explorer/records", tags=["Data Explorer"])
def api_explore_records(
    entity_type: str = Query(default="transactions"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    auth: AuthContext = Depends(require_scopes("read:all")),
    db: Session = Depends(get_db),
):
    return explore_records(
        db,
        entity_type=entity_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@api_router.get("/explorer/presets", tags=["Data Explorer"])
def api_list_filter_presets(auth: AuthContext = Depends(require_scopes("read:all")), db: Session = Depends(get_db)):
    presets = db.execute(select(FilterPreset).order_by(FilterPreset.created_at.desc())).scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "entity_type": p.entity_type,
            "filters": json.loads(p.filter_json or "{}"),
            "created_at": p.created_at.isoformat(),
        }
        for p in presets
    ]


@api_router.post("/explorer/presets", status_code=status.HTTP_201_CREATED, tags=["Data Explorer"])
def api_create_filter_preset(
    payload: FilterPresetCreate,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    p = FilterPreset(
        name=payload.name.strip(),
        entity_type=payload.entity_type.strip(),
        filter_json=json.dumps(payload.filters),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {
        "id": p.id,
        "name": p.name,
        "entity_type": p.entity_type,
        "filters": payload.filters,
        "created_at": p.created_at.isoformat(),
    }


@api_router.delete("/explorer/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Data Explorer"])
def api_delete_filter_preset(
    preset_id: str,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    p = db.execute(select(FilterPreset).where(FilterPreset.id == preset_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter preset not found.")
    db.delete(p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/nlq", tags=["Analytics & Overview"])
def api_natural_language_query(
    payload: NLQueryRequest,
    auth: AuthContext = Depends(require_scopes("read:all")),
    db: Session = Depends(get_db),
):
    return execute_local_nl_query(db, payload.query)


# ============================================================================
# HABITS ENDPOINTS
# ============================================================================
@api_router.get("/habits", response_model=List[HabitResponse], tags=["Habits"])
def api_list_habits(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category: Optional[str] = None,
    search: Optional[str] = None,
    ref_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:habits")),
    db: Session = Depends(get_db),
):
    stmt = select(Habit).order_by(Habit.created_at.asc())
    if status_filter:
        stmt = stmt.where(Habit.status == status_filter)
    if category:
        stmt = stmt.where(Habit.category.ilike(f"%{category}%"))
    habits = db.execute(stmt).scalars().all()
    if search:
        q = search.strip().lower()
        habits = [h for h in habits if q in h.name.lower() or q in (h.description or "").lower()]
    return [serialize_habit(db, h, reference_today=ref_date) for h in habits]


@api_router.post("/habits", response_model=HabitResponse, status_code=status.HTTP_201_CREATED, tags=["Habits"])
def api_create_habit(
    payload: HabitCreate,
    auth: AuthContext = Depends(require_scopes("write:habits")),
    db: Session = Depends(get_db),
):
    return create_habit(db, payload)


@api_router.get("/habits/{habit_id}", response_model=HabitResponse, tags=["Habits"])
def api_get_habit(
    habit_id: str,
    ref_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:habits")),
    db: Session = Depends(get_db),
):
    habit = db.execute(select(Habit).where(Habit.id == habit_id)).scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")
    return serialize_habit(db, habit, reference_today=ref_date)


@api_router.patch("/habits/{habit_id}", response_model=HabitResponse, tags=["Habits"])
def api_update_habit(
    habit_id: str,
    payload: HabitUpdate,
    auth: AuthContext = Depends(require_scopes("write:habits")),
    db: Session = Depends(get_db),
):
    habit = db.execute(select(Habit).where(Habit.id == habit_id)).scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")
    return update_habit(db, habit, payload)


@api_router.delete("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Habits"])
def api_delete_habit(
    habit_id: str,
    auth: AuthContext = Depends(require_scopes("write:habits")),
    db: Session = Depends(get_db),
):
    habit = db.execute(select(Habit).where(Habit.id == habit_id)).scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")
    db.delete(habit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/habits/{habit_id}/entries", response_model=List[HabitEntryResponse], tags=["Habits"])
def api_list_habit_entries(
    habit_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:habits")),
    db: Session = Depends(get_db),
):
    habit = db.execute(select(Habit).where(Habit.id == habit_id)).scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")
    stmt = select(HabitEntry).where(HabitEntry.habit_id == habit_id).order_by(HabitEntry.entry_date.desc())
    if start_date:
        stmt = stmt.where(HabitEntry.entry_date >= start_date)
    if end_date:
        stmt = stmt.where(HabitEntry.entry_date <= end_date)
    entries = db.execute(stmt).scalars().all()
    return [HabitEntryResponse.model_validate(e) for e in entries]


@api_router.post(
    "/habits/{habit_id}/entries",
    response_model=HabitEntryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Habits"],
)
def api_log_habit_entry(
    habit_id: str,
    payload: HabitEntryCreate,
    auth: AuthContext = Depends(require_scopes("write:habits")),
    db: Session = Depends(get_db),
):
    habit = db.execute(select(Habit).where(Habit.id == habit_id)).scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")
    entry = log_habit_entry(db, habit, payload)
    return HabitEntryResponse.model_validate(entry)


@api_router.delete(
    "/habits/{habit_id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Habits"],
)
def api_delete_habit_entry(
    habit_id: str,
    entry_id: str,
    auth: AuthContext = Depends(require_scopes("write:habits")),
    db: Session = Depends(get_db),
):
    entry = db.execute(
        select(HabitEntry).where(HabitEntry.id == entry_id, HabitEntry.habit_id == habit_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit entry not found.")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# PERSONAL FINANCE ENDPOINTS
# ============================================================================
@api_router.get("/accounts", response_model=List[AccountResponse], tags=["Finance"])
def api_list_accounts(
    auth: AuthContext = Depends(require_scopes("read:finance")),
    db: Session = Depends(get_db),
):
    accounts = db.execute(select(FinancialAccount).order_by(FinancialAccount.created_at.asc())).scalars().all()
    return [serialize_account(db, a) for a in accounts]


@api_router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED, tags=["Finance"])
def api_create_account(
    payload: AccountCreate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    exists = db.execute(
        select(FinancialAccount).where(FinancialAccount.name.ilike(payload.name.strip()))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this name already exists.")
    acc = FinancialAccount(
        name=payload.name.strip(),
        account_type=payload.account_type,
        currency=payload.currency.upper(),
        initial_balance=to_decimal(payload.initial_balance),
        color=payload.color,
        icon=payload.icon,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return serialize_account(db, acc)


@api_router.patch("/accounts/{account_id}", response_model=AccountResponse, tags=["Finance"])
def api_update_account(
    account_id: str,
    payload: AccountUpdate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    acc = db.execute(select(FinancialAccount).where(FinancialAccount.id == account_id)).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    data = payload.model_dump(exclude_unset=True)
    if "initial_balance" in data and data["initial_balance"] is not None:
        data["initial_balance"] = to_decimal(data["initial_balance"])
    if "currency" in data and data["currency"] is not None:
        data["currency"] = data["currency"].upper()
    for k, v in data.items():
        setattr(acc, k, v)
    db.commit()
    db.refresh(acc)
    return serialize_account(db, acc)


@api_router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Finance"])
def api_delete_account(
    account_id: str,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    acc = db.execute(select(FinancialAccount).where(FinancialAccount.id == account_id)).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    db.delete(acc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/transactions", tags=["Finance"])
def api_list_transactions(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    account_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="transaction_date", pattern="^(transaction_date|amount|created_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_scopes("read:finance")),
    db: Session = Depends(get_db),
):
    stmt = select(Transaction)
    if start_date:
        stmt = stmt.where(Transaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(Transaction.transaction_date <= end_date)
    if transaction_type:
        stmt = stmt.where(Transaction.transaction_type == transaction_type)
    if category:
        stmt = stmt.where(Transaction.category.ilike(f"%{category}%"))
    if currency:
        stmt = stmt.where(Transaction.currency == currency.upper())
    if account_id:
        stmt = stmt.where((Transaction.account_id == account_id) | (Transaction.to_account_id == account_id))

    sort_col = getattr(Transaction, sort_by, Transaction.transaction_date)
    stmt = stmt.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc(), Transaction.created_at.desc())

    txs = db.execute(stmt).scalars().all()
    if search:
        q = search.strip().lower()
        txs = [
            t
            for t in txs
            if q in (t.category or "").lower()
            or q in (t.merchant or "").lower()
            or q in (t.notes or "").lower()
            or q in (t.tags_csv or "").lower()
        ]

    total = len(txs)
    start_idx = (page - 1) * page_size
    sliced = txs[start_idx : start_idx + page_size]
    acc_map = {a.id: a.name for a in db.execute(select(FinancialAccount)).scalars().all()}

    return {
        "items": [serialize_transaction(db, t, acc_map).model_dump(mode="json") for t in sliced],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@api_router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Finance"],
)
def api_create_transaction(
    payload: TransactionCreate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    return create_transaction(db, payload)


@api_router.get("/transactions/{transaction_id}", response_model=TransactionResponse, tags=["Finance"])
def api_get_transaction(
    transaction_id: str,
    auth: AuthContext = Depends(require_scopes("read:finance")),
    db: Session = Depends(get_db),
):
    tx = db.execute(select(Transaction).where(Transaction.id == transaction_id)).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")
    return serialize_transaction(db, tx)


@api_router.patch("/transactions/{transaction_id}", response_model=TransactionResponse, tags=["Finance"])
def api_update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    tx = db.execute(select(Transaction).where(Transaction.id == transaction_id)).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")
    return update_transaction(db, tx, payload)


@api_router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Finance"])
def api_delete_transaction(
    transaction_id: str,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    tx = db.execute(select(Transaction).where(Transaction.id == transaction_id)).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")
    db.delete(tx)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/finance/summary", tags=["Finance"])
def api_get_finance_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("read:finance")),
    db: Session = Depends(get_db),
):
    process_recurring_rules(db)
    return get_finance_summary(db, start_date=start_date, end_date=end_date, currency=currency)


@api_router.get("/budgets", response_model=List[BudgetResponse], tags=["Finance"])
def api_list_budgets(
    month: Optional[str] = None,
    currency: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("read:finance")),
    db: Session = Depends(get_db),
):
    stmt = select(Budget).order_by(Budget.month.desc(), Budget.category.asc())
    if month:
        stmt = stmt.where(Budget.month == month)
    if currency:
        stmt = stmt.where(Budget.currency == currency.upper())
    budgets = db.execute(stmt).scalars().all()
    return [evaluate_budget(db, b) for b in budgets]


@api_router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED, tags=["Finance"])
def api_create_budget(
    payload: BudgetCreate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(Budget).where(
            Budget.month == payload.month,
            Budget.category == payload.category.strip(),
            Budget.currency == payload.currency.upper(),
        )
    ).scalar_one_or_none()
    if existing:
        existing.name = payload.name.strip()
        existing.amount_limit = to_decimal(payload.amount_limit)
        existing.alert_threshold_percent = payload.alert_threshold_percent
        existing.notes = payload.notes
        db.commit()
        db.refresh(existing)
        return evaluate_budget(db, existing)

    b = Budget(
        name=payload.name.strip(),
        month=payload.month,
        category=payload.category.strip(),
        currency=payload.currency.upper(),
        amount_limit=to_decimal(payload.amount_limit),
        alert_threshold_percent=payload.alert_threshold_percent,
        notes=payload.notes,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return evaluate_budget(db, b)


@api_router.patch("/budgets/{budget_id}", response_model=BudgetResponse, tags=["Finance"])
def api_update_budget(
    budget_id: str,
    payload: BudgetUpdate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    b = db.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found.")
    data = payload.model_dump(exclude_unset=True)
    if "amount_limit" in data and data["amount_limit"] is not None:
        data["amount_limit"] = to_decimal(data["amount_limit"])
    for k, v in data.items():
        setattr(b, k, v)
    db.commit()
    db.refresh(b)
    return evaluate_budget(db, b)


@api_router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Finance"])
def api_delete_budget(
    budget_id: str,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    b = db.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found.")
    db.delete(b)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/finance/recurring", response_model=List[RecurringRuleResponse], tags=["Finance"])
def api_list_recurring_rules(
    auth: AuthContext = Depends(require_scopes("read:finance")),
    db: Session = Depends(get_db),
):
    rules = db.execute(select(RecurringTransactionRule).order_by(RecurringTransactionRule.next_due_date.asc())).scalars().all()
    return [RecurringRuleResponse.model_validate(r) for r in rules]


@api_router.post(
    "/finance/recurring",
    response_model=RecurringRuleResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Finance"],
)
def api_create_recurring_rule(
    payload: RecurringRuleCreate,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    rule = RecurringTransactionRule(
        title=payload.title.strip(),
        amount=to_decimal(payload.amount),
        currency=payload.currency.upper(),
        transaction_type=payload.transaction_type,
        category=payload.category.strip(),
        subcategory=payload.subcategory,
        merchant=payload.merchant,
        account_id=payload.account_id,
        to_account_id=payload.to_account_id,
        payment_method=payload.payment_method,
        frequency=payload.frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        next_due_date=payload.start_date,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    process_recurring_rules(db)
    db.refresh(rule)
    return RecurringRuleResponse.model_validate(rule)


@api_router.post("/finance/recurring/process", response_model=List[TransactionResponse], tags=["Finance"])
def api_process_recurring_rules(
    up_to_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    return process_recurring_rules(db, up_to_date=up_to_date)


@api_router.delete("/finance/recurring/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Finance"])
def api_delete_recurring_rule(
    rule_id: str,
    auth: AuthContext = Depends(require_scopes("write:finance")),
    db: Session = Depends(get_db),
):
    rule = db.execute(select(RecurringTransactionRule).where(RecurringTransactionRule.id == rule_id)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring rule not found.")
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# SCREEN-TIME ENDPOINTS
# ============================================================================
@api_router.get("/screen-time", response_model=List[ScreenTimeResponse], tags=["Screen Time"])
def api_list_screen_time(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    device: Optional[str] = None,
    category: Optional[str] = None,
    app_name: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("read:screen_time")),
    db: Session = Depends(get_db),
):
    stmt = select(ScreenTimeSession).order_by(ScreenTimeSession.session_date.desc(), ScreenTimeSession.created_at.desc())
    if start_date:
        stmt = stmt.where(ScreenTimeSession.session_date >= start_date)
    if end_date:
        stmt = stmt.where(ScreenTimeSession.session_date <= end_date)
    if device:
        stmt = stmt.where(ScreenTimeSession.device == device)
    if category:
        stmt = stmt.where(ScreenTimeSession.category == category)
    if app_name:
        stmt = stmt.where(ScreenTimeSession.app_name.ilike(f"%{app_name}%"))
    rows = db.execute(stmt).scalars().all()
    return [ScreenTimeResponse.model_validate(r) for r in rows]


@api_router.post(
    "/screen-time",
    response_model=ScreenTimeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Screen Time"],
)
def api_create_screen_time(
    payload: ScreenTimeCreate,
    auth: AuthContext = Depends(require_scopes("write:screen_time")),
    db: Session = Depends(get_db),
):
    return create_screen_time_session(db, payload)


@api_router.get("/screen-time/summary", tags=["Screen Time"])
def api_get_screen_time_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:screen_time")),
    db: Session = Depends(get_db),
):
    return get_screen_time_summary(db, start_date=start_date, end_date=end_date)


@api_router.get("/screen-time/mappings", response_model=List[AppCategoryMappingResponse], tags=["Screen Time"])
def api_list_app_mappings(
    auth: AuthContext = Depends(require_scopes("read:screen_time")),
    db: Session = Depends(get_db),
):
    mappings = db.execute(select(AppCategoryMapping).order_by(AppCategoryMapping.app_name.asc())).scalars().all()
    return [AppCategoryMappingResponse.model_validate(m) for m in mappings]


@api_router.post(
    "/screen-time/mappings",
    response_model=AppCategoryMappingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Screen Time"],
)
def api_upsert_app_mapping(
    payload: AppCategoryMappingCreate,
    auth: AuthContext = Depends(require_scopes("write:screen_time")),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(AppCategoryMapping).where(AppCategoryMapping.app_name.ilike(payload.app_name.strip()))
    ).scalar_one_or_none()
    if existing:
        existing.category = payload.category
        existing.productivity_type = payload.productivity_type
        db.commit()
        db.refresh(existing)
        return AppCategoryMappingResponse.model_validate(existing)
    m = AppCategoryMapping(
        app_name=payload.app_name.strip(),
        category=payload.category,
        productivity_type=payload.productivity_type,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return AppCategoryMappingResponse.model_validate(m)


@api_router.delete("/screen-time/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Screen Time"])
def api_delete_app_mapping(
    mapping_id: str,
    auth: AuthContext = Depends(require_scopes("write:screen_time")),
    db: Session = Depends(get_db),
):
    m = db.execute(select(AppCategoryMapping).where(AppCategoryMapping.id == mapping_id)).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found.")
    db.delete(m)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/screen-time/{session_id}", response_model=ScreenTimeResponse, tags=["Screen Time"])
def api_get_screen_time_session(
    session_id: str,
    auth: AuthContext = Depends(require_scopes("read:screen_time")),
    db: Session = Depends(get_db),
):
    s = db.execute(select(ScreenTimeSession).where(ScreenTimeSession.id == session_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screen-time session not found.")
    return ScreenTimeResponse.model_validate(s)


@api_router.patch("/screen-time/{session_id}", response_model=ScreenTimeResponse, tags=["Screen Time"])
def api_update_screen_time_session(
    session_id: str,
    payload: ScreenTimeUpdate,
    auth: AuthContext = Depends(require_scopes("write:screen_time")),
    db: Session = Depends(get_db),
):
    s = db.execute(select(ScreenTimeSession).where(ScreenTimeSession.id == session_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screen-time session not found.")
    return update_screen_time_session(db, s, payload)


@api_router.delete("/screen-time/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Screen Time"])
def api_delete_screen_time_session(
    session_id: str,
    auth: AuthContext = Depends(require_scopes("write:screen_time")),
    db: Session = Depends(get_db),
):
    s = db.execute(select(ScreenTimeSession).where(ScreenTimeSession.id == session_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screen-time session not found.")
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# ACTIVITIES & PERSISTENT FOCUS TIMER ENDPOINTS
# ============================================================================
@api_router.get("/activities", response_model=List[ActivityResponse], tags=["Activities & Focus"])
def api_list_activities(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
    is_focus_session: Optional[bool] = None,
    auth: AuthContext = Depends(require_scopes("read:activities")),
    db: Session = Depends(get_db),
):
    stmt = select(ActivitySession).order_by(ActivitySession.start_time.desc())
    if start_date:
        stmt = stmt.where(ActivitySession.session_date >= start_date)
    if end_date:
        stmt = stmt.where(ActivitySession.session_date <= end_date)
    if category:
        stmt = stmt.where(ActivitySession.category.ilike(f"%{category}%"))
    if project:
        stmt = stmt.where(ActivitySession.project.ilike(f"%{project}%"))
    if is_focus_session is not None:
        stmt = stmt.where(ActivitySession.is_focus_session == is_focus_session)

    sessions = db.execute(stmt).scalars().all()
    overlaps = detect_overlapping_session_ids(list(sessions))
    return [serialize_activity(s, overlapping_ids=overlaps) for s in sessions]


@api_router.post(
    "/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Activities & Focus"],
)
def api_create_activity(
    payload: ActivityCreate,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    return create_manual_activity(db, payload)


@api_router.get("/activities/summary", tags=["Activities & Focus"])
def api_get_activities_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:activities")),
    db: Session = Depends(get_db),
):
    return get_activities_summary(db, start_date=start_date, end_date=end_date)


@api_router.get("/activities/timer/active", tags=["Activities & Focus"])
def api_get_active_timer(
    auth: AuthContext = Depends(require_scopes("read:activities")),
    db: Session = Depends(get_db),
):
    active = get_active_timer(db)
    return {"active_timer": serialize_activity(active).model_dump(mode="json") if active else None}


@api_router.post(
    "/activities/timer/start",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Activities & Focus"],
)
def api_start_timer(
    payload: TimerStartRequest,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    return start_focus_timer(db, payload)


@api_router.post("/activities/timer/pause", response_model=ActivityResponse, tags=["Activities & Focus"])
def api_pause_timer(
    session_id: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    return pause_focus_timer(db, session_id=session_id)


@api_router.post("/activities/timer/resume", response_model=ActivityResponse, tags=["Activities & Focus"])
def api_resume_timer(
    session_id: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    return resume_focus_timer(db, session_id=session_id)


@api_router.post("/activities/timer/stop", response_model=ActivityResponse, tags=["Activities & Focus"])
def api_stop_timer(
    session_id: Optional[str] = None,
    notes: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    return stop_focus_timer(db, session_id=session_id, notes=notes)


@api_router.get("/activities/{session_id}", response_model=ActivityResponse, tags=["Activities & Focus"])
def api_get_activity(
    session_id: str,
    auth: AuthContext = Depends(require_scopes("read:activities")),
    db: Session = Depends(get_db),
):
    s = db.execute(select(ActivitySession).where(ActivitySession.id == session_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity session not found.")
    return serialize_activity(s)


@api_router.patch("/activities/{session_id}", response_model=ActivityResponse, tags=["Activities & Focus"])
def api_update_activity(
    session_id: str,
    payload: ActivityUpdate,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    s = db.execute(select(ActivitySession).where(ActivitySession.id == session_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity session not found.")
    return update_activity_session(db, s, payload)


@api_router.delete("/activities/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Activities & Focus"])
def api_delete_activity(
    session_id: str,
    auth: AuthContext = Depends(require_scopes("write:activities")),
    db: Session = Depends(get_db),
):
    s = db.execute(select(ActivitySession).where(ActivitySession.id == session_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity session not found.")
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# GOALS & MILESTONES ENDPOINTS
# ============================================================================
@api_router.get("/goals", response_model=List[GoalResponse], tags=["Goals & Projects"])
def api_list_goals(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("read:goals")),
    db: Session = Depends(get_db),
):
    stmt = select(Goal).order_by(Goal.created_at.desc())
    if status_filter:
        stmt = stmt.where(Goal.status == status_filter)
    if category:
        stmt = stmt.where(Goal.category.ilike(f"%{category}%"))
    goals = db.execute(stmt).scalars().all()
    return [serialize_goal(g) for g in goals]


@api_router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED, tags=["Goals & Projects"])
def api_create_goal(
    payload: GoalCreate,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    return create_goal(db, payload)


@api_router.get("/goals/{goal_id}", response_model=GoalResponse, tags=["Goals & Projects"])
def api_get_goal(
    goal_id: str,
    auth: AuthContext = Depends(require_scopes("read:goals")),
    db: Session = Depends(get_db),
):
    g = db.execute(select(Goal).where(Goal.id == goal_id)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    return serialize_goal(g)


@api_router.patch("/goals/{goal_id}", response_model=GoalResponse, tags=["Goals & Projects"])
def api_update_goal(
    goal_id: str,
    payload: GoalUpdate,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    g = db.execute(select(Goal).where(Goal.id == goal_id)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    return update_goal(db, g, payload)


@api_router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Goals & Projects"])
def api_delete_goal(
    goal_id: str,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    g = db.execute(select(Goal).where(Goal.id == goal_id)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    db.delete(g)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/goals/{goal_id}/progress", response_model=GoalResponse, status_code=status.HTTP_201_CREATED, tags=["Goals & Projects"])
def api_log_goal_progress(
    goal_id: str,
    payload: GoalProgressCreate,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    g = db.execute(select(Goal).where(Goal.id == goal_id)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    return log_goal_progress(db, g, payload)


@api_router.post(
    "/goals/{goal_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Goals & Projects"],
)
def api_add_milestone(
    goal_id: str,
    payload: MilestoneCreate,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    g = db.execute(select(Goal).where(Goal.id == goal_id)).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    return add_goal_milestone(db, g, payload)


@api_router.patch(
    "/goals/{goal_id}/milestones/{milestone_id}",
    response_model=MilestoneResponse,
    tags=["Goals & Projects"],
)
def api_update_milestone(
    goal_id: str,
    milestone_id: str,
    payload: MilestoneUpdate,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    ms = db.execute(
        select(Milestone).where(Milestone.id == milestone_id, Milestone.goal_id == goal_id)
    ).scalar_one_or_none()
    if not ms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found.")
    return update_goal_milestone(db, ms, payload)


@api_router.delete(
    "/goals/{goal_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Goals & Projects"],
)
def api_delete_milestone(
    goal_id: str,
    milestone_id: str,
    auth: AuthContext = Depends(require_scopes("write:goals")),
    db: Session = Depends(get_db),
):
    ms = db.execute(
        select(Milestone).where(Milestone.id == milestone_id, Milestone.goal_id == goal_id)
    ).scalar_one_or_none()
    if not ms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found.")
    db.delete(ms)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# PRIVATE JOURNAL & DAILY REVIEW ENDPOINTS
# ============================================================================
@api_router.get("/journal", response_model=List[JournalResponse], tags=["Journal"])
def api_list_journal(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tag: Optional[str] = None,
    is_daily_review: Optional[bool] = None,
    search: Optional[str] = None,
    auth: AuthContext = Depends(require_scopes("read:journal")),
    db: Session = Depends(get_db),
):
    stmt = select(JournalEntry).order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    if start_date:
        stmt = stmt.where(JournalEntry.entry_date >= start_date)
    if end_date:
        stmt = stmt.where(JournalEntry.entry_date <= end_date)
    if is_daily_review is not None:
        stmt = stmt.where(JournalEntry.is_daily_review == is_daily_review)
    if tag:
        stmt = stmt.where(JournalEntry.tags_csv.ilike(f"%{tag}%"))
    entries = db.execute(stmt).scalars().all()
    if search:
        q = search.strip().lower()
        entries = [
            e
            for e in entries
            if q in (e.title or "").lower()
            or q in (e.content or "").lower()
            or q in (e.daily_intention or "").lower()
            or q in (e.highlights or "").lower()
            or q in (e.lessons_learned or "").lower()
            or q in (e.review_accomplishments or "").lower()
        ]
    return [serialize_journal(e) for e in entries]


@api_router.post(
    "/journal",
    response_model=JournalResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Journal"],
)
def api_create_journal(
    payload: JournalCreate,
    auth: AuthContext = Depends(require_scopes("write:journal")),
    db: Session = Depends(get_db),
):
    return create_journal_entry(db, payload)


@api_router.get("/journal/{entry_id}", response_model=JournalResponse, tags=["Journal"])
def api_get_journal_entry(
    entry_id: str,
    auth: AuthContext = Depends(require_scopes("read:journal")),
    db: Session = Depends(get_db),
):
    e = db.execute(select(JournalEntry).where(JournalEntry.id == entry_id)).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    return serialize_journal(e)


@api_router.patch("/journal/{entry_id}", response_model=JournalResponse, tags=["Journal"])
def api_update_journal(
    entry_id: str,
    payload: JournalUpdate,
    auth: AuthContext = Depends(require_scopes("write:journal")),
    db: Session = Depends(get_db),
):
    e = db.execute(select(JournalEntry).where(JournalEntry.id == entry_id)).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    return update_journal_entry(db, e, payload)


@api_router.delete("/journal/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Journal"])
def api_delete_journal(
    entry_id: str,
    auth: AuthContext = Depends(require_scopes("write:journal")),
    db: Session = Depends(get_db),
):
    e = db.execute(select(JournalEntry).where(JournalEntry.id == entry_id)).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    db.delete(e)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# WELLBEING ENDPOINTS
# ============================================================================
@api_router.get("/wellbeing", response_model=List[WellbeingResponse], tags=["Wellbeing"])
def api_list_wellbeing(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:wellbeing")),
    db: Session = Depends(get_db),
):
    stmt = select(WellbeingRecord).order_by(WellbeingRecord.record_date.desc())
    if start_date:
        stmt = stmt.where(WellbeingRecord.record_date >= start_date)
    if end_date:
        stmt = stmt.where(WellbeingRecord.record_date <= end_date)
    records = db.execute(stmt).scalars().all()
    return [serialize_wellbeing(r) for r in records]


@api_router.post(
    "/wellbeing",
    response_model=WellbeingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Wellbeing"],
)
def api_upsert_wellbeing(
    payload: WellbeingCreate,
    auth: AuthContext = Depends(require_scopes("write:wellbeing")),
    db: Session = Depends(get_db),
):
    return upsert_wellbeing_record(db, payload)


@api_router.get("/wellbeing/summary", tags=["Wellbeing"])
def api_get_wellbeing_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    auth: AuthContext = Depends(require_scopes("read:wellbeing")),
    db: Session = Depends(get_db),
):
    return get_wellbeing_summary(db, start_date=start_date, end_date=end_date)


@api_router.get("/wellbeing/{record_id}", response_model=WellbeingResponse, tags=["Wellbeing"])
def api_get_wellbeing_record(
    record_id: str,
    auth: AuthContext = Depends(require_scopes("read:wellbeing")),
    db: Session = Depends(get_db),
):
    r = db.execute(select(WellbeingRecord).where(WellbeingRecord.id == record_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellbeing record not found.")
    return serialize_wellbeing(r)


@api_router.patch("/wellbeing/{record_id}", response_model=WellbeingResponse, tags=["Wellbeing"])
def api_update_wellbeing_record(
    record_id: str,
    payload: WellbeingUpdate,
    auth: AuthContext = Depends(require_scopes("write:wellbeing")),
    db: Session = Depends(get_db),
):
    r = db.execute(select(WellbeingRecord).where(WellbeingRecord.id == record_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellbeing record not found.")
    data = payload.model_dump(exclude_unset=True, exclude={"custom_measurements"})
    for k, v in data.items():
        setattr(r, k, v)
    if payload.custom_measurements is not None:
        r.custom_measurements_json = json.dumps(payload.custom_measurements)
    db.commit()
    db.refresh(r)
    return serialize_wellbeing(r)


@api_router.delete("/wellbeing/{record_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Wellbeing"])
def api_delete_wellbeing_record(
    record_id: str,
    auth: AuthContext = Depends(require_scopes("write:wellbeing")),
    db: Session = Depends(get_db),
):
    r = db.execute(select(WellbeingRecord).where(WellbeingRecord.id == record_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellbeing record not found.")
    db.delete(r)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# IMPORTS, EXPORTS, BACKUPS & DATA DELETION
# ============================================================================
@api_router.get("/export", tags=["Imports, Exports & Backups"])
def api_export_data(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    domain: str = Query(default="all"),
    auth: AuthContext = Depends(require_scopes("read:exports")),
    db: Session = Depends(get_db),
):
    full_data = export_all_personal_data(db)
    if format == "json":
        return full_data

    # CSV Export for requested domain
    domain_map = {
        "transactions": full_data["transactions"],
        "habits": full_data["habits"],
        "habit_entries": full_data["habit_entries"],
        "screen_time": full_data["screen_time_sessions"],
        "activities": full_data["activity_sessions"],
        "goals": full_data["goals"],
        "journal": full_data["journal_entries"],
        "wellbeing": full_data["wellbeing_records"],
    }
    rows = domain_map.get(domain, full_data["transactions"])
    output = io.StringIO()
    if rows:
        fieldnames = [k for k in rows[0].keys() if not isinstance(rows[0][k], (list, dict))]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    else:
        output.write("id,notes\n")

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="personal_life_os_{domain}.csv"'},
    )


@api_router.post("/import/preview", tags=["Imports, Exports & Backups"])
def api_import_preview(
    payload: ImportPreviewRequest,
    auth: AuthContext = Depends(require_scopes("write:imports")),
    db: Session = Depends(get_db),
):
    return preview_csv_import(
        db,
        domain=payload.domain,
        filename=payload.filename,
        csv_content=payload.csv_content,
        field_mapping=payload.field_mapping,
        default_currency=payload.default_currency,
    )


@api_router.post("/import/commit", tags=["Imports, Exports & Backups"])
def api_import_commit(
    payload: ImportCommitRequest,
    auth: AuthContext = Depends(require_scopes("write:imports")),
    db: Session = Depends(get_db),
):
    return commit_csv_import(
        db,
        import_job_id=payload.import_job_id,
        skip_duplicates=payload.skip_duplicates,
        row_overrides=payload.row_overrides,
    )


@api_router.get("/backups", tags=["Imports, Exports & Backups"])
def api_list_backups(auth: AuthContext = Depends(require_scopes("read:all"))):
    return {"backups": list_database_backups()}


@api_router.post("/backups", status_code=status.HTTP_201_CREATED, tags=["Imports, Exports & Backups"])
def api_create_backup(
    label: Optional[str] = "manual",
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    return create_database_backup(db, label=label)


@api_router.post("/backups/restore", tags=["Imports, Exports & Backups"])
def api_restore_backup(
    payload: BackupRestoreRequest,
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    return validate_and_restore_backup(
        db,
        backup_filename=payload.backup_filename,
        confirm_overwrite=payload.confirm_overwrite,
    )


@api_router.delete("/data/records", tags=["Imports, Exports & Backups"])
def api_delete_all_personal_records(
    confirm: bool = Query(default=False),
    auth: AuthContext = Depends(require_scopes("write:all")),
    db: Session = Depends(get_db),
):
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation (confirm=true) is required to delete all personal records.",
        )

    for model in (
        HabitEntry,
        HabitSchedule,
        GoalHabitLink,
        GoalProgressEntry,
        Milestone,
        Goal,
        Habit,
        Transaction,
        Budget,
        RecurringTransactionRule,
        ScreenTimeSession,
        ActivitySession,
        JournalEntry,
        WellbeingRecord,
        InsightDismissal,
        ImportResult,
        ImportJob,
    ):
        db.query(model).delete()
    db.commit()
    return {"status": "deleted", "message": "All personal activity, habit, finance, journal, and wellbeing records have been deleted."}

