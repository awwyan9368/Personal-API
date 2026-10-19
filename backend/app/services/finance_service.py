import hashlib
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Budget,
    FinancialAccount,
    RecurringTransactionRule,
    Transaction,
    UserPreference,
)
from app.schemas.api_schemas import (
    AccountResponse,
    BudgetResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)

TWO_PLACES = Decimal("0.01")


def to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_transaction_hash(
    tx_date: date,
    amount: Decimal,
    currency: str,
    tx_type: str,
    category: str,
    merchant: Optional[str],
) -> str:
    norm_amt = str(to_decimal(amount))
    norm_merch = (merchant or "").strip().lower()
    norm_cat = (category or "").strip().lower()
    raw = f"{tx_date.isoformat()}|{norm_amt}|{currency.upper()}|{tx_type.lower()}|{norm_cat}|{norm_merch}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def serialize_transaction(db: Session, tx: Transaction, account_map: Optional[Dict[str, str]] = None) -> TransactionResponse:
    if account_map is None:
        accounts = db.execute(select(FinancialAccount)).scalars().all()
        account_map = {a.id: a.name for a in accounts}
    tags = [t.strip() for t in (tx.tags_csv or "").split(",") if t.strip()]
    return TransactionResponse(
        id=tx.id,
        amount=to_decimal(tx.amount),
        currency=tx.currency,
        transaction_type=tx.transaction_type,
        category=tx.category,
        subcategory=tx.subcategory,
        merchant=tx.merchant,
        transaction_date=tx.transaction_date,
        recorded_at=tx.recorded_at,
        account_id=tx.account_id,
        account_name=account_map.get(tx.account_id) if tx.account_id else None,
        to_account_id=tx.to_account_id,
        to_account_name=account_map.get(tx.to_account_id) if tx.to_account_id else None,
        payment_method=tx.payment_method,
        notes=tx.notes,
        tags=tags,
        receipt_reference=tx.receipt_reference,
        recurring_rule_id=tx.recurring_rule_id,
        created_at=tx.created_at,
        updated_at=tx.updated_at,
    )


