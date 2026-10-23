from rest_framework import permissions, serializers, viewsets

from .models import Branch, Organization


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "organization", "name", "address", "latitude", "longitude", "monthly_budget", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"organization": {"required": False}}

    def validate_organization(self, org):
        user = self.context["request"].user
        if not user.is_staff and org.id != user.organization_id:
            raise serializers.ValidationError("You can only manage branches of your own organization.")
        return org


class OrganizationSerializer(serializers.ModelSerializer):
    branches = BranchSerializer(many=True, read_only=True)

    class Meta:
        model = Organization
        fields = ["id", "name", "country", "kra_pin", "registration_number", "subscription_tier", "branches", "created_at"]
        # Country is fixed at signup; the plan changes only through billing/admin, never by self-service PATCH.
        read_only_fields = ["id", "country", "subscription_tier", "created_at"]


class IsOrgOwnerForWrites(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS or user.is_staff:
            return True
        return bool(user.organization_id and user.roles.filter(code="enterprise_admin").exists())

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        org_id = obj.id if isinstance(obj, Organization) else obj.organization_id
        return org_id == request.user.organization_id


class OrganizationViewSet(viewsets.ModelViewSet):
    """Organizations are created at signup; here you can only read and edit your own."""
    serializer_class = OrganizationSerializer
    permission_classes = [IsOrgOwnerForWrites]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = Organization.objects.filter(deleted_at__isnull=True).prefetch_related("branches")
        return qs if self.request.user.is_staff else qs.filter(id=self.request.user.organization_id)


class BranchViewSet(viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [IsOrgOwnerForWrites]
    http_method_names = ["get", "post", "patch", "head", "options"]  # branches hold order history: no hard deletes

    def get_queryset(self):
        qs = Branch.objects.filter(deleted_at__isnull=True)
        return qs if self.request.user.is_staff else qs.filter(organization_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        if self.request.user.is_staff:
            serializer.save()
        else:
            serializer.save(organization_id=self.request.user.organization_id)
