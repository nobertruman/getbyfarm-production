from django.contrib import admin
from django.urls import include, path

from .health import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("django-admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/suppliers/", include("suppliers.urls")),
    path("api/catalog/", include("catalog.urls")),
    path("api/pricing/", include("pricing.urls")),
    path("api/procurement/", include("procurement.urls")),
    path("api/carts/", include("carts.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/invoices/", include("invoices.urls")),
    path("api/deliveries/", include("deliveries.urls")),
    path("api/analytics/", include("analytics.urls")),
]
