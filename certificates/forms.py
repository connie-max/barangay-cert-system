from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CertificateRequest

class CertificateRequestForm(forms.ModelForm):
    class Meta:
        model = CertificateRequest
        fields = ['certificate_type']

    def clean(self):
        from .models import CERTIFICATE_TEXT_FIELDS
        cleaned_data = super().clean()
        cert_type = cleaned_data.get('certificate_type')
        if cert_type and str(cert_type) in CERTIFICATE_TEXT_FIELDS:
            field_info = CERTIFICATE_TEXT_FIELDS[str(cert_type)]
            if not self.data.get(field_info['field_name']):
                self.add_error(None, f"{field_info['label']} is required for this certificate type.")
        return cleaned_data


class ResidentSignUpForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
    address = forms.CharField(max_length=255)
    contact_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'full_name', 'address', 'contact_number']