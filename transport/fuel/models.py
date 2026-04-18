from django.db import models
from django.conf import settings
from transport.trips.models import Trip


class FuelStation(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class FuelRequest(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='trip_fuel_requests')
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    station = models.ForeignKey(FuelStation, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_trip_fuel_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_to_trip = models.BooleanField(default=False)
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Fuel request for {self.trip} by {self.driver}"

class FuelDocument(models.Model):
    fuel_request = models.ForeignKey(FuelRequest, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to='fuel_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document for {self.fuel_request}"
