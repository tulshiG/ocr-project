from django import forms

from .models import WorkReport


class WorkReportUploadForm(forms.ModelForm):
    class Meta:
        model = WorkReport
        fields = ["image"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
