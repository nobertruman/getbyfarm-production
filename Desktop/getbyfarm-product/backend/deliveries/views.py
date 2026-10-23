from rest_framework import mixins, permissions, serializers, viewsets

from .models import Delivery, DeliveryPartner, DeliveryTracking


class DeliveryTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryTracking
        fields = ["id", "status", "note", "recorded_at"]


class DeliverySerializer(serializers.ModelSerializer):
    tracking_events = DeliveryTrackingSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="order_allocation.supplier.business_name", read_only=True)
    order_number = serializers.CharField(source="order_allocation.order.order_number", read_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "order_number", "supplier_name", "delivery_address", "scheduled_start", "scheduled_end",
                  "status", "proof_of_delivery_url", "delivered_at", "tracking_events"]
        read_only_fields = fields


class DeliveryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only tracking for buyers (their branch), suppliers (their own) and staff. Delivery records are
    created and advanced by the supplier's fulfilment actions (orders.services.advance_allocation), so a
    buyer can never mark their own order 'delivered'. Courier-partner integrations are Phase 3.
    """
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status"]

    def get_queryset(self):
        user = self.request.user
        qs = (Delivery.objects.select_related("order_allocation__order", "order_allocation__supplier")
              .prefetch_related("tracking_events").order_by("-id"))
        if user.is_staff:
            return qs
        su = getattr(user, "supplieruser", None)
        if su:
            return qs.filter(order_allocation__supplier_id=su.supplier_id)
        return qs.filter(order_allocation__order__branch_id=user.branch_id)


class DeliveryPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPartner
        fields = ["id", "name", "is_internal"]


class DeliveryPartnerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryPartner.objects.all()
    serializer_class = DeliveryPartnerSerializer
    permission_classes = [permissions.IsAdminUser]
