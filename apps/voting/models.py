import uuid

from django.db import models
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
