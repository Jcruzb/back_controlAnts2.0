import json
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Family, Profile


DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "seeds" / "users.json"


class Command(BaseCommand):
    help = "Create or update users from a JSON seed file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_SEED_PATH),
            help="Path to the users seed JSON file.",
        )
        parser.add_argument(
            "--fast-passwords",
            action="store_true",
            help="Use a fast dev-only password hash when seeding users.",
        )

    def handle(self, *args, **options):
        seed_path = Path(options["path"]).expanduser().resolve()
        if not seed_path.exists():
            raise CommandError(f"Seed file not found: {seed_path}")

        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {seed_path}: {exc}") from exc

        users = payload.get("users")
        if not isinstance(users, list) or not users:
            raise CommandError("Seed file must contain a non-empty 'users' list")

        with transaction.atomic():
            for user_data in users:
                self._seed_user(
                    user_data,
                    fast_passwords=options["fast_passwords"],
                )

        self.stdout.write(self.style.SUCCESS(f"Seed completed from {seed_path}"))

    def _seed_user(self, user_data, *, fast_passwords=False):
        username = (user_data.get("username") or "").strip()
        password = user_data.get("password")

        if not username:
            raise CommandError("Each user must define a non-empty 'username'")
        if not password:
            raise CommandError(f"User '{username}' must define 'password'")

        desired_id = user_data.get("id")
        user = User.objects.filter(username=username).first()

        if user is None and desired_id is not None:
            user = User.objects.filter(id=desired_id).first()
            if user is not None and user.username != username:
                raise CommandError(
                    f"Cannot assign id={desired_id} to '{username}' because it already belongs to '{user.username}'"
                )

        created = user is None
        if created:
            user = User()
            if desired_id is not None:
                user.id = desired_id

        user.username = username
        user.email = (user_data.get("email") or "").strip().lower()
        user.first_name = (user_data.get("first_name") or "").strip()
        user.last_name = (user_data.get("last_name") or "").strip()
        user.is_active = user_data.get("is_active", True)
        user.is_staff = user_data.get("is_staff", False)
        user.is_superuser = user_data.get("is_superuser", False)
        if fast_passwords:
            user.password = make_password(password, hasher="md5")
        else:
            user.set_password(password)
        user.save()

        family_name = (user_data.get("family") or f"Familia de {username}").strip()
        family, _ = Family.objects.get_or_create(name=family_name)

        Profile.objects.update_or_create(
            user=user,
            defaults={
                "family": family,
                "role": user_data.get("role", "member"),
            },
        )

        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"User {action}: username={user.username} id={user.id} family={family.name}"
            )
        )
