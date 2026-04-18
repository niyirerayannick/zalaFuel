from django.db import models


class TimeStampedModel(models.Model):
    """Reusable timestamp mixin for audit trails."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
