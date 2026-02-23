from django.urls import path
from . import views

app_name = 'skills'

urlpatterns = [
    path('', views.skill_list, name='skill_list'),
    path('create/', views.skill_create, name='skill_create'),
    path('<uuid:skill_id>/', views.skill_detail, name='skill_detail'),
    path('<uuid:skill_id>/edit/', views.skill_edit, name='skill_edit'),
    path('<uuid:skill_id>/activate/', views.skill_activate, name='skill_activate'),
    path('<uuid:skill_id>/resources/add/', views.resource_add, name='resource_add'),
    path('resources/<uuid:resource_id>/sessions/log/', views.session_log, name='session_log'),
]
