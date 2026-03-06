from django import forms
from django.utils import timezone
from .models import (
    DiscussionForum, DiscussionThread, DiscussionPost, DiscussionPoll, PollOption,
    DiscussionSubscription, DiscussionTag, ThreadTag
)
from apps.accounts.models import User

class DiscussionForumForm(forms.ModelForm):
    """Form for creating and editing discussion forums"""
    
    class Meta:
        model = DiscussionForum
        fields = [
            'name', 'description', 'forum_type', 'access_level',
            'is_active', 'is_moderated', 'allow_attachments', 'allow_polls',
            'order', 'icon'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Forum name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Forum description'
            }),
            'forum_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'access_level': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Display order'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Font Awesome icon class (e.g., fas fa-comments)'
            }),
        }

class DiscussionThreadForm(forms.ModelForm):
    """Form for creating and editing discussion threads"""
    
    tags = forms.ModelMultipleChoiceField(
        queryset=DiscussionTag.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    class Meta:
        model = DiscussionThread
        fields = [
            'forum', 'title', 'content', 'priority', 'is_anonymous',
            'is_pinned', 'is_locked'
        ]
        widgets = {
            'forum': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Thread title'
            }),
            'content': forms.Textarea(attrs={
                'rows': 6,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Thread content'
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter forums based on user access
        if user and user.role not in ['company_secretary', 'it_administrator']:
            self.fields['forum'].queryset = DiscussionForum.objects.filter(
                access_level='public'
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle tags
        if commit:
            instance.save()
            
            # Clear existing tags
            instance.thread_tags.all().delete()
            
            # Add new tags
            for tag in self.cleaned_data.get('tags', []):
                ThreadTag.objects.create(thread=instance, tag=tag)
                # Increment usage count
                tag.usage_count += 1
                tag.save()
        
        return instance

class DiscussionPostForm(forms.ModelForm):
    """Form for creating discussion posts and replies"""
    
    parent_post = forms.ModelChoiceField(
        queryset=DiscussionPost.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    class Meta:
        model = DiscussionPost
        fields = ['content', 'is_anonymous']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Your message...'
            }),
        }

    def __init__(self, *args, **kwargs):
        thread = kwargs.pop('thread', None)
        parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)
        
        if thread:
            self.instance.thread = thread
            
            # Set parent post options for replies
            if parent:
                self.fields['parent_post'].queryset = DiscussionPost.objects.filter(
                    thread=thread,
                    post_type='original'
                )
                self.fields['parent_post'].initial = parent
            else:
                self.fields['parent_post'].queryset = DiscussionPost.objects.filter(
                    thread=thread,
                    post_type='original'
                )

class DiscussionPollForm(forms.ModelForm):
    """Form for creating discussion polls"""
    
    options = forms.CharField(
        help_text="Enter each option on a new line",
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Option 1\nOption 2\nOption 3'
        })
    )
    
    class Meta:
        model = DiscussionPoll
        fields = [
            'question', 'description', 'allow_multiple_choices',
            'is_anonymous', 'ends_at'
        ]
        widgets = {
            'question': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Poll question'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Poll description (optional)'
            }),
            'ends_at': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def clean_ends_at(self):
        ends_at = self.cleaned_data.get('ends_at')
        if ends_at and ends_at <= timezone.now():
            raise forms.ValidationError("End time must be in the future.")
        return ends_at

    def clean_options(self):
        options = self.cleaned_data.get('options', '')
        option_list = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        if len(option_list) < 2:
            raise forms.ValidationError("Poll must have at least 2 options.")
        
        if len(option_list) > 10:
            raise forms.ValidationError("Poll cannot have more than 10 options.")
        
        return option_list

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Create poll options
            options = self.cleaned_data.get('options', [])
            for i, option_text in enumerate(options):
                PollOption.objects.create(
                    poll=instance,
                    text=option_text,
                    order=i
                )
        
        return instance

class PollVoteForm(forms.Form):
    """Form for voting in polls"""
    
    def __init__(self, poll, *args, **kwargs):
        self.poll = poll
        super().__init__(*args, **kwargs)
        
        if poll.allow_multiple_choices:
            self.fields['options'] = forms.ModelMultipleChoiceField(
                queryset=poll.options.all(),
                widget=forms.CheckboxSelectMultiple,
                label="Select your choices"
            )
        else:
            self.fields['options'] = forms.ModelChoiceField(
                queryset=poll.options.all(),
                widget=forms.RadioSelect,
                label="Select your choice"
            )

class DiscussionSubscriptionForm(forms.ModelForm):
    """Form for managing discussion subscriptions"""
    
    class Meta:
        model = DiscussionSubscription
        fields = ['subscription_type']
        widgets = {
            'subscription_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            })
        }

class DiscussionTagForm(forms.ModelForm):
    """Form for creating and editing discussion tags"""
    
    class Meta:
        model = DiscussionTag
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Tag name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Tag description'
            }),
            'color': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '#007bff'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            return name.lower().strip()
        return name

class DiscussionSearchForm(forms.Form):
    """Form for searching discussions"""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search discussions...'
        })
    )
    
    forum = forms.ModelChoiceField(
        queryset=DiscussionForum.objects.filter(is_active=True),
        required=False,
        empty_label="All Forums",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    author = forms.ModelChoiceField(
        queryset=User.objects.filter(role='board_member'),
        required=False,
        empty_label="All Authors",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    priority = forms.ChoiceField(
        choices=[('', 'All Priorities')] + DiscussionThread.PRIORITY_LEVELS,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + DiscussionThread.STATUS_CHOICES,
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
    
    tags = forms.ModelMultipleChoiceField(
        queryset=DiscussionTag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

class PostEditForm(forms.ModelForm):
    """Form for editing discussion posts"""
    
    edit_reason = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Reason for editing'
        })
    )
    
    class Meta:
        model = DiscussionPost
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Updated content'
            }),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_edited = True
        instance.edited_at = timezone.now()
        instance.edited_reason = self.cleaned_data.get('edit_reason')
        
        if commit:
            instance.save()
        
        return instance
