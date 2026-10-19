from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Common & Pagination ---
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class PeriodComparisonMetric(BaseModel):
    current_value: float | Decimal
    previous_value: Optional[float | Decimal] = None
    absolute_change: Optional[float | Decimal] = None
    percentage_change: Optional[float] = None
    comparison_label: str
    has_sufficient_previous_data: bool = False
    explanation: str


# --- Auth & Profile ---
class SetupStatusResponse(BaseModel):
    is_initialized: bool
    has_user: bool
    app_name: str
    version: str


class SetupRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=80)
    display_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = None
    preferred_name: Optional[str] = None
    base_currency: str = Field(default="INR", min_length=3, max_length=8)
    timezone: str = Field(default="Asia/Kolkata")
    theme: Literal["dark", "light"] = "dark"


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserPreferenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preferred_name: str = "Builder"
    timezone: str = "Asia/Kolkata"
    base_currency: str = "INR"
    date_format: str = "YYYY-MM-DD"
    number_format: str = "en-IN"
    week_start_day: str = "monday"
    theme: str = "dark"
    daily_screen_time_target_minutes: int = 240
    focus_session_duration_minutes: int = 50
    break_duration_minutes: int = 10
    break_reminders_enabled: bool = True
    habit_reminders_enabled: bool = True
    budget_alert_threshold_percent: int = 85
    dashboard_widgets: List[str] = Field(
        default_factory=lambda: [
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
    )
    external_integrations_enabled: bool = False
    today_intention: Optional[str] = None
    today_intention_date: Optional[date] = None


class UserPreferenceUpdate(BaseModel):
    preferred_name: Optional[str] = None
    timezone: Optional[str] = None
    base_currency: Optional[str] = None
    date_format: Optional[str] = None
    number_format: Optional[str] = None
    week_start_day: Optional[str] = None
    theme: Optional[Literal["dark", "light"]] = None
    daily_screen_time_target_minutes: Optional[int] = Field(default=None, ge=15, le=1440)
    focus_session_duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    break_duration_minutes: Optional[int] = Field(default=None, ge=1, le=120)
    break_reminders_enabled: Optional[bool] = None
    habit_reminders_enabled: Optional[bool] = None
    budget_alert_threshold_percent: Optional[int] = Field(default=None, ge=10, le=100)
    dashboard_widgets: Optional[List[str]] = None
    external_integrations_enabled: Optional[bool] = None
    today_intention: Optional[str] = None
    today_intention_date: Optional[date] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    email: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    preferences: UserPreferenceSchema


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


# --- API Tokens ---
class ApiTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scopes: List[str] = Field(default_factory=lambda: ["read:all"])
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ApiTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    token_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_revoked: bool
    revoked_at: Optional[datetime] = None
    created_at: datetime


class ApiTokenCreatedResponse(ApiTokenResponse):
    raw_token: str


# --- Habits ---
class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    description: Optional[str] = None
    category: str = Field(default="Health", max_length=64)
    icon: str = Field(default="check-circle", max_length=48)
    accent_color: str = Field(default="#8b5cf6", max_length=24)
    frequency_type: Literal["daily", "selected_weekdays", "weekly_target"] = "daily"
    selected_weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    weekly_target: Optional[int] = Field(default=None, ge=1, le=7)
    target_value: Decimal = Field(default=Decimal("1.00"), gt=Decimal("0"))
    unit: str = Field(default="completion", max_length=32)
    is_quantitative: bool = False
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    reminder_preference: Optional[str] = None
    status: Literal["active", "archived"] = "active"

    @field_validator("selected_weekdays")
    @classmethod
    def validate_weekdays(cls, v: List[int]) -> List[int]:
        cleaned = sorted(set(d for d in v if 0 <= d <= 6))
        if not cleaned:
            return [0, 1, 2, 3, 4, 5, 6]
        return cleaned


class HabitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=140)
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    accent_color: Optional[str] = None
    frequency_type: Optional[Literal["daily", "selected_weekdays", "weekly_target"]] = None
    selected_weekdays: Optional[List[int]] = None
    weekly_target: Optional[int] = Field(default=None, ge=1, le=7)
    target_value: Optional[Decimal] = Field(default=None, gt=Decimal("0"))
    unit: Optional[str] = None
    is_quantitative: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reminder_preference: Optional[str] = None
    status: Optional[Literal["active", "archived"]] = None


class HabitEntryCreate(BaseModel):
    entry_date: date = Field(default_factory=date.today)
    completed: bool = True
    value: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"))
    notes: Optional[str] = None
    is_historical_correction: bool = False
    completed_at: Optional[datetime] = None


class HabitEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    habit_id: str
    entry_date: date
    completed: bool
    value: Decimal
    completed_at: datetime
    notes: Optional[str] = None
    is_historical_correction: bool = False
    created_at: datetime
    updated_at: datetime


class HabitResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: str
    icon: str
    accent_color: str
    frequency_type: str
    selected_weekdays: List[int]
    weekly_target: Optional[int] = None
    target_value: Decimal
    unit: str
    is_quantitative: bool
    start_date: date
    end_date: Optional[date] = None
    reminder_preference: Optional[str] = None
    status: str
    current_streak: int = 0
    best_streak: int = 0
    completion_rate_30d: float = 0.0
    completed_today: bool = False
    today_value: Decimal = Decimal("0.00")
    missed_scheduled_days_30d: int = 0
    recent_entries: List[HabitEntryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Personal Finance ---
class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    account_type: Literal["checking", "savings", "credit_card", "wallet", "cash", "investment"] = "checking"
    currency: str = Field(default="INR", min_length=3, max_length=8)
    initial_balance: Decimal = Field(default=Decimal("0.00"))
    color: str = Field(default="#3b82f6")
    icon: str = Field(default="wallet")
    is_active: bool = True
    notes: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    account_type: Optional[Literal["checking", "savings", "credit_card", "wallet", "cash", "investment"]] = None
    currency: Optional[str] = None
    initial_balance: Optional[Decimal] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class AccountResponse(BaseModel):
    id: str
    name: str
    account_type: str
    currency: str
    initial_balance: Decimal
    current_balance: Decimal
    color: str
    icon: str
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    currency: str = Field(default="INR", min_length=3, max_length=8)
    transaction_type: Literal["expense", "income", "transfer"] = "expense"
    category: str = Field(..., min_length=1, max_length=80)
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    transaction_date: date = Field(default_factory=date.today)
    account_id: Optional[str] = None
    to_account_id: Optional[str] = None
    payment_method: Optional[str] = "UPI"
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    receipt_reference: Optional[str] = None
    recurring_rule_id: Optional[str] = None


class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=Decimal("0.00"))
    currency: Optional[str] = None
    transaction_type: Optional[Literal["expense", "income", "transfer"]] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    transaction_date: Optional[date] = None
    account_id: Optional[str] = None
    to_account_id: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    receipt_reference: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    amount: Decimal
    currency: str
    transaction_type: str
    category: str
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    transaction_date: date
    recorded_at: datetime
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    to_account_id: Optional[str] = None
    to_account_name: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    receipt_reference: Optional[str] = None
    recurring_rule_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BudgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    category: str = Field(default="ALL", max_length=80)
    currency: str = Field(default="INR", min_length=3, max_length=8)
    amount_limit: Decimal = Field(..., gt=Decimal("0.00"))
    alert_threshold_percent: int = Field(default=85, ge=10, le=100)
    notes: Optional[str] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    amount_limit: Optional[Decimal] = Field(default=None, gt=Decimal("0.00"))
    alert_threshold_percent: Optional[int] = Field(default=None, ge=10, le=100)
    notes: Optional[str] = None


class BudgetResponse(BaseModel):
    id: str
    name: str
    month: str
    category: str
    currency: str
    amount_limit: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    utilization_percent: float
    alert_threshold_percent: int
    is_threshold_crossed: bool
    is_over_budget: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RecurringRuleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=140)
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    currency: str = Field(default="INR")
    transaction_type: Literal["expense", "income", "transfer"] = "expense"
    category: str = Field(..., min_length=1, max_length=80)
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    account_id: Optional[str] = None
    to_account_id: Optional[str] = None
    payment_method: Optional[str] = "Auto-Debit"
    frequency: Literal["daily", "weekly", "monthly", "yearly"] = "monthly"
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None


class RecurringRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    amount: Decimal
    currency: str
    transaction_type: str
    category: str
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    account_id: Optional[str] = None
    to_account_id: Optional[str] = None
    payment_method: Optional[str] = None
    frequency: str
    start_date: date
    end_date: Optional[date] = None
    next_due_date: date
    last_generated_date: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime


# --- Screen Time ---
class AppCategoryMappingCreate(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=140)
    category: Literal[
        "work", "learning", "communication", "entertainment", "social_media", "gaming", "utilities", "other"
    ] = "work"
    productivity_type: Literal["productive", "neutral", "non_productive"] = "productive"


class AppCategoryMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    app_name: str
    category: str
    productivity_type: str
    created_at: datetime
    updated_at: datetime


