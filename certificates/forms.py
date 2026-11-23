from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CertificateRequest, CEDULA_FIELDS, CIVIL_STATUS_CHOICES

class CertificateRequestForm(forms.ModelForm):
    class Meta:
        model = CertificateRequest
        # The extra fields are on the form so Django saves them. The page
        # only shows them when their certificate type is picked (see the
        # show/hide script in home.html and request_form.html).
        fields = ['certificate_type', 'financing_company', 'occupation',
                  'civil_status', 'date_of_birth', 'place_of_birth',
                  'citizenship', 'tin', 'annual_income']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'financing_company': forms.TextInput(attrs={'placeholder': 'e.g. BPI Auto Loan'}),
            'occupation': forms.TextInput(attrs={'placeholder': 'e.g. Teacher'}),
            'place_of_birth': forms.TextInput(attrs={'placeholder': 'e.g. Nabunturan, Davao de Oro'}),
            'citizenship': forms.TextInput(attrs={'placeholder': 'e.g. Filipino'}),
            'tin': forms.TextInput(attrs={'placeholder': 'e.g. 123-456-789-000'}),
            'annual_income': forms.NumberInput(attrs={'placeholder': 'e.g. 120000', 'min': '0', 'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The civil status list starts with a clear instruction, not "---------".
        self.fields['civil_status'].choices = [('', '- Select civil status -')] + list(CIVIL_STATUS_CHOICES)

    def clean(self):
        cleaned_data = super().clean()
        cert_type = cleaned_data.get('certificate_type')
        if not cert_type:
            return cleaned_data
        cert_name = str(cert_type)
        # A Loan needs the financing company name.
        if cert_name == 'Certificate of Loan' and not cleaned_data.get('financing_company'):
            self.add_error('financing_company',
                           "Name of Financing/Loan Company is required for this certificate type.")
        # A Cedula is printed with the resident's personal details, so all
        # of them are required. Every other certificate leaves them blank.
        if cert_name == 'Cedula':
            for field_name, label in CEDULA_FIELDS:
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, f"{label} is required for a Cedula.")
            # Annual income is required too (it sets the Cedula fee), but
            # P0 is a real answer (no income), so check for "empty", not "zero".
            income = cleaned_data.get('annual_income')
            if income is None:
                self.add_error('annual_income', "Annual Income is required for a Cedula.")
            elif income < 0:
                self.add_error('annual_income', "Annual Income cannot be negative.")
        return cleaned_data


class ResidentSignUpForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    address = forms.CharField(max_length=255)
    contact_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'full_name', 'address', 'contact_number']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email