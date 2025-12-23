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
    category = models.CharField(max_length=50)
    date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} - {self.category}"
    
class Category(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Expense(models.Model):
    month = models.ForeignKey(Month, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
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
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_day = models.IntegerField()  # 1 - 31
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