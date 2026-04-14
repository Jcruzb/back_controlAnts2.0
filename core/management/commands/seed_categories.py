import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Category, Family


DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "seeds" / "categories.json"


class Command(BaseCommand):
    help = "Create or update categories from a JSON seed file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_SEED_PATH),
            help="Path to the categories seed JSON file.",
        )
        parser.add_argument(
            "--family",
            dest="family_name",
            help="Apply the categories only to the given family name.",
        )

    def handle(self, *args, **options):
        seed_path = Path(options["path"]).expanduser().resolve()
        if not seed_path.exists():
            raise CommandError(f"Seed file not found: {seed_path}")

        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {seed_path}: {exc}") from exc

        categories = payload.get("categories")
        if not isinstance(categories, list) or not categories:
            raise CommandError("Seed file must contain a non-empty 'categories' list")

        families = self._get_families(options.get("family_name"))

        with transaction.atomic():
            for family in families:
                for category_data in categories:
                    self._seed_category(family, category_data)

        self.stdout.write(self.style.SUCCESS(f"Seed completed from {seed_path}"))

    def _get_families(self, family_name):
        if family_name:
            family = Family.objects.filter(name=family_name.strip()).first()
            if family is None:
                raise CommandError(f"Family not found: {family_name}")
            return [family]

        families = list(Family.objects.order_by("id"))
        if not families:
            raise CommandError("No families found. Seed users first.")
        return families

    def _seed_category(self, family, category_data):
        name = (category_data.get("name") or "").strip()
        icon = (category_data.get("icon") or "").strip()
        color = (category_data.get("color") or "#64748b").strip() or "#64748b"
        description = (category_data.get("description") or "").strip()

        if not name:
            raise CommandError("Each category must define a non-empty 'name'")
        if not icon:
            raise CommandError(f"Category '{name}' must define a non-empty 'icon'")

        category, created = Category.objects.update_or_create(
            family=family,
            name=name,
            defaults={
                "icon": icon,
                "color": color,
                "description": description,
            },
        )

        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Category {action}: family={family.name} name={category.name} icon={category.icon}"
            )
        )
