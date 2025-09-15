# inventory_management/inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory' 

urlpatterns = [
   
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),
    path('ocr_scan/', views.ocr_scan_view, name='ocr_scan'),
    path('save_scanned_items/', views.save_scanned_items, name='save_scanned_items'),
    path('clear-scan/', views.clear_scan_view, name='clear_scan'), # New path for clearing the page
    path('import/save/', views.save_imported_items, name='save_imported_items'),
    path('ocr_review/', views.ocr_review, name='ocr_review'),
    path('import/', views.import_items_view, name='import'),
    path('import/submit/', views.import_items_submit, name='import_items_submit'),
    path('import/review/', views.import_review, name='import_review'),
    path('import/save/', views.save_imported_items, name='save_imported_items'),
    path('import/get_new_uid/', views.get_new_uid, name='get_new_uid'),
    path('group/', views.group_view, name='group_view'),
    path('kit/<int:pk>/items/', views.kit_items_list, name='kit_items_list'),
    path('kit/<int:pk>/add/', views.add_item_to_kit, name='add_item_to_kit'),
    path('kit/<int:pk>/remove/<int:item_pk>/', views.remove_item_from_kit, name='remove_item_from_kit'),
     path('create-kit/', views.create_kit, name='create_kit'),
    
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('add_item/', views.add_item_view, name='add_item'),
    path('edit/<int:pk>/', views.edit_item, name='edit_item'),
    path('details/<int:pk_or_uid>/', views.item_details, name='item_details'),
    #path('delete/<int:pk>/', views.delete_item_by_pk, name='delete_item_by_pk'),
    path('delete/<int:pk>/', views.delete_item_view, name='delete_item'),
    path('batch-transfer-item/', views.batch_transfer_items, name='batch_transfer_items'), 
    path('batch-delete-items/', views.batch_delete_items, name='batch_delete_items'), 
    #path('status-check/', views.status_check, name='status_check'),
    path("get-category-prefix/<int:category_id>/", views.get_category_prefix, name="get_category_prefix"),
     path("add-items-from-invoice/", views.add_items_from_invoice, name="add_items_from_invoice"),
     path('delete-items/', views.delete_items_confirm, name='delete_items_confirm'),
      path("undo-delete/<int:pk>/", views.undo_delete, name="undo_delete"),
      
    path("undo-last-deletion/", views.undo_last_deletion, name="undo_last_deletion"),

     
     path('add/technical-data/<uuid:uid>/', views.technical_data_view, name='technical_data_form'),
     path('technical_data_form/<uuid:uid>/', views.technical_data_form, name='technical_data_form'),
      
    path('item_added/<uuid:uid>/', views.item_added_confirmation, name='item_added_confirmation'),
    
    path('inventory/add_technical_data/<slug:uid>/', views.technical_data_form, name='technical_data_form'),
         
    path('transfer/<int:pk>/', views.transfer_inventory_items, name='transfer_item_by_pk'),
   

    path('modify/', views.modify_item, name='modify_item'),
    

   
   path('item/<int:item_id>/documents/', views.item_documents, name='item_documents'), 
    path('document/delete/<int:item_id>/<int:doc_id>/', views.delete_document, name='delete_document'), 
    path("get-category-prefix/<int:category_id>/", views.get_category_prefix, name="get_category_prefix"),
    path('import_items/', views.import_items_view, name='import_items'),

  
    
    
    path('export/all-logs-excel/', views.export_all_logs_excel, name='export_all_logs_excel'),
     path('export/', views.export_inventory, name='export_inventory'),
     path('import_items/submit/', views.import_items_submit, name='import_items_submit'),
     path('import/review/', views.import_review, name='import_review'),


  
    path('logs/', views.inventory_logs, name='inventory_logs'),
    path('add-items-from-invoice/', views.add_items_from_invoice, name='add_items_from_invoice'),
    
    path('logs/clear_all/', views.clear_all_logs, name='clear_all_logs'),
    path('export/excel/', views.export_selected_items_to_excel, name='export_selected_items_to_excel'),
]
