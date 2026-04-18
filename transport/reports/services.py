from django.db.models import Sum
from django.db.models.functions import TruncMonth

from transport.trips.models import Trip


def monthly_profitability_report():
    return (
        Trip.objects.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(
            revenue=Sum("revenue"),
            fuel_cost=Sum("fuel_cost"),
            total_cost=Sum("total_cost"),
            profit=Sum("profit"),
        )
        .order_by("month")
    )
