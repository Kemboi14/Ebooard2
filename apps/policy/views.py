from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import Policy, PolicyCategory, PolicyReview, PolicyAcknowledgment
from .forms import PolicyForm, PolicyCategoryForm, PolicyReviewForm, PolicySearchForm, PolicyVersionForm
from apps.accounts.permissions import CAN_MANAGE_POLICIES

class PolicyListView(LoginRequiredMixin, ListView):
    """List all policies with search and filtering"""
    model = Policy
    template_name = 'policy/policy_list.html'
    context_object_name = 'policies'
    paginate_by = 12

    def get_queryset(self):
        queryset = Policy.objects.select_related('category', 'policy_owner', 'created_by').prefetch_related('acknowledgments')
        
        # Apply search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(content__icontains=search)
            )
        
        # Apply category filter
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Apply category type filter
        category_type = self.request.GET.get('category_type')
        if category_type:
            queryset = queryset.filter(category_type=category_type)
        
        # Apply status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Apply access level filter
        access_level = self.request.GET.get('access_level')
        if access_level:
            queryset = queryset.filter(access_level=access_level)
        
        # Filter by user's access level
        user = self.request.user
        if user.role == 'board_member':
            queryset = queryset.filter(access_level__in=['public', 'board'])
        elif user.role == 'company_secretary':
            queryset = queryset.filter(access_level__in=['public', 'board', 'committee'])
        elif user.role == 'compliance_officer':
            # Compliance officers can see all policies
            pass
        elif user.role == 'it_administrator':
            # IT admins can see all policies
            pass
        else:
            queryset = queryset.filter(access_level='public')
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PolicySearchForm(self.request.GET)
        context['categories'] = PolicyCategory.objects.all()
        context['can_manage'] = CAN_MANAGE_POLICIES
        return context

class PolicyDetailView(LoginRequiredMixin, DetailView):
    """View policy details"""
    model = Policy
    template_name = 'policy/policy_detail.html'
    context_object_name = 'policy'

    def get_object(self):
        obj = super().get_object()
        
        # Check access permissions
        user = self.request.user
        if obj.access_level == 'restricted' and user.role not in ['compliance_officer', 'it_administrator']:
            if obj.policy_owner != user:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to view this policy.")
        
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        policy = self.object
        
        # Get related policies
        context['superseded_policies'] = Policy.objects.filter(supersedes=policy).order_by('-version')
        context['newer_versions'] = Policy.objects.filter(supersedes=policy).order_by('version')
        
        # Get reviews
        context['reviews'] = policy.reviews.select_related('reviewer').order_by('-review_date')
        
        # Get acknowledgments
        context['acknowledgments'] = policy.acknowledgments.select_related('user').order_by('-acknowledged_at')
        
        # Check if user has acknowledged
        if self.request.user.is_authenticated:
            context['user_acknowledged'] = policy.acknowledgments.filter(
                user=self.request.user
            ).exists()
        
        context['can_manage'] = CAN_MANAGE_POLICIES
        context['can_edit'] = CAN_MANAGE_POLICIES or policy.policy_owner == self.request.user
        
        return context