class ScreenTimeCreate(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=140)
    device: Literal["desktop", "phone", "tablet", "web", "other"] = "desktop"
    session_date: date = Field(default_factory=date.today)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    category: Optional[str] = None
    productivity_type: Optional[Literal["productive", "neutral", "non_productive"]] = None
    data_source: Literal["manual", "csv_import", "local_collector", "api"] = "manual"
    notes: Optional[str] = None
    is_historical_correction: bool = False


class ScreenTimeUpdate(BaseModel):
    app_name: Optional[str] = None
    device: Optional[Literal["desktop", "phone", "tablet", "web", "other"]] = None
    session_date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    category: Optional[str] = None
    productivity_type: Optional[Literal["productive", "neutral", "non_productive"]] = None
    notes: Optional[str] = None
    is_historical_correction: Optional[bool] = None


class ScreenTimeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    app_name: str
    device: str
    session_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: int
    category: str
    productivity_type: str
    data_source: str
    notes: Optional[str] = None
    is_historical_correction: bool
    created_at: datetime
    updated_at: datetime


# --- Activities & Focus Timer ---
class TimerStartRequest(BaseModel):
    activity_name: str = Field(..., min_length=1, max_length=160)
    category: str = Field(default="Deep Work", max_length=80)
    project: Optional[str] = None
    planned_duration_minutes: Optional[int] = Field(default=50, ge=1, le=720)
    is_focus_session: bool = True
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ActivityCreate(BaseModel):
    activity_name: str = Field(..., min_length=1, max_length=160)
    category: str = Field(default="Deep Work", max_length=80)
    project: Optional[str] = None
    session_date: date = Field(default_factory=date.today)
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    planned_duration_minutes: Optional[int] = None
    is_focus_session: bool = False
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source: Literal["manual", "focus_timer", "csv_import", "api"] = "manual"


class ActivityUpdate(BaseModel):
    activity_name: Optional[str] = None
    category: Optional[str] = None
    project: Optional[str] = None
    session_date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    is_focus_session: Optional[bool] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ActivityResponse(BaseModel):
    id: str
    activity_name: str
    category: str
    project: Optional[str] = None
    session_date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: int
    elapsed_seconds: int
    timer_status: str
    last_resumed_at: Optional[datetime] = None
    planned_duration_minutes: Optional[int] = None
    is_focus_session: bool
    has_overlap: bool = False
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source: str
    created_at: datetime
    updated_at: datetime


# --- Wellbeing ---
class WellbeingCreate(BaseModel):
    record_date: date = Field(default_factory=date.today)
    sleep_duration_hours: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("24"))
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10)
    mood_score: Optional[int] = Field(default=None, ge=1, le=10)
    energy_score: Optional[int] = Field(default=None, ge=1, le=10)
    exercise_duration_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    exercise_type: Optional[str] = None
    water_intake_ml: Optional[int] = Field(default=None, ge=0, le=20000)
    weight_kg: Optional[Decimal] = Field(default=None, gt=Decimal("0"), le=Decimal("500"))
    custom_measurements: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class WellbeingUpdate(WellbeingCreate):
    pass


class WellbeingResponse(BaseModel):
    id: str
    record_date: date
    sleep_duration_hours: Optional[Decimal] = None
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None
    sleep_quality: Optional[int] = None
    mood_score: Optional[int] = None
    energy_score: Optional[int] = None
    exercise_duration_minutes: Optional[int] = None
    exercise_type: Optional[str] = None
    water_intake_ml: Optional[int] = None
    weight_kg: Optional[Decimal] = None
    custom_measurements: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime


# --- Goals & Milestones ---
class MilestoneCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    target_value: Optional[Decimal] = None
    target_date: Optional[date] = None
    is_completed: bool = False
    sort_order: int = 0


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    target_value: Optional[Decimal] = None
    target_date: Optional[date] = None
    is_completed: Optional[bool] = None
    sort_order: Optional[int] = None


class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    title: str
    target_value: Optional[Decimal] = None
    target_date: Optional[date] = None
    is_completed: bool
    completed_at: Optional[datetime] = None
    sort_order: int
    created_at: datetime


class GoalProgressCreate(BaseModel):
    entry_date: date = Field(default_factory=date.today)
    value_delta: Optional[Decimal] = None
    new_total: Optional[Decimal] = None
    notes: Optional[str] = None
    source: str = "manual"


class GoalProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    entry_date: date
    value_delta: Decimal
    new_total: Decimal
    notes: Optional[str] = None
    source: str
    created_at: datetime


class GoalCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = None
    category: str = Field(default="Personal", max_length=80)
    project: Optional[str] = None
    target_value: Decimal = Field(..., gt=Decimal("0"))
    current_value: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    unit: str = Field(default="units", max_length=32)
    start_date: date = Field(default_factory=date.today)
    target_date: Optional[date] = None
    status: Literal["active", "completed", "paused", "archived"] = "active"
    notes: Optional[str] = None
    related_habit_ids: List[str] = Field(default_factory=list)
    milestones: List[MilestoneCreate] = Field(default_factory=list)


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    project: Optional[str] = None
    target_value: Optional[Decimal] = Field(default=None, gt=Decimal("0"))
    current_value: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    unit: Optional[str] = None
    start_date: Optional[date] = None
    target_date: Optional[date] = None
    status: Optional[Literal["active", "completed", "paused", "archived"]] = None
    notes: Optional[str] = None
    related_habit_ids: Optional[List[str]] = None


class GoalResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: str
    project: Optional[str] = None
    target_value: Decimal
    current_value: Decimal
    progress_percent: float
    unit: str
    start_date: date
    target_date: Optional[date] = None
    days_remaining: Optional[int] = None
    expected_pace_percent: Optional[float] = None
    pace_status: str  # ahead | on_track | behind | completed | no_deadline
    status: str
    notes: Optional[str] = None
    related_habit_ids: List[str] = Field(default_factory=list)
    milestones: List[MilestoneResponse] = Field(default_factory=list)
    progress_entries: List[GoalProgressResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Journal & Daily Review ---
class JournalCreate(BaseModel):
    entry_date: date = Field(default_factory=date.today)
    title: Optional[str] = None
    content: str = ""
    daily_intention: Optional[str] = None
    highlights: Optional[str] = None
    lessons_learned: Optional[str] = None
    areas_to_improve: Optional[str] = None
    tomorrow_focus: Optional[str] = None
    review_accomplishments: Optional[str] = None
    review_time_spent: Optional[str] = None
    review_money_spent: Optional[str] = None
    review_energy_notes: Optional[str] = None
    review_went_well: Optional[str] = None
    review_could_improve: Optional[str] = None
    mood_reference: Optional[int] = Field(default=None, ge=1, le=10)
    energy_reference: Optional[int] = Field(default=None, ge=1, le=10)
    tags: List[str] = Field(default_factory=list)
    is_daily_review: bool = False


class JournalUpdate(BaseModel):
    entry_date: Optional[date] = None
    title: Optional[str] = None
    content: Optional[str] = None
    daily_intention: Optional[str] = None
    highlights: Optional[str] = None
    lessons_learned: Optional[str] = None
    areas_to_improve: Optional[str] = None
    tomorrow_focus: Optional[str] = None
    review_accomplishments: Optional[str] = None
    review_time_spent: Optional[str] = None
    review_money_spent: Optional[str] = None
    review_energy_notes: Optional[str] = None
    review_went_well: Optional[str] = None
    review_could_improve: Optional[str] = None
    mood_reference: Optional[int] = Field(default=None, ge=1, le=10)
    energy_reference: Optional[int] = Field(default=None, ge=1, le=10)
    tags: Optional[List[str]] = None
    is_daily_review: Optional[bool] = None


class JournalResponse(BaseModel):
    id: str
    entry_date: date
    title: Optional[str] = None
    content: str
    daily_intention: Optional[str] = None
    highlights: Optional[str] = None
    lessons_learned: Optional[str] = None
    areas_to_improve: Optional[str] = None
    tomorrow_focus: Optional[str] = None
    review_accomplishments: Optional[str] = None
    review_time_spent: Optional[str] = None
    review_money_spent: Optional[str] = None
    review_energy_notes: Optional[str] = None
    review_went_well: Optional[str] = None
    review_could_improve: Optional[str] = None
    mood_reference: Optional[int] = None
    energy_reference: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    is_daily_review: bool
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime


# --- Insights ---
class InsightStatusUpdate(BaseModel):
    insight_key: str
    status: Literal["dismissed", "reviewed", "active"]


# --- Natural Language Query ---
class NLQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)


# --- Imports & Backups ---
class ImportPreviewRequest(BaseModel):
    domain: Literal["transactions", "screen_time", "activities", "habits"]
    filename: str = "import.csv"
    csv_content: str
    field_mapping: Optional[Dict[str, str]] = None
    default_currency: str = "INR"


class ImportCommitRequest(BaseModel):
    import_job_id: str
    skip_duplicates: bool = True
    row_overrides: Optional[Dict[int, Dict[str, Any]]] = None


class BackupRestoreRequest(BaseModel):
    backup_filename: str
    confirm_overwrite: bool = False


class FilterPresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    entity_type: str
    filters: Dict[str, Any]

