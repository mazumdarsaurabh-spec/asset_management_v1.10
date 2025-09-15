# inventory_management/inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError, transaction
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User # Import User model explicitly for create_log_entry fallback
import json
from django.utils import timezone
from django.core.exceptions import FieldDoesNotExist 
from .forms import BatchDeleteForm, StatusCheckForm, ModifyItemForm,EditItemForm,AddItemForm,FilterForm,LoginForm,InventoryLogFilterForm
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from openpyxl.styles import Font, Alignment
from django.contrib.auth import get_user_model
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from datetime import datetime, date # Import date as well for datetime.date objects
import logging # Import logging

from .models import InventoryItem, Location, Project, InventoryLog,UIDCategorySequence,Document, ItemCategory # Added ItemCategory import
from django.contrib.auth.forms import UserCreationForm # Ensure UserCreationForm is imported for registration

logger = logging.getLogger(__name__) # Get a logger instance

User = get_user_model() # Get the User model

# Custom JSON encoder to handle datetime and date objects
class DjangoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

# Helper function to create log entries (ensure this is defined in your views.py)
def create_log_entry(user, item, action, details, uid_number_for_log=None):
    try:
        InventoryLog.objects.create(
            user=user,
            inventory_item=item, # Corrected: Use inventory_item to match your model
            action=action,
            details=details,
            uid_number=uid_number_for_log if uid_number_for_log is not None else (item.uid_no if item else None)
        )
    except Exception as e:
        logger.error(f"Failed to create inventory log entry: {e}")
        # Optionally, you might want to log this to a file or another system
        # as it's a critical failure to log actions.
# --- USER AUTHENTICATION VIEWS ---

def user_login(request):
    """Handles user login."""
    if request.user.is_authenticated:
        # If user is already logged in, redirect them to the dashboard
        return redirect('inventory:dashboard') 

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST) # Use AuthenticationForm's specific constructor
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome, {username}!')
                create_log_entry(request.user, None, 'login', 'User logged in successfully.')
                return redirect('inventory:dashboard') # Redirect to dashboard on successful login
            else:
                # This block is usually hit if authenticate returns None (wrong credentials)
                messages.error(request, 'Invalid username or password.')
                # Pass request.user (AnonymousUser if not logged in) or None for logging
                create_log_entry(request.user, None, 'login_failed', f'Failed login attempt for username: {username}')
        else:
            messages.error(request, 'Please correct the errors below.')
            create_log_entry(request.user, None, 'login_failed', 'Failed login attempt due to form errors.')
    else:
        form = LoginForm() # Empty form for GET request

    context = {
        'form': form,
        'form_title': 'Login'
    }
    return render(request, 'inventory/login.html', context)


@login_required(login_url='inventory:login')
def user_logout(request):
    """Handles user logout."""
    # Log the user out and record the action
    create_log_entry(request.user, None, 'logout', 'User logged out.')
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('inventory:login') # Corrected: Use namespaced URL for login page

def user_register(request):
    """Handles new user registration."""
    if request.user.is_authenticated:
        # Prevent authenticated users from registering new accounts
        return redirect('inventory:dashboard') 

    if request.method == 'POST':
        form = UserCreationForm(request.POST) # Corrected: Use UserCreationForm
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful. You can now log in.')
            create_log_entry(user, None, 'register', f'New user registered: {user.username}')
            return redirect('inventory:login') # Corrected: Use namespaced URL for login page
        else:
            messages.error(request, 'Registration failed. Please correct the errors.')
            # You might log form errors here if needed
    else:
        form = UserCreationForm() # Corrected: Use UserCreationForm
    
    context = {
        'form': form,
        'form_title': 'Register Account'
    }
    return render(request, 'inventory/register.html', context)

# --- INVENTORY MANAGEMENT VIEWS ---

# User = get_user_model() # Already defined at the top

