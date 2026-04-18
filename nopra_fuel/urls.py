from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(_request):
    return JsonResponse({"status": "ok", "service": "zalaeco-energy-terminal"})


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("account/", include("allauth.urls")),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("terminal-operations/", include("terminals.urls")),
    path("tank-stocks/", include("tanks.urls")),
    path("product-receipts/", include("receipts.urls")),
    path("dispatches/", include("dispatches.urls")),
    path("omc-sales/", include("sales.urls")),
    path("revenue-analysis/", include("revenue.urls")),
    path("market-share/", include("analytics.urls")),
path("products/", include("products.urls")),
    path("omcs/", include("omcs.urls")),
    path("reports/", include("reports.urls")),
    path("monitoring/", include("monitoring.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
