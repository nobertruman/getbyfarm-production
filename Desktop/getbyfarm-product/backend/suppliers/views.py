from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import SupplierDocument, SupplierOrganization

# New suppliers have no order history, so the scoring engine would rank them last forever.
# When an admin verifies a supplier we start unrated suppliers at a neutral prior (overridable per call)
# instead. Real scores from delivery history replace this in Phase 2.
NEUTRAL_RELIABILITY = 70
NEUTRAL_QUALITY = 3.0


class SupplierDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierDocument
        fields = ["id", "document_type", "file_url", "uploaded_at", "verified_at"]
        read_only_fields = ["id", "uploaded_at", "verified_at"]


class SupplierPublicSerializer(serializers.ModelSerializer):
    """What buyers see: no payout details, no KRA PIN, no registration number."""

    class Meta:
        model = SupplierOrganization
        fields = ["id", "business_name", "operating_location", "reliability_score", "quality_rating"]


class SupplierAdminSerializer(serializers.ModelSerializer):
    documents = SupplierDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierOrganization
        fields = ["id", "business_name", "country", "kra_pin", "registration_number", "operating_location",
                  "verification_status", "reliability_score", "quality_rating", "on_time_delivery_rate",
                  "documents", "created_at"]
        # Status and scores change only through the audited actions below, never by a bare PATCH.
        read_only_fields = ["id", "verification_status", "reliability_score", "quality_rating",
                            "on_time_delivery_rate", "created_at"]


class IsPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    """Buyer-facing directory: verified suppliers only."""
    queryset = SupplierOrganization.objects.filter(deleted_at__isnull=True, verification_status="verified").order_by("business_name")
    serializer_class = SupplierPublicSerializer


class SupplierAdminViewSet(viewsets.ModelViewSet):
    """Platform-admin only. Verification follows the enforced state machine in SupplierOrganization."""
    queryset = SupplierOrganization.objects.filter(deleted_at__isnull=True).prefetch_related("documents").order_by("created_at")
    serializer_class = SupplierAdminSerializer
    permission_classes = [IsPlatformAdmin]
    filterset_fields = ["verification_status"]
    http_method_names = ["get", "patch", "post", "head", "options"]  # no deletes, no creates via API

    def _transition(self, request, new_status):
        supplier = self.get_object()
        try:
            supplier.transition_status(new_status)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return supplier

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        result = self._transition(request, "under_review")
        return result if isinstance(result, Response) else Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        result = self._transition(request, "verified")
        if isinstance(result, Response):
            return result
        update = []
        if result.reliability_score == 0:
            result.reliability_score = request.data.get("reliability_score", NEUTRAL_RELIABILITY)
            update.append("reliability_score")
        if result.quality_rating == 0:
            result.quality_rating = request.data.get("quality_rating", NEUTRAL_QUALITY)
            update.append("quality_rating")
        if update:
            result.save(update_fields=update)
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        result = self._transition(request, "rejected")
        return result if isinstance(result, Response) else Response(self.get_serializer(result).data)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        result = self._transition(request, "suspended")
        return result if isinstance(result, Response) else Response(self.get_serializer(result).data)
