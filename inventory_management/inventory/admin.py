# inventory_management/inventory/admin.py

from django.contrib import admin
from .models import InventoryItem, Location, Project, InventoryLog, UIDCategorySequence, Document, ItemCategory # Import ItemCategory

# Register your models here.

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'contact_person', 'phone_number')
    search_fields = ('name', 'address')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    search_fields = ('name',)
    list_filter = ('start_date', 'end_date')

# Register ItemCategory model
@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'prefix')
    search_fields = ('name', 'prefix')
    ordering = ('name',)

# Register UIDCategorySequence model
@admin.register(UIDCategorySequence)
class UIDCategorySequenceAdmin(admin.ModelAdmin):
    list_display = ('category_prefix', 'year_month', 'last_sequence_number')
    search_fields = ('category_prefix', 'year_month')
    list_filter = ('year_month',)
    readonly_fields = ('last_sequence_number',) # Sequence number is auto-managed

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    # Added 'category' to list_display
    list_display = (
        'item_name', 'uid_no', 'serial_number', 'category', 'quantity', 
        'location', 'status', 'project', 'created_by', 'created_at', 'updated_at'
    )
    # Added 'category' to list_filter and search_fields
    list_filter = ('status', 'location', 'project', 'category') 
    search_fields = (
        'item_name', 'uid_no', 'serial_number', 'description', 
        'location__name', 'project__name', 'category__name' # Search by category name
    )
    date_hierarchy = 'created_at'
    ordering = ('item_name',)
    
    # Customize fields displayed in the add/change form
    fieldsets = (
        (None, {
            'fields': ('item_name', 'category', 'uid_no', 'serial_number', 'quantity', 'image')
        }),
        ('Location & Status', {
            'fields': ('location', 'project', 'status', 'last_transfer_date')
        }),
        ('Specifications', {
            'fields': ('cpu', 'gpu', 'os', 'installed_software', 'description'),
            'classes': ('collapse',), # Makes this section collapsible
        }),
        ('Audit Info', {
            'fields': ('created_by',), # 'created_at', 'updated_at' are usually readonly
            'classes': ('collapse',),
        }),
    )
    
    # Make uid_no, created_by, created_at, updated_at readonly
    readonly_fields = ('uid_no', 'created_by', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change: # Only set created_by when the object is first created
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

        
@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'inventory_item', 'uid_number', 'action', 'details_short')
    list_filter = ('action', 'user', 'timestamp')
    search_fields = ('details', 'inventory_item__item_name', 'uid_number', 'user__username')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    def details_short(self, obj):
        return obj.details[:75] + '...' if len(obj.details) > 75 else obj.details
    details_short.short_description = 'Details'

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'inventory_item', 'uploaded_by', 'uploaded_at', 'file_link')
    list_filter = ('inventory_item', 'uploaded_by')
    search_fields = ('name', 'inventory_item__item_name', 'description')
    readonly_fields = ('uploaded_at', 'uploaded_by')

    def file_link(self, obj):
        if obj.file:
            return f'<a href="{obj.file.url}" target="_blank">Download File</a>'
        return "No file"
    file_link.allow_tags = True
    file_link.short_description = 'File'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

