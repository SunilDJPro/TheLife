from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('goals/<uuid:goal_id>/delete/', views.delete_goal, name='delete_goal'),
    path('push-subscription/', views.save_push_subscription, name='push_subscription'),
]
