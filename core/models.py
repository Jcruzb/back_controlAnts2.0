from django.db import models

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver



class Family(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20,
        choices=[
            ('admin', 'Admin'),
            ('member', 'Member'),
        ],
        default='member'
    )

    def __str__(self):
        return f"{self.user.username} ({self.family.name})"
    
class Month(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()  # 1 - 12
    is_closed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['family', 'year', 'month'], name='uniq_family_year_month'),
            models.CheckConstraint(check=models.Q(month__gte=1, month__lte=12), name='month_between_1_and_12'),
            models.CheckConstraint(check=models.Q(year__gte=1, year__lte=9999), name='year_between_1_and_9999'),
        ]

    def __str__(self):
        return f"{self.family.name} - {self.month}/{self.year}"
    
class Income(models.Model):
    month = models.ForeignKey(Month, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey('Category', on_delete=models.PROTECT)

    # Optional link to a plan (for salaries / recurring planned incomes)
    income_plan = models.ForeignKey(
        'IncomePlan',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_incomes'
    )

    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='income_amount_positive'),
            models.UniqueConstraint(
                fields=['month', 'income_plan'],
                condition=models.Q(income_plan__isnull=False),
                name='uniq_income_per_month_per_income_plan',
            )
        ]
        indexes = [
            models.Index(fields=['month', 'income_plan'], name='idx_income_month_plan'),
        ]

    def __str__(self):
        return f"{self.amount} - {self.category}"
    

class IncomePlan(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    category = models.ForeignKey('Category', on_delete=models.PROTECT)

    name = models.CharField(max_length=100, blank=True)

    PLAN_TYPE_CHOICES = [
        ("ONE_MONTH", "Sólo un mes"),
        ("ONGOING", "Mantener en el tiempo"),
    ]
    plan_type = models.CharField(
        max_length=10,
        choices=PLAN_TYPE_CHOICES
    )

    # Optional: helps UX suggest a default date inside the month
    due_day = models.IntegerField(null=True, blank=True)  # 1 - 31

    active = models.BooleanField(default=True)

    start_month = models.ForeignKey(
        Month,
        on_delete=models.PROTECT,
        related_name="income_plans_starting"
    )
    end_month = models.ForeignKey(
        Month,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="income_plans_ending"
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        label = self.name or self.category.name
        return f"{label} ({self.plan_type})"

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(due_day__isnull=True) | models.Q(due_day__gte=1, due_day__lte=31),
                name='income_plan_due_day_valid',
            )
        ]


class IncomePlanVersion(models.Model):
    plan = models.ForeignKey(
        IncomePlan,
        related_name="versions",
        on_delete=models.CASCADE
    )

    planned_amount = models.DecimalField(max_digits=10, decimal_places=2)

    valid_from = models.ForeignKey(
        Month,
        on_delete=models.PROTECT,
        related_name="income_versions_from"
    )
    valid_to = models.ForeignKey(
        Month,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="income_versions_to"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["valid_from"]
        constraints = [
            models.CheckConstraint(check=models.Q(planned_amount__gt=0), name='income_version_amount_positive'),
        ]

    def __str__(self):
        label = self.plan.name or self.plan.category.name
        return f"{label} - {self.planned_amount}"
    
class Category(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default="#64748b")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['family', 'name'], name='uniq_category_name_per_family'),
        ]

class PlannedExpense(models.Model):
    month = models.ForeignKey(Month, on_delete=models.CASCADE, related_name="planned_expenses")
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=100, blank=True)  # opcional
    planned_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["month", "category"], name='uniq_planned_month_category'),
            models.CheckConstraint(check=models.Q(planned_amount__gt=0), name='planned_expense_amount_positive'),
        ]

    def __str__(self):
        return f"{self.month} - {self.category.name} ({self.planned_amount})"

class Expense(models.Model):
    month = models.ForeignKey(Month, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payer = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="paid_expenses",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    planned_expense = models.ForeignKey(
        'PlannedExpense',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='expenses'
    )

    planned_expense_plan = models.ForeignKey(
        'PlannedExpensePlan',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='expenses',
    )

    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)

    recurring_payment = models.ForeignKey(
        'RecurringPayment',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_expenses'
    )
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} - {self.category}"

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='expense_amount_positive'),
        ]
    
class RecurringPayment(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="recurring_payments"
    )
    payer = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recurring_payments_paid",
    )
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_day = models.IntegerField()  # 1 - 31
    
    start_date = models.DateField()   # cuándo empieza
    end_date = models.DateField(null=True, blank=True) 
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='recurring_amount_positive'),
            models.CheckConstraint(check=models.Q(due_day__gte=1, due_day__lte=31), name='recurring_due_day_valid'),
        ]


