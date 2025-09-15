# inventory_management/inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms
from urllib.parse import urlencode
from django.db import models
from django.db.models import Q,Count,F,Max
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError, transaction
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User
from django.forms import formset_factory
import json
import random
import pandas as pd
import io
import os
from decimal import Decimal
from django.core.files.base import ContentFile
import fitz
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
import pytesseract
from .ocr_parser import get_text_from_image, extract_details_with_llm
from .ocr_parser import extract_details_with_llm, get_text_from_image
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist 
from .forms import BatchDeleteForm, ModifyItemForm,EditItemForm,AddItemForm,FilterForm,LoginForm,InventoryLogFilterForm, InvoiceScanForm,InventoryDocumentForm, DeleteItemForm, BatchTransferForm
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from openpyxl.styles import Font, Alignment
from django.contrib.auth import get_user_model
import google.generativeai as genai
from django.urls import reverse
import openpyxl
import base64
import logging
import re
import uuid
from django.core.files.storage import FileSystemStorage
from PIL import Image
import requests 
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from datetime import datetime, date, timedelta
from django.core.serializers.json import DjangoJSONEncoder
import logging
from .models import Item, TechnicalData,ItemStatus, InventoryDocument,ItemLocation,Status
from .forms import TechnicalDataForm,InventoryForm,ImportItemForm
from django.core.files.uploadedfile import UploadedFile
from io import BytesIO
import fitz # PyMuPDF
from decimal import Decimal
from .models import InventoryItem,TechnicalData, Location, Project, InventoryLog,UIDCategorySequence,ItemCategory,DocumentTag,InventoryDocument,Category,ItemStatus
from django.contrib.auth.forms import UserCreationForm
from .forms import InventoryDocumentForm
from .models import Kit

logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r'"C:\Program Files\Tesseract-OCR\tesseract.exe"'


User = get_user_model()

class DjangoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
    

@login_required(login_url='inventory:login')
@require_POST
def clear_all_logs(request):
    if not request.user.is_superuser:
        messages.error(request, "Permission denied. Only administrators can clear logs.")
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

    try:
        with transaction.atomic():
            InventoryLog.objects.all().delete()
            
            create_log_entry(request.user, None, 'logs_cleared', f"All inventory logs cleared by {request.user.username}.")
            messages.success(request, "All inventory logs have been cleared successfully.")
            return JsonResponse({'success': True, 'message': 'All logs cleared successfully.'})
    except Exception as e:
        messages.error(request, f"An error occurred while clearing logs: {e}")
        create_log_entry(request.user, None, 'clear_logs_failed', f"Failed to clear all logs by {request.user.username}: {e}")
        return JsonResponse({'success': False, 'message': f'Error clearing logs: {e}'}, status=500)

    

@login_required(login_url='inventory:login')
def inventory_logs(request):
    logs = InventoryLog.objects.all()
    form = InventoryLogFilterForm(request.GET or None)

    if form.is_valid():
        user_filter = form.cleaned_data.get('user')
        action_filter = form.cleaned_data.get('action')
        item_name_filter = form.cleaned_data.get('item_name')
        uid_number_filter = form.cleaned_data.get('uid_number')
        start_date_filter = form.cleaned_data.get('start_date')
        end_date_filter = form.cleaned_data.get('end_date')

        if user_filter:
            logs = logs.filter(user=user_filter)
        if action_filter:
            logs = logs.filter(action__icontains=action_filter)
        if item_name_filter:
            logs = logs.filter(Q(inventory_item__item_name__icontains=item_name_filter) | Q(details__icontains=item_name_filter))
        if uid_number_filter:
            logs = logs.filter(uid_number__icontains=uid_number_filter)
        if start_date_filter:
            logs = logs.filter(timestamp__date__gte=start_date_filter)
        if end_date_filter:
            logs = logs.filter(timestamp__date__lte=end_date_filter)

    logs = logs.order_by('-timestamp')

    page_size = request.GET.get('page_size', 10)
    paginator = Paginator(logs, page_size)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'form': form,
        'page_sizes': [5, 10, 25, 50, 100],
        'page_size': int(page_size),
    }
    return render(request, 'inventory/inventory_logs.html', context)


def create_log_entry(user, item, action, details, uid_number_for_log=None):
    try:
        InventoryLog.objects.create(
            user=user,
            inventory_item=item,
            action=action,
            details=details,
            uid_number=uid_number_for_log if uid_number_for_log is not None else (item.uid_no if item else None)
        )
    except Exception as e:
        logger.error(f"Failed to create inventory log entry: {e}")

# --- USER AUTHENTICATION VIEWS ---

def user_login(request):
    if request.user.is_authenticated:
        return redirect('inventory:dashboard') 

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome, {username}!')
                create_log_entry(request.user, None, 'login', 'User logged in successfully.')
                return redirect('inventory:dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
                create_log_entry(request.user, None, 'login_failed', f'Failed login attempt for username: {username}')
        else:
            messages.error(request, 'Please correct the errors below.')
            create_log_entry(request.user, None, 'login_failed', 'Failed login attempt due to form errors.')
    else:
        form = LoginForm()

    context = {
        'form': form,
        'form_title': 'Login'
    }
    return render(request, 'inventory/login.html', context)


@login_required(login_url='inventory:login')
def user_logout(request):
    create_log_entry(request.user, None, 'logout', 'User logged out.')
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('inventory:login')

def user_register(request):
    if request.user.is_authenticated:
        return redirect('inventory:dashboard') 

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful. You can now log in.')
            create_log_entry(user, None, 'register', f'New user registered: {user.username}')
            return redirect('inventory:login')
        else:
            messages.error(request, 'Registration failed. Please correct the errors.')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'form_title': 'Register Account'
    }
    return render(request, 'inventory/register.html', context)

# --- INVENTORY MANAGEMENT VIEWS ---

@login_required(login_url='inventory:login')
def dashboard_view(request):
    items = InventoryItem.objects.filter(is_deleted=False)
    purge_old_deletions()

    # ✅ Initialize filter_form
    if request.method == "GET":
        filter_form = FilterForm(request.GET)
    else:
        filter_form = FilterForm()

    if filter_form.is_valid():
        search_query = filter_form.cleaned_data.get('search')
        if search_query:
            items = items.filter(
                Q(item_name__icontains=search_query) |
                Q(uid_no__icontains=search_query) |
                Q(serial_number__icontains=search_query) |
                Q(location__name__icontains=search_query) |
                Q(status__icontains=search_query) |
                Q(description__icontains=search_query)
            )

    sort = request.GET.get('sort', 'item_name')
    direction = request.GET.get('direction', 'asc')
    
    if sort == 'location__name':
        items = items.order_by('-location__name' if direction == 'desc' else 'location__name')
    elif sort == 'project__name':
        items = items.order_by('-project__name' if direction == 'desc' else 'project__name')
    else:
        if direction == 'desc':
            sort = f'-{sort}'
        items = items.order_by(sort)

    page_size = request.GET.get('page_size', 10)
    paginator = Paginator(items, page_size)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    locations = Location.objects.all().order_by('name')
    projects = Project.objects.all().order_by('name')
    users = User.objects.all().order_by('username')

    total_item_count = InventoryItem.objects.filter(is_deleted=False).count()

    context = {
        'filter_form': filter_form,
        'page_obj': page_obj,
        'page_sizes': [5, 10, 25, 50, 100],
        'page_size': int(page_size),
        'sort': sort.lstrip('-'),
        'direction': direction,
        'locations': locations,
        'projects': projects,
        'users': users,
        'total_item_count': total_item_count,
        'locations_json': json.dumps([model_to_dict(loc) for loc in locations], cls=DjangoJSONEncoder),
        'projects_json': json.dumps([model_to_dict(proj) for proj in projects], cls=DjangoJSONEncoder),
        'users_json': json.dumps([model_to_dict(user) for user in users], cls=DjangoJSONEncoder),
    }
    return render(request, 'inventory/dashboard.html', context)

