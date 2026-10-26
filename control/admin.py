from django.contrib import admin
from .models import Department, AdminAudit, PortalSettings, AdminNotification


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    list_select_related = ('head',)
    autocomplete_fields = ('head',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Department details', {'fields': ('name', 'code', 'head', 'is_active')}),
        ('About this department', {'fields': ('description',)}),
        ('Record history', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(AdminAudit)
class AdminAuditAdmin(admin.ModelAdmin):
    list_display = ('happened_at', 'actor', 'action', 'target_type', 'target_id', 'summary')
    list_filter = ('action', 'target_type')
    search_fields = ('summary', 'action', 'actor__username')
    readonly_fields = ('actor', 'action', 'target_type', 'target_id', 'summary', 'changes', 'happened_at')
    list_select_related = ('actor',)
    date_hierarchy = 'happened_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PortalSettings)
class PortalSettingsAdmin(admin.ModelAdmin):
    list_display = ('institution_name', 'currency', 'updated_at')
    readonly_fields = ('updated_at',)
    fieldsets = (
        ('Institutional identity', {'fields': ('institution_name', 'support_email')}),
        ('Reporting preferences', {'fields': ('currency', 'date_format')}),
        ('Record history', {'fields': ('updated_at',)}),
    )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not PortalSettings.objects.exists()


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'created_at', 'read_at')
    list_filter = ('created_at',)
    search_fields = ('recipient__username', 'title')
    readonly_fields = ('recipient', 'title', 'message', 'link', 'created_at', 'read_at')
    list_select_related = ('recipient',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
