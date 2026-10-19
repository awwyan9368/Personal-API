import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    preferences: Mapped[Optional["UserPreference"]] = relationship(
        "UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    api_tokens: Mapped[List["ApiToken"]] = relationship(
        "ApiToken", back_populates="user", cascade="all, delete-orphan"
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    preferred_name: Mapped[str] = mapped_column(String(120), default="Builder", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    date_format: Mapped[str] = mapped_column(String(32), default="YYYY-MM-DD", nullable=False)
    number_format: Mapped[str] = mapped_column(String(16), default="en-IN", nullable=False)
    week_start_day: Mapped[str] = mapped_column(String(16), default="monday", nullable=False)
    theme: Mapped[str] = mapped_column(String(16), default="dark", nullable=False)
    daily_screen_time_target_minutes: Mapped[int] = mapped_column(Integer, default=240, nullable=False)
    focus_session_duration_minutes: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    break_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    habit_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    budget_alert_threshold_percent: Mapped[int] = mapped_column(Integer, default=85, nullable=False)
    dashboard_widgets_json: Mapped[str] = mapped_column(
        Text,
        default='["habits","streaks","expenses","income","budget","screen_time","focus_time","activity_time","sleep","mood_energy","goals"]',
        nullable=False,
    )
    import_preferences_json: Mapped[str] = mapped_column(
        Text,
        default='{"skip_duplicates": true, "default_currency": "INR"}',
        nullable=False,
    )
    external_integrations_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    today_intention: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    today_intention_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="preferences")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    scopes: Mapped[str] = mapped_column(Text, default="read:all", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="api_tokens")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    color: Mapped[str] = mapped_column(String(24), default="#8b5cf6", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class EntityTag(Base):
    __tablename__ = "entity_tags"
    __table_args__ = (
        UniqueConstraint("tag_id", "entity_type", "entity_id", name="uq_entity_tag_link"),
        Index("ix_entity_tags_lookup", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(140), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="Health", index=True, nullable=False)
    icon: Mapped[str] = mapped_column(String(48), default="check-circle", nullable=False)
    accent_color: Mapped[str] = mapped_column(String(24), default="#8b5cf6", nullable=False)
    frequency_type: Mapped[str] = mapped_column(
        String(32), default="daily", nullable=False
    )  # daily | selected_weekdays | weekly_target
    selected_weekdays: Mapped[str] = mapped_column(
        String(32), default="0,1,2,3,4,5,6", nullable=False
    )  # 0=Mon .. 6=Sun
    weekly_target: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1.00"), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="completion", nullable=False)
    is_quantitative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reminder_preference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True, nullable=False)  # active | archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    schedules: Mapped[List["HabitSchedule"]] = relationship(
        "HabitSchedule", back_populates="habit", cascade="all, delete-orphan"
    )
    entries: Mapped[List["HabitEntry"]] = relationship(
        "HabitEntry", back_populates="habit", cascade="all, delete-orphan"
    )


class HabitSchedule(Base):
    __tablename__ = "habit_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    habit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("habits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    frequency_type: Mapped[str] = mapped_column(String(32), default="daily", nullable=False)
    selected_weekdays: Mapped[str] = mapped_column(String(32), default="0,1,2,3,4,5,6", nullable=False)
    weekly_target: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    habit: Mapped["Habit"] = relationship("Habit", back_populates="schedules")


class HabitEntry(Base):
    __tablename__ = "habit_entries"
    __table_args__ = (
        UniqueConstraint("habit_id", "entry_date", name="uq_habit_entry_date"),
        Index("ix_habit_entries_date_completed", "entry_date", "completed"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    habit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("habits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1.00"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_historical_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    habit: Mapped["Habit"] = relationship("Habit", back_populates="entries")


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(32), default="checking", nullable=False
    )  # checking | savings | credit_card | wallet | cash | investment
    currency: Mapped[str] = mapped_column(String(8), default="INR", index=True, nullable=False)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    color: Mapped[str] = mapped_column(String(24), default="#3b82f6", nullable=False)
    icon: Mapped[str] = mapped_column(String(48), default="wallet", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "domain", name="uq_category_name_domain"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    domain: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # finance_expense | finance_income | activity | screen_time | habit | goal
    parent_category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    color: Mapped[str] = mapped_column(String(24), default="#8b5cf6", nullable=False)
    icon: Mapped[str] = mapped_column(String(48), default="tag", nullable=False)
    is_productive: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class RecurringTransactionRule(Base):
    __tablename__ = "recurring_transaction_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        String(24), default="expense", nullable=False
    )  # expense | income | transfer
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    merchant: Mapped[Optional[str]] = mapped_column(String(140), nullable=True)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )
    to_account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    frequency: Mapped[str] = mapped_column(
        String(24), default="monthly", nullable=False
    )  # daily | weekly | monthly | yearly
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    last_generated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_date_type_currency", "transaction_date", "transaction_type", "currency"),
        UniqueConstraint("recurring_rule_id", "occurrence_date", name="uq_recurring_occurrence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", index=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        String(24), default="expense", index=True, nullable=False
    )  # expense | income | transfer
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    merchant: Mapped[Optional[str]] = mapped_column(String(140), index=True, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("financial_accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    to_account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_csv: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    receipt_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recurring_rule_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("recurring_transaction_rules.id", ondelete="SET NULL"), nullable=True
    )
    occurrence_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    import_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True
    )
    external_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("month", "category", "currency", name="uq_budget_month_category_curr"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    month: Mapped[str] = mapped_column(String(7), index=True, nullable=False)  # YYYY-MM
    category: Mapped[str] = mapped_column(
        String(80), default="ALL", index=True, nullable=False
    )  # "ALL" for overall monthly budget, or specific category name
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    amount_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    alert_threshold_percent: Mapped[int] = mapped_column(Integer, default=85, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class AppCategoryMapping(Base):
    __tablename__ = "app_category_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    app_name: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), default="work", nullable=False
    )  # work | learning | communication | entertainment | social_media | gaming | utilities | other
    productivity_type: Mapped[str] = mapped_column(
        String(32), default="productive", nullable=False
    )  # productive | neutral | non_productive
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ScreenTimeSession(Base):
    __tablename__ = "screen_time_sessions"
    __table_args__ = (
        Index("ix_screen_time_date_category", "session_date", "category"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    app_name: Mapped[str] = mapped_column(String(140), index=True, nullable=False)
    device: Mapped[str] = mapped_column(
        String(48), default="desktop", index=True, nullable=False
    )  # desktop | phone | tablet | web | other
    session_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="other", index=True, nullable=False)
    productivity_type: Mapped[str] = mapped_column(
        String(32), default="neutral", index=True, nullable=False
    )  # productive | neutral | non_productive
    data_source: Mapped[str] = mapped_column(
        String(32), default="manual", nullable=False
    )  # manual | csv_import | local_collector | api
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_historical_correction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    import_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True
    )
    external_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ActivitySession(Base):
    __tablename__ = "activity_sessions"
    __table_args__ = (
        Index("ix_activities_date_status", "session_date", "timer_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    activity_name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="Deep Work", index=True, nullable=False)
    project: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    session_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accumulated_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timer_status: Mapped[str] = mapped_column(
        String(24), default="completed", index=True, nullable=False
    )  # running | paused | completed
    last_resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_focus_session: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_csv: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), default="manual", nullable=False
    )  # manual | focus_timer | csv_import | api
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class WellbeingRecord(Base):
    __tablename__ = "wellbeing_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_date: Mapped[date] = mapped_column(Date, unique=True, index=True, nullable=False)
    sleep_duration_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    bedtime: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # HH:MM
    wake_time: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # HH:MM
    sleep_quality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10
    mood_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10
    energy_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10
    exercise_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exercise_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    water_intake_ml: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    custom_measurements_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80), default="Personal", index=True, nullable=False)
    project: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    target_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="units", nullable=False)
    start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), default="active", index=True, nullable=False
    )  # active | completed | paused | archived
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_habit_ids_csv: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    milestones: Mapped[List["Milestone"]] = relationship(
        "Milestone", back_populates="goal", cascade="all, delete-orphan", order_by="Milestone.sort_order"
    )
    progress_entries: Mapped[List["GoalProgressEntry"]] = relationship(
        "GoalProgressEntry", back_populates="goal", cascade="all, delete-orphan", order_by="GoalProgressEntry.entry_date"
    )
    habit_links: Mapped[List["GoalHabitLink"]] = relationship(
        "GoalHabitLink", back_populates="goal", cascade="all, delete-orphan"
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    target_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="milestones")


