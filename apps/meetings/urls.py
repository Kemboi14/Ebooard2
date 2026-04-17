from django.urls import path

from . import views

app_name = "meetings"

urlpatterns = [
    # List & search
    path("", views.MeetingListView.as_view(), name="meeting_list"),
    path("search/", views.meeting_search, name="meeting_search"),
    path("calendar/data/", views.meetings_calendar_data, name="calendar_data"),
    # Create & update
    path("create/", views.CreateMeetingView.as_view(), name="create_meeting"),
    path("<uuid:pk>/edit/", views.UpdateMeetingView.as_view(), name="update_meeting"),
    # Detail
    path("<uuid:pk>/", views.MeetingDetailView.as_view(), name="meeting_detail"),
    # Status management
    path("<uuid:pk>/status/", views.update_meeting_status, name="update_status"),
    path("<uuid:pk>/quorum/", views.check_quorum, name="check_quorum"),
    # RSVP
    path("<uuid:pk>/rsvp/", views.rsvp_meeting, name="rsvp"),
    # Agenda
    path("<uuid:pk>/agenda/", views.manage_agenda, name="manage_agenda"),
    path(
        "<uuid:pk>/agenda/<uuid:item_pk>/delete/",
        views.delete_agenda_item,
        name="delete_agenda_item",
    ),
    path(
        "<uuid:pk>/agenda/<uuid:item_pk>/discussed/",
        views.mark_agenda_discussed,
        name="mark_agenda_discussed",
    ),
    # Minutes
    path("<uuid:pk>/minutes/", views.manage_minutes, name="manage_minutes"),
    path(
        "<uuid:pk>/minutes/advance/",
        views.advance_minutes_status,
        name="advance_minutes",
    ),
    # Attendance
    path("<uuid:pk>/attendance/", views.manage_attendance, name="manage_attendance"),
    # Action items
    path("<uuid:pk>/actions/", views.manage_actions, name="manage_actions"),
    path(
        "<uuid:pk>/actions/<uuid:action_pk>/status/",
        views.update_action_status,
        name="update_action_status",
    ),
    # AI Recording
    path("<uuid:pk>/recording/create/", views.create_meeting_recording, name="create_recording"),
    # Video Conferencing
    path("<uuid:pk>/video/zoom/", views.create_zoom_meeting, name="create_zoom_meeting"),
    path("<uuid:pk>/video/teams/", views.create_teams_meeting, name="create_teams_meeting"),
    path("videoconferencesession/", views.VideoConferenceSessionListView.as_view(), name="videoconferencesession"),
    
    # Agenda Suggestions
    path("agenda-suggestions/create/", views.AgendaSuggestionCreateView.as_view(), name="agenda_suggestion_create"),
    path("agenda-suggestions/<uuid:pk>/accept/", views.accept_agenda_suggestion, name="accept_suggestion"),
    path("agenda-suggestions/<uuid:pk>/reject/", views.reject_agenda_suggestion, name="reject_suggestion"),
    
    # Board Packs
    path("board-packs/", views.BoardPackListView.as_view(), name="board_packs"),
    path("board-packs/<uuid:pk>/", views.BoardPackDetailView.as_view(), name="board_pack_detail"),
    path("board-packs/create/", views.BoardPackCreateView.as_view(), name="board_pack_create"),
    path("board-packs/<uuid:pk>/distribute/", views.distribute_board_pack, name="distribute_board_pack"),
]
