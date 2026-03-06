from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Audit Log URLs
    path('', views.AuditLogListView.as_view(), name='audit_list'),
    path('dashboard/', views.audit_dashboard, name='audit_dashboard'),
    path('<uuid:pk>/', views.AuditLogDetailView.as_view(), name='audit_detail'),
    path('export/', views.export_audit_logs, name='export_logs'),
    path('cleanup/', views.cleanup_old_logs, name='cleanup'),
    
    # Retention Policies (staff only)
    path('retention/', views.retention_policies, name='retention_policies'),
]
