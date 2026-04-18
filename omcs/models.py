from django.db import models

from core.models import TimeStampedModel


class OMC(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=30, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