@login_required(login_url='inventory:login')
def dashboard_view(request):
    # Initialize FilterForm with GET data
    filter_form = FilterForm(request.GET or None) 
    items = InventoryItem.objects.all() 

    # Apply filtering based on form data if valid
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

    # Example: Sorting logic
    sort = request.GET.get('sort', 'item_name')
    direction = request.GET.get('direction', 'asc')
    
    if sort == 'location__name':
        if direction == 'desc':
            items = items.order_by('-location__name')
        else:
            items = items.order_by('location__name')
    elif sort == 'project__name':
        if direction == 'desc':
            items = items.order_by('-project__name')
        else:
            items = items.order_by('project__name')
    else:
        if direction == 'desc':
            sort = f'-{sort}'
        items = items.order_by(sort)

    # Pagination
    page_size = request.GET.get('page_size', 10)
    paginator = Paginator(items, page_size)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Fetch all locations, projects, and users for dropdowns/JSON data
    locations = Location.objects.all().order_by('name')
    projects = Project.objects.all().order_by('name')
    users = User.objects.all().order_by('username') # Fetch all users

    total_item_count = InventoryItem.objects.count() # Get total count for dashboard display

    context = {
        'filter_form': filter_form, # Ensure your filter form is passed if used
        'page_obj': page_obj,
        'page_sizes': [5, 10, 25, 50, 100], # Example page sizes
        'page_size': int(page_size), # Ensure page_size is an integer
        'sort': sort.lstrip('-'), # Remove '-' for template display
        'direction': direction,
        'locations': locations,
        'projects': projects,
        'users': users,
        'total_item_count': total_item_count, # Pass total item count

        # IMPORTANT: Convert querysets to JSON strings using json.dumps and model_to_dict
        # Use the custom DjangoJSONEncoder here
        'locations_json': json.dumps([model_to_dict(loc) for loc in locations], cls=DjangoJSONEncoder),
        'projects_json': json.dumps([model_to_dict(proj) for proj in projects], cls=DjangoJSONEncoder),
        'users_json': json.dumps([model_to_dict(user) for user in users], cls=DjangoJSONEncoder),
    }
    return render(request, 'inventory/dashboard.html', context)

