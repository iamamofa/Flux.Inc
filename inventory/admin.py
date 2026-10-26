from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import Count

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

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(flux_member_count=Count('user', distinct=True))

    @admin.display(description='Users')
    def member_count(self, obj):
        return obj.flux_member_count


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
    autocomplete_fields = ('project_manager',)
    fieldsets = (
        ('Project details', {
            'fields': ('name', 'is_active', 'project_manager'),
            'description': 'Set the project name, status, and responsible manager.',
        }),
        ('Team & access', {
            'fields': ('project_editors', 'project_members'),
            'description': 'Editors have full project access. Members have limited access.',
        }),
        ('Low-stock notification schedule', {
            'fields': ('low_stock_morning_time', 'low_stock_evening_time'),
        }),
        ('Record history', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


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
    autocomplete_fields = ('project',)

    def get_fieldsets(self, request, obj=None):
        sections = [
            ('Record details', ('name', 'product_code', 'project', 'is_active')),
            ('Stock & replenishment', ('pack_count', 'items_per_pack', 'items_left_in_pack', 'threshold_value')),
            ('Storage & shelf life', ('storage_location', 'cold_storage', 'oem_temperature', 'temperature_unit', 'expiry_date')),
            ('Supplier & safety', ('vendor', 'country_of_origin', 'hazard_level')),
            ('Additional notes', ('notes',)),
        ]
        field_names = {field.name for field in self.model._meta.fields}
        return [(title, {'fields': tuple(name for name in names if name in field_names)})
                for title, names in sections if any(name in field_names for name in names)]


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
    autocomplete_fields = ('project',)
    fieldsets = (
        ('Equipment details', {'fields': ('name', 'equip_id', 'serial_num', 'project', 'quantity', 'status', 'is_active')}),
        ('Location & installation', {'fields': ('storage_location', 'date_installed', 'operating_temperature')}),
        ('Source & support', {'fields': ('source', 'donated_by', 'warranty_end_date', 'service_contract_start', 'service_contract_end')}),
        ('Calibration schedule', {'fields': ('last_calibration_date', 'next_calibration_date')}),
        ('Additional notes', {'fields': ('notes',)}),
    )


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
    autocomplete_fields = ('project',)
    fieldsets = (
        ('Sample identity', {'fields': ('sample_id', 'sample_type', 'project', 'country', 'collection_date', 'is_active')}),
        ('Quantity & concentration', {'fields': ('volume', 'volume_unit', 'concentration', 'concentration_unit', 'threshold_value')}),
        ('Additional notes', {'fields': ('notes',)}),
    )


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
    fieldsets = (
        ('Applicant details', {'fields': ('first_name', 'last_name', 'email')}),
        ('Institution & review', {'fields': ('workplace', 'department', 'id_image', 'is_approved')}),
        ('Record history', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'phone_number', 'time_zone')
    list_filter = ('department', 'time_zone')
    search_fields = ('user__username', 'user__email', 'department', 'phone_number')
    filter_horizontal = ('managed_projects',)
    list_select_related = ('user',)
    autocomplete_fields = ('user',)
    fieldsets = (
        ('Member information', {'fields': ('user', 'department', 'phone_number', 'time_zone')}),
        ('Profile details', {'fields': ('profile_picture', 'bio')}),
        ('Project assignments', {'fields': ('managed_projects',)}),
    )


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'project', 'user', 'action')
    list_filter = ('project', 'timestamp')
    search_fields = ('action', 'user__username', 'project__name')
    readonly_fields = ('id', 'project', 'user', 'action', 'details', 'timestamp')
    date_hierarchy = 'timestamp'
    list_select_related = ('project', 'user')
    list_per_page = 50

    def has_add_permission(self, request):
        return False


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

    def get_search_fields(self, request):
        identifier = 'sample_id' if self.model is TrashSample else 'name'
        return ('project__name', identifier, 'deletion_reason')


for model in (TrashConsumable, TrashReagent, TrashEquipment, TrashSample):
    admin.site.register(model, DeletedRecordAdmin)


@admin.register(Rooms)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_name', 'building')
    search_fields = ('room_name', 'building', 'notes')
    list_filter = ('building',)
    ordering = ('building', 'room_name')


@admin.register(Storages)
class StorageAdmin(admin.ModelAdmin):
    list_display = ('storage_name', 'storage_type', 'room_id', 'temperature', 'temperature_unit')
    search_fields = ('storage_name', 'storage_type', 'room_id__room_name', 'room_id__building')
    list_filter = ('storage_type', 'temperature_unit')
    list_select_related = ('room_id',)
    autocomplete_fields = ('room_id',)


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ('shelf_label', 'project', 'storage', 'capacity')
    search_fields = ('shelf_label', 'project__name', 'storage__storage_name')
    list_filter = ('project',)
    list_select_related = ('project', 'storage')
    autocomplete_fields = ('project', 'storage', 'project_manager')


@admin.register(Rack)
class RackAdmin(admin.ModelAdmin):
    list_display = ('rack_label', 'project', 'shelf', 'capacity')
    search_fields = ('rack_label', 'project__name', 'shelf__shelf_label')
    list_filter = ('project',)
    list_select_related = ('project', 'shelf')
    autocomplete_fields = ('project', 'shelf', 'project_manager')


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = ('box_label', 'project', 'rack', 'row_count', 'column_count')
    search_fields = ('box_label', 'project__name', 'rack__rack_label')
    list_filter = ('project',)
    list_select_related = ('project', 'rack')
    autocomplete_fields = ('project', 'rack', 'project_manager')


@admin.register(Sample_Locations)
class SampleLocationAdmin(admin.ModelAdmin):
    list_display = ('sample', 'box', 'well_id', 'moved_in_at', 'moved_out_at')
    search_fields = ('sample__sample_id', 'box__box_label', 'well_id')
    list_filter = ('moved_in_at', 'moved_out_at')
    list_select_related = ('sample', 'box')
    autocomplete_fields = ('sample', 'box')


@admin.register(MSDSSection)
class SafetySectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'required', 'order')
    list_filter = ('required',)
    search_fields = ('name', 'description', 'keywords')
    ordering = ('order', 'name')


@admin.register(MSDSValidationResult)
class SafetyValidationAdmin(admin.ModelAdmin):
    list_display = ('msds_file', 'section', 'found', 'match_quality')
    list_filter = ('found', 'section')
    search_fields = ('msds_file__original_filename', 'section__name', 'extracted_text')
    list_select_related = ('msds_file', 'section')
    autocomplete_fields = ('msds_file', 'section')
