import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User

class RiskCategory(models.Model):
    """Risk categories for classification and organization"""

    CATEGORY_CHOICES = [
        ('strategic', 'Strategic Risk'),
        ('operational', 'Operational Risk'),
        ('financial', 'Financial Risk'),
        ('compliance', 'Compliance Risk'),
        ('reputational', 'Reputational Risk'),
        ('cybersecurity', 'Cybersecurity Risk'),
        ('market', 'Market Risk'),
        ('regulatory', 'Regulatory Risk'),
        ('environmental', 'Environmental Risk'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_risk_categories')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Risk Category'
        verbose_name_plural = 'Risk Categories'
        ordering = ['category_type', 'name']

    def __str__(self):
        return f"{self.get_category_type_display()} - {self.name}"

    @property
    def full_path(self):
        """Get full category path including parent categories"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return f"{self.get_category_type_display()} > {self.name}"

class Risk(models.Model):
    """Main risk model for identification and tracking"""

    STATUS_CHOICES = [
        ('identified', 'Identified'),
        ('assessed', 'Assessed'),
        ('mitigated', 'Mitigated'),
        ('monitored', 'Monitored'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated'),
    ]

    IMPACT_LEVEL_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    PROBABILITY_CHOICES = [
        ('very_low', 'Very Low'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('very_high', 'Very High'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(RiskCategory, on_delete=models.SET_NULL, null=True, related_name='risks')

    # Risk assessment
    impact_level = models.CharField(max_length=10, choices=IMPACT_LEVEL_CHOICES, default='medium')
    probability = models.CharField(max_length=10, choices=PROBABILITY_CHOICES, default='medium')
    risk_score = models.PositiveIntegerField(help_text="Calculated risk score (1-25)", default=1)

    # Status and management
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='identified')
    risk_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_risks')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_risks')

    # Financial impact
    potential_impact = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Potential financial impact in USD")
    potential_impact_description = models.TextField(blank=True)

    # Timestamps
    identified_date = models.DateField(default=timezone.now)
    target_resolution_date = models.DateField(null=True, blank=True)
    actual_resolution_date = models.DateField(null=True, blank=True)

    # Metadata
    identified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='identified_risks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Risk'
        verbose_name_plural = 'Risks'
        ordering = ['-risk_score', '-created_at']

    def __str__(self):
        return f"Risk {self.id}: {self.title}"

    @property
    def risk_level(self):
        """Calculate risk level based on score"""
        if self.risk_score >= 20:
            return 'Critical'
        elif self.risk_score >= 15:
            return 'High'
        elif self.risk_score >= 10:
            return 'Medium'
        elif self.risk_score >= 5:
            return 'Low'
        else:
            return 'Very Low'

    @property
    def days_overdue(self):
        """Calculate days past target resolution date"""
        if self.target_resolution_date and self.status != 'closed':
            days = (timezone.now().date() - self.target_resolution_date).days
            return max(0, days)
        return 0

    def calculate_risk_score(self):
        """Calculate risk score based on impact and probability"""
        impact_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        probability_scores = {'very_low': 1, 'low': 2, 'medium': 3, 'high': 4, 'very_high': 5}

        impact = impact_scores.get(self.impact_level, 2)
        prob = probability_scores.get(self.probability, 3)

        self.risk_score = impact * prob
        return self.risk_score

    def save(self, *args, **kwargs):
        """Calculate risk score before saving"""
        self.calculate_risk_score()
        super().save(*args, **kwargs)

class RiskAssessment(models.Model):
    """Detailed risk assessment with analysis"""

    ASSESSMENT_TYPE_CHOICES = [
        ('initial', 'Initial Assessment'),
        ('detailed', 'Detailed Assessment'),
        ('periodic', 'Periodic Review'),
        ('incident', 'Post-Incident Assessment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name='assessments')

    # Assessment details
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES, default='initial')
    assessment_date = models.DateField(default=timezone.now)

    # Detailed analysis
    root_causes = models.TextField(blank=True, help_text="Identified root causes")
    impact_analysis = models.TextField(blank=True, help_text="Detailed impact analysis")
    vulnerability_analysis = models.TextField(blank=True, help_text="Vulnerability assessment")
    existing_controls = models.TextField(blank=True, help_text="Current controls in place")
    control_effectiveness = models.TextField(blank=True, help_text="Effectiveness of existing controls")

    # Quantitative assessment
    impact_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Impact probability (0-1)")
    impact_severity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Impact severity (0-1)")

    # Recommendations
    recommended_actions = models.TextField(blank=True, help_text="Recommended actions")
    priority_level = models.CharField(max_length=10, choices=Risk.IMPACT_LEVEL_CHOICES, default='medium')

    # Assessment team
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='risk_assessments')
    reviewers = models.ManyToManyField(User, blank=True, related_name='reviewed_assessments')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Risk Assessment'
        verbose_name_plural = 'Risk Assessments'
        ordering = ['-assessment_date']

    def __str__(self):
        return f"{self.risk.title} - {self.get_assessment_type_display()} ({self.assessment_date})"

class RiskMitigation(models.Model):
    """Risk mitigation and treatment plans"""

    MITIGATION_TYPE_CHOICES = [
        ('accept', 'Accept Risk'),
        ('avoid', 'Avoid Risk'),
        ('transfer', 'Transfer Risk'),
        ('mitigate', 'Mitigate Risk'),
        ('monitor', 'Monitor Only'),
    ]

    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('implemented', 'Implemented'),
        ('effective', 'Effective'),
        ('ineffective', 'Ineffective'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name='mitigations')
    assessment = models.ForeignKey(RiskAssessment, on_delete=models.SET_NULL, null=True, blank=True, related_name='mitigations')

    # Mitigation details
    mitigation_type = models.CharField(max_length=20, choices=MITIGATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')

    # Implementation
    responsible_party = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mitigation_responsibilities')
    target_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)

    # Budget and resources
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    resources_required = models.TextField(blank=True)

    # Effectiveness measurement
    effectiveness_rating = models.PositiveIntegerField(null=True, blank=True, help_text="Effectiveness rating (1-5)", validators=[MinValueValidator(1), MaxValueValidator(5)])
    effectiveness_notes = models.TextField(blank=True)

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_mitigations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Risk Mitigation'
        verbose_name_plural = 'Risk Mitigations'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.risk.title} - {self.title}"

    @property
    def is_overdue(self):
        """Check if mitigation is overdue"""
        if self.target_completion_date and self.status not in ['implemented', 'effective', 'cancelled']:
            return timezone.now().date() > self.target_completion_date
        return False

class RiskMonitoring(models.Model):
    """Risk monitoring and review records"""

    MONITORING_TYPE_CHOICES = [
        ('regular', 'Regular Review'),
        ('incident', 'Incident Review'),
        ('audit', 'Audit Review'),
        ('escalation', 'Escalation Review'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name='monitoring_records')

    # Monitoring details
    monitoring_type = models.CharField(max_length=20, choices=MONITORING_TYPE_CHOICES, default='regular')
    monitoring_date = models.DateField(default=timezone.now)
    next_review_date = models.DateField(null=True, blank=True)

    # Current status
    current_status = models.TextField(help_text="Current risk status and developments")
    risk_score_change = models.IntegerField(default=0, help_text="Change in risk score (+/-)")
    new_risk_score = models.PositiveIntegerField(help_text="Updated risk score")

    # Actions taken
    actions_taken = models.TextField(blank=True)
    effectiveness_assessment = models.TextField(blank=True)

    # Recommendations
    recommendations = models.TextField(blank=True)
    escalation_required = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True)

    # Monitoring team
    monitored_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='risk_monitoring')
    reviewers = models.ManyToManyField(User, blank=True, related_name='reviewed_monitoring')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Risk Monitoring'
        verbose_name_plural = 'Risk Monitoring'
        ordering = ['-monitoring_date']

    def __str__(self):
        return f"{self.risk.title} - {self.get_monitoring_type_display()} ({self.monitoring_date})"

class RiskIncident(models.Model):
    """Risk incidents and occurrences"""

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('reported', 'Reported'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name='incidents')

    # Incident details
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='reported')

    # Incident data
    incident_date = models.DateTimeField(default=timezone.now)
    reported_date = models.DateTimeField(auto_now_add=True)
    resolution_date = models.DateTimeField(null=True, blank=True)

    # Impact assessment
    actual_impact = models.TextField(blank=True)
    financial_impact = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    lessons_learned = models.TextField(blank=True)

    # Response team
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_incidents')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    response_team = models.ManyToManyField(User, blank=True, related_name='incident_responses')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Risk Incident'
        verbose_name_plural = 'Risk Incidents'
        ordering = ['-incident_date']

    def __str__(self):
        return f"{self.risk.title} - Incident: {self.title}"