@login_required(login_url='inventory:login')
def export_selected_items_to_excel(request):
    selected_ids_str = request.GET.get('ids', '') # Get the 'ids' parameter from the URL

    if not selected_ids_str:
        # If no IDs are provided from the frontend, return an error or all data as fallback
        # In your case, you want ONLY selected, so returning an error/blank is appropriate
        return HttpResponse("No items selected for export.", status=400)

    # Convert the comma-separated string of IDs to a list of integers
    try:
        selected_ids= [int(item_id.strip()) for item_id in selected_ids_str.split(',') if item_id.strip()]
    except ValueError:
        return HttpResponse("Invalid item IDs provided.", status=400)

    # Filter InventoryItem objects based on the selected IDs
    # THIS IS THE CRUCIAL PART THAT ENSURES ONLY SELECTED ITEMS ARE EXPORTED
    items_to_export = InventoryItem.objects.filter(id__in=selected_ids)
    # Check if any items were actually found for the given IDs
    if not items_to_export.exists():
        return HttpResponse("No items found matching the selected IDs.", status=404)

    # Prepare data for DataFrame
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
            'Date Added': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else 'N/A', # Using created_at
            'Created At': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else 'N/A', 
            'Updated At': item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else 'N/A',
        })

    import pandas as pd
    df = pd.DataFrame(data)

    # Create the Excel response
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Selected Items')
    output.seek(0) # Rewind to the beginning of the stream

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="selected_inventory_items.xlsx"'
    response.write(output.read())
    return response # Corrected: Added the missing return statement

    

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
                new_location_id = item_data.get('new_location') # Frontend sends 'new_location'
                new_project_id = item_data.get('project')      # Frontend sends 'project'
                # assigned_to_id = item_data.get('assigned_to') # If you add this to frontend, uncomment
                transfer_date_str = item_data.get('transfer_date')

                if not all([item_id, new_location_id, transfer_date_str]):
                    error_msg = f"Missing required data for item ID {item_id}. (new_location, transfer_date are required)"
                    logger.warning(f"Batch transfer failed for item {item_id}: {error_msg}")
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                    continue # Skip to next item

                try:
                    item = InventoryItem.objects.select_for_update().get(id=item_id)
                    
                    # Store old values for logging
                    old_location_name = item.location.name if item.location else "N/A"
                    old_project_name = item.project.name if item.project else "N/A"
                    # old_assigned_to_name = item.assigned_to.get_full_name() or item.assigned_to.username if item.assigned_to else "N/A"

                    new_location = Location.objects.get(id=new_location_id)
                    
                    new_project = None
                    if new_project_id:
                        try:
                            new_project = Project.objects.get(id=new_project_id)
                        except Project.DoesNotExist:
                            error_msg = f"Project with ID {new_project_id} not found for item ID {item_id}."
                            logger.error(error_msg)
                            failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                            continue # Skip to next item
                    
                    assigned_to_user = None
                    # If you add assigned_to to frontend, uncomment and adjust accordingly
                    # if assigned_to_id:
                    #     try:
                    #         assigned_to_user = User.objects.get(id=assigned_to_id)
                    #     except User.DoesNotExist:
                    #         error_msg = f"User with ID {assigned_to_id} not found for item ID {item_id}."
                    #         logger.error(error_msg)
                    #         failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                    #         continue # Skip to next item

                    transfer_date = datetime.strptime(transfer_date_str, '%Y-%m-%d').date()

                    # Update the item
                    item.location = new_location
                    item.project = new_project
                    # item.assigned_to = assigned_to_user # Uncomment if using assigned_to
                    item.last_transfer_date = transfer_date # Assuming this field exists and is a DateField
                    item.save()

                    # Create log entry
                    log_details = (
                        f"Transferred item '{item.item_name}' (UID: {item.uid_no}) "
                        f"from Location: '{old_location_name}' to '{new_location.name}'."
                    )
                    if new_project:
                        log_details += f" Project changed from '{old_project_name}' to '{new_project.name}'."
                    # if assigned_to_user: # Uncomment if using assigned_to
                    #     log_details += f" Assigned from '{old_assigned_to_name}' to '{assigned_to_user.get_full_name() or assigned_to_user.username}'."
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
                except ValueError as ve: # For datetime parsing errors
                    error_msg = f"Invalid date format for item ID {item_id}: {ve}. Use YYYY-MM-DD."
                    logger.error(error_msg)
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
                except Exception as e:
                    error_msg = f"An unexpected error occurred for item ID {item_id}: {e}"
                    logger.exception(error_msg) # Log full traceback for unexpected errors
                    failed_transfers_details.append(f"Item ID {item_id}: {error_msg}")
            
            # Final response based on overall success/failure
            if failed_transfers_details:
                response_message = f"Successfully transferred {successful_transfers_count} item(s). {len(failed_transfers_details)} item(s) failed: " + "; ".join(failed_transfers_details)
                messages.error(request, response_message) # Use messages for user feedback
                return JsonResponse({'success': False, 'message': response_message}, status=400)
            else:
                response_message = f"Successfully transferred {successful_transfers_count} asset(s)."
                messages.success(request, response_message) # Use messages for user feedback
                return JsonResponse({'success': True, 'message': response_message})

        except json.JSONDecodeError:
            logger.error("Batch transfer: Invalid JSON request body.")
            messages.error(request, "Invalid data received for transfer.")
            return JsonResponse({'success': False, 'message': 'Invalid JSON request body.'}, status=400)
        except Exception as e:
            logger.exception("An unexpected error occurred during batch transfer request processing.")
            messages.error(request, f"An unexpected server error occurred: {str(e)}")
            return JsonResponse({'success': False, 'message': f'An unexpected server error occurred: {str(e)}'}, status=500)
    
    logger.warning("Batch transfer: Invalid request method. Must be POST.")
    messages.error(request, "Invalid request method for transfer.")
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

# Placeholder for delete_item_by_pk (not used in dashboard, but kept for completeness)
def delete_item_by_pk(request, pk):
    pass

