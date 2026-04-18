from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import Expense


def _sync_trip_expenses(trip):
    """Recalculate a trip's other_expenses from linked Expense records and save."""
    total = trip.expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    if trip.other_expenses != total:
        trip.other_expenses = total
        # Call full save() so Trip.recalculate_financials() updates
        # total_cost, profit, cost_per_km, revenue_per_km
        trip.save()


@receiver(pre_save, sender=Expense)
def expense_pre_save(sender, instance, **kwargs):
    """Stash the previous trip_id so we can sync the old trip after save."""
    if instance.pk:
        try:
            old = Expense.objects.filter(pk=instance.pk).values_list('trip_id', flat=True).first()
            instance._old_trip_id = old
        except Exception:
            instance._old_trip_id = None
    else:
        instance._old_trip_id = None


@receiver(post_save, sender=Expense)
def expense_saved(sender, instance, **kwargs):
    """When an expense is saved, sync totals back to its linked trip (and old trip if changed)."""
    from transport.trips.models import Trip

    # Sync the old trip if expense was moved to a different trip
    old_trip_id = getattr(instance, '_old_trip_id', None)
    if old_trip_id and old_trip_id != instance.trip_id:
        try:
            old_trip = Trip.objects.get(pk=old_trip_id)
            _sync_trip_expenses(old_trip)
        except Trip.DoesNotExist:
            pass

    # Sync the current trip
    if instance.trip_id:
        _sync_trip_expenses(instance.trip)


@receiver(post_delete, sender=Expense)
def expense_deleted(sender, instance, **kwargs):
    """When an expense is deleted, sync totals back to its linked trip."""
    if instance.trip_id:
        try:
            from transport.trips.models import Trip
            trip = Trip.objects.get(pk=instance.trip_id)
            _sync_trip_expenses(trip)
        except Trip.DoesNotExist:
            pass
