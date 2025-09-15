 #inventory_management/inventory/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Assuming you have these models already, or similar structures:
class Location(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name

class Project(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name

# --- Ensure ItemCategory is defined correctly ---
class ItemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Laptop, Monitor, Server")
    prefix = models.CharField(max_length=10, unique=True, help_text="Short prefix for UID (e.g., LAP, MON, SRV)")
    # Add any other fields relevant to your categories

    class Meta:
        verbose_name_plural = "Item Categories"

    def __str__(self):
        return self.name

# --- Ensure UIDCategorySequence is defined correctly ---
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
    # Corrected: Use string literal 'ItemCategory' for ForeignKey to resolve NameError
    category = models.ForeignKey('ItemCategory', on_delete=models.SET_NULL, null=True, blank=True) 
    uid_no = models.CharField(max_length=50, unique=True, blank=True, null=True) # Auto-generated
    serial_number = models.CharField(max_length=255, unique=True, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    description = models.TextField(blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='inventory_images/', blank=True, null=True)
    
    # Hardware/Software specific fields
    cpu = models.CharField(max_length=100, blank=True, null=True)
    gpu = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)
    installed_software = models.TextField(blank=True, null=True)

    # Timestamps and creator
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_items')
    
    # New field for transfer date
    last_transfer_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['item_name']
        verbose_name_plural = "Inventory Items"

    def __str__(self):
        return f"{self.item_name} ({self.uid_no or self.serial_number or 'N/A'})"

class InventoryLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100) # e.g., 'added', 'updated', 'deleted', 'transferred'
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    uid_number = models.CharField(max_length=50, blank=True, null=True, help_text="UID of the item at the time of log")

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Inventory Logs"

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.user.username if self.user else 'N/A'} - {self.action} - {self.inventory_item.item_name if self.inventory_item else self.uid_number}"

class Document(models.Model):
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='item_documents/')
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name
