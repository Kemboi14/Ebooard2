import uuid
from datetime import timedelta

from django import forms
from django.utils import timezone

from apps.accounts.models import User

from .models import (
    Branch,
    BranchInvitation,
    Committee,
    CommitteeMembership,
    Organization,
    UserBranchMembership,
)

# ---------------------------------------------------------------------------
# Shared widget style helpers
# ---------------------------------------------------------------------------

INPUT_CLASS = (
    "w-full px-4 py-3 border border-gray-300 rounded-lg "
    "focus:ring-2 focus:ring-green-500 focus:border-transparent"
)
SELECT_CLASS = (
    "w-full px-4 py-3 border border-gray-300 rounded-lg "
    "focus:ring-2 focus:ring-green-500 focus:border-transparent bg-white"
)
TEXTAREA_CLASS = (
    "w-full px-4 py-3 border border-gray-300 rounded-lg "
    "focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
)
CHECKBOX_CLASS = "h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded"


def text_input(placeholder="", **kwargs):
    attrs = {"class": INPUT_CLASS, "placeholder": placeholder}
    attrs.update(kwargs)
    return forms.TextInput(attrs=attrs)


def email_input(placeholder="", **kwargs):
    attrs = {"class": INPUT_CLASS, "placeholder": placeholder}
    attrs.update(kwargs)
    return forms.EmailInput(attrs=attrs)


def url_input(placeholder="", **kwargs):
    attrs = {"class": INPUT_CLASS, "placeholder": placeholder}
    attrs.update(kwargs)
    return forms.URLInput(attrs=attrs)


def select_widget(**kwargs):
    attrs = {"class": SELECT_CLASS}
    attrs.update(kwargs)
    return forms.Select(attrs=attrs)


def textarea_widget(rows=4, placeholder="", **kwargs):
    attrs = {"class": TEXTAREA_CLASS, "rows": rows, "placeholder": placeholder}
    attrs.update(kwargs)
    return forms.Textarea(attrs=attrs)


def date_input(**kwargs):
    attrs = {"class": INPUT_CLASS, "type": "date"}
    attrs.update(kwargs)
    return forms.DateInput(attrs=attrs, format="%Y-%m-%d")


def number_input(placeholder="", **kwargs):
    attrs = {"class": INPUT_CLASS, "placeholder": placeholder}
    attrs.update(kwargs)
    return forms.NumberInput(attrs=attrs)


