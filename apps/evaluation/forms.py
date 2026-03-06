from django import forms
from django.utils import timezone
from .models import (
    EvaluationTemplate, EvaluationQuestion, Evaluation, EvaluationAnswer, 
    EvaluationComment, EvaluationSummary, EvaluationCycle
)
from apps.accounts.models import User

class EvaluationTemplateForm(forms.ModelForm):
    """Enterprise-grade form for creating and editing evaluation templates"""
    
    class Meta:
        model = EvaluationTemplate
        fields = [
            'name', 'description', 'evaluation_type', 'framework', 'target_audience',
            'evaluation_frequency', 'confidentiality_level', 'evaluator_instructions',
            'evaluatee_guidance', 'max_score', 'passing_score', 'scoring_scale',
            'regulatory_requirements', 'data_retention_period', 'requires_calibration',
            'allows_self_nomination', 'anonymous_feedback', 'is_active', 'is_public',
            'approval_required'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Template name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Template description'
            }),
            'evaluation_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'framework': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'target_audience': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., Board Members, Executives'
            }),
            'evaluation_frequency': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., Annual, Semi-Annual, Quarterly'
            }),
            'confidentiality_level': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'evaluator_instructions': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Instructions for evaluators'
            }),
            'evaluatee_guidance': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Guidance for evaluatees'
            }),
            'max_score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Maximum score'
            }),
            'passing_score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Passing score'
            }),
            'scoring_scale': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'JSON format scoring scale definitions'
            }),
            'regulatory_requirements': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Regulatory or compliance requirements'
            }),
            'data_retention_period': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Retention period in months'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        max_score = cleaned_data.get('max_score')
        passing_score = cleaned_data.get('passing_score')
        
        if max_score and passing_score:
            if passing_score > max_score:
                raise forms.ValidationError('Passing score cannot be greater than maximum score.')
        
        return cleaned_data

class EvaluationQuestionForm(forms.ModelForm):
    """Form for creating and editing evaluation questions"""
    
    class Meta:
        model = EvaluationQuestion
        fields = [
            'text', 'question_type', 'order', 'weight', 'max_score',
            'choices', 'is_required', 'category'
        ]
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Question text'
            }),
            'question_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Order'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Weight'
            }),
            'max_score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Maximum score'
            }),
            'choices': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'JSON format choices for multiple choice questions'
            }),
            'category': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Category (optional)'
            }),
        }

    def clean_choices(self):
        """Validate choices JSON format"""
        choices = self.cleaned_data.get('choices')
        question_type = self.cleaned_data.get('question_type')
        
        if question_type == 'multiple_choice' and not choices:
            raise forms.ValidationError('Choices are required for multiple choice questions.')
        
        if choices:
            try:
                import json
                parsed_choices = json.loads(choices)
                if not isinstance(parsed_choices, list):
                    raise forms.ValidationError('Choices must be a JSON array.')
            except json.JSONDecodeError:
                raise forms.ValidationError('Invalid JSON format for choices.')
        
        return choices

