from rest_framework.routers import DefaultRouter

from .views import BuyerOrderViewSet, SupplierAllocationViewSet

router = DefaultRouter()
router.register("allocations", SupplierAllocationViewSet, basename="order-allocation")
router.register("", BuyerOrderViewSet, basename="order")

urlpatterns = router.urls
