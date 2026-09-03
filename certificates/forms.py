from django import forms
from .models import CertificateRequest

class CertificateRequestForm(forms.ModelForm):
    class Meta:
        model = CertificateRequest
        fields = ['certificate_type']