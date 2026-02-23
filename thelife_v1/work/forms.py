from django import forms
from .models import WorkProfile, Project, Deliverable, WorkLog


class WorkProfileForm(forms.ModelForm):
    class Meta:
        model = WorkProfile
        fields = ['current_role', 'organization', 'department',
                  'work_start_time', 'work_end_time', 'responsibilities']
        widgets = {
            'current_role': forms.TextInput(attrs={'class': 'form-input'}),
            'organization': forms.TextInput(attrs={'class': 'form-input'}),
            'department': forms.TextInput(attrs={'class': 'form-input'}),
            'work_start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'work_end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'responsibilities': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'status', 'priority',
                  'start_date', 'target_date', 'tags']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'priority': forms.Select(attrs={'class': 'form-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'target_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'tags': forms.TextInput(attrs={'class': 'form-input',
                                           'placeholder': 'backend, api, urgent'}),
        }


class DeliverableForm(forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = ['title', 'description', 'status', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


class WorkLogForm(forms.ModelForm):
    class Meta:
        model = WorkLog
        fields = ['project', 'deliverable', 'date', 'title',
                  'description', 'hours_spent', 'status_tag', 'blockers']
        widgets = {
            'project': forms.Select(attrs={
                'class': 'form-input',
                'hx-get': '/work/deliverables-for-project/',
                'hx-target': '#id_deliverable',
                'hx-trigger': 'change',
            }),
            'deliverable': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'title': forms.TextInput(attrs={'class': 'form-input',
                                            'placeholder': 'What did you work on?'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'hours_spent': forms.NumberInput(attrs={'class': 'form-input',
                                                     'step': '0.25', 'min': '0'}),
            'status_tag': forms.TextInput(attrs={'class': 'form-input',
                                                  'placeholder': 'completed, in-progress, blocked'}),
            'blockers': forms.Textarea(attrs={'class': 'form-input', 'rows': 2,
                                              'placeholder': 'Any blockers?'}),
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['project'].queryset = Project.objects.filter(user=user, status='active')
            self.fields['deliverable'].queryset = Deliverable.objects.none()
            if self.data.get('project'):
                try:
                    self.fields['deliverable'].queryset = Deliverable.objects.filter(
                        project_id=self.data['project'])
                except (ValueError, TypeError):
                    pass
            elif self.instance.pk and self.instance.project_id:
                self.fields['deliverable'].queryset = Deliverable.objects.filter(
                    project=self.instance.project)
