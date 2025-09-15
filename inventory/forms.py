from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from .models import InventoryItem, Project, ItemCategory, InventoryDocument, InventoryLog, TechnicalData,DocumentTag
from django.core.exceptions import ValidationError
from decimal import Decimal # Import Decimal
from inventory.models import Category,ItemStatus,Location

User = get_user_model()

DOCUMENT_TAG_CHOICES = [
    ('', 'Select a Tag'), # An empty option for the default selection
    ('Warranty', 'Warranty'),
    ('Invoice', 'Invoice'),
    ('Datasheet', 'Datasheet'),
    ('Shipment Doc', 'Shipment Doc'),
    ('Other', 'Other'),
]
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
class RegisterForm(UserCreationForm):
    """Custom registration form based on Django's UserCreationForm."""
    # Explicitly define the email field here
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class AddItemForm(forms.ModelForm):
    # Define choices for the new 'tag' field
    TAG_CHOICES = [
        ('', 'Select a Tag'),
        ('Warranty', 'Warranty'),
        ('Invoice', 'Invoice'),
        ('Datasheet', 'Datasheet'),
        ('Shipment Doc', 'Shipment Doc'),
        ('Other', 'Other'),
    ]

    tag = forms.ChoiceField(
        choices=TAG_CHOICES,
        required=True,
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
        fields = [

            'invoice_number','item_name', 'category', 'serial_number', 'quantity', 'location', 
            'status', 'description', 'project', 'image',
            'cpu', 'gpu', 'os', 'installed_software','price',
            'tag', 'document_file_upload'
        ]
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'project': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'cpu': forms.TextInput(attrs={'class': 'form-control'}),
            'gpu': forms.TextInput(attrs={'class': 'form-control'}),
            'os': forms.TextInput(attrs={'class': 'form-control'}),
            'installed_software': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tag': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = "Select a Category"
        self.fields['location'].empty_label = "Select a Location"
        self.fields['project'].empty_label = "Select a Project"

class TechnicalDataForm(forms.ModelForm):
    class Meta:
        model = TechnicalData
        fields = [
            'host_name', 'wifi_mac', 'mac_address', 'internet_source',
            'network', 'ip_address', 'build', 'city', 'country', 'os',
            'google_rd', 'pin', 'anydesk_id', 'anydesk_password',
            'edit_agent_date', 'last_belarc_update', 'last_system_update',
            'known_issues', 'pending_hw_replacements', 'previous_hw_replacements',
            'elevated_credential',
        ]
        widgets = {
            'host_name': forms.TextInput(attrs={'class': 'form-control'}),
            'wifi_mac': forms.TextInput(attrs={'class': 'form-control'}),
            'mac_address': forms.TextInput(attrs={'class': 'form-control'}),
            'internet_source': forms.TextInput(attrs={'class': 'form-control'}),
            'network': forms.TextInput(attrs={'class': 'form-control'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            'build': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'os': forms.TextInput(attrs={'class': 'form-control'}),
            'google_rd': forms.TextInput(attrs={'class': 'form-control'}),
            'pin': forms.TextInput(attrs={'class': 'form-control'}),
            'anydesk_id': forms.TextInput(attrs={'class': 'form-control'}),
            'anydesk_password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'edit_agent_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_belarc_update': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_system_update': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'known_issues': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'pending_hw_replacements': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'previous_hw_replacements': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'elevated_credential': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'host_name': 'Host Name',
            'wifi_mac': 'WiFi MAC Address',
            'mac_address': 'MAC Address',
            'internet_source': 'Internet Source',
            'network': 'Network',
            'ip_address': 'IP Address',
            'build': 'Build Version',
            'city': 'City',
            'country': 'Country',
            'os': 'Operating System',
            'google_rd': 'Google Remote Desktop',
            'pin': 'PIN',
            'anydesk_id': 'AnyDesk ID',
            'anydesk_password': 'AnyDesk Password',
            'edit_agent_date': 'Agent Edit Date',
            'last_belarc_update': 'Last Belarc Update',
            'last_system_update': 'Last System Update',
            'known_issues': 'Known Issues',
            'pending_hw_replacements': 'Pending Hardware Replacements',
            'previous_hw_replacements': 'Previous Hardware Replacements',
            'elevated_credential': 'Elevated Credential',
        }
class InventoryDocumentForm(forms.ModelForm):
    tag = forms.ModelChoiceField(queryset=DocumentTag.objects.all(), empty_label="Select a Tag")

    class Meta:
        model = InventoryDocument
        fields = ['tag', 'file']

class EditItemForm(forms.ModelForm):
    # Add fields for document upload
    tag = forms.ModelChoiceField(
        queryset=DocumentTag.objects.all(),
        label="Document Tag",
        empty_label="Select a tag",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    document_file_upload = forms.FileField(
        required=False,
        help_text="Upload a new related document (e.g., PDF, image)",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )
    # Corrected: Explicitly define the price field and set it to not be required
    price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = InventoryItem
        fields = [
            'invoice_number',   # 🔑 added here
            'item_name', 'category', 'serial_number', 'quantity', 'location',
            'status', 'description', 'project', 'image',
            'cpu', 'gpu', 'os', 'installed_software', 'price',
            'tag', 'document_file_upload'
        ]
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
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
        self.fields['category'].empty_label = "Select a Category"
        self.fields['location'].empty_label = "Select a Location"
        self.fields['project'].empty_label = "Select a Project"

class DeleteItemForm(forms.Form):
    uid_no = forms.CharField(
        label='Asset UID Number',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter the UID of the item to delete'})
    )
    reason_for_deletion = forms.CharField(
        label='Reason for Deletion',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g., End of life, Lost, Damaged beyond repair'}),
        required=True
    )


class BatchDeleteForm(forms.Form):
    uid_no = forms.CharField(
        label="UID Number",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter UID of item to delete (e.g., LAP0001)'})
    )
    reason_for_deletion = forms.CharField(
        label="Reason for Deletion/Reduction",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g., Decommissioned, Lost, Damaged beyond repair'}),
        required=True
    )


class BatchTransferForm(forms.Form):
    new_location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        empty_label="Select a new location",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="New Location"
    )
    item_ids = forms.CharField(widget=forms.HiddenInput())

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
    category = forms.ModelChoiceField(
        queryset=ItemCategory.objects.all().order_by('name'),
        required=True,
        empty_label="Select a Category",
        label='Category',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
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

class ImportReviewForm(forms.Form):
    # This form is dynamically generated in the view, so we don't define fields here.
    # The fields are added in the view based on the parsed Excel data.
    pass

class ImportItemForm(forms.Form):
    # This form is no longer a ModelForm to avoid the FieldError
    
    # Fields that come from the Excel sheet (not editable in form)
    item_name = forms.CharField(max_length=100, required=False)
    description = forms.CharField(max_length=200, required=False)
    quantity = forms.IntegerField(required=False, min_value=1, initial=1)

    # These are the fields to be manually entered by the user
    uid_no = forms.CharField(max_length=20, required=False)
    serial_number = forms.CharField(max_length=100, required=False)
    category = forms.ModelChoiceField(queryset=ItemCategory.objects.all(), required=True)
    location = forms.ModelChoiceField(queryset=Location.objects.all(), required=True)
    status = forms.ModelChoiceField(queryset=ItemStatus.objects.all(), required=True)
    project = forms.ModelChoiceField(queryset=Project.objects.all(), required=False)

class InventoryForm(forms.ModelForm):
    # This field is now a single-select dropdown menu
    tag = forms.ModelChoiceField(
        queryset=DocumentTag.objects.all(),
        required=False,
        label="TAG"
    )

    document_file_upload = forms.FileField(required=False, label="Upload Document")

    price = forms.DecimalField(max_digits=10, decimal_places=2, required=True, label="Price")
    
    # Fields for the TechnicalData model
    cpu = forms.CharField(max_length=255, required=False, label="CPU")
    gpu = forms.CharField(max_length=255, required=False, label="GPU")
    os = forms.CharField(max_length=255, required=False, label="Operating System")
    installed_software = forms.CharField(widget=forms.Textarea, required=False, label="Installed Software")

    class Meta:
        model = InventoryItem
        fields = [
            'invoice_number','item_name', 'category', 'serial_number', 'quantity', 'location',
            'status', 'project', 'description', 'image', 'price'
        ]
    
    def clean_invoice_number(self):
        invoice_number = self.cleaned_data.get("invoice_number")
        if invoice_number:
            # Check if another item already has this invoice number
            qs = InventoryItem.objects.filter(invoice_number=invoice_number)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)  # allow same item to re-save
            if qs.exists():
                raise forms.ValidationError(f"❌ Invoice number '{invoice_number}' already exists.")
        return invoice_number

    def save(self, commit=True):
        inventory_item = super().save(commit=False)
        if commit:
            inventory_item.save()
            
            # Handling the single-select tag
            selected_tag = self.cleaned_data.get('tag')
            if selected_tag:
                inventory_item.tag = selected_tag
            
            # Handle TechnicalData
            TechnicalData.objects.update_or_create(
                item=inventory_item,
                defaults={
                    'cpu': self.cleaned_data.get('cpu'),
                    'gpu': self.cleaned_data.get('gpu'),
                    'os': self.cleaned_data.get('os'),
                    'installed_software': self.cleaned_data.get('installed_software'),
                }
            )
        return inventory_item


class InventoryLogFilterForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Owner"
    )
    action = forms.CharField(max_length=100, required=False, label="Action")
    item_name = forms.CharField(max_length=255, required=False, label="Item Name")
    uid_number = forms.CharField(max_length=50, required=False, label="UID Number")
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label="From Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label="Till Date"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(inventorylog__isnull=False).distinct()
        
        self.fields['item_name'].widget.attrs.update({'placeholder': 'Enter Item Name'})
        self.fields['uid_number'].widget.attrs.update({'placeholder': 'Enter UID Number'})




        
# New form for handling invoice uploads
class InvoiceScanForm(forms.Form):
    invoice_file = forms.FileField(
        required=True,
        help_text="Upload an invoice in PDF or image format (JPG, PNG).",
        label="Invoice File",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )
    # New fields to pass context to the save function
    location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by('name'),
        required=False,  
        empty_label="Select a Location",
        label='Default Location',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all().order_by('name'),
        required=False,  
        empty_label="Select a Project",
        label="Default Project",
        widget=forms.Select(attrs={'class': 'form-control'})
    )