from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the complete local demo scenario (users, incomes, planning and expenses)."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=4, help="Number of demo months (default: 4).")
        parser.add_argument("--reset", action="store_true", help="Delete only the isolated demo scenario.")

    def handle(self, *args, **options):
        call_command("seed_demo", months=options["months"], reset=options["reset"])
        self.stdout.write(self.style.SUCCESS("All local demo seeds completed successfully"))
