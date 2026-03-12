from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect

from .models import Branch, UserBranchMembership


class BranchAccessMixin(LoginRequiredMixin):
    """
    Mixin that ensures the current user has access to the branch
    identified by `branch_pk` URL kwarg (or `pk` if the view is a
    Branch detail view).

    Usage in a class-based view:
        class MyView(BranchAccessMixin, DetailView):
            branch_pk_url_kwarg = 'branch_pk'   # default
    """

    branch_pk_url_kwarg = "branch_pk"

    def get_branch(self):
        pk = self.kwargs.get(self.branch_pk_url_kwarg) or self.kwargs.get("pk")
        return get_object_or_404(Branch, pk=pk)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        branch = self.get_branch()
        user = request.user

        # IT admins bypass all branch access checks
        if user.role == "it_administrator":
            self.branch = branch
            return super().dispatch(request, *args, **kwargs)

        has_access = UserBranchMembership.objects.filter(
            user=user,
            branch=branch,
            is_active=True,
        ).exists()

        if not has_access:
            messages.error(
                request,
                f"You do not have access to the branch '{branch.name}'.",
            )
            return redirect("agencies:branch_list")

        self.branch = branch
        return super().dispatch(request, *args, **kwargs)


class OrganizationAdminMixin(LoginRequiredMixin):
    """
    Restricts the view to IT administrators only.
    Any other role gets a 403-style redirect to the dashboard.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.role != "it_administrator":
            messages.error(
                request,
                "You must be an IT Administrator to access this section.",
            )
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)


class CommitteeAccessMixin(LoginRequiredMixin):
    """
    Ensures the user belongs to the branch that owns the committee,
    and — for confidential committees — that the user is also a
    direct committee member.

    Expects `pk` or `committee_pk` URL kwarg to identify the committee.
    """

    committee_pk_url_kwarg = "committee_pk"

    def get_committee(self):
        from .models import Committee

        pk = self.kwargs.get(self.committee_pk_url_kwarg) or self.kwargs.get("pk")
        return get_object_or_404(Committee, pk=pk)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        committee = self.get_committee()
        user = request.user

        if user.role == "it_administrator":
            self.committee = committee
            return super().dispatch(request, *args, **kwargs)

        # Branch-level access
        has_branch_access = UserBranchMembership.objects.filter(
            user=user,
            branch=committee.branch,
            is_active=True,
        ).exists()

        if not has_branch_access:
            messages.error(
                request,
                f"You do not have access to the branch '{committee.branch.name}'.",
            )
            return redirect("agencies:committee_list")

        # Confidential committee — must be a direct member
        if committee.is_confidential:
            from .models import CommitteeMembership

            is_member = CommitteeMembership.objects.filter(
                user=user,
                committee=committee,
                is_active=True,
            ).exists()

            if not is_member:
                messages.error(
                    request,
                    "This committee is confidential. "
                    "Access is restricted to its members.",
                )
                return redirect("agencies:committee_list")

        self.committee = committee
        return super().dispatch(request, *args, **kwargs)


class ActiveBranchContextMixin:
    """
    Non-login mixin that reads the user's active branch from the session
    and injects `active_branch` and `active_branch_id` into the template
    context.

    Mix this into any view that needs to be branch-context-aware.

    Example:
        class MeetingListView(ActiveBranchContextMixin, LoginRequiredMixin, ListView):
            ...
    """

    def get_active_branch(self):
        branch_id = self.request.session.get("active_branch_id")
        if not branch_id:
            # Fall back to the user's primary branch
            from .models import UserBranchMembership

            primary = (
                UserBranchMembership.objects.filter(
                    user=self.request.user,
                    is_primary=True,
                    is_active=True,
                )
                .select_related("branch")
                .first()
            )

            if primary:
                return primary.branch
            return None

        try:
            return Branch.objects.get(pk=branch_id)
        except Branch.DoesNotExist:
            return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_branch = self.get_active_branch()
        ctx["active_branch"] = active_branch
        ctx["active_branch_id"] = str(active_branch.pk) if active_branch else None

        if self.request.user.is_authenticated:
            from .models import UserBranchMembership

            ctx["user_branch_count"] = UserBranchMembership.objects.filter(
                user=self.request.user, is_active=True
            ).count()

        return ctx


class BranchManagerMixin(LoginRequiredMixin):
    """
    Allows access only to users with the 'it_administrator' or
    'company_secretary' role.  Used for views that manage branch
    configuration, membership, committees, etc.
    """

    allowed_management_roles = ["it_administrator", "company_secretary"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.role not in self.allowed_management_roles:
            messages.error(
                request,
                "You do not have permission to perform this action.",
            )
            return redirect("agencies:agency_dashboard")

        return super().dispatch(request, *args, **kwargs)
