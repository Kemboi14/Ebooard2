from django import forms
from django.utils import timezone
from .models import Policy, PolicyCategory, PolicyReview, PolicyAcknowledgment
from apps.accounts.models import User

class PolicyForm(forms.ModelForm):
    """Form for creating and editing policies"""
    
    class Meta:
        model = Policy
        fields = [
            'title', 'description', 'content', 'category', 'category_type',
            'effective_date', 'review_date', 'expiry_date',
            'policy_owner', 'access_level', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Enter policy title'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Brief description of the policy'
            }),
            'content': forms.Textarea(attrs={
                'rows': 12,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Full policy content with sections, clauses, etc.'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'category_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'effective_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'review_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'policy_owner': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'access_level': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users for policy owner field
        self.fields['policy_owner'].queryset = User.objects.filter(
            role__in=['board_member', 'company_secretary', 'compliance_officer']
        )
        self.fields['policy_owner'].required = False
        
        # Add empty choice for category
        self.fields['category'].empty_label = "Select a category (optional)"
        self.fields['category'].required = False

    def clean(self):
        cleaned_data = super().clean()
        effective_date = cleaned_data.get('effective_date')
        review_date = cleaned_data.get('review_date')
        expiry_date = cleaned_data.get('expiry_date')
        
        # Validate date logic
        if effective_date and review_date:
            if review_date <= effective_date:
                raise forms.ValidationError('Review date must be after effective date.')
        
        if effective_date and expiry_date:
            if expiry_date <= effective_date:
                raise forms.ValidationError('Expiry date must be after effective date.')
        
        if review_date and expiry_date:
            if expiry_date <= review_date:
                raise forms.ValidationError('Expiry date must be after review date.')
        
        # Validate dates are not in the past (except for existing policies)
        if not self.instance.pk:  # New policy
            today = timezone.now().date()
            if effective_date and effective_date < today:
                raise forms.ValidationError('Effective date cannot be in the past for new policies.')
        
        return cleaned_data

class PolicyCategoryForm(forms.ModelForm):
    """Form for creating and editing policy categories"""
    
    class Meta:
        model = PolicyCategory
        fields = ['name', 'description', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Category name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Category description'
            }),
            'parent': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude self from parent choices to prevent circular references
        if self.instance.pk:
            self.fields['parent'].queryset = PolicyCategory.objects.exclude(
                pk=self.instance.pk
            ).exclude(
                parent__pk=self.instance.pk
            )
        else:
            self.fields['parent'].queryset = PolicyCategory.objects.all()
        
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = "No parent (root category)"

class PolicyReviewForm(forms.ModelForm):
    """Form for creating and editing policy reviews"""
    
    class Meta:
        model = PolicyReview
        fields = ['reviewer', 'review_date', 'review_type', 'findings', 'recommendations', 'action_required', 'next_review_date']
        widgets = {
            'reviewer': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'review_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'review_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'findings': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Review findings and observations'
            }),
            'recommendations': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Recommendations for improvement'
            }),
            'next_review_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users for reviewer field
        self.fields['reviewer'].queryset = User.objects.filter(
            role__in=['board_member', 'company_secretary', 'compliance_officer']
        )
        self.fields['reviewer'].required = False

class PolicySearchForm(forms.Form):
    """Form for searching policies"""
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Search policies...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=PolicyCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    category_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Policy.CATEGORY_TYPES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Policy.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    access_level = forms.ChoiceField(
        choices=[('', 'All Access Levels')] + Policy._meta.get_field('access_level').choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

class PolicyVersionForm(forms.ModelForm):
    """Form for creating new versions of existing policies"""
    
    class Meta:
        model = Policy
        fields = ['description', 'content', 'effective_date', 'review_date', 'expiry_date', 'policy_owner', 'access_level']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Updated description for this version'
            }),
            'content': forms.Textarea(attrs={
                'rows': 12,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Updated policy content'
            }),
            'effective_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'review_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'policy_owner': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'access_level': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users for policy owner field
        self.fields['policy_owner'].queryset = User.objects.filter(
            role__in=['board_member', 'company_secretary', 'compliance_officer']
        )
        self.fields['policy_owner'].required = False

    def clean(self):
        cleaned_data = super().clean()
        effective_date = cleaned_data.get('effective_date')
        review_date = cleaned_data.get('review_date')
        expiry_date = cleaned_data.get('expiry_date')
        
        # Validate date logic
        if effective_date and review_date:
            if review_date <= effective_date:
                raise forms.ValidationError('Review date must be after effective date.')
        
        if effective_date and expiry_date:
            if expiry_date <= effective_date:
                raise forms.ValidationError('Expiry date must be after effective date.')
        
        return cleaned_data
