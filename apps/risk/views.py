from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.decorators import role_required
from apps.accounts.permissions import MANAGE_RISK
from apps.accounts.mixins import BranchOrganizationFilterMixin

from .forms import (
    RiskAssessmentForm,
    RiskCategoryForm,
    RiskForm,
    RiskIncidentForm,
    RiskMitigationForm,
    RiskMonitoringForm,
    RiskSearchForm,
)
from .models import (
    Risk,
    RiskAssessment,
    RiskCategory,
    RiskIncident,
    RiskMitigation,
    RiskMonitoring,
    ConflictOfInterestDeclaration,
    WhistleblowerReport,
    ComplianceRequirement,
    ComplianceAudit,
    BoardEvaluation,
    DirectorEvaluation,
    ComplianceArchive,
    ComplianceAttendance,
)


class RiskListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List view for risks with role-based filtering and search"""

    model = Risk
    template_name = "risk/risk_list.html"
    context_object_name = "risks"
    paginate_by = 15

    def get_queryset(self):
        """Filter risks based on user role and permissions"""
        user = self.request.user
        queryset = Risk.objects.select_related("risk_owner", "assigned_to", "category", "identified_by")

        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset)

        # Role-based filtering within branch context
        if user.role == "it_administrator":
            return queryset
        elif user.role == "compliance_officer":
            return queryset  # Compliance officers see all risks in their branches
        elif user.role == "executive_management":
            return queryset.filter(
                Q(status__in=["identified", "assessed", "mitigated", "monitored"])
                | Q(risk_owner=user)
                | Q(assigned_to=user)
            )
        else:
            # Other users see risks they're assigned to or own
            return queryset.filter(
                Q(risk_owner=user)
                | Q(assigned_to=user)
                | Q(status__in=["identified", "assessed"])  # Public risks
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = RiskSearchForm(self.request.GET or None)
        context["can_manage"] = self.request.user.role in MANAGE_RISK
        context["risk_stats"] = self.get_risk_statistics()
        return context

    def get_risk_statistics(self):
        """Get risk statistics for dashboard"""
        queryset = self.get_queryset()
        return {
            "total_risks": queryset.count(),
            "critical_risks": queryset.filter(risk_score__gte=20).count(),
            "high_risks": queryset.filter(
                risk_score__gte=15, risk_score__lt=20
            ).count(),
            "open_risks": queryset.exclude(status__in=["closed"]).count(),
            "overdue_risks": queryset.filter(
                target_resolution_date__lt=timezone.now().date(),
                status__in=["identified", "assessed", "mitigated"],
            ).count(),
        }


class RiskDetailView(LoginRequiredMixin, DetailView):
    """Detail view for individual risks"""

    model = Risk
    template_name = "risk/risk_detail.html"
    context_object_name = "risk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        risk = self.get_object()
        user = self.request.user

        context["can_manage"] = user.role in MANAGE_RISK
        context["can_edit"] = self.can_edit_risk(user, risk)
        context["assessments"] = risk.assessments.all().order_by("-assessment_date")
        context["mitigations"] = risk.mitigations.all().order_by("-created_at")
        context["monitoring_records"] = risk.monitoring_records.all().order_by(
            "-monitoring_date"
        )
        context["incidents"] = risk.incidents.all().order_by("-incident_date")

        # Assessment form
        if context["can_manage"]:
            context["assessment_form"] = RiskAssessmentForm()

        # Mitigation form
        if context["can_manage"]:
            context["mitigation_form"] = RiskMitigationForm()

        # Monitoring form
        if context["can_manage"]:
            context["monitoring_form"] = RiskMonitoringForm(
                initial={"new_risk_score": risk.risk_score}
            )

        # Incident form
        context["incident_form"] = RiskIncidentForm()

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
    template_name = "risk/create_risk.html"
    success_url = reverse_lazy("risk:risk_list")

    def form_valid(self, form):
        """Set identified_by and create activity"""
        form.instance.identified_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Risk created successfully!")
        return response


class UpdateRiskView(LoginRequiredMixin, UpdateView):
    """Update view for existing risks"""

    model = Risk
    form_class = RiskForm
    template_name = "risk/create_risk.html"
    success_url = reverse_lazy("risk:risk_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Update Risk: {self.object.title}"
        context["is_update"] = True
        return context

    def form_valid(self, form):
        """Update risk and recalculate score"""
        form.save()
        messages.success(self.request, "Risk updated successfully!")
        return super().form_valid(form)


@role_required("compliance_officer", "executive_management", "it_administrator")
def manage_categories(request):
    """Manage risk categories"""
    categories = RiskCategory.objects.all()

    if request.method == "POST":
        form = RiskCategoryForm(request.POST)
        if form.is_valid():
            form.instance.created_by = request.user
            form.save()
            messages.success(request, "Category created successfully!")
            return redirect("risk:manage_categories")
    else:
        form = RiskCategoryForm()

    return render(
        request,
        "risk/manage_categories.html",
        {
            "categories": categories,
            "form": form,
        },
    )


@login_required
def create_assessment(request, pk):
    """Create risk assessment"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user

    if user.role not in MANAGE_RISK:
        messages.error(request, "You do not have permission to create assessments.")
        return redirect("risk:risk_detail", pk=pk)

    if request.method == "POST":
        form = RiskAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.risk = risk
            assessment.assessed_by = user
            assessment.save()

            # Update risk status
            risk.status = "assessed"
            risk.save()

            messages.success(request, "Assessment created successfully!")
            return redirect("risk:risk_detail", pk=pk)
    else:
        form = RiskAssessmentForm()

    return render(
        request,
        "risk/create_assessment.html",
        {
            "risk": risk,
            "form": form,
        },
    )


