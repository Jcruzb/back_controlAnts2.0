from django.db import migrations


def migrate_planned_expenses_to_plans(apps, schema_editor):
    PlannedExpense = apps.get_model("core", "PlannedExpense")
    PlannedExpensePlan = apps.get_model("core", "PlannedExpensePlan")
    PlannedExpenseVersion = apps.get_model("core", "PlannedExpenseVersion")

    for pe in PlannedExpense.objects.all():
        plan = PlannedExpensePlan.objects.create(
            family=pe.family,
            category=pe.category,
            name=pe.name or pe.category.name,
            plan_type="ONE_MONTH",
            active=True,
            start_month=pe.month,
            end_month=pe.month,
            created_by=pe.created_by,
        )

        PlannedExpenseVersion.objects.create(
            plan=plan,
            planned_amount=pe.planned_amount,
            valid_from=pe.month,
            valid_to=pe.month,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_plannedexpenseplan_plannedexpenseversion"),
    ]

    operations = [
        migrations.RunPython(migrate_planned_expenses_to_plans),
    ]