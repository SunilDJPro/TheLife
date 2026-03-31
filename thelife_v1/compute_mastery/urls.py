"""Compute Mastery URL patterns — all under /mastery/ prefix."""
from django.urls import path
from . import views

app_name = 'compute_mastery'

urlpatterns = [
    # Problem browsing
    path('', views.problem_list, name='problem_list'),
    path('problem/new/', views.problem_create, name='problem_create'),
    path('problem/<slug:slug>/', views.problem_detail, name='problem_detail'),
    path('problem/<slug:slug>/edit/', views.problem_edit, name='problem_edit'),
    path('problem/<slug:slug>/delete/', views.problem_delete, name='problem_delete'),
    path('problem/<slug:slug>/test-cases/', views.test_case_manage, name='test_case_manage'),

    # Solutions
    path('problem/<slug:slug>/solutions/', views.solution_list, name='solution_list'),
    path('problem/<slug:slug>/solutions/compare/', views.solution_compare, name='solution_compare'),

    # API endpoints (AJAX)
    path('api/run/', views.api_run_code, name='api_run'),
    path('api/submit/', views.api_submit_code, name='api_submit'),
    path('judge/status/<str:job_id>/', views.judge_poll_status, name='judge_status'),
]
