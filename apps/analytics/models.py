import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, Q
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User


class AnalyticsMetric(models.Model):
    """Core analytics metrics tracking"""

    METRIC_TYPES = [
        ('attendance', 'Meeting Attendance'),
        ('participation', 'Participation Rate'),
        ('engagement', 'Engagement Score'),
        ('documents', 'Document Activity'),
        ('voting', 'Voting Activity'),
        ('discussions', 'Discussion Activity'),
        ('notifications', 'Notification Activity'),
        ('system_usage', 'System Usage'),
        ('compliance', 'Compliance Metrics'),
        ('performance', 'Performance Metrics'),
        ('governance', 'Governance Metrics'),
        ('financial', 'Financial Metrics'),
        ('operational', 'Operational Metrics'),
        ('risk', 'Risk Metrics'),
    ]

    DATA_TYPES = [
        ('count', 'Count'),
        ('percentage', 'Percentage'),
        ('currency', 'Currency'),
        ('number', 'Number'),
        ('ratio', 'Ratio'),
        ('score', 'Score'),
    ]

    CATEGORIES = [
        ('governance', 'Governance'),
        ('financial', 'Financial'),
        ('operational', 'Operational'),
        ('compliance', 'Compliance'),
        ('risk', 'Risk'),
        ('performance', 'Performance'),
        ('meetings', 'Meetings'),
    ]

    FREQUENCY_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True, default='', help_text="Unique key for the metric")
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORIES, default='governance')
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='number')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')

    # Metric configuration
    is_active = models.BooleanField(default=True)
    target_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, help_text="Unit of measurement")
    
    # Visualization settings
    visualization_type = models.CharField(
        max_length=20,
        choices=[
            ('line', 'Line Chart'),
            ('bar', 'Bar Chart'),
            ('pie', 'Pie Chart'),
            ('gauge', 'Gauge'),
            ('number', 'Number Display'),
            ('table', 'Table'),
        ],
        default='line'
    )

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_metrics')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Analytics Metric'
        verbose_name_plural = 'Analytics Metrics'
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['metric_type', 'is_active']),
            models.Index(fields=['frequency', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.key})"


