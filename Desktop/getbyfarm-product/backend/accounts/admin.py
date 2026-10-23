from django.contrib import admin

from .models import Permission, Role, RolePermission, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "organization", "is_active", "is_staff", "created_at")
    list_filter = ("is_active", "is_staff", "roles")
    search_fields = ("email", "full_name", "phone")
    filter_horizontal = ("roles",)
    # Passwords are never edited here (hash would be shown/overwritten). Users sign up via the app;
    # create platform staff with `manage.py createsuperuser`.
    exclude = ("password", "groups", "user_permissions")
    readonly_fields = ("last_login", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(RolePermission)
