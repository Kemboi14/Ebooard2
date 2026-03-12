from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.decorators import role_required
from apps.accounts.permissions import CAN_VOTE, MANAGE_MEETINGS

from .forms import (
    AgendaItemForm,
    AttendanceUpdateForm,
    CreateMeetingForm,
    MeetingActionForm,
    MeetingMinutesForm,
    MeetingSearchForm,
)
from .models import (
    AgendaItem,
    Meeting,
    MeetingAction,
    MeetingAttendance,
    MeetingMinutes,
)

# ─── Meeting List ────────────────────────────────────────────────────────────


class MeetingListView(LoginRequiredMixin, ListView):
    """List view for meetings with role-based filtering and stats."""

    model = Meeting
    template_name = "meetings/meeting_list.html"
    context_object_name = "meetings"
    paginate_by = 12

    def get_queryset(self):
        user = self.request.user
        qs = Meeting.objects.select_related("organizer", "branch", "committee")

        # Role-based filtering
        if user.role in MANAGE_MEETINGS:
            pass  # See all meetings
        elif user.role == "board_member":
            qs = qs.filter(
                Q(attendees=user) | Q(required_attendees=user) | Q(organizer=user)
            )
        else:
            qs = qs.filter(Q(attendees=user) | Q(organizer=user))

        # Search / filter from GET params
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(location__icontains=q)
            )

        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)

        meeting_type = self.request.GET.get("type", "")
        if meeting_type:
            qs = qs.filter(meeting_type=meeting_type)

        date_from = self.request.GET.get("date_from", "")
        if date_from:
            qs = qs.filter(scheduled_date__date__gte=date_from)

        date_to = self.request.GET.get("date_to", "")
        if date_to:
            qs = qs.filter(scheduled_date__date__lte=date_to)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        context["can_manage"] = user.role in MANAGE_MEETINGS
        context["search_form"] = MeetingSearchForm(self.request.GET or None)

        # Summary stats
        base_qs = self.get_queryset()
        context["stats"] = {
            "upcoming": base_qs.filter(
                status="scheduled", scheduled_date__gt=now
            ).count(),
            "in_progress": base_qs.filter(status="in_progress").count(),
            "completed": base_qs.filter(status="completed").count(),
            "total": base_qs.count(),
        }

        # Upcoming meetings (next 5) for quick access
        context["upcoming_meetings"] = base_qs.filter(
            status="scheduled", scheduled_date__gt=now
        ).order_by("scheduled_date")[:5]

        return context


# ─── Meeting Detail ──────────────────────────────────────────────────────────


