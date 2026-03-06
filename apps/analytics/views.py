from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q, Case, When, Value, CharField
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.http import JsonResponse, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.core.cache import cache
import json
import datetime

from .models import (
    AnalyticsMetric, AnalyticsDataPoint, AnalyticsDashboard,
    AnalyticsWidget, BoardAnalyticsSnapshot, UserAnalyticsProfile, AnalyticsReport
)
from apps.accounts.decorators import role_required
from apps.accounts.permissions import MANAGE_DOCUMENTS


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """Main analytics dashboard view"""
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get recent snapshots
        recent_snapshots = BoardAnalyticsSnapshot.objects.filter(
            snapshot_type='daily'
        ).order_by('-snapshot_date')[:30]

        # Current metrics
        current_snapshot = recent_snapshots.first()
        previous_snapshot = recent_snapshots.filter(snapshot_date__lt=current_snapshot.snapshot_date).first() if current_snapshot else None

        context.update({
            'current_snapshot': current_snapshot,
            'previous_snapshot': previous_snapshot,
            'recent_snapshots': recent_snapshots,
            'user_profile': self.get_user_analytics_profile(user),
            'can_manage': user.role in ['it_administrator', 'company_secretary'],
        })

        return context

    def get_user_analytics_profile(self, user):
        """Get or create user analytics profile"""
        profile, created = UserAnalyticsProfile.objects.get_or_create(
            user=user,
            defaults={'overall_engagement_score': 0}
        )
        return profile


@login_required
def analytics_api_data(request):
    """API endpoint for analytics data"""
    metric_type = request.GET.get('metric')
    period = request.GET.get('period', '30d')  # 7d, 30d, 90d, 1y

    # Calculate date range
    end_date = timezone.now()
    if period == '7d':
        start_date = end_date - datetime.timedelta(days=7)
    elif period == '30d':
        start_date = end_date - datetime.timedelta(days=30)
    elif period == '90d':
        start_date = end_date - datetime.timedelta(days=90)
    elif period == '1y':
        start_date = end_date - datetime.timedelta(days=365)
    else:
        start_date = end_date - datetime.timedelta(days=30)

    # Get data points
    data_points = AnalyticsDataPoint.objects.filter(
        timestamp__range=(start_date, end_date)
    ).select_related('metric')

    if metric_type:
        data_points = data_points.filter(metric__metric_type=metric_type)

    # Group by metric and date
    data = {}
    for point in data_points:
        metric_name = point.metric.name
        date_key = point.timestamp.date().isoformat()

        if metric_name not in data:
            data[metric_name] = {}

        data[metric_name][date_key] = float(point.value)

    return JsonResponse({
        'data': data,
        'start_date': start_date.date().isoformat(),
        'end_date': end_date.date().isoformat(),
    })


@login_required
def meeting_analytics(request):
    """Meeting analytics view"""
    user = request.user

    # Meeting statistics
    from apps.meetings.models import Meeting, MeetingAttendance, VideoConferenceSession

    # Basic meeting stats
    total_meetings = Meeting.objects.count()
    upcoming_meetings = Meeting.objects.filter(
        scheduled_date__gt=timezone.now(),
        status='scheduled'
    ).count()

    # Attendance stats
    attendance_stats = MeetingAttendance.objects.aggregate(
        total_attendance=Count('id'),
        attended_count=Count(Case(When(status='attended', then=1))),
        absent_count=Count(Case(When(status='absent', then=1))),
    )

    attendance_rate = 0
    if attendance_stats['total_attendance'] > 0:
        attendance_rate = (attendance_stats['attended_count'] / attendance_stats['total_attendance']) * 100

    # Virtual meeting stats
    virtual_meetings = Meeting.objects.filter(is_virtual=True).count()
    video_sessions = VideoConferenceSession.objects.all()
    total_participants = video_sessions.aggregate(
        total=Sum('participant_count')
    )['total'] or 0

    # Recent meetings with attendance
    recent_meetings = Meeting.objects.select_related().filter(
        scheduled_date__lte=timezone.now()
    ).order_by('-scheduled_date')[:10]

    meeting_data = []
    for meeting in recent_meetings:
        attendance = meeting.attendance_records.all()
        attended = attendance.filter(status='attended').count()
        total_invited = attendance.count()

        meeting_data.append({
            'title': meeting.title,
            'date': meeting.scheduled_date.date(),
            'attended': attended,
            'invited': total_invited,
            'rate': (attended / total_invited * 100) if total_invited > 0 else 0,
        })

    context = {
        'total_meetings': total_meetings,
        'upcoming_meetings': upcoming_meetings,
        'attendance_rate': round(attendance_rate, 1),
        'virtual_meetings': virtual_meetings,
        'total_participants': total_participants,
        'meeting_data': meeting_data,
        'attendance_stats': attendance_stats,
    }

    return render(request, 'analytics/meeting_analytics.html', context)


