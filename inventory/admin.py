from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User

from .models import (
    Consumable,
    Equipment,
    Log,
    LowStockEmailDelivery,
    MSDSFile,
    MSDSSection,
    MSDSValidationResult,
    Project,
    Rack,
    Reagent,
    Rooms,
    Sample,
    Sample_Locations,
    Shelf,
    Box,
    Storages,
    TrashConsumable,
    TrashEquipment,
    TrashReagent,
    TrashSample,
    UserApplication,
    UserProfile,
)


admin.site.site_header = 'Flux administration'
admin.site.site_title = 'Flux admin'
admin.site.index_title = 'Institutional operations'


class FluxUserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_active',
        'is_staff',
        'last_login',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    list_per_page = 25


admin.site.unregister(User)
admin.site.register(User, FluxUserAdmin)


class FluxGroupAdmin(DjangoGroupAdmin):
    list_display = ('name', 'member_count')
    search_fields = ('name',)

    @admin.display(description='Users')
    def member_count(self, obj):
        return obj.user_set.count()


admin.site.unregister(Group)
admin.site.register(Group, FluxGroupAdmin)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'project_manager',
        'is_active',
        'low_stock_morning_time',
        'low_stock_evening_time',
        'created_at',
    )
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'project_manager__username', 'project_manager__email')
    filter_horizontal = ('project_editors', 'project_members')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 25
    list_select_related = ('project_manager',)


class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'product_code',
        'project',
        'pack_count',
        'threshold_value',
        'expiry_date',
        'is_active',
    )
    list_filter = ('project', 'is_active', 'cold_storage', 'expiry_date')
    search_fields = ('name', 'product_code', 'vendor', 'project__name')
    list_select_related = ('project',)
    list_per_page = 25
    date_hierarchy = 'expiry_date'


@admin.register(Consumable)
class ConsumableAdmin(InventoryItemAdmin):
    pass


@admin.register(Reagent)
class ReagentAdmin(InventoryItemAdmin):
    list_display = InventoryItemAdmin.list_display + ('hazard_level', 'country_of_origin')
    list_filter = InventoryItemAdmin.list_filter + ('hazard_level', 'country_of_origin')
    search_fields = InventoryItemAdmin.search_fields + ('country_of_origin',)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'equip_id',
        'project',
        'status',
        'next_calibration_date',
        'is_active',
    )
    list_filter = ('status', 'is_active', 'project')
    search_fields = ('name', 'equip_id', 'serial_num', 'project__name')
    list_select_related = ('project',)
    list_per_page = 25
    date_hierarchy = 'next_calibration_date'


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = (
        'sample_id',
        'sample_type',
        'project',
        'volume',
        'volume_unit',
        'collection_date',
        'is_active',
    )
    list_filter = ('sample_type', 'country', 'is_active', 'project')
    search_fields = ('sample_id', 'sample_type', 'country', 'project__name')
    list_select_related = ('project',)
    list_per_page = 25
    date_hierarchy = 'collection_date'


@admin.register(UserApplication)
class UserApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'first_name',
        'last_name',
        'email',
        'department',
        'workplace',
        'is_approved',
        'created_at',
    )
    list_filter = ('is_approved', 'department', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'department', 'workplace')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 25


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'phone_number', 'time_zone')
    list_filter = ('department', 'time_zone')
    search_fields = ('user__username', 'user__email', 'department', 'phone_number')
    filter_horizontal = ('managed_projects',)
    list_select_related = ('user',)


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'project', 'user', 'action')
    list_filter = ('project', 'timestamp')
    search_fields = ('action', 'user__username', 'project__name')
    readonly_fields = ('id', 'project', 'user', 'action', 'details', 'timestamp')
    date_hierarchy = 'timestamp'
    list_select_related = ('project', 'user')
    list_per_page = 50


@admin.register(LowStockEmailDelivery)
class LowStockEmailDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'project',
        'recipient',
        'scheduled_date',
        'scheduled_time',
        'attempt_count',
        'last_attempt_at',
        'sent_at',
    )
    list_filter = ('scheduled_date', 'scheduled_time', 'sent_at')
    search_fields = ('project__name', 'recipient__username', 'recipient__email', 'last_error')
    readonly_fields = (
        'project',
        'recipient',
        'scheduled_date',
        'scheduled_time',
        'attempt_count',
        'last_attempt_at',
        'sent_at',
        'last_error',
    )
    date_hierarchy = 'scheduled_date'
    list_select_related = ('project', 'recipient')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MSDSFile)
class MSDSFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'reagent', 'uploaded_by', 'scan_result', 'is_verified', 'upload_date')
    list_filter = ('scan_result', 'is_verified', 'upload_date')
    search_fields = ('original_filename', 'reagent__name', 'reagent__project__name', 'file_hash')
    readonly_fields = ('original_filename', 'file_size', 'file_hash', 'upload_date')
    list_select_related = ('reagent', 'uploaded_by', 'reagent__project')
    date_hierarchy = 'upload_date'


class DeletedRecordAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'project', 'deleted_at', 'deleted_by', 'deletion_reason')
    list_filter = ('project', 'deleted_at')
    search_fields = ('project__name', 'name', 'deletion_reason')
    date_hierarchy = 'deleted_at'
    list_select_related = ('project', 'deleted_by')


for model in (TrashConsumable, TrashReagent, TrashEquipment, TrashSample):
    admin.site.register(model, DeletedRecordAdmin)


for model in (
    MSDSSection,
    MSDSValidationResult,
    Box,
    Rack,
    Rooms,
    Sample_Locations,
    Shelf,
    Storages,
):
    admin.site.register(model)