@login_required
def create_mitigation(request, pk):
    """Create risk mitigation plan"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user

    if user.role not in MANAGE_RISK:
        messages.error(
            request, "You do not have permission to create mitigation plans."
        )
        return redirect("risk:risk_detail", pk=pk)

    if request.method == "POST":
        form = RiskMitigationForm(request.POST)
        if form.is_valid():
            mitigation = form.save(commit=False)
            mitigation.risk = risk
            mitigation.created_by = user
            mitigation.save()

            # Update risk status
            risk.status = "mitigated"
            risk.save()

            messages.success(request, "Mitigation plan created successfully!")
            return redirect("risk:risk_detail", pk=pk)
    else:
        form = RiskMitigationForm()

    return render(
        request,
        "risk/create_mitigation.html",
        {
            "risk": risk,
            "form": form,
        },
    )


@login_required
def create_monitoring(request, pk):
    """Create risk monitoring record"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user

    if user.role not in MANAGE_RISK:
        messages.error(
            request, "You do not have permission to create monitoring records."
        )
        return redirect("risk:risk_detail", pk=pk)

    if request.method == "POST":
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
            risk.status = "monitored"
            risk.save()

            messages.success(request, "Monitoring record created successfully!")
            return redirect("risk:risk_detail", pk=pk)
    else:
        form = RiskMonitoringForm(initial={"new_risk_score": risk.risk_score})

    return render(
        request,
        "risk/create_monitoring.html",
        {
            "risk": risk,
            "form": form,
        },
    )


@login_required
def report_incident(request, pk):
    """Report risk incident"""
    risk = get_object_or_404(Risk, pk=pk)
    user = request.user

    if request.method == "POST":
        form = RiskIncidentForm(request.POST)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.risk = risk
            incident.reported_by = user
            incident.save()

            # Update risk status if incident is critical
            if incident.severity == "critical":
                risk.status = "escalated"
                risk.save()

            messages.success(request, "Incident reported successfully!")
            return redirect("risk:risk_detail", pk=pk)
    else:
        form = RiskIncidentForm()

    return render(
        request,
        "risk/report_incident.html",
        {
            "risk": risk,
            "form": form,
        },
    )


