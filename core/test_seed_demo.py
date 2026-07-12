from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from core.management.commands.seed_demo import DEMO_FAMILY, DEMO_USERNAMES, load_seed
from core.models import Expense, Family, Income, Profile


@override_settings(DEBUG=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeedDemoCommandTests(TestCase):
    def run_seed(self, *args):
        output = StringIO()
        call_command("seed_demo", *args, stdout=output)
        return output.getvalue()

    def test_seed_is_idempotent_and_creates_a_coherent_demo_family(self):
        self.run_seed("--months", "4")
        first_counts = (User.objects.count(), Expense.objects.count(), Income.objects.count())

        output = self.run_seed("--months", "4")

        self.assertEqual(first_counts, (User.objects.count(), Expense.objects.count(), Income.objects.count()))
        family = Family.objects.get(name=DEMO_FAMILY)
        self.assertEqual(Profile.objects.filter(family=family).count(), 2)
        self.assertEqual(set(family.profile_set.values_list("user__username", flat=True)), set(DEMO_USERNAMES))
        self.assertIn("Demo seed completed", output)

    def test_seed_values_are_loaded_from_json(self):
        identity = load_seed("users")
        incomes = load_seed("incomes")
        expenses = load_seed("expenses")

        self.assertEqual(identity["family"], DEMO_FAMILY)
        self.assertEqual(len(incomes["plans"]), 2)
        self.assertGreater(len(expenses["variable"]), 0)

    def test_independent_users_seed_only_creates_identity(self):
        self.run_seed("--only", "users")

        family = Family.objects.get(name=DEMO_FAMILY)
        self.assertEqual(Profile.objects.filter(family=family).count(), 2)
        self.assertFalse(Income.objects.filter(month__family=family).exists())

    def test_seed_all_runs_complete_demo(self):
        output = StringIO()
        call_command("seed_all", stdout=output)

        family = Family.objects.get(name=DEMO_FAMILY)
        self.assertTrue(Expense.objects.filter(month__family=family).exists())
        self.assertIn("All local demo seeds completed", output.getvalue())

    def test_one_month_range_creates_current_month(self):
        self.run_seed("--months", "1")

        family = Family.objects.get(name=DEMO_FAMILY)
        self.assertEqual(family.month_set.count(), 1)

    def test_reset_deletes_only_demo_data(self):
        real_user = User.objects.create_user("real@example.com", password="safe-password")
        real_family = real_user.profile.family
        self.run_seed()

        self.run_seed("--reset")

        self.assertFalse(Family.objects.filter(name=DEMO_FAMILY).exists())
        self.assertFalse(User.objects.filter(username__in=DEMO_USERNAMES).exists())
        self.assertTrue(User.objects.filter(pk=real_user.pk).exists())
        self.assertTrue(Family.objects.filter(pk=real_family.pk).exists())

    @override_settings(DEBUG=False)
    def test_seed_is_blocked_outside_debug_without_explicit_opt_in(self):
        with self.assertRaisesMessage(CommandError, "Demo seeds are disabled"):
            self.run_seed()