class AnalyticsDataPoint(models.Model):
    """Individual data points for metrics"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric = models.ForeignKey(AnalyticsMetric, on_delete=models.CASCADE, related_name='data_points')

    # Data values
    value = models.DecimalField(max_digits=15, decimal_places=4)
    value_text = models.CharField(max_length=200, blank=True)  # For non-numeric data
    timestamp = models.DateTimeField()

    # Context data
    context_data = models.JSONField(default=dict, blank=True, help_text="Additional context (user_id, meeting_id, etc.)")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Analytics Data Point'
        verbose_name_plural = 'Analytics Data Points'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['metric', '-timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['metric', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.metric.name} - {self.value} at {self.timestamp}"


class AnalyticsDashboard(models.Model):
    """Customizable analytics dashboards"""

    DASHBOARD_TYPES = [
        ('governance', 'Governance Dashboard'),
        ('financial', 'Financial Dashboard'),
        ('operational', 'Operational Dashboard'),
        ('compliance', 'Compliance Dashboard'),
        ('risk', 'Risk Dashboard'),
        ('performance', 'Performance Dashboard'),
        ('custom', 'Custom Dashboard'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES, default='custom')

    # Dashboard configuration
    layout_config = models.JSONField(default=dict, blank=True, help_text="Dashboard layout configuration")
    filters_config = models.JSONField(default=dict, blank=True, help_text="Default filters configuration")
    
    # Auto-refresh settings
    auto_refresh_enabled = models.BooleanField(default=False)
    auto_refresh_interval = models.PositiveIntegerField(default=300, help_text="Auto-refresh interval in seconds")

    # Access control
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False, help_text="Whether this is a default dashboard for the type")
    allowed_roles = models.JSONField(default=list, blank=True, help_text="List of allowed user roles")

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_dashboards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Analytics Dashboard'
        verbose_name_plural = 'Analytics Dashboards'
        ordering = ['dashboard_type', 'name']
        indexes = [
            models.Index(fields=['dashboard_type']),
            models.Index(fields=['is_default']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_dashboard_type_display()})"


class AnalyticsWidget(models.Model):
    """Dashboard widgets for displaying metrics"""

    WIDGET_TYPES = [
        ('line_chart', 'Line Chart'),
        ('bar_chart', 'Bar Chart'),
        ('pie_chart', 'Pie Chart'),
        ('area_chart', 'Area Chart'),
        ('metric_card', 'Metric Card'),
        ('table', 'Data Table'),
        ('heatmap', 'Heatmap'),
        ('gauge', 'Gauge Chart'),
        ('trend', 'Trend Indicator'),
        ('kpi_card', 'KPI Card'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(AnalyticsDashboard, on_delete=models.CASCADE, related_name='widgets')

    # Widget configuration
    title = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=6)
    height = models.PositiveIntegerField(default=4)
    
    # Visibility settings
    is_visible = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False, help_text="Pin widget to top of dashboard")

    # Data configuration
    metric = models.ForeignKey(AnalyticsMetric, on_delete=models.CASCADE, null=True, blank=True)
    data_config = models.JSONField(default=dict, blank=True, help_text="Widget data configuration")
    chart_config = models.JSONField(default=dict, blank=True, help_text="Chart-specific configuration")
    
    # Insight settings
    show_insights = models.BooleanField(default=True, help_text="Show AI-generated insights")
    insight_config = models.JSONField(default=dict, blank=True, help_text="Insight configuration")

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_widgets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Analytics Widget'
        verbose_name_plural = 'Analytics Widgets'
        ordering = ['-is_pinned', 'position_y', 'position_x']

    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"


class BoardAnalyticsSnapshot(models.Model):
    """Daily/weekly snapshots of board analytics"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot_date = models.DateField()
    snapshot_type = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ], default='daily')

    # Key metrics
    total_meetings = models.PositiveIntegerField(default=0)
    total_attendees = models.PositiveIntegerField(default=0)
    average_attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Document metrics
    total_documents = models.PositiveIntegerField(default=0)
    document_views = models.PositiveIntegerField(default=0)
    document_downloads = models.PositiveIntegerField(default=0)

    # Voting metrics
    total_votes = models.PositiveIntegerField(default=0)
    voting_participation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Discussion metrics
    total_discussions = models.PositiveIntegerField(default=0)
    discussion_participation = models.PositiveIntegerField(default=0)

    # System usage
    active_users = models.PositiveIntegerField(default=0)
    login_count = models.PositiveIntegerField(default=0)

    # Performance metrics
    system_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    average_response_time = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # in milliseconds

    # Detailed data
    raw_data = models.JSONField(default=dict, blank=True, help_text="Detailed metrics data")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Board Analytics Snapshot'
        verbose_name_plural = 'Board Analytics Snapshots'
        ordering = ['-snapshot_date', '-snapshot_type']
        unique_together = ['snapshot_date', 'snapshot_type']
        indexes = [
            models.Index(fields=['snapshot_date', 'snapshot_type']),
        ]

    def __str__(self):
        return f"{self.snapshot_type.title()} Snapshot - {self.snapshot_date}"


