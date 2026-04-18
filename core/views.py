from datetime import timedelta

from django.views.generic import TemplateView
from django.db.models import Sum, F
from django.utils import timezone

from accounts.mixins import OperationsRoleMixin
from accounts.station_access import (
    filter_fuel_sales_queryset_for_user,
    filter_shifts_queryset_for_user,
    filter_tanks_queryset_for_user,
    visible_stations,
)
from stations.models import Station, Pump
from inventory.models import FuelTank
from sales.models import FuelSale, ShiftSession


class DashboardView(OperationsRoleMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()
        user = self.request.user

        stations_qs = visible_stations(user)
        stations_count = stations_qs.count()
        st_ids = list(stations_qs.values_list("pk", flat=True))
        pumps_count = (
            Pump.objects.filter(station_id__in=st_ids).count()
            if st_ids
            else 0
        )
        tanks_scope = filter_tanks_queryset_for_user(FuelTank.objects.all(), user)
        tanks_count = tanks_scope.count()
        low_tanks = list(
            tanks_scope.filter(low_level_threshold__gt=0, current_volume_liters__lte=F("low_level_threshold"))
            .select_related("station")
            .order_by("current_volume_liters", "name")[:5]
        )
        shifts_scope = filter_shifts_queryset_for_user(ShiftSession.objects.all(), user)
        open_shifts = shifts_scope.filter(status=ShiftSession.Status.OPEN).count()
        shifts_count = shifts_scope.count()
        tanks_low = tanks_scope.filter(
            low_level_threshold__gt=0, current_volume_liters__lte=F("low_level_threshold")
        ).count()
        sales_scope = filter_fuel_sales_queryset_for_user(FuelSale.objects.all(), user)
        sales_today = sales_scope.filter(created_at__date=today).aggregate(s=Sum("total_amount"))["s"] or 0

        # 7-day sales trend (oldest -> newest)
        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            total = sales_scope.filter(created_at__date=day).aggregate(s=Sum("total_amount"))["s"] or 0
            trend.append({"day": day, "total": float(total)})
        sales_trend_max = max([point["total"] for point in trend], default=0) or 1

        recent_sales = sales_scope.select_related("shift__station", "attendant", "nozzle", "pump").order_by(
            "-created_at"
        )[:4]
        recent_shifts = shifts_scope.select_related("station", "attendant").order_by("-opened_at")[:4]

        context.update(
            {
                "page_title": "Fuel Dashboard",
                "active_menu": "dashboard",
                "highlights": {
                    "stations": stations_count,
                    "pumps": pumps_count,
                    "tanks": tanks_count,
                    "shifts": shifts_count,
                    "open_shifts": open_shifts,
                    "tanks_low": tanks_low,
                    "sales_today": float(sales_today),
                },
                "sales_trend": trend,
                "sales_trend_max": sales_trend_max,
                "low_tanks": low_tanks,
                "recent_sales": recent_sales,
                "recent_shifts": recent_shifts,
            }
        )
        return context
