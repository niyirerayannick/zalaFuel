from django.db.models.signals import post_save
from django.dispatch import receiver

from transport.drivers.models import Driver
from transport.vehicles.models import Vehicle

from .models import Trip


@receiver(post_save, sender=Trip)
def update_assignment_statuses(sender, instance, **kwargs):
    if instance.status in {Trip.TripStatus.ASSIGNED, Trip.TripStatus.IN_TRANSIT}:
        if instance.vehicle.status != Vehicle.VehicleStatus.ASSIGNED:
            instance.vehicle.status = Vehicle.VehicleStatus.ASSIGNED
            instance.vehicle.save(update_fields=["status", "updated_at"])
        if instance.driver.status != Driver.DriverStatus.ASSIGNED:
            instance.driver.status = Driver.DriverStatus.ASSIGNED
            instance.driver.save(update_fields=["status", "updated_at"])

    if instance.status in {Trip.TripStatus.DELIVERED, Trip.TripStatus.COMPLETED, Trip.TripStatus.CLOSED}:
        if instance.vehicle.status != Vehicle.VehicleStatus.AVAILABLE:
            instance.vehicle.status = Vehicle.VehicleStatus.AVAILABLE
            instance.vehicle.save(update_fields=["status", "updated_at"])
        if instance.driver.status != Driver.DriverStatus.AVAILABLE:
            instance.driver.status = Driver.DriverStatus.AVAILABLE
            instance.driver.save(update_fields=["status", "updated_at"])
