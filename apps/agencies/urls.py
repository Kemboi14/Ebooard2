from django.urls import path

from . import views

app_name = "agencies"

urlpatterns = [
    # -----------------------------------------------------------------------
    # Agency / Multi-Branch Dashboard
    # -----------------------------------------------------------------------
    path("", views.agency_dashboard, name="agency_dashboard"),
    path("switch/<uuid:branch_pk>/", views.switch_branch_context, name="switch_branch"),
    path("clear-context/", views.clear_branch_context, name="clear_context"),
    # -----------------------------------------------------------------------
    # Organizations
    # -----------------------------------------------------------------------
    path(
        "organizations/", views.OrganizationListView.as_view(), name="organization_list"
    ),
    path(
        "organizations/create/",
        views.OrganizationCreateView.as_view(),
        name="organization_create",
    ),
    path(
        "organizations/<uuid:pk>/",
        views.OrganizationDetailView.as_view(),
        name="organization_detail",
    ),
    path(
        "organizations/<uuid:pk>/edit/",
        views.OrganizationUpdateView.as_view(),
        name="organization_update",
    ),
    # -----------------------------------------------------------------------
    # Branches
    # -----------------------------------------------------------------------
    path("branches/", views.BranchListView.as_view(), name="branch_list"),
    path("branches/create/", views.BranchCreateView.as_view(), name="branch_create"),
    path("branches/<uuid:pk>/", views.BranchDetailView.as_view(), name="branch_detail"),
    path(
        "branches/<uuid:pk>/edit/",
        views.BranchUpdateView.as_view(),
        name="branch_update",
    ),
    path(
        "branches/<uuid:pk>/toggle-active/",
        views.toggle_branch_active,
        name="toggle_branch_active",
    ),
    # Branch members management
    path(
        "branches/<uuid:branch_pk>/members/",
        views.manage_branch_members,
        name="manage_branch_members",
    ),
    path(
        "memberships/<uuid:membership_pk>/toggle/",
        views.toggle_branch_membership,
        name="toggle_branch_membership",
    ),
    path(
        "memberships/<uuid:membership_pk>/set-primary/",
        views.set_primary_branch,
        name="set_primary_branch",
    ),
    # Branch invitations
    path(
        "branches/<uuid:branch_pk>/invite/",
        views.send_invitation,
        name="send_invitation",
    ),
    path(
        "branches/<uuid:branch_pk>/invitations/",
        views.invitation_list,
        name="invitation_list",
    ),
    path(
        "invitations/<uuid:invitation_pk>/revoke/",
        views.revoke_invitation,
        name="revoke_invitation",
    ),
    path(
        "invite/<uuid:token>/accept/", views.accept_invitation, name="accept_invitation"
    ),
    # -----------------------------------------------------------------------
    # Committees
    # -----------------------------------------------------------------------
    path("committees/", views.CommitteeListView.as_view(), name="committee_list"),
    path(
        "committees/create/",
        views.CommitteeCreateView.as_view(),
        name="committee_create",
    ),
    path(
        "committees/<uuid:pk>/",
        views.CommitteeDetailView.as_view(),
        name="committee_detail",
    ),
    path(
        "committees/<uuid:pk>/edit/",
        views.CommitteeUpdateView.as_view(),
        name="committee_update",
    ),
    # Committee members management
    path(
        "committees/<uuid:committee_pk>/members/",
        views.manage_committee_members,
        name="manage_committee_members",
    ),
    path(
        "memberships/<uuid:membership_pk>/committee-toggle/",
        views.toggle_committee_membership,
        name="toggle_committee_membership",
    ),
    # -----------------------------------------------------------------------
    # API / HTMX Endpoints
    # -----------------------------------------------------------------------
    path(
        "api/branches/<uuid:branch_pk>/members/",
        views.branch_members_api,
        name="branch_members_api",
    ),
    path(
        "api/committees/<uuid:committee_pk>/members/",
        views.committee_members_api,
        name="committee_members_api",
    ),
    path("api/my-branches/", views.user_branches_api, name="user_branches_api"),
    path("api/org-tree/", views.global_org_tree_api, name="org_tree_api"),
]
