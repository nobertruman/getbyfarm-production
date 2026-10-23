from django.contrib import admin

from .models import SupplierDocument, SupplierOrganization, SupplierUser


class DocumentInline(admin.TabularInline):
    model = SupplierDocument
    extra = 0


@admin.register(SupplierOrganization)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("business_name", "verification_status", "reliability_score", "quality_rating", "created_at")
    list_filter = ("verification_status",)
    search_fields = ("business_name", "kra_pin")
    inlines = [DocumentInline]
    # Status moves only through the app's verification workflow (/admin console), which enforces valid transitions.
    readonly_fields = ("verification_status", "payout_details")


admin.site.register(SupplierUser)
