from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, SupplierAdminViewSet

router = DefaultRouter()
router.register("directory", SupplierViewSet, basename="supplier-directory")
router.register("admin", SupplierAdminViewSet, basename="supplier-admin")

urlpatterns = router.urls
