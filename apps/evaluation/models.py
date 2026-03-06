from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
import uuid

User = get_user_model()

class EvaluationFramework(models.Model):
    """Enterprise-grade evaluation frameworks"""
    
    FRAMEWORK_TYPES = [
        ('competency', 'Competency-Based'),
        ('behavioral', 'Behavioral Anchored Rating Scale (BARS)'),
        ('360', '360-Degree Multi-Rater'),
        ('balanced_scorecard', 'Balanced Scorecard'),
        ('kpi', 'Key Performance Indicators'),
        ('custom', 'Custom Framework'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    framework_type = models.CharField(max_length=20, choices=FRAMEWORK_TYPES)
    
    # Framework configuration
    competencies = models.JSONField(null=True, blank=True, help_text="Competency definitions and levels")
    behavioral_indicators = models.JSONField(null=True, blank=True, help_text="Behavioral anchors for rating scales")
    weight_distribution = models.JSONField(null=True, blank=True, help_text="Weight distribution for different areas")
    
    # Scoring methodology
    scoring_method = models.CharField(max_length=50, default='weighted_average', help_text="Scoring calculation method")
    calibration_required = models.BooleanField(default=False, help_text="Requires calibration sessions")
    statistical_analysis = models.BooleanField(default=False, help_text="Enable statistical analysis")
    
    # Enterprise features
    industry_standard = models.BooleanField(default=False, help_text="Based on industry standards")
    regulatory_compliance = models.CharField(max_length=100, blank=True, help_text="Regulatory compliance (e.g., SOX, GDPR)")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_frameworks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Evaluation Framework"
        verbose_name_plural = "Evaluation Frameworks"
    
    def __str__(self):
        return f"{self.name} ({self.get_framework_type_display()})"

class EvaluationTemplate(models.Model):
    """Enterprise-grade evaluation templates"""
    
    EVALUATION_TYPES = [
        ('self', 'Self Evaluation'),
        ('peer', 'Peer Review'),
        ('board', 'Board Assessment'),
        ('committee', 'Committee Evaluation'),
        ('performance', 'Performance Review'),
        ('360', '360-Degree Feedback'),
        ('succession', 'Succession Planning'),
        ('compliance', 'Regulatory Compliance'),
        ('governance', 'Corporate Governance'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    evaluation_type = models.CharField(max_length=20, choices=EVALUATION_TYPES)
    
    # Framework integration
    framework = models.ForeignKey(EvaluationFramework, on_delete=models.SET_NULL, null=True, blank=True, related_name='templates')
    
    # Advanced configuration
    target_audience = models.CharField(max_length=100, blank=True, help_text="Target audience (e.g., Board Members, Executives)")
    evaluation_frequency = models.CharField(max_length=50, blank=True, help_text="How often evaluations occur")
    confidentiality_level = models.CharField(max_length=20, default='confidential', choices=[
        ('public', 'Public'),
        ('internal', 'Internal Only'),
        ('confidential', 'Confidential'),
        ('anonymous', 'Anonymous'),
    ])
    
    # Instructions and guidance
    evaluator_instructions = models.TextField(blank=True, help_text="Instructions for evaluators")
    evaluatee_guidance = models.TextField(blank=True, help_text="Guidance for evaluatees")
    
    # Scoring configuration
    max_score = models.IntegerField(default=100)
    passing_score = models.IntegerField(default=70)
    scoring_scale = models.JSONField(null=True, blank=True, help_text="Custom scoring scale definitions")
    
    # Enterprise compliance
    regulatory_requirements = models.TextField(blank=True, help_text="Regulatory or compliance requirements")
    data_retention_period = models.IntegerField(null=True, blank=True, help_text="Data retention period in months")
    
    # Advanced features
    requires_calibration = models.BooleanField(default=False, help_text="Requires calibration sessions")
    allows_self_nomination = models.BooleanField(default=False, help_text="Allows self-nomination of evaluators")
    anonymous_feedback = models.BooleanField(default=False, help_text="Enable anonymous feedback")
    
    # Status and availability
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False, help_text="Available to all authorized users")
    approval_required = models.BooleanField(default=True, help_text="Requires approval before publishing")
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_templates')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_templates')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Evaluation Templates"
        indexes = [
            models.Index(fields=['evaluation_type', 'is_active']),
            models.Index(fields=['framework', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_evaluation_type_display()})"
    
    def get_absolute_url(self):
        return reverse('evaluation:template_detail', kwargs={'pk': self.pk})
    
    @property
    def is_compliant(self):
        """Check if template meets regulatory requirements"""
        if not self.regulatory_requirements:
            return True
        # Add compliance checking logic here
        return True

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Evaluation Templates"

    def __str__(self):
        return f"{self.name} ({self.get_evaluation_type_display()})"

    def get_absolute_url(self):
        return reverse('evaluation:template_detail', kwargs={'pk': self.pk})

class EvaluationQuestion(models.Model):
    """Questions within evaluation templates"""
    
    QUESTION_TYPES = [
        ('rating', 'Rating Scale'),
        ('text', 'Text Answer'),
        ('yes_no', 'Yes/No'),
        ('multiple_choice', 'Multiple Choice'),
        ('ranking', 'Ranking'),
        ('numeric', 'Numeric Score'),
    ]
    
    template = models.ForeignKey(EvaluationTemplate, on_delete=models.CASCADE, related_name='questions')
    
    # Question details
    text = models.TextField(help_text="The question text")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    order = models.PositiveIntegerField(default=0)
    
    # Scoring and weighting
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, help_text="Relative weight in scoring")
    max_score = models.IntegerField(null=True, blank=True, help_text="Maximum points for this question")
    
    # Options for multiple choice questions
    choices = models.JSONField(null=True, blank=True, help_text="Options for multiple choice questions")
    
    # Required status
    is_required = models.BooleanField(default=True)
    
    # Category for grouping
    category = models.CharField(max_length=100, blank=True, help_text="Category for grouping questions")
    
    class Meta:
        ordering = ['template', 'order', 'id']
        unique_together = ['template', 'order']
        verbose_name_plural = "Evaluation Questions"

    def __str__(self):
        return f"{self.template.name} - Q{self.order + 1}: {self.text[:50]}..."

class Evaluation(models.Model):
    """Enterprise-grade evaluation instances with compliance and audit features"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
        ('calibration', 'Calibration Required'),
        ('escalated', 'Escalated'),
    ]
    
    COMPLIANCE_LEVELS = [
        ('basic', 'Basic Compliance'),
        ('enhanced', 'Enhanced Compliance'),
        ('strict', 'Strict Compliance'),
        ('regulatory', 'Regulatory Compliance'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(EvaluationTemplate, on_delete=models.PROTECT, related_name='evaluations')
    
    # People involved
    evaluator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluations_given')
    evaluatee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluations_received')
    
    # Additional evaluators for 360-degree feedback
    additional_evaluators = models.ManyToManyField(User, related_name='additional_evaluations', blank=True)
    
    # Evaluation period and scheduling
    evaluation_period = models.CharField(max_length=100, help_text="e.g., Q1 2024, Annual 2024")
    start_date = models.DateField()
    end_date = models.DateField()
    reminder_sent = models.BooleanField(default=False)
    escalation_date = models.DateField(null=True, blank=True)
    
    # Advanced workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, default='normal', choices=[
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ])
    
    # Compliance and regulatory
    compliance_level = models.CharField(max_length=20, choices=COMPLIANCE_LEVELS, default='basic')
    regulatory_reference = models.CharField(max_length=100, blank=True, help_text="Regulatory reference number")
    data_retention_expiry = models.DateField(null=True, blank=True)
    
    # Advanced scoring with calibration
    total_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_possible_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    calibrated_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    performance_band = models.CharField(max_length=20, blank=True, help_text="Performance band (e.g., Exceeds, Meets, Below)")
    
    # Statistical analysis
    statistical_data = models.JSONField(null=True, blank=True, help_text="Statistical analysis data")
    
    # Review and approval workflow
    current_reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_reviews')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_evaluations')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True)
    
    # Multi-stage approval
    approval_workflow = models.JSONField(null=True, blank=True, help_text="Multi-stage approval workflow configuration")
    approval_stage = models.CharField(max_length=50, blank=True, help_text="Current approval stage")
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_evaluations')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Calibration and quality assurance
    requires_calibration = models.BooleanField(default=False)
    calibration_completed = models.BooleanField(default=False)
    calibration_session = models.ForeignKey('CalibrationSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluations')
    
    # Audit trail
    audit_trail = models.JSONField(null=True, blank=True, help_text="Complete audit trail of changes")
    
    # Metadata with enhanced tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['evaluatee', 'status']),
            models.Index(fields=['evaluator', 'status']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['evaluation_period']),
            models.Index(fields=['compliance_level']),
            models.Index(fields=['priority']),
            models.Index(fields=['end_date']),
        ]
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['evaluatee', 'status']),
            models.Index(fields=['evaluator', 'status']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['evaluation_period']),
        ]

    def __str__(self):
        evaluator_name = self.evaluator.get_full_name() if self.evaluator else "System"
        evaluatee_name = self.evaluatee.get_full_name() if self.evaluatee else "Unknown"
        return f"{evaluator_name} → {evaluatee_name} ({self.template.name})"

    def get_absolute_url(self):
        return reverse('evaluation:evaluation_detail', kwargs={'pk': self.pk})

    def get_absolute_url(self):
        return reverse('evaluation:evaluation_detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self):
        """Check if evaluation is past due date"""
        return self.end_date < timezone.now().date() and self.status not in ['submitted', 'approved', 'archived']

    @property
    def days_remaining(self):
        """Days remaining until due date"""
        if self.status in ['submitted', 'approved', 'archived']:
            return 0
        delta = self.end_date - timezone.now().date()
        return max(0, delta.days)

    def calculate_score(self):
        """Calculate total score from all answers with advanced scoring"""
        answers = self.answers.all()
        if not answers:
            return
        
        total_score = 0
        max_score = 0
        
        for answer in answers:
            if answer.score is not None:
                # Apply weighting if available
                weight = answer.question.weight or 1.0
                total_score += answer.score * weight
            if answer.question.max_score:
                weight = answer.question.weight or 1.0
                max_score += answer.question.max_score * weight
        
        self.total_score = total_score
        self.max_possible_score = max_score or self.template.max_score
        
        if self.max_possible_score > 0:
            self.percentage_score = (total_score / self.max_possible_score) * 100
        
        # Calculate performance band
        if self.percentage_score:
            if self.percentage_score >= 90:
                self.performance_band = 'Exceeds Expectations'
            elif self.percentage_score >= 80:
                self.performance_band = 'Meets Expectations'
            elif self.percentage_score >= 70:
                self.performance_band = 'Below Expectations'
            else:
                self.performance_band = 'Significantly Below'
        
        self.save(update_fields=['total_score', 'max_possible_score', 'percentage_score', 'performance_band'])

class CalibrationSession(models.Model):
    """Enterprise calibration sessions for scoring consistency"""
    
    SESSION_TYPES = [
        ('internal', 'Internal Calibration'),
        ('external', 'External Calibration'),
        ('peer_review', 'Peer Review Calibration'),
        ('expert_review', 'Expert Review'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES)
    
    # Session details
    facilitator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='facilitated_sessions')
    participants = models.ManyToManyField(User, related_name='calibration_sessions')
    
    # Scheduling
    scheduled_date = models.DateTimeField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2, help_text="Duration in hours")
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, default='scheduled', choices=[
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ])
    
    # Calibration data
    calibration_results = models.JSONField(null=True, blank=True, help_text="Calibration results and statistics")
    consensus_scores = models.JSONField(null=True, blank=True, help_text="Agreed-upon calibrated scores")
    
    # Quality metrics
    inter_rater_reliability = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    calibration_accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Follow-up
    action_items = models.TextField(blank=True, help_text="Action items from calibration session")
    follow_up_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_calibration_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = "Calibration Session"
        verbose_name_plural = "Calibration Sessions"
    
    def __str__(self):
        return f"{self.name} ({self.get_session_type_display()})"

class EvaluationAnalytics(models.Model):
    """Advanced analytics and benchmarking for evaluations"""
    
    # Reference
    evaluation = models.OneToOneField(Evaluation, on_delete=models.CASCADE, related_name='analytics')
    
    # Benchmarking data
    industry_benchmarks = models.JSONField(null=True, blank=True, help_text="Industry benchmarking data")
    peer_comparison = models.JSONField(null=True, blank=True, help_text="Peer comparison data")
    historical_trends = models.JSONField(null=True, blank=True, help_text="Historical performance trends")
    
    # Statistical analysis
    mean_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    median_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    standard_deviation = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentile_rank = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Predictive analytics
    performance_prediction = models.JSONField(null=True, blank=True, help_text="Predictive performance indicators")
    risk_indicators = models.JSONField(null=True, blank=True, help_text="Risk assessment indicators")
    
    # Competency analysis
    competency_scores = models.JSONField(null=True, blank=True, help_text="Individual competency scores")
    competency_gaps = models.JSONField(null=True, blank=True, help_text="Identified competency gaps")
    
    # Development recommendations
    development_plan = models.TextField(blank=True, help_text="AI-generated development recommendations")
    training_suggestions = models.JSONField(null=True, blank=True, help_text="Suggested training programs")
    
    # Generated
    generated_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Evaluation Analytics"
        verbose_name_plural = "Evaluation Analytics"
    
    def __str__(self):
        return f"Analytics for {self.evaluation}"

class EvaluationAnswer(models.Model):
    """Answers to evaluation questions"""
    
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(EvaluationQuestion, on_delete=models.CASCADE, related_name='answers')
    
    # Answer content
    text_answer = models.TextField(blank=True)
    numeric_answer = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    choice_answer = models.CharField(max_length=200, blank=True)
    
    # Scoring
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Comments
    comments = models.TextField(blank=True, help_text="Additional comments on this answer")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['evaluation', 'question']
        ordering = ['question__order']

    def __str__(self):
        return f"Answer to {self.question.text[:30]}... for {self.evaluation}"

    def get_answer_value(self):
        """Get the appropriate answer value based on question type"""
        if self.question.question_type == 'text':
            return self.text_answer
        elif self.question.question_type in ['rating', 'numeric']:
            return self.numeric_answer
        elif self.question.question_type == 'multiple_choice':
            return self.choice_answer
        elif self.question.question_type == 'yes_no':
            return self.choice_answer
        return None

class EvaluationComment(models.Model):
    """Comments and feedback on evaluations"""
    
    COMMENT_TYPES = [
        ('general', 'General Comment'),
        ('strength', 'Strength'),
        ('weakness', 'Weakness'),
        ('recommendation', 'Recommendation'),
        ('concern', 'Concern'),
    ]
    
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    comment_type = models.CharField(max_length=20, choices=COMMENT_TYPES, default='general')
    text = models.TextField()
    
    # Visibility
    is_public = models.BooleanField(default=True, help_text="Visible to the evaluatee")
    is_anonymous = models.BooleanField(default=False, help_text="Hide author identity")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_comment_type_display()} on {self.evaluation}"

class EvaluationSummary(models.Model):
    """Summarized evaluation results for reporting"""
    
    # Reference to evaluation
    evaluation = models.OneToOneField(Evaluation, on_delete=models.CASCADE, related_name='summary')
    
    # Overall assessment
    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    performance_level = models.CharField(max_length=20, blank=True)
    
    # Key findings
    strengths = models.TextField(blank=True, help_text="Key strengths identified")
    areas_for_improvement = models.TextField(blank=True, help_text="Areas needing improvement")
    recommendations = models.TextField(blank=True, help_text="Actionable recommendations")
    
    # Development goals
    short_term_goals = models.TextField(blank=True, help_text="Goals for next 3-6 months")
    long_term_goals = models.TextField(blank=True, help_text="Goals for next 12 months")
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_up_evaluations')
    
    # Generated by
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_summaries')
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Evaluation Summaries"

    def __str__(self):
        return f"Summary for {self.evaluation}"

class EvaluationCycle(models.Model):
    """Manage evaluation cycles and periods"""
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Period
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Configuration
    template = models.ForeignKey(EvaluationTemplate, on_delete=models.PROTECT)
    auto_assign_evaluators = models.BooleanField(default=False)
    reminder_frequency = models.IntegerField(default=7, help_text="Days between reminders")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    
    # Participants
    participants = models.ManyToManyField(User, related_name='evaluation_cycles')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = "Evaluation Cycles"

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    @property
    def is_current(self):
        """Check if cycle is currently active"""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.is_active

    def get_completion_rate(self):
        """Calculate completion rate for this cycle"""
        total_evaluations = self.evaluations.count()
        completed_evaluations = self.evaluations.filter(status='submitted').count()
        
        if total_evaluations == 0:
            return 0
        return (completed_evaluations / total_evaluations) * 100
