from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run all project seeds in the correct order."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fast-passwords",
            action="store_true",
            help="Use a fast dev-only password hash when seeding users.",
        )
        parser.add_argument(
            "--family",
            dest="family_name",
            help="Apply family-scoped seeds only to the given family name.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Running seed_users"))
        seed_users_options = {}
        if options.get("fast_passwords"):
            seed_users_options["fast_passwords"] = True
        call_command("seed_users", **seed_users_options)

        family_name = options.get("family_name")

        self.stdout.write(self.style.MIGRATE_HEADING("Running seed_categories"))
        seed_categories_options = {}
        if family_name:
            seed_categories_options["family_name"] = family_name
        call_command("seed_categories", **seed_categories_options)

        self.stdout.write(self.style.MIGRATE_HEADING("Running seed_recurring_payments"))
        seed_recurring_options = {}
        if family_name:
            seed_recurring_options["family_name"] = family_name
        call_command("seed_recurring_payments", **seed_recurring_options)

        self.stdout.write(self.style.SUCCESS("All seeds completed successfully"))
