from django.urls import path
from . import views

app_name = 'activities'

urlpatterns = [
    path('', views.activity_log_list, name='log_list'),
    path('create/', views.activity_log_create, name='log_create'),
    path('<uuid:log_id>/edit/', views.activity_log_edit, name='log_edit'),
    path('<uuid:log_id>/delete/', views.activity_log_delete, name='log_delete'),
    path('quick-log/', views.quick_log_save, name='quick_log'),
    path('types/', views.get_activity_types, name='get_types'),
    path('search/', views.search_activities, name='search'),
    path('metadata-form/', views.get_metadata_form, name='metadata_form'),
    path('recurring/', views.recurring_task_list, name='recurring_tasks'),
    path('recurring/<uuid:task_id>/log/', views.recurring_task_log, name='recurring_log'),
    path('recurring/<uuid:task_id>/delete/', views.recurring_task_delete, name='recurring_delete'),
]
