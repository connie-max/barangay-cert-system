from django.db import models
from django.contrib.auth.models import User

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
    date_requested = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.resident} - {self.certificate_type} ({self.status})"