@login_required
def document_analytics(request):
    """Document analytics view"""
    user = request.user

    from apps.documents.models import Document, DocumentActivity, DocumentTag

    # Document statistics
    total_documents = Document.objects.count()
    published_documents = Document.objects.filter(status='published').count()
    draft_documents = Document.objects.filter(status='draft').count()

    # Activity stats
    activity_stats = DocumentActivity.objects.aggregate(
        total_views=Count(Case(When(activity_type='viewed', then=1))),
        total_downloads=Count(Case(When(activity_type='downloaded', then=1))),
        total_uploads=Count(Case(When(activity_type='uploaded', then=1))),
    )

    # Popular documents
    popular_documents = Document.objects.annotate(
        view_count=Count('activities', filter=Q(activities__activity_type='viewed')),
        download_count=Count('activities', filter=Q(activities__activity_type='downloaded'))
    ).order_by('-view_count')[:10]

    # Tag usage
    tag_usage = DocumentTag.objects.order_by('-usage_count')[:10]

    # Recent activity
    recent_activity = DocumentActivity.objects.select_related(
        'document', 'user'
    ).order_by('-created_at')[:20]

    context = {
        'total_documents': total_documents,
        'published_documents': published_documents,
        'draft_documents': draft_documents,
        'activity_stats': activity_stats,
        'popular_documents': popular_documents,
        'tag_usage': tag_usage,
        'recent_activity': recent_activity,
    }

    return render(request, 'analytics/document_analytics.html', context)


@login_required
def user_engagement_analytics(request):
    """User engagement analytics view"""
    user = request.user

    # User engagement profiles
    engagement_profiles = UserAnalyticsProfile.objects.select_related('user').order_by(
        '-overall_engagement_score'
    )[:20]

    # User activity summary
    total_users = UserAnalyticsProfile.objects.count()
    active_users = UserAnalyticsProfile.objects.filter(
        last_activity__gte=timezone.now() - datetime.timedelta(days=30)
    ).count()

    # Engagement distribution
    engagement_ranges = {
        'High (80-100)': UserAnalyticsProfile.objects.filter(overall_engagement_score__gte=80).count(),
        'Medium (50-79)': UserAnalyticsProfile.objects.filter(
            overall_engagement_score__gte=50, overall_engagement_score__lt=80
        ).count(),
        'Low (0-49)': UserAnalyticsProfile.objects.filter(overall_engagement_score__lt=50).count(),
    }

    # Top contributors
    top_contributors = UserAnalyticsProfile.objects.select_related('user').order_by(
        '-meetings_attended', '-documents_viewed', '-votes_cast'
    )[:10]

    context = {
        'engagement_profiles': engagement_profiles,
        'total_users': total_users,
        'active_users': active_users,
        'engagement_ranges': engagement_ranges,
        'top_contributors': top_contributors,
        'active_percentage': (active_users / total_users * 100) if total_users > 0 else 0,
    }

    return render(request, 'analytics/user_engagement.html', context)


@login_required
def system_performance_analytics(request):
    """System performance analytics view"""
    user = request.user

    # Recent snapshots
    snapshots = BoardAnalyticsSnapshot.objects.filter(
        snapshot_type='daily'
    ).order_by('-snapshot_date')[:30]

    # Performance metrics
    avg_response_time = snapshots.aggregate(
        avg=Avg('average_response_time')
    )['avg'] or 0

    avg_uptime = snapshots.aggregate(
        avg=Avg('system_uptime')
    )['avg'] or 100

    # Recent system activity
    recent_activity = {
        'logins': snapshots.aggregate(avg=Avg('login_count'))['avg'] or 0,
        'active_users': snapshots.aggregate(avg=Avg('active_users'))['avg'] or 0,
        'documents': snapshots.aggregate(avg=Avg('total_documents'))['avg'] or 0,
        'meetings': snapshots.aggregate(avg=Avg('total_meetings'))['avg'] or 0,
    }

    # Performance trends
    performance_trends = []
    for snapshot in snapshots[:14]:  # Last 14 days
        performance_trends.append({
            'date': snapshot.snapshot_date.isoformat(),
            'response_time': float(snapshot.average_response_time),
            'uptime': float(snapshot.system_uptime),
            'active_users': snapshot.active_users,
        })

    context = {
        'avg_response_time': round(avg_response_time, 2),
        'avg_uptime': round(avg_uptime, 2),
        'recent_activity': recent_activity,
        'performance_trends': json.dumps(performance_trends, cls=DjangoJSONEncoder),
        'snapshots': snapshots,
    }

    return render(request, 'analytics/system_performance.html', context)


