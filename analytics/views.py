from django.db.models import Sum
from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.core.paginator import Paginator

from accounts.mixins import ReportsRoleMixin

from .models import MarketShareSnapshot


class MarketShareDashboardView(ReportsRoleMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_queryset(self):
        snapshot_date = self.request.GET.get("date") or MarketShareSnapshot.objects.order_by("-snapshot_date").values_list("snapshot_date", flat=True).first()
        product_filter = self.request.GET.get("product") or ""
        omc_filter = self.request.GET.get("omc") or ""

        snapshots = MarketShareSnapshot.objects.filter(snapshot_date=snapshot_date).select_related("omc", "product")

        if product_filter:
            snapshots = snapshots.filter(product_id=product_filter)
        if omc_filter:
            snapshots = snapshots.filter(omc_id=omc_filter)

        return snapshots.order_by("-market_share_percent", "-volume_liters")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        latest_date = MarketShareSnapshot.objects.order_by("-snapshot_date").values_list("snapshot_date", flat=True).first()
        all_snapshots = MarketShareSnapshot.objects.filter(snapshot_date=latest_date).select_related("omc", "product") if latest_date else MarketShareSnapshot.objects.none()

        total_volume = all_snapshots.aggregate(total=Sum("volume_liters"))["total"] or 0
        total_revenue = all_snapshots.aggregate(total=Sum("revenue_amount"))["total"] or 0

        top_by_volume = all_snapshots.order_by("-volume_liters").first()
        top_by_revenue = all_snapshots.order_by("-revenue_amount").first()
        active_omcs = all_snapshots.values("omc").distinct().count()

        snapshots = self.get_queryset()

        omc_ranking = snapshots.order_by("-market_share_percent", "-volume_liters")

        product_share = snapshots.values(
            "product__product_name"
        ).annotate(
            total_volume=Sum("volume_liters"),
            total_revenue=Sum("revenue_amount")
        ).order_by("-total_volume")

        context.update(
            {
                "page_title": "Market Share",
                "active_menu": "market_share",
                "latest_date": latest_date,
                "snapshots": snapshots,
                "omc_ranking": omc_ranking,
                "product_share": product_share,
                "kpi_total_volume": total_volume,
                "kpi_total_revenue": total_revenue,
                "kpi_top_volume_omc": top_by_volume.omc.name if top_by_volume else "-",
                "kpi_top_revenue_omc": top_by_revenue.omc.name if top_by_revenue else "-",
                "kpi_active_omcs": active_omcs,
                "filters": {
                    "date": self.request.GET.get("date", ""),
                    "product": self.request.GET.get("product", ""),
                    "omc": self.request.GET.get("omc", ""),
                },
            }
        )
        return context

