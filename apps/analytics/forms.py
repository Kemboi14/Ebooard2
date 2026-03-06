from django import forms
from .models import AnalyticsMetric, AnalyticsDashboard, AnalyticsWidget, AnalyticsReport


class AnalyticsMetricForm(forms.ModelForm):
    """Form for creating/editing analytics metrics"""

    class Meta:
        model = AnalyticsMetric
        fields = [
            'metric_type', 'name', 'description', 'frequency',
            'is_active', 'target_value', 'unit'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Metric name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Metric description'
            }),
            'target_value': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Target value (optional)'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Unit (e.g., %, count, hours)'
            }),
        }


class AnalyticsDashboardForm(forms.ModelForm):
    """Form for creating/editing analytics dashboards"""

    class Meta:
        model = AnalyticsDashboard
        fields = ['name', 'description', 'slug', 'is_public', 'allowed_roles']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Dashboard name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Dashboard description'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'URL slug'
            }),
        }


class AnalyticsWidgetForm(forms.ModelForm):
    """Form for creating/editing dashboard widgets"""

    class Meta:
        model = AnalyticsWidget
        fields = [
            'title', 'widget_type', 'position_x', 'position_y',
            'width', 'height', 'metric', 'data_config'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Widget title'
            }),
            'position_x': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'min': 0
            }),
            'position_y': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'min': 0
            }),
            'width': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'min': 1,
                'max': 12
            }),
            'height': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'min': 1,
                'max': 12
            }),
            'data_config': forms.Textarea(attrs={
                'rows': 5,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'JSON configuration for data source'
            }),
        }


class AnalyticsReportForm(forms.ModelForm):
    """Form for generating analytics reports"""

    class Meta:
        model = AnalyticsReport
        fields = ['title', 'report_type', 'format', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Report title'
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


class AnalyticsFilterForm(forms.Form):
    """Form for filtering analytics data"""

    date_range = forms.ChoiceField(
        choices=[
            ('7d', 'Last 7 days'),
            ('30d', 'Last 30 days'),
            ('90d', 'Last 90 days'),
            ('1y', 'Last year'),
            ('custom', 'Custom range'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

    metric_types = forms.MultipleChoiceField(
        choices=[
            ('attendance', 'Meeting Attendance'),
            ('participation', 'Participation'),
            ('engagement', 'Engagement'),
            ('documents', 'Document Activity'),
            ('voting', 'Voting Activity'),
            ('discussions', 'Discussion Activity'),
            ('notifications', 'Notification Activity'),
            ('system_usage', 'System Usage'),
        ],
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

    users = forms.MultipleChoiceField(
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate users dynamically
        from apps.accounts.models import User
        self.fields['users'].choices = [
            (user.id, user.get_full_name())
            for user in User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        ]
