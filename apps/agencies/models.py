import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User


class Organization(models.Model):
    """
    Top-level organization (Enwealth Global HQ).
    All branches/subsidiaries belong to one organization.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="organizations/logos/", null=True, blank=True)

    # Address
    head_office_address = models.TextField(blank=True)
    head_office_country = models.CharField(max_length=100, blank=True)
    head_office_city = models.CharField(max_length=100, blank=True)

    # Contact
    primary_email = models.EmailField(blank=True)
    primary_phone = models.CharField(max_length=30, blank=True)

    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_organizations",
    )

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("agencies:organization_detail", kwargs={"pk": self.pk})

    @property
    def total_branches(self):
        return self.branches.filter(is_active=True).count()

    @property
    def total_users(self):
        return (
            UserBranchMembership.objects.filter(
                branch__organization=self, is_active=True
            )
            .values("user")
            .distinct()
            .count()
        )

    @property
    def total_committees(self):
        return Committee.objects.filter(
            branch__organization=self, is_active=True
        ).count()


class Branch(models.Model):
    """
    A branch / subsidiary / regional office of the organization.
    Each branch operates independently but reports to the parent organization.
    A branch can also have a parent branch (subsidiary of a subsidiary).
    """

    BRANCH_TYPES = [
        ("headquarters", "Headquarters"),
        ("regional_office", "Regional Office"),
        ("country_office", "Country Office"),
        ("subsidiary", "Subsidiary Company"),
        ("affiliate", "Affiliate"),
        ("joint_venture", "Joint Venture"),
        ("representative_office", "Representative Office"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("under_review", "Under Review"),
        ("suspended", "Suspended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="branches"
    )
    parent_branch = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_branches",
        help_text="Parent branch if this is a subsidiary of another branch",
    )

    # Identity
    name = models.CharField(max_length=200)
    code = models.CharField(
        max_length=20, unique=True, help_text="Unique branch code e.g. EN-KE-001"
    )
    branch_type = models.CharField(
        max_length=30, choices=BRANCH_TYPES, default="regional_office"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Location
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    timezone_name = models.CharField(
        max_length=60,
        default="Africa/Nairobi",
        help_text="IANA timezone name e.g. Europe/London",
    )

    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)

    # Branding (override org logo if needed)
    logo = models.ImageField(upload_to="branches/logos/", null=True, blank=True)

    # Governance settings
    max_users = models.PositiveIntegerField(
        default=1000, help_text="Maximum number of users for this branch"
    )
    has_own_board = models.BooleanField(
        default=True, help_text="Branch has its own board of directors"
    )
    reporting_currency = models.CharField(max_length=10, default="USD")

    # Metadata
    is_active = models.BooleanField(default=True)
    established_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_branches",
    )

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        ordering = ["organization", "country", "name"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["country"]),
            models.Index(fields=["branch_type"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.code}] — {self.country}"

    def get_absolute_url(self):
        return reverse("agencies:branch_detail", kwargs={"pk": self.pk})

    @property
    def total_members(self):
        return self.memberships.filter(is_active=True).count()

    @property
    def total_committees(self):
        return self.committees.filter(is_active=True).count()

    @property
    def board_members(self):
        return self.memberships.filter(
            is_active=True, user__role="board_member"
        ).select_related("user")

    @property
    def active_memberships(self):
        return self.memberships.filter(is_active=True).select_related("user")

    @property
    def display_logo(self):
        """Return branch logo or fall back to org logo."""
        if self.logo:
            return self.logo
        if self.organization.logo:
            return self.organization.logo
        return None

    def get_hierarchy_path(self):
        """Return ordered list of ancestor Branch objects (excluding self), root-first."""
        ancestors = []
        current = self.parent_branch
        while current:
            ancestors.insert(0, current)
            current = current.parent_branch
        return ancestors

    def can_add_user(self):
        return self.total_members < self.max_users


class Committee(models.Model):
    """
    A committee within a branch (e.g. Board of Directors, Audit Committee,
    Risk Committee, Finance Committee, Remuneration Committee, etc.)
    Each committee has its own members, meetings, documents, and voting.
    """

    COMMITTEE_TYPES = [
        ("board_of_directors", "Board of Directors"),
        ("executive_committee", "Executive Committee"),
        ("audit_committee", "Audit Committee"),
        ("risk_committee", "Risk & Compliance Committee"),
        ("finance_committee", "Finance Committee"),
        ("remuneration_committee", "Remuneration Committee"),
        ("nomination_committee", "Nomination Committee"),
        ("investment_committee", "Investment Committee"),
        ("strategy_committee", "Strategy Committee"),
        ("governance_committee", "Governance Committee"),
        ("technical_committee", "Technical Committee"),
        ("special_committee", "Special / Ad-hoc Committee"),
        ("subsidiary_board", "Subsidiary Board"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("dissolved", "Dissolved"),
        ("under_review", "Under Review"),
    ]

    QUORUM_TYPES = [
        ("majority", "Simple Majority"),
        ("two_thirds", "Two-Thirds"),
        ("three_quarters", "Three-Quarters"),
        ("unanimous", "Unanimous"),
        ("custom", "Custom"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="committees"
    )

    # Identity
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, help_text="Short code e.g. BOD, AUDIT, RISK")
    committee_type = models.CharField(
        max_length=30, choices=COMMITTEE_TYPES, default="other"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    description = models.TextField(blank=True)
    mandate = models.TextField(
        blank=True, help_text="Committee mandate and terms of reference"
    )

    # Governance
    quorum_type = models.CharField(
        max_length=20, choices=QUORUM_TYPES, default="majority"
    )
    quorum_custom_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Custom quorum count (used when quorum_type=custom)",
    )
    min_members = models.PositiveIntegerField(default=3)
    max_members = models.PositiveIntegerField(default=15)
    meeting_frequency = models.CharField(
        max_length=50, blank=True, help_text="e.g. Monthly, Quarterly, As needed"
    )

    # Hierarchy — a committee can be a sub-committee of another
    parent_committee = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_committees",
    )

    # Chair and Secretary
    chairperson = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chaired_committees",
    )
    secretary = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secretarial_committees",
    )

    # Dates
    established_date = models.DateField(null=True, blank=True)
    dissolution_date = models.DateField(null=True, blank=True)

    # Metadata
    is_active = models.BooleanField(default=True)
    is_confidential = models.BooleanField(
        default=False,
        help_text="Restrict visibility of this committee to its members only",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_committees",
    )

    class Meta:
        verbose_name = "Committee"
        verbose_name_plural = "Committees"
        ordering = ["branch", "name"]
        unique_together = [["branch", "code"]]
        indexes = [
            models.Index(fields=["branch", "is_active"]),
            models.Index(fields=["committee_type"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.branch.name}"

    def get_absolute_url(self):
        return reverse("agencies:committee_detail", kwargs={"pk": self.pk})

    @property
    def active_members(self):
        return self.memberships.filter(is_active=True).select_related("user")

    @property
    def active_member_count(self):
        return self.memberships.filter(is_active=True).count()

    @property
    def has_quorum(self):
        """Check if committee currently has enough members for quorum."""
        count = self.active_member_count
        if self.quorum_type == "majority":
            return count >= (self.max_members // 2) + 1
        elif self.quorum_type == "two_thirds":
            return count >= round(self.max_members * 2 / 3)
        elif self.quorum_type == "three_quarters":
            return count >= round(self.max_members * 3 / 4)
        elif self.quorum_type == "unanimous":
            return count >= self.max_members
        elif self.quorum_type == "custom" and self.quorum_custom_value:
            return count >= self.quorum_custom_value
        return True


class CommitteeMembership(models.Model):
    """
    Links a user to a committee with a specific role within that committee.
    A user can be a member of multiple committees.
    """

    MEMBERSHIP_ROLES = [
        ("chairperson", "Chairperson"),
        ("vice_chairperson", "Vice Chairperson"),
        ("secretary", "Secretary"),
        ("treasurer", "Treasurer"),
        ("member", "Member"),
        ("observer", "Observer"),
        ("advisor", "Advisor / Consultant"),
        ("alternate", "Alternate Member"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
        ("resigned", "Resigned"),
        ("term_ended", "Term Ended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    committee = models.ForeignKey(
        Committee, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="committee_memberships"
    )

    # Role within this committee
    committee_role = models.CharField(
        max_length=30, choices=MEMBERSHIP_ROLES, default="member"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Term management
    term_start = models.DateField(default=timezone.now)
    term_end = models.DateField(null=True, blank=True)
    is_current_term = models.BooleanField(default=True)

    # Voting rights
    has_voting_rights = models.BooleanField(
        default=True, help_text="Whether this member can vote in committee decisions"
    )

    # Notes
    notes = models.TextField(blank=True)

    # Metadata
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_committee_members",
    )

    class Meta:
        verbose_name = "Committee Membership"
        verbose_name_plural = "Committee Memberships"
        unique_together = [["committee", "user"]]
        ordering = ["committee", "committee_role", "user__last_name"]
        indexes = [
            models.Index(fields=["committee", "is_active"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["committee_role"]),
        ]

    def __str__(self):
        return (
            f"{self.user.get_full_name()} — "
            f"{self.get_committee_role_display()} @ {self.committee.name}"
        )

    @property
    def is_term_active(self):
        if self.term_end:
            return timezone.now().date() <= self.term_end
        return True

    @property
    def days_remaining_in_term(self):
        if self.term_end:
            delta = self.term_end - timezone.now().date()
            return max(0, delta.days)
        return None


class UserBranchMembership(models.Model):
    """
    Links a user to a branch with a branch-level role.
    This is the primary access control layer — a user can only
    access data for branches they are a member of.
    A user may belong to multiple branches (e.g. a group CFO
    sitting on multiple country boards).
    """

    ACCESS_LEVELS = [
        ("full", "Full Access"),
        ("read_only", "Read Only"),
        ("limited", "Limited Access"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="branch_memberships"
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="memberships"
    )

    # Branch-level role (can differ from global user.role)
    branch_role = models.CharField(
        max_length=50,
        choices=User.ROLE_CHOICES,
        help_text="User's role specifically within this branch",
    )

    access_level = models.CharField(
        max_length=20, choices=ACCESS_LEVELS, default="full"
    )

    # Is this the user's primary / home branch?
    is_primary = models.BooleanField(
        default=False, help_text="Primary branch shown on login and dashboard"
    )

    # Term
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    # Metadata
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_branch_members",
    )

    class Meta:
        verbose_name = "User Branch Membership"
        verbose_name_plural = "User Branch Memberships"
        unique_together = [["user", "branch"]]
        ordering = ["-is_primary", "branch__name"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["branch", "is_active"]),
            models.Index(fields=["branch_role"]),
            models.Index(fields=["is_primary"]),
        ]

    def __str__(self):
        primary = " [Primary]" if self.is_primary else ""
        return (
            f"{self.user.get_full_name()} — "
            f"{self.get_branch_role_display()} @ {self.branch.name}{primary}"
        )

    @property
    def is_term_active(self):
        if self.end_date:
            return timezone.now().date() <= self.end_date
        return True

    def save(self, *args, **kwargs):
        """
        Ensure a user has only one primary branch at a time.
        """
        if self.is_primary:
            UserBranchMembership.objects.filter(
                user=self.user, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class BranchInvitation(models.Model):
    """
    Invitation token to onboard a new user into a branch.
    Admin sends invite → user registers via token link.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="invitations"
    )
    invited_email = models.EmailField()
    intended_role = models.CharField(max_length=50, choices=User.ROLE_CHOICES)
    intended_committee = models.ForeignKey(
        Committee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )

    # Token
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Expiry
    expires_at = models.DateTimeField()
    message = models.TextField(
        blank=True, help_text="Personal message to include in invitation email"
    )

    # Result
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Branch Invitation"
        verbose_name_plural = "Branch Invitations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite: {self.invited_email} → {self.branch.name}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.status == "pending" and not self.is_expired
