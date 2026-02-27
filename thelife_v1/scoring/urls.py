from django.urls import path
from . import views

app_name = 'scoring'

urlpatterns = [
    path('', views.scoring_dashboard, name='dashboard'),
    path('detail/<str:date_str>/', views.score_detail, name='detail'),
    path('recalculate/', views.recalculate_score, name='recalculate'),
    path('llm-score/', views.run_llm_scoring, name='llm_score'),
    path('llm-batch/', views.run_llm_batch, name='llm_batch'),
    path('history/', views.score_history, name='history'),
    path('chart-data/', views.score_chart_data, name='chart_data'),
]
