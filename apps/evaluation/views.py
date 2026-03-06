from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, F
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import (
    EvaluationTemplate, EvaluationQuestion, Evaluation, EvaluationAnswer, 
    EvaluationComment, EvaluationSummary, EvaluationCycle, EvaluationFramework,
    CalibrationSession, EvaluationAnalytics
)
from .forms import (
    EvaluationTemplateForm, EvaluationQuestionForm, EvaluationForm, EvaluationAnswerForm,
    EvaluationCommentForm, EvaluationSummaryForm, EvaluationCycleForm
)
from apps.accounts.models import User

# ... existing views ...

def get_evaluation_trends(evaluations):
    """Generate monthly trend data for evaluations"""
    from django.db.models.functions import TruncMonth
    from django.db.models import Count
    
    # Last 12 months trend
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=365)
    
    trends = evaluations.filter(
        created_at__gte=start_date,
        status='approved'
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id'),
        avg_score=Avg('percentage_score')
    ).order_by('month')
    
    # Convert to chart-ready format
    monthly_data = []
    for trend in trends:
        monthly_data.append({
            'month': trend['month'].strftime('%b %Y'),
            'count': trend['count'],
            'avg_score': round(trend['avg_score'] or 0, 1)
        })
    
    return monthly_data

def calculate_compliance_rate(evaluations):
    """Calculate compliance rate based on evaluation completion and timeliness"""
    total_evaluations = evaluations.count()
    if total_evaluations == 0:
        return 0
    
    # Completed evaluations
    completed = evaluations.filter(status='approved').count()
    
    # On-time completions
    on_time = evaluations.filter(
        status='approved',
        submitted_at__lte=F('end_date')
    ).count()
    
    # Calculate weighted compliance score
    completion_rate = (completed / total_evaluations) * 100
    timeliness_rate = (on_time / total_evaluations) * 100 if completed > 0 else 0
    
    # Overall compliance (70% completion + 30% timeliness)
    compliance_rate = (completion_rate * 0.7) + (timeliness_rate * 0.3)
    
    return round(compliance_rate, 1)

def get_industry_benchmarks():
    """Get industry benchmarking data"""
    # This would typically pull from a benchmarking database
    # For now, return sample benchmarks
    return {
        'board_effectiveness': {
            'average_score': 82.5,
            'top_quartile': 90.0,
            'bottom_quartile': 75.0,
            'sample_size': 1250
        },
        'director_performance': {
            'average_score': 85.2,
            'top_quartile': 92.1,
            'bottom_quartile': 78.3,
            'sample_size': 980
        },
        'compliance_rate': {
            'average_rate': 87.3,
            'top_quartile': 95.0,
            'bottom_quartile': 80.0,
            'sample_size': 1500
        }
    }

def generate_predictive_insights(evaluations):
    """Generate predictive insights using evaluation data"""
    insights = []
    
    # Risk of overdue evaluations
    overdue_risk = evaluations.filter(
        status__in=['draft', 'in_progress'],
        end_date__lt=timezone.now().date() + timezone.timedelta(days=14)
    ).count()
    
    if overdue_risk > 0:
        insights.append({
            'type': 'warning',
            'title': 'Overdue Evaluation Risk',
            'message': f'{overdue_risk} evaluations are at risk of becoming overdue in the next 2 weeks.',
            'action': 'Send reminders to evaluators'
        })
    
    # Performance trends
    recent_avg = evaluations.filter(
        status='approved',
        created_at__gte=timezone.now() - timezone.timedelta(days=90)
    ).aggregate(avg=Avg('percentage_score'))['avg']
    
    previous_avg = evaluations.filter(
        status='approved',
        created_at__gte=timezone.now() - timezone.timedelta(days=180),
        created_at__lt=timezone.now() - timezone.timedelta(days=90)
    ).aggregate(avg=Avg('percentage_score'))['avg']
    
    if recent_avg and previous_avg:
        change = recent_avg - previous_avg
        if abs(change) > 5:
            trend = "improving" if change > 0 else "declining"
            insights.append({
                'type': 'info',
                'title': 'Performance Trend',
                'message': f'Board performance scores are {trend} by {abs(change):.1f} points compared to previous period.',
                'action': 'Review performance drivers'
            })
    
    # Calibration needs
    needs_calibration = evaluations.filter(
        status='approved',
        requires_calibration=True,
        calibration_completed=False
    ).count()
    
    if needs_calibration > 0:
        insights.append({
            'type': 'action',
            'title': 'Calibration Required',
            'message': f'{needs_calibration} evaluations require calibration for scoring consistency.',
            'action': 'Schedule calibration session'
        })
    
    # Diversity insights (if available)
    # This would analyze evaluation patterns by demographics
    
    return insights

