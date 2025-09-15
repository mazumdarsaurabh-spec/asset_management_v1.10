 #inventory_management/inventory/models.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid
from django.db import transaction
from datetime import date
from django.db.models import Max


from django.db.models import F

from decimal import Decimal

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100, null=False, blank=True)
    category_prefix = models.CharField(max_length=3, unique=True)

    def __str__(self):
        return self.name

class Location(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name

class ItemLocation(models.Model):
    """
    Represents a physical location where an inventory item can be stored.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Name of the storage location (e.g., 'Warehouse A', 'Office 3B')")

    def __str__(self):
        return self.name

class Item(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_name = models.CharField(max_length=200)
    description = models.TextField()

    def __str__(self):
        return self.item_name

class TechnicalData(models.Model):
    item = models.OneToOneField('InventoryItem', on_delete=models.CASCADE, primary_key=True,related_name='technical_data')

    host_name = models.CharField(max_length=255, blank=True, null=True)
    wifi_mac = models.CharField(max_length=17, blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    internet_source = models.CharField(max_length=255, blank=True, null=True)
    network = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    build = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')) 
    country = models.CharField(max_length=255, blank=True, null=True)
    os = models.CharField(max_length=255, blank=True, null=True)
    google_rd = models.CharField(max_length=255, blank=True, null=True)
    pin = models.CharField(max_length=255, blank=True, null=True)
    anydesk_id = models.CharField(max_length=255, blank=True, null=True)
    anydesk_password = models.CharField(max_length=255, blank=True, null=True)
    elevated_credential = models.CharField(max_length=255, blank=True, null=True)
    
    edit_agent_date = models.DateField(blank=True, null=True)
    last_belarc_update = models.DateField(blank=True, null=True)
    last_system_update = models.DateField(blank=True, null=True)

    known_issues = models.TextField(blank=True, null=True)
    pending_hw_replacements = models.TextField(blank=True, null=True)
    previous_hw_replacements = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Technical Data for {self.item.uid_no}"
    
class Project(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name
class ItemStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Item Statuses"

    def __str__(self):
        return self.name
    
class Status(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Statuses"


    

class ItemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Laptop, Monitor, Server")
    prefix = models.CharField(max_length=10, unique=True, help_text="Short prefix for UID (e.g., LAP, MON, SRV)")

    class Meta:
        verbose_name_plural = "Item Categories"

    def __str__(self):
        return self.name

class UIDCategorySequence(models.Model):
    category_prefix = models.CharField(max_length=10, unique=True, help_text="Matches ItemCategory prefix")
    year_month = models.CharField(max_length=4, help_text="Format YYMM, e.g., 2312 for Dec 2023")
    last_sequence_number = models.IntegerField(default=0, help_text="Last sequence number used for this category and month")

    class Meta:
        unique_together = ('category_prefix', 'year_month')
        verbose_name = "UID Category Sequence"
        verbose_name_plural = "UID Category Sequences"

    def __str__(self):
        return f"{self.category_prefix}-{self.year_month}: {self.last_sequence_number}"
    
class InventoryItem(models.Model):
    STATUS_CHOICES = [
        ('Offline', 'Offline'),
        ('Online', 'Online'),
        ('Assigned', 'Assigned'),
        ('In Transit', 'In Transit'),
    ]

    item_name = models.CharField(max_length=255)
    category = models.ForeignKey('ItemCategory', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    invoice_number = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    image = models.ImageField(upload_to='inventory_images/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Offline')
    uid_no = models.CharField(max_length=50, unique=True, editable=False, blank=True, null=True)
    serial_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')) 
    location = models.ForeignKey('Location', on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)
    cpu = models.CharField(max_length=100, blank=True, null=True)
    gpu = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)
    installed_software = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_items')
    last_transfer_date = models.DateField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="items_created")
    owner_poc = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['item_name']
        verbose_name_plural = "Inventory Items"

    def __str__(self):
        return f"{self.item_name} ({self.uid_no or self.serial_number or 'N/A'})"
    
    def is_in_kit(self):
        return self.kits.exists()
    
    def save(self, *args, **kwargs):
        # Generate a UID only if it's a new item and a UID has not been set yet.
        if not self.pk and not self.uid_no:
            # Check if a category is linked to the item
            if self.category:
                category_prefix = self.category.prefix
            else:
                # Fallback to a default prefix if no category is assigned
                category_prefix = "OTH"

            today_str = date.today().strftime('%y%m%d')
            prefix_with_date = f"{category_prefix}{today_str}"
            
            # Find the highest existing UID number for the day and category
            with transaction.atomic():
                max_uid = InventoryItem.objects.select_for_update().filter(
                    uid_no__startswith=prefix_with_date
                ).aggregate(max_uid=Max('uid_no'))

                latest_seq = 0
                if max_uid['max_uid']:
                    try:
                        # Extract the numeric part of the UID and convert to an integer
                        latest_seq = int(max_uid['max_uid'][-4:])
                    except (ValueError, IndexError):
                        # Reset sequence if the UID format is unexpected
                        latest_seq = 0
                
                # Increment the sequence number and format the new UID
                next_seq = latest_seq + 1
                self.uid_no = f"{prefix_with_date}{next_seq:04d}"

        super().save(*args, **kwargs)


class Kit(models.Model):
    name = models.CharField(max_length=255, unique=True)
    items = models.ManyToManyField('InventoryItem', related_name='kits')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    


class InventoryLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    uid_number = models.CharField(max_length=50, blank=True, null=True, help_text="UID of the item at the time of log")

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Inventory Logs"

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.user.username if self.user else 'N/A'} - {self.action} - {self.inventory_item.item_name if self.inventory_item else self.uid_number}"


class DocumentTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name






class InventoryDocument(models.Model):
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='documents')
    tag = models.ForeignKey(DocumentTag, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='item_document/')
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name