from django.contrib import admin

from .models import Delivery, DeliveryPartner, DeliveryTracking


class TrackingInline(admin.TabularInline):
    model = DeliveryTracking
    extra = 0
    readonly_fields = ("status", "note", "recorded_at")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("order_allocation", "status", "delivered_at")
    list_filter = ("status",)
    inlines = [TrackingInline]


admin.site.register(DeliveryPartner)
