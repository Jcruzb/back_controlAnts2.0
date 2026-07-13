from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_harden_budget_integrity"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannedExpenseOccurrence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_completed", models.BooleanField(default=False)),
                (
                    "month",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="planned_expense_occurrences",
                        to="core.month",
                    ),
                ),
                (
                    "planned_expense",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="occurrences",
                        to="core.plannedexpense",
                    ),
                ),
                (
                    "planned_expense_plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="occurrences",
                        to="core.plannedexpenseplan",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="plannedexpenseoccurrence",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        ("planned_expense__isnull", False),
                        ("planned_expense_plan__isnull", True),
                    )
                    | models.Q(
                        ("planned_expense__isnull", True),
                        ("planned_expense_plan__isnull", False),
                    )
                ),
                name="planned_occurrence_exactly_one_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="plannedexpenseoccurrence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("planned_expense__isnull", False)),
                fields=("planned_expense", "month"),
                name="uniq_legacy_planned_occurrence_month",
            ),
        ),
        migrations.AddConstraint(
            model_name="plannedexpenseoccurrence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("planned_expense_plan__isnull", False)),
                fields=("planned_expense_plan", "month"),
                name="uniq_plan_occurrence_month",
            ),
        ),
        migrations.AddIndex(
            model_name="plannedexpenseoccurrence",
            index=models.Index(
                fields=["month", "planned_expense"],
                name="idx_legacy_plan_occ_month",
            ),
        ),
        migrations.AddIndex(
            model_name="plannedexpenseoccurrence",
            index=models.Index(
                fields=["month", "planned_expense_plan"],
                name="idx_plan_occ_month",
            ),
        ),
    ]
