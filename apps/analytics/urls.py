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
    path('board-performance/', views.board_performance_analytics, name='board_performance'),
    path('compliance-scorecard/', views.compliance_scorecard, name='compliance_scorecard'),
    path('attendance-participation/', views.attendance_participation_analytics, name='attendance_participation'),
    path('decision-tracking/', views.decision_tracking_analytics, name='decision_tracking'),

    # Compliance Scorecards
    path('compliance-scorecards/', views.ComplianceScorecardListView.as_view(), name='compliance_scorecards'),
    path('compliance-scorecards/<uuid:pk>/', views.ComplianceScorecardDetailView.as_view(), name='compliance_scorecard_detail'),
    path('compliance-scorecards/create/', views.ComplianceScorecardCreateView.as_view(), name='compliance_scorecard_create'),

    # Attendance Analytics
    path('attendance-analytics/', views.AttendanceAnalyticsListView.as_view(), name='attendance_analytics_list'),
    path('attendance-analytics/<uuid:pk>/', views.AttendanceAnalyticsDetailView.as_view(), name='attendance_analytics_detail'),

    # Decision Tracking
    path('decisions/', views.DecisionTrackingListView.as_view(), name='decision_tracking'),
    path('decisions/<uuid:pk>/', views.DecisionTrackingDetailView.as_view(), name='decision_detail'),
    path('decisions/create/', views.DecisionTrackingCreateView.as_view(), name='decision_create'),
    path('decisions/<uuid:pk>/update/', views.DecisionTrackingUpdateView.as_view(), name='decision_update'),

    # Custom Reports
    path('reports/', views.analytics_reports, name='reports'),
    path('reports/custom/', views.custom_report_builder, name='custom_report_builder'),
    path('custom-reports/', views.CustomReportListView.as_view(), name='custom_reports'),
    path('custom-reports/<uuid:pk>/', views.CustomReportDetailView.as_view(), name='custom_report_detail'),
    path('custom-reports/create/', views.CustomReportCreateView.as_view(), name='custom_report_create'),
    path('custom-reports/<uuid:pk>/generate/', views.CustomReportGenerateView.as_view(), name='custom_report_generate'),

    # Data export
    path('export/', views.export_analytics_data, name='export_data'),

    # API endpoints
    path('api/data/', views.analytics_api_data, name='api_data'),
    path('api/live/', views.analytics_live_data, name='live_data'),
    
    # Governance Dashboards
    path('governance-dashboards/', views.GovernanceDashboardListView.as_view(), name='governance_dashboards'),
    path('governance-dashboards/<uuid:pk>/', views.GovernanceDashboardDetailView.as_view(), name='governance_dashboard_detail'),
    path('governance-dashboards/create/', views.GovernanceDashboardCreateView.as_view(), name='governance_dashboard_create'),
    path('governance-dashboards/<uuid:pk>/update/', views.GovernanceDashboardUpdateView.as_view(), name='governance_dashboard_update'),
    
    # Analytics Widgets
    path('widgets/', views.AnalyticsWidgetListView.as_view(), name='widgets'),
    path('widgets/create/', views.AnalyticsWidgetCreateView.as_view(), name='widget_create'),
    path('widgets/<uuid:pk>/update/', views.AnalyticsWidgetUpdateView.as_view(), name='widget_update'),
]