# MODIFIED: modify_item view to handle search and redirection
@login_required(login_url='inventory:login')
def modify_item(request):
    item = None
    form = ModifyItemForm(request.GET or None) # Use GET for search form

    if request.method == 'GET' and form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        if search_query:
            # Try to find item by UID or Serial Number
            try:
                item = InventoryItem.objects.get(Q(uid_no__iexact=search_query) | Q(serial_number__iexact=search_query))
                # If item found, redirect directly to its edit page
                return redirect('inventory:edit_item', pk=item.pk)
            except InventoryItem.DoesNotExist:
                messages.error(request, f"No asset found with UID or Serial Number: '{search_query}'. Please try again.")
            except InventoryItem.MultipleObjectsReturned:
                messages.warning(request, f"Multiple assets found for '{search_query}'. Please be more specific.")
    
    # If no item found, or no search query, or method is not GET, display the search form
    context = {
        'form': form,
        'item': item, # Will be None if no item found or no search performed
    }
    return render(request, 'inventory/modify_item.html', context)


@login_required(login_url='inventory:login')
def status_check(request):
    form = StatusCheckForm(request.GET or None)
    items = InventoryItem.objects.all()

    if form.is_valid():
        status_filter = form.cleaned_data.get('status')
        location_filter = form.cleaned_data.get('location')
        project_filter = form.cleaned_data.get('project')

        if status_filter:
            items = items.filter(status=status_filter)
        if location_filter:
            items = items.filter(location=location_filter)
        if project_filter:
            items = items.filter(project=project_filter)

    context = {
        'form': form,
        'items': items,
    }
    return render(request, 'inventory/status_check.html', context)

# Placeholder for transfer_inventory_items (not used in dashboard, but kept for completeness)
def transfer_inventory_items(request, pk):
    pass

@login_required(login_url='inventory:login')
@transaction.atomic
def batch_delete_items(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body) # Expecting JSON from frontend
            item_ids_to_delete = data.get('item_ids', []) # Get list of IDs
            reason = data.get('reason', '') # Get reason

            if not item_ids_to_delete:
                messages.error(request, "No items selected for deletion.")
                return JsonResponse({'success': False, 'message': 'No items selected for deletion.'}, status=400)

            # Ensure IDs are integers
            try:
                uids = [int(item_id) for item_id in item_ids_to_delete]
            except ValueError:
                messages.error(request, "Invalid item ID format provided for deletion.")
                return JsonResponse({'success': False, 'message': 'Invalid item ID format.'}, status=400)

            items_to_delete = InventoryItem.objects.filter(id__in=uids)

            if not items_to_delete.exists():
                messages.error(request, "No selected items found for deletion.")
                return JsonResponse({'success': False, 'message': 'No selected items found for deletion.'}, status=404)

            deleted_count = items_to_delete.count()
            
            # Log deletion for each item before deleting
            for item in items_to_delete:
                create_log_entry(
                    request.user, item, 'deleted', 
                    f"Item '{item.item_name}' (UID: {item.uid_no}) deleted. Reason: {reason}",
                    uid_number_for_log=item.uid_no
                )

            items_to_delete.delete() # Perform the deletion

            messages.success(request, f"Successfully deleted {deleted_count} asset(s). Reason: {reason}")
            return JsonResponse({'success': True, 'message': f"Successfully deleted {deleted_count} asset(s)."})

        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON request body for deletion.")
            return JsonResponse({'success': False, 'message': 'Invalid JSON request body.'}, status=400)
        except Exception as e:
            logger.exception("An unexpected error occurred during batch deletion.")
            messages.error(request, f"An unexpected error occurred during deletion: {str(e)}")
            return JsonResponse({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}, status=500)
    else:
        messages.error(request, "Invalid request method for deletion.")
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

# Placeholder for item_documents (not used in dashboard, but kept for completeness)
def item_documents(request, item_id):
    pass

# Placeholder for delete_document (not used in dashboard, but kept for completeness)
def delete_document(request, item_id, doc_id):
    pass

# Placeholder for export_all_logs_excel (not used in dashboard, but kept for completeness)
def export_all_logs_excel(request):
    pass

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
def add_item_view(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES)
        if form.is_valid():
            inventory_item = form.save(commit=False)
            inventory_item.created_by = request.user
            inventory_item.save()

            document_file = form.cleaned_data.get('document_file_upload')
            
            if document_file:
                InventoryDocument.objects.create(
                    inventory_item=inventory_item,
                    name=document_file.name,
                    file=document_file,
                    uploaded_by=request.user
                )
                messages.success(request, f"Asset '{inventory_item.item_name}' added successfully with document.")
            else:
                messages.success(request, f"Asset '{inventory_item.item_name}' added successfully without document.")

            # ✅ CORRECTED LINE: Redirect to a valid URL after a successful save
            return redirect('inventory:dashboard')
    else:
        form = InventoryForm()

    context = {
        'form': form,
    }
    return render(request, 'inventory/add_item.html', context)