class UserAnalyticsProfile(models.Model):
    """User-specific analytics and engagement tracking"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='analytics_profile')

    # Engagement scores
    overall_engagement_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    meeting_participation_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    document_engagement_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discussion_participation_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Activity counts
    meetings_attended = models.PositiveIntegerField(default=0)
    documents_viewed = models.PositiveIntegerField(default=0)
    votes_cast = models.PositiveIntegerField(default=0)
    discussions_started = models.PositiveIntegerField(default=0)
    comments_made = models.PositiveIntegerField(default=0)

    # Time tracking
    total_time_online = models.PositiveIntegerField(default=0, help_text="Total time online in minutes")
    last_activity = models.DateTimeField(null=True, blank=True)

    # Preferences
    dashboard_preferences = models.JSONField(default=dict, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Analytics Profile'
        verbose_name_plural = 'User Analytics Profiles'
        indexes = [
            models.Index(fields=['-overall_engagement_score']),
            models.Index(fields=['last_activity']),
        ]

    def __str__(self):
        return f"Analytics Profile for {self.user.get_full_name()}"

    def update_engagement_score(self):
        """Calculate and update overall engagement score"""
        # Simple engagement calculation based on activity
        activities = (
            self.meetings_attended * 2 +
            self.documents_viewed * 1 +
            self.votes_cast * 3 +
            self.discussions_started * 2 +
            self.comments_made * 1.5
        )

        # Normalize to 0-100 scale
        self.overall_engagement_score = min(activities / 10, 100)
        self.save(update_fields=['overall_engagement_score'])


class AnalyticsReport(models.Model):
    """Generated analytics reports"""

    REPORT_TYPES = [
        ('meeting_summary', 'Meeting Summary Report'),
        ('attendance_report', 'Attendance Report'),
        ('engagement_report', 'Engagement Report'),
        ('document_usage', 'Document Usage Report'),
        ('system_performance', 'System Performance Report'),
        ('compliance_report', 'Compliance Report'),
        ('custom', 'Custom Report'),
    ]

    REPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    format = models.CharField(max_length=10, choices=REPORT_FORMATS, default='pdf')

    # Date range
    start_date = models.DateField()
    end_date = models.DateField()

    # Report content
    configuration = models.JSONField(default=dict, blank=True, help_text="Report configuration")
    data = models.JSONField(default=dict, blank=True, help_text="Report data")

    # File
    file = models.FileField(upload_to='analytics/reports/%Y/%m/', null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=[
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='generating')

    # Metadata
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ComplianceScorecard(models.Model):
    """Compliance scorecard tracking"""

    STATUS_CHOICES = [
        ('compliant', 'Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('partially_compliant', 'Partially Compliant'),
        ('not_applicable', 'Not Applicable'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Compliance metrics
    overall_score = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Category scores
    governance_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    financial_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    operational_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Details
    findings = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    # Metadata
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviewed_scorecards')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Compliance Scorecard'
        verbose_name_plural = 'Compliance Scorecards'
        ordering = ['-period_end']
    
    def __str__(self):
        return f"{self.period_start} to {self.period_end} - {self.overall_score}%"


class AttendanceAnalytics(models.Model):
    """Attendance and participation analytics"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.CASCADE, related_name='attendance_analytics')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_analytics')
    
    # Attendance metrics
    attended = models.BooleanField(default=True)
    arrived_late = models.BooleanField(default=False)
    left_early = models.BooleanField(default=False)
    participation_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Engagement
    questions_asked = models.PositiveIntegerField(default=0)
    comments_made = models.PositiveIntegerField(default=0)
    documents_reviewed = models.PositiveIntegerField(default=0)
    
    # Context
    meeting_duration = models.DurationField(null=True, blank=True)
    attendance_duration = models.DurationField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Attendance Analytics'
        verbose_name_plural = 'Attendance Analytics'
        unique_together = ['meeting', 'user']
        ordering = ['-meeting__scheduled_date']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.meeting.title}"


class DecisionTracking(models.Model):
    """Track decisions and their outcomes"""

    DECISION_TYPES = [
        ('strategic', 'Strategic Decision'),
        ('operational', 'Operational Decision'),
        ('financial', 'Financial Decision'),
        ('governance', 'Governance Decision'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    decision_type = models.CharField(max_length=20, choices=DECISION_TYPES)
    
    # Related to meeting or motion
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.SET_NULL, null=True, blank=True, related_name='decisions')
    motion = models.ForeignKey('voting.Motion', on_delete=models.SET_NULL, null=True, blank=True, related_name='decisions')
    
    # Status and outcome
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    outcome = models.TextField(blank=True, help_text="Final outcome of the decision")
    
    # Timeline
    decision_date = models.DateField(null=True, blank=True)
    implementation_date = models.DateField(null=True, blank=True)
    target_completion_date = models.DateField(null=True, blank=True)
    
    # Impact assessment
    impact_description = models.TextField(blank=True)
    success_metrics = models.TextField(blank=True)
    
    # Ownership
    decision_maker = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='decisions_made')
    implementer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='decisions_implemented')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Decision Tracking'
        verbose_name_plural = 'Decision Tracking'
        ordering = ['-decision_date']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


class CustomReport(models.Model):
    """Custom report builder"""

    REPORT_TYPES = [
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('comparative', 'Comparative Report'),
        ('trend', 'Trend Analysis'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    
    # Data sources
    data_sources = models.JSONField(default=list, blank=True, help_text="List of data sources for the report")
    
    # Configuration
    filters = models.JSONField(default=dict, blank=True, help_text="Filter configuration")
    groupings = models.JSONField(default=list, blank=True, help_text="Grouping configuration")
    calculations = models.JSONField(default=list, blank=True, help_text="Calculations to perform")
    
    # Scheduling
    schedule = models.CharField(max_length=50, blank=True, help_text="Cron-like schedule")
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Output
    output_format = models.CharField(max_length=10, choices=[
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ], default='pdf')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # File
    generated_file = models.FileField(upload_to='reports/custom/%Y/%m/', null=True, blank=True)
    
    # Ownership
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='custom_reports')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_generated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Custom Report'
        verbose_name_plural = 'Custom Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
