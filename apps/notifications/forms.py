from django import forms
from django.utils import timezone
from .models import (
    Notification, NotificationPreference, NotificationTemplate, NotificationBatch, NotificationChannel
)
from apps.accounts.models import User

class NotificationForm(forms.ModelForm):
    """Form for creating individual notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'recipient', 'title', 'message', 'notification_type', 'priority',
            'action_url', 'expires_at', 'metadata'
        ]
        widgets = {
            'recipient': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Notification title'
            }),
            'message': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Notification message'
            }),
            'notification_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'action_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Action URL (optional)'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise forms.ValidationError("Expiration time must be in the future.")
        return expires_at

class NotificationPreferenceForm(forms.ModelForm):
    """Form for managing user notification preferences"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_meeting_reminders', 'email_voting_notifications', 'email_document_updates',
            'email_discussion_replies', 'email_risk_alerts', 'email_audit_alerts', 'email_system_updates',
            'in_app_meeting_reminders', 'in_app_voting_notifications', 'in_app_document_updates',
            'in_app_discussion_replies', 'in_app_risk_alerts', 'in_app_audit_alerts', 'in_app_system_updates',
            'email_frequency', 'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end'
        ]
        widgets = {
            'email_frequency': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'quiet_hours_start': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'quiet_hours_end': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        quiet_hours_enabled = cleaned_data.get('quiet_hours_enabled')
        quiet_hours_start = cleaned_data.get('quiet_hours_start')
        quiet_hours_end = cleaned_data.get('quiet_hours_end')
        
        if quiet_hours_enabled and (not quiet_hours_start or not quiet_hours_end):
            raise forms.ValidationError("Both start and end times are required when quiet hours are enabled.")
        
        return cleaned_data

class NotificationTemplateForm(forms.ModelForm):
    """Form for creating and editing notification templates"""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'name', 'notification_type', 'title_template', 'message_template',
            'email_subject_template', 'email_body_template', 'default_priority',
            'default_action_url', 'description', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Template name'
            }),
            'notification_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'title_template': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Title template (e.g., "Meeting {{ meeting.title }} starts soon")'
            }),
            'message_template': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Message template (e.g., "Your meeting {{ meeting.title }} starts at {{ meeting.start_time }}")'
            }),
            'email_subject_template': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Email subject template'
            }),
            'email_body_template': forms.Textarea(attrs={
                'rows': 5,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Email body template'
            }),
            'default_priority': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'default_action_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Default action URL'
            }),
            'description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Template description'
            }),
        }

class NotificationBatchForm(forms.ModelForm):
    """Form for creating batch notifications"""
    
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role='board_member'),
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    class Meta:
        model = NotificationBatch
        fields = [
            'title', 'message', 'notification_type', 'priority', 'recipients'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Batch notification title'
            }),
            'message': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Batch notification message'
            }),
            'notification_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['recipients'].initial = self.instance.recipients.all()

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            # Save many-to-many relationship
            instance.recipients.set(self.cleaned_data['recipients'])
            instance.total_recipients = instance.recipients.count()
            instance.save(update_fields=['total_recipients'])
        
        return instance

class NotificationChannelForm(forms.ModelForm):
    """Form for managing notification channels"""
    
    class Meta:
        model = NotificationChannel
        fields = ['name', 'channel_type', 'configuration', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Channel name'
            }),
            'channel_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'configuration': forms.Textarea(attrs={
                'rows': 6,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Channel configuration (JSON format)'
            }),
        }

    def clean_configuration(self):
        configuration = self.cleaned_data.get('configuration')
        if configuration:
            try:
                import json
                json.loads(configuration)
            except json.JSONDecodeError:
                raise forms.ValidationError("Configuration must be valid JSON.")
        return configuration

class NotificationSearchForm(forms.Form):
    """Form for searching notifications"""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search notifications...'
        })
    )
    
    notification_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Notification.NOTIFICATION_TYPES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    priority = forms.ChoiceField(
        choices=[('', 'All Priorities')] + Notification.PRIORITY_LEVELS,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    is_read = forms.ChoiceField(
        choices=[('', 'All'), ('read', 'Read'), ('unread', 'Unread')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

class QuickNotificationForm(forms.Form):
    """Quick form for sending common notifications"""
    
    recipient = forms.ModelChoiceField(
        queryset=User.objects.filter(role='board_member'),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    notification_type = forms.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Notification title'
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Notification message'
        })
    )
    
    priority = forms.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        initial='normal',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    action_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Action URL (optional)'
        })
    )
