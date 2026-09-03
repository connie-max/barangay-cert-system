from django.contrib import admin
from .models import CertificateType, Resident, CertificateRequest

admin.site.register(CertificateType)
admin.site.register(Resident)
admin.site.register(CertificateRequest)