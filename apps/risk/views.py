from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.http import JsonResponse

from .models import Risk, RiskCategory, RiskAssessment, RiskMitigation, RiskMonitoring, RiskIncident
from .forms import (
    RiskForm, RiskCategoryForm, RiskAssessmentForm, RiskMitigationForm,
    RiskMonitoringForm, RiskIncidentForm, RiskSearchForm
)
from apps.accounts.decorators import role_required
from apps.accounts.permissions import MANAGE_RISK

class RiskListView(LoginRequiredMixin, ListView):
    """List view for risks with role-based filtering and search"""
    model = Risk
    template_name = 'risk/risk_list.html'
    context_object_name = 'risks'
    paginate_by = 15
    
    def get_queryset(self):
        """Filter risks based on user role and permissions"""
        user = self.request.user
        queryset = Risk.objects.all()
        
        # Role-based filtering
        if user.role == 'it_administrator':
            return queryset
        elif user.role == 'compliance_officer':
            return queryset  # Compliance officers see all risks
        elif user.role == 'executive_management':
            return queryset.filter(
                Q(status__in=['identified', 'assessed', 'mitigated', 'monitored']) |
                Q(risk_owner=user) |
                Q(assigned_to=user)
            )
        else:
            # Other users see risks they're assigned to or own
            return queryset.filter(
                Q(risk_owner=user) |
                Q(assigned_to=user) |
                Q(status__in=['identified', 'assessed'])  # Public risks
            )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = RiskSearchForm(self.request.GET or None)
        context['can_manage'] = self.request.user.role in MANAGE_RISK
        context['risk_stats'] = self.get_risk_statistics()
        return context
    
    def get_risk_statistics(self):
        """Get risk statistics for dashboard"""
        queryset = self.get_queryset()
        return {
            'total_risks': queryset.count(),
            'critical_risks': queryset.filter(risk_score__gte=20).count(),
            'high_risks': queryset.filter(risk_score__gte=15, risk_score__lt=20).count(),
            'open_risks': queryset.exclude(status__in=['closed']).count(),
            'overdue_risks': queryset.filter(
                target_resolution_date__lt=timezone.now().date(),
                status__in=['identified', 'assessed', 'mitigated']
            ).count(),
        }

class RiskDetailView(LoginRequiredMixin, DetailView):
    """Detail view for individual risks"""
    model = Risk
    template_name = 'risk/risk_detail.html'
    context_object_name = 'risk'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        risk = self.get_object()
        user = self.request.user
        
        context['can_manage'] = user.role in MANAGE_RISK
        context['can_edit'] = self.can_edit_risk(user, risk)
        context['assessments'] = risk.assessments.all().order_by('-assessment_date')
        context['mitigations'] = risk.mitigations.all().order_by('-created_at')
        context['monitoring_records'] = risk.monitoring_records.all().order_by('-monitoring_date')
        context['incidents'] = risk.incidents.all().order_by('-incident_date')
        
        # Assessment form
        if context['can_manage']:
            context['assessment_form'] = RiskAssessmentForm()
        
        # Mitigation form
        if context['can_manage']:
            context['mitigation_form'] = RiskMitigationForm()
        
        # Monitoring form
        if context['can_manage']:
            context['monitoring_form'] = RiskMonitoringForm(initial={'new_risk_score': risk.risk_score})
        
        # Incident form
        context['incident_form'] = RiskIncidentForm()
        
        return context
    
    def can_edit_risk(self, user, risk):
        """Check if user can edit this risk"""
        if user.role in MANAGE_RISK:
            return True
        return risk.risk_owner == user or risk.assigned_to == user

class CreateRiskView(LoginRequiredMixin, CreateView):
    """Create view for new risks"""
    model = Risk
    form_class = RiskForm
    template_name = 'risk/create_risk.html'
    success_url = reverse_lazy('risk:risk_list')
    
    def form_valid(self, form):
        """Set identified_by and create activity"""
        form.instance.identified_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Risk created successfully!')
        return response

@role_required('compliance_officer', 'executive_management', 'it_administrator')
def manage_categories(request):
    """Manage risk categories"""
    categories = RiskCategory.objects.all()
    
    if request.method == 'POST':
        form = RiskCategoryForm(request.POST)
        if form.is_valid():
            form.instance.created_by = request.user
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('risk:manage_categories')
    else:
        form = RiskCategoryForm()
    
    return render(request, 'risk/manage_categories.html', {
        'categories': categories,
        'form': form,
    })

