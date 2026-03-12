from django import forms
from django.utils import timezone

from apps.accounts.models import User

from .models import (
    AgendaItem,
    Meeting,
    MeetingAction,
    MeetingAttendance,
    MeetingMinutes,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

INPUT_CLS = (
    "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm "
    "focus:ring-2 focus:ring-purple-500 focus:border-transparent "
    "bg-white placeholder-gray-400"
)
SELECT_CLS = (
    "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm "
    "focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white"
)
TEXTAREA_CLS = (
    "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm "
    "focus:ring-2 focus:ring-purple-500 focus:border-transparent "
    "bg-white placeholder-gray-400 resize-y"
)
CHECKBOX_CLS = "h-4 w-4 rounded border-gray-300 focus:ring-purple-500"


def _input(placeholder="", extra=""):
    return forms.TextInput(
        attrs={"class": INPUT_CLS + extra, "placeholder": placeholder}
    )


def _select(extra=""):
    return forms.Select(attrs={"class": SELECT_CLS + extra})


def _textarea(rows=4, placeholder="", extra=""):
    return forms.Textarea(
        attrs={
            "class": TEXTAREA_CLS + extra,
            "rows": rows,
            "placeholder": placeholder,
        }
    )


def _datetime():
    return forms.DateTimeInput(attrs={"class": INPUT_CLS, "type": "datetime-local"})


def _date():
    return forms.DateInput(attrs={"class": INPUT_CLS, "type": "date"})


# ─── Meeting Form ─────────────────────────────────────────────────────────────


class CreateMeetingForm(forms.ModelForm):
    """Create or update a meeting."""

    class Meta:
        model = Meeting
        fields = [
            # Identity
            "title",
            "reference_number",
            "description",
            "meeting_type",
            "status",
            # Organisation context
            "branch",
            "committee",
            # Scheduling
            "scheduled_date",
            "scheduled_end_time",
            "timezone_display",
            "location",
            "venue_notes",
            # Virtual meeting
            "is_virtual",
            "virtual_platform",
            "virtual_meeting_url",
            "virtual_meeting_id",
            "virtual_meeting_password",
            "virtual_dial_in",
            # VC settings
            "enable_recording",
            "enable_chat",
            "enable_screen_sharing",
            "enable_breakout_rooms",
            "enable_waiting_room",
            "max_participants",
            # Content
            "agenda",
            "quorum_required",
            # People
            "attendees",
            "required_attendees",
        ]
        widgets = {
            "title": _input("e.g. Q1 Board Meeting 2025"),
            "reference_number": _input("e.g. BM-2025-001"),
            "description": _textarea(3, "Brief description of the meeting purpose…"),
            "meeting_type": _select(),
            "status": _select(),
            "branch": _select(),
            "committee": _select(),
            "scheduled_date": _datetime(),
            "scheduled_end_time": _datetime(),
            "timezone_display": _input("Africa/Nairobi"),
            "location": _input("e.g. Boardroom A, 3rd Floor, Head Office"),
            "venue_notes": _textarea(2, "Directions, parking, access information…"),
            "is_virtual": forms.CheckboxInput(attrs={"class": CHECKBOX_CLS}),
            "virtual_platform": _select(),
            "virtual_meeting_url": forms.URLInput(
                attrs={
                    "class": INPUT_CLS,
                    "placeholder": "https://zoom.us/j/123456789",
                }
            ),
            "virtual_meeting_id": _input("e.g. 123 456 7890"),
            "virtual_meeting_password": _input("Meeting password (if any)"),
            "virtual_dial_in": _input("e.g. +254 20 123 4567"),
            "enable_recording": forms.CheckboxInput(attrs={"class": CHECKBOX_CLS}),
            "enable_chat": forms.CheckboxInput(attrs={"class": CHECKBOX_CLS}),
            "enable_screen_sharing": forms.CheckboxInput(attrs={"class": CHECKBOX_CLS}),
            "enable_breakout_rooms": forms.CheckboxInput(attrs={"class": CHECKBOX_CLS}),
            "enable_waiting_room": forms.CheckboxInput(attrs={"class": CHECKBOX_CLS}),
            "max_participants": forms.NumberInput(
                attrs={
                    "class": INPUT_CLS,
                    "placeholder": "Leave blank for unlimited",
                    "min": 1,
                }
            ),
            "agenda": _textarea(5, "List the key agenda items…"),
            "quorum_required": forms.NumberInput(
                attrs={
                    "class": INPUT_CLS,
                    "placeholder": "e.g. 5",
                    "min": 1,
                }
            ),
            "attendees": forms.SelectMultiple(
                attrs={
                    "class": (
                        "w-full border border-gray-300 rounded-lg text-sm "
                        "focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    ),
                    "size": 6,
                }
            ),
            "required_attendees": forms.SelectMultiple(
                attrs={
                    "class": (
                        "w-full border border-gray-300 rounded-lg text-sm "
                        "focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    ),
                    "size": 6,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_users = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        )
        self.fields["attendees"].queryset = active_users
        self.fields["required_attendees"].queryset = active_users
        self.fields["reference_number"].required = False
        self.fields["description"].required = False
        self.fields["branch"].required = False
        self.fields["committee"].required = False
        self.fields["venue_notes"].required = False
        self.fields["quorum_required"].required = False
        self.fields["max_participants"].required = False

        # Make virtual fields not required at form level (model.clean handles it)
        for f in [
            "virtual_platform",
            "virtual_meeting_url",
            "virtual_meeting_id",
            "virtual_meeting_password",
            "virtual_dial_in",
        ]:
            self.fields[f].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("scheduled_date")
        end = cleaned.get("scheduled_end_time")

        if start and end:
            if end <= start:
                raise forms.ValidationError("End time must be after start time.")
            if start <= timezone.now():
                raise forms.ValidationError(
                    "Meeting must be scheduled for a future date and time."
                )

        is_virtual = cleaned.get("is_virtual")
        platform = cleaned.get("virtual_platform")
        url = cleaned.get("virtual_meeting_url")

        if is_virtual and not platform:
            self.add_error(
                "virtual_platform",
                "Please select a platform for the virtual meeting.",
            )
        if platform and not url:
            self.add_error(
                "virtual_meeting_url",
                "A meeting URL is required when a platform is selected.",
            )

        return cleaned


# ─── Agenda Item Form ─────────────────────────────────────────────────────────


class AgendaItemForm(forms.ModelForm):
    """Add or edit a structured agenda item."""

    class Meta:
        model = AgendaItem
        fields = [
            "order",
            "title",
            "item_type",
            "description",
            "priority",
            "estimated_duration",
            "presenter",
            "attachment",
            "action_owner",
            "action_due_date",
        ]
        widgets = {
            "order": forms.NumberInput(
                attrs={"class": INPUT_CLS, "min": 1, "placeholder": "1"}
            ),
            "title": _input("e.g. Approval of Previous Minutes"),
            "item_type": _select(),
            "description": _textarea(3, "Detailed description or background…"),
            "priority": _select(),
            "estimated_duration": forms.NumberInput(
                attrs={
                    "class": INPUT_CLS,
                    "min": 1,
                    "placeholder": "Minutes",
                }
            ),
            "presenter": _select(),
            "attachment": forms.ClearableFileInput(attrs={"class": INPUT_CLS}),
            "action_owner": _select(),
            "action_due_date": _date(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_users = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        )
        self.fields["presenter"].queryset = active_users
        self.fields["presenter"].required = False
        self.fields["description"].required = False
        self.fields["attachment"].required = False
        self.fields["action_owner"].queryset = active_users
        self.fields["action_owner"].required = False
        self.fields["action_due_date"].required = False


# ─── Meeting Minutes Form ─────────────────────────────────────────────────────


class MeetingMinutesForm(forms.ModelForm):
    """Create or edit meeting minutes."""

    class Meta:
        model = MeetingMinutes
        fields = [
            "content",
            "decisions",
            "action_items",
            "next_meeting_date",
            "attachment",
        ]
        widgets = {
            "content": _textarea(
                14,
                "Record the full minutes of the meeting…",
            ),
            "decisions": _textarea(
                5,
                "List all key decisions and resolutions made…",
            ),
            "action_items": _textarea(
                5,
                "List action items, responsible persons, and deadlines…",
            ),
            "next_meeting_date": _datetime(),
            "attachment": forms.ClearableFileInput(attrs={"class": INPUT_CLS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["decisions"].required = False
        self.fields["action_items"].required = False
        self.fields["next_meeting_date"].required = False
        self.fields["attachment"].required = False


# ─── Attendance Update Form ───────────────────────────────────────────────────


class AttendanceUpdateForm(forms.ModelForm):
    """Update a single attendance record."""

    class Meta:
        model = MeetingAttendance
        fields = ["status", "rsvp_status", "notes", "check_in_time", "check_out_time"]
        widgets = {
            "status": _select(),
            "rsvp_status": _select(),
            "notes": _textarea(2, "Reason for absence or additional notes…"),
            "check_in_time": forms.DateTimeInput(
                attrs={"class": INPUT_CLS, "type": "datetime-local"}
            ),
            "check_out_time": forms.DateTimeInput(
                attrs={"class": INPUT_CLS, "type": "datetime-local"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
        self.fields["check_in_time"].required = False
        self.fields["check_out_time"].required = False
        self.fields["rsvp_status"].required = False


# ─── Meeting Action Form ──────────────────────────────────────────────────────


class MeetingActionForm(forms.ModelForm):
    """Create or update a meeting action item."""

    class Meta:
        model = MeetingAction
        fields = [
            "title",
            "description",
            "assigned_to",
            "due_date",
            "priority",
            "agenda_item",
        ]
        widgets = {
            "title": _input("e.g. Prepare Q2 Financial Report"),
            "description": _textarea(3, "Details of the action required…"),
            "assigned_to": _select(),
            "due_date": _date(),
            "priority": _select(),
            "agenda_item": _select(),
        }

    def __init__(self, meeting=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_users = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        )
        self.fields["assigned_to"].queryset = active_users
        self.fields["assigned_to"].required = False
        self.fields["description"].required = False
        self.fields["due_date"].required = False
        self.fields["agenda_item"].required = False

        if meeting:
            self.fields["agenda_item"].queryset = AgendaItem.objects.filter(
                meeting=meeting
            ).order_by("order")
        else:
            self.fields["agenda_item"].queryset = AgendaItem.objects.none()


# ─── Search Form ──────────────────────────────────────────────────────────────


class MeetingSearchForm(forms.Form):
    SEARCH_TYPE_CHOICES = [
        ("all", "All Fields"),
        ("title", "Title"),
        ("description", "Description"),
        ("agenda", "Agenda"),
    ]

    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLS,
                "placeholder": "Search meetings…",
            }
        ),
    )

    search_type = forms.ChoiceField(
        choices=SEARCH_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLS}),
    )

    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + Meeting.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLS}),
    )

    meeting_type = forms.ChoiceField(
        choices=[("", "All Types")] + Meeting.TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLS}),
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLS, "type": "date"}),
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": INPUT_CLS, "type": "date"}),
    )
