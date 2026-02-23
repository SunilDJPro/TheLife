from django.urls import path
from . import views

app_name = 'entertainment'

urlpatterns = [
    path('', views.entertainment_list, name='list'),
    path('create/', views.entertainment_create, name='create'),
    path('<uuid:log_id>/edit/', views.entertainment_edit, name='edit'),
    path('<uuid:log_id>/delete/', views.entertainment_delete, name='delete'),
]
