from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, BranchViewSet

router = DefaultRouter()
router.register("orgs", OrganizationViewSet, basename="organization")
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = router.urls