# ---------------------------------------------------------------------------
# ORGANIZATION FORM
# ---------------------------------------------------------------------------


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "legal_name",
            "registration_number",
            "website",
            "logo",
            "head_office_address",
            "head_office_country",
            "head_office_city",
            "primary_email",
            "primary_phone",
            "is_active",
        ]
        widgets = {
            "name": text_input("Organization name e.g. Enwealth Group"),
            "legal_name": text_input("Legal / registered name"),
            "registration_number": text_input("Company registration number"),
            "website": url_input("https://www.example.com"),
            "logo": forms.FileInput(attrs={"class": INPUT_CLASS}),
            "head_office_address": textarea_widget(
                rows=3, placeholder="Head office street address"
            ),
            "head_office_country": text_input("Country"),
            "head_office_city": text_input("City"),
            "primary_email": email_input("contact@organization.com"),
            "primary_phone": text_input("+1 (555) 000-0000"),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Organization name is required.")
        return name


# ---------------------------------------------------------------------------
# BRANCH FORM
# ---------------------------------------------------------------------------

COMMON_TIMEZONES = [
    ("Africa/Nairobi", "Africa/Nairobi (EAT)"),
    ("Africa/Lagos", "Africa/Lagos (WAT)"),
    ("Africa/Cairo", "Africa/Cairo (EET)"),
    ("Africa/Johannesburg", "Africa/Johannesburg (SAST)"),
    ("America/New_York", "America/New_York (EST/EDT)"),
    ("America/Chicago", "America/Chicago (CST/CDT)"),
    ("America/Los_Angeles", "America/Los_Angeles (PST/PDT)"),
    ("America/Sao_Paulo", "America/Sao_Paulo (BRT)"),
    ("Europe/London", "Europe/London (GMT/BST)"),
    ("Europe/Paris", "Europe/Paris (CET/CEST)"),
    ("Europe/Berlin", "Europe/Berlin (CET/CEST)"),
    ("Europe/Moscow", "Europe/Moscow (MSK)"),
    ("Asia/Dubai", "Asia/Dubai (GST)"),
    ("Asia/Karachi", "Asia/Karachi (PKT)"),
    ("Asia/Kolkata", "Asia/Kolkata (IST)"),
    ("Asia/Singapore", "Asia/Singapore (SGT)"),
    ("Asia/Tokyo", "Asia/Tokyo (JST)"),
    ("Asia/Shanghai", "Asia/Shanghai (CST)"),
    ("Australia/Sydney", "Australia/Sydney (AEST/AEDT)"),
    ("Pacific/Auckland", "Pacific/Auckland (NZST/NZDT)"),
]


class BranchForm(forms.ModelForm):
    timezone_name = forms.ChoiceField(
        choices=COMMON_TIMEZONES,
        widget=select_widget(),
        label="Timezone",
        initial="Africa/Nairobi",
    )

    class Meta:
        model = Branch
        fields = [
            "organization",
            "parent_branch",
            "name",
            "code",
            "branch_type",
            "status",
            "country",
            "city",
            "address",
            "timezone_name",
            "email",
            "phone",
            "website",
            "logo",
            "max_users",
            "has_own_board",
            "reporting_currency",
            "established_date",
            "is_active",
        ]
        widgets = {
            "organization": select_widget(),
            "parent_branch": select_widget(),
            "name": text_input("Branch / office name e.g. Enwealth Kenya"),
            "code": text_input("Unique branch code e.g. EN-KE-001"),
            "branch_type": select_widget(),
            "status": select_widget(),
            "country": text_input("Country e.g. Kenya"),
            "city": text_input("City e.g. Nairobi"),
            "address": textarea_widget(rows=3, placeholder="Physical office address"),
            "email": email_input("branch@enwealth.com"),
            "phone": text_input("+254 700 000 000"),
            "website": url_input("https://branch.enwealth.com"),
            "logo": forms.FileInput(attrs={"class": INPUT_CLASS}),
            "max_users": number_input("1000"),
            "reporting_currency": text_input("USD"),
            "established_date": date_input(),
            "has_own_board": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        if not code:
            raise forms.ValidationError("Branch code is required.")
        qs = Branch.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f"Branch code '{code}' is already in use. Please choose a unique code."
            )
        return code

    def clean_max_users(self):
        max_users = self.cleaned_data.get("max_users", 1000)
        if max_users < 1:
            raise forms.ValidationError("Maximum users must be at least 1.")
        if max_users > 100000:
            raise forms.ValidationError("Maximum users cannot exceed 100,000.")
        return max_users

    def clean(self):
        cleaned = super().clean()
        org = cleaned.get("organization")
        parent = cleaned.get("parent_branch")
        if parent and org and parent.organization != org:
            self.add_error(
                "parent_branch",
                "Parent branch must belong to the same organization.",
            )
        return cleaned


# ---------------------------------------------------------------------------
# COMMITTEE FORM
# ---------------------------------------------------------------------------


class CommitteeForm(forms.ModelForm):
    """
    The `user` kwarg is injected from the view so we can restrict
    the branch dropdown to only branches the user has access to.
    """

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.role != "it_administrator":
            from .models import UserBranchMembership

            branch_ids = UserBranchMembership.objects.filter(
                user=user, is_active=True
            ).values_list("branch_id", flat=True)
            self.fields["branch"].queryset = Branch.objects.filter(
                id__in=branch_ids, is_active=True
            )
            # Only committees in accessible branches as parents
            self.fields["parent_committee"].queryset = Committee.objects.filter(
                branch_id__in=branch_ids, is_active=True
            )

    class Meta:
        model = Committee
        fields = [
            "branch",
            "parent_committee",
            "name",
            "code",
            "committee_type",
            "status",
            "description",
            "mandate",
            "quorum_type",
            "quorum_custom_value",
            "min_members",
            "max_members",
            "meeting_frequency",
            "chairperson",
            "secretary",
            "established_date",
            "dissolution_date",
            "is_confidential",
            "is_active",
        ]
        widgets = {
            "branch": select_widget(),
            "parent_committee": select_widget(),
            "name": text_input("Committee name e.g. Board of Directors"),
            "code": text_input("Short code e.g. BOD, AUDIT, RISK"),
            "committee_type": select_widget(),
            "status": select_widget(),
            "description": textarea_widget(
                rows=3, placeholder="Brief committee description"
            ),
            "mandate": textarea_widget(
                rows=4,
                placeholder="Committee mandate and terms of reference",
            ),
            "quorum_type": select_widget(),
            "quorum_custom_value": number_input("e.g. 5"),
            "min_members": number_input("3"),
            "max_members": number_input("15"),
            "meeting_frequency": text_input("e.g. Monthly, Quarterly, As needed"),
            "chairperson": select_widget(),
            "secretary": select_widget(),
            "established_date": date_input(),
            "dissolution_date": date_input(),
            "is_confidential": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        branch = self.cleaned_data.get("branch")
        if not code:
            raise forms.ValidationError("Committee code is required.")
        if branch:
            qs = Committee.objects.filter(branch=branch, code=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"Code '{code}' is already used by another committee in this branch."
                )
        return code

    def clean(self):
        cleaned = super().clean()
        min_m = cleaned.get("min_members", 3)
        max_m = cleaned.get("max_members", 15)
        if min_m and max_m and min_m > max_m:
            self.add_error(
                "min_members",
                "Minimum members cannot exceed maximum members.",
            )
        quorum = cleaned.get("quorum_type")
        custom_val = cleaned.get("quorum_custom_value")
        if quorum == "custom" and not custom_val:
            self.add_error(
                "quorum_custom_value",
                "Please specify a custom quorum value.",
            )
        return cleaned


# ---------------------------------------------------------------------------
# COMMITTEE MEMBERSHIP FORM
# ---------------------------------------------------------------------------


class CommitteeMembershipForm(forms.ModelForm):
    """
    The `committee` kwarg restricts the user dropdown to members of the
    committee's branch.
    """

    def __init__(self, *args, committee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if committee:
            # Only users who are members of the branch
            branch_user_ids = UserBranchMembership.objects.filter(
                branch=committee.branch, is_active=True
            ).values_list("user_id", flat=True)
            # Exclude users already in this committee
            existing_user_ids = CommitteeMembership.objects.filter(
                committee=committee
            ).values_list("user_id", flat=True)
            self.fields["user"].queryset = User.objects.filter(
                id__in=branch_user_ids, is_active=True
            ).exclude(id__in=existing_user_ids)

    class Meta:
        model = CommitteeMembership
        fields = [
            "user",
            "committee_role",
            "status",
            "term_start",
            "term_end",
            "has_voting_rights",
            "notes",
        ]
        widgets = {
            "user": select_widget(),
            "committee_role": select_widget(),
            "status": select_widget(),
            "term_start": date_input(),
            "term_end": date_input(),
            "has_voting_rights": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "notes": textarea_widget(rows=2, placeholder="Optional notes"),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("term_start")
        end = cleaned.get("term_end")
        if start and end and end < start:
            self.add_error("term_end", "Term end date cannot be before start date.")
        return cleaned


# ---------------------------------------------------------------------------
# USER BRANCH MEMBERSHIP FORM
# ---------------------------------------------------------------------------


class UserBranchMembershipForm(forms.ModelForm):
    """
    The `branch` kwarg is injected from the view.
    The user dropdown shows only users NOT already in the branch.
    """

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        if branch:
            existing_user_ids = UserBranchMembership.objects.filter(
                branch=branch
            ).values_list("user_id", flat=True)
            self.fields["user"].queryset = User.objects.filter(is_active=True).exclude(
                id__in=existing_user_ids
            )

    class Meta:
        model = UserBranchMembership
        fields = [
            "user",
            "branch_role",
            "access_level",
            "is_primary",
            "start_date",
            "end_date",
            "notes",
        ]
        widgets = {
            "user": select_widget(),
            "branch_role": select_widget(),
            "access_level": select_widget(),
            "is_primary": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
            "start_date": date_input(),
            "end_date": date_input(),
            "notes": textarea_widget(rows=2, placeholder="Optional notes"),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before start date.")
        return cleaned


# ---------------------------------------------------------------------------
# BRANCH INVITATION FORM
# ---------------------------------------------------------------------------


class BranchInvitationForm(forms.ModelForm):
    """
    The `branch` kwarg is injected from the view.
    """

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        if branch:
            self.fields["intended_committee"].queryset = Committee.objects.filter(
                branch=branch, is_active=True
            )

    class Meta:
        model = BranchInvitation
        fields = [
            "invited_email",
            "intended_role",
            "intended_committee",
            "message",
        ]
        widgets = {
            "invited_email": email_input("person@example.com"),
            "intended_role": select_widget(),
            "intended_committee": select_widget(),
            "message": textarea_widget(
                rows=4,
                placeholder="Personal message to include in the invitation email (optional)",
            ),
        }

    def clean_invited_email(self):
        email = self.cleaned_data.get("invited_email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Email address is required.")
        return email


# ---------------------------------------------------------------------------
# BRANCH / COMMITTEE SEARCH / FILTER FORMS (used in list views)
# ---------------------------------------------------------------------------


class BranchSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=text_input("Search branches by name, code or country…"),
        label="Search",
    )
    country = forms.CharField(
        required=False,
        widget=text_input("Country"),
        label="Country",
    )
    branch_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Types")] + list(Branch.BRANCH_TYPES),
        widget=select_widget(),
        label="Branch Type",
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(Branch.STATUS_CHOICES),
        widget=select_widget(),
        label="Status",
    )


class CommitteeSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=text_input("Search committees by name or code…"),
        label="Search",
    )
    committee_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Types")] + list(Committee.COMMITTEE_TYPES),
        widget=select_widget(),
        label="Committee Type",
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(Committee.STATUS_CHOICES),
        widget=select_widget(),
        label="Status",
    )