class GoalProgressEntry(Base):
    __tablename__ = "goal_progress_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    value_delta: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    new_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="progress_entries")


class GoalHabitLink(Base):
    __tablename__ = "goal_habit_links"
    __table_args__ = (UniqueConstraint("goal_id", "habit_id", name="uq_goal_habit_link"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    habit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("habits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contribution_weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("1.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="habit_links")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entry_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    daily_intention: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    highlights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    areas_to_improve: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tomorrow_focus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_accomplishments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_time_spent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_money_spent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_energy_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_went_well: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_could_improve: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mood_reference: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    energy_reference: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tags_csv: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_daily_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class InsightDismissal(Base):
    __tablename__ = "insight_dismissals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    insight_key: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="dismissed", nullable=False)  # dismissed | reviewed
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # transactions | screen_time | activities | habits
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default="previewed", index=True, nullable=False
    )  # previewed | committed | failed
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preview_payload_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[List["ImportResult"]] = relationship(
        "ImportResult", back_populates="job", cascade="all, delete-orphan"
    )


class ImportResult(Base):
    __tablename__ = "import_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    import_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # valid | duplicate | error | imported
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    raw_row_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    job: Mapped["ImportJob"] = relationship("ImportJob", back_populates="results")


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    integration_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_receiving_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status_message: Mapped[str] = mapped_column(String(255), default="Unconfigured", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class FilterPreset(Base):
    __tablename__ = "filter_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    filter_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

