from django.contrib import admin

from .models import Order, OrderAllocation, OrderItem, PurchaseApproval


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ItemInline(ReadOnlyInline):
    model = OrderItem


class AllocationInline(ReadOnlyInline):
    model = OrderAllocation


class ApprovalInline(ReadOnlyInline):
    model = PurchaseApproval


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Orders are evidence: staff can inspect them but not edit amounts or delete them."""
    list_display = ("order_number", "branch", "status", "total_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number",)
    inlines = [ItemInline, AllocationInline, ApprovalInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]