class RecurringPaymentOccurrence(models.Model):
    """Monthly instance of a recurring payment.

    Expenses remain the real money movements. This model stores the user's
    explicit decision to close that month's obligation.
    """

    recurring_payment = models.ForeignKey(
        RecurringPayment,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    month = models.ForeignKey(
        Month,
        on_delete=models.CASCADE,
        related_name="recurring_payment_occurrences",
    )
    is_completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recurring_payment", "month"],
                name="uniq_recurring_payment_occurrence_month",
            )
        ]
        indexes = [
            models.Index(
                fields=["month", "recurring_payment"],
                name="idx_recurring_occ_month",
            )
        ]

    def __str__(self):
        return f"{self.recurring_payment.name} - {self.month}"
    
@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if created:
        family = Family.objects.create(name=f"Familia de {instance.username}")
        Profile.objects.create(
            user=instance,
            family=family,
            role='member'
        )


# Planned expense redesign models
class PlannedExpensePlan(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    name = models.CharField(max_length=100, blank=True)

    PLAN_TYPE_CHOICES = [
        ("ONE_MONTH", "Sólo un mes"),
        ("ONGOING", "Mantener en el tiempo"),
    ]
    plan_type = models.CharField(
        max_length=10,
        choices=PLAN_TYPE_CHOICES
    )

    active = models.BooleanField(default=True)

    start_month = models.ForeignKey(
        Month,
        on_delete=models.PROTECT,
        related_name="planned_plans_starting"
    )
    end_month = models.ForeignKey(
        Month,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="planned_plans_ending"
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category.name} ({self.plan_type})"


class PlannedExpenseVersion(models.Model):
    plan = models.ForeignKey(
        PlannedExpensePlan,
        related_name="versions",
        on_delete=models.CASCADE
    )

    planned_amount = models.DecimalField(max_digits=10, decimal_places=2)

    valid_from = models.ForeignKey(
        Month,
        on_delete=models.PROTECT,
        related_name="planned_versions_from"
    )
    valid_to = models.ForeignKey(
        Month,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="planned_versions_to"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["valid_from"]
        constraints = [
            models.CheckConstraint(check=models.Q(planned_amount__gt=0), name='planned_version_amount_positive'),
        ]

    def __str__(self):
        return f"{self.plan} - {self.planned_amount}"


class PlannedExpenseOccurrence(models.Model):
    """Monthly completion state for either planned-expense system."""

    planned_expense = models.ForeignKey(
        PlannedExpense,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    planned_expense_plan = models.ForeignKey(
        PlannedExpensePlan,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    month = models.ForeignKey(
        Month,
        on_delete=models.CASCADE,
        related_name="planned_expense_occurrences",
    )
    is_completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        planned_expense__isnull=False,
                        planned_expense_plan__isnull=True,
                    )
                    | models.Q(
                        planned_expense__isnull=True,
                        planned_expense_plan__isnull=False,
                    )
                ),
                name="planned_occurrence_exactly_one_source",
            ),
            models.UniqueConstraint(
                fields=["planned_expense", "month"],
                condition=models.Q(planned_expense__isnull=False),
                name="uniq_legacy_planned_occurrence_month",
            ),
            models.UniqueConstraint(
                fields=["planned_expense_plan", "month"],
                condition=models.Q(planned_expense_plan__isnull=False),
                name="uniq_plan_occurrence_month",
            ),
        ]
        indexes = [
            models.Index(fields=["month", "planned_expense"], name="idx_legacy_plan_occ_month"),
            models.Index(fields=["month", "planned_expense_plan"], name="idx_plan_occ_month"),
        ]

    def __str__(self):
        source = self.planned_expense or self.planned_expense_plan
        return f"{source} - {self.month}"


class CreditAccount(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class FinancedPurchase(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    credit_account = models.ForeignKey(CreditAccount, null=True, blank=True, on_delete=models.PROTECT)
    purchase_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    installment_count = models.PositiveSmallIntegerField()
    first_due_date = models.DateField()
    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(total_amount__gt=0), name='financing_total_positive'), models.CheckConstraint(check=models.Q(installment_count__gte=1, installment_count__lte=360), name='financing_count_range')]


class FinancingInstallment(models.Model):
    purchase = models.ForeignKey(FinancedPurchase, related_name='installments', on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['purchase', 'number'], name='unique_financing_installment'), models.CheckConstraint(check=models.Q(amount__gt=0), name='financing_installment_positive')]


class FinancingPayment(models.Model):
    installment = models.ForeignKey(FinancingInstallment, related_name='payments', on_delete=models.PROTECT)
    expense = models.OneToOneField(Expense, related_name='financing_payment', on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['installment', 'idempotency_key'], name='unique_financing_payment_key')]
