from django import forms
from django.utils import timezone
from .models import ActivityLog, ActivityCategory, ActivityType, RecurringTask


class ActivityLogForm(forms.ModelForm):
    """Form for logging an activity."""

    category = forms.ModelChoiceField(
        queryset=ActivityCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-input',
            'hx-get': '/activities/types/',
            'hx-target': '#id_activity_type',
            'hx-trigger': 'change',
            'hx-swap': 'innerHTML',
        })
    )

    class Meta:
        model = ActivityLog
        fields = ['category', 'activity_type', 'date', 'start_time', 'end_time',
                  'title', 'description', 'notes', 'productivity_rating', 'metadata']
        widgets = {
            'activity_type': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'What did you do?',
                'autocomplete': 'off',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input', 'rows': 2,
                'placeholder': 'Brief description...',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-input', 'rows': 2,
                'placeholder': 'Reflections, learnings, or notes...',
            }),
            'productivity_rating': forms.Select(attrs={'class': 'form-input'}),
            'metadata': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.initial.get('date'):
            self.initial['date'] = today
        # activity_type starts empty, populated via HTMX
        self.fields['activity_type'].queryset = ActivityType.objects.none()
        if self.data.get('category'):
            try:
                cat_id = self.data.get('category')
                self.fields['activity_type'].queryset = ActivityType.objects.filter(
                    category_id=cat_id, is_active=True)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.category_id:
            self.fields['activity_type'].queryset = ActivityType.objects.filter(
                category=self.instance.category, is_active=True)


class QuickLogForm(forms.Form):
    """Simplified quick-log form for catch-up prompts."""
    category = forms.ModelChoiceField(
        queryset=ActivityCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-input form-input-sm'})
    )
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input form-input-sm',
            'placeholder': 'What did you do?',
        })
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-input form-input-sm', 'type': 'time'})
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-input form-input-sm', 'type': 'time'})
    )
    productivity_rating = forms.ChoiceField(
        choices=ActivityLog.PRODUCTIVITY_CHOICES,
        initial=3,
        widget=forms.Select(attrs={'class': 'form-input form-input-sm'})
    )


class RecurringTaskForm(forms.ModelForm):
    """Form for creating recurring tasks."""
    class Meta:
        model = RecurringTask
        fields = ['category', 'activity_type', 'title', 'description',
                  'frequency', 'day_of_week', 'day_of_month', 'start_time', 'end_time']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-input'}),
            'activity_type': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'frequency': forms.Select(attrs={'class': 'form-input'}),
            'day_of_week': forms.Select(attrs={'class': 'form-input'},
                                         choices=[(None, '---')] + [(i, d) for i, d in
                                                   enumerate(['Monday', 'Tuesday', 'Wednesday',
                                                              'Thursday', 'Friday', 'Saturday', 'Sunday'])]),
            'day_of_month': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 31}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
        }


class MetadataFitnessForm(forms.Form):
    """Extra fields for Fitness activities."""
    intensity = forms.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('extreme', 'Extreme')],
        widget=forms.Select(attrs={'class': 'form-input form-input-sm'}),
        required=False,
    )
    sets = forms.IntegerField(required=False, widget=forms.NumberInput(
        attrs={'class': 'form-input form-input-sm', 'placeholder': 'Sets'}))
    reps = forms.IntegerField(required=False, widget=forms.NumberInput(
        attrs={'class': 'form-input form-input-sm', 'placeholder': 'Reps'}))


class MetadataMealForm(forms.Form):
    """Extra fields for Meal activities."""
    meal_type = forms.ChoiceField(
        choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'),
                 ('dinner', 'Dinner'), ('snack', 'Snack')],
        widget=forms.Select(attrs={'class': 'form-input form-input-sm'}),
    )
    home_cooked = forms.BooleanField(required=False, widget=forms.CheckboxInput(
        attrs={'class': 'form-checkbox'}))


class MetadataCommuteForm(forms.Form):
    """Extra fields for Commute activities."""
    mode = forms.ChoiceField(
        choices=[('drive', 'Drive'), ('public_transit', 'Public Transit'),
                 ('walk', 'Walk'), ('ride', 'Ride'), ('bike', 'Bike')],
        widget=forms.Select(attrs={'class': 'form-input form-input-sm'}),
        required=False,
    )
    from_location = forms.CharField(max_length=100, required=False, widget=forms.TextInput(
        attrs={'class': 'form-input form-input-sm', 'placeholder': 'From'}))
    to_location = forms.CharField(max_length=100, required=False, widget=forms.TextInput(
        attrs={'class': 'form-input form-input-sm', 'placeholder': 'To'}))
