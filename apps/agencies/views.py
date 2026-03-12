import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.accounts.decorators import role_required
from apps.accounts.models import User

from .forms import (
    BranchForm,
    BranchInvitationForm,
    CommitteeForm,
    CommitteeMembershipForm,
    OrganizationForm,
    UserBranchMembershipForm,
)
from .mixins import BranchAccessMixin, OrganizationAdminMixin
from .models import (
    Branch,
    BranchInvitation,
    Committee,
    CommitteeMembership,
    Organization,
    UserBranchMembership,
)

# ---------------------------------------------------------------------------
# ORGANIZATION VIEWS
# ---------------------------------------------------------------------------


class OrganizationListView(LoginRequiredMixin, ListView):
    """List all organizations — visible to IT admins only."""

    model = Organization
    template_name = "agencies/organization_list.html"
    context_object_name = "organizations"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "it_administrator":
            messages.error(request, "You do not have permission to view organizations.")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Organization.objects.annotate(
            branch_count=Count("branches", filter=Q(branches__is_active=True)),
        )
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(legal_name__icontains=search)
                | Q(head_office_country__icontains=search)
            )
        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_organizations"] = Organization.objects.filter(is_active=True).count()
        ctx["total_branches"] = Branch.objects.filter(is_active=True).count()
        ctx["total_users"] = (
            UserBranchMembership.objects.filter(is_active=True)
            .values("user")
            .distinct()
            .count()
        )
        ctx["search_query"] = self.request.GET.get("q", "")
        return ctx


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    """Organization detail — full branch tree, stats."""

    model = Organization
    template_name = "agencies/organization_detail.html"
    context_object_name = "organization"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "it_administrator":
            messages.error(request, "Access denied.")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.object

        # Top-level branches (no parent)
        ctx["top_branches"] = Branch.objects.filter(
            organization=org, parent_branch__isnull=True, is_active=True
        ).annotate(
            member_count=Count("memberships", filter=Q(memberships__is_active=True)),
            committee_count=Count("committees", filter=Q(committees__is_active=True)),
        )

        ctx["all_branches"] = Branch.objects.filter(organization=org).order_by(
            "country", "name"
        )

        ctx["total_committees"] = Committee.objects.filter(
            branch__organization=org, is_active=True
        ).count()

        ctx["recent_invitations"] = BranchInvitation.objects.filter(
            branch__organization=org
        ).order_by("-created_at")[:10]

        return ctx


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "agencies/organization_form.html"
    success_url = reverse_lazy("agencies:organization_list")

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "it_administrator":
            messages.error(request, "Only IT Administrators can create organizations.")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(
            self.request, f"Organization '{form.instance.name}' created successfully."
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Create Organization"
        ctx["is_update"] = False
        return ctx


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "agencies/organization_form.html"
    success_url = reverse_lazy("agencies:organization_list")

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "it_administrator":
            messages.error(request, "Only IT Administrators can edit organizations.")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(
            self.request, f"Organization '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Edit Organization: {self.object.name}"
        ctx["is_update"] = True
        return ctx


# ---------------------------------------------------------------------------
# BRANCH VIEWS
# ---------------------------------------------------------------------------


class BranchListView(LoginRequiredMixin, ListView):
    """
    List branches the current user belongs to.
    IT admins see all branches across all organizations.
    """

    model = Branch
    template_name = "agencies/branch_list.html"
    context_object_name = "branches"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role == "it_administrator":
            qs = Branch.objects.select_related("organization", "parent_branch")
        else:
            # Only branches where user has an active membership
            user_branch_ids = UserBranchMembership.objects.filter(
                user=user, is_active=True
            ).values_list("branch_id", flat=True)
            qs = Branch.objects.filter(id__in=user_branch_ids).select_related(
                "organization", "parent_branch"
            )

        # Filters
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(country__icontains=search)
            )

        country = self.request.GET.get("country")
        if country:
            qs = qs.filter(country=country)

        branch_type = self.request.GET.get("type")
        if branch_type:
            qs = qs.filter(branch_type=branch_type)

        org_id = self.request.GET.get("org")
        if org_id and user.role == "it_administrator":
            qs = qs.filter(organization_id=org_id)

        return qs.annotate(
            member_count=Count("memberships", filter=Q(memberships__is_active=True)),
            committee_count=Count("committees", filter=Q(committees__is_active=True)),
        ).order_by("country", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        ctx["branch_types"] = Branch.BRANCH_TYPES
        ctx["search_query"] = self.request.GET.get("q", "")
        ctx["selected_country"] = self.request.GET.get("country", "")
        ctx["selected_type"] = self.request.GET.get("type", "")

        # Countries list for filter
        if user.role == "it_administrator":
            ctx["countries"] = (
                Branch.objects.filter(is_active=True)
                .values_list("country", flat=True)
                .distinct()
                .order_by("country")
            )
            ctx["organizations"] = Organization.objects.filter(is_active=True)
        else:
            user_branch_ids = UserBranchMembership.objects.filter(
                user=user, is_active=True
            ).values_list("branch_id", flat=True)
            ctx["countries"] = (
                Branch.objects.filter(id__in=user_branch_ids)
                .values_list("country", flat=True)
                .distinct()
                .order_by("country")
            )

        # User's primary branch
        ctx["primary_branch"] = (
            UserBranchMembership.objects.filter(
                user=user, is_primary=True, is_active=True
            )
            .select_related("branch")
            .first()
        )

        ctx["can_create_branch"] = user.role == "it_administrator"
        return ctx


class BranchDetailView(LoginRequiredMixin, DetailView):
    """Branch detail — committees, members, meetings summary."""

    model = Branch
    template_name = "agencies/branch_detail.html"
    context_object_name = "branch"

    def dispatch(self, request, *args, **kwargs):
        branch = get_object_or_404(Branch, pk=kwargs["pk"])
        user = request.user
        if user.role != "it_administrator":
            has_access = UserBranchMembership.objects.filter(
                user=user, branch=branch, is_active=True
            ).exists()
            if not has_access:
                messages.error(request, "You do not have access to this branch.")
                return redirect("agencies:branch_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        branch = self.object
        user = self.request.user

        # Committees grouped by type
        ctx["committees"] = (
            Committee.objects.filter(branch=branch, is_active=True)
            .annotate(
                member_count=Count("memberships", filter=Q(memberships__is_active=True))
            )
            .order_by("committee_type", "name")
        )

        # Members list
        ctx["members"] = (
            UserBranchMembership.objects.filter(branch=branch, is_active=True)
            .select_related("user")
            .order_by("branch_role", "user__last_name")
        )

        # Role breakdown
        ctx["role_counts"] = (
            UserBranchMembership.objects.filter(branch=branch, is_active=True)
            .values("branch_role")
            .annotate(count=Count("id"))
            .order_by("branch_role")
        )

        # Sub-branches
        ctx["sub_branches"] = Branch.objects.filter(
            parent_branch=branch, is_active=True
        ).annotate(
            member_count=Count("memberships", filter=Q(memberships__is_active=True))
        )

        # Pending invitations
        ctx["pending_invitations"] = BranchInvitation.objects.filter(
            branch=branch, status="pending"
        ).order_by("-created_at")[:10]

        # User's membership in this branch
        try:
            ctx["user_membership"] = UserBranchMembership.objects.get(
                user=user, branch=branch
            )
        except UserBranchMembership.DoesNotExist:
            ctx["user_membership"] = None

        # User's committees in this branch
        ctx["user_committees"] = CommitteeMembership.objects.filter(
            user=user, committee__branch=branch, is_active=True
        ).select_related("committee")

        ctx["can_manage"] = user.role in ["it_administrator", "company_secretary"]
        ctx["can_invite"] = user.role in ["it_administrator", "company_secretary"]
        ctx["ancestor_branches"] = branch.get_hierarchy_path()
        ctx["can_deactivate"] = user.role == "it_administrator"

        return ctx


class BranchCreateView(LoginRequiredMixin, CreateView):
    model = Branch
    form_class = BranchForm
    template_name = "agencies/branch_form.html"
    success_url = reverse_lazy("agencies:branch_list")

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "it_administrator":
            messages.error(request, "Only IT Administrators can create branches.")
            return redirect("agencies:branch_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(
            self.request,
            f"Branch '{form.instance.name}' [{form.instance.code}] created successfully.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("agencies:branch_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Create Branch"
        ctx["is_update"] = False
        return ctx


class BranchUpdateView(LoginRequiredMixin, UpdateView):
    model = Branch
    form_class = BranchForm
    template_name = "agencies/branch_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "it_administrator":
            messages.error(request, "Only IT Administrators can edit branches.")
            return redirect("agencies:branch_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(
            self.request, f"Branch '{form.instance.name}' updated successfully."
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("agencies:branch_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Edit Branch: {self.object.name}"
        ctx["is_update"] = True
        return ctx


@login_required
def toggle_branch_active(request, pk):
    """Deactivate or reactivate a branch (IT admin only)."""
    if request.user.role != "it_administrator":
        messages.error(request, "Only IT Administrators can deactivate branches.")
        return redirect("agencies:branch_detail", pk=pk)

    branch = get_object_or_404(Branch, pk=pk)

    if request.method == "POST":
        if branch.is_active:
            branch.is_active = False
            branch.status = "inactive"
            branch.save(update_fields=["is_active", "status", "updated_at"])
            messages.warning(
                request,
                f"Branch '{branch.name}' has been deactivated. Members can no longer access it.",
            )
        else:
            branch.is_active = True
            branch.status = "active"
            branch.save(update_fields=["is_active", "status", "updated_at"])
            messages.success(
                request,
                f"Branch '{branch.name}' has been reactivated successfully.",
            )

    return redirect("agencies:branch_detail", pk=pk)


# ---------------------------------------------------------------------------
# COMMITTEE VIEWS
# ---------------------------------------------------------------------------


class CommitteeListView(LoginRequiredMixin, ListView):
    """List committees the user belongs to or can see."""

    model = Committee
    template_name = "agencies/committee_list.html"
    context_object_name = "committees"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role == "it_administrator":
            qs = Committee.objects.select_related(
                "branch", "branch__organization", "chairperson"
            )
        else:
            # Committees in branches user belongs to
            user_branch_ids = UserBranchMembership.objects.filter(
                user=user, is_active=True
            ).values_list("branch_id", flat=True)

            qs = Committee.objects.filter(
                branch_id__in=user_branch_ids, is_active=True
            ).select_related("branch", "branch__organization", "chairperson")

            # Exclude confidential committees where user is not a member
            user_committee_ids = CommitteeMembership.objects.filter(
                user=user, is_active=True
            ).values_list("committee_id", flat=True)
            qs = qs.filter(Q(is_confidential=False) | Q(id__in=user_committee_ids))

        # Filters
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))

        branch_id = self.request.GET.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        committee_type = self.request.GET.get("type")
        if committee_type:
            qs = qs.filter(committee_type=committee_type)

        return qs.annotate(
            member_count=Count("memberships", filter=Q(memberships__is_active=True))
        ).order_by("branch__name", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["committee_types"] = Committee.COMMITTEE_TYPES
        ctx["search_query"] = self.request.GET.get("q", "")
        ctx["selected_type"] = self.request.GET.get("type", "")
        ctx["selected_branch"] = self.request.GET.get("branch", "")

        # Branches for filter dropdown
        if user.role == "it_administrator":
            ctx["branches"] = Branch.objects.filter(is_active=True).order_by("name")
        else:
            user_branch_ids = UserBranchMembership.objects.filter(
                user=user, is_active=True
            ).values_list("branch_id", flat=True)
            ctx["branches"] = Branch.objects.filter(
                id__in=user_branch_ids, is_active=True
            ).order_by("name")

        # My committees
        ctx["my_committees"] = CommitteeMembership.objects.filter(
            user=user, is_active=True
        ).select_related("committee", "committee__branch")

        ctx["can_create"] = user.role in ["it_administrator", "company_secretary"]
        return ctx


class CommitteeDetailView(LoginRequiredMixin, DetailView):
    """Committee detail — members, meetings, voting."""

    model = Committee
    template_name = "agencies/committee_detail.html"
    context_object_name = "committee"

    def dispatch(self, request, *args, **kwargs):
        committee = get_object_or_404(Committee, pk=kwargs["pk"])
        user = request.user

        if user.role == "it_administrator":
            return super().dispatch(request, *args, **kwargs)

        # Must be a member of the branch
        has_branch_access = UserBranchMembership.objects.filter(
            user=user, branch=committee.branch, is_active=True
        ).exists()

        if not has_branch_access:
            messages.error(request, "You do not have access to this committee.")
            return redirect("agencies:committee_list")

        # Confidential committee check
        if committee.is_confidential:
            is_member = CommitteeMembership.objects.filter(
                user=user, committee=committee, is_active=True
            ).exists()
            if not is_member:
                messages.error(
                    request, "This is a confidential committee. Access restricted."
                )
                return redirect("agencies:committee_list")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        committee = self.object
        user = self.request.user

        ctx["memberships"] = (
            CommitteeMembership.objects.filter(committee=committee, is_active=True)
            .select_related("user")
            .order_by("committee_role", "user__last_name")
        )

        ctx["inactive_memberships"] = (
            CommitteeMembership.objects.filter(committee=committee, is_active=False)
            .select_related("user")
            .order_by("-updated_at")[:10]
        )

        # Sub-committees
        ctx["sub_committees"] = Committee.objects.filter(
            parent_committee=committee, is_active=True
        ).annotate(
            member_count=Count("memberships", filter=Q(memberships__is_active=True))
        )

        # Current user's membership
        try:
            ctx["user_membership"] = CommitteeMembership.objects.get(
                user=user, committee=committee
            )
        except CommitteeMembership.DoesNotExist:
            ctx["user_membership"] = None

        ctx["can_manage"] = user.role in ["it_administrator", "company_secretary"]
        ctx["role_breakdown"] = (
            CommitteeMembership.objects.filter(committee=committee, is_active=True)
            .values("committee_role")
            .annotate(count=Count("id"))
        )

        return ctx


class CommitteeCreateView(LoginRequiredMixin, CreateView):
    model = Committee
    form_class = CommitteeForm
    template_name = "agencies/committee_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ["it_administrator", "company_secretary"]:
            messages.error(request, "You do not have permission to create committees.")
            return redirect("agencies:committee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(
            self.request,
            f"Committee '{form.instance.name}' created successfully.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("agencies:committee_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Create Committee"
        ctx["is_update"] = False
        return ctx


class CommitteeUpdateView(LoginRequiredMixin, UpdateView):
    model = Committee
    form_class = CommitteeForm
    template_name = "agencies/committee_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ["it_administrator", "company_secretary"]:
            messages.error(request, "You do not have permission to edit committees.")
            return redirect("agencies:committee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Committee '{form.instance.name}' updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("agencies:committee_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Edit Committee: {self.object.name}"
        ctx["is_update"] = True
        return ctx


# ---------------------------------------------------------------------------
# MEMBERSHIP VIEWS
# ---------------------------------------------------------------------------


@login_required
def manage_branch_members(request, branch_pk):
    """Add / remove users from a branch."""
    branch = get_object_or_404(Branch, pk=branch_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(request, "You do not have permission to manage branch members.")
        return redirect("agencies:branch_detail", pk=branch_pk)

    memberships = (
        UserBranchMembership.objects.filter(branch=branch)
        .select_related("user")
        .order_by("branch_role", "user__last_name")
    )

    if request.method == "POST":
        form = UserBranchMembershipForm(request.POST, branch=branch)
        if form.is_valid():
            membership = form.save(commit=False)
            membership.branch = branch
            membership.added_by = request.user

            # Enforce user limit
            if not branch.can_add_user():
                messages.error(
                    request,
                    f"Branch has reached its maximum user limit of {branch.max_users}.",
                )
                return redirect("agencies:manage_branch_members", branch_pk=branch_pk)

            membership.save()
            messages.success(
                request,
                f"{membership.user.get_full_name()} added to {branch.name} "
                f"as {membership.get_branch_role_display()}.",
            )
            return redirect("agencies:manage_branch_members", branch_pk=branch_pk)
    else:
        form = UserBranchMembershipForm(branch=branch)

    return render(
        request,
        "agencies/manage_branch_members.html",
        {
            "branch": branch,
            "memberships": memberships,
            "form": form,
            "active_count": memberships.filter(is_active=True).count(),
        },
    )


@login_required
def toggle_branch_membership(request, membership_pk):
    """Activate or deactivate a branch membership."""
    membership = get_object_or_404(UserBranchMembership, pk=membership_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(request, "Permission denied.")
        return redirect("agencies:branch_detail", pk=membership.branch.pk)

    if request.method == "POST":
        membership.is_active = not membership.is_active
        membership.save()
        state = "activated" if membership.is_active else "deactivated"
        messages.success(
            request,
            f"{membership.user.get_full_name()}'s membership {state}.",
        )

    return redirect("agencies:manage_branch_members", branch_pk=membership.branch.pk)


@login_required
def set_primary_branch(request, membership_pk):
    """Let a user switch their primary branch."""
    membership = get_object_or_404(
        UserBranchMembership, pk=membership_pk, user=request.user
    )

    if request.method == "POST":
        membership.is_primary = True
        membership.save()  # save() handles clearing old primary
        messages.success(
            request, f"{membership.branch.name} set as your primary branch."
        )

    return redirect("agencies:branch_list")


@login_required
def manage_committee_members(request, committee_pk):
    """Add / remove members from a committee."""
    committee = get_object_or_404(Committee, pk=committee_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(
            request, "You do not have permission to manage committee members."
        )
        return redirect("agencies:committee_detail", pk=committee_pk)

    memberships = (
        CommitteeMembership.objects.filter(committee=committee)
        .select_related("user")
        .order_by("committee_role", "user__last_name")
    )

    if request.method == "POST":
        form = CommitteeMembershipForm(request.POST, committee=committee)
        if form.is_valid():
            # Check max members
            active_count = memberships.filter(is_active=True).count()
            if active_count >= committee.max_members:
                messages.error(
                    request,
                    f"Committee has reached its maximum of {committee.max_members} members.",
                )
                return redirect(
                    "agencies:manage_committee_members", committee_pk=committee_pk
                )

            membership = form.save(commit=False)
            membership.committee = committee
            membership.added_by = request.user
            membership.save()
            messages.success(
                request,
                f"{membership.user.get_full_name()} added to {committee.name} "
                f"as {membership.get_committee_role_display()}.",
            )
            return redirect(
                "agencies:manage_committee_members", committee_pk=committee_pk
            )
    else:
        form = CommitteeMembershipForm(committee=committee)

    return render(
        request,
        "agencies/manage_committee_members.html",
        {
            "committee": committee,
            "memberships": memberships,
            "form": form,
            "active_count": memberships.filter(is_active=True).count(),
        },
    )


@login_required
def toggle_committee_membership(request, membership_pk):
    """Activate or deactivate a committee membership."""
    membership = get_object_or_404(CommitteeMembership, pk=membership_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(request, "Permission denied.")
        return redirect("agencies:committee_detail", pk=membership.committee.pk)

    if request.method == "POST":
        membership.is_active = not membership.is_active
        membership.save()
        state = "activated" if membership.is_active else "deactivated"
        messages.success(
            request,
            f"{membership.user.get_full_name()}'s committee membership {state}.",
        )

    return redirect(
        "agencies:manage_committee_members", committee_pk=membership.committee.pk
    )


# ---------------------------------------------------------------------------
# INVITATION VIEWS
# ---------------------------------------------------------------------------


@login_required
def send_invitation(request, branch_pk):
    """Send an email invitation to join a branch."""
    branch = get_object_or_404(Branch, pk=branch_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(request, "You do not have permission to send invitations.")
        return redirect("agencies:branch_detail", pk=branch_pk)

    if request.method == "POST":
        form = BranchInvitationForm(request.POST, branch=branch)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.branch = branch
            invitation.created_by = request.user
            invitation.expires_at = timezone.now() + timedelta(days=7)
            invitation.save()

            # TODO: Send invitation email via Celery task
            # send_branch_invitation_email.delay(invitation.pk)

            messages.success(
                request,
                f"Invitation sent to {invitation.invited_email} for {branch.name}.",
            )
            return redirect("agencies:branch_detail", pk=branch_pk)
    else:
        form = BranchInvitationForm(branch=branch)

    return render(
        request,
        "agencies/send_invitation.html",
        {"branch": branch, "form": form},
    )


@login_required
def invitation_list(request, branch_pk):
    """List all invitations for a branch."""
    branch = get_object_or_404(Branch, pk=branch_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(request, "Permission denied.")
        return redirect("agencies:branch_detail", pk=branch_pk)

    invitations = BranchInvitation.objects.filter(branch=branch).order_by("-created_at")

    status_filter = request.GET.get("status")
    if status_filter:
        invitations = invitations.filter(status=status_filter)

    paginator = Paginator(invitations, 20)
    page = request.GET.get("page")
    invitations_page = paginator.get_page(page)

    return render(
        request,
        "agencies/invitation_list.html",
        {
            "branch": branch,
            "invitations": invitations_page,
            "status_filter": status_filter or "",
            "pending_count": BranchInvitation.objects.filter(
                branch=branch, status="pending"
            ).count(),
        },
    )


def accept_invitation(request, token):
    """
    Public view — user clicks link from invitation email.
    Creates account or links existing account to the branch.
    """
    invitation = get_object_or_404(BranchInvitation, token=token)

    if not invitation.is_valid:
        messages.error(
            request,
            "This invitation link is no longer valid. It may have expired or been revoked.",
        )
        return redirect("accounts:login")

    if request.method == "POST":
        if request.user.is_authenticated:
            # Link existing user
            if request.user.email.lower() != invitation.invited_email.lower():
                messages.error(
                    request,
                    "This invitation was sent to a different email address. "
                    "Please log in with the correct account.",
                )
                return redirect("accounts:login")

            # Create branch membership
            membership, created = UserBranchMembership.objects.get_or_create(
                user=request.user,
                branch=invitation.branch,
                defaults={
                    "branch_role": invitation.intended_role,
                    "is_primary": not UserBranchMembership.objects.filter(
                        user=request.user, is_primary=True
                    ).exists(),
                    "added_by": invitation.created_by,
                },
            )

            if not created:
                membership.is_active = True
                membership.save()

            # Also add to committee if specified
            if invitation.intended_committee:
                CommitteeMembership.objects.get_or_create(
                    user=request.user,
                    committee=invitation.intended_committee,
                    defaults={
                        "committee_role": "member",
                        "added_by": invitation.created_by,
                    },
                )

            # Mark invitation accepted
            invitation.status = "accepted"
            invitation.accepted_by = request.user
            invitation.accepted_at = timezone.now()
            invitation.save()

            messages.success(
                request,
                f"Welcome to {invitation.branch.name}! You have been successfully added.",
            )
            return redirect("agencies:branch_detail", pk=invitation.branch.pk)

        else:
            # Redirect to login with invitation token in session
            request.session["pending_invitation_token"] = str(token)
            messages.info(
                request,
                "Please log in or create an account to accept this invitation.",
            )
            return redirect(f"/auth/login/?next=/agencies/invite/{token}/accept/")

    return render(
        request,
        "agencies/accept_invitation.html",
        {"invitation": invitation},
    )


@login_required
def revoke_invitation(request, invitation_pk):
    """Revoke a pending invitation."""
    invitation = get_object_or_404(BranchInvitation, pk=invitation_pk)

    if request.user.role not in ["it_administrator", "company_secretary"]:
        messages.error(request, "Permission denied.")
        return redirect("agencies:branch_detail", pk=invitation.branch.pk)

    if request.method == "POST":
        invitation.status = "revoked"
        invitation.save()
        messages.success(
            request, f"Invitation to {invitation.invited_email} has been revoked."
        )

    return redirect("agencies:invitation_list", branch_pk=invitation.branch.pk)


# ---------------------------------------------------------------------------
# AGENCY DASHBOARD & OVERVIEW
# ---------------------------------------------------------------------------


@login_required
def agency_dashboard(request):
    """
    Multi-agency overview dashboard.
    IT admins see global stats across all orgs and branches.
    Others see their personal multi-branch membership overview.
    """
    user = request.user

    if user.role == "it_administrator":
        # Global overview
        context = {
            "total_organizations": Organization.objects.filter(is_active=True).count(),
            "total_branches": Branch.objects.filter(is_active=True).count(),
            "total_committees": Committee.objects.filter(is_active=True).count(),
            "total_active_members": UserBranchMembership.objects.filter(is_active=True)
            .values("user")
            .distinct()
            .count(),
            "pending_invitations": BranchInvitation.objects.filter(
                status="pending"
            ).count(),
            "organizations": Organization.objects.filter(is_active=True).annotate(
                branch_count=Count("branches", filter=Q(branches__is_active=True))
            )[:10],
            "recent_branches": Branch.objects.filter(is_active=True).order_by(
                "-created_at"
            )[:8],
            "branch_type_breakdown": Branch.objects.filter(is_active=True)
            .values("branch_type")
            .annotate(count=Count("id"))
            .order_by("-count"),
            "country_breakdown": Branch.objects.filter(is_active=True)
            .values("country")
            .annotate(count=Count("id"))
            .order_by("-count")[:10],
            "is_global_admin": True,
        }
    else:
        # Personal multi-branch overview
        user_memberships = UserBranchMembership.objects.filter(
            user=user, is_active=True
        ).select_related("branch", "branch__organization")

        user_branch_ids = user_memberships.values_list("branch_id", flat=True)

        committee_memberships = CommitteeMembership.objects.filter(
            user=user, is_active=True
        ).select_related("committee", "committee__branch")

        primary_membership = user_memberships.filter(is_primary=True).first()

        context = {
            "user_memberships": user_memberships,
            "committee_memberships": committee_memberships,
            "primary_membership": primary_membership,
            "branch_count": user_memberships.count(),
            "committee_count": committee_memberships.count(),
            "pending_invitations": BranchInvitation.objects.filter(
                invited_email=user.email, status="pending"
            ).count(),
            "is_global_admin": False,
        }

    return render(request, "agencies/agency_dashboard.html", context)


@login_required
def switch_branch_context(request, branch_pk):
    """
    Switch the user's active branch context stored in session.
    This makes the dashboard, meetings, documents etc. filter
    to the selected branch automatically.
    """
    branch = get_object_or_404(Branch, pk=branch_pk)
    user = request.user

    has_access = (
        user.role == "it_administrator"
        or UserBranchMembership.objects.filter(
            user=user, branch=branch, is_active=True
        ).exists()
    )

    if not has_access:
        messages.error(request, "You do not have access to this branch.")
        return redirect("agencies:agency_dashboard")

    request.session["active_branch_id"] = str(branch.pk)
    request.session["active_branch_name"] = branch.name
    request.session["active_branch_code"] = branch.code

    messages.success(request, f"Switched to {branch.name} [{branch.code}].")

    next_url = request.GET.get("next", "dashboard")
    return redirect(next_url)


@login_required
def clear_branch_context(request):
    """Clear branch context — return to global view."""
    request.session.pop("active_branch_id", None)
    request.session.pop("active_branch_name", None)
    request.session.pop("active_branch_code", None)
    messages.info(request, "Viewing all branches.")
    return redirect("agencies:agency_dashboard")


# ---------------------------------------------------------------------------
# API / HTMX ENDPOINTS
# ---------------------------------------------------------------------------


@login_required
def branch_members_api(request, branch_pk):
    """JSON endpoint — members of a branch (for HTMX dropdowns)."""
    branch = get_object_or_404(Branch, pk=branch_pk)
    user = request.user

    has_access = (
        user.role == "it_administrator"
        or UserBranchMembership.objects.filter(
            user=user, branch=branch, is_active=True
        ).exists()
    )

    if not has_access:
        return JsonResponse({"error": "Access denied"}, status=403)

    members = UserBranchMembership.objects.filter(
        branch=branch, is_active=True
    ).select_related("user")

    data = [
        {
            "id": str(m.user.pk),
            "name": m.user.get_full_name(),
            "email": m.user.email,
            "role": m.get_branch_role_display(),
            "branch_role": m.branch_role,
        }
        for m in members
    ]
    return JsonResponse({"members": data, "count": len(data)})


@login_required
def committee_members_api(request, committee_pk):
    """JSON endpoint — members of a committee."""
    committee = get_object_or_404(Committee, pk=committee_pk)
    user = request.user

    has_access = (
        user.role == "it_administrator"
        or UserBranchMembership.objects.filter(
            user=user, branch=committee.branch, is_active=True
        ).exists()
    )

    if not has_access:
        return JsonResponse({"error": "Access denied"}, status=403)

    members = CommitteeMembership.objects.filter(
        committee=committee, is_active=True
    ).select_related("user")

    data = [
        {
            "id": str(m.user.pk),
            "name": m.user.get_full_name(),
            "email": m.user.email,
            "committee_role": m.get_committee_role_display(),
            "has_voting_rights": m.has_voting_rights,
        }
        for m in members
    ]
    return JsonResponse({"members": data, "count": len(data)})


@login_required
def user_branches_api(request):
    """JSON endpoint — branches available for the current user (for context switcher)."""
    user = request.user
    active_branch_id = request.session.get("active_branch_id")

    if user.role == "it_administrator":
        memberships = None
        branches_qs = Branch.objects.filter(is_active=True).select_related(
            "organization"
        )
        data = [
            {
                "id": str(b.pk),
                "name": b.name,
                "code": b.code,
                "country": b.country,
                "organization": b.organization.name,
                "is_active_context": str(b.pk) == active_branch_id,
            }
            for b in branches_qs
        ]
    else:
        memberships = UserBranchMembership.objects.filter(
            user=user, is_active=True
        ).select_related("branch", "branch__organization")
        data = [
            {
                "id": str(m.branch.pk),
                "name": m.branch.name,
                "code": m.branch.code,
                "country": m.branch.country,
                "organization": m.branch.organization.name,
                "role": m.get_branch_role_display(),
                "is_primary": m.is_primary,
                "is_active_context": str(m.branch.pk) == active_branch_id,
            }
            for m in memberships
        ]

    return JsonResponse({"branches": data, "count": len(data)})


@login_required
def global_org_tree_api(request):
    """JSON endpoint — full org/branch/committee tree for IT admins."""
    if request.user.role != "it_administrator":
        return JsonResponse({"error": "Access denied"}, status=403)

    orgs = Organization.objects.filter(is_active=True).prefetch_related(
        "branches__committees"
    )

    tree = []
    for org in orgs:
        org_node = {
            "id": str(org.pk),
            "name": org.name,
            "type": "organization",
            "country": org.head_office_country,
            "branches": [],
        }
        for branch in org.branches.filter(is_active=True, parent_branch__isnull=True):
            branch_node = _build_branch_node(branch)
            org_node["branches"].append(branch_node)
        tree.append(org_node)

    return JsonResponse({"tree": tree})


def _build_branch_node(branch):
    """Recursively build branch tree node."""
    node = {
        "id": str(branch.pk),
        "name": branch.name,
        "code": branch.code,
        "type": "branch",
        "branch_type": branch.branch_type,
        "country": branch.country,
        "member_count": branch.total_members,
        "committees": [
            {
                "id": str(c.pk),
                "name": c.name,
                "code": c.code,
                "type": "committee",
                "committee_type": c.committee_type,
                "member_count": c.active_member_count,
            }
            for c in branch.committees.filter(is_active=True)
        ],
        "sub_branches": [],
    }
    for sub in branch.sub_branches.filter(is_active=True):
        node["sub_branches"].append(_build_branch_node(sub))
    return node
