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


class ComplianceRequirement(models.Model):
    """Compliance requirements and regulations"""

    CATEGORY_CHOICES = [
        ('gdpr', 'GDPR'),
        ('data_protection', 'Data Protection'),
        ('financial', 'Financial Regulation'),
        ('governance', 'Corporate Governance'),
        ('health_safety', 'Health & Safety'),
        ('environmental', 'Environmental'),
        ('employment', 'Employment Law'),
        ('tax', 'Tax Compliance'),
        ('reporting', 'Reporting Requirements'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('compliant', 'Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('partially_compliant', 'Partially Compliant'),
        ('not_applicable', 'Not Applicable'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    reference_number = models.CharField(max_length=50, blank=True, help_text="Regulation reference number")
    
    # Compliance status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='partially_compliant')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Dates
    effective_date = models.DateField(help_text="When this requirement became effective")
    review_date = models.DateField(help_text="Next review date")
    
    # Ownership
    compliance_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='compliance_requirements')
    
    # Score (0-100)
    compliance_score = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # GDPR specific fields
    gdpr_article = models.CharField(max_length=20, blank=True, help_text="GDPR Article number if applicable")
    data_subject_rights = models.TextField(blank=True, help_text="Data subject rights addressed")
    data_processing_purpose = models.TextField(blank=True, help_text="Purpose of data processing")
    lawful_basis = models.CharField(max_length=100, blank=True, help_text="Lawful basis for processing")
    
    # Local law compliance
    jurisdiction = models.CharField(max_length=100, blank=True, help_text="Applicable jurisdiction/country")
    local_law_reference = models.TextField(blank=True, help_text="References to local laws and regulations")
    
    # Documentation
    evidence_documents = models.ManyToManyField('documents.Document', blank=True, related_name='compliance_evidence')
    policy_document = models.ForeignKey('documents.Document', on_delete=models.SET_NULL, null=True, blank=True, related_name='compliance_policies')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compliance Requirement'
        verbose_name_plural = 'Compliance Requirements'
        ordering = ['priority', '-compliance_score', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class ComplianceAudit(models.Model):
    """Compliance audit records"""

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('findings', 'Findings Identified'),
        ('remediation', 'Remediation Required'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Audit details
    requirement = models.ForeignKey(ComplianceRequirement, on_delete=models.CASCADE, related_name='audits')
    audit_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Audit results
    score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    findings = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    # Audit team
    auditor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='conducted_audits')
    reviewed_by = models.ManyToManyField(User, blank=True, related_name='reviewed_audits')
    
    # Remediation
    remediation_plan = models.TextField(blank=True)
    remediation_due_date = models.DateField(null=True, blank=True)
    remediation_completed_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compliance Audit'
        verbose_name_plural = 'Compliance Audits'
        ordering = ['-audit_date']

    def __str__(self):
        return f"{self.title} - {self.audit_date}"


class ConflictOfInterestDeclaration(models.Model):
    """Conflict of interest declarations for board members"""

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('mitigated', 'Mitigated'),
        ('escalated', 'Escalated'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    declarant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='coi_declarations')
    
    # Declaration details
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Detailed description of the conflict of interest")
    
    # Type of conflict
    conflict_type = models.CharField(max_length=100, help_text="Type of conflict (e.g., financial, personal, business)")
    related_entity = models.CharField(max_length=200, blank=True, help_text="Name of related entity or individual")
    relationship_nature = models.TextField(blank=True, help_text="Nature of the relationship")
    
    # Severity and status
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Mitigation plan
    mitigation_plan = models.TextField(blank=True, help_text="Plan to mitigate the conflict")
    mitigation_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_mitigations')
    mitigation_approved_at = models.DateTimeField(null=True, blank=True)
    
    # Review
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_coi')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Meeting context
    related_meeting = models.ForeignKey('meetings.Meeting', on_delete=models.SET_NULL, null=True, blank=True, related_name='coi_declarations')
    
    # Timestamps
    declared_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Conflict of Interest Declaration'
        verbose_name_plural = 'Conflict of Interest Declarations'
        ordering = ['-declared_at']
        indexes = [
            models.Index(fields=['declarant', '-declared_at']),
            models.Index(fields=['status', '-declared_at']),
            models.Index(fields=['severity', '-declared_at']),
        ]
    
    def __str__(self):
        return f"{self.declarant.get_full_name() if self.declarant else 'Unknown'} - {self.title}"


class WhistleblowerReport(models.Model):
    """Anonymous whistleblower reports for reporting concerns"""

    CATEGORY_CHOICES = [
        ('fraud', 'Fraud'),
        ('corruption', 'Corruption'),
        ('harassment', 'Harassment'),
        ('discrimination', 'Discrimination'),
        ('safety', 'Safety Violation'),
        ('environmental', 'Environmental Concern'),
        ('financial', 'Financial Irregularity'),
        ('governance', 'Governance Issue'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('unfounded', 'Unfounded'),
        ('closed', 'Closed'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Report details
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Detailed description of the concern")
    
    # Anonymity
    is_anonymous = models.BooleanField(default=True)
    reporter_email = models.EmailField(blank=True, help_text="Optional email for follow-up (if not fully anonymous)")
    reporter_phone = models.CharField(max_length=20, blank=True, help_text="Optional phone for follow-up (if not fully anonymous)")
    
    # Incident details
    incident_date = models.DateField(null=True, blank=True, help_text="Date of the incident")
    location = models.CharField(max_length=200, blank=True, help_text="Location of the incident")
    individuals_involved = models.TextField(blank=True, help_text="Names of individuals involved (if known)")
    
    # Severity and status
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    
    # Attachments
    attachments = models.JSONField(null=True, blank=True, help_text="List of attached file IDs")
    
    # Investigation
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_reports')
    investigation_notes = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Whistleblower Report'
        verbose_name_plural = 'Whistleblower Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['category', '-created_at']),
        ]
    
    def __str__(self):
        anonymous = "Anonymous" if self.is_anonymous else "Reported"
        return f"{anonymous} - {self.title}"


class BoardEvaluation(models.Model):
    """Board evaluation and self-assessment"""

    EVALUATION_TYPE_CHOICES = [
        ('annual', 'Annual Evaluation'),
        ('quarterly', 'Quarterly Review'),
        ('special', 'Special Evaluation'),
        ('self_assessment', 'Self-Assessment'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Evaluation details
    evaluation_type = models.CharField(max_length=20, choices=EVALUATION_TYPE_CHOICES)
    evaluation_period_start = models.DateField(help_text="Start date of evaluation period")
    evaluation_period_end = models.DateField(help_text="End date of evaluation period")
    title = models.CharField(max_length=200)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Overall assessment
    overall_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    overall_rating = models.CharField(max_length=20, blank=True, help_text="Overall rating (e.g., Excellent, Good, Needs Improvement)")
    summary = models.TextField(help_text="Executive summary of the evaluation")
    
    # Strengths and areas for improvement
    strengths = models.TextField(blank=True, help_text="Board strengths identified")
    areas_for_improvement = models.TextField(blank=True, help_text="Areas requiring improvement")
    recommendations = models.TextField(blank=True, help_text="Recommendations for improvement")
    
    # Governance assessment
    governance_effectiveness = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    strategic_oversight = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    risk_management = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Board composition
    composition_assessment = models.TextField(blank=True, help_text="Assessment of board composition and diversity")
    independence_assessment = models.TextField(blank=True, help_text="Assessment of board independence")
    
    # Review and approval
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_board_evaluations')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_board_evaluations')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Documentation
    supporting_documents = models.ManyToManyField('documents.Document', blank=True, related_name='board_evaluations')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_board_evaluations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Board Evaluation'
        verbose_name_plural = 'Board Evaluations'
        ordering = ['-evaluation_period_end']
        indexes = [
            models.Index(fields=['evaluation_type', '-evaluation_period_end']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.get_evaluation_type_display()} - {self.evaluation_period_end.strftime('%Y')}"
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage based on filled fields"""
        total_fields = 7  # Count of key fields to track
        filled_fields = 0
        if self.overall_score: filled_fields += 1
        if self.overall_rating: filled_fields += 1
        if self.summary: filled_fields += 1
        if self.strengths: filled_fields += 1
        if self.areas_for_improvement: filled_fields += 1
        if self.recommendations: filled_fields += 1
        if self.governance_effectiveness: filled_fields += 1
        return (filled_fields / total_fields) * 100 if total_fields > 0 else 0


class DirectorEvaluation(models.Model):
    """Individual director evaluation as part of board evaluation"""

    RATING_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('satisfactory', 'Satisfactory'),
        ('needs_improvement', 'Needs Improvement'),
        ('unsatisfactory', 'Unsatisfactory'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board_evaluation = models.ForeignKey(BoardEvaluation, on_delete=models.CASCADE, related_name='director_evaluations')
    director = models.ForeignKey(User, on_delete=models.CASCADE, related_name='evaluations')
    
    # Self-assessment
    self_rating = models.CharField(max_length=20, choices=RATING_CHOICES, blank=True)
    self_assessment = models.TextField(blank=True, help_text="Director's self-assessment")
    
    # Peer assessment
    peer_rating = models.CharField(max_length=20, choices=RATING_CHOICES, blank=True)
    peer_feedback = models.TextField(blank=True, help_text="Peer feedback summary")
    
    # Board chair assessment
    chair_rating = models.CharField(max_length=20, choices=RATING_CHOICES, blank=True)
    chair_feedback = models.TextField(blank=True, help_text="Board chair's feedback")
    
    # Overall rating
    overall_rating = models.CharField(max_length=20, choices=RATING_CHOICES, blank=True)
    overall_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Specific competencies
    governance_knowledge = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    strategic_thinking = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    financial_literacy = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    industry_expertise = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    communication = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    participation = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    
    # Development needs
    development_needs = models.TextField(blank=True, help_text="Identified development needs")
    training_recommendations = models.TextField(blank=True, help_text="Training and development recommendations")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Director Evaluation'
        verbose_name_plural = 'Director Evaluations'
        ordering = ['board_evaluation', 'director']
        unique_together = ['board_evaluation', 'director']
    
    def __str__(self):
        return f"{self.director.get_full_name()} - {self.board_evaluation.get_evaluation_type_display()}"


class ComplianceAttendance(models.Model):
    """Track compliance-related attendance for meetings and governance events"""

    ATTENDANCE_STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('excused', 'Excused'),
        ('late', 'Late'),
        ('remote', 'Remote/Video'),
    ]

    COMPLIANCE_TYPE_CHOICES = [
        ('statutory', 'Statutory Meeting'),
        ('board', 'Board Meeting'),
        ('committee', 'Committee Meeting'),
        ('training', 'Compliance Training'),
        ('audit', 'Audit Meeting'),
        ('risk', 'Risk Committee Meeting'),
        ('other', 'Other Compliance Event'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User and meeting
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='compliance_attendance')
    meeting = models.ForeignKey(
        'meetings.Meeting',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_attendance'
    )
    
    # Compliance details
    compliance_type = models.CharField(max_length=20, choices=COMPLIANCE_TYPE_CHOICES, default='board')
    attendance_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default='present')
    
    # Duration tracking
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Duration of attendance in minutes")
    
    # Excuse details
    is_excused = models.BooleanField(default=False)
    excuse_reason = models.TextField(blank=True, help_text="Reason for absence if excused")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_excuses',
        help_text="Who approved the excuse"
    )
    
    # Notes
    notes = models.TextField(blank=True, help_text="Additional notes about attendance")
    
    # Timestamps
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_compliance_attendance'
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Compliance Attendance'
        verbose_name_plural = 'Compliance Attendance Records'
        ordering = ['-recorded_at']
        unique_together = ['user', 'meeting']
        indexes = [
            models.Index(fields=['user', '-recorded_at']),
            models.Index(fields=['meeting']),
            models.Index(fields=['compliance_type']),
            models.Index(fields=['attendance_status']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_compliance_type_display()} - {self.get_attendance_status_display()}"
    
    @property
    def was_present(self):
        """Check if user was present (including remote)"""
        return self.attendance_status in ['present', 'remote', 'late']
    
    @property
    def is_compliant(self):
        """Check if attendance meets compliance requirements"""
        # Excused absences are compliant
        if self.is_excused:
            return True
        # Present or remote is compliant
        return self.was_present


class ComplianceArchive(models.Model):
    """Archived compliance records for long-term retention"""

    ARCHIVE_STATUS_CHOICES = [
        ('archived', 'Archived'),
        ('restored', 'Restored'),
        ('expired', 'Expired'),
        ('permanently_deleted', 'Permanently Deleted'),
    ]

    RECORD_TYPE_CHOICES = [
        ('compliance_attendance', 'Compliance Attendance'),
        ('policy_review', 'Policy Review'),
        ('risk_assessment', 'Risk Assessment'),
        ('audit_report', 'Audit Report'),
        ('annual_meeting', 'Annual Meeting'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Record identification
    record_type = models.CharField(max_length=30, choices=RECORD_TYPE_CHOICES)
    original_record_id = models.UUIDField(help_text="ID of the original record before archiving")
    record_title = models.CharField(max_length=255, help_text="Title or description of the archived record")
    
    # Compliance context
    compliance_category = models.CharField(max_length=100, blank=True, help_text="Category of compliance")
    compliance_period_start = models.DateField(null=True, blank=True)
    compliance_period_end = models.DateField(null=True, blank=True)
    
    # Archived data (JSON snapshot)
    archived_data = models.JSONField(default=dict, help_text="Snapshot of record data at archiving time")
    
    # Archiving details
    archived_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='archived_compliance_records'
    )
    archived_at = models.DateTimeField(auto_now_add=True)
    archive_reason = models.TextField(blank=True, help_text="Reason for archiving")
    
    # Retention
    retention_period_years = models.PositiveIntegerField(default=7, help_text="Years to retain this archive")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this archive can be permanently deleted")
    
    # Status
    archive_status = models.CharField(max_length=30, choices=ARCHIVE_STATUS_CHOICES, default='archived')
    restored_at = models.DateTimeField(null=True, blank=True)
    restored_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restored_compliance_records'
    )
    
    # Related documents
    related_documents = models.ManyToManyField(
        'documents.Document',
        blank=True,
        related_name='compliance_archives'
    )
    
    class Meta:
        verbose_name = 'Compliance Archive'
        verbose_name_plural = 'Compliance Archives'
        ordering = ['-archived_at']
        indexes = [
            models.Index(fields=['record_type']),
            models.Index(fields=['archived_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['archive_status']),
        ]
    
    def __str__(self):
        return f"{self.get_record_type_display()} - {self.record_title} (Archived {self.archived_at.strftime('%Y-%m-%d')})"
    
    def save(self, *args, **kwargs):
        """Calculate expiry date on save"""
        if not self.expires_at and self.retention_period_years:
            from datetime import timedelta
            self.expires_at = self.archived_at + timedelta(days=self.retention_period_years * 365)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if archive retention period has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def days_until_expiry(self):
        """Days until archive expires"""
        if self.expires_at:
            delta = self.expires_at - timezone.now()
            return delta.days
        return None
    
    def restore(self, restored_by):
        """Restore this archived record"""
        self.archive_status = 'restored'
        self.restored_at = timezone.now()
        self.restored_by = restored_by
        self.save(update_fields=['archive_status', 'restored_at', 'restored_by'])
