from django.contrib import admin

from .models import Branch, Country, Organization


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "currency_code", "default_tax_rate", "is_active")
    list_editable = ("is_active",)


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "subscription_tier", "created_at")
    list_filter = ("subscription_tier", "country")
    search_fields = ("name", "kra_pin")
    inlines = [BranchInline]
