from django import forms
from django.utils import timezone
from .models import Meeting, AgendaItem, MeetingMinutes
from apps.accounts.models import User

class CreateMeetingForm(forms.ModelForm):
    """Form for creating new meetings"""
    
    class Meta:
        model = Meeting
        fields = [
            'title', 'description', 'meeting_type', 'scheduled_date', 
            'scheduled_end_time', 'location', 'is_virtual', 'virtual_platform', 
            'virtual_meeting_url', 'virtual_meeting_id', 'virtual_meeting_password',
            'virtual_dial_in', 'agenda', 'attendees', 'required_attendees'
        ]
        widgets = {
            'scheduled_date': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'type': 'datetime-local'
            }),
            'scheduled_end_time': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'type': 'datetime-local'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'agenda': forms.Textarea(attrs={
                'rows': 6,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'virtual_meeting_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'https://zoom.us/j/123456789'
            }),
            'virtual_meeting_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': '123 456 7890'
            }),
            'virtual_meeting_password': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'meeting password (optional)'
            }),
            'virtual_dial_in': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': '+1 234 567 8901'
            }),
            'attendees': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'required_attendees': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attendees'].queryset = User.objects.filter(is_active=True)
        self.fields['required_attendees'].queryset = User.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate that end time is after start time
        start_time = cleaned_data.get('scheduled_date')
        end_time = cleaned_data.get('scheduled_end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError('End time must be after start time.')
        
        # Validate that meeting is scheduled in the future
        if start_time and start_time <= timezone.now():
            raise forms.ValidationError('Meeting must be scheduled for a future date and time.')
        
        return cleaned_data

class AgendaForm(forms.ModelForm):
    """Form for creating/editing agenda items"""
    
    class Meta:
        model = AgendaItem
        fields = ['title', 'description', 'priority', 'order', 'estimated_duration', 'attachment']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'estimated_duration': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

class MeetingMinutesForm(forms.ModelForm):
    """Form for creating/editing meeting minutes"""
    
    class Meta:
        model = MeetingMinutes
        fields = ['content', 'action_items', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 12,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'action_items': forms.Textarea(attrs={
                'rows': 6,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

class MeetingSearchForm(forms.Form):
    """Form for searching meetings"""
    
    SEARCH_CHOICES = [
        ('title', 'Title'),
        ('description', 'Description'),
        ('agenda', 'Agenda'),
        ('all', 'All Fields'),
    ]
    
    search_type = forms.ChoiceField(choices=SEARCH_CHOICES, required=False)
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Search meetings...'
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
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Meeting.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
