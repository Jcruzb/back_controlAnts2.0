import uuid
from django.conf import settings
from django.db import models


class MovementProposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey('core.Family', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    movements = models.JSONField()
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class FamilyCategoryAlias(models.Model):
    family = models.ForeignKey('core.Family', on_delete=models.CASCADE)
    category = models.ForeignKey('core.Category', on_delete=models.CASCADE)
    alias = models.CharField(max_length=100)
    learned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['family', 'alias'], name='unique_family_category_alias')]
