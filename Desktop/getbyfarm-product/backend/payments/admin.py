from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Read-only ledger for reconciliation (check 'Amount mismatch' rows and cancelled-but-paid orders)."""
    list_display = ("order", "provider", "amount", "status", "provider_reference", "result_description", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("provider_reference", "order__order_number")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]
