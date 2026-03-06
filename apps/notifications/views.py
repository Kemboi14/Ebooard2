from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .models import (
    Notification, NotificationPreference, NotificationTemplate, NotificationBatch, NotificationChannel
)
from .forms import (
    NotificationForm, NotificationPreferenceForm, NotificationTemplateForm, NotificationBatchForm,
    NotificationChannelForm, NotificationSearchForm, QuickNotificationForm
)
from apps.accounts.models import User

class NotificationListView(LoginRequiredMixin, ListView):
    """List all notifications for the current user"""
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user).select_related('content_type')
        
        # Apply filters
        search = self.request.GET.get('query')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(message__icontains=search)
            )
        
        notification_type = self.request.GET.get('notification_type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        is_read = self.request.GET.get('is_read')
        if is_read == 'read':
            queryset = queryset.filter(is_read=True)
        elif is_read == 'unread':
            queryset = queryset.filter(is_read=False)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = NotificationSearchForm(self.request.GET)
        context['unread_count'] = Notification.objects.filter(
            recipient=self.request.user, is_read=False
        ).count()
        return context

class NotificationDetailView(LoginRequiredMixin, DetailView):
    """View notification details"""
    model = Notification
    template_name = 'notifications/notification_detail.html'
    context_object_name = 'notification'

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def get_object(self):
        obj = super().get_object()
        # Mark as read when viewed
        if not obj.is_read:
            obj.mark_as_read()
        return obj

@login_required
def mark_notification_read(request, pk):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('HX-Request'):
        return HttpResponse(status=200)
    
    return redirect('notifications:notification_list')

@login_required
def mark_notification_unread(request, pk):
    """Mark a notification as unread"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = False
    notification.read_at = None
    notification.save(update_fields=['is_read', 'read_at'])
    
    if request.headers.get('HX-Request'):
        return HttpResponse(status=200)
    
    return redirect('notifications:notification_list')

@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    
    if request.headers.get('HX-Request'):
        return HttpResponse(status=200)
    
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications:notification_list')

@login_required
@require_POST
def delete_notification(request, pk):
    """Delete a notification"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    
    if request.headers.get('HX-Request'):
        return HttpResponse(status=200)
    
    messages.success(request, "Notification deleted.")
    return redirect('notifications:notification_list')

@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    preference, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, "Notification preferences updated successfully.")
            return redirect('notifications:preferences')
    else:
        form = NotificationPreferenceForm(instance=preference)
    
    return render(request, 'notifications/notification_preferences.html', {
        'form': form,
        'preference': preference
    })

class NotificationCreateView(LoginRequiredMixin, CreateView):
    """Create a new notification"""
    model = Notification
    form_class = NotificationForm
    template_name = 'notifications/notification_form.html'
    success_url = reverse_lazy('notifications:notification_list')

    def form_valid(self, form):
        form.instance.save()
        messages.success(self.request, f"Notification sent to {form.instance.recipient.get_full_name()}.")
        return super().form_valid(form)

class NotificationTemplateListView(LoginRequiredMixin, ListView):
    """List notification templates"""
    model = NotificationTemplate
    template_name = 'notifications/template_list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        return NotificationTemplate.objects.filter(is_active=True).order_by('name')

