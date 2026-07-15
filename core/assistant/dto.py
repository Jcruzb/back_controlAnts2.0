from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional


MONEY_QUANTUM = Decimal("0.01")
SPANISH_MONTH_NAMES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


def money_string(value) -> str:
    return str(Decimal(value or 0).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def percentage_string(value) -> str:
    return money_string(value)


@dataclass(frozen=True)
class PeriodDTO:
    year: int
    month: int
    label: str

    @classmethod
    def create(cls, *, year: int, month: int):
        return cls(
            year=year,
            month=month,
            label=f"{SPANISH_MONTH_NAMES[month - 1]} de {year}",
        )


@dataclass(frozen=True)
class MonthlyBudgetSummaryDTO:
    period: PeriodDTO
    currency: str
    planned_total: str
    planned_paid: str
    planned_pending: str
    unplanned_total: str
    budget_variance: str
    percentage_used: str
    status: str

    @classmethod
    def from_budget(cls, *, budget: Dict[str, Any], currency: str):
        return cls(
            period=PeriodDTO.create(year=budget["year"], month=budget["month"]),
            currency=currency,
            planned_total=money_string(budget["total_planned"]),
            planned_paid=money_string(budget["planned_paid_amount"]),
            planned_pending=money_string(budget["planned_pending_amount"]),
            unplanned_total=money_string(budget["unplanned_total"]),
            budget_variance=money_string(budget["budget_variance"]),
            percentage_used=percentage_string(budget["percentage_used"]),
            status=budget["status"],
        )

    def to_dict(self):
        return {
            "period": asdict(self.period),
            "currency": self.currency,
            "planned": {
                "total": self.planned_total,
                "paid": self.planned_paid,
                "pending": self.planned_pending,
            },
            "unplanned": {"total": self.unplanned_total},
            "budget": {
                "variance": self.budget_variance,
                "percentage_used": self.percentage_used,
                "status": self.status,
            },
        }


@dataclass(frozen=True)
class MonthlyCashSummaryDTO:
    period: PeriodDTO
    currency: str
    actual_income: str
    total_outflows: str
    planned_outflows: str
    unplanned_outflows: str
    cash_balance: str

    @classmethod
    def from_budget(cls, *, budget: Dict[str, Any], currency: str):
        return cls(
            period=PeriodDTO.create(year=budget["year"], month=budget["month"]),
            currency=currency,
            actual_income=money_string(budget["actual_income"]),
            total_outflows=money_string(budget["actual_spent"]),
            planned_outflows=money_string(budget["planned_paid_amount"]),
            unplanned_outflows=money_string(budget["unplanned_total"]),
            cash_balance=money_string(budget["cash_balance"]),
        )

    def to_dict(self):
        return {
            "period": asdict(self.period),
            "currency": self.currency,
            "income": {"actual": self.actual_income},
            "outflows": {
                "total": self.total_outflows,
                "planned": self.planned_outflows,
                "unplanned": self.unplanned_outflows,
            },
            "cash_balance": self.cash_balance,
        }


@dataclass(frozen=True)
class ExpenseListItemDTO:
    id: int
    name: str
    amount: str
    date: str
    category_name: str
    category_icon: str
    payer_display_name: Optional[str]
    is_planned: bool

    @classmethod
    def from_expense(cls, expense):
        payer_display_name = None
        if expense.payer is not None:
            payer_display_name = expense.payer.get_full_name().strip() or expense.payer.username
        return cls(
            id=expense.id,
            name=expense.description or expense.category.name,
            amount=money_string(expense.amount),
            date=expense.date.isoformat(),
            category_name=expense.category.name,
            category_icon=expense.category.icon,
            payer_display_name=payer_display_name,
            is_planned=bool(
                expense.planned_expense_id
                or expense.planned_expense_plan_id
                or expense.recurring_payment_id
            ),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "date": self.date,
            "category": {
                "name": self.category_name,
                "icon": self.category_icon,
            },
            "payer": (
                {"display_name": self.payer_display_name}
                if self.payer_display_name is not None
                else None
            ),
            "is_planned": self.is_planned,
        }


@dataclass(frozen=True)
class RecurringPaymentStatusDTO:
    id: int
    name: str
    category_name: str
    payer_display_name: Optional[str]
    planned_amount: str
    paid_amount: str
    pending_amount: str
    difference_amount: str
    is_completed: bool
    payment_status: str

    @classmethod
    def from_budget_item(cls, item):
        payer = item.get("payer_detail") or {}
        return cls(
            id=item["id"],
            name=item["name"],
            category_name=item["category_name"],
            payer_display_name=payer.get("display_name"),
            planned_amount=money_string(item["planned_amount"]),
            paid_amount=money_string(item["paid_amount"]),
            pending_amount=money_string(item["pending_amount"]),
            difference_amount=money_string(item["difference_amount"]),
            is_completed=item["is_completed"],
            payment_status=item["payment_status"],
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": {"name": self.category_name},
            "payer": (
                {"display_name": self.payer_display_name}
                if self.payer_display_name is not None
                else None
            ),
            "planned_amount": self.planned_amount,
            "paid_amount": self.paid_amount,
            "pending_amount": self.pending_amount,
            "difference_amount": self.difference_amount,
            "is_completed": self.is_completed,
            "payment_status": self.payment_status,
        }


@dataclass(frozen=True)
class CategorySpendingSummaryDTO:
    category_id: int
    name: str
    icon: str
    amount: str
    count: int
    percentage: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class PayerSpendingSummaryDTO:
    payer_id: Optional[int]
    display_name: str
    amount: str
    count: int
    percentage: str

    def to_dict(self):
        return asdict(self)

