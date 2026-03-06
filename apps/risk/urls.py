from django.urls import path
from . import views

app_name = 'risk'

urlpatterns = [
    path('', views.RiskListView.as_view(), name='risk_list'),
    path('create/', views.CreateRiskView.as_view(), name='create_risk'),
    path('<uuid:pk>/', views.RiskDetailView.as_view(), name='risk_detail'),
    path('<uuid:pk>/assessment/', views.create_assessment, name='create_assessment'),
    path('<uuid:pk>/mitigation/', views.create_mitigation, name='create_mitigation'),
    path('<uuid:pk>/monitoring/', views.create_monitoring, name='create_monitoring'),
    path('<uuid:pk>/incident/', views.report_incident, name='report_incident'),
    path('search/', views.risk_search, name='risk_search'),
    path('dashboard/', views.risk_dashboard, name='risk_dashboard'),
    path('reports/', views.risk_reports, name='risk_reports'),
    path('categories/', views.manage_categories, name='manage_categories'),
]
