from django.urls import path

from .views import AdminOverviewView, BuyerDashboardView, SupplierDashboardView

urlpatterns = [
    path("buyer-dashboard/", BuyerDashboardView.as_view(), name="buyer-dashboard"),
    path("supplier-dashboard/", SupplierDashboardView.as_view(), name="supplier-dashboard"),
    path("admin-overview/", AdminOverviewView.as_view(), name="admin-overview"),
]
