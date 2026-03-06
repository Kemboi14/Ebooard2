from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse

from .models import Motion, VotingSession, Vote, VoteOption, VoteResult
from .forms import MotionForm, VoteForm, VotingSessionForm, MotionSearchForm, VoteOptionForm
from apps.accounts.decorators import role_required
from apps.accounts.permissions import CAN_VOTE

class MotionListView(LoginRequiredMixin, ListView):
    """List view for motions with role-based filtering"""
    model = Motion
    template_name = 'voting/motion_list.html'
    context_object_name = 'motions'
    paginate_by = 10
    
    def get_queryset(self):
        """Filter motions based on user role"""
        user = self.request.user
        queryset = Motion.objects.all()
        
        # Role-based filtering
        if user.role == 'it_administrator':
            return queryset
        elif user.role in ['company_secretary', 'executive_management']:
            return queryset
        elif user.role == 'board_member':
            return queryset.filter(status__in=['proposed', 'debate', 'voting', 'passed', 'failed'])
        else:
            return queryset.filter(status__in=['passed', 'failed'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = MotionSearchForm(self.request.GET or None)
        context['can_create'] = self.request.user.role in ['company_secretary', 'executive_management', 'it_administrator']
        return context

class MotionDetailView(LoginRequiredMixin, DetailView):
    """Detail view for individual motions"""
    model = Motion
    template_name = 'voting/motion_detail.html'
    context_object_name = 'motion'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        motion = self.get_object()
        user = self.request.user
        
        context['can_vote'] = user.role in CAN_VOTE
        context['has_voted'] = Vote.objects.filter(motion=motion, voter=user).exists()
        context['vote_options'] = motion.vote_options.all().order_by('order')
        context['user_vote'] = Vote.objects.filter(motion=motion, voter=user).first()
        context['vote_form'] = VoteForm(motion=motion) if context['can_vote'] and motion.is_voting_open else None
        
        return context

class CreateMotionView(LoginRequiredMixin, CreateView):
    """Create view for new motions"""
    model = Motion
    form_class = MotionForm
    template_name = 'voting/create_motion.html'
    success_url = reverse_lazy('voting:motion_list')
    
    def dispatch(self, request, *args, **kwargs):
        """Only users who can create motions can access"""
        if request.user.role not in ['company_secretary', 'executive_management', 'it_administrator']:
            messages.error(request, 'You do not have permission to create motions.')
            return redirect('voting:motion_list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Set proposed_by and create activity"""
        form.instance.proposed_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Motion created successfully!')
        return response

@login_required
def cast_vote(request, pk):
    """Handle vote casting"""
    motion = get_object_or_404(Motion, pk=pk)
    user = request.user
    
    if user.role not in CAN_VOTE:
        messages.error(request, 'You do not have permission to vote.')
        return redirect('voting:motion_detail', pk=pk)
    
    if not motion.is_voting_open:
        messages.error(request, 'Voting is not currently open for this motion.')
        return redirect('voting:motion_detail', pk=pk)
    
    if Vote.objects.filter(motion=motion, voter=user).exists():
        messages.error(request, 'You have already voted on this motion.')
        return redirect('voting:motion_detail', pk=pk)
    
    if request.method == 'POST':
        form = VoteForm(motion=motion, data=request.POST)
        if form.is_valid():
            vote = form.save(commit=False)
            vote.motion = motion
            vote.voter = user
            vote.ip_address = request.META.get('REMOTE_ADDR')
            vote.save()
            
            messages.success(request, 'Your vote has been recorded!')
            return redirect('voting:motion_detail', pk=pk)
    else:
        form = VoteForm(motion=motion)
    
    return render(request, 'voting/cast_vote.html', {
        'motion': motion,
        'form': form,
    })

@role_required('company_secretary', 'executive_management', 'it_administrator')
def manage_voting_session(request, pk=None):
    """Manage voting sessions"""
    if pk:
        session = get_object_or_404(VotingSession, pk=pk)
        motions = session.motions.all()
    else:
        session = None
        motions = Motion.objects.none()
    
    if request.method == 'POST':
        form = VotingSessionForm(request.POST)
        if form.is_valid():
            form.instance.created_by = request.user
            form.save()
            messages.success(request, 'Voting session created successfully!')
            return redirect('voting:manage_session', pk=form.instance.id)
    else:
        form = VotingSessionForm()
    
    return render(request, 'voting/manage_session.html', {
        'session': session,
        'motions': motions,
        'form': form,
    })

@login_required
def motion_search(request):
    """Search motions based on form criteria"""
    form = MotionSearchForm(request.GET)
    motions = Motion.objects.all()
    
    # Apply role-based filtering
    user = request.user
    if user.role == 'it_administrator':
        pass  # See all
    elif user.role in ['company_secretary', 'executive_management']:
        pass  # See all
    elif user.role == 'board_member':
        motions = motions.filter(status__in=['proposed', 'debate', 'voting', 'passed', 'failed'])
    else:
        motions = motions.filter(status__in=['passed', 'failed'])
    
    if form.is_valid():
        query = form.cleaned_data.get('query', '')
        search_type = form.cleaned_data.get('search_type', 'all')
        status = form.cleaned_data.get('status')
        voting_type = form.cleaned_data.get('voting_type')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        
        if query:
            if search_type == 'title':
                motions = motions.filter(title__icontains=query)
            elif search_type == 'description':
                motions = motions.filter(description__icontains=query)
            elif search_type == 'background':
                motions = motions.filter(background__icontains=query)
            else:  # all fields
                motions = motions.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(background__icontains=query)
                )
        
        if status:
            motions = motions.filter(status=status)
        if voting_type:
            motions = motions.filter(voting_type=voting_type)
        if date_from:
            motions = motions.filter(created_at__date__gte=date_from)
        if date_to:
            motions = motions.filter(created_at__date__lte=date_to)
    
    return render(request, 'voting/motion_list.html', {
        'motions': motions,
        'search_form': form,
        'can_create': request.user.role in ['company_secretary', 'executive_management', 'it_administrator'],
    })

@login_required
def vote_results(request, pk):
    """Show voting results for a motion"""
    motion = get_object_or_404(Motion, pk=pk)
    
    # Check if user can view results
    user = request.user
    if user.role not in ['company_secretary', 'executive_management', 'it_administrator']:
        if motion.status not in ['passed', 'failed']:
            messages.error(request, 'Results are not yet available for this motion.')
            return redirect('voting:motion_detail', pk=pk)
    
    try:
        result = motion.result
    except VoteResult.DoesNotExist:
        result = None
    
    return render(request, 'voting/vote_results.html', {
        'motion': motion,
        'result': result,
        'can_manage': user.role in ['company_secretary', 'executive_management', 'it_administrator'],
    })

@login_required
def voting_dashboard(request):
    """Main voting dashboard with active sessions and motions"""
    user = request.user
    
    # Get active voting session
    active_session = VotingSession.objects.filter(
        status='active',
        eligible_voters=user
    ).first()
    
    # Get motions user can vote on
    if user.role in CAN_VOTE:
        votable_motions = Motion.objects.filter(
            status='voting',
            voting_deadline__gt=timezone.now()
        ).exclude(
            votes__voter=user
        )
    else:
        votable_motions = Motion.objects.none()
    
    # Get user's voting history
    user_votes = Vote.objects.filter(voter=user).select_related('motion')
    
    return render(request, 'voting/voting_dashboard.html', {
        'active_session': active_session,
        'votable_motions': votable_motions,
        'user_votes': user_votes,
        'can_create': user.role in ['company_secretary', 'executive_management', 'it_administrator'],
    })
