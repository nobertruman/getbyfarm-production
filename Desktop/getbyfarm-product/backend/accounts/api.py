"""Auth & account endpoints: register, me, throttled login, logout (refresh-token revocation)."""
from django.conf import settings
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from organizations.models import Branch, Country, Organization
from suppliers.models import SupplierOrganization, SupplierUser
from .models import Role, User


class ThrottledLoginView(TokenObtainPairView):
    throttle_scope = "login"


class ThrottledRefreshView(TokenRefreshView):
    throttle_scope = "login"


class RegisterSerializer(serializers.Serializer):
    account_type = serializers.ChoiceField(choices=["buyer", "supplier"])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    business_name = serializers.CharField(max_length=200)
    branch_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    operating_location = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value or None

    def validate(self, attrs):
        probe = User(email=attrs["email"], full_name=attrs["full_name"])
        try:
            password_validation.validate_password(attrs["password"], user=probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class RegisterView(APIView):
    """POST /api/auth/register/ — self-serve signup for a buyer business or a supplier.

    Buyers get an Organization + first Branch and the 'enterprise_admin' role (the owner can approve
    at every level, so single-person businesses are not blocked by the approval chain).
    Suppliers are created as 'pending' and are invisible to buyers until a platform admin verifies them.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        country = Country.objects.filter(code=settings.DEFAULT_COUNTRY_CODE, is_active=True).first()
        if country is None:
            return Response({"detail": "Service is not configured for signups yet."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        user = User(email=data["email"], full_name=data["full_name"], phone=data.get("phone"))
        user.set_password(data["password"])

        if data["account_type"] == "buyer":
            org = Organization.objects.create(name=data["business_name"], country=country)
            branch = Branch.objects.create(
                organization=org, name=data.get("branch_name") or "Main branch",
                address=data.get("operating_location", ""),
            )
            user.organization, user.branch = org, branch
            user.save()
            user.roles.add(Role.objects.get(code="enterprise_admin"))
        else:
            user.save()
            supplier = SupplierOrganization.objects.create(
                business_name=data["business_name"], country=country,
                operating_location=data.get("operating_location", ""),
            )
            SupplierUser.objects.create(user=user, supplier=supplier)
            user.roles.add(Role.objects.get(code="supplier_admin"))

        return Response({"detail": "Account created.", "email": user.email}, status=status.HTTP_201_CREATED)


def serialize_me(user: User) -> dict:
    supplier_user = getattr(user, "supplieruser", None)
    if user.is_staff:
        role = "admin"
    elif supplier_user:
        role = "supplier"
    else:
        role = "buyer"
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "roles": list(user.roles.values_list("code", flat=True)),
        "organization": {"id": str(user.organization_id), "name": user.organization.name} if user.organization_id else None,
        "branch": {"id": str(user.branch_id), "name": user.branch.name} if user.branch_id else None,
        "supplier": {
            "id": str(supplier_user.supplier_id),
            "business_name": supplier_user.supplier.business_name,
            "verification_status": supplier_user.supplier.verification_status,
        } if supplier_user else None,
    }


class MeView(APIView):
    """GET /api/auth/me/ — who am I, and which surface (buyer / supplier / admin) should I see?"""

    def get(self, request):
        return Response(serialize_me(request.user))


class LogoutView(APIView):
    """POST /api/auth/logout/ {refresh} — revokes the refresh token server-side."""

    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            pass  # already invalid/expired: the end state (unusable token) is what we want
        return Response(status=status.HTTP_204_NO_CONTENT)