def generate_uid(category_prefix, current_seq):
    """
    Helper function to generate a new unique UID.
    This now uses a passed sequence number to ensure continuity within a batch.
    """
    if not category_prefix:
        category_prefix = 'OTH'
        
    today_str = date.today().strftime('%y%m%d')
    prefix_with_date = f"{category_prefix}{today_str}"
    
    return f"{prefix_with_date}{current_seq:04d}"


@login_required(login_url='inventory:login')
def add_item_view(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES)
        if form.is_valid():
            inventory_item = form.save(commit=False)
            inventory_item.created_by = request.user
            inventory_item.invoice_number = form.cleaned_data.get("invoice_number")
            inventory_item.save()
            
            # Get the document file and selected tag from the form
            document_file = form.cleaned_data.get('document_file_upload')
            selected_tag = form.cleaned_data.get('tag')
            

            if document_file:
                InventoryDocument.objects.create(
                    inventory_item=inventory_item,
                    tag=selected_tag, # Use the correct field: 'tag'
                    file=document_file,
                    uploaded_by=request.user
                )
                messages.success(request, f"Asset '{inventory_item.item_name}' added successfully with document.")
            else:
                messages.success(request, f"Asset '{inventory_item.item_name}' added successfully without document.")

            create_log_entry(
                user=request.user,
                item=inventory_item,
                action="item_added",
                details=f"Asset '{inventory_item.item_name}' was added with UID {inventory_item.uid_no}.",
            )
            
            
            return redirect(reverse('inventory:dashboard'))
            
            
        else:
            print("Form is not valid. Errors:", form.errors)
            messages.error(request, "Failed to add asset. Please correct the errors below.")
            
    else:
        form = InventoryForm()

    context = {
        'form': form,
    }
    return render(request, 'inventory/add_item.html', context)

@login_required(login_url='inventory:login')
@require_POST
def add_items_from_invoice(request):
    invoice_number = request.POST.get("invoice_number", "") or None

    # ✅ single saved invoice file path
    invoice_rel_path = request.session.pop("uploaded_invoice_path", None)
    invoice_file_path = os.path.join(settings.MEDIA_ROOT, invoice_rel_path) if invoice_rel_path else None

    indices = set()
    pattern = re.compile(r"^items\[(\d+)\]\[item_name\]$")
    for key in request.POST.keys():
        m = pattern.match(key)
        if m:
            indices.add(int(m.group(1)))

    saved_count = 0
    errors = []

    for idx in sorted(indices):
        prefix = f"items[{idx}]"
        item_name = request.POST.get(f"{prefix}[item_name]", "").strip()
        description = request.POST.get(f"{prefix}[description]", "").strip()
        quantity = request.POST.get(f"{prefix}[quantity]", "1")
        unit_price = request.POST.get(f"{prefix}[unit_price]", "0")
        serial_number = request.POST.get(f"{prefix}[serial_number]", "").strip()
        category_val = request.POST.get(f"{prefix}[category_id]", "")
        status_val = request.POST.get(f"{prefix}[status]", "")
        location_val = request.POST.get(f"{prefix}[location_id]", "")

        # sanitize numbers
        try:
            qty = int(float(quantity)) if quantity else 1
        except Exception:
            qty = 1
        try:
            price = Decimal(str(unit_price)) if unit_price else Decimal("0.00")
        except Exception:
            price = Decimal("0.00")

        # resolve category (fallback to Other)
        category_obj = None
        if category_val and category_val != "other":
            try:
                category_obj = ItemCategory.objects.filter(id=int(category_val)).first()
            except Exception:
                category_obj = None
        if not category_obj:
            category_obj = ItemCategory.objects.filter(name__iexact="Other").first()

        # resolve location
        location_obj = None
        if location_val:
            try:
                location_obj = Location.objects.filter(id=int(location_val)).first()
            except Exception:
                location_obj = None

        try:
            inv_item = InventoryItem(
                item_name=item_name or "Untitled",
                description=description,
                invoice_number=invoice_number,
                category=category_obj,
                status=status_val or InventoryItem.STATUS_CHOICES[0][0],
                serial_number=serial_number or None,
                quantity=qty,
                price=price,
                location=location_obj,
                created_by=request.user
            )
            inv_item.save()
            saved_count += 1

            # ✅ link the SAME invoice copy to each item
            if invoice_file_path and os.path.exists(invoice_file_path):
                tag, _ = DocumentTag.objects.get_or_create(name="Invoice")
                InventoryDocument.objects.create(
                    inventory_item=inv_item,
                    tag=tag,
                    file=invoice_rel_path,  # relative to MEDIA_ROOT
                    description=f"Invoice document for {invoice_number or 'N/A'}",
                    uploaded_by=request.user
                )

                create_log_entry(
                user=request.user,
                item=inv_item,
                action="item_added",
                details=f"Scanned item '{inv_item.item_name}' was added from invoice {invoice_number or 'N/A'}."
            )

        except Exception as e:
            errors.append(f"Row {idx}: {e}")

    if saved_count:
        messages.success(request, f"{saved_count} scanned item(s) saved successfully.")
    if errors:
        messages.error(request, "Some rows failed to save: " + "; ".join(errors))

    return redirect("inventory:dashboard")


@login_required
def save_scanned_items(request):
    if request.method == "POST":
        form = ScannedItemForm(request.POST)

        if form.is_valid():
            # Save the item
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()
            create_log_entry(
                user=request.user,
                item=item,
                action="item_added",
                details=f"Scanned item '{item.item_name}' was saved with UID {item.uid_no}."
            )

            return redirect("inventory:dashboard")
        else:
            # Re-render scan page with errors and highlighted fields
            return render(request, "inventory/scan_invoice.html", {"form": form})

    else:
        form = ScannedItemForm()
        return render(request, "inventory/scan_invoice.html", {"form": form})



def ocr_review(request):
    """
    Displays the extracted OCR data for user review and editing.
    """
    scanned_items = request.session.get('scanned_items', [])
    if not scanned_items:
        messages.warning(request, "No scanned items to review. Please upload an invoice.")
        return redirect('inventory:scan_invoice_page')
    
    context = {
        'items': scanned_items,
        'locations': Location.objects.all(),
        'projects': Project.objects.all(),
        'item_categories': ItemCategory.objects.all(),
        'statuses': ItemStatus.objects.all()
    }
    return render(request, 'inventory/ocr_review.html', context)


