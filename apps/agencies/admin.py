from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Branch,
    BranchInvitation,
    Committee,
    CommitteeMembership,
    Organization,
    UserBranchMembership,
)

# ---------------------------------------------------------------------------
# INLINE ADMINS
# ---------------------------------------------------------------------------


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0
    fields = ["name", "code", "branch_type", "country", "status", "is_active"]
    show_change_link = True
    can_delete = False


class CommitteeInline(admin.TabularInline):
    model = Committee
    extra = 0
    fields = ["name", "code", "committee_type", "status", "is_active"]
    show_change_link = True
    can_delete = False


class UserBranchMembershipInline(admin.TabularInline):
    model = UserBranchMembership
    extra = 0
    fields = [
        "user",
        "branch_role",
        "access_level",
        "is_primary",
        "is_active",
        "start_date",
    ]
    raw_id_fields = ["user"]
    show_change_link = True


class CommitteeMembershipInline(admin.TabularInline):
    model = CommitteeMembership
    extra = 0
    fields = [
        "user",
        "committee_role",
        "has_voting_rights",
        "status",
        "is_active",
        "term_start",
        "term_end",
    ]
    raw_id_fields = ["user"]
    show_change_link = True


class BranchInvitationInline(admin.TabularInline):
    model = BranchInvitation
    extra = 0
    fields = ["invited_email", "intended_role", "status", "expires_at", "created_at"]
    readonly_fields = ["created_at"]
    show_change_link = True
    can_delete = False


# ---------------------------------------------------------------------------
# ORGANIZATION ADMIN
# ---------------------------------------------------------------------------


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "legal_name",
        "head_office_country",
        "total_branches_display",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "head_office_country"]
    search_fields = ["name", "legal_name", "registration_number", "primary_email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["name"]
    inlines = [BranchInline]

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "name",
                    "legal_name",
                    "registration_number",
                    "website",
                    "logo",
                )
            },
        ),
        (
            "Head Office",
            {
                "fields": (
                    "head_office_address",
                    "head_office_country",
                    "head_office_city",
                )
            },
        ),
        ("Contact", {"fields": ("primary_email", "primary_phone")}),
        (
            "Status & Metadata",
            {
                "fields": (
                    "is_active",
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_branch_count=Count("branches", distinct=True))
        )

    @admin.display(description="Branches", ordering="_branch_count")
    def total_branches_display(self, obj):
        url = (
            reverse("admin:agencies_branch_changelist")
            + f"?organization__id__exact={obj.pk}"
        )
        return format_html('<a href="{}">{} branch(es)</a>', url, obj._branch_count)


# ---------------------------------------------------------------------------
# BRANCH ADMIN
# ---------------------------------------------------------------------------


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "organization",
        "branch_type",
        "country",
        "city",
        "status",
        "total_members_display",
        "total_committees_display",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "status",
        "branch_type",
        "country",
        "organization",
        "has_own_board",
    ]
    search_fields = [
        "name",
        "code",
        "country",
        "city",
        "email",
        "organization__name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["created_by"]
    list_select_related = ["organization", "parent_branch"]
    ordering = ["organization", "country", "name"]
    inlines = [CommitteeInline, UserBranchMembershipInline, BranchInvitationInline]

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "organization",
                    "parent_branch",
                    "name",
                    "code",
                    "branch_type",
                    "status",
                    "logo",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "country",
                    "city",
                    "address",
                    "timezone_name",
                )
            },
        ),
        ("Contact", {"fields": ("email", "phone", "website")}),
        (
            "Governance",
            {
                "fields": (
                    "max_users",
                    "has_own_board",
                    "reporting_currency",
                    "established_date",
                )
            },
        ),
        (
            "Status & Metadata",
            {
                "fields": (
                    "is_active",
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _member_count=Count("memberships", distinct=True),
                _committee_count=Count("committees", distinct=True),
            )
        )

    @admin.display(description="Members", ordering="_member_count")
    def total_members_display(self, obj):
        url = (
            reverse("admin:agencies_userbranchmembership_changelist")
            + f"?branch__id__exact={obj.pk}"
        )
        return format_html('<a href="{}">{}</a>', url, obj._member_count)

    @admin.display(description="Committees", ordering="_committee_count")
    def total_committees_display(self, obj):
        url = (
            reverse("admin:agencies_committee_changelist")
            + f"?branch__id__exact={obj.pk}"
        )
        return format_html('<a href="{}">{}</a>', url, obj._committee_count)


# ---------------------------------------------------------------------------
# COMMITTEE ADMIN
# ---------------------------------------------------------------------------


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "branch",
        "committee_type",
        "status",
        "chairperson",
        "active_member_count_display",
        "is_confidential",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "status",
        "committee_type",
        "is_confidential",
        "quorum_type",
        "branch__organization",
    ]
    search_fields = [
        "name",
        "code",
        "branch__name",
        "branch__organization__name",
        "chairperson__email",
        "chairperson__first_name",
        "chairperson__last_name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["chairperson", "secretary", "created_by"]
    list_select_related = ["branch", "branch__organization", "chairperson"]
    ordering = ["branch__name", "name"]
    inlines = [CommitteeMembershipInline]

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "branch",
                    "parent_committee",
                    "name",
                    "code",
                    "committee_type",
                    "status",
                    "description",
                    "mandate",
                )
            },
        ),
        (
            "Governance",
            {
                "fields": (
                    "quorum_type",
                    "quorum_custom_value",
                    "min_members",
                    "max_members",
                    "meeting_frequency",
                    "chairperson",
                    "secretary",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "established_date",
                    "dissolution_date",
                )
            },
        ),
        (
            "Access & Metadata",
            {
                "fields": (
                    "is_active",
                    "is_confidential",
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_member_count=Count("memberships", distinct=True))
        )

    @admin.display(description="Active Members", ordering="_member_count")
    def active_member_count_display(self, obj):
        url = (
            reverse("admin:agencies_committeemembership_changelist")
            + f"?committee__id__exact={obj.pk}&is_active__exact=1"
        )
        return format_html('<a href="{}">{}</a>', url, obj._member_count)


# ---------------------------------------------------------------------------
# COMMITTEE MEMBERSHIP ADMIN
# ---------------------------------------------------------------------------


@admin.register(CommitteeMembership)
class CommitteeMembershipAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "committee",
        "committee_role",
        "status",
        "has_voting_rights",
        "term_start",
        "term_end",
        "is_active",
        "joined_at",
    ]
    list_filter = [
        "is_active",
        "status",
        "committee_role",
        "has_voting_rights",
        "committee__branch__organization",
        "committee__branch",
        "committee__committee_type",
    ]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "committee__name",
        "committee__branch__name",
    ]
    readonly_fields = ["id", "joined_at", "updated_at"]
    raw_id_fields = ["user", "added_by"]
    list_select_related = ["user", "committee", "committee__branch"]
    ordering = ["committee__branch__name", "committee__name", "committee_role"]
    date_hierarchy = "joined_at"

    fieldsets = (
        (
            "Membership",
            {
                "fields": (
                    "id",
                    "committee",
                    "user",
                    "committee_role",
                    "status",
                )
            },
        ),
        (
            "Term",
            {
                "fields": (
                    "term_start",
                    "term_end",
                    "is_current_term",
                )
            },
        ),
        (
            "Rights & Notes",
            {
                "fields": (
                    "has_voting_rights",
                    "notes",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "is_active",
                    "added_by",
                    "joined_at",
                    "updated_at",
                )
            },
        ),
    )