@login_required
def risk_search(request):
    """Search risks based on form criteria"""
    form = RiskSearchForm(request.GET)
    risks = Risk.objects.all()

    # Apply role-based filtering
    user = request.user
    if user.role == "it_administrator":
        pass  # See all
    elif user.role == "compliance_officer":
        pass  # See all
    elif user.role == "executive_management":
        risks = risks.filter(
            Q(status__in=["identified", "assessed", "mitigated", "monitored"])
            | Q(risk_owner=user)
            | Q(assigned_to=user)
        )
    else:
        risks = risks.filter(
            Q(risk_owner=user)
            | Q(assigned_to=user)
            | Q(status__in=["identified", "assessed"])
        )

    if form.is_valid():
        query = form.cleaned_data.get("query", "")
        search_type = form.cleaned_data.get("search_type", "all")
        category = form.cleaned_data.get("category")
        status = form.cleaned_data.get("status")
        risk_level = form.cleaned_data.get("risk_level")
        risk_owner = form.cleaned_data.get("risk_owner")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")

        if query:
            if search_type == "title":
                risks = risks.filter(title__icontains=query)
            elif search_type == "description":
                risks = risks.filter(description__icontains=query)
            else:  # all fields
                risks = risks.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                )

        if category:
            risks = risks.filter(category=category)
        if status:
            risks = risks.filter(status=status)
        if risk_level:
            if risk_level == "critical":
                risks = risks.filter(risk_score__gte=20)
            elif risk_level == "high":
                risks = risks.filter(risk_score__gte=15, risk_score__lt=20)
            elif risk_level == "medium":
                risks = risks.filter(risk_score__gte=10, risk_score__lt=15)
            elif risk_level == "low":
                risks = risks.filter(risk_score__gte=5, risk_score__lt=10)
            elif risk_level == "very_low":
                risks = risks.filter(risk_score__lt=5)
        if risk_owner:
            risks = risks.filter(risk_owner=risk_owner)
        if date_from:
            risks = risks.filter(created_at__date__gte=date_from)
        if date_to:
            risks = risks.filter(created_at__date__lte=date_to)

    return render(
        request,
        "risk/risk_list.html",
        {
            "risks": risks,
            "search_form": form,
            "can_manage": request.user.role in MANAGE_RISK,
        },
    )


@login_required
def risk_dashboard(request):
    """Risk management dashboard with statistics and charts"""
    user = request.user

    # Get risks based on user permissions
    if user.role in MANAGE_RISK:
        risks = Risk.objects.all()
    else:
        risks = Risk.objects.filter(
            Q(risk_owner=user)
            | Q(assigned_to=user)
            | Q(status__in=["identified", "assessed"])
        )

    # Statistics
    stats = {
        "total_risks": risks.count(),
        "open_risks": risks.exclude(status__in=["closed"]).count(),
        "critical_risks": risks.filter(risk_score__gte=20).count(),
        "high_risks": risks.filter(risk_score__gte=15, risk_score__lt=20).count(),
        "medium_risks": risks.filter(risk_score__gte=10, risk_score__lt=15).count(),
        "low_risks": risks.filter(risk_score__gte=5, risk_score__lt=10).count(),
        "very_low_risks": risks.filter(risk_score__lt=5).count(),
        "overdue_risks": risks.filter(
            target_resolution_date__lt=timezone.now().date(),
            status__in=["identified", "assessed", "mitigated"],
        ).count(),
        "recent_incidents": RiskIncident.objects.filter(
            reported_date__gte=timezone.now() - timezone.timedelta(days=30)
        ).count(),
    }

    # Recent risks
    recent_risks = risks.order_by("-created_at")[:10]

    # High priority risks
    high_priority_risks = (
        risks.filter(risk_score__gte=15)
        .exclude(status="closed")
        .order_by("-risk_score")[:10]
    )

    # Recent incidents
    recent_incidents = RiskIncident.objects.select_related("risk").order_by(
        "-incident_date"
    )[:10]

    return render(
        request,
        "risk/risk_dashboard.html",
        {
            "stats": stats,
            "recent_risks": recent_risks,
            "high_priority_risks": high_priority_risks,
            "recent_incidents": recent_incidents,
            "can_manage": user.role in MANAGE_RISK,
        },
    )


