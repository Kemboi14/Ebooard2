from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Main dashboard
    path('', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    path('dashboard/', views.AnalyticsDashboardView.as_view(), name='dashboard_alt'),

    # Analytics views
    path('meetings/', views.meeting_analytics, name='meeting_analytics'),
    path('documents/', views.document_analytics, name='document_analytics'),
    path('engagement/', views.user_engagement_analytics, name='user_engagement'),
    path('performance/', views.system_performance_analytics, name='system_performance'),
    path('voting/', views.voting_analytics, name='voting_analytics'),

    # Reports
    path('reports/', views.analytics_reports, name='reports'),

    # Data export
    path('export/', views.export_analytics_data, name='export_data'),

    # API endpoints
    path('api/data/', views.analytics_api_data, name='api_data'),
    path('api/live/', views.analytics_live_data, name='live_data'),
]
