from django.contrib import admin
from .models import Family, Profile, Month, Income, Expense, RecurringPayment, Category

admin.site.register(Family)
admin.site.register(Profile)
admin.site.register(Month)
admin.site.register(Income)
admin.site.register(Expense)
admin.site.register(RecurringPayment)
admin.site.register(Category)
