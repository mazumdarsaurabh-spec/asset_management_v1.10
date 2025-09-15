# inventory_management/inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory' 

urlpatterns = [
   
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),

    
    path('', views.dashboard_view, name='dashboard'), 
    path('add_item/', views.add_item_view, name='add_item'),
    path('edit/<int:pk>/', views.edit_item, name='edit_item'),
    path('details/<int:pk>/', views.item_details, name='item_details'),
    path('delete/<int:pk>/', views.delete_item_by_pk, name='delete_item_by_pk'),
    path('batch-transfer-item/', views.batch_transfer_items, name='batch_transfer_items'), 
    path('batch-delete-items/', views.batch_delete_items, name='batch_delete_items'), 
    path('status-check/', views.status_check, name='status_check'),

   
    path('transfer/<int:pk>/', views.transfer_inventory_items, name='transfer_item_by_pk'),
   

    path('modify/', views.modify_item, name='modify_item'),

   
    path('item/<int:item_id>/document/', views.item_document, name='item_document'), 
    path('document/delete/<int:item_id>/<int:doc_id>/', views.delete_document, name='delete_document'), 

  
    
    
    path('export/all-logs-excel/', views.export_all_logs_excel, name='export_all_logs_excel'),

  
    path('logs/', views.inventory_logs, name='inventory_logs'),
    
    path('logs/clear_all/', views.clear_all_logs, name='clear_all_logs'),
    path('export/excel/', views.export_selected_items_to_excel, name='export_selected_items_to_excel'),
]
