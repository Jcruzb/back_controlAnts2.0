from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_expense_payer_recurringpayment_payer"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecurringPaymentOccurrence",
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
                        related_name="recurring_payment_occurrences",
                        to="core.month",
                    ),
                ),
                (
                    "recurring_payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="occurrences",
                        to="core.recurringpayment",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="recurringpaymentoccurrence",
            constraint=models.UniqueConstraint(
                fields=("recurring_payment", "month"),
                name="uniq_recurring_payment_occurrence_month",
            ),
        ),
        migrations.AddIndex(
            model_name="recurringpaymentoccurrence",
            index=models.Index(
                fields=["month", "recurring_payment"],
                name="idx_recurring_occ_month",
            ),
        ),
    ]