@login_required
def risk_reports(request):
    """Risk reporting and analytics"""
    user = request.user

    if user.role not in MANAGE_RISK:
        messages.error(request, "You do not have permission to view reports.")
        return redirect("risk:risk_list")

    # Risk distribution by category
    category_stats = RiskCategory.objects.annotate(
        risk_count=Count("risks"), avg_score=Avg("risks__risk_score")
    ).filter(risk_count__gt=0)

    # Risk status distribution
    status_stats = []
    for status_choice in Risk.STATUS_CHOICES:
        status_code, status_name = status_choice
        count = Risk.objects.filter(status=status_code).count()
        status_stats.append(
            {
                "status": status_name,
                "count": count,
                "percentage": (count / Risk.objects.count() * 100)
                if Risk.objects.count() > 0
                else 0,
            }
        )

    # Risk level distribution — keys use underscores so Django template dot-notation works
    level_stats = {
        "Critical": Risk.objects.filter(risk_score__gte=20).count(),
        "High": Risk.objects.filter(risk_score__gte=15, risk_score__lt=20).count(),
        "Medium": Risk.objects.filter(risk_score__gte=10, risk_score__lt=15).count(),
        "Low": Risk.objects.filter(risk_score__gte=5, risk_score__lt=10).count(),
        "Very_Low": Risk.objects.filter(risk_score__lt=5).count(),
    }

    # Monthly risk trends (last 12 months)
    from django.db.models.functions import TruncMonth

    monthly_trends = (
        Risk.objects.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")[:12]
    )

    return render(
        request,
        "risk/risk_reports.html",
        {
            "category_stats": category_stats,
            "status_stats": status_stats,
            "level_stats": level_stats,
            "monthly_trends": monthly_trends,
        },
    )


# ─── Conflict of Interest Views ─────────────────────────────────────────────────

class ConflictOfInterestListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List conflict of interest declarations"""
    model = ConflictOfInterestDeclaration
    template_name = 'risk/coi_declarations.html'
    context_object_name = 'declarations'
    ordering = ['-declared_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("declarant")
        user = self.request.user

        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset, branch_field='branch')

        if user.role not in MANAGE_RISK:
            queryset = queryset.filter(declarant=user)
        return queryset


class ConflictOfInterestDetailView(LoginRequiredMixin, DetailView):
    """View conflict of interest declaration details"""
    model = ConflictOfInterestDeclaration
    template_name = 'risk/coi_detail.html'
    context_object_name = 'declaration'


class ConflictOfInterestCreateView(LoginRequiredMixin, CreateView):
    """Create a conflict of interest declaration"""
    model = ConflictOfInterestDeclaration
    template_name = 'risk/coi_form.html'
    fields = ['title', 'description', 'conflict_type', 'related_entity', 'relationship_nature', 'severity', 'mitigation_plan']
    success_url = reverse_lazy('risk:coi_declarations')
    
    def form_valid(self, form):
        form.instance.declarant = self.request.user
        messages.success(self.request, 'Conflict of interest declaration submitted successfully.')
        return super().form_valid(form)


@login_required
@role_required('compliance_officer', 'executive_management', 'it_administrator')
def review_coi(request, pk):
    """Review a conflict of interest declaration"""
    coi = get_object_or_404(ConflictOfInterestDeclaration, pk=pk)
    
    if request.method == 'POST':
        coi.reviewed_by = request.user
        coi.reviewed_at = timezone.now()
        coi.review_notes = request.POST.get('review_notes')
        coi.status = request.POST.get('status', 'acknowledged')
        coi.save()
        
        messages.success(request, 'Conflict of interest reviewed successfully.')
        return redirect('risk:coi_detail', pk=pk)
    
    return render(request, 'risk/coi_review.html', {'declaration': coi})


# ─── Whistleblower Portal Views ───────────────────────────────────────────────

class WhistleblowerReportListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List whistleblower reports"""
    model = WhistleblowerReport
    template_name = 'risk/whistleblower_reports.html'
    context_object_name = 'reports'
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("assigned_to")
        user = self.request.user

        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset, branch_field='branch')

        if user.role not in MANAGE_RISK:
            queryset = queryset.filter(assigned_to=user)
        return queryset


class WhistleblowerReportDetailView(LoginRequiredMixin, DetailView):
    """View whistleblower report details"""
    model = WhistleblowerReport
    template_name = 'risk/whistleblower_detail.html'
    context_object_name = 'report'