@login_required(login_url='inventory:login') # Corrected: Use namespaced URL for login_url
def edit_item(request, pk):
    """Handles editing an existing inventory item."""
    item = get_object_or_404(InventoryItem.objects.select_related('location', 'project', 'category'), pk=pk) # Added 'category' to select_related
    documents = item.documents.all() # Fetch all related documents

    if request.method == 'POST':
        # Capture original values before form submission for logging changes
        original_values = {
            'item_name': item.item_name, 
            'category': item.category, # Store the ItemCategory object directly
            'uid_no': item.uid_no,
            'serial_number': item.serial_number, 
            'location': item.location, 
            'status': item.status,
            'description': item.description, 
            'project': item.project, 
            'quantity': item.quantity,
            'image': item.image.name if item.image else None, # Store image path/name
            'cpu': item.cpu, 
            'gpu': item.gpu, 
            'os': item.os, 
            'installed_software': item.installed_software,
        }

        form = EditItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            updated_item = form.save(commit=False) # Get the updated item instance

            changes = [] # List to store detected changes for logging

            # Iterate through changed fields to build a detailed log entry
            for field_name in form.changed_data:
                try:
                    model_field_instance = InventoryItem._meta.get_field(field_name)
                except FieldDoesNotExist: # Corrected: Use FieldDoesNotExist directly after import
                    logger.warning(f"Field '{field_name}' not found in InventoryItem model fields for logging.")
                    continue # Skip if field doesn't exist in model

                original_value = original_values.get(field_name)
                current_value = getattr(updated_item, field_name)

                display_original = original_value
                display_current = current_value

                # Special handling for ForeignKey fields (e.g., Location, Project)
                if isinstance(model_field_instance, models.ForeignKey):
                    if field_name == 'category': # Specific handling for category ForeignKey
                        display_original = original_value.name if original_value else 'None'
                        display_current = current_value.name if current_value else 'None'
                    else: # General ForeignKey handling
                        display_original = original_value.name if original_value else 'None'
                        display_current = current_value.name if current_value else 'None'
                # Special handling for FileField/ImageField
                elif isinstance(model_field_instance, (models.FileField, models.ImageField)):
                    new_file_uploaded = field_name in request.FILES
                    file_cleared = form.cleaned_data.get(f'clear_{field_name}') # Check if clear checkbox was ticked

                    if new_file_uploaded:
                        display_original = "existing file" if original_value else "no file"
                        display_current = f"new file: {request.FILES[field_name].name}"
                    elif file_cleared and original_value: # Only log if there was an original file and it was cleared
                        display_original = original_value
                        display_current = "file cleared"
                    else:
                        continue # If no new file and not cleared, no change in file field
                # Special handling for CharField with choices (like status)
                elif field_name == 'status':
                    # Use get_FIELD_display() for status field to get human-readable values
                    original_display = item.get_status_display() # Use 'item' (original instance) for original display
                    current_display = updated_item.get_status_display() # Use 'updated_item' for current display
                    if original_display != current_display: 
                        changes.append(f"Status: '{original_display}' to '{current_display}'")
                    continue # Already added, so continue to next field


                # Convert values to strings for comparison and logging, handle None/empty strings
                display_original_str = str(display_original) if display_original is not None and display_original != '' else 'Empty'
                display_current_str = str(current_value) if current_value is not None and current_value != '' else 'Empty'

                # Only add to changes if values are actually different
                if display_original_str != display_current_str:
                    changes.append(f"{model_field_instance.verbose_name.replace('_', ' ').title()}: '{display_original_str}' to '{display_current_str}'")

            updated_item.save() # Save the changes to the database

            # Handle document upload if provided
            document_file_upload = form.cleaned_data.get('document_file_upload')
            document_name = form.cleaned_data.get('document_name')
            if document_file_upload:
                Document.objects.create(
                    inventory_item=updated_item,
                    name=document_name if document_name else document_file_upload.name,
                    file=document_file_upload,
                    uploaded_by=request.user
                )
                create_log_entry(
                    request.user, updated_item, 'document_added',
                    f"Document '{document_name if document_name else document_file_upload.name}' uploaded for item {updated_item.item_name} (UID: {updated_item.uid_no}).",
                    uid_number_for_log=updated_item.uid_no
                )


            if changes:
                log_details = f"Updated item '{updated_item.item_name}' (UID: {updated_item.uid_no}). Changes: {'; '.join(changes)}."
                create_log_entry(request.user, updated_item, 'updated', log_details, uid_number_for_log=updated_item.uid_no)
                messages.success(request, f'Item "{updated_item.item_name}" (UID: {updated_item.uid_no}) updated successfully! Changes: {", ".join(changes)}.')
            else:
                messages.info(request, 'No changes detected for the item.')
            # Redirect to the dashboard after successful update
            return redirect('inventory:dashboard') 
        else:
            messages.error(request, "Failed to update item. Please correct the errors.")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        form = EditItemForm(instance=item) # Populate form with existing item data for GET request

    context = {
        'form': form,
        'item': item,
        'documents': documents, # Pass documents to the template
        'form_title': f'Edit Item: {item.item_name} ({item.uid_no})'
    }
    return render(request, 'inventory/edit_item.html', context)