# ... rest of views ...

class EvaluationListView(LoginRequiredMixin, ListView):
    """List all evaluations with filtering"""
    model = Evaluation
    template_name = 'evaluation/evaluation_list.html'
    context_object_name = 'evaluations'
    paginate_by = 12

    def get_queryset(self):
        queryset = Evaluation.objects.select_related(
            'template', 'evaluator', 'evaluatee', 'reviewed_by'
        ).prefetch_related('answers', 'comments')
        
        # Filter by user role
        user = self.request.user
        if user.role == 'board_member':
            # Board members can see evaluations they're involved in
            queryset = queryset.filter(
                Q(evaluator=user) | Q(evaluatee=user)
            )
        elif user.role in ['company_secretary', 'compliance_officer']:
            # Can see all evaluations
            pass
        else:
            # Other roles see nothing
            queryset = queryset.none()
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        evaluator_id = self.request.GET.get('evaluator')
        if evaluator_id:
            queryset = queryset.filter(evaluator_id=evaluator_id)
        
        evaluatee_id = self.request.GET.get('evaluatee')
        if evaluatee_id:
            queryset = queryset.filter(evaluatee_id=evaluatee_id)
        
        template_id = self.request.GET.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        period = self.request.GET.get('period')
        if period:
            queryset = queryset.filter(evaluation_period__icontains=period)
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter options
        context['status_choices'] = Evaluation.STATUS_CHOICES
        context['templates'] = EvaluationTemplate.objects.filter(is_active=True)
        context['board_members'] = User.objects.filter(role='board_member')
        
        # Current filters
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'evaluator': self.request.GET.get('evaluator', ''),
            'evaluatee': self.request.GET.get('evaluatee', ''),
            'template': self.request.GET.get('template', ''),
            'period': self.request.GET.get('period', ''),
        }
        
        # Calculate status percentages for progress bars
        evaluations = self.get_queryset()
        total_count = evaluations.count()
        context['total_evaluations'] = total_count
        context['pending_evaluations'] = evaluations.filter(status='in_progress').count()
        context['submitted_evaluations'] = evaluations.filter(status='submitted').count()
        context['completed_evaluations'] = evaluations.filter(status='approved').count()
        context['overdue_evaluations'] = evaluations.filter(
            end_date__lt=timezone.now().date(),
            status__in=['draft', 'in_progress']
        ).count()
        
        # Calculate percentages
        if total_count > 0:
            context['pending_percentage'] = round((context['pending_evaluations'] / total_count) * 100, 1)
            context['submitted_percentage'] = round((context['submitted_evaluations'] / total_count) * 100, 1)
            context['completed_percentage'] = round((context['completed_evaluations'] / total_count) * 100, 1)
            context['overdue_percentage'] = round((context['overdue_evaluations'] / total_count) * 100, 1)
        else:
            context['pending_percentage'] = 0
            context['submitted_percentage'] = 0
            context['completed_percentage'] = 0
            context['overdue_percentage'] = 0
        
        return context

class EvaluationDetailView(LoginRequiredMixin, DetailView):
    """View evaluation details and answers"""
    model = Evaluation
    template_name = 'evaluation/evaluation_detail.html'
    context_object_name = 'evaluation'

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        
        # Check permissions
        if user.role == 'board_member':
            if obj.evaluator != user and obj.evaluatee != user:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("You can only view evaluations you're involved in.")
        elif user.role not in ['company_secretary', 'compliance_officer']:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to view this evaluation.")
        
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evaluation = self.object
        
        # Get answers grouped by question
        answers = evaluation.answers.select_related('question').order_by('question__order')
        context['answers'] = answers
        
        # Get comments
        context['comments'] = evaluation.comments.select_related('author').order_by('-created_at')
        
        # Check if user can edit
        user = self.request.user
        context['can_edit'] = (
            user.role in ['company_secretary', 'compliance_officer'] or
            (user.role == 'board_member' and evaluation.evaluator == user and evaluation.status in ['draft', 'in_progress'])
        )
        
        # Check if summary exists
        context['has_summary'] = hasattr(evaluation, 'summary')
        
        return context