@login_required
def voting_analytics(request):
    """Voting analytics view"""
    user = request.user

    from apps.voting.models import Motion, Vote

    # Voting statistics
    total_motions = Motion.objects.count()
    active_motions = Motion.objects.filter(
        status__in=['active', 'open_for_voting']
    ).count()

    # Vote statistics
    vote_stats = Vote.objects.aggregate(
        total_votes=Count('id'),
        yes_votes=Count(Case(When(choice='yes', then=1))),
        no_votes=Count(Case(When(choice='no', then=1))),
        abstain_votes=Count(Case(When(choice='abstain', then=1))),
    )

    # Participation rate
    unique_voters = Vote.objects.values('voter').distinct().count()
    total_board_members = UserAnalyticsProfile.objects.filter(
        user__role='board_member'
    ).count()

    participation_rate = (unique_voters / total_board_members * 100) if total_board_members > 0 else 0

    # Recent motions with results
    recent_motions = Motion.objects.select_related().filter(
        status__in=['passed', 'failed', 'closed']
    ).order_by('-created_at')[:10]

    motion_data = []
    for motion in recent_motions:
        votes = motion.votes.all()
        yes_count = votes.filter(choice='yes').count()
        no_count = votes.filter(choice='no').count()
        abstain_count = votes.filter(choice='abstain').count()

        motion_data.append({
            'title': motion.title,
            'date': motion.created_at.date(),
            'status': motion.get_status_display(),
            'yes_votes': yes_count,
            'no_votes': no_count,
            'abstain_votes': abstain_count,
            'total_votes': yes_count + no_count + abstain_count,
        })

    context = {
        'total_motions': total_motions,
        'active_motions': active_motions,
        'vote_stats': vote_stats,
        'participation_rate': round(participation_rate, 1),
        'motion_data': motion_data,
    }

    return render(request, 'analytics/voting_analytics.html', context)


@login_required
def analytics_reports(request):
    """Analytics reports management"""
    # Allow access to admins (Django admin) or specific roles
    if not (request.user.is_staff or request.user.role in ['it_administrator', 'company_secretary']):
        return render(request, '403.html', status=403)

    reports = AnalyticsReport.objects.select_related('generated_by').order_by('-created_at')

    if request.method == 'POST':
        # Handle report generation
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        format_type = request.POST.get('format', 'pdf')

        if report_type and start_date and end_date:
            report = AnalyticsReport.objects.create(
                title=f"{report_type.replace('_', ' ').title()} Report - {start_date} to {end_date}",
                report_type=report_type,
                format=format_type,
                start_date=start_date,
                end_date=end_date,
                generated_by=request.user,
                status='generating'
            )

            # TODO: Implement actual report generation logic
            # For now, just mark as completed
            report.status = 'completed'
            report.generated_at = timezone.now()
            report.save()

            messages.success(request, f"Report '{report.title}' generated successfully.")
            return redirect('analytics:reports')

    context = {
        'reports': reports,
    }

    return render(request, 'analytics/reports.html', context)


@login_required
def export_analytics_data(request):
    """Export analytics data as CSV/Excel"""
    data_type = request.GET.get('type', 'meetings')
    format_type = request.GET.get('format', 'csv')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # TODO: Implement actual data export logic
    # For now, return a simple response

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{data_type}_analytics.csv"'

    # Simple CSV header
    response.write('Date,Metric,Value\n')

    # Add some sample data
    response.write('2024-01-01,Sample Metric,100\n')
    response.write('2024-01-02,Sample Metric,120\n')

    return response


# API endpoints for real-time data
@login_required
def analytics_live_data(request):
    """Real-time analytics data for dashboard widgets"""
    data_type = request.GET.get('type', 'summary')

    if data_type == 'summary':
        # Get current summary stats
        current_snapshot = BoardAnalyticsSnapshot.objects.filter(
            snapshot_type='daily'
        ).order_by('-snapshot_date').first()

        if current_snapshot:
            data = {
                'meetings': current_snapshot.total_meetings,
                'attendance_rate': float(current_snapshot.average_attendance_rate),
                'documents': current_snapshot.total_documents,
                'active_users': current_snapshot.active_users,
                'voting_participation': float(current_snapshot.voting_participation_rate),
            }
        else:
            data = {
                'meetings': 0,
                'attendance_rate': 0,
                'documents': 0,
                'active_users': 0,
                'voting_participation': 0,
            }

    elif data_type == 'trends':
        # Get trend data for the last 7 days
        snapshots = BoardAnalyticsSnapshot.objects.filter(
            snapshot_type='daily',
            snapshot_date__gte=timezone.now().date() - datetime.timedelta(days=7)
        ).order_by('snapshot_date')

        data = []
        for snapshot in snapshots:
            data.append({
                'date': snapshot.snapshot_date.isoformat(),
                'meetings': snapshot.total_meetings,
                'attendance': float(snapshot.average_attendance_rate),
                'documents': snapshot.total_documents,
                'users': snapshot.active_users,
            })

    return JsonResponse({'data': data, 'timestamp': timezone.now().isoformat()})
