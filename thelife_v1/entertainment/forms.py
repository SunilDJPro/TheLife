from django import forms
from .models import EntertainmentLog


class EntertainmentLogForm(forms.ModelForm):
    class Meta:
        model = EntertainmentLog
        fields = ['title', 'description', 'entertainment_type', 'venue',
                  'date', 'start_time', 'duration_minutes', 'rating', 'is_scheduled']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'What did you watch/play?'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'entertainment_type': forms.Select(attrs={'class': 'form-input'}),
            'venue': forms.TextInput(attrs={'class': 'form-input',
                                            'placeholder': 'e.g., HT-Screen 1 Dolby Atmos'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'rating': forms.Select(attrs={'class': 'form-input'}),
            'is_scheduled': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