@login_required
@transaction.atomic
def delete_item_by_pk(request, pk):
    if request.method != "POST":
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    try:
        with transaction.atomic():
            item = get_object_or_404(InventoryItem, pk=pk)
            item.is_deleted = True
            item.deleted_at = timezone.now()
            item.save()

            undo_url = reverse("inventory:undo_delete", args=[item.id])
            messages.success(request,
                f'Item "{item.item_name}" deleted. '
                f'<a href="{undo_url}" class="btn btn-link btn-sm">Undo</a>'
            )

            return JsonResponse({'success': True, 'message': 'Item deleted (pending hard delete).'})
    except Exception as e:
        logging.error(f"Error deleting item {pk}: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred while deleting the item.'}, status=500)


@login_required(login_url='inventory:login')
@transaction.atomic
def delete_item_view(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)

    if request.method == "POST":
        item.is_deleted = True
        item.deleted_at = timezone.now()
        item.save()

        create_log_entry(
            user=request.user,
            item=item,
            action="item_deleted",
            details=f'Item "{item.item_name}" (UID {item.uid_no}) was deleted.'
        )

        undo_url = reverse("inventory:undo_delete", args=[item.id])
        messages.success(
            request,
            f'Item "{item.item_name}" deleted. '
            f'<a href="{undo_url}" class="btn btn-sm btn-warning ml-2">Undo</a>'
        )

        return redirect("inventory:dashboard")

    return render(request, "inventory/delete_item.html", {
        "item": item,
        "form_title": f"Delete Asset: {item.item_name}",
    })


def purge_old_deletions():
    expiry_time = timezone.now() - timedelta(seconds=30)  # keep 30s for undo
    old_items = InventoryItem.objects.filter(is_deleted=True, deleted_at__lt=expiry_time)
    for item in old_items:
            create_log_entry(
                user=None,  # system action
                item=None,
                action="item_purged",
                details=f'Item "{item.item_name}" (UID {item.uid_no}) was permanently deleted.',
                uid_number_for_log=item.uid_no
            )

    count = old_items.count()
    if count:
        logger.info(f"Purging {count} items permanently.")
        old_items.delete()


@login_required(login_url='inventory:login')
def import_items_view(request):
    if request.method == 'POST':
        form = InventoryDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded_file = request.FILES['document_file']
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()

                if file_ext in ['.xlsx', '.xls']:
                    df = pd.read_excel(uploaded_file)
                elif file_ext == '.csv':
                    df = pd.read_csv(uploaded_file)
                else:
                    messages.error(request, 'Invalid file format. Please upload an Excel or CSV file.')
                    return redirect('inventory:dashboard')

                with transaction.atomic():
                    df.columns = df.columns.str.strip().str.lower()
                    for index, row in df.iterrows():
                        try:
                            raw_serial = row.get('serial_number')
                            
                            # ✅ Check for duplicate serial number
                            if pd.isna(raw_serial) or str(raw_serial).strip() == "":
                                serial_number = None
                            else:
                                serial_number = str(raw_serial).strip()
                            if serial_number and InventoryItem.objects.filter(serial_number=serial_number).exists():
                                messages.warning(request, f"Skipped row {index+2}: Serial Number '{serial_number}'is duplicate.")
                                
                                continue

                            category_id = row.get('category_id')
                            location_id = row.get('location_id')
                            status_id = row.get('status_id')

                            category = ItemCategory.objects.get(id=category_id)
                            location = Location.objects.get(id=location_id)
                            status = ItemStatus.objects.get(id=status_id)

                            unit_price = Decimal(str(row.get('unit_price', '0')))
                            quantity = int(row.get('quantity', 0))

                            InventoryItem.objects.create(
                                uid_no=row.get('uid_no'),
                                item_name=row.get('item_name'),
                                description=row.get('description'),
                                serial_number=serial_number,
                                quantity=quantity,
                                price=unit_price,
                                category=category,
                                status=status,
                                location=location,
                                created_by=request.user,
                            )
                        except (ItemCategory.DoesNotExist, Location.DoesNotExist, ItemStatus.DoesNotExist) as e:
                            messages.error(request, f"Skipped row {index + 2}: Missing Category, Location, or Status.")
                            continue
                        except Exception as e:
                            messages.error(request, f"Skipped row {index + 2}: {e}")
                            continue

                messages.success(request, 'Items imported successfully.')
                return redirect('inventory:dashboard')

            except Exception as e:
                messages.error(request, f'An unexpected error occurred during import: {e}')
                return redirect('inventory:dashboard')
    else:
        form = InventoryDocumentForm()

    return render(request, 'inventory/import_items.html', {'form': form})

@login_required
def export_inventory(request):
    """
    Exports a filtered or complete list of inventory items to an Excel file.
    """
    try:
        # Get item IDs from the query parameters
        item_ids_str = request.GET.get('item_ids', '')
        if item_ids_str:
            item_ids = [int(item_id) for item_id in item_ids_str.split(',') if item_id.isdigit()]
            items = InventoryItem.objects.filter(id__in=item_ids).order_by('item_name')
        else:
            # If no specific items are selected, export all items
            items = InventoryItem.objects.all().order_by('item_name')

        if not items:
            messages.warning(request, "No items found to export.")
            return redirect('inventory:dashboard')

        # Create a DataFrame from the queryset
        data = []
        for item in items:
            # Safely get the status display name. The .get_status_display() method
            # correctly handles the value from the choices tuple.
            status_display = item.get_status_display()
            
            # Safely get related object names, handling cases where they might be None.
            category_name = item.category.name if item.category else 'N/A'
            location_name = item.location.name if item.location else 'N/A'
            project_name = item.project.name if item.project else 'N/A'

            # This is the crucial fix for the 'str' object error.
            # It correctly joins the names of all related kits.
            kit_names = ", ".join([k.name for k in item.kits.all()]) if item.kits.exists() else 'N/A'
            
            data.append({
                'UID No': item.uid_no,
                'Item Name': item.item_name,
                'Description': item.description,
                'Serial Number': item.serial_number,
                'Quantity': item.quantity,
                'Price': item.price,
                'Category': category_name,
                'Status': status_display,
                'Location': location_name,
                'Project': project_name,
                'Kit': kit_names,
                'Created By': item.created_by.username,
                'Created At': item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        df = pd.DataFrame(data)

        # Create an in-memory buffer for the Excel file
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventory Data')
        
        # Prepare the response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="inventory_data.xlsx"'
        return response
    
    except Exception as e:
        logging.error(f"Error during inventory export: {e}")
        messages.error(request, "An unexpected error occurred during export.")
        return redirect('inventory:dashboard')

@login_required(login_url='inventory:login')
def delete_item_general(request):
    """Handles deleting an entire item by UID number."""
    item_name_to_display = None
    initial_uid_no = request.GET.get('uid_no')

    if request.method == 'POST':
        form = DeleteItemForm(request.POST)
        if form.is_valid():
            uid_no = form.cleaned_data['uid_no']
            reason_for_deletion = form.cleaned_data['reason_for_deletion']

            try:
                with transaction.atomic():
                    item_to_delete = get_object_or_404(InventoryItem, uid_no=uid_no)
                    item_name_for_log = item_to_delete.item_name
                    
                    create_log_entry(
                        request.user, item_to_delete, 'deleted',
                        f"Deleted item {item_name_for_log} (UID: {uid_no}). Reason: {reason_for_deletion}",
                        uid_number_for_log=uid_no
                    )

                    item_to_delete.delete()

                    messages.success(request, f"Item with UID '{uid_no}' has been deleted.")
                    return redirect('inventory:dashboard')

            except InventoryItem.DoesNotExist:
                messages.error(request, f"Item with UID '{uid_no}' not found.")
            except Exception as e:
                messages.error(request, f"An unexpected error occurred during deletion: {e}")
        else:
            messages.error(request, "Form validation failed. Please correct the errors.")
    else:
        if initial_uid_no:
            try:
                item = InventoryItem.objects.get(uid_no=initial_uid_no)
                form = DeleteItemForm(initial={'uid_no': initial_uid_no})
                item_name_to_display = item.item_name
            except InventoryItem.DoesNotExist:
                messages.warning(request, f"Item with UID '{initial_uid_no}' not found. Please enter details manually.")
                form = DeleteItemForm()
            except Exception as e:
                messages.error(request, f"Error pre-populating form: {e}")
                form = DeleteItemForm()
        else:
            form = DeleteItemForm()

    return render(request, 'inventory/delete_item.html', {
        'form': form,
        'form_title': 'Delete Asset',
        'item_name': item_name_to_display
    })

@login_required(login_url='inventory:login')
def save_imported_items(request):
    if request.method == 'POST':
        ImportItemFormSet = formset_factory(ImportItemForm)
        formset = ImportItemFormSet(request.POST)

        if formset.is_valid():
            saved_count = 0
            skipped_count = 0

            with transaction.atomic():
                # Get the latest sequence for each category in one pass
                sequential_uids = {}
                for form in formset:
                    category_id = form.cleaned_data.get('category').id
                    if category_id not in sequential_uids:
                        category_prefix = ItemCategory.objects.get(id=category_id).prefix
                        max_uid = InventoryItem.objects.select_for_update().filter(
                            uid_no__startswith=category_prefix
                        ).aggregate(max_uid=Max('uid_no'))

                        latest_seq = 0
                        if max_uid['max_uid']:
                            try:
                                latest_seq = int(max_uid['max_uid'][-4:])
                            except (ValueError, IndexError):
                                latest_seq = 0
                        sequential_uids[category_id] = latest_seq

                for idx, form in enumerate(formset, start=2):  # start=2 to match Excel row numbers
                    item_data = form.cleaned_data
                    category_id = item_data.get('category').id
                    sequential_uids[category_id] += 1
                    uid_no = generate_uid(item_data.get('category').prefix, sequential_uids[category_id])

                    # ✅ Clean serial number
                    raw_serial = item_data.get('serial_number')
                    if not raw_serial or str(raw_serial).strip().lower() in ["", "nan", "none"]:
                        serial_number = None
                    else:
                        serial_number = str(raw_serial).strip()

                    # ✅ Duplicate check
                    if serial_number and InventoryItem.objects.filter(serial_number=serial_number).exists():
                        messages.warning(request, f"Skipped row {idx}: Serial Number '{serial_number}' already exists.")
                        skipped_count += 1
                        continue

                    price_val = item_data.get('price') or Decimal('1.00')

                    InventoryItem.objects.create(
                        uid_no=uid_no,
                        item_name=item_data.get('item_name'),
                        description=item_data.get('description'),
                        quantity=item_data.get('quantity'),
                        price=price_val,
                        serial_number=serial_number,
                        category=item_data.get('category'),
                        location=item_data.get('location'),
                        status=item_data.get('status'),
                        project=item_data.get('project'),
                        created_by=request.user
                    )
                    saved_count += 1

            messages.success(request, f"✅ {saved_count} items imported successfully. ⚠️ {skipped_count} skipped due to duplicates.")
            if 'import_data' in request.session:
                del request.session['import_data']
            return redirect('inventory:dashboard')

        else:
            messages.error(request, "Error saving items. Please correct the errors below.")
            context = {
                'formset': formset,
                'item_categories': ItemCategory.objects.all(),
                'locations': Location.objects.all(),
                'statuses': ItemStatus.objects.all(),
                'projects': Project.objects.all(),
            }
            return render(request, 'inventory/import_review.html', context)

    return redirect('inventory:import')


@login_required(login_url='inventory:login')
@transaction.atomic
def delete_items_confirm(request):
    if request.method == "POST":
        item_ids = request.POST.getlist("item_ids")
        reason = request.POST.get("reason", "Not provided")

        items = InventoryItem.objects.filter(id__in=item_ids, is_deleted=False)
        deleted_items = []

        for item in items:
            item.is_deleted = True
            item.deleted_at = timezone.now()
            item.save()

        create_log_entry(
                user=request.user,
                item=item,
                action="item_deleted",
                details=f'Item "{item.item_name}" (UID {item.uid_no}) was deleted. Reason: {reason}'
            )


        deleted_items.append(item)

        if deleted_items:
            item_names = [i.item_name for i in deleted_items]
            undo_links = " ".join(
                f'<a href="{reverse("inventory:undo_delete", args=[i.id])}" '
                f'class="btn btn-sm btn-warning ml-2">Undo {i.item_name}</a>'
                for i in deleted_items
            )

            messages.success(
                request,
                f'Successfully deleted {len(deleted_items)} item(s): '
                f'{", ".join(item_names)}. Reason: {reason} {undo_links}'
            )
        else:
            messages.warning(request, "No valid items found to delete.")

        return redirect("inventory:dashboard")

@login_required(login_url='inventory:login')
def delete_document(request, item_id, doc_id):
    document = get_object_or_404(InventoryDocument, pk=doc_id, inventory_item__pk=item_id)

    if request.method == 'POST':
        # ✅ Capture filename before deletion
        doc_name = document.file.name if document.file else f"Document ID {document.id}"
        item = document.inventory_item

        # Delete document
        document.delete()

        # ✅ Log deletion
        create_log_entry(
            user=request.user,
            item=item,
            action="document_deleted",
            details=f"Document '{doc_name}' was deleted from item '{item.item_name}' (UID {item.uid_no})."
        )

        messages.success(request, f"Document '{doc_name}' deleted successfully.")

    return redirect('inventory:edit_item', pk=item_id)@login_required(login_url='inventory:login')


def delete_document(request, item_id, doc_id):
    document = get_object_or_404(InventoryDocument, pk=doc_id, inventory_item__pk=item_id)

    if request.method == 'POST':
        # ✅ Capture filename before deletion
        doc_name = document.file.name if document.file else f"Document ID {document.id}"
        item = document.inventory_item

        # Delete document
        document.delete()

        # ✅ Log deletion
        create_log_entry(
            user=request.user,
            item=item,
            action="document_deleted",
            details=f"Document '{doc_name}' was deleted from item '{item.item_name}' (UID {item.uid_no})."
        )

        messages.success(request, f"Document '{doc_name}' deleted successfully.")

    return redirect('inventory:edit_item', pk=item_id)


@login_required(login_url='inventory:login')
@transaction.atomic
def batch_delete_items(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
        item_ids_to_delete = data.get('item_ids', [])
        reason = data.get('reason', '')

        if not item_ids_to_delete:
            return JsonResponse({'success': False, 'message': 'No items selected for deletion.'}, status=400)

        try:
            uids = [int(item_id) for item_id in item_ids_to_delete]
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid item ID format.'}, status=400)

        items_to_delete = InventoryItem.objects.filter(id__in=uids)

        if not items_to_delete.exists():
            return JsonResponse({'success': False, 'message': 'No selected items found for deletion.'}, status=404)

        deleted_count = items_to_delete.count()

        for item in items_to_delete:
            item.is_deleted = True
            item.deleted_at = timezone.now()
            item.save()

        create_log_entry(
                user=request.user,
                item=item,
                action="item_deleted",
                details=f"Item '{item.item_name}' (UID {item.uid_no}) deleted in batch. Reason: {reason}"
            )

        return JsonResponse({'success': True, 'message': f"Soft-deleted {deleted_count} asset(s)."})
    except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON request body.'}, status=400)
    except Exception as e:
            return JsonResponse({'success': False, 'message': f'Unexpected error: {str(e)}'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    

@login_required(login_url='inventory:login')
def undo_last_deletion(request):
    last_ids = request.session.get('last_deleted_ids', [])
    if not last_ids:
        messages.warning(request, "No recently deleted items to restore.")
        return redirect("inventory:dashboard")

    items = InventoryItem.objects.filter(id__in=last_ids, is_deleted=True)
    restored_count = items.count()

    items.update(is_deleted=False, deleted_at=None)
    request.session['last_deleted_ids'] = []  
    create_log_entry(
            user=request.user,
            item=item,
            action="item_restored",
            details=f'Item "{item.item_name}" (UID {item.uid_no}) was restored (undo last deletion).'
        )
    

    messages.success(request, f"Restored {restored_count} item(s).")
    return redirect("inventory:dashboard")
            
          
    

@login_required
def undo_delete(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if item.is_deleted:
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        
        create_log_entry(
            user=request.user,
            item=item,
            action="item_restored",
            details=f'Item "{item.item_name}" (UID {item.uid_no}) was restored (undo).'
        )

        messages.success(request, f'Item "{item.item_name}" restored.')
    return redirect("inventory:dashboard")

@login_required(login_url='inventory:login')
def export_selected_items_to_excel(request):
    selected_ids_str = request.GET.get('ids', '')
    if not selected_ids_str:
        return HttpResponse("No items selected for export.", status=400)
    try:
        selected_ids= [int(item_id.strip()) for item_id in selected_ids_str.split(',') if item_id.strip()]
    except ValueError:
        return HttpResponse("Invalid item IDs provided.", status=400)

    items_to_export = InventoryItem.objects.filter(id__in=selected_ids)
    if not items_to_export.exists():
        return HttpResponse("No items found matching the selected IDs.", status=404)

    data = []
    for item in items_to_export:
        data.append({
            'Item Name': item.item_name,
            'UID No': item.uid_no,
            'Serial Number': item.serial_number if item.serial_number else 'N/A',
            'Quantity': item.quantity,
            'Location': item.location.name if item.location else 'N/A',
            'Project': item.project.name if item.project else 'N/A',
            'Status': item.get_status_display(),
            'Description': item.description if item.description else 'N/A',
            'Date Added': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else 'N/A',
            'Created At': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else 'N/A', 
            'Updated At': item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else 'N/A',
        })

    import pandas as pd
    df = pd.DataFrame(data)

    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Selected Items')
    output.seek(0)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="selected_inventory_items.xlsx"'
    response.write(output.read())
    create_log_entry(
        user=request.user,
        item=None,
        action="inventory_exported",
        details=f"Exported {len(selected_ids)} selected inventory items."
    )

    return response



def export_all_logs_excel(request):
    pass



@login_required(login_url='inventory:login')
@transaction.atomic
def batch_transfer_items(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items_to_transfer = data.get('items', [])
            
            if not items_to_transfer:
                logger.warning("Batch transfer: No items provided in request body.")
                return JsonResponse({'success': False, 'message': 'No items provided for transfer.'}, status=400)

            successful_transfers_count = 0
            failed_transfers_details = []

            for item_data in items_to_transfer:
                item_id = item_data.get('id')
                new_location_id = item_data.get('new_location')
                new_project_id = item_data.get('project')
                transfer_date_str = item_data.get('transfer_date')
                

                if not all([item_id, new_location_id, transfer_date_str]):
                    error_msg = f"Missing required data for item ID {item_id}. (new_location, transfer_date are required)"
                    logger.warning(f"Batch transfer failed for item {item_id}: {error_msg}")
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                    continue

                try:
                    item = InventoryItem.objects.select_for_update().get(id=item_id)
                    
                    old_location_name = item.location.name if item.location else "N/A"
                    old_project_name = item.project.name if item.project else "N/A"
                    
                    new_location = Location.objects.get(id=new_location_id)
                    
                    new_project = None
                    if new_project_id:
                        try:
                            new_project = Project.objects.get(id=new_project_id)
                        except Project.DoesNotExist:
                            error_msg = f"Project with ID {new_project_id} not found for item ID {item_id}."
                            logger.error(error_msg)
                            failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                            continue
                    
                    transfer_date = datetime.strptime(transfer_date_str, '%Y-%m-%d').date()

                    # Change: Set the status to 'IN_TRANSIT' for each item in the batch
                    item.location = new_location
                    item.project = new_project
                    item.status = 'IN_TRANSIT' # Set status to In Transit
                    item.last_transfer_date = transfer_date
                    item.owner_poc = item_data.get('poc_name')
                    item.save()

                    log_details = (
                        f"Transferred item '{item.item_name}' (UID: {item.uid_no}) "
                        f"from Location: '{old_location_name}' to '{new_location.name}'."
                    )
                    if new_project:
                        log_details += f" Project changed from '{old_project_name}' to '{new_project.name}'."
                    log_details += f" Transfer Date: {transfer_date_str}."

                    create_log_entry(request.user, item, 'transferred', log_details, uid_number_for_log=item.uid_no)
                    successful_transfers_count += 1

                except InventoryItem.DoesNotExist:
                    error_msg = f"Inventory item with ID {item_id} not found."
                    logger.error(error_msg)
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                except Location.DoesNotExist:
                    error_msg = f"New location with ID {new_location_id} not found."
                    logger.error(error_msg)
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                except ValueError as ve:
                    error_msg = f"Invalid date format for item ID {item_id}: {ve}. Use YYYY-MM-DD."
                    logger.error(error_msg)
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                except Exception as e:
                    error_msg = f"An unexpected error occurred for item ID {item_id}: {e}"
                    logger.exception(error_msg)
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
            
            if failed_transfers_details:
                response_message = f"Successfully transferred {successful_transfers_count} item(s). {len(failed_transfers_details)} item(s) failed: " + "; ".join(failed_transfers_details)
                messages.error(request, response_message)
                return JsonResponse({'success': False, 'message': response_message}, status=400)
            else:
                response_message = f"Successfully transferred {successful_transfers_count} asset(s)."
                messages.success(request, response_message)
                return JsonResponse({'success': True, 'message': response_message})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data received.'}, status=400)
        except Exception as e:
            logger.exception("An unexpected error occurred during batch transfer.")
            return JsonResponse({'success': False, 'message': f'An unexpected server error occurred: {str(e)}'}, status=500)

def import_review(request):
    if 'import_data' not in request.session:
        messages.error(request, 'No data found. Please upload a file first.')
        return redirect('inventory:import')
    
    import_data = request.session['import_data']
    
    # Do not generate UIDs here anymore
    ImportItemFormSet = formset_factory(ImportItemForm, extra=0)
    formset = ImportItemFormSet(initial=import_data)

    context = {
        'formset': formset,
        'item_categories': ItemCategory.objects.all(),
        'locations': Location.objects.all(),
        'statuses': ItemStatus.objects.all(),
        'projects': Project.objects.all(),
    }
    return render(request, 'inventory/import_review.html', context)



def import_items_submit(request):
    if request.method == 'POST':
        file = request.FILES.get('file')

        if not file:
            return JsonResponse({'success': False, 'message': 'No file was uploaded.'}, status=400)

        try:
            file_name = file.name
            
            # Read file content into a buffer to be handled by pandas
            file_content = file.read()
            
            if file_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file_content))
            elif file_name.endswith('.csv'):
                # Handle potential encoding issues more robustly
                try:
                    df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(io.BytesIO(file_content), encoding='latin1')
                    except UnicodeDecodeError:
                        df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8', errors='replace')

            else:
                return JsonResponse({'success': False, 'message': 'Unsupported file format. Please upload a .xlsx, .xls, or .csv file.'}, status=400)
            
            df.columns = df.columns.str.strip().str.lower()
            
            columns_to_extract = ['item_name', 'description', 'quantity']
            data_to_review = df.reindex(columns=columns_to_extract).to_dict('records')
            
            # --- UPDATED LOGIC ---
            # Automatically match category and set serial_number to blank
            all_categories = {re.escape(cat.name.lower()): cat.id for cat in ItemCategory.objects.all()}
            category_regex = re.compile('|'.join(all_categories.keys()))
            
            for item in data_to_review:
                item_desc = str(item.get('description', '')).lower()
                matched_category_id = None
                
                match = category_regex.search(item_desc)
                if match:
                    category_name = match.group(0)
                    matched_category_id = all_categories.get(category_name)
                
                # If no match, set to 'Other' category ID. You MUST have 'Other' in your database.
                if not matched_category_id:
                    other_category = ItemCategory.objects.filter(name__iexact='Other').first()
                    if other_category:
                        matched_category_id = other_category.id
                
                item['category_id'] = matched_category_id
                item['serial_number'] = '' # Force serial number to be blank
            # --- END OF UPDATED LOGIC ---

            request.session['import_data'] = data_to_review

            create_log_entry(
                user=request.user,
                item=None,
                action="import_submitted",
                details=f"User {request.user.username} submitted file '{file_name}' for import review. {len(data_to_review)} rows processed."
            )
            
            return JsonResponse({'success': True, 'redirect_url': '/inventory/import/review/'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error processing file: {e}'}, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

def group_view(request):
    if request.method == 'POST':
        kit_name = request.POST.get('kit_name')
        item_ids = request.POST.getlist('selected_items')

        if not kit_name or not item_ids:
            messages.error(request, "Kit name and at least one item are required.")
            return redirect('inventory:group_view')

        kit = Kit.objects.create(name=kit_name)
        kit.items.add(*item_ids)
        create_log_entry(
    user=request.user,
    item=None,
    action="kit_created",
    details=f"Kit '{kit_name}' created with {len(item_ids)} items."
)

        messages.success(request, f"Kit '{kit_name}' created successfully!")
        return redirect('inventory:dashboard')  # redirect after success

    # 👇 This ensures every GET request loads a fresh/empty form
    items = InventoryItem.objects.all()
    context = {
        'items': items,
        'selected_items': [],  # clear previous selections
        'kit_name': ''         # clear previous kit name
    }
    return render(request, 'inventory/group.html', context)


def get_new_uid(request):
    """
    This endpoint is no longer used for dynamic UID generation.
    It can be removed or left as a placeholder.
    """
    return JsonResponse({'error': 'This endpoint is deprecated.'}, status=405)

@login_required(login_url='inventory:login')
def modify_item(request):
    item = None
    form = ModifyItemForm(request.GET or None)

    if request.method == 'GET' and form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        if search_query:
            try:
                item = InventoryItem.objects.get(Q(uid_no__iexact=search_query) | Q(serial_number__iexact=search_query))

                create_log_entry(
                    user=request.user,
                    item=item,
                    action="item_search",
                    details=f"Search successful: found item '{item.item_name}' (UID {item.uid_no}) using query '{search_query}'."
                )
                return redirect('inventory:edit_item', pk=item.pk)
            except InventoryItem.DoesNotExist:
                messages.error(request, f"No asset found with UID or Serial Number: '{search_query}'. Please try again.")
            except InventoryItem.MultipleObjectsReturned:
                messages.warning(request, f"Multiple assets found for '{search_query}'. Please be more specific.")
    
    context = {
        'form': form,
        'item': item,
    }
    return render(request, 'inventory/modify_item.html', context)

@login_required(login_url='inventory:login')
@transaction.atomic
def edit_item(request, pk):
    item = get_object_or_404(
        InventoryItem.objects.select_related('location', 'project', 'category'),
        pk=pk
    )
    documents = item.documents.all()
    all_kits = Kit.objects.all()   # 🔑 Ensure all kits are fetched

    form_title = f'Edit Item: {item.item_name} ({item.uid_no})'

    if request.method == 'POST':
        # ✅ Bind invoice_number + all other fields
        item_form = EditItemForm(request.POST, request.FILES, instance=item)
        document_form = InventoryDocumentForm(request.POST, request.FILES)

        if 'item_submit' in request.POST:
            if item_form.is_valid():
                updated_item = item_form.save(commit=False)
                updated_item.save()

                # 🔑 Handle Kit assignment
                kit_id = request.POST.get("kit")
                if kit_id:
                    kit = Kit.objects.filter(pk=kit_id).first()
                    if kit:
                        updated_item.kits.set([kit])
                else:
                    updated_item.kits.clear()

                messages.success(
                    request,
                    f'Item "{updated_item.item_name}" updated successfully!'
                )

                create_log_entry(
                     user=request.user,
                      item=updated_item,
                      action="item_updated",
                      details=f"Item '{updated_item.item_name}' updated via edit form."
                 )
                return redirect('inventory:item_details', pk_or_uid=item.pk)

            messages.error(
                request,
                "Failed to update item details. Please correct the errors."
            )

        elif 'document_submit' in request.POST:
            if document_form.is_valid():
                new_doc = document_form.save(commit=False)
                new_doc.inventory_item = item
                new_doc.uploaded_by = request.user
                new_doc.save()
                messages.success(request, "Document uploaded successfully.")
                return redirect('inventory:item_details', pk_or_uid=item.pk)

            messages.error(request, "Failed to upload document.")

    else:
        # ✅ Pre-fill invoice_number + other fields
        item_form = EditItemForm(instance=item)
        document_form = InventoryDocumentForm()

    # 🔑 Pass context to template
    context = {
        'item': item,
        'item_form': item_form,
        'document_form': document_form,
        'documents': documents,
        'form_title': form_title,
        'all_kits': all_kits,
        'item_kits': item.kits,   # Existing kit relationships
    }
    return render(request, 'inventory/edit_item.html', context)


@login_required(login_url='inventory:login')
def add_item_to_kit(request, pk):
    """
    Adds an item to a specific kit.
    """
    if request.method == 'POST':
        kit = get_object_or_404(Kit, pk=pk)
        item_id = request.POST.get('item_id')
        
        if item_id:
            try:
                item = Item.objects.get(pk=item_id)
                kit.items.add(item)
                messages.success(request, f'Item "{item.item_name}" has been added to the kit "{kit.name}".')

                create_log_entry(
                    user=request.user,
                    item=item,
                    action="added_to_kit",
                    details=f"Item '{item.item_name}' (UID {item.uid_no}) added to Kit '{kit.name}'."
                )
            except Item.DoesNotExist:
                messages.error(request, 'The selected item does not exist.')
            except Exception as e:
                messages.error(request, f'An error occurred: {e}')
        
    return redirect('inventory:kit_items_list', pk=kit.pk)


@login_required
def item_details(request, pk_or_uid):
    try:
        # Support both PK and UID
        if InventoryItem.objects.filter(uid_no=pk_or_uid).exists():
            item = get_object_or_404(InventoryItem, uid_no=pk_or_uid)
        else:
            item = get_object_or_404(InventoryItem, pk=pk_or_uid)

        # Get related documents
        documents = item.documents.all()

        # Get kits (since an item can be part of multiple kits)
        kits = item.kits.all()  # assumes `related_name="kits"` in your Kit model

        context = {
            "item": item,
            "documents": documents,
            "kit_name": ", ".join([kit.name for kit in kits]) if kits else "N/A"
        }
        return render(request, "inventory/item_details.html", context)

    except Exception as e:
        messages.error(request, f"Error loading item details: {e}")
        return redirect("inventory:dashboard")
    

    
@login_required
@require_POST
def create_kit(request):
    kit_name = request.POST.get("kit_name")
    item_ids = request.POST.getlist("item_ids[]")  # from JS

    if not kit_name or not item_ids:
        return JsonResponse({"success": False, "message": "Kit name and items are required."})

    # Create the kit
    kit, created = Kit.objects.get_or_create(name=kit_name)
    kit.items.set(InventoryItem.objects.filter(id__in=item_ids))
    kit.save()

    create_log_entry(
        user=request.user,
        item=None,
        action="kit_created",
        details=f"Kit '{kit.name}' created with {len(item_ids)} items."
    )

    return JsonResponse({"success": True, "message": f"Kit '{kit.name}' created successfully."})

@login_required(login_url='inventory:login')
def remove_item_from_kit(request, pk, item_pk):
    """
    Removes an item from a specific kit.
    """
    if request.method == 'GET':
        kit = get_object_or_404(Kit, pk=pk)
        try:
            item = kit.items.get(pk=item_pk)
            kit.items.remove(item)
            messages.success(request, f'Item "{item.item_name}" has been removed from the kit "{kit.name}".')
        except Item.DoesNotExist:
            messages.warning(request, 'The item you are trying to remove is not in this kit or does not exist.')
        create_log_entry(
            user=request.user,
            item=item,
            action="removed_from_kit",
            details=f"Item '{item.item_name}' removed from Kit '{kit.name}'."
       )
   
        
        return redirect('inventory:kit_items_list', pk=kit.pk)
    else:
        messages.error(request, "Invalid request method.")
        return redirect('inventory:kit_items_list', pk=pk)





@login_required(login_url='inventory:login')
def kit_items_list(request, pk):
    kit = get_object_or_404(Kit, pk=pk)

    # Items that are NOT yet in this kit
    available_items = InventoryItem.objects.exclude(kits=kit)

    if request.method == "POST":
        if 'add_item' in request.POST:
            item_id = request.POST.get('item_id')
            if item_id:
                item = get_object_or_404(InventoryItem, pk=item_id)
                kit.items.add(item)
                messages.success(request, f"Item '{item.item_name}' added to kit '{kit.name}'.")
            create_log_entry(
                    user=request.user,
                    item=item,
                    action="added_to_kit",
                    details=f"Item '{item.item_name}' (UID {item.uid_no}) added to Kit '{kit.name}'."
                )



            return redirect('inventory:kit_items_list', pk=kit.pk)

        elif 'remove_item' in request.POST:
            item_id = request.POST.get('item_id')
            if item_id:
                item = get_object_or_404(InventoryItem, pk=item_id)
                kit.items.remove(item)
                messages.warning(request, f"Item '{item.item_name}' removed from kit '{kit.name}'.")
                return redirect('inventory:kit_items_list', pk=kit.pk)

    return render(request, 'inventory/kit_items_list.html', {
        'kit': kit,
        'available_items': available_items,
    })


@login_required(login_url='inventory:login')
def item_documents(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    documents = InventoryDocument.objects.filter(inventory_item=item)

    if request.method == 'POST':
        form = InventoryDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.inventory_item = item
            document.uploaded_by = request.user
            document.save()
            messages.success(request, "Document uploaded successfully.")

            # ✅ Log the uploaded document
            create_log_entry(
                user=request.user,
                item=item,
                action="document_uploaded",
                details=f"Document '{document.file.name}' uploaded for item '{item.item_name}' (UID {item.uid_no})."
            )

            return redirect('inventory:item_documents', item_id=item_id)
        else:
            messages.error(request, f"Form Error: {form.errors}")

    # This section runs for GET requests or if the form submission was invalid
    document_form = InventoryDocumentForm()
    item_form = InventoryForm(instance=item)

    context = {
        'item': item,
        'item_form': item_form,
        'document_form': document_form,
        'documents': documents,
    }
    return render(request, 'inventory/item_documents.html', context)

def get_category_prefix(request, category_id):
    """
    Returns the prefix for a given ItemCategory via JSON.
    """
    try:
        category = ItemCategory.objects.get(id=category_id)
        prefix = category.prefix
        return JsonResponse({'prefix': prefix})
    except ItemCategory.DoesNotExist:
        return JsonResponse({'error': 'Category not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='inventory:login')
def clear_scan_view(request):
    """
    Clears the OCR scan results by redirecting to a new, empty form.
    This function is intended to be used with a "Clear Scan" button.
    """
    return redirect('inventory:add_item')


def technical_data_view(request, uid):
    item = get_object_or_404(InventoryItem, uid_no=uid)
    if request.method == 'POST':
        form = TechnicalDataForm(request.POST)
        if form.is_valid():
            tech_data = form.save(commit=False)
            tech_data.inventory_item = item
            tech_data.save()
            return JsonResponse({'success': True})
    else:
        form = TechnicalDataForm()

    return render(request, 'inventory/technical_data_form.html', {'form': form, 'item': item})

@login_required(login_url='inventory:login')
def technical_data_form(request, uid):
    """
    Handles the form for adding or updating technical data for a specific inventory item.
    """
    item = get_object_or_404(InventoryItem, uid_no=uid)

    try:
        technical_data_instance = TechnicalData.objects.get(item=item)
    except TechnicalData.DoesNotExist:
        technical_data_instance = None

    if request.method == 'POST':
        form = TechnicalDataForm(request.POST, instance=technical_data_instance)
        if form.is_valid():
            tech_data = form.save(commit=False)
            tech_data.item = item
            tech_data.save()
            
            messages.success(request, "Technical data saved successfully!")
            return redirect('inventory:dashboard')
    else:
        form = TechnicalDataForm(instance=technical_data_instance)

    return render(request, 'inventory/technical_data_form.html', {
        'form': form,
        'item': item
    })


@login_required(login_url='inventory:login')
def item_added_confirmation(request, uid):
    
    item = get_object_or_404(InventoryItem, uid_no=uid)
    context = {
        'item': item
    }
    return render(request, 'inventory/item_added_confirmation.html', context)

@login_required(login_url='inventory:login')
def transfer_inventory_items(request, pk):
    """
    Handles the display and submission of the transfer form for a single item.
    """
    item = get_object_or_404(InventoryItem, pk=pk)

    if not Location.objects.exists():
        messages.error(request, "No locations available for transfer. Please add locations in the Django admin first.")
        return redirect('inventory:dashboard')

    if request.method == 'POST':
        form = BatchTransferForm(request.POST)
        if form.is_valid():
            new_location = form.cleaned_data['new_location']
            
            # Change: Set the status to 'IN_TRANSIT' before saving
            item.location = new_location
            item.status = 'IN_TRANSIT'  # Set status to In Transit
            item.save()

            create_log_entry(
            user=request.user,
            item=item,
            action="transferred",
            details=f"Item '{item.item_name}' (UID: {item.uid_no}) transferred to '{new_location.name}'."
      )

            messages.success(request, f"Successfully initiated transfer for '{item.item_name}'. Status set to 'In Transit'.")
            return redirect('inventory:dashboard')
    else:
        # For a GET request, create the form with the item's ID in the hidden field.
        form = BatchTransferForm(initial={'item_ids': str(item.pk)})
    
    context = {
        'form_title': 'Transfer Asset',
        'item': item,
        'transfer_form': form,
    }
    return render(request, 'inventory/transfer_item.html', context)



def determine_item_type(item_name):
    """
    Categorizes an item as 'Technical' or 'General' based on its name.
    """
    technical_keywords = [
        'laptop', 'server', 'desktop', 'docking station', 'cpu', 'gpu',
        'pc', 'computer', 'macbook', 'workstation'
    ]
    if any(keyword in item_name.lower() for keyword in technical_keywords):
        return "Technical"
    return "General"

genai.configure(api_key=settings.GEMINI_API_KEY)

def _to_float(x):
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def _to_int(x):
    if x is None or x == "":
        return None
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    s = str(x).strip()
    try:
        v = float(s.replace(",", "."))
        if abs(v - round(v)) < 1e-6:
            return int(round(v))
    except Exception:
        pass
    return None


def _looks_like_code(s: str) -> bool:
    """Detect product codes like 'P-Smart-Box', 'K-19015-00-M/0998'."""
    if not s:
        return False
    s = str(s).strip()
    if "." in s:              # avoid decimals
        return False
    if len(s.split()) > 3:    # long text → not a code
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9\-_\/]+$", s)) and any(c.isalpha() for c in s)


def _is_long_text(s: str) -> bool:
    if not s:
        return False
    return len(str(s).strip().split()) >= 3


# ----------------- OCR Scan View -----------------
from django.contrib import messages

from django.contrib import messages

def ocr_scan_view(request):
    scanned_items = []
    invoice_number = ""
    total_estimated = Decimal("0.00")

    if request.method == "POST" and request.FILES.get("invoice_file"):
        uploaded_file = request.FILES["invoice_file"]
        scanned_items = get_text_from_image(uploaded_file)

        # ✅ Extract invoice from OCR
        invoice_number = extract_invoice_number(uploaded_file)

        # ✅ If user entered manually in Scan Now form, override OCR result
        manual_invoice_number = request.POST.get("invoice", "").strip()
        if manual_invoice_number:
            invoice_number = manual_invoice_number

        invoices_dir = os.path.join(settings.MEDIA_ROOT, "documents", "invoices")
        os.makedirs(invoices_dir, exist_ok=True)

        # ✅ Decide filename
        if invoice_number:
            safe_name = f"invoice-{invoice_number}"
        else:
            safe_name = timezone.now().strftime("invoice-%Y%m%d-%H%M%S")

        ext = os.path.splitext(uploaded_file.name)[1] or ".pdf"
        saved_invoice_path = os.path.join(invoices_dir, f"{safe_name}{ext}")

        # ✅ Block duplicate invoice number
        if invoice_number and os.path.exists(saved_invoice_path):
            messages.error(request, f"❌ Invoice with number {invoice_number} already exists. Upload rejected.")
            return redirect("inventory:ocr_scan")

        # ✅ Save new invoice file
        with open(saved_invoice_path, "wb+") as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        # ✅ Store relative path for add_items_from_invoice
        request.session["uploaded_invoice_path"] = os.path.relpath(saved_invoice_path, settings.MEDIA_ROOT)

        # ✅ calculate total
        for item in scanned_items:
            try:
                price = Decimal(str(item.get("total_price") or 0))
                total_estimated += price
            except Exception:
                continue

        
        create_log_entry(
            user=request.user,
            item=None,
            action="ocr_scan",
            details=(
                f"OCR scan performed on file '{uploaded_file.name}'. "
                f"Invoice number: {invoice_number or 'N/A'}, "
                f"Items detected: {len(scanned_items)}, "
                f"Estimated total: {total_estimated}"
            )
        )
       

    context = {
        "item_categories": ItemCategory.objects.all(),
        "status_choices": InventoryItem.STATUS_CHOICES,
        "locations": Location.objects.all(),
        "scanned_items": scanned_items,
        "scanned_invoice_number": invoice_number,  # prefill in main form if found
        "total_estimated": total_estimated,
    }
    return render(request, "inventory/scan_invoice_page.html", context)

def extract_invoice_number(image_file):
    # Try to detect "Invoice No", "Bill No", "Quote No" etc.
    try:
        text = run_easyocr_or_gemini(image_file)  # whichever OCR function you use
        match = re.search(r'(Invoice|Bill|Quote)\s*[:\-]?\s*(\w+)', text, re.IGNORECASE)
        if match:
            return match.group(2)
        return ""
    except:
        return ""
    

    
def invoice_scan_results(request):
    categories = Category.objects.all()
    statuses = Status.objects.all()
    return render(request, "inventory/invoice_results.html", {
        "categories": categories,
        "statuses": statuses,
        "scanned_items": [],  # will be filled after OCR
    })


def parse_extracted_data(text):
    """
    Parses OCR text and assigns category_id by checking against DB categories.
    """
    items = []
    lines = text.split("\n")

    # Fetch categories
    categories = list(ItemCategory.objects.all())

    # Precompute lowercase names
    cat_names = {c.name.lower(): c.id for c in categories}

    item_pattern = re.compile(r"(.+?)\s+(\d+)\s+([\d.]+)")

    for line in lines:
        match = item_pattern.search(line)
        if not match:
            continue

        description = match.group(1).strip()
        quantity = int(match.group(2))
        unit_price = float(match.group(3))

        # Default → None (template selects "Other")
        category_id = None
        desc_lower = description.lower()

        # ✅ 1. Exact match
        if desc_lower in cat_names:
            category_id = cat_names[desc_lower]
        else:
            # ✅ 2. Whole-word match
            for cat in categories:
                if re.search(rf"\b{re.escape(cat.name.lower())}\b", desc_lower):
                    category_id = cat.id
                    break

        items.append({
            "category_id": category_id,
            "item_name": description.split()[0],  # crude fallback for name
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": quantity * unit_price,
            "serial_number": "N/A",
        })

    # Fallback sample if no items parsed
    if not items:
        items = [
            {"category_id": None, "item_name": "Laptop Charger",
             "description": "12V ,3Amp Charger", "quantity": 1,
             "unit_price": 50.00, "total_price": 50.00, "serial_number": "SN123"},
            {"category_id": None, "item_name": "HDMI Cable",
             "description": "HDMI Cable", "quantity": 2,
             "unit_price": 15.00, "total_price": 30.00, "serial_number": "SN124"},
        ]

    return items

class ScannedItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['invoice_number', 'category', 'serial_number', 'location', 'status', 'project', 'item_name', 'description', 'quantity', 'price']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make mandatory fields required
        self.fields['invoice_number'].required = True
        self.fields['category'].required = True
        self.fields['serial_number'].required = True
        self.fields['location'].required = True
        self.fields['status'].required = True
        self.fields['project'].required = True