@login_required(login_url='inventory:login')
def item_documents(request, item_id):
    """Handles displaying and uploading documents for a specific inventory item."""
    item = get_object_or_404(InventoryItem, pk=item_id)
    documents = item.documents.all() # Get all documents related to this item

    if request.method == 'POST':
        # This part handles document upload within the same view
        document_file = request.FILES.get('document_file')
        # MODIFIED: Get 'tag' instead of 'document_name'
        tag = request.POST.get('tag') 

        if document_file and tag: # Ensure both file and tag are present
            Document.objects.create(
                inventory_item=item,
                name=tag, # Use tag as the document name
                file=document_file,
                uploaded_by=request.user
            )
            create_log_entry(
                request.user, item, 'document_added',
                f"Document '{tag}' uploaded for item {item.item_name} (UID: {item.uid_no}).",
                uid_number_for_log=item.uid_no
            )
            messages.success(request, f"Document '{tag}' uploaded successfully!")
            return redirect('inventory:item_documents', item_id=item.pk)
        else:
            if not document_file:
                messages.error(request, "No document file selected for upload.")
            if not tag:
                messages.error(request, "Please select a TAG for the document.")


    context = {
        'item': item,
        'documents': documents,
        'form_title': f'Documents for {item.item_name} ({item.uid_no})'
    }
    return render(request, 'inventory/item_documents.html', context)

@login_required(login_url='inventory:login')
@require_POST # Ensures only POST requests are accepted for deletion
def delete_document(request, item_id, doc_id):
    """Handles deleting a specific document."""
    document = get_object_or_404(Document, pk=doc_id, inventory_item__pk=item_id)
    item = document.inventory_item # Get the related inventory item

    # Add a log entry before deleting the document
    create_log_entry(
        request.user, item, 'document_deleted',
        f"Document '{document.name}' deleted from item {item.item_name} (UID: {item.uid_no}).",
        uid_number_for_log=item.uid_no
    )
    
    document.delete()
    messages.success(request, f"Document '{document.name}' deleted successfully.")
    return redirect('inventory:item_documents', item_id=item.pk)


# Placeholder for export_all_logs_excel (not used in dashboard, but kept for completeness)
def export_all_logs_excel(request):
    pass

@login_required(login_url='inventory:login') # Corrected: Use namespaced URL for login_url
def item_details(request, pk):
    """Handles displaying details of a single inventory item."""
    item = get_object_or_404(InventoryItem, pk=pk)
    # Fetch all documents related to this item
    documents = item.documents.all() 
    context = {
        'item': item,
        'documents': documents, # Pass documents to the template
    }
    return render(request, 'inventory/item_details.html', context)