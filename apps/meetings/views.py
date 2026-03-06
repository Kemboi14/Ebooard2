from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q

from .models import Meeting, AgendaItem, MeetingMinutes, MeetingAttendance
from .forms import CreateMeetingForm, AgendaForm, MeetingMinutesForm, MeetingSearchForm
from apps.accounts.decorators import role_required
from apps.accounts.permissions import MANAGE_MEETINGS

class MeetingListView(LoginRequiredMixin, ListView):
    """List view for meetings with role-based filtering"""
    model = Meeting
    template_name = 'meetings/meeting_list.html'
    context_object_name = 'meetings'
    paginate_by = 10
    
    def get_queryset(self):
        """Filter meetings based on user role"""
        user = self.request.user
        queryset = Meeting.objects.all()
        
        if user.role == 'company_secretary':
            # Company secretaries see all meetings
            return queryset
        elif user.role == 'board_member':
            # Board members see meetings they're invited to or attending
            return queryset.filter(
                Q(attendees=user) | Q(required_attendees=user)
            )
        else:
            # Other roles see meetings they're attending
            return queryset.filter(attendees=user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = MeetingSearchForm(self.request.GET or None)
        context['can_manage'] = self.request.user.role in MANAGE_MEETINGS
        return context

class MeetingDetailView(LoginRequiredMixin, DetailView):
    """Detail view for individual meetings"""
    model = Meeting
    template_name = 'meetings/meeting_detail.html'
    context_object_name = 'meeting'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meeting = self.get_object()
        user = self.request.user
        
        context['can_manage'] = user.role in MANAGE_MEETINGS
        context['is_attending'] = user in meeting.attendees.all()
        context['is_required'] = user in meeting.required_attendees.all()
        context['agenda_items'] = meeting.agendaitem_set.all().order_by('order')
        context['attendance_records'] = meeting.meetingattendance_set.all().order_by('attendee__first_name')
        
        # Get minutes if they exist
        try:
            context['minutes'] = meeting.meetingminutes
        except MeetingMinutes.DoesNotExist:
            context['minutes'] = None
        
        return context

class CreateMeetingView(LoginRequiredMixin, CreateView):
    """Create view for new meetings"""
    model = Meeting
    form_class = CreateMeetingForm
    template_name = 'meetings/meeting_form.html'
    success_url = reverse_lazy('meetings:meeting_list')
    
    def dispatch(self, request, *args, **kwargs):
        """Only users who can manage meetings can create them"""
        if request.user.role not in MANAGE_MEETINGS:
            messages.error(request, 'You do not have permission to create meetings.')
            return redirect('meetings:meeting_list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Set organizer and created_by fields"""
        form.instance.organizer = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Meeting created successfully!')
        return super().form_valid(form)

class UpdateMeetingView(LoginRequiredMixin, UpdateView):
    """Update view for existing meetings"""
    model = Meeting
    form_class = CreateMeetingForm
    template_name = 'meetings/meeting_form.html'
    context_object_name = 'meeting'
    
    def dispatch(self, request, *args, **kwargs):
        """Only users who can manage meetings can update them"""
        if request.user.role not in MANAGE_MEETINGS:
            messages.error(request, 'You do not have permission to update meetings.')
            return redirect('meetings:meeting_list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        context['can_manage'] = self.request.user.role in MANAGE_MEETINGS
        return context
    
    def form_valid(self, form):
        """Set updated_by field"""
        messages.success(self.request, 'Meeting updated successfully!')
        return super().form_valid(form)

@role_required('company_secretary', 'it_administrator')
def manage_agenda(request, meeting_id):
    """View to manage agenda items for a meeting"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    agenda_items = meeting.agendaitem_set.all().order_by('order')
    
    if request.method == 'POST':
        form = AgendaForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.meeting = meeting
            form.instance.created_by = request.user
            form.save()
            messages.success(request, 'Agenda item added successfully!')
            return redirect('meetings:meeting_detail', pk=meeting_id)
    else:
        form = AgendaForm()
    
    return render(request, 'meetings/manage_agenda.html', {
        'meeting': meeting,
        'agenda_items': agenda_items,
        'form': form,
    })

@role_required('company_secretary', 'it_administrator')
def manage_minutes(request, meeting_id):
    """View to manage meeting minutes"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    try:
        minutes = meeting.meetingminutes
    except MeetingMinutes.DoesNotExist:
        minutes = None
    
    if request.method == 'POST':
        form = MeetingMinutesForm(request.POST, request.FILES, instance=minutes)
        if form.is_valid():
            form.instance.meeting = meeting
            if not minutes:
                form.instance.drafted_by = request.user
            else:
                form.instance.updated_by = request.user
            form.save()
            messages.success(request, 'Minutes saved successfully!')
            return redirect('meetings:meeting_detail', pk=meeting_id)
    else:
        form = MeetingMinutesForm(instance=minutes)
    
    return render(request, 'meetings/manage_minutes.html', {
        'meeting': meeting,
        'minutes': minutes,
        'form': form,
    })

@role_required('company_secretary', 'it_administrator')
def manage_attendance(request, meeting_id):
    """View to manage meeting attendance"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    attendance_records = meeting.meetingattendance_set.all().order_by('attendee__first_name')
    
    if request.method == 'POST':
        # Handle attendance updates
        for attendee in meeting.attendees.all():
            status_key = f"status_{attendee.id}"
            notes_key = f"notes_{attendee.id}"
            check_in_key = f"check_in_{attendee.id}"
            check_out_key = f"check_out_{attendee.id}"
            
            if status_key in request.POST:
                attendance, created = MeetingAttendance.objects.get_or_create(
                    meeting=meeting,
                    attendee=attendee,
                    defaults={'recorded_by': request.user}
                )
                attendance.status = request.POST[status_key]
                attendance.notes = request.POST.get(notes_key, '')
                
                if check_in_key in request.POST:
                    attendance.check_in_time = timezone.now()
                if check_out_key in request.POST:
                    attendance.check_out_time = timezone.now()
                
                attendance.save()
        
        messages.success(request, 'Attendance updated successfully!')
        return redirect('meetings:meeting_detail', pk=meeting_id)
    
    return render(request, 'meetings/manage_attendance.html', {
        'meeting': meeting,
        'attendance_records': attendance_records,
    })

@login_required
def meeting_search(request):
    """Search meetings based on form criteria"""
    form = MeetingSearchForm(request.GET)
    meetings = Meeting.objects.all()
    
    if form.is_valid():
        query = form.cleaned_data.get('query', '')
        search_type = form.cleaned_data.get('search_type', 'all')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        status = form.cleaned_data.get('status')
        
        if query:
            if search_type == 'title':
                meetings = meetings.filter(title__icontains=query)
            elif search_type == 'description':
                meetings = meetings.filter(description__icontains=query)
            elif search_type == 'agenda':
                meetings = meetings.filter(agenda__icontains=query)
            else:  # all fields
                meetings = meetings.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(agenda__icontains=query)
                )
        
        if date_from:
            meetings = meetings.filter(scheduled_date__date__gte=date_from)
        if date_to:
            meetings = meetings.filter(scheduled_date__date__lte=date_to)
        if status:
            meetings = meetings.filter(status=status)
    
    return render(request, 'meetings/meeting_list.html', {
        'meetings': meetings,
        'search_form': form,
        'can_manage': request.user.role in MANAGE_MEETINGS,
    })
