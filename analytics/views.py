from django.views.generic import TemplateView

from accounts.mixins import ReportsRoleMixin

from .models import MarketShareSnapshot


class MarketShareDashboardView(ReportsRoleMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        latest_date = MarketShareSnapshot.objects.order_by("-snapshot_date").values_list("snapshot_date", flat=True).first()
        snapshots = MarketShareSnapshot.objects.filter(snapshot_date=latest_date).select_related("omc", "product") if latest_date else MarketShareSnapshot.objects.none()
        context.update(
            {
                "page_title": "Market Share",
                "active_menu": "market_share",
                "latest_date": latest_date,
                "snapshots": snapshots,
                "omc_ranking": snapshots.order_by("-market_share_percent", "-volume_liters"),
                "product_share": snapshots.values("product__name", "market_share_percent", "volume_liters").order_by("product__name"),
            }
        )
        return context

