from django.urls import path
from . import views

app_name = 'risk'

urlpatterns = [
    # Risk Management
    path('', views.RiskListView.as_view(), name='risk_list'),
    path('create/', views.CreateRiskView.as_view(), name='create_risk'),
    path('<uuid:pk>/', views.RiskDetailView.as_view(), name='risk_detail'),
    path('<uuid:pk>/update/', views.UpdateRiskView.as_view(), name='update_risk'),
    path('<uuid:pk>/assessment/', views.create_assessment, name='create_assessment'),
    path('<uuid:pk>/mitigation/', views.create_mitigation, name='create_mitigation'),
    path('<uuid:pk>/monitoring/', views.create_monitoring, name='create_monitoring'),
    path('<uuid:pk>/incident/', views.report_incident, name='report_incident'),
    path('search/', views.risk_search, name='risk_search'),
    path('dashboard/', views.risk_dashboard, name='risk_dashboard'),
    path('reports/', views.risk_reports, name='risk_reports'),
    path('categories/', views.manage_categories, name='manage_categories'),
    
    # Conflict of Interest
    path('coi-declarations/', views.ConflictOfInterestListView.as_view(), name='coi_declarations'),
    path('coi-declarations/<uuid:pk>/', views.ConflictOfInterestDetailView.as_view(), name='coi_detail'),
    path('coi-declarations/create/', views.ConflictOfInterestCreateView.as_view(), name='coi_create'),
    path('coi-declarations/<uuid:pk>/review/', views.review_coi, name='coi_review'),
    
    # Whistleblower Portal
    path('whistleblower-reports/', views.WhistleblowerReportListView.as_view(), name='whistleblower_reports'),
    path('whistleblower-reports/<uuid:pk>/', views.WhistleblowerReportDetailView.as_view(), name='whistleblower_detail'),
    path('whistleblower-reports/create/', views.create_whistleblower_report, name='whistleblower_create'),
    path('whistleblower-reports/<uuid:pk>/investigate/', views.investigate_whistleblower_report, name='whistleblower_investigate'),
    
    # Compliance
    path('compliance-requirements/', views.ComplianceRequirementListView.as_view(), name='compliance_requirements'),
    path('compliance-requirements/<uuid:pk>/', views.ComplianceRequirementDetailView.as_view(), name='compliance_detail'),
    path('compliance-audits/', views.ComplianceAuditListView.as_view(), name='compliance_audits'),
    path('compliance-audits/<uuid:pk>/', views.ComplianceAuditDetailView.as_view(), name='compliance_audit_detail'),
    
    # Board Evaluation
    path('board-evaluations/', views.BoardEvaluationListView.as_view(), name='board_evaluations'),
    path('board-evaluations/<uuid:pk>/', views.BoardEvaluationDetailView.as_view(), name='board_evaluation_detail'),
    path('board-evaluations/create/', views.BoardEvaluationCreateView.as_view(), name='board_evaluation_create'),
    path('director-evaluations/<uuid:pk>/', views.DirectorEvaluationDetailView.as_view(), name='director_evaluation_detail'),
    path('director-evaluations/<uuid:pk>/update/', views.DirectorEvaluationUpdateView.as_view(), name='director_evaluation_update'),
    
    # Compliance Archive
    path('compliance-archives/', views.ComplianceArchiveListView.as_view(), name='compliance_archives'),
    path('compliance-archives/<uuid:pk>/', views.ComplianceArchiveDetailView.as_view(), name='compliance_archive_detail'),
    
    # Compliance Attendance
    path('compliance-attendance/', views.ComplianceAttendanceListView.as_view(), name='compliance_attendance'),
    path('compliance-attendance/create/', views.ComplianceAttendanceCreateView.as_view(), name='compliance_attendance_create'),
    path('compliance-attendance/<uuid:pk>/update/', views.ComplianceAttendanceUpdateView.as_view(), name='compliance_attendance_update'),
]
