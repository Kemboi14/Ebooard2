from .permissions import *


def user_permissions(request):
    if not request.user.is_authenticated:
        return {}

    role = request.user.role

    # -------------------------------------------------------------------
    # Base permission flags (unchanged from original)
    # -------------------------------------------------------------------
    ctx = {
        "user_role": role,
        "can_manage_meetings": role in MANAGE_MEETINGS,
        "can_vote": role in CAN_VOTE,
        "can_view_audit": role in VIEW_AUDIT,
        "can_manage_risk": role in MANAGE_RISK,
        "can_manage_policies": role in MANAGE_POLICIES,
        "can_manage_documents": role in MANAGE_DOCUMENTS,
        "is_admin": role in ADMIN_ROLES,
        "mfa_required": role in MFA_REQUIRED_ROLES,
    }

    # -------------------------------------------------------------------
    # Multi-agency / branch context
    # -------------------------------------------------------------------
    try:
        from apps.agencies.models import (
            Branch,
            CommitteeMembership,
            UserBranchMembership,
        )

        # Active branch from session
        active_branch_id = request.session.get("active_branch_id")
        active_branch = None

        if active_branch_id:
            try:
                active_branch = Branch.objects.select_related("organization").get(
                    pk=active_branch_id
                )
            except Branch.DoesNotExist:
                # Stale session key — clear it
                request.session.pop("active_branch_id", None)
                request.session.pop("active_branch_name", None)
                request.session.pop("active_branch_code", None)

        # Fall back to the user's primary branch when no context is set
        if active_branch is None:
            primary = (
                UserBranchMembership.objects.filter(
                    user=request.user,
                    is_primary=True,
                    is_active=True,
                )
                .select_related("branch", "branch__organization")
                .first()
            )
            if primary:
                active_branch = primary.branch

        # All branches the user belongs to (for the switcher dropdown)
        if role == "it_administrator":
            user_branches = (
                Branch.objects.filter(is_active=True)
                .select_related("organization")
                .order_by("organization__name", "country", "name")
            )
            user_branch_count = user_branches.count()
        else:
            user_branch_memberships = (
                UserBranchMembership.objects.filter(user=request.user, is_active=True)
                .select_related("branch", "branch__organization")
                .order_by(
                    "branch__organization__name", "branch__country", "branch__name"
                )
            )
            user_branches = [m.branch for m in user_branch_memberships]
            user_branch_count = len(user_branches)

        # User's committees (for sidebar / committee-aware filtering)
        user_committees = (
            CommitteeMembership.objects.filter(user=request.user, is_active=True)
            .select_related("committee", "committee__branch")
            .order_by("committee__branch__name", "committee__name")
        )

        # Current membership in the active branch (role within that branch)
        active_branch_membership = None
        active_branch_role = role  # default to global role
        if active_branch and role != "it_administrator":
            try:
                active_branch_membership = UserBranchMembership.objects.get(
                    user=request.user,
                    branch=active_branch,
                    is_active=True,
                )
                active_branch_role = active_branch_membership.branch_role
            except UserBranchMembership.DoesNotExist:
                pass

        ctx.update(
            {
                # Active branch (session or primary fallback)
                "active_branch": active_branch,
                "active_branch_id": str(active_branch.pk) if active_branch else None,
                "active_branch_name": active_branch.name if active_branch else None,
                "active_branch_code": active_branch.code if active_branch else None,
                # User's role *within* the active branch
                "active_branch_role": active_branch_role,
                "active_branch_membership": active_branch_membership,
                # All branches available to this user (for switcher)
                "user_branches": user_branches,
                "user_branch_count": user_branch_count,
                "is_multi_branch": user_branch_count > 1,
                # Committees the user belongs to
                "user_committees": user_committees,
                "user_committee_count": user_committees.count(),
                # Agency-level permissions
                "can_manage_branches": role
                in ["it_administrator", "company_secretary"],
                "can_manage_committees": role
                in ["it_administrator", "company_secretary"],
                "can_invite_members": role in ["it_administrator", "company_secretary"],
                "is_global_admin": role == "it_administrator",
            }
        )

    except Exception:
        # If agencies app tables don't exist yet (pre-migration), fail gracefully
        ctx.update(
            {
                "active_branch": None,
                "active_branch_id": None,
                "active_branch_name": None,
                "active_branch_code": None,
                "active_branch_role": role,
                "active_branch_membership": None,
                "user_branches": [],
                "user_branch_count": 0,
                "is_multi_branch": False,
                "user_committees": [],
                "user_committee_count": 0,
                "can_manage_branches": False,
                "can_manage_committees": False,
                "can_invite_members": False,
                "is_global_admin": role == "it_administrator",
            }
        )

    return ctx
