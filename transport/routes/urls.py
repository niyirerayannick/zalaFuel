from django.urls import path
from . import views

app_name = 'routes'

# Route management endpoints
urlpatterns = [
    path("", views.RouteListView.as_view(), name="list"),
    path("create/", views.RouteCreateView.as_view(), name="create"),
    path("<int:pk>/", views.RouteDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.RouteUpdateView.as_view(), name="edit"),
    
    # Route-specific analytics
    path("<int:pk>/profitability/", views.RouteDetailView.as_view(), name="profitability"),
    path("<int:pk>/analytics/", views.RouteDetailView.as_view(), name="analytics"),
    path("popular-routes/", views.RouteListView.as_view(), name="popular-routes"),
]