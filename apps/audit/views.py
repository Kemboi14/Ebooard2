from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.generic import ListView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
import csv
import json
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date

from .models import AuditLog, AuditLogExport, AuditLogRetention
from apps.accounts.permissions import VIEW_AUDIT

class AuditLogListView(LoginRequiredMixin, ListView):
    """List and filter audit logs"""
    model = AuditLog
    template_name = 'audit/audit_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50

    def get_queryset(self):
        queryset = AuditLog.objects.select_related('user', 'content_type').order_by('-timestamp')
        
        # Apply filters
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        module = self.request.GET.get('module')
        if module:
            queryset = queryset.filter(module=module)
        
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            try:
                date_from = parse_date(date_from)
                if date_from:
                    queryset = queryset.filter(timestamp__date__gte=date_from)
            except ValueError:
                pass
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            try:
                date_to = parse_date(date_to)
                if date_to:
                    queryset = queryset.filter(timestamp__date__lte=date_to)
            except ValueError:
                pass
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(details__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        success = self.request.GET.get('success')
        if success:
            queryset = queryset.filter(success=success == 'true')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter options
        context['action_choices'] = AuditLog.ACTION_TYPES
        context['module_choices'] = AuditLog.MODULES
        context['severity_choices'] = AuditLog.SEVERITY_LEVELS
        
        # Current filters for form
        context['current_filters'] = {
            'user': self.request.GET.get('user', ''),
            'action': self.request.GET.get('action', ''),
            'module': self.request.GET.get('module', ''),
            'severity': self.request.GET.get('severity', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'search': self.request.GET.get('search', ''),
            'success': self.request.GET.get('success', ''),
        }
        
        # Statistics
        queryset = self.get_queryset()
        context['total_logs'] = queryset.count()
        context['failed_logs'] = queryset.filter(success=False).count()
        context['high_severity_logs'] = queryset.filter(severity__in=['high', 'critical']).count()
        
        # Recent activity
        context['recent_logs'] = queryset[:10]
        
        return context

class AuditLogDetailView(LoginRequiredMixin, DetailView):
    """View detailed audit log entry"""
    model = AuditLog
    template_name = 'audit/audit_detail.html'
    context_object_name = 'audit_log'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit_log = self.object
        
        # Related logs (same user, same object, or similar action)
        related_logs = AuditLog.objects.filter(
            Q(user=audit_log.user) |
            Q(content_type=audit_log.content_type, object_id=audit_log.object_id) |
            Q(action=audit_log.action, module=audit_log.module)
        ).exclude(pk=audit_log.pk).order_by('-timestamp')[:10]
        
        context['related_logs'] = related_logs
        return context

@login_required
def export_audit_logs(request):
    """Export audit logs to various formats"""
    if not VIEW_AUDIT:
        messages.error(request, "You don't have permission to export audit logs.")
        return redirect('audit:audit_list')
    
    format_type = request.GET.get('format', 'csv')
    
    # Get filtered queryset
    queryset = AuditLog.objects.all().order_by('-timestamp')
    
    # Apply same filters as list view
    user_id = request.GET.get('user')
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    
    action = request.GET.get('action')
    if action:
        queryset = queryset.filter(action=action)
    
    module = request.GET.get('module')
    if module:
        queryset = queryset.filter(module=module)
    
    severity = request.GET.get('severity')
    if severity:
        queryset = queryset.filter(severity=severity)
    
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            date_from = parse_date(date_from)
            if date_from:
                queryset = queryset.filter(timestamp__date__gte=date_from)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            date_to = parse_date(date_to)
            if date_to:
                queryset = queryset.filter(timestamp__date__lte=date_to)
        except ValueError:
            pass
    
    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(description__icontains=search) |
            Q(details__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Create export record
    export_record = AuditLogExport.objects.create(
        user=request.user,
        format=format_type,
        filters=request.GET.dict(),
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    
    try:
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Timestamp', 'User', 'Action', 'Module', 'Severity', 
                'Description', 'Object Type', 'Object ID', 'IP Address', 
                'Success', 'Details'
            ])
            
            for log in queryset:
                writer.writerow([
                    log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    log.user.get_full_name() if log.user else 'System',
                    log.get_action_display(),
                    log.get_module_display(),
                    log.get_severity_display(),
                    log.description,
                    log.object_type,
                    log.object_id,
                    log.ip_address or '',
                    'Yes' if log.success else 'No',
                    log.details
                ])
            
            # Update export record
            export_record.status = 'completed'
            export_record.completed_at = timezone.now()
            export_record.record_count = queryset.count()
            export_record.save()
            
            return response
        
        elif format_type == 'json':
            response = HttpResponse(content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            
            logs_data = []
            for log in queryset:
                logs_data.append({
                    'timestamp': log.timestamp.isoformat(),
                    'user': log.user.get_full_name() if log.user else 'System',
                    'action': log.get_action_display(),
                    'module': log.get_module_display(),
                    'severity': log.get_severity_display(),
                    'description': log.description,
                    'object_type': log.object_type,
                    'object_id': log.object_id,
                    'ip_address': log.ip_address,
                    'success': log.success,
                    'details': log.details,
                    'old_values': log.old_values,
                    'new_values': log.new_values,
                })
            
            response.write(json.dumps(logs_data, indent=2))
            
            # Update export record
            export_record.status = 'completed'
            export_record.completed_at = timezone.now()
            export_record.record_count = queryset.count()
            export_record.save()
            
            return response
        
        else:
            messages.error(request, "Export format not supported.")
            return redirect('audit:audit_list')
    
    except Exception as e:
        export_record.status = 'failed'
        export_record.error_message = str(e)
        export_record.save()
        
        messages.error(request, f"Export failed: {str(e)}")
        return redirect('audit:audit_list')

@login_required
def audit_dashboard(request):
    """Audit trail dashboard with statistics"""
    if not VIEW_AUDIT:
        messages.error(request, "You don't have permission to view audit logs.")
        return redirect('dashboard:dashboard')
    
    # Time-based statistics
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    context = {
        'total_logs': AuditLog.objects.count(),
        'logs_last_24h': AuditLog.objects.filter(timestamp__gte=last_24h).count(),
        'logs_last_7d': AuditLog.objects.filter(timestamp__gte=last_7d).count(),
        'logs_last_30d': AuditLog.objects.filter(timestamp__gte=last_30d).count(),
        
        'failed_logs': AuditLog.objects.filter(success=False).count(),
        'failed_logs_last_24h': AuditLog.objects.filter(
            success=False, timestamp__gte=last_24h
        ).count(),
        
        'high_severity_logs': AuditLog.objects.filter(
            severity__in=['high', 'critical']
        ).count(),
        'critical_logs_last_24h': AuditLog.objects.filter(
            severity='critical', timestamp__gte=last_24h
        ).count(),
        
        'unique_users': AuditLog.objects.filter(
            user__isnull=False
        ).values('user').distinct().count(),
        
        'top_modules': AuditLog.objects.values('module').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10],
        
        'top_actions': AuditLog.objects.values('action').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10],
        
        'recent_logs': AuditLog.objects.select_related('user').order_by('-timestamp')[:20],
        
        'recent_exports': AuditLogExport.objects.select_related('user').order_by('-requested_at')[:10],
    }
    
    return render(request, 'audit/audit_dashboard.html', context)

@login_required
def cleanup_old_logs(request):
    """Clean up old audit logs based on retention policies"""
    if not VIEW_AUDIT:
        messages.error(request, "You don't have permission to manage audit logs.")
        return redirect('audit:audit_list')
    
    if request.method == 'POST':
        days = int(request.POST.get('days', 365))
        module = request.POST.get('module', 'all')
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = AuditLog.objects.filter(timestamp__lt=cutoff_date)
        if module != 'all':
            queryset = queryset.filter(module=module)
        
        deleted_count = queryset.count()
        queryset.delete()
        
        messages.success(request, f"Deleted {deleted_count} old audit logs.")
        return redirect('audit:audit_list')
    
    return render(request, 'audit/cleanup_confirm.html')

@staff_member_required
def retention_policies(request):
    """Manage audit log retention policies"""
    policies = AuditLogRetention.objects.all()
    
    if request.method == 'POST':
        # Create or update policies
        for module, _ in AuditLogRetention.MODULE_CHOICES:
            retention_days = request.POST.get(f'retention_{module}')
            if retention_days:
                try:
                    retention_days = int(retention_days)
                    policy, created = AuditLogRetention.objects.update_or_create(
                        module=module,
                        defaults={'retention_days': retention_days}
                    )
                except ValueError:
                    pass
        
        messages.success(request, "Retention policies updated.")
        return redirect('audit:retention_policies')
    
    return render(request, 'audit/retention_policies.html', {'policies': policies})
