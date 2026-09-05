from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CertificateRequest

class CertificateRequestForm(forms.ModelForm):
    class Meta:
        model = CertificateRequest
        fields = ['certificate_type']


class ResidentSignUpForm(UserCreationForm):
    address = forms.CharField(max_length=255)
    contact_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'address', 'contact_number']