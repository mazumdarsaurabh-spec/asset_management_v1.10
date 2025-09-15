 #inventory_management/inventory/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model # Import get_user_model
from .models import InventoryItem, Location, Project, ItemCategory, Document, InventoryLog # Import ItemCategory and InventoryLog
from django.core.exceptions import ValidationError # Import ValidationError

User = get_user_model() # Get the currently active User model

# Custom LoginForm (if you have one, otherwise use Django's AuthenticationForm directly)
class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )

    class Meta:
        fields = ['username', 'password']

# Custom RegisterForm (if you have one, otherwise use Django's UserCreationForm directly)
# Assuming you might have a custom form for registration beyond basic UserCreationForm
# If not, you can remove this and just use UserCreationForm in views.py
class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',) # Example: add email field
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }



class AddItemForm(forms.ModelForm):
    # Define choices for the new 'tag' field
    TAG_CHOICES = [
        ('', 'Select a Tag'), # Empty option for "Select a Tag"
        ('Warranty', 'Warranty'),
        ('Invoice', 'Invoice'),
        ('Datasheet', 'Datasheet'),
        ('Shipment Doc', 'Shipment Doc'),
        ('Other', 'Other'),
    ]

    # Replaced document_name with tag, made it a ChoiceField and mandatory
    tag = forms.ChoiceField(
        choices=TAG_CHOICES,
        required=True, # Made mandatory
        help_text="Select a tag for the uploaded document",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    document_file_upload = forms.FileField(
        required=False, 
        help_text="Upload a related document (e.g., PDF, image)",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )

    class Meta:
        model = InventoryItem
        # Exclude 'uid_no' as it's auto-generated
        # Exclude 'created_by' as it's set in the view
        # Exclude 'last_transfer_date' as it's set during transfer
        fields = [
            'item_name', 'category', 'serial_number', 'quantity', 'location', 
            'status', 'description', 'project', 'image',
            'cpu', 'gpu', 'os', 'installed_software',
            'tag', 'document_file_upload' # Updated to 'tag'
        ]
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'project': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'cpu': forms.TextInput(attrs={'class': 'form-control'}),
            'gpu': forms.TextInput(attrs={'class': 'form-control'}),
            'os': forms.TextInput(attrs={'class': 'form-control'}),
            'installed_software': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tag': forms.Select(attrs={'class': 'form-control'}), # Added widget for 'tag'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add an empty_label for ForeignKey fields to allow "Select..." option
        self.fields['category'].empty_label = "Select a Category"
        self.fields['location'].empty_label = "Select a Location"
        self.fields['project'].empty_label = "Select a Project"
        
        # Set initial display for hardware fields to hidden
        # This is primarily handled by JS in the template, but good for initial server-side rendering
        # self.fields['cpu'].widget.attrs['style'] = 'display:none;'
        # self.fields['gpu'].widget.attrs['style'] = 'display:none;'
        # self.fields['os'].widget.attrs['style'] = 'display:none;'
        # self.fields['installed_software'].widget.attrs['style'] = 'display:none;'
       


class EditItemForm(forms.ModelForm):
    # Add fields for document upload directly to the form
    document_name = forms.CharField(
        max_length=255, 
        required=False, 
        help_text="Name for the uploaded document (e.g., 'Purchase Receipt')",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    document_file_upload = forms.FileField(
        required=False, 
        help_text="Upload a new related document (e.g., PDF, image)",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )

    class Meta:
        model = InventoryItem
        # Exclude 'uid_no' as it's auto-generated and shouldn't be edited
        # Exclude 'created_by' as it's set once
        # Exclude 'last_transfer_date' as it's set during transfer
        fields = [
            'item_name', 'category', 'serial_number', 'quantity', 'location', 
            'status', 'description', 'project', 'image',
            'cpu', 'gpu', 'os', 'installed_software',
            'document_name', 'document_file_upload' # Include document fields
        ]
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'project': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'cpu': forms.TextInput(attrs={'class': 'form-control'}),
            'gpu': forms.TextInput(attrs={'class': 'form-control'}),
            'os': forms.TextInput(attrs={'class': 'form-control'}),
            'installed_software': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add an empty_label for ForeignKey fields to allow "Select..." option
        self.fields['category'].empty_label = "Select a Category"
        self.fields['location'].empty_label = "Select a Location"
        self.fields['project'].empty_label = "Select a Project"

        # Make UID No field read-only if instance exists
        if self.instance and self.instance.uid_no:
            self.fields['uid_no'].widget.attrs['readonly'] = True
            self.fields['uid_no'].widget.attrs['disabled'] = True # Disable to prevent it from being sent in POST data

        

class BatchDeleteForm(forms.Form):
    # This form is likely used for confirming deletion and providing a reason
    # The actual item IDs are passed via JavaScript in the batch_delete_items view
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Reason for deletion/reduction'}),
        required=True
    )

class StatusCheckForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(InventoryItem.STATUS_CHOICES),
        required=False,
        label='Filter by Status',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by('name'),
        required=False,
        empty_label="All Locations",
        label='Filter by Location',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all().order_by('name'),
        required=False,
        empty_label="All Projects",
        label='Filter by Project',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class ModifyItemForm(forms.Form):
    # This form is used for searching for an item to modify
    search_query = forms.CharField(
        max_length=255,
        required=True,
        label='Search by UID or Serial Number',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter UID or Serial Number'})
    )

class FilterForm(forms.Form):
    search = forms.CharField(
        max_length=255, 
        required=False, 
        widget=forms.TextInput(attrs={'placeholder': 'Search items...', 'class': 'form-control'})
    )
    # Corrected: Use ModelChoiceField for category to query ItemCategory model
    category = forms.ModelChoiceField(
        queryset=ItemCategory.objects.all().order_by('name'),
        required=False,
        empty_label="All Categories",
        label='Category',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    # Status still uses InventoryItem.STATUS_CHOICES as it's a CharField with choices
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(InventoryItem.STATUS_CHOICES),
        required=False,
        label='Status',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by('name'),
        required=False,
        empty_label="All Locations",
        label='Location',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all().order_by('name'),
        required=False,
        empty_label="All Projects",
        label='Project',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class InventoryLogFilterForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        required=False,
        empty_label="All Users",
        label="User",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    action = forms.ChoiceField(
        choices=[('', 'All Actions')] + list(InventoryLog.ACTION_CHOICES if hasattr(InventoryLog, 'ACTION_CHOICES') else []),
        required=False,
        label="Action",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    item_name = forms.CharField(
        max_length=255,
        required=False,
        label="Item Name (or Details)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search item name or log details'})
    )
    uid_number = forms.CharField(
        max_length=50,
        required=False,
        label="UID Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search by UID'})
    )
    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        label="End Date",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
