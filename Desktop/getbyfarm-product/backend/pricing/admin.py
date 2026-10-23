from django.contrib import admin

from .models import PriceHistory, SupplierPrice


@admin.register(SupplierPrice)
class SupplierPriceAdmin(admin.ModelAdmin):
    list_display = ("product", "supplier", "unit_price", "stock_quantity", "is_active", "updated_at")
    list_filter = ("is_active", "supplier")
    search_fields = ("product__name", "supplier__business_name")


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "supplier", "unit_price", "recorded_at")
    list_filter = ("product",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