class MeetingDetailView(LoginRequiredMixin, DetailView):
    """Full meeting detail with agenda, attendance, minutes, and actions."""

    model = Meeting
    template_name = "meetings/meeting_detail.html"
    context_object_name = "meeting"

    def get_queryset(self):
        return Meeting.objects.select_related(
            "organizer", "created_by", "branch", "committee"
        ).prefetch_related(
            "attendees",
            "required_attendees",
            Prefetch(
                "agenda_items",
                queryset=AgendaItem.objects.select_related("presenter").order_by(
                    "order"
                ),
            ),
            Prefetch(
                "attendance_records",
                queryset=MeetingAttendance.objects.select_related("attendee").order_by(
                    "attendee__first_name"
                ),
            ),
            Prefetch(
                "actions",
                queryset=MeetingAction.objects.select_related("assigned_to").order_by(
                    "due_date"
                ),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meeting = self.get_object()
        user = self.request.user

        context["can_manage"] = user.role in MANAGE_MEETINGS
        context["is_organizer"] = user == meeting.organizer
        context["is_attending"] = meeting.attendees.filter(pk=user.pk).exists()
        context["is_required"] = meeting.required_attendees.filter(pk=user.pk).exists()
        context["can_join"] = meeting.can_user_join(user)

        # Agenda items (already prefetched)
        context["agenda_items"] = meeting.agenda_items.all()

        # Minutes (fixed accessor: related_name='minutes')
        try:
            context["minutes"] = meeting.minutes
        except MeetingMinutes.DoesNotExist:
            context["minutes"] = None

        # Attendance (fixed accessor: related_name='attendance_records')
        attendance_qs = meeting.attendance_records.all()
        context["attendance_records"] = attendance_qs
        context["attendance_summary"] = {
            "attended": attendance_qs.filter(status="attended").count(),
            "absent": attendance_qs.filter(status="absent").count(),
            "apologies": attendance_qs.filter(status="apologies").count(),
            "no_response": attendance_qs.filter(status="no_response").count(),
            "late": attendance_qs.filter(status="late").count(),
        }

        # Quorum
        context["quorum_met"] = meeting.has_quorum
        context["quorum_required"] = meeting.quorum_required

        # Actions
        actions = meeting.actions.all()
        context["actions"] = actions
        context["open_actions"] = actions.filter(
            status__in=["open", "in_progress"]
        ).count()
        context["overdue_actions"] = [a for a in actions if a.is_overdue]

        # Join instructions
        context["join_instructions"] = meeting.get_join_instructions()

        # Motions linked to this meeting
        try:
            from apps.voting.models import Motion

            context["motions"] = meeting.motions.all().order_by("created_at")
        except Exception:
            context["motions"] = []

        # Status flow — what statuses can a manager transition to?
        context["next_statuses"] = _get_next_statuses(meeting.status)

        return context


def _get_next_statuses(current_status):
    """Return valid next status transitions."""
    flow = {
        "scheduled": ["in_progress", "postponed", "cancelled"],
        "in_progress": ["completed", "cancelled"],
        "postponed": ["scheduled", "cancelled"],
        "completed": [],
        "cancelled": [],
    }
    return flow.get(current_status, [])


# ─── Create / Update ─────────────────────────────────────────────────────────


class CreateMeetingView(LoginRequiredMixin, CreateView):
    model = Meeting
    form_class = CreateMeetingForm
    template_name = "meetings/meeting_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in MANAGE_MEETINGS:
            messages.error(request, "You do not have permission to create meetings.")
            return redirect("meetings:meeting_list")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("meetings:meeting_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request, f'Meeting "{self.object.title}" scheduled successfully.'
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = False
        context["page_heading"] = "Schedule New Meeting"
        return context


class UpdateMeetingView(LoginRequiredMixin, UpdateView):
    model = Meeting
    form_class = CreateMeetingForm
    template_name = "meetings/meeting_form.html"
    context_object_name = "meeting"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in MANAGE_MEETINGS:
            messages.error(request, "You do not have permission to update meetings.")
            return redirect("meetings:meeting_list")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("meetings:meeting_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Meeting updated successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        context["page_heading"] = f"Edit: {self.object.title}"
        context["can_manage"] = True
        return context


# ─── Status Management ───────────────────────────────────────────────────────


@login_required
@require_POST
def update_meeting_status(request, pk):
    """Change meeting status (start, complete, postpone, cancel)."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "You do not have permission to change meeting status.")
        return redirect("meetings:meeting_detail", pk=pk)

    meeting = get_object_or_404(Meeting, pk=pk)
    new_status = request.POST.get("status", "")
    valid_next = _get_next_statuses(meeting.status)

    if new_status not in valid_next:
        messages.error(
            request,
            f'Cannot transition meeting from "{meeting.get_status_display()}" '
            f'to "{new_status}".',
        )
        return redirect("meetings:meeting_detail", pk=pk)

    old_status = meeting.get_status_display()
    meeting.status = new_status

    # Auto-set quorum when marking in-progress
    if new_status == "in_progress" and meeting.quorum_required:
        attended = meeting.attendance_records.filter(
            status__in=["attended", "late"]
        ).count()
        meeting.quorum_status = (
            "quorum_met" if attended >= meeting.quorum_required else "quorum_not_met"
        )

    meeting.save()
    messages.success(
        request,
        f'Meeting status updated from "{old_status}" to '
        f'"{meeting.get_status_display()}".',
    )
    return redirect("meetings:meeting_detail", pk=pk)


# ─── Quorum Check ────────────────────────────────────────────────────────────


@login_required
@require_POST
def check_quorum(request, pk):
    """Recalculate and save quorum status based on current attendance."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "Permission denied.")
        return redirect("meetings:meeting_detail", pk=pk)

    meeting = get_object_or_404(Meeting, pk=pk)

    if not meeting.quorum_required:
        messages.info(request, "No quorum threshold is set for this meeting.")
        return redirect("meetings:meeting_detail", pk=pk)

    attended = meeting.attendance_records.filter(
        status__in=["attended", "late", "partial"]
    ).count()

    if attended >= meeting.quorum_required:
        meeting.quorum_status = "quorum_met"
        messages.success(
            request,
            f"Quorum confirmed: {attended} of {meeting.quorum_required} required "
            f"members are present.",
        )
    else:
        meeting.quorum_status = "quorum_not_met"
        messages.warning(
            request,
            f"Quorum not met: {attended} of {meeting.quorum_required} required "
            f"members are present.",
        )

    meeting.save(update_fields=["quorum_status"])
    return redirect("meetings:meeting_detail", pk=pk)


# ─── Agenda ──────────────────────────────────────────────────────────────────


@login_required
def manage_agenda(request, pk):
    """Add / view agenda items for a meeting."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "You do not have permission to manage the agenda.")
        return redirect("meetings:meeting_detail", pk=pk)

    meeting = get_object_or_404(Meeting, pk=pk)
    agenda_items = meeting.agenda_items.order_by("order")

    if request.method == "POST":
        form = AgendaItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.meeting = meeting
            item.created_by = request.user
            item.save()
            messages.success(request, f'Agenda item "{item.title}" added.')
            return redirect("meetings:manage_agenda", pk=pk)
    else:
        # Pre-populate order with next available number
        next_order = (agenda_items.last().order + 1) if agenda_items.exists() else 1
        form = AgendaItemForm(initial={"order": next_order})

    return render(
        request,
        "meetings/manage_agenda.html",
        {
            "meeting": meeting,
            "agenda_items": agenda_items,
            "form": form,
            "can_manage": True,
        },
    )


@login_required
@require_POST
def delete_agenda_item(request, pk, item_pk):
    """Delete a single agenda item."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "Permission denied.")
        return redirect("meetings:meeting_detail", pk=pk)

    item = get_object_or_404(AgendaItem, pk=item_pk, meeting__pk=pk)
    title = item.title
    item.delete()
    messages.success(request, f'Agenda item "{title}" removed.')
    return redirect("meetings:manage_agenda", pk=pk)


@login_required
@require_POST
def mark_agenda_discussed(request, pk, item_pk):
    """Mark an agenda item as discussed and record a decision."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "Permission denied.")
        return redirect("meetings:meeting_detail", pk=pk)

    item = get_object_or_404(AgendaItem, pk=item_pk, meeting__pk=pk)
    item.is_discussed = True
    item.decision = request.POST.get("decision", "").strip()
    item.save(update_fields=["is_discussed", "decision", "updated_at"])
    messages.success(request, f'Agenda item "{item.title}" marked as discussed.')
    return redirect("meetings:meeting_detail", pk=pk)


# ─── Minutes ─────────────────────────────────────────────────────────────────


@login_required
def manage_minutes(request, pk):
    """Create or edit meeting minutes."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "You do not have permission to manage minutes.")
        return redirect("meetings:meeting_detail", pk=pk)

    meeting = get_object_or_404(Meeting, pk=pk)

    # Fixed accessor: related_name='minutes'
    try:
        minutes = meeting.minutes
    except MeetingMinutes.DoesNotExist:
        minutes = None

    if request.method == "POST":
        form = MeetingMinutesForm(request.POST, request.FILES, instance=minutes)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.meeting = meeting
            if not minutes:
                obj.drafted_by = request.user
            obj.save()
            messages.success(request, "Minutes saved successfully.")
            return redirect("meetings:meeting_detail", pk=pk)
    else:
        form = MeetingMinutesForm(instance=minutes)

    return render(
        request,
        "meetings/manage_minutes.html",
        {
            "meeting": meeting,
            "minutes": minutes,
            "form": form,
            "can_manage": True,
        },
    )


@login_required
@require_POST
def advance_minutes_status(request, pk):
    """Move minutes through the approval workflow."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "Permission denied.")
        return redirect("meetings:meeting_detail", pk=pk)

    meeting = get_object_or_404(Meeting, pk=pk)

    try:
        minutes = meeting.minutes
    except MeetingMinutes.DoesNotExist:
        messages.error(request, "No minutes found for this meeting.")
        return redirect("meetings:meeting_detail", pk=pk)

    action = request.POST.get("action", "")
    now = timezone.now()

    if action == "submit" and minutes.can_be_submitted:
        minutes.status = "submitted"
        minutes.submitted_at = now
        minutes.save(update_fields=["status", "submitted_at", "updated_at"])
        messages.success(request, "Minutes submitted for review.")

    elif action == "review" and minutes.status == "submitted":
        minutes.status = "reviewed"
        minutes.reviewed_by = request.user
        minutes.reviewed_at = now
        minutes.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"]
        )
        messages.success(request, "Minutes marked as reviewed.")

    elif action == "approve" and minutes.can_be_approved:
        minutes.status = "approved"
        minutes.approved_by = request.user
        minutes.approved_at = now
        minutes.save(
            update_fields=["status", "approved_by", "approved_at", "updated_at"]
        )
        messages.success(request, "Minutes approved.")

    elif action == "publish" and minutes.status == "approved":
        minutes.status = "published"
        minutes.published_by = request.user
        minutes.published_at = now
        minutes.save(
            update_fields=["status", "published_by", "published_at", "updated_at"]
        )
        messages.success(request, "Minutes published and available to all attendees.")

    else:
        messages.error(
            request,
            f'Cannot perform "{action}" on minutes with status '
            f'"{minutes.get_status_display()}".',
        )

    return redirect("meetings:meeting_detail", pk=pk)


# ─── Attendance ──────────────────────────────────────────────────────────────


@login_required
def manage_attendance(request, pk):
    """Record or update attendance for a meeting."""
    if request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "You do not have permission to manage attendance.")
        return redirect("meetings:meeting_detail", pk=pk)

    meeting = get_object_or_404(Meeting, pk=pk)
    all_attendees = list(meeting.attendees.all()) + list(
        meeting.required_attendees.exclude(
            pk__in=meeting.attendees.values_list("pk", flat=True)
        )
    )

    if request.method == "POST":
        updated = 0
        for attendee in all_attendees:
            status_key = f"status_{attendee.pk}"
            rsvp_key = f"rsvp_{attendee.pk}"
            notes_key = f"notes_{attendee.pk}"
            check_in_key = f"check_in_{attendee.pk}"
            check_out_key = f"check_out_{attendee.pk}"

            if status_key in request.POST:
                record, _ = MeetingAttendance.objects.get_or_create(
                    meeting=meeting,
                    attendee=attendee,
                    defaults={"recorded_by": request.user},
                )
                record.status = request.POST[status_key]
                record.notes = request.POST.get(notes_key, "")

                if rsvp_key in request.POST:
                    record.rsvp_status = request.POST[rsvp_key]
                    record.rsvp_at = timezone.now()

                if check_in_key in request.POST and request.POST[check_in_key]:
                    from django.utils.dateparse import parse_datetime

                    parsed = parse_datetime(request.POST[check_in_key])
                    if parsed:
                        record.check_in_time = parsed

                if check_out_key in request.POST and request.POST[check_out_key]:
                    from django.utils.dateparse import parse_datetime

                    parsed = parse_datetime(request.POST[check_out_key])
                    if parsed:
                        record.check_out_time = parsed

                record.save()
                updated += 1

        messages.success(request, f"Attendance updated for {updated} member(s).")
        return redirect("meetings:meeting_detail", pk=pk)

    # Build context with existing records keyed by attendee pk
    existing = {r.attendee_id: r for r in meeting.attendance_records.all()}

    attendee_data = []
    for attendee in all_attendees:
        attendee_data.append(
            {
                "user": attendee,
                "record": existing.get(attendee.pk),
                "is_required": meeting.required_attendees.filter(
                    pk=attendee.pk
                ).exists(),
            }
        )

    return render(
        request,
        "meetings/manage_attendance.html",
        {
            "meeting": meeting,
            "attendee_data": attendee_data,
            "status_choices": MeetingAttendance.STATUS_CHOICES,
            "can_manage": True,
        },
    )


@login_required
@require_POST
def rsvp_meeting(request, pk):
    """Allow an attendee to RSVP to a meeting."""
    meeting = get_object_or_404(Meeting, pk=pk)
    user = request.user

    if not meeting.can_user_join(user):
        messages.error(request, "You are not on the attendee list for this meeting.")
        return redirect("meetings:meeting_detail", pk=pk)

    rsvp = request.POST.get("rsvp", "accepted")
    notes = request.POST.get("notes", "").strip()

    record, _ = MeetingAttendance.objects.get_or_create(
        meeting=meeting,
        attendee=user,
        defaults={"recorded_by": user},
    )
    record.rsvp_status = rsvp
    record.rsvp_at = timezone.now()
    record.rsvp_notes = notes
    record.save(update_fields=["rsvp_status", "rsvp_at", "rsvp_notes", "updated_at"])

    labels = {
        "accepted": "accepted",
        "declined": "declined",
        "tentative": "marked as tentative",
    }
    messages.success(
        request, f"You have {labels.get(rsvp, rsvp)} the meeting invitation."
    )
    return redirect("meetings:meeting_detail", pk=pk)


# ─── Actions ─────────────────────────────────────────────────────────────────


@login_required
def manage_actions(request, pk):
    """Add / view meeting action items."""
    meeting = get_object_or_404(Meeting, pk=pk)

    if request.user.role not in MANAGE_MEETINGS:
        # Non-managers can still view their own actions
        actions = meeting.actions.filter(assigned_to=request.user)
        return render(
            request,
            "meetings/meeting_actions.html",
            {
                "meeting": meeting,
                "actions": actions,
                "can_manage": False,
            },
        )

    if request.method == "POST":
        form = MeetingActionForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.meeting = meeting
            action.created_by = request.user
            action.save()
            messages.success(request, f'Action item "{action.title}" created.')
            return redirect("meetings:manage_actions", pk=pk)
    else:
        form = MeetingActionForm()

    actions = meeting.actions.select_related("assigned_to", "agenda_item").order_by(
        "due_date"
    )

    return render(
        request,
        "meetings/meeting_actions.html",
        {
            "meeting": meeting,
            "actions": actions,
            "form": form,
            "can_manage": True,
        },
    )


@login_required
@require_POST
def update_action_status(request, pk, action_pk):
    """Update the status of a meeting action item."""
    meeting = get_object_or_404(Meeting, pk=pk)
    action = get_object_or_404(MeetingAction, pk=action_pk, meeting=meeting)

    # Only assigned user or manager can update
    if request.user != action.assigned_to and request.user.role not in MANAGE_MEETINGS:
        messages.error(request, "You do not have permission to update this action.")
        return redirect("meetings:manage_actions", pk=pk)

    new_status = request.POST.get("status", "")
    if new_status in dict(MeetingAction.STATUS_CHOICES):
        action.status = new_status
        action.completion_notes = request.POST.get("completion_notes", "").strip()
        if new_status == "completed":
            action.completed_at = timezone.now()
        action.save(
            update_fields=["status", "completion_notes", "completed_at", "updated_at"]
        )
        messages.success(request, f'Action "{action.title}" updated to {new_status}.')
    else:
        messages.error(request, "Invalid status.")

    return redirect("meetings:manage_actions", pk=pk)


# ─── Search ──────────────────────────────────────────────────────────────────


@login_required
def meeting_search(request):
    """Full-text search across meetings."""
    form = MeetingSearchForm(request.GET or None)
    user = request.user
    meetings = Meeting.objects.select_related("organizer")

    # Role-based base filter
    if user.role not in MANAGE_MEETINGS:
        meetings = meetings.filter(
            Q(attendees=user) | Q(required_attendees=user) | Q(organizer=user)
        ).distinct()

    if form.is_valid():
        q = form.cleaned_data.get("query", "").strip()
        search_type = form.cleaned_data.get("search_type", "all")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        status = form.cleaned_data.get("status")

        if q:
            if search_type == "title":
                meetings = meetings.filter(title__icontains=q)
            elif search_type == "description":
                meetings = meetings.filter(description__icontains=q)
            elif search_type == "agenda":
                meetings = meetings.filter(agenda__icontains=q)
            else:
                meetings = meetings.filter(
                    Q(title__icontains=q)
                    | Q(description__icontains=q)
                    | Q(agenda__icontains=q)
                    | Q(location__icontains=q)
                )
        if date_from:
            meetings = meetings.filter(scheduled_date__date__gte=date_from)
        if date_to:
            meetings = meetings.filter(scheduled_date__date__lte=date_to)
        if status:
            meetings = meetings.filter(status=status)

    return render(
        request,
        "meetings/meeting_list.html",
        {
            "meetings": meetings,
            "search_form": form,
            "can_manage": user.role in MANAGE_MEETINGS,
            "is_search": True,
        },
    )


# ─── Calendar / API ──────────────────────────────────────────────────────────


@login_required
def meetings_calendar_data(request):
    """JSON endpoint for calendar view."""
    user = request.user
    qs = Meeting.objects.all()

    if user.role not in MANAGE_MEETINGS:
        qs = qs.filter(
            Q(attendees=user) | Q(required_attendees=user) | Q(organizer=user)
        ).distinct()

    # Limit to a reasonable date range
    from_date = request.GET.get("start")
    to_date = request.GET.get("end")
    if from_date:
        qs = qs.filter(scheduled_date__gte=from_date)
    if to_date:
        qs = qs.filter(scheduled_date__lte=to_date)

    STATUS_COLORS = {
        "scheduled": "#7dc143",
        "in_progress": "#2d7a6e",
        "completed": "#6b7280",
        "cancelled": "#ef4444",
        "postponed": "#f59e0b",
    }

    events = []
    for m in qs:
        events.append(
            {
                "id": str(m.pk),
                "title": m.title,
                "start": m.scheduled_date.isoformat(),
                "end": m.scheduled_end_time.isoformat(),
                "color": STATUS_COLORS.get(m.status, "#2d1b5e"),
                "url": m.get_absolute_url(),
                "extendedProps": {
                    "type": m.get_meeting_type_display(),
                    "status": m.get_status_display(),
                    "location": m.location,
                    "virtual": m.is_virtual,
                    "platform": m.platform_display,
                },
            }
        )

    return JsonResponse(events, safe=False)
