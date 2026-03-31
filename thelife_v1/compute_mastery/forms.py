"""Forms for Compute Mastery — Problem CRUD and TestCase management."""
from django import forms
from django.forms import inlineformset_factory
from .models import Problem, TestCase, Tag


class ProblemForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., dp, simd, concurrency (comma-separated)',
            'class': 'form-input',
        }),
        help_text="Comma-separated tags. New tags are created automatically."
    )

    starter_code_cpp = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 10,
            'class': 'form-textarea code-input',
            'placeholder': '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    // your code here\n    return 0;\n}',
            'spellcheck': 'false',
        }),
        label="Starter Code (C++)",
    )

    class Meta:
        model = Problem
        fields = ['title', 'description', 'difficulty', 'category', 'constraints', 'hints']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Problem title'}),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea', 'rows': 12,
                'placeholder': 'Problem statement in Markdown...',
            }),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'constraints': forms.Textarea(attrs={
                'class': 'form-textarea', 'rows': 4,
                'placeholder': '1 <= n <= 10^5\n1 <= a[i] <= 10^9',
            }),
            'hints': forms.Textarea(attrs={
                'class': 'form-textarea', 'rows': 4,
                'placeholder': 'Optional hints...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Pre-fill tags
            self.fields['tags_input'].initial = ', '.join(
                t.name for t in self.instance.tags.all()
            )
            # Pre-fill starter code
            self.fields['starter_code_cpp'].initial = self.instance.starter_code.get('cpp', '')

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Build starter_code JSON
        cpp_code = self.cleaned_data.get('starter_code_cpp', '').strip()
        starter = instance.starter_code or {}
        if cpp_code:
            starter['cpp'] = cpp_code
        instance.starter_code = starter

        if commit:
            instance.save()
            # Handle tags
            self._save_tags(instance)
            self.save_m2m()
        return instance

    def _save_tags(self, instance):
        tags_text = self.cleaned_data.get('tags_input', '')
        tag_names = [t.strip().lower() for t in tags_text.split(',') if t.strip()]
        tags = []
        for name in tag_names:
            tag, _ = Tag.objects.get_or_create(
                name=name,
                defaults={'slug': name.replace(' ', '-')},
            )
            tags.append(tag)
        instance.tags.set(tags)


class TestCaseForm(forms.ModelForm):
    class Meta:
        model = TestCase
        fields = ['input_data', 'expected_output', 'is_sample', 'order',
                  'time_limit_ms', 'memory_limit_mb']
        widgets = {
            'input_data': forms.Textarea(attrs={
                'class': 'form-textarea code-input', 'rows': 4,
                'placeholder': 'stdin input...',
                'spellcheck': 'false',
            }),
            'expected_output': forms.Textarea(attrs={
                'class': 'form-textarea code-input', 'rows': 4,
                'placeholder': 'Expected stdout output...',
                'spellcheck': 'false',
            }),
            'is_sample': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'style': 'width:80px'}),
            'time_limit_ms': forms.NumberInput(attrs={'class': 'form-input', 'style': 'width:100px'}),
            'memory_limit_mb': forms.NumberInput(attrs={'class': 'form-input', 'style': 'width:100px'}),
        }


TestCaseFormSet = inlineformset_factory(
    Problem, TestCase,
    form=TestCaseForm,
    extra=2,
    can_delete=True,
)