class EvaluationForm(forms.ModelForm):
    """Form for creating and editing evaluations"""
    
    class Meta:
        model = Evaluation
        fields = [
            'template', 'evaluator', 'evaluatee', 'evaluation_period',
            'start_date', 'end_date'
        ]
        widgets = {
            'template': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'evaluator': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'evaluatee': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'evaluation_period': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., Q1 2024, Annual 2024'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users for evaluator and evaluatee fields
        board_members = User.objects.filter(role='board_member')
        self.fields['evaluator'].queryset = board_members
        self.fields['evaluatee'].queryset = board_members

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        evaluator = cleaned_data.get('evaluator')
        evaluatee = cleaned_data.get('evaluatee')
        
        # Validate date logic
        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError('End date must be after start date.')
        
        # Validate evaluator/evaluatee relationship
        if evaluator and evaluatee and evaluator == evaluatee:
            raise forms.ValidationError('Evaluator and evaluatee cannot be the same person.')
        
        return cleaned_data

class EvaluationAnswerForm(forms.ModelForm):
    """Form for answering evaluation questions"""
    
    class Meta:
        model = EvaluationAnswer
        fields = ['text_answer', 'numeric_answer', 'choice_answer', 'score', 'comments']
        widgets = {
            'text_answer': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Your answer'
            }),
            'numeric_answer': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Numeric answer'
            }),
            'choice_answer': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'score': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Score'
            }),
            'comments': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Additional comments (optional)'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        
        if self.question:
            # Configure form based on question type
            if self.question.question_type == 'rating':
                self.fields['numeric_answer'].widget = forms.Select(
                    choices=[(i, i) for i in range(1, 6)],
                    attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'}
                )
            elif self.question.question_type == 'yes_no':
                self.fields['choice_answer'].widget = forms.Select(
                    choices=[('yes', 'Yes'), ('no', 'No')],
                    attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'}
                )
            elif self.question.question_type == 'multiple_choice':
                if self.question.choices:
                    import json
                    choices = json.loads(self.question.choices)
                    self.fields['choice_answer'].widget = forms.Select(
                        choices=[(choice, choice) for choice in choices],
                        attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'}
                    )
            
            # Set required fields
            if self.question.question_type == 'text':
                self.fields['text_answer'].required = self.question.is_required
            elif self.question.question_type in ['rating', 'numeric']:
                self.fields['numeric_answer'].required = self.question.is_required
            elif self.question.question_type in ['yes_no', 'multiple_choice']:
                self.fields['choice_answer'].required = self.question.is_required

    def clean_score(self):
        """Validate score against question max score"""
        score = self.cleaned_data.get('score')
        
        if self.question and score is not None:
            if self.question.max_score and score > self.question.max_score:
                raise forms.ValidationError(f'Score cannot exceed maximum score of {self.question.max_score}.')
        
        return score

class EvaluationCommentForm(forms.ModelForm):
    """Form for adding comments to evaluations"""
    
    class Meta:
        model = EvaluationComment
        fields = ['comment_type', 'text', 'is_public', 'is_anonymous']
        widgets = {
            'comment_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'text': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Your comment'
            }),
        }

class EvaluationSummaryForm(forms.ModelForm):
    """Form for creating evaluation summaries"""
    
    class Meta:
        model = EvaluationSummary
        fields = [
            'overall_rating', 'performance_level', 'strengths', 'areas_for_improvement',
            'recommendations', 'short_term_goals', 'long_term_goals',
            'follow_up_required', 'follow_up_date', 'follow_up_assigned_to'
        ]
        widgets = {
            'overall_rating': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'step': '0.1',
                'min': '0',
                'max': '5'
            }),
            'performance_level': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., Exceeds Expectations, Meets Expectations, Needs Improvement'
            }),
            'strengths': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Key strengths identified'
            }),
            'areas_for_improvement': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Areas needing improvement'
            }),
            'recommendations': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Actionable recommendations'
            }),
            'short_term_goals': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Goals for next 3-6 months'
            }),
            'long_term_goals': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Goals for next 12 months'
            }),
            'follow_up_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'follow_up_assigned_to': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users for follow-up assignment
        self.fields['follow_up_assigned_to'].queryset = User.objects.filter(
            role__in=['board_member', 'company_secretary']
        )

class EvaluationCycleForm(forms.ModelForm):
    """Form for creating and managing evaluation cycles"""
    
    class Meta:
        model = EvaluationCycle
        fields = [
            'name', 'description', 'start_date', 'end_date', 'template',
            'auto_assign_evaluators', 'reminder_frequency', 'participants'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Cycle name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Cycle description'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'template': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'reminder_frequency': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Days between reminders'
            }),
            'participants': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter participants to board members
        self.fields['participants'].queryset = User.objects.filter(role='board_member')

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError('End date must be after start date.')
        
        return cleaned_data
