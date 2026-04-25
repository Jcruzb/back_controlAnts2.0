import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Category, Family, RecurringPayment


DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "seeds" / "recurring_payments.json"


class Command(BaseCommand):
    help = "Create or update recurring payments from a JSON seed file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_SEED_PATH),
            help="Path to the recurring payments seed JSON file.",
        )
        parser.add_argument(
            "--family",
            dest="family_name",
            help="Only apply entries for the given family name.",
        )

    def handle(self, *args, **options):
        seed_path = Path(options["path"]).expanduser().resolve()
        if not seed_path.exists():
            raise CommandError(f"Seed file not found: {seed_path}")

        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {seed_path}: {exc}") from exc

        recurring_payments = payload.get("recurring_payments")
        if not isinstance(recurring_payments, list) or not recurring_payments:
            raise CommandError("Seed file must contain a non-empty 'recurring_payments' list")

        family_name = options.get("family_name")
        if family_name:
            recurring_payments = [
                item for item in recurring_payments
                if (item.get("family") or "").strip() == family_name.strip()
            ]
            if not recurring_payments:
                raise CommandError(f"No recurring payments found for family: {family_name}")

        with transaction.atomic():
            for recurring_payment_data in recurring_payments:
                self._seed_recurring_payment(recurring_payment_data)

        self.stdout.write(self.style.SUCCESS(f"Seed completed from {seed_path}"))

    def _seed_recurring_payment(self, recurring_payment_data):
        family_name = (recurring_payment_data.get("family") or "").strip()
        category_name = (recurring_payment_data.get("category") or "").strip()
        name = (recurring_payment_data.get("name") or "").strip()

        if not family_name:
            raise CommandError("Each recurring payment must define a non-empty 'family'")
        if not category_name:
            raise CommandError(f"Recurring payment '{name or '[unnamed]'}' must define a non-empty 'category'")
        if not name:
            raise CommandError("Each recurring payment must define a non-empty 'name'")

        family = Family.objects.filter(name=family_name).first()
        if family is None:
            raise CommandError(f"Family not found for recurring payment '{name}': {family_name}")

        category = Category.objects.filter(family=family, name=category_name).first()
        if category is None:
            raise CommandError(
                f"Category not found for recurring payment '{name}': family={family_name} category={category_name}"
            )

        amount_raw = recurring_payment_data.get("amount")
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            raise CommandError(f"Recurring payment '{name}' has invalid amount: {amount_raw}")

        if amount <= 0:
            raise CommandError(f"Recurring payment '{name}' must define a positive amount")

        due_day = recurring_payment_data.get("due_day")
        if not isinstance(due_day, int) or not (1 <= due_day <= 31):
            raise CommandError(f"Recurring payment '{name}' must define due_day between 1 and 31")

        start_date = recurring_payment_data.get("start_date")
        if not start_date:
            raise CommandError(f"Recurring payment '{name}' must define start_date")

        end_date = recurring_payment_data.get("end_date")
        active = recurring_payment_data.get("active", True)
        payer = None
        payer_username = (recurring_payment_data.get("payer") or "").strip()
        if payer_username:
            payer = User.objects.filter(
                username=payer_username,
                profile__family=family,
                is_active=True,
            ).first()
            if payer is None:
                raise CommandError(
                    f"Payer not found for recurring payment '{name}': "
                    f"family={family_name} username={payer_username}"
                )

        recurring_payment, created = RecurringPayment.objects.update_or_create(
            family=family,
            name=name,
            defaults={
                "category": category,
                "payer": payer,
                "amount": amount,
                "due_day": due_day,
                "start_date": start_date,
                "end_date": end_date,
                "active": active,
            },
        )

        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Recurring payment {action}: family={family.name} name={recurring_payment.name}"
            )
        )
