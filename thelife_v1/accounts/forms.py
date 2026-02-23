import zoneinfo
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User, UserGoal

# Common timezones (sorted, deduplicated)
TIMEZONE_CHOICES = sorted(
    [(tz, tz.replace('_', ' ')) for tz in zoneinfo.available_timezones()
     if '/' in tz and not tz.startswith(('Etc/', 'SystemV/'))],
    key=lambda x: x[0]
)


class TheLifeLoginForm(AuthenticationForm):
    """Custom login form with TheLife styling."""
    username = forms.CharField(
        label='Email or Username',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your email or username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password',
        })
    )


class UserProfileForm(forms.ModelForm):
    """User profile settings form."""
    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
        initial='Asia/Kolkata',
    )

    class Meta:
        model = User
        fields = ['display_name', 'timezone', 'wake_time', 'sleep_time',
                  'log_interval_hours', 'max_active_skills', 'long_term_goals']
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-input'}),
            'wake_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'sleep_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'log_interval_hours': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 4}),
            'max_active_skills': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 5}),
            'long_term_goals': forms.Textarea(attrs={'class': 'form-input', 'rows': 4,
                                                      'placeholder': 'Describe your long-term goals...'}),
        }


class UserGoalForm(forms.ModelForm):
    """Form for adding/editing goals."""
    class Meta:
        model = UserGoal
        fields = ['title', 'description', 'target_date', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Goal title'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'target_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }