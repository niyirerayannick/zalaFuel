from django.urls import path
from . import views

app_name = 'customers' 

# Customer management endpoints
urlpatterns = [
    path("", views.CustomerListView.as_view(), name="list"),
    path("export/pdf/", views.CustomerPdfExportView.as_view(), name="export-pdf"),
    path("export/excel/", views.CustomerExcelExportView.as_view(), name="export-excel"),
    path("create/", views.CustomerCreateView.as_view(), name="create"), 
    path("<int:pk>/", views.CustomerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CustomerUpdateView.as_view(), name="edit"),
    path("<int:customer_id>/status/", views.customer_quick_status, name="status-update"),
    
    # Customer-specific routes
    path("<int:pk>/trips/", views.CustomerDetailView.as_view(), name="trip-history"),
    path("<int:pk>/payments/", views.CustomerDetailView.as_view(), name="payment-history"),
    path("<int:pk>/balance/", views.CustomerDetailView.as_view(), name="outstanding-balance"),
    path("outstanding-balances/", views.CustomerListView.as_view(), name="outstanding-balances"),
]