class EvaluationCreateView(LoginRequiredMixin, CreateView):
    """Create a new evaluation"""
    model = Evaluation
    form_class = EvaluationForm
    template_name = 'evaluation/evaluation_form.html'
    success_url = reverse_lazy('evaluation:evaluation_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['company_secretary', 'compliance_officer', 'it_administrator']:
            messages.error(request, "You don't have permission to create evaluations.")
            return redirect('evaluation:evaluation_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Evaluation created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Evaluation'
        context['is_update'] = False
        return context

class EvaluationUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing evaluation"""
    model = Evaluation
    form_class = EvaluationForm
    template_name = 'evaluation/evaluation_form.html'

    def dispatch(self, request, *args, **kwargs):
        evaluation = self.get_object()
        user = request.user
        
        if user.role not in ['company_secretary', 'compliance_officer']:
            if evaluation.evaluator != user or evaluation.status not in ['draft', 'in_progress']:
                messages.error(request, "You don't have permission to edit this evaluation.")
                return redirect('evaluation:evaluation_detail', pk=evaluation.pk)
        
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"Evaluation updated successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Evaluation'
        context['is_update'] = True
        return context

@login_required
def take_evaluation(request, pk):
    """Take an evaluation (answer questions)"""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    user = request.user
    
    # Check permissions
    if user.role == 'board_member':
        if evaluation.evaluator != user:
            messages.error(request, "You can only take evaluations assigned to you.")
            return redirect('evaluation:evaluation_detail', pk=pk)
    elif user.role not in ['company_secretary', 'compliance_officer']:
        messages.error(request, "You don't have permission to take this evaluation.")
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    if evaluation.status in ['submitted', 'approved', 'archived']:
        messages.error(request, "This evaluation cannot be modified.")
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    # Update status to in_progress
    if evaluation.status == 'draft':
        evaluation.status = 'in_progress'
        evaluation.save()
    
    questions = evaluation.template.questions.order_by('order')
    
    if request.method == 'POST':
        with transaction.atomic():
            for question in questions:
                answer, created = EvaluationAnswer.objects.get_or_create(
                    evaluation=evaluation,
                    question=question,
                    defaults={}
                )
                
                # Update answer based on question type
                if question.question_type == 'text':
                    answer.text_answer = request.POST.get(f'text_{question.id}')
                elif question.question_type in ['rating', 'numeric']:
                    answer.numeric_answer = request.POST.get(f'numeric_{question.id}')
                elif question.question_type in ['yes_no', 'multiple_choice']:
                    answer.choice_answer = request.POST.get(f'choice_{question.id}')
                
                # Score
                score = request.POST.get(f'score_{question.id}')
                if score:
                    answer.score = float(score)
                
                # Comments
                answer.comments = request.POST.get(f'comments_{question.id}')
                answer.save()
            
            # Calculate total score
            evaluation.calculate_score()
            
            # Check if evaluation is complete
            required_questions = questions.filter(is_required=True)
            answered_questions = evaluation.answers.filter(
                question__in=required_questions
            )
            
            if answered_questions.count() == required_questions.count():
                evaluation.status = 'submitted'
                evaluation.submitted_at = timezone.now()
                evaluation.save()
                messages.success(request, "Evaluation submitted successfully!")
            else:
                messages.info(request, "Evaluation saved. Please complete all required questions.")
        
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    return render(request, 'evaluation/take_evaluation.html', {
        'evaluation': evaluation,
        'questions': questions,
        'answers': {answer.question_id: answer for answer in evaluation.answers.all()}
    })

@login_required
def submit_evaluation(request, pk):
    """Submit an evaluation for review"""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    user = request.user
    
    # Check permissions
    if user.role == 'board_member':
        if evaluation.evaluator != user:
            messages.error(request, "You can only submit evaluations assigned to you.")
            return redirect('evaluation:evaluation_detail', pk=pk)
    elif user.role not in ['company_secretary', 'compliance_officer']:
        messages.error(request, "You don't have permission to submit this evaluation.")
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    if evaluation.status != 'in_progress':
        messages.error(request, "This evaluation cannot be submitted.")
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    # Check if all required questions are answered
    required_questions = evaluation.template.questions.filter(is_required=True)
    answered_questions = evaluation.answers.filter(
        question__in=required_questions
    )
    
    if answered_questions.count() < required_questions.count():
        messages.error(request, "Please complete all required questions before submitting.")
        return redirect('evaluation:take_evaluation', pk=pk)
    
    evaluation.status = 'submitted'
    evaluation.submitted_at = timezone.now()
    evaluation.save()
    
    messages.success(request, "Evaluation submitted for review!")
    return redirect('evaluation:evaluation_detail', pk=pk)

@login_required
def review_evaluation(request, pk):
    """Review and approve/reject an evaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    user = request.user
    
    if user.role not in ['company_secretary', 'compliance_officer']:
        messages.error(request, "You don't have permission to review evaluations.")
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    if evaluation.status != 'submitted':
        messages.error(request, "This evaluation cannot be reviewed.")
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        comments = request.POST.get('review_comments', '')
        
        if action == 'approve':
            evaluation.status = 'approved'
            evaluation.approved_by = user
            evaluation.approved_at = timezone.now()
            messages.success(request, "Evaluation approved!")
        elif action == 'reject':
            evaluation.status = 'rejected'
            messages.warning(request, "Evaluation rejected.")
        else:
            messages.error(request, "Invalid action.")
            return redirect('evaluation:evaluation_detail', pk=pk)
        
        evaluation.reviewed_by = user
        evaluation.reviewed_at = timezone.now()
        evaluation.review_comments = comments
        evaluation.save()
        
        return redirect('evaluation:evaluation_detail', pk=pk)
    
    return render(request, 'evaluation/review_evaluation.html', {
        'evaluation': evaluation
    })

# Template Management
class TemplateListView(LoginRequiredMixin, ListView):
    """List evaluation templates"""
    model = EvaluationTemplate
    template_name = 'evaluation/template_list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        user = self.request.user
        if user.role in ['company_secretary', 'compliance_officer']:
            return EvaluationTemplate.objects.all()
        else:
            return EvaluationTemplate.objects.filter(is_public=True)

class TemplateDetailView(LoginRequiredMixin, DetailView):
    """View template details"""
    model = EvaluationTemplate
    template_name = 'evaluation/template_detail.html'
    context_object_name = 'template'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.questions.order_by('order')
        return context

class TemplateCreateView(LoginRequiredMixin, CreateView):
    """Create a new evaluation template"""
    model = EvaluationTemplate
    form_class = EvaluationTemplateForm
    template_name = 'evaluation/template_form.html'
    success_url = reverse_lazy('evaluation:template_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['company_secretary', 'compliance_officer', 'it_administrator']:
            messages.error(request, "You don't have permission to create templates.")
            return redirect('evaluation:template_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Template '{form.instance.name}' created successfully.")
        return super().form_valid(form)

@login_required
def add_question(request, template_pk):
    """Add a question to a template"""
    template = get_object_or_404(EvaluationTemplate, pk=template_pk)
    
    if request.user.role not in ['company_secretary', 'compliance_officer', 'it_administrator']:
        messages.error(request, "You don't have permission to edit templates.")
        return redirect('evaluation:template_detail', pk=template_pk)
    
    if request.method == 'POST':
        form = EvaluationQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.template = template
            question.save()
            messages.success(request, "Question added successfully!")
            return redirect('evaluation:template_detail', pk=template_pk)
    else:
        form = EvaluationQuestionForm(initial={'order': template.questions.count()})
    
    return render(request, 'evaluation/question_form.html', {
        'form': form,
        'template': template
    })

@login_required
def evaluation_dashboard(request):
    """Enterprise-grade evaluation dashboard with advanced analytics"""
    user = request.user
    
    # Base queryset based on user role
    if user.role == 'board_member':
        evaluations = Evaluation.objects.filter(
            Q(evaluator=user) | Q(evaluatee=user)
        )
    elif user.role in ['company_secretary', 'compliance_officer']:
        evaluations = Evaluation.objects.all()
    else:
        evaluations = Evaluation.objects.none()
    
    # Advanced analytics data
    analytics = {
        'total_evaluations': evaluations.count(),
        'pending_evaluations': evaluations.filter(status='in_progress').count(),
        'submitted_evaluations': evaluations.filter(status='submitted').count(),
        'completed_evaluations': evaluations.filter(status='approved').count(),
        'overdue_evaluations': evaluations.filter(
            end_date__lt=timezone.now().date(),
            status__in=['draft', 'in_progress']
        ).count(),
        
        # Performance metrics
        'average_score': evaluations.filter(status='approved').aggregate(
            avg_score=Avg('percentage_score')
        )['avg_score'] or 0,
        
        'high_performers': evaluations.filter(
            status='approved', 
            percentage_score__gte=90
        ).count(),
        
        'needs_improvement': evaluations.filter(
            status='approved', 
            percentage_score__lt=70
        ).count(),
    }
    
    # Additional context data
    context = analytics.copy()
    
    # Trend analysis (last 12 months)
    monthly_trends_data = get_evaluation_trends(evaluations)
    context['monthly_trends'] = monthly_trends_data if monthly_trends_data else []
    
    # Risk indicators
    context['at_risk_evaluations'] = evaluations.filter(
        status__in=['draft', 'in_progress'],
        end_date__lt=timezone.now().date() + timezone.timedelta(days=7)
    ).count()
    
    # Compliance status
    context['compliance_rate'] = calculate_compliance_rate(evaluations)
    
    # Recent evaluations with detailed info
    context['recent_evaluations'] = evaluations.select_related(
        'template', 'evaluator', 'evaluatee', 'reviewed_by'
    ).order_by('-created_at')[:10]
    
    # My evaluations
    context['my_evaluations'] = evaluations.filter(evaluator=user).order_by('-created_at')[:5]
    context['evaluations_of_me'] = evaluations.filter(evaluatee=user).order_by('-created_at')[:5]
    
    # Templates and cycles
    context['templates'] = EvaluationTemplate.objects.filter(is_active=True)
    context['cycles'] = EvaluationCycle.objects.filter(is_active=True)
    
    # Calibration status
    context['pending_calibrations'] = evaluations.filter(
        status='calibration',
        requires_calibration=True
    ).count()
    
    # Benchmarking data
    context['industry_benchmarks'] = get_industry_benchmarks()
    
    # Predictive insights
    context['predictive_insights'] = generate_predictive_insights(evaluations)
    
    return render(request, 'evaluation/evaluation_dashboard.html', context)
    
@login_required
def populate_professional_templates(request):
    """Populate professional evaluation templates via web interface"""
    if request.user.role not in ['company_secretary', 'compliance_officer', 'it_administrator']:
        messages.error(request, "You don't have permission to populate templates.")
        return redirect('evaluation:template_list')
    
    if request.method == 'POST':
        try:
            # Import and run the management command
            from .management.commands.populate_professional_templates import Command
            command = Command()
            command.handle()
            
            messages.success(request, "Professional evaluation templates have been successfully loaded!")
        except Exception as e:
            messages.error(request, f"Error loading templates: {str(e)}")
    
    return redirect('evaluation:template_list')

# Cycle Management
class CycleListView(LoginRequiredMixin, ListView):
    """List evaluation cycles"""
    model = EvaluationCycle
    template_name = 'evaluation/cycle_list.html'
    context_object_name = 'cycles'

    def get_queryset(self):
        if self.request.user.role in ['company_secretary', 'compliance_officer']:
            return EvaluationCycle.objects.all()
        else:
            return EvaluationCycle.objects.filter(
                participants=self.request.user,
                is_active=True
            )

class CycleDetailView(LoginRequiredMixin, DetailView):
    """View cycle details"""
    model = EvaluationCycle
    template_name = 'evaluation/cycle_detail.html'
    context_object_name = 'cycle'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = self.object
        
        context['evaluations'] = cycle.evaluations.all()
        context['completion_rate'] = cycle.get_completion_rate()
        
        return context

class CycleCreateView(LoginRequiredMixin, CreateView):
    """Create a new evaluation cycle"""
    model = EvaluationCycle
    form_class = EvaluationCycleForm
    template_name = 'evaluation/cycle_form.html'
    success_url = reverse_lazy('evaluation:cycle_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['company_secretary', 'compliance_officer', 'it_administrator']:
            messages.error(request, "You don't have permission to create cycles.")
            return redirect('evaluation:cycle_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Cycle '{form.instance.name}' created successfully.")
        return super().form_valid(form)
