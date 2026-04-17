"""
Views for AI-powered meeting recording system.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import (
    MeetingRecording,
    Transcription,
    MeetingSummary,
    ActionItem,
    SentimentAnalysis,
    TopicDetection,
    RecordingSettings,
)
from django.core.paginator import Paginator


@login_required
def recording_list(request):
    """
    List all meeting recordings.
    """
    recordings = MeetingRecording.objects.select_related(
        'meeting', 'created_by'
    ).prefetch_related(
        'transcriptions', 'summaries', 'action_items'
    ).order_by('-started_at')
    
    # Filter by platform
    platform = request.GET.get('platform')
    if platform:
        recordings = recordings.filter(platform=platform)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        recordings = recordings.filter(status=status)
    
    # Filter by my recordings only
    my_only = request.GET.get('my_only')
    if my_only == 'true':
        recordings = recordings.filter(created_by=request.user)
    
    # Pagination
    paginator = Paginator(recordings, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Add duration_minutes to each recording
    for recording in page_obj:
        if recording.duration_seconds:
            recording.duration_minutes = recording.duration_seconds // 60
        else:
            recording.duration_minutes = 0
    
    context = {
        'page_obj': page_obj,
        'platform': platform,
        'status': status,
        'my_only': my_only,
    }
    
    return render(request, 'recordings/recording_list.html', context)


@login_required
def recording_detail(request, recording_id):
    """
    Detail view for a specific recording.
    """
    recording = get_object_or_404(
        MeetingRecording.objects.select_related(
            'meeting', 'created_by'
        ).prefetch_related(
            'transcriptions__segments',
            'summaries',
            'action_items',
            'sentiment_analysis',
            'topics',
        ),
        id=recording_id
    )
    
    # Get transcription
    transcription = recording.transcriptions.first()
    
    # Get summaries
    executive_summary = recording.summaries.filter(summary_type='executive').first()
    detailed_summary = recording.summaries.filter(summary_type='detailed').first()
    
    # Get action items
    action_items = recording.action_items.all()
    
    # Get sentiment analysis
    sentiment = recording.sentiment_analysis.first()
    
    # Get topics
    topics = recording.topics.all()
    
    context = {
        'recording': recording,
        'transcription': transcription,
        'executive_summary': executive_summary,
        'detailed_summary': detailed_summary,
        'action_items': action_items,
        'sentiment': sentiment,
        'topics': topics,
    }
    
    return render(request, 'recordings/recording_detail.html', context)


@login_required
def transcription_view(request, transcription_id):
    """
    View transcription with speaker identification and timestamps.
    """
    transcription = get_object_or_404(
        Transcription.objects.select_related('recording'),
        id=transcription_id
    )
    
    segments = transcription.segments.all().order_by('start_time')
    
    context = {
        'transcription': transcription,
        'segments': segments,
    }
    
    return render(request, 'recordings/transcription_view.html', context)


@login_required
def action_items_list(request):
    """
    List all action items with filtering.
    """
    action_items = ActionItem.objects.select_related(
        'recording', 'assigned_to'
    ).order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        action_items = action_items.filter(status=status)
    
    # Filter by priority
    priority = request.GET.get('priority')
    if priority:
        action_items = action_items.filter(priority=priority)
    
    # Filter by assigned to me
    my_only = request.GET.get('my_only')
    if my_only == 'true':
        action_items = action_items.filter(assigned_to=request.user)
    
    # Pagination
    paginator = Paginator(action_items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'priority': priority,
        'my_only': my_only,
    }
    
    return render(request, 'recordings/action_items_list.html', context)


@login_required
def action_item_detail(request, action_item_id):
    """
    Detail view for a specific action item.
    """
    action_item = get_object_or_404(
        ActionItem.objects.select_related('recording', 'assigned_to'),
        id=action_item_id
    )
    
    context = {
        'action_item': action_item,
    }
    
    return render(request, 'recordings/action_item_detail.html', context)


@login_required
def update_action_item_status(request, action_item_id):
    """
    Update action item status.
    """
    if request.method == 'POST':
        action_item = get_object_or_404(ActionItem, id=action_item_id)
        new_status = request.POST.get('status')
        
        if new_status in ['pending', 'in_progress', 'completed', 'cancelled']:
            action_item.status = new_status
            if new_status == 'completed':
                action_item.completed_at = timezone.now()
            action_item.save()
            
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'status': 'success'})
            
            messages.success(request, f"Action item status updated to {new_status}")
            return redirect('recordings:action_item_detail', action_item_id=action_item.id)
    
    return redirect('recordings:action_item_detail', action_item_id=action_item_id)


@login_required
def meeting_summaries_list(request):
    """
    List all meeting summaries.
    """
    summaries = MeetingSummary.objects.select_related(
        'recording'
    ).order_by('-created_at')
    
    # Filter by type
    summary_type = request.GET.get('type')
    if summary_type:
        summaries = summaries.filter(summary_type=summary_type)
    
    # Pagination
    paginator = Paginator(summaries, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'summary_type': summary_type,
    }
    
    return render(request, 'recordings/summaries_list.html', context)


@login_required
def dashboard(request):
    """
    Dashboard showing recording statistics and recent activity.
    """
    # Statistics
    total_recordings = MeetingRecording.objects.count()
    completed_recordings = MeetingRecording.objects.filter(status='completed').count()
    pending_recordings = MeetingRecording.objects.filter(status='pending').count()
    
    total_action_items = ActionItem.objects.count()
    completed_action_items = ActionItem.objects.filter(status='completed').count()
    pending_action_items = ActionItem.objects.filter(status='pending').count()
    
    my_action_items = ActionItem.objects.filter(assigned_to=request.user, status='pending')
    
    # Recent recordings
    recent_recordings = MeetingRecording.objects.select_related(
        'meeting', 'created_by'
    ).order_by('-started_at')[:5]
    
    # Recent action items
    recent_action_items = ActionItem.objects.select_related(
        'recording', 'assigned_to'
    ).order_by('-created_at')[:5]
    
    context = {
        'total_recordings': total_recordings,
        'completed_recordings': completed_recordings,
        'pending_recordings': pending_recordings,
        'total_action_items': total_action_items,
        'completed_action_items': completed_action_items,
        'pending_action_items': pending_action_items,
        'my_action_items': my_action_items,
        'recent_recordings': recent_recordings,
        'recent_action_items': recent_action_items,
    }
    
    return render(request, 'recordings/dashboard.html', context)