@login_required
def create_whistleblower_report(request):
    """Create a whistleblower report (can be anonymous)"""
    if request.method == 'POST':
        # Create report
        report = WhistleblowerReport.objects.create(
            category=request.POST.get('category'),
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            is_anonymous=request.POST.get('is_anonymous') == 'on',
            reporter_email=request.POST.get('reporter_email', ''),
            reporter_phone=request.POST.get('reporter_phone', ''),
            incident_date=request.POST.get('incident_date') or None,
            location=request.POST.get('location', ''),
            individuals_involved=request.POST.get('individuals_involved', ''),
            severity=request.POST.get('severity', 'medium'),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        messages.success(request, 'Report submitted successfully. You will be contacted if follow-up is needed.')
        return redirect('dashboard')
    
    return render(request, 'risk/whistleblower_form.html')


@login_required
@role_required('compliance_officer', 'executive_management', 'it_administrator')
def investigate_whistleblower_report(request, pk):
    """Investigate a whistleblower report"""
    report = get_object_or_404(WhistleblowerReport, pk=pk)
    
    if request.method == 'POST':
        report.assigned_to = request.user
        report.investigation_notes = request.POST.get('investigation_notes')
        report.status = request.POST.get('status', 'under_review')
        report.save()
        
        messages.success(request, 'Report investigation updated successfully.')
        return redirect('risk:whistleblower_detail', pk=pk)
    
    return render(request, 'risk/whistleblower_investigate.html', {'report': report})


# ─── Compliance Views ─────────────────────────────────────────────────────────

class ComplianceRequirementListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List compliance requirements"""
    model = ComplianceRequirement
    template_name = 'risk/compliance_requirements.html'
    context_object_name = 'requirements'
    ordering = ['priority', '-compliance_score']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("compliance_owner")
        # Organization and branch filtering
        queryset = self.filter_queryset_by_branch(queryset)
        return queryset


class ComplianceRequirementDetailView(LoginRequiredMixin, DetailView):
    """View compliance requirement details"""
    model = ComplianceRequirement
    template_name = 'risk/compliance_detail.html'
    context_object_name = 'requirement'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['audits'] = self.object.audits.all()
        return context


class ComplianceAuditListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List compliance audits"""
    model = ComplianceAudit
    template_name = 'risk/compliance_audits.html'
    context_object_name = 'audits'
    ordering = ['-audit_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("requirement", "requirement__compliance_owner")
        return queryset


class ComplianceAuditDetailView(LoginRequiredMixin, DetailView):
    """View compliance audit details"""
    model = ComplianceAudit
    template_name = 'risk/compliance_audit_detail.html'
    context_object_name = 'audit'


# ─── Board Evaluation Views ───────────────────────────────────────────────────

class BoardEvaluationListView(LoginRequiredMixin, BranchOrganizationFilterMixin, ListView):
    """List board evaluations"""
    model = BoardEvaluation
    template_name = 'risk/board_evaluations.html'
    context_object_name = 'evaluations'
    ordering = ['-evaluation_period_end']

    def get_queryset(self):
        queryset = super().get_queryset().select_related("created_by")
        # Organization and branch filtering
        # Board evaluations are organization-wide, so filter by created_by's branch
        branch_ids = self.get_user_branch_ids()
        if branch_ids:
            queryset = queryset.filter(
                Q(created_by__userbranchmembership__branch_id__in=branch_ids)
            ).distinct()
        return queryset


class BoardEvaluationDetailView(LoginRequiredMixin, DetailView):
    """View board evaluation details"""
    model = BoardEvaluation
    template_name = 'risk/board_evaluation_detail.html'
    context_object_name = 'evaluation'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['director_evaluations'] = self.object.director_evaluations.all()
        return context


class BoardEvaluationCreateView(LoginRequiredMixin, CreateView):
    """Create a board evaluation"""
    model = BoardEvaluation
    template_name = 'risk/board_evaluation_form.html'
    fields = ['evaluation_type', 'evaluation_period_start', 'evaluation_period_end', 'title', 'summary', 'strengths', 'areas_for_improvement', 'recommendations', 'governance_effectiveness', 'strategic_oversight', 'risk_management', 'composition_assessment', 'independence_assessment']
    success_url = reverse_lazy('risk:board_evaluations')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'draft'
        messages.success(self.request, 'Board evaluation created successfully.')
        return super().form_valid(form)


class DirectorEvaluationDetailView(LoginRequiredMixin, DetailView):
    """View director evaluation details"""
    model = DirectorEvaluation
    template_name = 'risk/director_evaluation_detail.html'
    context_object_name = 'evaluation'


class DirectorEvaluationUpdateView(LoginRequiredMixin, UpdateView):
    """Update a director evaluation"""
    model = DirectorEvaluation
    template_name = 'risk/director_evaluation_form.html'
    fields = ['self_rating', 'self_assessment', 'peer_rating', 'peer_feedback', 'chair_rating', 'chair_feedback']
    success_url = reverse_lazy('risk:board_evaluations')
    
    def form_valid(self, form):
        messages.success(self.request, 'Director evaluation updated successfully.')
        return super().form_valid(form)


# ============================================================================
# Compliance Archive Views
# ============================================================================

class ComplianceArchiveListView(LoginRequiredMixin, ListView):
    """List all compliance archives"""
    model = ComplianceArchive
    template_name = 'risk/compliance_archive_list.html'
    context_object_name = 'archives'
    ordering = ['-archived_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        record_type = self.request.GET.get('record_type')
        if record_type:
            queryset = queryset.filter(record_type=record_type)
        return queryset


class ComplianceArchiveDetailView(LoginRequiredMixin, DetailView):
    """View compliance archive details"""
    model = ComplianceArchive
    template_name = 'risk/compliance_archive_detail.html'
    context_object_name = 'archive'


class ComplianceArchiveCreateView(LoginRequiredMixin, CreateView):
    """Create a new compliance archive record"""
    model = ComplianceArchive
    template_name = 'risk/compliance_archive_form.html'
    fields = ['record_type', 'original_record_id', 'record_title', 'compliance_category',
              'compliance_period_start', 'compliance_period_end', 'archived_data',
              'archive_reason', 'retention_period_years', 'expires_at']
    success_url = reverse_lazy('risk:compliance_archives')

    def form_valid(self, form):
        form.instance.archived_by = self.request.user
        messages.success(self.request, 'Compliance archive created successfully.')
        return super().form_valid(form)


class ComplianceArchiveUpdateView(LoginRequiredMixin, UpdateView):
    """Update a compliance archive record"""
    model = ComplianceArchive
    template_name = 'risk/compliance_archive_form.html'
    fields = ['record_type', 'record_title', 'compliance_category',
              'compliance_period_start', 'compliance_period_end',
              'archive_reason', 'retention_period_years', 'expires_at', 'archive_status']
    success_url = reverse_lazy('risk:compliance_archives')

    def form_valid(self, form):
        messages.success(self.request, 'Compliance archive updated successfully.')
        return super().form_valid(form)


# ============================================================================
# Compliance Attendance Views
# ============================================================================

class ComplianceAttendanceListView(LoginRequiredMixin, ListView):
    """List all compliance attendance records"""
    model = ComplianceAttendance
    template_name = 'risk/compliance_attendance_list.html'
    context_object_name = 'attendance_records'
    ordering = ['-recorded_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.select_related('user', 'meeting', 'recorded_by')
        compliance_type = self.request.GET.get('compliance_type')
        if compliance_type:
            queryset = queryset.filter(compliance_type=compliance_type)
        return queryset


class ComplianceAttendanceCreateView(LoginRequiredMixin, CreateView):
    """Create a compliance attendance record"""
    model = ComplianceAttendance
    template_name = 'risk/compliance_attendance_form.html'
    fields = ['user', 'meeting', 'compliance_type', 'attendance_status', 'is_excused', 
              'excuse_reason', 'check_in_time', 'check_out_time', 'notes']
    success_url = reverse_lazy('risk:compliance_attendance')
    
    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        messages.success(self.request, 'Compliance attendance recorded successfully.')
        return super().form_valid(form)


class ComplianceAttendanceUpdateView(LoginRequiredMixin, UpdateView):
    """Update a compliance attendance record"""
    model = ComplianceAttendance
    template_name = 'risk/compliance_attendance_form.html'
    fields = ['attendance_status', 'is_excused', 'excuse_reason', 'check_in_time', 
              'check_out_time', 'notes']
    success_url = reverse_lazy('risk:compliance_attendance')
    
    def form_valid(self, form):
        messages.success(self.request, 'Compliance attendance updated successfully.')
        return super().form_valid(form)
