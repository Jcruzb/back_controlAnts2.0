import os
import json
from calendar import monthrange
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    Category,
    Expense,
    Family,
    Income,
    IncomePlan,
    IncomePlanVersion,
    Month,
    PlannedExpense,
    PlannedExpensePlan,
    PlannedExpenseVersion,
    Profile,
    RecurringPayment,
    RecurringPaymentOccurrence,
)


DEMO_SEEDS_DIR = Path(__file__).resolve().parents[2] / "seeds" / "demo"


def load_seed(name):
    path = DEMO_SEEDS_DIR / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CommandError(f"Demo seed file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON in {path}: {exc}") from exc


IDENTITY = load_seed("users")
DEMO_FAMILY = IDENTITY["family"]
DEMO_PREFIX = IDENTITY["prefix"]
DEMO_USERNAMES = tuple(item["username"] for item in IDENTITY["users"])
DEMO_PASSWORD = IDENTITY["users"][0]["password"]


def add_months(value, offset):
    absolute = value.year * 12 + value.month - 1 + offset
    return date(absolute // 12, absolute % 12 + 1, 1)


def valid_date(month_date, day):
    return date(month_date.year, month_date.month, min(day, monthrange(month_date.year, month_date.month)[1]))


class Command(BaseCommand):
    help = "Create an idempotent, realistic demo family without touching real data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=4,
            help="Number of months: current, one future (when possible), and the remainder historical (default: 4).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete only the isolated demo family and its two demo users.",
        )
        parser.add_argument(
            "--only",
            choices=("users", "categories", "incomes", "planned_expenses", "recurring_payments", "expenses"),
            help="Seed one domain plus its required dependencies.",
        )

    def handle(self, *args, **options):
        self._assert_safe_environment()
        months_count = options["months"]
        if not 1 <= months_count <= 60:
            raise CommandError("--months must be between 1 and 60")

        with transaction.atomic():
            if options["reset"]:
                self._reset()
                return
            self.stats = Counter()
            self.seed_data = {
                name: load_seed(name)
                for name in ("users", "categories", "incomes", "planned_expenses", "recurring_payments", "expenses")
            }
            family, users = self._seed_identity()
            if options["only"] == "users":
                return self._write_summary()
            categories = self._seed_categories(family)
            if options["only"] == "categories":
                return self._write_summary()
            months = self._seed_months(family, months_count)
            income_plans = self._seed_income_plans(family, users, categories, months)
            self._seed_incomes(users, categories, months, income_plans)
            if options["only"] == "incomes":
                return self._write_summary()
            planned = self._seed_planned_expenses(family, users[0], categories, months)
            if options["only"] == "planned_expenses":
                return self._write_summary()
            recurring = self._seed_recurring_payments(family, users, categories, months)
            if options["only"] == "recurring_payments":
                return self._write_summary()
            self._seed_expenses(users, categories, months, planned, recurring)

        self._write_summary()

    def _write_summary(self):
        summary = ", ".join(f"{key}={value}" for key, value in sorted(self.stats.items()))
        self.stdout.write(self.style.SUCCESS(f"Demo seed completed: {summary}"))
        self.stdout.write(f"Login: {DEMO_USERNAMES[0]} / {DEMO_PASSWORD}")

    def _assert_safe_environment(self):
        allowed = os.getenv("ALLOW_DEMO_SEEDS", "").lower() in {"1", "true", "yes", "on"}
        if not settings.DEBUG and not allowed:
            raise CommandError(
                "Demo seeds are disabled because DEBUG=False. Set ALLOW_DEMO_SEEDS=true explicitly to allow this operation."
            )

    def _reset(self):
        family = Family.objects.filter(name=DEMO_FAMILY).first()
        users = list(User.objects.filter(username__in=DEMO_USERNAMES).select_related("profile__family"))
        if family:
            foreign_members = family.profile_set.exclude(user__username__in=DEMO_USERNAMES)
            if foreign_members.exists():
                raise CommandError("Refusing reset: the demo family contains users outside the demo set")
        for user in users:
            user_family = getattr(getattr(user, "profile", None), "family", None)
            allowed_family_names = {DEMO_FAMILY, f"Familia de {user.username}"}
            if user_family and user_family.name not in allowed_family_names:
                raise CommandError(f"Refusing reset: {user.username} no longer belongs to the demo family")
        if family:
            # Delete in dependency order because Month and Category are protected
            # by planning models. Every queryset remains scoped to the validated
            # reserved family.
            Expense.objects.filter(month__family=family).delete()
            Income.objects.filter(month__family=family).delete()
            RecurringPaymentOccurrence.objects.filter(month__family=family).delete()
            PlannedExpense.objects.filter(family=family).delete()
            PlannedExpensePlan.objects.filter(family=family).delete()
            IncomePlan.objects.filter(family=family).delete()
            RecurringPayment.objects.filter(family=family).delete()
            Month.objects.filter(family=family).delete()
            Category.objects.filter(family=family).delete()
            family.delete()
        for user in users:
            user.delete()
        self.stdout.write(self.style.SUCCESS("Demo data reset completed; no non-demo family was touched"))

    def _record(self, model_name, created):
        self.stats[f"{model_name}_{'created' if created else 'updated'}"] += 1

    def _seed_identity(self):
        family, family_created = Family.objects.get_or_create(name=DEMO_FAMILY)
        self._record("families", family_created)
        foreign_members = family.profile_set.exclude(user__username__in=DEMO_USERNAMES)
        if foreign_members.exists():
            raise CommandError("The reserved demo family name is already used by non-demo users")

        users = []
        for spec in self.seed_data["users"]["users"]:
            username = spec["username"]
            existing = User.objects.filter(username=username).select_related("profile__family").first()
            if existing and existing.profile.family_id != family.id:
                raise CommandError(f"Reserved demo username already belongs to another family: {username}")
            user, created = User.objects.get_or_create(username=username)
            user.email = spec.get("email", username)
            user.first_name = spec.get("first_name", "")
            user.last_name = spec.get("last_name", "")
            user.is_active = spec.get("is_active", True)
            user.is_staff = spec.get("is_staff", False)
            user.is_superuser = spec.get("is_superuser", False)
            user.set_password(spec["password"])
            user.save()
            Profile.objects.update_or_create(user=user, defaults={"family": family, "role": spec.get("role", "member")})
            self._record("users", created)
            users.append(user)
        return family, users

    def _seed_categories(self, family):
        result = {}
        for spec in self.seed_data["categories"]["categories"]:
            name = spec["name"]
            category, created = Category.objects.update_or_create(
                family=family,
                name=name,
                defaults={
                    "icon": spec["icon"], "color": spec.get("color", "#64748b"),
                    "description": spec.get("description", ""),
                },
            )
            self._record("categories", created)
            result[name] = category
        return result

    def _seed_months(self, family, count):
        current = date.today().replace(day=1)
        offsets = [0] if count == 1 else list(range(-(count - 2), 1)) + [1]
        result = []
        for month_date in offsets:
            value = add_months(current, month_date)
            month, created = Month.objects.get_or_create(
                family=family, year=value.year, month=value.month, defaults={"is_closed": False}
            )
            self._record("months", created)
            result.append((value, month))
        return result

    def _seed_income_plans(self, family, users, categories, months):
        first_month = months[0][1]
        result = []
        users_by_name = {user.username: user for user in users}
        for spec in self.seed_data["incomes"]["plans"]:
            name, amount = spec["name"], spec["amount"]
            creator = users_by_name[spec["user"]]
            plan, created = IncomePlan.objects.update_or_create(
                family=family,
                name=DEMO_PREFIX + name,
                defaults={
                    "category": categories[spec["category"]], "plan_type": "ONGOING", "due_day": spec.get("due_day", 1),
                    "active": True, "start_month": first_month, "end_month": None, "created_by": creator,
                },
            )
            self._record("income_plans", created)
            version, version_created = IncomePlanVersion.objects.update_or_create(
                plan=plan, valid_from=first_month,
                defaults={"planned_amount": Decimal(amount), "valid_to": None},
            )
            self._record("income_versions", version_created)
            result.append((plan, creator, Decimal(amount)))
        return result

    def _seed_planned_expenses(self, family, creator, categories, months):
        seed = self.seed_data["planned_expenses"]
        result = {}
        for month_date, month in months:
            for spec in seed["monthly"]:
                category_name, amount = spec["category"], spec["amount"]
                planned, created = PlannedExpense.objects.update_or_create(
                    month=month,
                    category=categories[category_name],
                    defaults={
                        "family": family, "name": DEMO_PREFIX + category_name,
                        "planned_amount": Decimal(amount), "created_by": creator,
                    },
                )
                self._record("planned_expenses", created)
                result[(month.id, category_name)] = planned

        future_date, future_month = months[-1]
        if future_date > date.today().replace(day=1):
            future = seed["future"]
            plan, created = PlannedExpensePlan.objects.update_or_create(
                family=family, name=DEMO_PREFIX + future["name"],
                defaults={
                    "category": categories[future["category"]], "plan_type": "ONE_MONTH", "active": True,
                    "start_month": future_month, "end_month": future_month, "created_by": creator,
                },
            )
            self._record("planned_plans", created)
            version, version_created = PlannedExpenseVersion.objects.update_or_create(
                plan=plan, valid_from=future_month,
                defaults={"planned_amount": Decimal(future["amount"]), "valid_to": future_month},
            )
            self._record("planned_versions", version_created)
        return result

    def _seed_recurring_payments(self, family, users, categories, months):
        first_date = months[0][0]
        users_by_name = {user.username: user for user in users}
        result = {}
        for spec in self.seed_data["recurring_payments"]["recurring_payments"]:
            name, amount, due_day = spec["name"], spec["amount"], spec["due_day"]
            category_name, payer = spec["category"], users_by_name[spec["payer"]]
            recurring, created = RecurringPayment.objects.update_or_create(
                family=family, name=DEMO_PREFIX + name,
                defaults={
                    "category": categories[category_name], "payer": payer, "amount": Decimal(amount),
                    "due_day": due_day, "start_date": first_date, "end_date": None, "active": True,
                },
            )
            self._record("recurring_payments", created)
            result[name] = recurring
        return result

    def _seed_incomes(self, users, categories, months, income_plans):
        users_by_name = {user.username: user for user in users}
        current = date.today().replace(day=1)
        by_offset = {(value.year - current.year) * 12 + value.month - current.month: (value, month) for value, month in months}
        for month_date, month in months:
            if month_date > current:
                continue
            for plan, user, amount in income_plans:
                income, created = Income.objects.update_or_create(
                    month=month, income_plan=plan,
                    defaults={
                        "user": user, "amount": amount, "category": categories["Otros"],
                        "date": valid_date(month_date, 1), "description": DEMO_PREFIX + plan.name.removeprefix(DEMO_PREFIX),
                    },
                )
                self._record("incomes", created)
        for spec in self.seed_data["incomes"]["extras"]:
            offset = spec["month_offset"]
            if offset not in by_offset:
                continue
            month_date, month = by_offset[offset]
            self._upsert_income(
                month=month, user=users_by_name[spec["user"]], category=categories[spec["category"]],
                amount=Decimal(spec["amount"]), date=valid_date(month_date, spec.get("day", 1)),
                description=DEMO_PREFIX + spec["description"],
            )

    def _upsert_income(self, **values):
        lookup = {key: values[key] for key in ("month", "user", "category", "date", "description") if key in values}
        existing = Income.objects.filter(**lookup, income_plan__isnull=True).order_by("id").first()
        if existing:
            existing.amount = values["amount"]
            existing.save(update_fields=["amount"])
            created = False
        else:
            Income.objects.create(**values)
            created = True
        self._record("incomes", created)

    def _seed_expenses(self, users, categories, months, planned, recurring):
        current = date.today().replace(day=1)
        seed = self.seed_data["expenses"]
        for index, (month_date, month) in enumerate(months):
            if month_date > current:
                continue
            factor_config = seed["historical_factor"]
            factor = Decimal("1.00") if month_date == current else Decimal(factor_config["base"]) + Decimal(index) * Decimal(factor_config["step"])
            for pos, spec in enumerate(seed["variable"]):
                category_name = spec["category"]
                planned_expense = planned.get((month.id, category_name))
                self._upsert_expense(
                    month=month, user=users[pos % 2], payer=users[pos % 2],
                    amount=(Decimal(spec["amount"]) * factor).quantize(Decimal("0.01")),
                    category=categories[category_name], planned_expense=planned_expense,
                    recurring_payment=None, date=valid_date(month_date, spec["day"]),
                    description=DEMO_PREFIX + spec["description"], is_recurring=False,
                )
            for spec in seed["recurring"]:
                name = spec["name"]
                recurring_payment = recurring[name]
                for payment in spec["payments"]:
                    self._upsert_expense(
                        month=month, user=users[0], payer=recurring_payment.payer,
                        amount=Decimal(payment["amount"]), category=recurring_payment.category, planned_expense=None,
                        recurring_payment=recurring_payment, date=valid_date(month_date, payment["day"]),
                        description=DEMO_PREFIX + recurring_payment.name.removeprefix(DEMO_PREFIX), is_recurring=True,
                    )
                occurrence, created = RecurringPaymentOccurrence.objects.get_or_create(
                    recurring_payment=recurring_payment, month=month,
                )
                should_complete = spec.get("complete_historical", False) and month_date < current
                if occurrence.is_completed != should_complete:
                    occurrence.is_completed = should_complete
                    occurrence.save(update_fields=["is_completed"])
                self._record("recurring_occurrences", created)

    def _upsert_expense(self, **values):
        lookup = {
            key: values[key]
            for key in ("month", "user", "category", "planned_expense", "recurring_payment", "date", "description")
        }
        existing = Expense.objects.filter(**lookup).order_by("id").first()
        if existing:
            for key in ("payer", "amount", "is_recurring"):
                setattr(existing, key, values[key])
            existing.save(update_fields=["payer", "amount", "is_recurring"])
            created = False
        else:
            Expense.objects.create(**values)
            created = True
        self._record("expenses", created)