class PolicyCreateView(LoginRequiredMixin, CreateView):
    """Create a new policy"""
    model = Policy
    form_class = PolicyForm
    template_name = 'policy/policy_form.html'
    success_url = reverse_lazy('policy:policy_list')

    def dispatch(self, request, *args, **kwargs):
        if not CAN_MANAGE_POLICIES:
            messages.error(request, "You don't have permission to create policies.")
            return redirect('policy:policy_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Policy '{form.instance.title}' created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Policy'
        context['is_update'] = False
        return context

class PolicyUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing policy"""
    model = Policy
    form_class = PolicyForm
    template_name = 'policy/policy_form.html'

    def dispatch(self, request, *args, **kwargs):
        policy = self.get_object()
        if not CAN_MANAGE_POLICIES and policy.policy_owner != request.user:
            messages.error(request, "You don't have permission to edit this policy.")
            return redirect('policy:policy_detail', pk=policy.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"Policy '{form.instance.title}' updated successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Policy'
        context['is_update'] = True
        return context

@login_required
def create_policy_version(request, pk):
    """Create a new version of an existing policy"""
    policy = get_object_or_404(Policy, pk=pk)
    
    if not CAN_MANAGE_POLICIES and policy.policy_owner != request.user:
        messages.error(request, "You don't have permission to create versions of this policy.")
        return redirect('policy:policy_detail', pk=policy.pk)
    
    if request.method == 'POST':
        form = PolicyVersionForm(request.POST, request.FILES)
        if form.is_valid():
            new_policy = policy.create_new_version(
                content_changes=form.cleaned_data['content'],
                description=form.cleaned_data['description'],
                effective_date=form.cleaned_data['effective_date'],
                review_date=form.cleaned_data['review_date'],
                expiry_date=form.cleaned_data['expiry_date'],
                policy_owner=form.cleaned_data['policy_owner'],
                access_level=form.cleaned_data['access_level'],
                created_by=request.user,
            )
            messages.success(request, f"New version {new_policy.version} created successfully.")
            return redirect('policy:policy_detail', pk=new_policy.pk)
    else:
        form = PolicyVersionForm(initial={
            'description': policy.description,
            'content': policy.content,
            'effective_date': policy.effective_date,
            'review_date': policy.review_date,
            'expiry_date': policy.expiry_date,
            'policy_owner': policy.policy_owner,
            'access_level': policy.access_level,
        })
    
    return render(request, 'policy/policy_version_form.html', {
        'form': form,
        'policy': policy,
        'title': f'Create New Version of {policy.title}',
    })

@login_required
@require_POST
def acknowledge_policy(request, pk):
    """Acknowledge a policy"""
    policy = get_object_or_404(Policy, pk=pk)
    
    # Check if user can access this policy
    if policy.access_level == 'restricted' and request.user.role not in ['compliance_officer', 'it_administrator']:
        if policy.policy_owner != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Create or update acknowledgment
    acknowledgment, created = PolicyAcknowledgment.objects.get_or_create(
        policy=policy,
        user=request.user,
        defaults={
            'ip_address': request.META.get('REMOTE_ADDR'),
            'notes': request.POST.get('notes', ''),
        }
    )
    
    if not created:
        acknowledgment.notes = request.POST.get('notes', '')
        acknowledgment.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Policy acknowledged successfully',
        'acknowledged_at': acknowledgment.acknowledged_at.strftime('%Y-%m-%d %H:%M'),
    })

@login_required
def policy_dashboard(request):
    """Policy management dashboard"""
    context = {
        'total_policies': Policy.objects.count(),
        'published_policies': Policy.objects.filter(status='published', is_current=True).count(),
        'draft_policies': Policy.objects.filter(status='draft').count(),
        'policies_needing_review': Policy.objects.filter(
            review_date__lte=timezone.now().date(),
            status='published',
            is_current=True
        ).count(),
        'recent_policies': Policy.objects.order_by('-created_at')[:5],
        'categories': PolicyCategory.objects.all(),
        'can_manage': CAN_MANAGE_POLICIES,
    }
    
    return render(request, 'policy/policy_dashboard.html', context)

class CategoryListView(LoginRequiredMixin, ListView):
    """List policy categories"""
    model = PolicyCategory
    template_name = 'policy/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return PolicyCategory.objects.select_related('parent').prefetch_related('children')

class CategoryCreateView(LoginRequiredMixin, CreateView):
    """Create a new policy category"""
    model = PolicyCategory
    form_class = PolicyCategoryForm
    template_name = 'policy/category_form.html'
    success_url = reverse_lazy('policy:category_list')

    def dispatch(self, request, *args, **kwargs):
        if not CAN_MANAGE_POLICIES:
            messages.error(request, "You don't have permission to create categories.")
            return redirect('policy:category_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing policy category"""
    model = PolicyCategory
    form_class = PolicyCategoryForm
    template_name = 'policy/category_form.html'
    success_url = reverse_lazy('policy:category_list')

    def dispatch(self, request, *args, **kwargs):
        if not CAN_MANAGE_POLICIES:
            messages.error(request, "You don't have permission to edit categories.")
            return redirect('policy:category_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

class ReviewCreateView(LoginRequiredMixin, CreateView):
    """Create a new policy review"""
    model = PolicyReview
    form_class = PolicyReviewForm
    template_name = 'policy/review_form.html'

    def dispatch(self, request, *args, **kwargs):
        policy = get_object_or_404(Policy, pk=kwargs['policy_pk'])
        if not CAN_MANAGE_POLICIES and policy.policy_owner != request.user:
            messages.error(request, "You don't have permission to review this policy.")
            return redirect('policy:policy_detail', pk=policy.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        policy = get_object_or_404(Policy, pk=self.kwargs['policy_pk'])
        form.instance.policy = policy
        messages.success(self.request, f"Review for '{policy.title}' created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('policy:policy_detail', kwargs={'pk': self.kwargs['policy_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['policy'] = get_object_or_404(Policy, pk=self.kwargs['policy_pk'])
        return context