class NotificationTemplateCreateView(LoginRequiredMixin, CreateView):
    """Create a new notification template"""
    model = NotificationTemplate
    form_class = NotificationTemplateForm
    template_name = 'notifications/template_form.html'
    success_url = reverse_lazy('notifications:template_list')

    def form_valid(self, form):
        messages.success(self.request, f"Template '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class NotificationBatchCreateView(LoginRequiredMixin, CreateView):
    """Create batch notifications"""
    model = NotificationBatch
    form_class = NotificationBatchForm
    template_name = 'notifications/batch_form.html'
    success_url = reverse_lazy('notifications:notification_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        batch = form.save()
        
        # Create individual notifications
        notifications = batch.create_notifications()
        
        messages.success(self.request, f"Batch notification sent to {batch.total_recipients} recipients.")
        return redirect('notifications:notification_list')

@login_required
def quick_notification(request):
    """Quick notification form"""
    if request.method == 'POST':
        form = QuickNotificationForm(request.POST)
        if form.is_valid():
            notification = Notification.objects.create(
                recipient=form.cleaned_data['recipient'],
                title=form.cleaned_data['title'],
                message=form.cleaned_data['message'],
                notification_type=form.cleaned_data['notification_type'],
                priority=form.cleaned_data['priority'],
                action_url=form.cleaned_data['action_url'],
            )
            
            messages.success(request, f"Notification sent to {notification.recipient.get_full_name()}.")
            return redirect('notifications:notification_list')
    else:
        form = QuickNotificationForm()
    
    return render(request, 'notifications/quick_notification.html', {
        'form': form
    })

@login_required
def notification_center(request):
    """Notification center dashboard"""
    user = request.user
    
    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=user
    ).order_by('-created_at')[:10]
    
    # Statistics
    total_notifications = Notification.objects.filter(recipient=user).count()
    unread_notifications = Notification.objects.filter(recipient=user, is_read=False).count()
    
    # Notification types breakdown
    notification_types = Notification.objects.filter(recipient=user).values(
        'notification_type'
    ).annotate(count=Count('id')).order_by('-count')
    
    # Priority breakdown
    priority_breakdown = Notification.objects.filter(recipient=user).values(
        'priority'
    ).annotate(count=Count('id'))
    
    return render(request, 'notifications/notification_center.html', {
        'recent_notifications': recent_notifications,
        'total_notifications': total_notifications,
        'unread_notifications': unread_notifications,
        'notification_types': notification_types,
        'priority_breakdown': priority_breakdown,
        'quick_form': QuickNotificationForm(),
    })

@login_required
def notification_stats(request):
    """Get notification statistics for dashboard"""
    user = request.user
    
    stats = {
        'total': Notification.objects.filter(recipient=user).count(),
        'unread': Notification.objects.filter(recipient=user, is_read=False).count(),
        'urgent': Notification.objects.filter(recipient=user, priority='urgent', is_read=False).count(),
        'high': Notification.objects.filter(recipient=user, priority='high', is_read=False).count(),
    }
    
    return JsonResponse(stats)

@login_required
def send_test_notification(request):
    """Send a test notification to the current user"""
    notification = Notification.objects.create(
        recipient=request.user,
        title="Test Notification",
        message="This is a test notification to verify the system is working correctly.",
        notification_type="system_update",
        priority="normal",
    )
    
    messages.success(request, "Test notification sent!")
    return redirect('notifications:notification_center')

# Template Management (admin only)
class NotificationChannelListView(LoginRequiredMixin, ListView):
    """List notification channels"""
    model = NotificationChannel
    template_name = 'notifications/channel_list.html'
    context_object_name = 'channels'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['company_secretary', 'it_administrator']:
            messages.error(request, "You don't have permission to manage notification channels.")
            return redirect('notifications:notification_list')
        return super().dispatch(request, *args, **kwargs)

class NotificationChannelCreateView(LoginRequiredMixin, CreateView):
    """Create a new notification channel"""
    model = NotificationChannel
    form_class = NotificationChannelForm
    template_name = 'notifications/channel_form.html'
    success_url = reverse_lazy('notifications:channel_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['company_secretary', 'it_administrator']:
            messages.error(request, "You don't have permission to create notification channels.")
            return redirect('notifications:notification_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"Channel '{form.instance.name}' created successfully.")
        return super().form_valid(form)

# Notification Service Functions
def create_notification(recipient, title, message, notification_type, 
                       priority='normal', action_url=None, metadata=None):
    """Helper function to create a notification"""
    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        action_url=action_url,
        metadata=metadata or {}
    )
    return notification

def create_batch_notification(recipients, title, message, notification_type,
                           priority='normal', action_url=None, metadata=None):
    """Helper function to create batch notifications"""
    batch = NotificationBatch.objects.create(
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        action_url=action_url,
    )
    batch.recipients.set(recipients)
    batch.total_recipients = batch.recipients.count()
    batch.save()
    
    # Create individual notifications
    return batch.create_notifications()

def send_meeting_reminder(meeting, recipients=None):
    """Send meeting reminder notifications"""
    if recipients is None:
        recipients = meeting.participants.all()
    
    for recipient in recipients:
        create_notification(
            recipient=recipient,
            title=f"Meeting Reminder: {meeting.title}",
            message=f"Your meeting '{meeting.title}' starts at {meeting.start_time}.",
            notification_type='meeting_reminder',
            priority='high',
            action_url=f"/meetings/{meeting.pk}/",
            metadata={'meeting_id': str(meeting.pk)}
        )

def send_voting_notification(voting, notification_type, recipients=None):
    """Send voting-related notifications"""
    if recipients is None:
        recipients = voting.participants.all()
    
    if notification_type == 'voting_open':
        title = f"Voting Open: {voting.title}"
        message = f"A new vote '{voting.title}' is now open. Cast your vote before {voting.end_time}."
    elif notification_type == 'voting_close':
        title = f"Voting Closing Soon: {voting.title}"
        message = f"The vote '{voting.title}' closes in 1 hour. Make sure to cast your vote."
    elif notification_type == 'voting_result':
        title = f"Voting Results: {voting.title}"
        message = f"Results for '{voting.title}' are now available."
    else:
        return
    
    for recipient in recipients:
        create_notification(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            priority='normal',
            action_url=f"/voting/{voting.pk}/",
            metadata={'voting_id': str(voting.pk)}
        )
