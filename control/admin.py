from django.contrib import admin
from .models import Department, AdminAudit, PortalSettings, AdminNotification


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(AdminAudit)
class AdminAuditAdmin(admin.ModelAdmin):
    list_display = ('happened_at', 'actor', 'action', 'target_type', 'target_id', 'summary')
    list_filter = ('action', 'target_type')
    search_fields = ('summary', 'action', 'actor__username')
    readonly_fields = ('actor', 'action', 'target_type', 'target_id', 'summary', 'changes', 'happened_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PortalSettings)
class PortalSettingsAdmin(admin.ModelAdmin):
    list_display = ('institution_name', 'currency', 'updated_at')


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'created_at', 'read_at')
    list_filter = ('created_at',)
    search_fields = ('recipient__username', 'title')
    readonly_fields = ('recipient', 'title', 'message', 'link', 'created_at', 'read_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
