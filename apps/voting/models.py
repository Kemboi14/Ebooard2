import uuid

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from apps.accounts.models import User


class Motion(models.Model):
    """Board motion for voting"""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("proposed", "Proposed"),
        ("debate", "Under Debate"),
        ("voting", "Voting Open"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("withdrawn", "Withdrawn"),
        ("tabled", "Tabled"),
    ]

    VOTING_TYPE_CHOICES = [
        ("simple_majority", "Simple Majority (>50%)"),
        ("qualified_majority", "Qualified Majority (>60%)"),
        ("two_thirds", "Two-Thirds Majority (>66.7%)"),
        ("unanimous", "Unanimous"),
        ("consensus", "Consensus"),
    ]

    CATEGORY_CHOICES = [
        ("governance", "Governance"),
        ("financial", "Financial"),
        ("strategic", "Strategic"),
        ("operational", "Operational"),
        ("compliance", "Compliance"),
        ("personnel", "Personnel"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    background = models.TextField(
        blank=True, help_text="Background information and context for the motion"
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="governance"
    )
    reference_number = models.CharField(
        max_length=50, blank=True, help_text="Official motion reference number"
    )

    # Linked meeting (optional)
    meeting = models.ForeignKey(
        "meetings.Meeting",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="motions",
        help_text="Meeting where this motion was / will be tabled",
    )

    # Voting configuration
    voting_type = models.CharField(
        max_length=20, choices=VOTING_TYPE_CHOICES, default="simple_majority"
    )
    required_votes = models.PositiveIntegerField(
        help_text="Minimum number of votes required for the result to be valid"
    )
    voting_deadline = models.DateTimeField(help_text="Deadline for casting votes")

    # Status and proposers
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    proposed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="proposed_motions",
    )
    seconded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seconded_motions",
    )

    # Allows anonymous voting on this motion
    allow_anonymous = models.BooleanField(
        default=False,
        help_text="Allow board members to cast anonymous votes on this motion",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    voting_started_at = models.DateTimeField(null=True, blank=True)
    voting_ended_at = models.DateTimeField(null=True, blank=True)
    tabled_at = models.DateTimeField(
        null=True, blank=True, help_text="When the motion was tabled / withdrawn"
    )

    # Result notes
    result_notes = models.TextField(
        blank=True, help_text="Notes on the outcome, recorded by the secretary"
    )

    class Meta:
        verbose_name = "Motion"
        verbose_name_plural = "Motions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["voting_deadline"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title}"

    # ── Vote count properties ──────────────────────────────────────────────

    @property
    def total_votes(self):
        return self.votes.count()

    @property
    def yes_votes(self):
        return self.votes.filter(choice="yes").count()

    @property
    def no_votes(self):
        return self.votes.filter(choice="no").count()

    @property
    def abstain_votes(self):
        return self.votes.filter(choice="abstain").count()

    @property
    def yes_percentage(self):
        total = self.total_votes
        return round((self.yes_votes / total) * 100, 1) if total else 0

    @property
    def no_percentage(self):
        total = self.total_votes
        return round((self.no_votes / total) * 100, 1) if total else 0

    @property
    def abstain_percentage(self):
        total = self.total_votes
        return round((self.abstain_votes / total) * 100, 1) if total else 0

    # ── Status checks ──────────────────────────────────────────────────────

    @property
    def is_voting_open(self):
        """True only while the voting window is active."""
        return (
            self.status == "voting"
            and timezone.now() <= self.voting_deadline
            and not self.voting_ended_at
        )

    @property
    def is_deadline_passed(self):
        return timezone.now() > self.voting_deadline

    @property
    def is_concluded(self):
        return self.status in ("passed", "failed", "withdrawn", "tabled")

    @property
    def is_passed(self):
        """Check whether the motion passes based on voting type thresholds."""
        if self.status == "passed":
            return True
        if self.status == "failed":
            return False

        total = self.total_votes
        yes = self.yes_votes

        if total == 0:
            return False

        if self.voting_type == "simple_majority":
            return yes > total / 2
        elif self.voting_type == "qualified_majority":
            return yes / total >= 0.60
        elif self.voting_type == "two_thirds":
            return yes / total >= 2 / 3
        elif self.voting_type == "unanimous":
            return yes == total and self.no_votes == 0
        elif self.voting_type == "consensus":
            return self.no_votes == 0 and self.abstain_votes <= total * 0.10
        return False

    @property
    def threshold_description(self):
        """Human-readable description of what is needed to pass."""
        if self.voting_type == "simple_majority":
            return "More than 50% Yes votes required"
        elif self.voting_type == "qualified_majority":
            return "At least 60% Yes votes required"
        elif self.voting_type == "two_thirds":
            return "At least 66.7% Yes votes required"
        elif self.voting_type == "unanimous":
            return "All voters must vote Yes (no No votes allowed)"
        elif self.voting_type == "consensus":
            return "No No votes; abstentions limited to 10%"
        return ""

    # ── Lifecycle methods ──────────────────────────────────────────────────

    def open_voting(self, opened_by=None):
        """Transition motion to 'voting' status."""
        if self.status not in ("proposed", "debate"):
            raise ValueError(
                f"Cannot open voting on a motion with status '{self.status}'."
            )
        self.status = "voting"
        self.voting_started_at = timezone.now()
        self.save(update_fields=["status", "voting_started_at", "updated_at"])

    def close_voting(self, closed_by=None, force_status=None):
        """
        Close voting and automatically set status to passed/failed.
        Pass force_status='passed'|'failed'|'tabled'|'withdrawn' to override.
        """
        if self.status != "voting":
            raise ValueError(
                "Can only close voting on a motion that is in 'voting' status."
            )

        self.voting_ended_at = timezone.now()

        if force_status:
            self.status = force_status
        else:
            self.status = "passed" if self.is_passed else "failed"

        self.save(update_fields=["status", "voting_ended_at", "updated_at"])

        # Snapshot result
        VoteResult.objects.update_or_create(
            motion=self,
            defaults=dict(
                total_votes=self.total_votes,
                yes_votes=self.yes_votes,
                no_votes=self.no_votes,
                abstain_votes=self.abstain_votes,
                passed=(self.status == "passed"),
                voting_type=self.voting_type,
                certified_by=closed_by,
            ),
        )
        return self.status

    def withdraw(self, withdrawn_by=None, notes=""):
        self.status = "withdrawn"
        self.tabled_at = timezone.now()
        if notes:
            self.result_notes = notes
        self.save(update_fields=["status", "tabled_at", "result_notes", "updated_at"])

    def table(self, tabled_by=None, notes=""):
        self.status = "tabled"
        self.tabled_at = timezone.now()
        if notes:
            self.result_notes = notes
        self.save(update_fields=["status", "tabled_at", "result_notes", "updated_at"])

    def get_absolute_url(self):
        return f"/voting/motions/{self.id}/"


class VotingSession(models.Model):
    """
    A formal voting session that groups one or more motions.
    Linked optionally to a Meeting.
    """

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meeting = models.ForeignKey(
        "meetings.Meeting",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voting_sessions",
    )

    # ← fixed: M2M to Motion so session.motions.all() works correctly
    motions = models.ManyToManyField(
        Motion,
        related_name="sessions",
        blank=True,
        help_text="Motions included in this voting session",
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    eligible_voters = models.ManyToManyField(
        User, related_name="eligible_sessions", blank=True
    )
    
    # Committee restriction - if set, only committee members can vote
    committee = models.ForeignKey(
        "accounts.Committee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voting_sessions",
        help_text="Restrict voting to members of this committee"
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Voting Session"
        verbose_name_plural = "Voting Sessions"
        ordering = ["-start_time"]

    def __str__(self):
        return f"Voting Session: {self.title}"

    @property
    def is_active(self):
        now = timezone.now()
        return self.status == "active" and self.start_time <= now <= self.end_time

    @property
    def motions_count(self):
        return self.motions.count()

    @property
    def open_motions_count(self):
        return self.motions.filter(status="voting").count()

    def activate(self):
        self.status = "active"
        self.save(update_fields=["status", "updated_at"])

    def complete(self):
        self.status = "completed"
        self.save(update_fields=["status", "updated_at"])
    
    def get_eligible_voters(self):
        """
        Get eligible voters for this session.
        If committee is set, only active committee members with voting rights are eligible.
        Otherwise, returns all eligible_voters.
        """
        if self.committee:
            # Return only active committee members with voting rights
            from apps.accounts.models import CommitteeMembership
            committee_members = CommitteeMembership.objects.filter(
                committee=self.committee,
                is_active=True,
                has_voting_rights=True
            ).select_related('user')
            return [cm.user for cm in committee_members if cm.is_currently_active]
        else:
            # Return all manually added eligible voters
            return list(self.eligible_voters.all())
    
    def is_user_eligible_to_vote(self, user):
        """
        Check if a user is eligible to vote in this session.
        """
        if self.committee:
            # Check if user is an active committee member with voting rights
            from apps.accounts.models import CommitteeMembership
            membership = CommitteeMembership.objects.filter(
                user=user,
                committee=self.committee,
                is_active=True,
                has_voting_rights=True
            ).first()
            return membership is not None and membership.is_currently_active
        else:
            # Check if user is in eligible_voters
            return self.eligible_voters.filter(id=user.id).exists()


class VoteOption(models.Model):
    """Custom options for multiple-choice votes (beyond yes/no/abstain)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    motion = models.ForeignKey(
        Motion, on_delete=models.CASCADE, related_name="vote_options"
    )
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vote Option"
        verbose_name_plural = "Vote Options"
        ordering = ["order"]
        unique_together = ["motion", "order"]

    def __str__(self):
        return f"{self.motion.title} — Option {self.order}: {self.text}"

    @property
    def vote_count(self):
        return self.votes.count()


class Vote(models.Model):
    """Individual vote cast by a board member."""

    CHOICE_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("abstain", "Abstain"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="votes")
    choice = models.CharField(max_length=10, choices=CHOICE_CHOICES)
    vote_option = models.ForeignKey(
        VoteOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="votes",
    )

    comment = models.TextField(
        blank=True, help_text="Optional explanation of vote (not shown if anonymous)"
    )
    is_anonymous = models.BooleanField(
        default=False,
        help_text="Hide voter identity from other members (secretary can still see)",
    )

    cast_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Vote"
        verbose_name_plural = "Votes"
        ordering = ["-cast_at"]
        unique_together = ["motion", "voter"]  # one vote per member per motion

    def __str__(self):
        name = "Anonymous" if self.is_anonymous else self.voter.get_full_name()
        return f"{name} — {self.get_choice_display()} — {self.motion.title}"


class VoteResult(models.Model):
    """
    Certified snapshot of voting results, created when voting is closed.
    Updated via Motion.close_voting().
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    motion = models.OneToOneField(
        Motion, on_delete=models.CASCADE, related_name="result"
    )

    total_votes = models.PositiveIntegerField(default=0)
    yes_votes = models.PositiveIntegerField(default=0)
    no_votes = models.PositiveIntegerField(default=0)
    abstain_votes = models.PositiveIntegerField(default=0)

    passed = models.BooleanField()
    voting_type = models.CharField(max_length=20, choices=Motion.VOTING_TYPE_CHOICES)

    summary = models.TextField(blank=True)

    certified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certified_results",
    )
    certified_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vote Result"
        verbose_name_plural = "Vote Results"

    def __str__(self):
        outcome = "Passed" if self.passed else "Failed"
        return f"Result — {self.motion.title}: {outcome}"

    @property
    def yes_percentage(self):
        return (
            round((self.yes_votes / self.total_votes) * 100, 1)
            if self.total_votes
            else 0
        )

    @property
    def no_percentage(self):
        return (
            round((self.no_votes / self.total_votes) * 100, 1)
            if self.total_votes
            else 0
        )

    @property
    def abstain_percentage(self):
        return (
            round((self.abstain_votes / self.total_votes) * 100, 1)
            if self.total_votes
            else 0
        )


class ProxyVote(models.Model):
    """Proxy voting for when a board member cannot attend"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Proxy relationship
    principal = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_proxies', help_text="Board member giving proxy")
    proxy = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_proxies', help_text="Board member receiving proxy")
    
    # Motion context
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='proxy_votes')
    
    # Voting instructions
    voting_instructions = models.CharField(max_length=10, choices=Vote.CHOICE_CHOICES, help_text="How to vote on behalf")
    custom_instructions = models.TextField(blank=True, help_text="Additional instructions for the proxy")
    
    # Approval
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_proxies')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Execution
    executed = models.BooleanField(default=False, help_text="Whether the proxy vote was executed")
    executed_at = models.DateTimeField(null=True, blank=True)
    
    # Validity
    valid_from = models.DateTimeField(help_text="When the proxy becomes valid")
    valid_until = models.DateTimeField(help_text="When the proxy expires")
    
    # Documentation
    supporting_document = models.FileField(upload_to='proxy_documents/', null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Proxy Vote'
        verbose_name_plural = 'Proxy Votes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['principal', '-created_at']),
            models.Index(fields=['proxy', '-created_at']),
            models.Index(fields=['motion', '-created_at']),
            models.Index(fields=['status']),
        ]
        unique_together = ['principal', 'motion']
    
    def __str__(self):
        return f"{self.principal.get_full_name()} → {self.proxy.get_full_name()} - {self.motion.title}"
    
    @property
    def is_valid(self):
        """Check if proxy is currently valid"""
        now = timezone.now()
        return self.status == 'approved' and self.valid_from <= now <= self.valid_until
    
    @property
    def is_expired(self):
        """Check if proxy has expired"""
        return timezone.now() > self.valid_until


class DecisionDocumentation(models.Model):
    """Documentation for board decisions with legal compliance tracking"""

    COMPLIANCE_STATUS_CHOICES = [
        ('compliant', 'Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('partially_compliant', 'Partially Compliant'),
        ('pending_review', 'Pending Review'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Related motion
    motion = models.OneToOneField(Motion, on_delete=models.CASCADE, related_name='decision_documentation')
    
    # Decision details
    decision_summary = models.TextField(help_text="Summary of the decision")
    legal_basis = models.TextField(help_text="Legal basis for the decision")
    compliance_notes = models.TextField(blank=True, help_text="Notes on compliance considerations")
    
    # Compliance status
    compliance_status = models.CharField(max_length=30, choices=COMPLIANCE_STATUS_CHOICES, default='pending_review')
    compliance_score = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Implementation plan
    implementation_plan = models.TextField(blank=True, help_text="Plan for implementing the decision")
    implementation_deadline = models.DateField(null=True, blank=True)
    implementation_status = models.CharField(max_length=50, blank=True, help_text="Current implementation status")
    
    # Documentation
    supporting_documents = models.ManyToManyField('documents.Document', blank=True, related_name='decision_documentations')
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_decisions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Decision Documentation'
        verbose_name_plural = 'Decision Documentations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['motion']),
            models.Index(fields=['compliance_status']),
        ]
    
    def __str__(self):
        return f"Documentation for {self.motion.title}"
    
    @property
    def is_compliant(self):
        return self.compliance_status == 'compliant'


class VotingPattern(models.Model):
    """Track voting patterns and analytics for board members"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voting_patterns')
    
    # Overall statistics
    total_votes = models.PositiveIntegerField(default=0)
    votes_in_favor = models.PositiveIntegerField(default=0)
    votes_against = models.PositiveIntegerField(default=0)
    abstentions = models.PositiveIntegerField(default=0)
    
    # Voting consistency
    consistency_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Voting consistency score (0-100)")
    
    # Category breakdown (JSON: {"governance": {"in_favor": 10, "against": 2}, ...})
    category_breakdown = models.JSONField(null=True, blank=True)
    
    # Participation
    participation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage of motions voted on")
    total_eligible_votes = models.PositiveIntegerField(default=0)
    
    # Voting patterns
    typically_votes_with_majority = models.BooleanField(default=True)
    often_abstains = models.BooleanField(default=False)
    frequently_dissents = models.BooleanField(default=False)
    
    # Metadata
    last_calculated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Voting Pattern'
        verbose_name_plural = 'Voting Patterns'
        ordering = ['-last_calculated_at']
        indexes = [
            models.Index(fields=['user', '-last_calculated_at']),
            models.Index(fields=['-participation_rate']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Voting Patterns"
    
    @property
    def support_percentage(self):
        """Calculate percentage of votes in favor"""
        if self.total_votes == 0:
            return 0
        return (self.votes_in_favor / self.total_votes) * 100
    
    @property
    def opposition_percentage(self):
        """Calculate percentage of votes against"""
        if self.total_votes == 0:
            return 0
        return (self.votes_against / self.total_votes) * 100


class VotingHistory(models.Model):
    """Historical record of all votes for pattern analysis"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vote = models.ForeignKey('Vote', on_delete=models.CASCADE, related_name='history_records')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voting_history')
    
    # Vote details snapshot
    motion_title = models.CharField(max_length=200)
    motion_category = models.CharField(max_length=20)
    vote_choice = models.CharField(max_length=20)
    
    # Context
    voting_session_date = models.DateTimeField()
    meeting_title = models.CharField(max_length=200, blank=True)
    
    # Outcome
    motion_outcome = models.CharField(max_length=20, help_text="Final outcome of the motion")
    vote_weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    
    # Analysis flags
    was_decisive_vote = models.BooleanField(default=False, help_text="Whether this vote was decisive")
    aligned_with_majority = models.BooleanField(default=True)
    
    # Metadata
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Voting History'
        verbose_name_plural = 'Voting History'
        ordering = ['-voting_session_date']
        indexes = [
            models.Index(fields=['user', '-voting_session_date']),
            models.Index(fields=['motion_category']),
            models.Index(fields=['vote_choice']),
            models.Index(fields=['-voting_session_date']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.motion_title} ({self.vote_choice})"


class QuorumTracking(models.Model):
    """Track quorum status for meetings and voting sessions"""

    STATUS_CHOICES = [
        ('not_met', 'Quorum Not Met'),
        ('met', 'Quorum Met'),
        ('lost', 'Quorum Lost'),
        ('waived', 'Quorum Waived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.CASCADE, related_name='quorum_records', null=True, blank=True)
    voting_session = models.ForeignKey('VotingSession', on_delete=models.CASCADE, related_name='quorum_records', null=True, blank=True)
    
    # Quorum details
    required_members = models.IntegerField(help_text="Number of members required for quorum")
    present_members = models.IntegerField(help_text="Number of members present")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_met')
    
    # Timestamps
    quorum_met_at = models.DateTimeField(null=True, blank=True, help_text="When quorum was first met")
    quorum_lost_at = models.DateTimeField(null=True, blank=True, help_text="When quorum was lost")
    checked_at = models.DateTimeField(auto_now_add=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Quorum Tracking'
        verbose_name_plural = 'Quorum Tracking'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['meeting', '-checked_at']),
            models.Index(fields=['voting_session', '-checked_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        if self.meeting:
            return f"{self.meeting.title} - {self.get_status_display()}"
        return f"Voting Session - {self.get_status_display()}"
    
    @property
    def quorum_percentage(self):
        """Calculate percentage of quorum met"""
        if self.required_members == 0:
            return 0
        return (self.present_members / self.required_members) * 100