def create_transaction(db: Session, payload: TransactionCreate) -> TransactionResponse:
    amt = to_decimal(payload.amount)
    tags_csv = ",".join(t.strip() for t in payload.tags if t.strip()) if payload.tags else None
    ext_hash = compute_transaction_hash(
        payload.transaction_date,
        amt,
        payload.currency,
        payload.transaction_type,
        payload.category,
        payload.merchant,
    )
    tx = Transaction(
        amount=amt,
        currency=payload.currency.upper(),
        transaction_type=payload.transaction_type,
        category=payload.category,
        subcategory=payload.subcategory,
        merchant=payload.merchant,
        transaction_date=payload.transaction_date,
        account_id=payload.account_id,
        to_account_id=payload.to_account_id,
        payment_method=payload.payment_method,
        notes=payload.notes,
        tags_csv=tags_csv,
        receipt_reference=payload.receipt_reference,
        recurring_rule_id=payload.recurring_rule_id,
        external_hash=ext_hash,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return serialize_transaction(db, tx)


def update_transaction(db: Session, tx: Transaction, payload: TransactionUpdate) -> TransactionResponse:
    data = payload.model_dump(exclude_unset=True)
    if "amount" in data and data["amount"] is not None:
        data["amount"] = to_decimal(data["amount"])
    if "currency" in data and data["currency"] is not None:
        data["currency"] = data["currency"].upper()
    if "tags" in data:
        tags_list = data.pop("tags") or []
        tx.tags_csv = ",".join(t.strip() for t in tags_list if t.strip()) or None

    for k, v in data.items():
        setattr(tx, k, v)

    tx.external_hash = compute_transaction_hash(
        tx.transaction_date,
        to_decimal(tx.amount),
        tx.currency,
        tx.transaction_type,
        tx.category,
        tx.merchant,
    )
    db.commit()
    db.refresh(tx)
    return serialize_transaction(db, tx)


def calculate_account_balance(db: Session, account: FinancialAccount) -> Decimal:
    """
    Calculates exact account balance using Decimal arithmetic:
    initial_balance + income (same currency) - expenses (same currency)
    - outgoing transfers + incoming transfers.
    """
    balance = to_decimal(account.initial_balance)
    txs = db.execute(
        select(Transaction).where(
            (Transaction.account_id == account.id) | (Transaction.to_account_id == account.id)
        )
    ).scalars().all()

    for tx in txs:
        if tx.currency.upper() != account.currency.upper():
            continue
        amt = to_decimal(tx.amount)
        if tx.transaction_type == "income" and tx.account_id == account.id:
            balance += amt
        elif tx.transaction_type == "expense" and tx.account_id == account.id:
            balance -= amt
        elif tx.transaction_type == "transfer":
            if tx.account_id == account.id:
                balance -= amt
            if tx.to_account_id == account.id:
                balance += amt

    return balance.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def serialize_account(db: Session, account: FinancialAccount) -> AccountResponse:
    current_bal = calculate_account_balance(db, account)
    return AccountResponse(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        currency=account.currency,
        initial_balance=to_decimal(account.initial_balance),
        current_balance=current_bal,
        color=account.color,
        icon=account.icon,
        is_active=account.is_active,
        notes=account.notes,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _advance_date(d: date, frequency: str) -> date:
    if frequency == "daily":
        return d + timedelta(days=1)
    if frequency == "weekly":
        return d + timedelta(days=7)
    if frequency == "monthly":
        return d + relativedelta(months=1)
    if frequency == "yearly":
        return d + relativedelta(years=1)
    return d + relativedelta(months=1)


def process_recurring_rules(db: Session, up_to_date: Optional[date] = None) -> List[TransactionResponse]:
    """
    Deterministically materializes due recurring transactions up to `up_to_date`.
    Tracks `occurrence_date` per `recurring_rule_id` so duplicates are impossible.
    """
    target_date = up_to_date or date.today()
    rules = db.execute(
        select(RecurringTransactionRule).where(
            RecurringTransactionRule.is_active == True,  # noqa: E712
            RecurringTransactionRule.next_due_date <= target_date,
        )
    ).scalars().all()

    created_txs: List[Transaction] = []
    for rule in rules:
        due = rule.next_due_date
        safety_counter = 0
        while due <= target_date and safety_counter < 366:
            safety_counter += 1
            if rule.end_date and due > rule.end_date:
                rule.is_active = False
                break

            # Check if occurrence already exists
            exists = db.execute(
                select(Transaction).where(
                    Transaction.recurring_rule_id == rule.id,
                    Transaction.occurrence_date == due,
                )
            ).scalar_one_or_none()

            if not exists:
                amt = to_decimal(rule.amount)
                tx = Transaction(
                    amount=amt,
                    currency=rule.currency.upper(),
                    transaction_type=rule.transaction_type,
                    category=rule.category,
                    subcategory=rule.subcategory,
                    merchant=rule.merchant or rule.title,
                    transaction_date=due,
                    account_id=rule.account_id,
                    to_account_id=rule.to_account_id,
                    payment_method=rule.payment_method,
                    notes=f"Auto-generated from recurring rule: {rule.title}",
                    recurring_rule_id=rule.id,
                    occurrence_date=due,
                    external_hash=compute_transaction_hash(
                        due, amt, rule.currency, rule.transaction_type, rule.category, rule.merchant or rule.title
                    ),
                )
                db.add(tx)
                created_txs.append(tx)

            rule.last_generated_date = due
            due = _advance_date(due, rule.frequency)
            rule.next_due_date = due

    if created_txs or rules:
        db.commit()

    return [serialize_transaction(db, tx) for tx in created_txs]


def evaluate_budget(db: Session, budget: Budget) -> BudgetResponse:
    year_str, month_str = budget.month.split("-")
    year, month = int(year_str), int(month_str)
    start_d = date(year, month, 1)
    end_d = date(year, month, monthrange(year, month)[1])

    stmt = select(Transaction).where(
        Transaction.transaction_date >= start_d,
        Transaction.transaction_date <= end_d,
        Transaction.transaction_type == "expense",
        Transaction.currency == budget.currency.upper(),
    )
    if budget.category and budget.category.upper() != "ALL":
        stmt = stmt.where(func.lower(Transaction.category) == budget.category.lower())

    txs = db.execute(stmt).scalars().all()
    spent = sum((to_decimal(t.amount) for t in txs), Decimal("0.00")).quantize(TWO_PLACES)
    limit_amt = to_decimal(budget.amount_limit)
    remaining = (limit_amt - spent).quantize(TWO_PLACES)
    util_pct = float((spent / limit_amt) * Decimal("100.0")) if limit_amt > Decimal("0.00") else 0.0
    util_pct = round(util_pct, 2)

    return BudgetResponse(
        id=budget.id,
        name=budget.name,
        month=budget.month,
        category=budget.category,
        currency=budget.currency,
        amount_limit=limit_amt,
        spent_amount=spent,
        remaining_amount=remaining,
        utilization_percent=util_pct,
        alert_threshold_percent=budget.alert_threshold_percent,
        is_threshold_crossed=util_pct >= float(budget.alert_threshold_percent),
        is_over_budget=spent > limit_amt,
        notes=budget.notes,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
    )


def get_finance_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes consolidated financial summary using exact Decimal arithmetic.
    - Never silently combines different currencies.
    - Excludes transfers from income and expense totals.
    """
    pref = db.execute(select(UserPreference)).scalar_one_or_none()
    active_currency = (currency or (pref.base_currency if pref else "INR")).upper()

    today = date.today()
    if not start_date or not end_date:
        start_date = date(today.year, today.month, 1)
        end_date = date(today.year, today.month, monthrange(today.year, today.month)[1])

    all_period_txs = db.execute(
        select(Transaction).where(
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
    ).scalars().all()

    # Group available currencies in period so user knows if records exist in other currencies
    currencies_present = sorted(set(t.currency.upper() for t in all_period_txs))
    by_currency_totals: Dict[str, Dict[str, str]] = {}
    for curr in currencies_present:
        c_txs = [t for t in all_period_txs if t.currency.upper() == curr]
        inc = sum((to_decimal(t.amount) for t in c_txs if t.transaction_type == "income"), Decimal("0.00"))
        exp = sum((to_decimal(t.amount) for t in c_txs if t.transaction_type == "expense"), Decimal("0.00"))
        trf = sum((to_decimal(t.amount) for t in c_txs if t.transaction_type == "transfer"), Decimal("0.00"))
        by_currency_totals[curr] = {
            "income": str(inc.quantize(TWO_PLACES)),
            "expense": str(exp.quantize(TWO_PLACES)),
            "net": str((inc - exp).quantize(TWO_PLACES)),
            "transfers_excluded": str(trf.quantize(TWO_PLACES)),
        }

    # Filter to active_currency for primary analytics
    txs = [t for t in all_period_txs if t.currency.upper() == active_currency]

    total_income = sum(
        (to_decimal(t.amount) for t in txs if t.transaction_type == "income"),
        Decimal("0.00"),
    ).quantize(TWO_PLACES)
    total_expense = sum(
        (to_decimal(t.amount) for t in txs if t.transaction_type == "expense"),
        Decimal("0.00"),
    ).quantize(TWO_PLACES)
    total_transfer = sum(
        (to_decimal(t.amount) for t in txs if t.transaction_type == "transfer"),
        Decimal("0.00"),
    ).quantize(TWO_PLACES)
    net_savings = (total_income - total_expense).quantize(TWO_PLACES)
    savings_rate = (
        round(float((net_savings / total_income) * Decimal("100.0")), 2)
        if total_income > Decimal("0.00")
        else None
    )

    # Category breakdown for expenses
    category_totals: Dict[str, Decimal] = {}
    merchant_totals: Dict[str, Decimal] = {}
    daily_map: Dict[str, Dict[str, Decimal]] = {}

    for t in txs:
        d_key = t.transaction_date.isoformat()
        if d_key not in daily_map:
            daily_map[d_key] = {"income": Decimal("0.00"), "expense": Decimal("0.00")}
        amt = to_decimal(t.amount)
        if t.transaction_type == "expense":
            category_totals[t.category] = category_totals.get(t.category, Decimal("0.00")) + amt
            merch_name = (t.merchant or "Unspecified").strip()
            merchant_totals[merch_name] = merchant_totals.get(merch_name, Decimal("0.00")) + amt
            daily_map[d_key]["expense"] += amt
        elif t.transaction_type == "income":
            daily_map[d_key]["income"] += amt

    category_breakdown = []
    for cat, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        share = round(float((amt / total_expense) * Decimal("100.0")), 2) if total_expense > Decimal("0.00") else 0.0
        category_breakdown.append(
            {
                "category": cat,
                "amount": str(amt.quantize(TWO_PLACES)),
                "amount_numeric": float(amt.quantize(TWO_PLACES)),
                "percentage": share,
            }
        )

    merchant_breakdown = [
        {
            "merchant": m,
            "amount": str(amt.quantize(TWO_PLACES)),
            "amount_numeric": float(amt.quantize(TWO_PLACES)),
        }
        for m, amt in sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    expense_txs = sorted(
        [t for t in txs if t.transaction_type == "expense"],
        key=lambda x: to_decimal(x.amount),
        reverse=True,
    )
    largest_expenses = [serialize_transaction(db, t).model_dump(mode="json") for t in expense_txs[:5]]

    # Previous period comparison of equal length
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)
    prev_txs = db.execute(
        select(Transaction).where(
            Transaction.transaction_date >= prev_start,
            Transaction.transaction_date <= prev_end,
            Transaction.currency == active_currency,
        )
    ).scalars().all()

    prev_expense = sum(
        (to_decimal(t.amount) for t in prev_txs if t.transaction_type == "expense"),
        Decimal("0.00"),
    ).quantize(TWO_PLACES)
    prev_income = sum(
        (to_decimal(t.amount) for t in prev_txs if t.transaction_type == "income"),
        Decimal("0.00"),
    ).quantize(TWO_PLACES)

    exp_abs_change = (total_expense - prev_expense).quantize(TWO_PLACES)
    exp_pct_change = (
        round(float((exp_abs_change / prev_expense) * Decimal("100.0")), 2)
        if prev_expense > Decimal("0.00")
        else None
    )

    # Budgets for the start_date's YYYY-MM
    month_key = start_date.strftime("%Y-%m")
    budgets_db = db.execute(
        select(Budget).where(Budget.month == month_key, Budget.currency == active_currency)
    ).scalars().all()
    evaluated_budgets = [evaluate_budget(db, b) for b in budgets_db]
    budget_alerts = [
        {
            "budget_id": b.id,
            "name": b.name,
            "category": b.category,
            "utilization_percent": b.utilization_percent,
            "spent_amount": str(b.spent_amount),
            "amount_limit": str(b.amount_limit),
            "severity": "critical" if b.is_over_budget else "warning",
            "message": (
                f"Budget '{b.name}' ({b.category}) exceeded limit: {active_currency} {b.spent_amount} / {b.amount_limit}"
                if b.is_over_budget
                else f"Budget '{b.name}' ({b.category}) reached {b.utilization_percent}% of {active_currency} {b.amount_limit}"
            ),
        }
        for b in evaluated_budgets
        if b.is_threshold_crossed
    ]

    daily_series = []
    for i in range(period_days):
        d_iso = (start_date + timedelta(days=i)).isoformat()
        vals = daily_map.get(d_iso, {"income": Decimal("0.00"), "expense": Decimal("0.00")})
        daily_series.append(
            {
                "date": d_iso,
                "income": float(vals["income"].quantize(TWO_PLACES)),
                "expense": float(vals["expense"].quantize(TWO_PLACES)),
            }
        )

    return {
        "currency": active_currency,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_income": str(total_income),
        "total_income_numeric": float(total_income),
        "total_expense": str(total_expense),
        "total_expense_numeric": float(total_expense),
        "total_transfers_excluded": str(total_transfer),
        "net_savings": str(net_savings),
        "net_savings_numeric": float(net_savings),
        "savings_rate_percent": savings_rate,
        "currencies_present": currencies_present,
        "by_currency_totals": by_currency_totals,
        "category_breakdown": category_breakdown,
        "merchant_breakdown": merchant_breakdown,
        "largest_expenses": largest_expenses,
        "daily_series": daily_series,
        "budgets": [b.model_dump(mode="json") for b in evaluated_budgets],
        "budget_alerts": budget_alerts,
        "period_comparison": {
            "previous_start_date": prev_start.isoformat(),
            "previous_end_date": prev_end.isoformat(),
            "previous_expense": str(prev_expense),
            "previous_income": str(prev_income),
            "expense_absolute_change": str(exp_abs_change),
            "expense_percentage_change": exp_pct_change,
            "has_sufficient_previous_data": len(prev_txs) > 0 and prev_expense > Decimal("0.00"),
            "explanation": (
                f"Compared with {prev_start.isoformat()} to {prev_end.isoformat()}"
                if len(prev_txs) > 0 and prev_expense > Decimal("0.00")
                else "Insufficient expense records in the previous period to calculate a percentage change."
            ),
        },
    }

