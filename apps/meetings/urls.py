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
]