# ---------------------------------------------------------------------------
# USER BRANCH MEMBERSHIP ADMIN
# ---------------------------------------------------------------------------


@admin.register(UserBranchMembership)
class UserBranchMembershipAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "branch",
        "branch_role",
        "access_level",
        "is_primary",
        "is_active",
        "start_date",
        "end_date",
        "joined_at",
    ]
    list_filter = [
        "is_active",
        "is_primary",
        "branch_role",
        "access_level",
        "branch__organization",
        "branch__country",
    ]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "branch__name",
        "branch__code",
        "branch__organization__name",
    ]
    readonly_fields = ["id", "joined_at", "updated_at"]
    raw_id_fields = ["user", "added_by"]
    list_select_related = ["user", "branch", "branch__organization"]
    ordering = ["branch__name", "branch_role", "user__last_name"]
    date_hierarchy = "joined_at"

    fieldsets = (
        (
            "Membership",
            {
                "fields": (
                    "id",
                    "user",
                    "branch",
                    "branch_role",
                    "access_level",
                    "is_primary",
                )
            },
        ),
        (
            "Term",
            {
                "fields": (
                    "start_date",
                    "end_date",
                )
            },
        ),
        (
            "Notes & Metadata",
            {
                "fields": (
                    "notes",
                    "is_active",
                    "added_by",
                    "joined_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = ["activate_memberships", "deactivate_memberships"]

    @admin.action(description="Activate selected memberships")
    def activate_memberships(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} membership(s) activated.")

    @admin.action(description="Deactivate selected memberships")
    def deactivate_memberships(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} membership(s) deactivated.")


# ---------------------------------------------------------------------------
# BRANCH INVITATION ADMIN
# ---------------------------------------------------------------------------


@admin.register(BranchInvitation)
class BranchInvitationAdmin(admin.ModelAdmin):
    list_display = [
        "invited_email",
        "branch",
        "intended_role",
        "status",
        "expires_at",
        "created_by",
        "created_at",
        "accepted_by",
    ]
    list_filter = [
        "status",
        "intended_role",
        "branch__organization",
        "branch",
    ]
    search_fields = [
        "invited_email",
        "branch__name",
        "branch__organization__name",
        "created_by__email",
        "accepted_by__email",
    ]
    readonly_fields = [
        "id",
        "token",
        "created_at",
        "accepted_at",
        "invitation_link",
    ]
    raw_id_fields = ["created_by", "accepted_by"]
    list_select_related = [
        "branch",
        "branch__organization",
        "created_by",
        "accepted_by",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Invitation",
            {
                "fields": (
                    "id",
                    "branch",
                    "invited_email",
                    "intended_role",
                    "intended_committee",
                    "message",
                )
            },
        ),
        (
            "Token & Status",
            {
                "fields": (
                    "token",
                    "invitation_link",
                    "status",
                    "expires_at",
                )
            },
        ),
        (
            "Result",
            {
                "fields": (
                    "accepted_by",
                    "accepted_at",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                )
            },
        ),
    )

    @admin.display(description="Invitation Link")
    def invitation_link(self, obj):
        if obj.token:
            url = f"/agencies/invite/{obj.token}/accept/"
            return format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return "—"

    actions = ["revoke_invitations"]

    @admin.action(description="Revoke selected invitations")
    def revoke_invitations(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="revoked")
        self.message_user(request, f"{updated} invitation(s) revoked.")
