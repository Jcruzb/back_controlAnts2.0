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
        unique_together = ('family', 'year', 'month')

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

class PlannedExpense(models.Model):
    month = models.ForeignKey(Month, on_delete=models.CASCADE, related_name="planned_expenses")
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=100, blank=True)  # opcional
    planned_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("month", "category")

    def __str__(self):
        return f"{self.month} - {self.category.name} ({self.planned_amount})"

class Expense(models.Model):
    month = models.ForeignKey(Month, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    planned_expense = models.ForeignKey(
        'PlannedExpense',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='expenses'
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
    
class RecurringPayment(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="recurring_payments"
    )
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_day = models.IntegerField()  # 1 - 31
    
    start_date = models.DateField()   # cuándo empieza
    end_date = models.DateField(null=True, blank=True) 
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if created:
        family = Family.objects.first()
        if family:
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

    def __str__(self):
        return f"{self.plan} - {self.planned_amount}"