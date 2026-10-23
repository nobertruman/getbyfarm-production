from rest_framework.routers import DefaultRouter
from .views import SupplierPriceViewSet

router = DefaultRouter()
router.register("supplier-prices", SupplierPriceViewSet, basename="supplier-price")

urlpatterns = router.urls
