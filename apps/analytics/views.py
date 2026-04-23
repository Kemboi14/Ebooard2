from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.accounts.mixins import BranchOrganizationFilterMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q, Case, When, Value, CharField
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.http import JsonResponse, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
import datetime

from .models import (
    AnalyticsMetric, AnalyticsDataPoint, AnalyticsDashboard,
    AnalyticsWidget, BoardAnalyticsSnapshot, UserAnalyticsProfile, AnalyticsReport,
    ComplianceScorecard, AttendanceAnalytics, DecisionTracking, CustomReport
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


@login_required
def board_performance_analytics(request):
    """Board performance analytics with KPIs"""
    user = request.user
    
    from apps.meetings.models import Meeting, MeetingAttendance
    from apps.voting.models import Motion, Vote
    from apps.documents.models import Document
    from apps.agencies.models import CommitteeMembership
    
    # Time period
    period = request.GET.get('period', '90d')
    if period == '30d':
        start_date = timezone.now() - datetime.timedelta(days=30)
    elif period == '90d':
        start_date = timezone.now() - datetime.timedelta(days=90)
    elif period == '1y':
        start_date = timezone.now() - datetime.timedelta(days=365)
    else:
        start_date = timezone.now() - datetime.timedelta(days=90)
    
    # Meeting KPIs
    total_meetings = Meeting.objects.filter(scheduled_date__gte=start_date).count()
    completed_meetings = Meeting.objects.filter(
        scheduled_date__gte=start_date,
        status='completed'
    ).count()
    
    # Attendance KPIs
    attendance_records = MeetingAttendance.objects.filter(
        meeting__scheduled_date__gte=start_date
    )
    total_attendance = attendance_records.count()
    attended_count = attendance_records.filter(status='attended').count()
    attendance_rate = (attended_count / total_attendance * 100) if total_attendance > 0 else 0
    
    # Voting KPIs
    total_motions = Motion.objects.filter(created_at__gte=start_date).count()
    passed_motions = Motion.objects.filter(
        created_at__gte=start_date,
        status='passed'
    ).count()
    
    total_votes = Vote.objects.filter(created_at__gte=start_date).count()
    board_members = CommitteeMembership.objects.filter(
        is_active=True,
        user__role='board_member'
    ).count()
    
    # Document KPIs
    board_documents = Document.objects.filter(
        created_at__gte=start_date,
        category__in=['board_minutes', 'board_resolutions', 'board_policies']
    ).count()
    
    # Decision tracking
    decisions_with_outcomes = Motion.objects.filter(
        created_at__gte=start_date,
        status__in=['passed', 'failed']
    ).count()
    
    # Board member participation
    board_member_participation = []
    for membership in CommitteeMembership.objects.filter(
        is_active=True,
        user__role='board_member'
    ).select_related('user'):
        member = membership.user
        meetings_attended = MeetingAttendance.objects.filter(
            meeting__scheduled_date__gte=start_date,
            user=member,
            status='attended'
        ).count()
        votes_cast = Vote.objects.filter(
            created_at__gte=start_date,
            voter=member
        ).count()
        
        board_member_participation.append({
            'name': member.get_full_name(),
            'meetings_attended': meetings_attended,
            'votes_cast': votes_cast,
            'engagement_score': (meetings_attended * 10 + votes_cast * 5)
        })
    
    # Sort by engagement score
    board_member_participation.sort(key=lambda x: x['engagement_score'], reverse=True)
    
    context = {
        'period': period,
        'total_meetings': total_meetings,
        'completed_meetings': completed_meetings,
        'completion_rate': round((completed_meetings / total_meetings * 100) if total_meetings > 0 else 0, 1),
        'attendance_rate': round(attendance_rate, 1),
        'total_motions': total_motions,
        'passed_motions': passed_motions,
        'pass_rate': round((passed_motions / total_motions * 100) if total_motions > 0 else 0, 1),
        'total_votes': total_votes,
        'voting_participation': round((total_votes / (board_members * total_motions) * 100) if board_members > 0 and total_motions > 0 else 0, 1),
        'board_documents': board_documents,
        'decisions_with_outcomes': decisions_with_outcomes,
        'board_member_participation': board_member_participation,
    }
    
    return render(request, 'analytics/board_performance.html', context)


@login_required
def compliance_scorecard(request):
    """Compliance scorecard with real-time tracking"""
    user = request.user
    
    from apps.risk.models import ComplianceRequirement, ComplianceAudit
    
    # Overall compliance score
    all_requirements = ComplianceRequirement.objects.all()
    total_requirements = all_requirements.count()
    
    # Calculate overall compliance score
    if total_requirements > 0:
        avg_compliance_score = all_requirements.aggregate(
            avg=Avg('compliance_score')
        )['avg'] or 0
    else:
        avg_compliance_score = 100
    
    # Compliance by category
    compliance_by_category = []
    for category in ComplianceRequirement.CATEGORY_CHOICES:
        category_code = category[0]
        category_name = category[1]
        requirements = all_requirements.filter(category=category_code)
        
        if requirements.count() > 0:
            category_score = requirements.aggregate(avg=Avg('compliance_score'))['avg'] or 0
            compliant_count = requirements.filter(status='compliant').count()
            non_compliant_count = requirements.filter(status='non_compliant').count()
            
            compliance_by_category.append({
                'category': category_name,
                'score': round(category_score, 1),
                'total': requirements.count(),
                'compliant': compliant_count,
                'non_compliant': non_compliant_count,
            })
    
    # High priority items
    high_priority_items = all_requirements.filter(
        priority__in=['high', 'critical'],
        status__in=['non_compliant', 'partially_compliant']
    ).order_by('-priority', '-compliance_score')[:10]
    
    # Upcoming audits
    upcoming_audits = ComplianceAudit.objects.filter(
        audit_date__gte=timezone.now().date(),
        status__in=['scheduled', 'in_progress']
    ).order_by('audit_date')[:10]
    
    # Recent audit results
    recent_audits = ComplianceAudit.objects.filter(
        status='completed'
    ).order_by('-audit_date')[:10]
    
    # Overdue reviews
    overdue_reviews = all_requirements.filter(
        review_date__lt=timezone.now().date(),
        status__in=['partially_compliant', 'non_compliant']
    ).order_by('review_date')[:10]
    
    context = {
        'overall_score': round(avg_compliance_score, 1),
        'total_requirements': total_requirements,
        'compliance_by_category': compliance_by_category,
        'high_priority_items': high_priority_items,
        'upcoming_audits': upcoming_audits,
        'recent_audits': recent_audits,
        'overdue_reviews': overdue_reviews,
    }
    
    return render(request, 'analytics/compliance_scorecard.html', context)


@login_required
def attendance_participation_analytics(request):
    """Attendance and participation analytics with detailed tracking"""
    user = request.user
    
    from apps.meetings.models import Meeting, MeetingAttendance
    from apps.voting.models import Vote
    from apps.agencies.models import CommitteeMembership
    
    # Time period
    period = request.GET.get('period', '90d')
    if period == '30d':
        start_date = timezone.now() - datetime.timedelta(days=30)
    elif period == '90d':
        start_date = timezone.now() - datetime.timedelta(days=90)
    elif period == '1y':
        start_date = timezone.now() - datetime.timedelta(days=365)
    else:
        start_date = timezone.now() - datetime.timedelta(days=90)
    
    # Overall attendance
    total_invitations = MeetingAttendance.objects.filter(
        meeting__scheduled_date__gte=start_date
    ).count()
    attended = MeetingAttendance.objects.filter(
        meeting__scheduled_date__gte=start_date,
        status='attended'
    ).count()
    overall_attendance_rate = (attended / total_invitations * 100) if total_invitations > 0 else 0
    
    # Attendance by meeting type
    meeting_types = Meeting.objects.filter(
        scheduled_date__gte=start_date
    ).values('meeting_type').annotate(
        total=Count('attendance_records'),
        attended=Count('attendance_records', filter=Q(attendance_records__status='attended'))
    )
    
    attendance_by_type = []
    for mt in meeting_types:
        attendance_by_type.append({
            'type': mt['meeting_type'] or 'Regular',
            'total': mt['total'],
            'attended': mt['attended'],
            'rate': round((mt['attended'] / mt['total'] * 100) if mt['total'] > 0 else 0, 1)
        })
    
    # Individual member participation
    member_participation = []
    for membership in CommitteeMembership.objects.filter(
        is_active=True
    ).select_related('user'):
        member = membership.user
        meetings_attended = MeetingAttendance.objects.filter(
            meeting__scheduled_date__gte=start_date,
            user=member,
            status='attended'
        ).count()
        total_invited = MeetingAttendance.objects.filter(
            meeting__scheduled_date__gte=start_date,
            user=member
        ).count()
        votes_cast = Vote.objects.filter(
            created_at__gte=start_date,
            voter=member
        ).count()
        
        attendance_rate = (meetings_attended / total_invited * 100) if total_invited > 0 else 0
        
        member_participation.append({
            'name': member.get_full_name(),
            'role': member.role,
            'meetings_attended': meetings_attended,
            'total_invited': total_invited,
            'attendance_rate': round(attendance_rate, 1),
            'votes_cast': votes_cast,
            'participation_score': round((attendance_rate * 0.6 + (votes_cast / 10) * 40), 1)
        })
    
    # Sort by participation score
    member_participation.sort(key=lambda x: x['participation_score'], reverse=True)
    
    # Monthly attendance trends
    monthly_attendance = []
    for i in range(12):
        month_start = (timezone.now() - datetime.timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        
        month_attendance = MeetingAttendance.objects.filter(
            meeting__scheduled_date__range=(month_start, month_end)
        ).aggregate(
            total=Count('id'),
            attended=Count('id', filter=Q(status='attended'))
        )
        
        rate = (month_attendance['attended'] / month_attendance['total'] * 100) if month_attendance['total'] > 0 else 0
        
        monthly_attendance.append({
            'month': month_start.strftime('%B %Y'),
            'total': month_attendance['total'],
            'attended': month_attendance['attended'],
            'rate': round(rate, 1)
        })
    
    monthly_attendance.reverse()
    
    # Absenteeism analysis
    absenteeism_records = MeetingAttendance.objects.filter(
        meeting__scheduled_date__gte=start_date,
        status='absent'
    ).select_related('user', 'meeting')
    
    context = {
        'period': period,
        'overall_attendance_rate': round(overall_attendance_rate, 1),
        'total_invitations': total_invitations,
        'attended': attended,
        'absent': total_invitations - attended,
        'attendance_by_type': attendance_by_type,
        'member_participation': member_participation,
        'monthly_attendance': monthly_attendance[-6:],  # Last 6 months
        'absenteeism_records': absenteeism_records[:20],
    }
    
    return render(request, 'analytics/attendance_participation.html', context)


@login_required
def decision_tracking_analytics(request):
    """Decision tracking and outcome metrics"""
    user = request.user
    
    from apps.voting.models import Motion, Vote
    from apps.meetings.models import Meeting
    
    # Time period
    period = request.GET.get('period', '90d')
    if period == '30d':
        start_date = timezone.now() - datetime.timedelta(days=30)
    elif period == '90d':
        start_date = timezone.now() - datetime.timedelta(days=90)
    elif period == '1y':
        start_date = timezone.now() - datetime.timedelta(days=365)
    else:
        start_date = timezone.now() - datetime.timedelta(days=90)
    
    # Decision statistics
    total_decisions = Motion.objects.filter(created_at__gte=start_date).count()
    passed_decisions = Motion.objects.filter(
        created_at__gte=start_date,
        status='passed'
    ).count()
    failed_decisions = Motion.objects.filter(
        created_at__gte=start_date,
        status='failed'
    ).count()
    pending_decisions = Motion.objects.filter(
        created_at__gte=start_date,
        status__in=['active', 'open_for_voting']
    ).count()
    
    # Decision pass rate
    pass_rate = (passed_decisions / total_decisions * 100) if total_decisions > 0 else 0
    
    # Decisions by category
    decisions_by_category = Motion.objects.filter(
        created_at__gte=start_date
    ).values('category').annotate(
        total=Count('id'),
        passed=Count('id', filter=Q(status='passed')),
        failed=Count('id', filter=Q(status='failed'))
    )
    
    category_stats = []
    for dc in decisions_by_category:
        category_total = dc['total']
        category_stats.append({
            'category': dc['category'] or 'General',
            'total': category_total,
            'passed': dc['passed'],
            'failed': dc['failed'],
            'pass_rate': round((dc['passed'] / category_total * 100) if category_total > 0 else 0, 1)
        })
    
    # Decision outcomes
    decision_outcomes = Motion.objects.filter(
        created_at__gte=start_date,
        status__in=['passed', 'failed']
    ).select_related('meeting').order_by('-created_at')[:20]
    
    # Time to decision (average days from creation to closure)
    decisions_with_dates = Motion.objects.filter(
        created_at__gte=start_date,
        status__in=['passed', 'failed'],
        closed_at__isnull=False
    )
    
    avg_decision_time = 0
    if decisions_with_dates.exists():
        decision_times = [(d.closed_at - d.created_at).days for d in decisions_with_dates]
        avg_decision_time = sum(decision_times) / len(decision_times)
    
    # Decision implementation tracking
    implemented_decisions = Motion.objects.filter(
        created_at__gte=start_date,
        status='passed',
        implemented=True
    ).count()
    
    implementation_rate = (implemented_decisions / passed_decisions * 100) if passed_decisions > 0 else 0
    
    # Recent decisions with outcomes
    recent_decisions = []
    for motion in Motion.objects.filter(
        created_at__gte=start_date,
        status__in=['passed', 'failed']
    ).order_by('-created_at')[:10]:
        yes_votes = motion.votes.filter(choice='yes').count()
        no_votes = motion.votes.filter(choice='no').count()
        abstain_votes = motion.votes.filter(choice='abstain').count()
        
        recent_decisions.append({
            'title': motion.title,
            'date': motion.created_at.date(),
            'status': motion.get_status_display(),
            'category': motion.category or 'General',
            'yes_votes': yes_votes,
            'no_votes': no_votes,
            'abstain_votes': abstain_votes,
            'total_votes': yes_votes + no_votes + abstain_votes,
            'implemented': motion.implemented if motion.status == 'passed' else None,
        })
    
    context = {
        'period': period,
        'total_decisions': total_decisions,
        'passed_decisions': passed_decisions,
        'failed_decisions': failed_decisions,
        'pending_decisions': pending_decisions,
        'pass_rate': round(pass_rate, 1),
        'category_stats': category_stats,
        'decision_outcomes': decision_outcomes,
        'avg_decision_time': round(avg_decision_time, 1),
        'implemented_decisions': implemented_decisions,
        'implementation_rate': round(implementation_rate, 1),
        'recent_decisions': recent_decisions,
    }
    
    return render(request, 'analytics/decision_tracking.html', context)


@login_required
def custom_report_builder(request):
    """Custom report builder for creating personalized reports"""
    user = request.user
    
    # Only allow admins and company secretaries to build reports
    if user.role not in ['it_administrator', 'company_secretary']:
        messages.error(request, "You don't have permission to build custom reports.")
        return redirect('analytics:dashboard')
    
    if request.method == 'POST':
        # Build report based on user selections
        report_type = request.POST.get('report_type')
        data_sources = request.POST.getlist('data_sources')
        date_range = request.POST.get('date_range')
        custom_start = request.POST.get('start_date')
        custom_end = request.POST.get('end_date')
        include_charts = request.POST.get('include_charts') == 'on'
        export_format = request.POST.get('format', 'pdf')
        
        # Calculate date range
        if date_range == 'custom' and custom_start and custom_end:
            start_date = datetime.datetime.strptime(custom_start, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(custom_end, '%Y-%m-%d').date()
        elif date_range == '30d':
            start_date = (timezone.now() - datetime.timedelta(days=30)).date()
            end_date = timezone.now().date()
        elif date_range == '90d':
            start_date = (timezone.now() - datetime.timedelta(days=90)).date()
            end_date = timezone.now().date()
        elif date_range == '1y':
            start_date = (timezone.now() - datetime.timedelta(days=365)).date()
            end_date = timezone.now().date()
        else:
            start_date = (timezone.now() - datetime.timedelta(days=90)).date()
            end_date = timezone.now().date()
        
        # Gather data based on selected sources
        report_data = {}
        
        if 'meetings' in data_sources:
            from apps.meetings.models import Meeting, MeetingAttendance
            meetings = Meeting.objects.filter(scheduled_date__range=(start_date, end_date))
            report_data['meetings'] = {
                'total': meetings.count(),
                'completed': meetings.filter(status='completed').count(),
                'attendance_rate': MeetingAttendance.objects.filter(
                    meeting__scheduled_date__range=(start_date, end_date)
                ).aggregate(
                    attended=Count('id', filter=Q(status='attended')),
                    total=Count('id')
                )
            }
        
        if 'voting' in data_sources:
            from apps.voting.models import Motion, Vote
            motions = Motion.objects.filter(created_at__range=(start_date, end_date))
            report_data['voting'] = {
                'total_motions': motions.count(),
                'passed': motions.filter(status='passed').count(),
                'failed': motions.filter(status='failed').count(),
                'total_votes': Vote.objects.filter(created_at__range=(start_date, end_date)).count()
            }
        
        if 'documents' in data_sources:
            from apps.documents.models import Document
            documents = Document.objects.filter(created_at__range=(start_date, end_date))
            report_data['documents'] = {
                'total': documents.count(),
                'published': documents.filter(status='published').count(),
                'draft': documents.filter(status='draft').count()
            }
        
        if 'compliance' in data_sources:
            from apps.risk.models import ComplianceRequirement
            requirements = ComplianceRequirement.objects.all()
            report_data['compliance'] = {
                'total': requirements.count(),
                'compliant': requirements.filter(status='compliant').count(),
                'non_compliant': requirements.filter(status='non_compliant').count(),
                'avg_score': requirements.aggregate(avg=Avg('compliance_score'))['avg'] or 0
            }
        
        # Create report record
        report = AnalyticsReport.objects.create(
            title=f"Custom Report - {report_type}",
            report_type='custom',
            format=export_format,
            start_date=start_date,
            end_date=end_date,
            generated_by=user,
            status='completed',
            generated_at=timezone.now()
        )
        
        # For now, just redirect to reports list with success message
        # In production, this would generate the actual report file
        messages.success(request, f"Custom report '{report.title}' generated successfully.")
        return redirect('analytics:reports')
    
    context = {
        'data_sources': [
            ('meetings', 'Meeting Data'),
            ('voting', 'Voting Records'),
            ('documents', 'Document Statistics'),
            ('compliance', 'Compliance Status'),
            ('attendance', 'Attendance Records'),
            ('risks', 'Risk Assessments'),
        ],
    }
    
    return render(request, 'analytics/custom_report_builder.html', context)


# Compliance Scorecard Views
class ComplianceScorecardListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List all compliance scorecards"""
    model = ComplianceScorecard
    template_name = 'analytics/compliance_scorecards.html'
    context_object_name = 'scorecards'
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("reviewed_by")
        user = self.request.user

        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset)

        # Role-based filtering within branch context
        if user.role == "it_administrator":
            pass  # See all scorecards
        elif user.role in ['company_secretary', 'compliance_officer']:
            pass  # See all scorecards in their branches
        else:
            queryset = queryset.filter(is_public=True)
        return queryset


class ComplianceScorecardDetailView(LoginRequiredMixin, DetailView):
    """View compliance scorecard details"""
    model = ComplianceScorecard
    template_name = 'analytics/compliance_scorecard_detail.html'
    context_object_name = 'scorecard'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scorecard = self.object
        context['criteria'] = scorecard.criteria.all()
        context['can_edit'] = self.request.user.role in ['it_administrator', 'company_secretary', 'compliance_officer']
        return context


class ComplianceScorecardCreateView(LoginRequiredMixin, CreateView):
    """Create a new compliance scorecard"""
    model = ComplianceScorecard
    template_name = 'analytics/compliance_scorecard_form.html'
    fields = ['name', 'description', 'assessment_period', 'branch', 'is_public']
    success_url = reverse_lazy('analytics:compliance_scorecards')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Compliance scorecard created successfully.')
        return super().form_valid(form)


# Attendance Analytics Views
class AttendanceAnalyticsListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List attendance analytics records"""
    model = AttendanceAnalytics
    template_name = 'analytics/attendance_analytics.html'
    context_object_name = 'analytics'
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user", "meeting", "meeting__branch")
        user = self.request.user

        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset, branch_field='meeting__branch')

        # Role-based filtering within branch context
        if user.role != "it_administrator":
            # Non-IT admins see only their own attendance records
            queryset = queryset.filter(user=user)

        meeting_id = self.request.GET.get('meeting')
        user_id = self.request.GET.get('user')

        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset


class AttendanceAnalyticsDetailView(LoginRequiredMixin, DetailView):
    """View attendance analytics details"""
    model = AttendanceAnalytics
    template_name = 'analytics/attendance_analytics_detail.html'
    context_object_name = 'analytics'


# Decision Tracking Views
class DecisionTrackingListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List decision tracking records"""
    model = DecisionTracking
    template_name = 'analytics/decision_tracking.html'
    context_object_name = 'decisions'
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("motion", "motion__meeting", "motion__meeting__branch")
        user = self.request.user

        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset, branch_field='motion__meeting__branch')

        # Role-based filtering within branch context
        if user.role != "it_administrator":
            # Non-IT admins see only decisions from their meetings
            queryset = queryset.filter(motion__meeting__attendees=user)

        status = self.request.GET.get('status')
        category = self.request.GET.get('category')

        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)
        return queryset


class DecisionTrackingDetailView(LoginRequiredMixin, DetailView):
    """View decision tracking details"""
    model = DecisionTracking
    template_name = 'analytics/decision_tracking_detail.html'
    context_object_name = 'decision'


class DecisionTrackingCreateView(LoginRequiredMixin, CreateView):
    """Create a new decision tracking record"""
    model = DecisionTracking
    template_name = 'analytics/decision_tracking_form.html'
    fields = ['motion', 'decision', 'category', 'priority', 'impact_level', 'estimated_completion_date']
    success_url = reverse_lazy('analytics:decision_tracking')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Decision tracking record created successfully.')
        return super().form_valid(form)


class DecisionTrackingUpdateView(LoginRequiredMixin, UpdateView):
    """Update decision tracking record"""
    model = DecisionTracking
    template_name = 'analytics/decision_tracking_form.html'
    fields = ['status', 'progress_percentage', 'actual_completion_date', 'notes', 'outcome']
    success_url = reverse_lazy('analytics:decision_tracking')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Decision tracking record updated successfully.')
        return super().form_valid(form)


# Custom Report Views
class CustomReportListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List all custom reports"""
    model = CustomReport
    template_name = 'analytics/custom_reports.html'
    context_object_name = 'reports'
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("created_by")
        user = self.request.user

        # Organization and branch filtering
        # Custom reports are created by users, filter by created_by's branch
        branch_ids = self.get_user_branch_ids()
        if branch_ids:
            queryset = queryset.filter(
                Q(created_by__userbranchmembership__branch_id__in=branch_ids) |
                Q(is_public=True)
            ).distinct()
        elif user.role != "it_administrator":
            queryset = queryset.filter(is_public=True)
        return queryset


class CustomReportDetailView(LoginRequiredMixin, DetailView):
    """View custom report details"""
    model = CustomReport
    template_name = 'analytics/custom_report_detail.html'
    context_object_name = 'report'


class CustomReportCreateView(LoginRequiredMixin, CreateView):
    """Create a new custom report"""
    model = CustomReport
    template_name = 'analytics/custom_report_form.html'
    fields = ['title', 'description', 'report_type', 'data_sources', 'filters', 'groupings', 'calculations']
    success_url = reverse_lazy('analytics:custom_reports')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Custom report created successfully.')
        return super().form_valid(form)


# ============================================================================
# Enhanced Analytics Dashboard Views
# ============================================================================

class GovernanceDashboardListView(LoginRequiredMixin, ListView):
    """List all governance dashboards"""
    model = AnalyticsDashboard
    template_name = 'analytics/governance_dashboard_list.html'
    context_object_name = 'dashboards'
    ordering = ['-is_default', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        dashboard_type = self.request.GET.get('dashboard_type')
        if dashboard_type:
            queryset = queryset.filter(dashboard_type=dashboard_type)
        return queryset


class GovernanceDashboardDetailView(LoginRequiredMixin, DetailView):
    """View governance dashboard details with widgets"""
    model = AnalyticsDashboard
    template_name = 'analytics/governance_dashboard_detail.html'
    context_object_name = 'dashboard'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['widgets'] = self.object.widgets.filter(is_visible=True).order_by('-is_pinned', 'order')
        return context


class GovernanceDashboardCreateView(LoginRequiredMixin, CreateView):
    """Create a new governance dashboard"""
    model = AnalyticsDashboard
    template_name = 'analytics/governance_dashboard_form.html'
    fields = ['name', 'description', 'dashboard_type', 'is_public', 'auto_refresh_interval', 
              'allowed_roles']
    success_url = reverse_lazy('analytics:governance_dashboards')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Governance dashboard created successfully.')
        return super().form_valid(form)


class GovernanceDashboardUpdateView(LoginRequiredMixin, UpdateView):
    """Update a governance dashboard"""
    model = AnalyticsDashboard
    template_name = 'analytics/governance_dashboard_form.html'
    fields = ['name', 'description', 'is_public', 'auto_refresh_interval', 'allowed_roles']
    success_url = reverse_lazy('analytics:governance_dashboards')
    
    def form_valid(self, form):
        messages.success(self.request, 'Governance dashboard updated successfully.')
        return super().form_valid(form)


# ============================================================================
# Analytics Widget Views
# ============================================================================

class AnalyticsWidgetListView(LoginRequiredMixin, ListView):
    """List all analytics widgets"""
    model = AnalyticsWidget
    template_name = 'analytics/widget_list.html'
    context_object_name = 'widgets'
    ordering = ['dashboard', 'order']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related('dashboard', 'metric')
        dashboard_id = self.request.GET.get('dashboard')
        if dashboard_id:
            queryset = queryset.filter(dashboard_id=dashboard_id)
        return queryset


class AnalyticsWidgetCreateView(LoginRequiredMixin, CreateView):
    """Create a new analytics widget"""
    model = AnalyticsWidget
    template_name = 'analytics/widget_form.html'
    fields = ['dashboard', 'metric', 'widget_type', 'title', 'order', 'is_visible', 'is_pinned', 
              'show_insights', 'insight_config', 'visualization_settings']
    success_url = reverse_lazy('analytics:widgets')
    
    def form_valid(self, form):
        messages.success(self.request, 'Analytics widget created successfully.')
        return super().form_valid(form)


class AnalyticsWidgetUpdateView(LoginRequiredMixin, UpdateView):
    """Update an analytics widget"""
    model = AnalyticsWidget
    template_name = 'analytics/widget_form.html'
    fields = ['title', 'order', 'is_visible', 'is_pinned', 'show_insights', 'insight_config', 'visualization_settings']
    success_url = reverse_lazy('analytics:widgets')
    
    def form_valid(self, form):
        messages.success(self.request, 'Analytics widget updated successfully.')
        return super().form_valid(form)


class CustomReportGenerateView(LoginRequiredMixin, DetailView):
    """Generate and export custom report"""
    model = CustomReport
    template_name = 'analytics/custom_report_generate.html'
    context_object_name = 'report'
