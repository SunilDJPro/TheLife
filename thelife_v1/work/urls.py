from django.urls import path
from . import views

app_name = 'work'

urlpatterns = [
    path('', views.work_dashboard, name='dashboard'),
    path('profile/edit/', views.work_profile_edit, name='profile_edit'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<uuid:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<uuid:project_id>/edit/', views.project_edit, name='project_edit'),
    path('projects/<uuid:project_id>/deliverables/add/', views.deliverable_add, name='deliverable_add'),
    path('deliverables/<uuid:deliverable_id>/status/', views.deliverable_update_status, name='deliverable_status'),
    path('logs/create/', views.work_log_create, name='log_create'),
    path('logs/', views.work_log_list, name='log_list'),
    path('deliverables-for-project/', views.deliverables_for_project, name='deliverables_for_project'),
]
