from django.db import models
from django.contrib.auth.models import User

CERTIFICATE_REQUIREMENTS = {
    "Certificate of Residency": [],
    "Certificate of Barangay Clearance": [],
    "Certificate of Cash Assistance": ["Valid ID", "Photo of 3 Signatures"],
    "Certificate of Medical": [],
    "Certificate of Indigency": [],
    "Cedula": [],
    "Certificate of Burial Assistance": ["Valid ID", "Photo of 3 Signatures"],
    "Certificate of Loan": [],
    "Certificate of Low Income": [],
    "Certificate of Burial": [],
}

CERTIFICATE_TEXT_FIELDS = {
    "Certificate of Loan": {
        "field_name": "financing_company",
        "label": "Name of Financing/Loan Company",
    },
}

class CertificateType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Resident(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150, default='')
    address = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.full_name or self.user.username


class CertificateRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('pending_verification', 'Pending Verification'),
        ('paid', 'Paid'),
    ]

    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    certificate_type = models.ForeignKey(CertificateType, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_reference = models.CharField(max_length=100, blank=True)
    financing_company = models.CharField(max_length=150, blank=True, null=True)
    date_requested = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.resident} - {self.certificate_type} ({self.status})"
    
class RequestAttachment(models.Model):
    request = models.ForeignKey(
        CertificateRequest,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    label = models.CharField(max_length=100)
    image = models.ImageField(upload_to='requirements/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label} for request #{self.request.id}"