from rest_framework.routers import DefaultRouter
from .views import DeliveryViewSet, DeliveryPartnerViewSet

router = DefaultRouter()
router.register("partners", DeliveryPartnerViewSet, basename="delivery-partner")
router.register("", DeliveryViewSet, basename="delivery")

urlpatterns = router.urls
