from django import forms
from django.utils import timezone
from .models import Motion, VotingSession, VoteOption, Vote
from apps.accounts.models import User

class MotionForm(forms.ModelForm):
    """Form for creating and editing motions"""
    
    class Meta:
        model = Motion
        fields = [
            'title', 'description', 'background', 'voting_type', 
            'required_votes', 'voting_deadline', 'seconded_by'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'rows': 6,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'background': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'voting_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'required_votes': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'voting_deadline': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'type': 'datetime-local'
            }),
            'seconded_by': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seconded_by'].queryset = User.objects.filter(is_active=True)
        self.fields['seconded_by'].required = False
    
    def clean_voting_deadline(self):
        """Validate that voting deadline is in the future"""
        deadline = self.cleaned_data.get('voting_deadline')
        if deadline and deadline <= timezone.now():
            raise forms.ValidationError('Voting deadline must be in the future.')
        return deadline
    
    def clean_required_votes(self):
        """Validate required votes based on voting type"""
        voting_type = self.cleaned_data.get('voting_type')
        required_votes = self.cleaned_data.get('required_votes')
        
        if voting_type and required_votes:
            if voting_type == 'simple_majority' and required_votes < 1:
                raise forms.ValidationError('Simple majority requires at least 1 vote.')
            elif voting_type == 'qualified_majority' and required_votes < 2:
                raise forms.ValidationError('Qualified majority requires at least 2 votes.')
            elif voting_type == 'two_thirds' and required_votes < 3:
                raise forms.ValidationError('Two-thirds majority requires at least 3 votes.')
        
        return required_votes

class VoteForm(forms.ModelForm):
    """Form for casting votes"""
    
    class Meta:
        model = Vote
        fields = ['choice', 'vote_option', 'comment', 'is_anonymous']
        widgets = {
            'choice': forms.RadioSelect(attrs={
                'class': 'space-y-2'
            }),
            'vote_option': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'comment': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Optional: Explain your vote...'
            }),
            'is_anonymous': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 rounded focus:ring-green-500'
            }),
        }
    
    def __init__(self, motion, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.motion = motion
        
        # Filter vote options based on motion
        if motion and motion.vote_options.exists():
            self.fields['vote_option'].queryset = motion.vote_options.all()
            self.fields['vote_option'].required = False
        else:
            # For simple yes/no/abstain votes, hide vote options
            del self.fields['vote_option']
    
    def clean(self):
        """Validate vote based on motion status and deadline"""
        cleaned_data = super().clean()
        
        if self.motion:
            # Check if voting is open
            if not self.motion.is_voting_open:
                raise forms.ValidationError('Voting is not currently open for this motion.')
            
            # Check if deadline has passed
            if timezone.now() > self.motion.voting_deadline:
                raise forms.ValidationError('Voting deadline has passed.')
        
        return cleaned_data

class VotingSessionForm(forms.ModelForm):
    """Form for creating voting sessions"""
    
    class Meta:
        model = VotingSession
        fields = [
            'title', 'description', 'meeting', 'start_time', 
            'end_time', 'eligible_voters'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'meeting': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'start_time': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'type': 'datetime-local'
            }),
            'end_time': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'type': 'datetime-local'
            }),
            'eligible_voters': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['eligible_voters'].queryset = User.objects.filter(is_active=True)
        self.fields['meeting'].required = False
    
    def clean(self):
        """Validate session timing"""
        cleaned_data = super().clean()
        
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError('End time must be after start time.')
            
            if start_time <= timezone.now():
                raise forms.ValidationError('Start time must be in the future.')
        
        return cleaned_data

class VoteOptionForm(forms.ModelForm):
    """Form for adding vote options to motions"""
    
    class Meta:
        model = VoteOption
        fields = ['text', 'order']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

class MotionSearchForm(forms.Form):
    """Form for searching motions"""
    
    SEARCH_CHOICES = [
        ('title', 'Title'),
        ('description', 'Description'),
        ('background', 'Background'),
        ('all', 'All Fields'),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Search motions...'
        })
    )
    
    search_type = forms.ChoiceField(choices=SEARCH_CHOICES, required=False)
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Motion.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    voting_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Motion.VOTING_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'type': 'date'
        })
    )
