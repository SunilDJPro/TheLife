from django import forms
from .models import Skill, SkillResource, SkillSession


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'description', 'status', 'priority', 'target_completion_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Computer Architecture'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'priority': forms.Select(attrs={'class': 'form-input'}),
            'target_completion_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


class SkillResourceForm(forms.ModelForm):
    class Meta:
        model = SkillResource
        fields = ['resource_type', 'title', 'url', 'author',
                  'total_pages', 'total_sections', 'total_duration_hours']
        widgets = {
            'resource_type': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'author': forms.TextInput(attrs={'class': 'form-input'}),
            'total_pages': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'total_sections': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'total_duration_hours': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5'}),
        }


class SkillSessionForm(forms.ModelForm):
    class Meta:
        model = SkillSession
        fields = ['date', 'start_time', 'end_time',
                  'start_page', 'end_page',
                  'sections_covered', 'sections_count',
                  'video_timestamp_start', 'video_timestamp_end',
                  'notes', 'rating']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'start_page': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'end_page': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'sections_covered': forms.TextInput(attrs={'class': 'form-input',
                                                        'placeholder': 'e.g., Ch 3.1 - 3.4'}),
            'sections_count': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'video_timestamp_start': forms.TextInput(attrs={'class': 'form-input',
                                                             'placeholder': '0:00:00'}),
            'video_timestamp_end': forms.TextInput(attrs={'class': 'form-input',
                                                           'placeholder': '1:30:00'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'rating': forms.Select(attrs={'class': 'form-input'}),
        }
