from django.db import models
from django.contrib.auth.models import User

class CertificateType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Resident(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.user.username


class CertificateRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    certificate_type = models.ForeignKey(CertificateType, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date_requested = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.resident} - {self.certificate_type} ({self.status})"