@login_required
def create_assessment(request, pk):
    """Create risk assessment"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user
    
    if user.role not in MANAGE_RISK:
        messages.error(request, 'You do not have permission to create assessments.')
        return redirect('risk:risk_detail', pk=pk)
    
    if request.method == 'POST':
        form = RiskAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.risk = risk
            assessment.assessed_by = user
            assessment.save()
            
            # Update risk status
            risk.status = 'assessed'
            risk.save()
            
            messages.success(request, 'Assessment created successfully!')
            return redirect('risk:risk_detail', pk=pk)
    else:
        form = RiskAssessmentForm()
    
    return render(request, 'risk/create_assessment.html', {
        'risk': risk,
        'form': form,
    })

@login_required
def create_mitigation(request, pk):
    """Create risk mitigation plan"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user
    
    if user.role not in MANAGE_RISK:
        messages.error(request, 'You do not have permission to create mitigation plans.')
        return redirect('risk:risk_detail', pk=pk)
    
    if request.method == 'POST':
        form = RiskMitigationForm(request.POST)
        if form.is_valid():
            mitigation = form.save(commit=False)
            mitigation.risk = risk
            mitigation.created_by = user
            mitigation.save()
            
            # Update risk status
            risk.status = 'mitigated'
            risk.save()
            
            messages.success(request, 'Mitigation plan created successfully!')
            return redirect('risk:risk_detail', pk=pk)
    else:
        form = RiskMitigationForm()
    
    return render(request, 'risk/create_mitigation.html', {
        'risk': risk,
        'form': form,
    })

@login_required
def create_monitoring(request, pk):
    """Create risk monitoring record"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user
    
    if user.role not in MANAGE_RISK:
        messages.error(request, 'You do not have permission to create monitoring records.')
        return redirect('risk:risk_detail', pk=pk)
    
    if request.method == 'POST':
        form = RiskMonitoringForm(request.POST)
        if form.is_valid():
            monitoring = form.save(commit=False)
            monitoring.risk = risk
            monitoring.monitored_by = user
            monitoring.save()
            
            # Update risk score if changed
            if monitoring.new_risk_score != risk.risk_score:
                risk.risk_score = monitoring.new_risk_score
                risk.save()
            
            # Update risk status
            risk.status = 'monitored'
            risk.save()
            
            messages.success(request, 'Monitoring record created successfully!')
            return redirect('risk:risk_detail', pk=pk)
    else:
        form = RiskMonitoringForm(initial={'new_risk_score': risk.risk_score})
    
    return render(request, 'risk/create_monitoring.html', {
        'risk': risk,
        'form': form,
    })

@login_required
def report_incident(request, pk):
    """Report risk incident"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user
    
    if request.method == 'POST':
        form = RiskIncidentForm(request.POST)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.risk = risk
            incident.reported_by = user
            incident.save()
            
            # Update risk status if incident is critical
            if incident.severity == 'critical':
                risk.status = 'escalated'
                risk.save()
            
            messages.success(request, 'Incident reported successfully!')
            return redirect('risk:risk_detail', pk=pk)
    else:
        form = RiskIncidentForm()
    
    return render(request, 'risk/report_incident.html', {
        'risk': risk,
        'form': form,
    })

@login_required
def risk_search(request):
    """Search risks based on form criteria"""
    form = RiskSearchForm(request.GET)
    risks = Risk.objects.all()
    
    # Apply role-based filtering
    user = request.user
    if user.role == 'it_administrator':
        pass  # See all
    elif user.role == 'compliance_officer':
        pass  # See all
    elif user.role == 'executive_management':
        risks = risks.filter(
            Q(status__in=['identified', 'assessed', 'mitigated', 'monitored']) |
            Q(risk_owner=user) |
            Q(assigned_to=user)
        )
    else:
        risks = risks.filter(
            Q(risk_owner=user) |
            Q(assigned_to=user) |
            Q(status__in=['identified', 'assessed'])
        )
    
    if form.is_valid():
        query = form.cleaned_data.get('query', '')
        search_type = form.cleaned_data.get('search_type', 'all')
        category = form.cleaned_data.get('category')
        status = form.cleaned_data.get('status')
        risk_level = form.cleaned_data.get('risk_level')
        risk_owner = form.cleaned_data.get('risk_owner')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        
        if query:
            if search_type == 'title':
                risks = risks.filter(title__icontains=query)
            elif search_type == 'description':
                risks = risks.filter(description__icontains=query)
            else:  # all fields
                risks = risks.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )
        
        if category:
            risks = risks.filter(category=category)
        if status:
            risks = risks.filter(status=status)
        if risk_level:
            if risk_level == 'critical':
                risks = risks.filter(risk_score__gte=20)
            elif risk_level == 'high':
                risks = risks.filter(risk_score__gte=15, risk_score__lt=20)
            elif risk_level == 'medium':
                risks = risks.filter(risk_score__gte=10, risk_score__lt=15)
            elif risk_level == 'low':
                risks = risks.filter(risk_score__gte=5, risk_score__lt=10)
            elif risk_level == 'very_low':
                risks = risks.filter(risk_score__lt=5)
        if risk_owner:
            risks = risks.filter(risk_owner=risk_owner)
        if date_from:
            risks = risks.filter(created_at__date__gte=date_from)
        if date_to:
            risks = risks.filter(created_at__date__lte=date_to)
    
    return render(request, 'risk/risk_list.html', {
        'risks': risks,
        'search_form': form,
        'can_manage': request.user.role in MANAGE_RISK,
    })

