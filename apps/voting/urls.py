from django.urls import path

from . import views

app_name = "voting"

urlpatterns = [
    path("", views.MotionListView.as_view(), name="motion_list"),
    path("dashboard/", views.voting_dashboard, name="voting_dashboard"),
    path("search/", views.motion_search, name="motion_search"),
    path("motions/create/", views.CreateMotionView.as_view(), name="create_motion"),
    path("motions/<uuid:pk>/", views.MotionDetailView.as_view(), name="motion_detail"),
    path("motions/<uuid:pk>/vote/", views.cast_vote, name="cast_vote"),
    path("motions/<uuid:pk>/results/", views.vote_results, name="vote_results"),
    path("motions/<uuid:pk>/open-voting/", views.open_voting, name="open_voting"),
    path("motions/<uuid:pk>/close-voting/", views.close_voting, name="close_voting"),
    path("session/", views.manage_voting_session, name="manage_session"),
    path(
        "session/<uuid:pk>/", views.manage_voting_session, name="manage_session_detail"
    ),
]