@login_required
def risk_dashboard(request):
    """Risk management dashboard with statistics and charts"""
    user = request.user
    
    # Get risks based on user permissions
    if user.role in MANAGE_RISK:
        risks = Risk.objects.all()
    else:
        risks = Risk.objects.filter(
            Q(risk_owner=user) |
            Q(assigned_to=user) |
            Q(status__in=['identified', 'assessed'])
        )
    
    # Statistics
    stats = {
        'total_risks': risks.count(),
        'open_risks': risks.exclude(status__in=['closed']).count(),
        'critical_risks': risks.filter(risk_score__gte=20).count(),
        'high_risks': risks.filter(risk_score__gte=15, risk_score__lt=20).count(),
        'medium_risks': risks.filter(risk_score__gte=10, risk_score__lt=15).count(),
        'low_risks': risks.filter(risk_score__gte=5, risk_score__lt=10).count(),
        'very_low_risks': risks.filter(risk_score__lt=5).count(),
        'overdue_risks': risks.filter(
            target_resolution_date__lt=timezone.now().date(),
            status__in=['identified', 'assessed', 'mitigated']
        ).count(),
        'recent_incidents': RiskIncident.objects.filter(
            reported_date__gte=timezone.now() - timezone.timedelta(days=30)
        ).count(),
    }
    
    # Recent risks
    recent_risks = risks.order_by('-created_at')[:10]
    
    # High priority risks
    high_priority_risks = risks.filter(risk_score__gte=15).exclude(status='closed').order_by('-risk_score')[:10]
    
    # Recent incidents
    recent_incidents = RiskIncident.objects.select_related('risk').order_by('-incident_date')[:10]
    
    return render(request, 'risk/risk_dashboard.html', {
        'stats': stats,
        'recent_risks': recent_risks,
        'high_priority_risks': high_priority_risks,
        'recent_incidents': recent_incidents,
        'can_manage': user.role in MANAGE_RISK,
    })

@login_required
def risk_reports(request):
    """Risk reporting and analytics"""
    user = request.user
    
    if user.role not in MANAGE_RISK:
        messages.error(request, 'You do not have permission to view reports.')
        return redirect('risk:risk_list')
    
    # Risk distribution by category
    category_stats = RiskCategory.objects.annotate(
        risk_count=Count('risks'),
        avg_score=Avg('risks__risk_score')
    ).filter(risk_count__gt=0)
    
    # Risk status distribution
    status_stats = []
    for status_choice in Risk.STATUS_CHOICES:
        status_code, status_name = status_choice
        count = Risk.objects.filter(status=status_code).count()
        status_stats.append({
            'status': status_name,
            'count': count,
            'percentage': (count / Risk.objects.count() * 100) if Risk.objects.count() > 0 else 0
        })
    
    # Risk level distribution
    level_stats = {
        'Critical': Risk.objects.filter(risk_score__gte=20).count(),
        'High': Risk.objects.filter(risk_score__gte=15, risk_score__lt=20).count(),
        'Medium': Risk.objects.filter(risk_score__gte=10, risk_score__lt=15).count(),
        'Low': Risk.objects.filter(risk_score__gte=5, risk_score__lt=10).count(),
        'Very Low': Risk.objects.filter(risk_score__lt=5).count(),
    }
    
    # Monthly risk trends (last 12 months)
    from django.db.models.functions import TruncMonth
    monthly_trends = Risk.objects.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')[:12]
    
    return render(request, 'risk/risk_reports.html', {
        'category_stats': category_stats,
        'status_stats': status_stats,
        'level_stats': level_stats,
        'monthly_trends': monthly_trends,
    })
