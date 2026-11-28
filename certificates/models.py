from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Every certificate except Cedula costs the same fixed amount, so it lives
# in ONE place. If the barangay ever changes the fee, change it here only.
CERTIFICATE_FEE = Decimal('50.00')

# A Cedula (Community Tax Certificate) is priced differently: it follows
# the Local Government Code, not the flat P50. The price is a P5.00 basic
# tax, plus P1.00 for every P1,000 of the resident's annual income (whole
# thousands only). The extra tax for income never goes past P5,000, so the
# most anyone pays before interest is P5,005.
# The tax is due by the last day of February. From March onwards, the law
# (RA 7160, Sec. 161) adds 2% interest for every month (or part of a
# month) it is late, until it is paid. Example: P120,000 income in
# November -> base P5 + P120 = P125, 9 months late x 2% = P22.50,
# total P147.50.
CEDULA_BASIC_FEE = Decimal('5.00')
CEDULA_PER_THOUSAND = Decimal('1.00')
CEDULA_MAX_ADDITIONAL = Decimal('5000.00')
CEDULA_LATE_RATE = Decimal('0.02')  # 2% per month late


def cedula_months_late(on_date=None):
    # How many months late the Cedula tax is, against the February
    # deadline of the same year. January and February are never late.
    # March is 1 month late, April is 2, ... November is 9, December is 10.
    # A part of a month counts as a whole month.
    if on_date is None:
        on_date = timezone.localdate()
    if on_date.month <= 2:
        return 0
    return on_date.month - 2


def cedula_fee_breakdown(annual_income, on_date=None):
    # The "why" behind the fee, so the pages can show the working:
    # base, months late, interest, and total.
    income = annual_income or 0
    whole_thousands = int(income // 1000)
    additional = CEDULA_PER_THOUSAND * whole_thousands
    if additional > CEDULA_MAX_ADDITIONAL:
        additional = CEDULA_MAX_ADDITIONAL
    base = CEDULA_BASIC_FEE + additional
    months = cedula_months_late(on_date)
    interest = (base * CEDULA_LATE_RATE * months).quantize(Decimal('0.01'))
    return {
        'base': base,
        'additional': additional,
        'months_late': months,
        'interest': interest,
        'total': base + interest,
    }


def cedula_fee(annual_income, on_date=None):
    # The full Cedula fee on a given date (base + late interest).
    # annual_income may be None (not a Cedula request): the basic P5 only.
    # No date given means today.
    return cedula_fee_breakdown(annual_income, on_date=on_date)['total']

CERTIFICATE_REQUIREMENTS = {
    "Certificate of Residency": ["Valid ID"],
    "Certificate of Barangay Clearance": ["Certificate of Residency"],
    "Certificate of Cash Assistance": ["Valid ID", "Photo of 3 Signatures"],
    "Certificate of Medical": ["Certificate of Residency"],
    "Certificate of Indigency": ["Certificate of Residency"],
    "Cedula": [],
    "Certificate of Burial Assistance": ["Valid ID", "Photo of 3 Signatures"],
    "Certificate of Loan": ["Certificate of Residency"],
    "Certificate of Low Income": ["Certificate of Residency"],
    "Certificate of Burial": ["Certificate of Residency"],
}

CERTIFICATE_TEXT_FIELDS = {
    "Certificate of Loan": {
        "field_name": "financing_company",
        "label": "Name of Financing/Loan Company",
    },
}

# A Cedula (Community Tax Certificate) needs no valid ID, but the paper
# cedula itself is printed with the resident's personal details, so the
# resident must type them in when requesting one. Name and address already
# come from the resident's account, so they are not listed here.
CIVIL_STATUS_CHOICES = [
    ('Single', 'Single'),
    ('Married', 'Married'),
    ('Widowed', 'Widowed'),
    ('Separated', 'Separated'),
]

# (field name on CertificateRequest, label shown on the form)
CEDULA_FIELDS = [
    ("occupation", "Occupation / Work"),
    ("civil_status", "Civil Status"),
    ("date_of_birth", "Date of Birth"),
    ("place_of_birth", "Place of Birth"),
    ("citizenship", "Citizenship"),
    ("tin", "TIN (Tax Identification Number)"),
]

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
        ('ready_for_pickup', 'Ready for Pickup'),
        ('rejected', 'Rejected'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('pending_verification', 'Pending Verification'),
        ('paid', 'Paid'),
    ]

    resident = models.ForeignKey(Resident, on_delete=models.CASCADE)
    certificate_type = models.ForeignKey(CertificateType, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_reference = models.CharField(max_length=100, blank=True)
    financing_company = models.CharField(max_length=150, blank=True, null=True)
    date_requested = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    # --- Personal details for a Cedula (ma'am's feedback) ---
    # A cedula is printed with these details, so the resident types them in
    # when requesting one. They stay blank for every other certificate type.
    occupation = models.CharField("Occupation / Work", max_length=100, blank=True)
    civil_status = models.CharField("Civil Status", max_length=20, blank=True, choices=CIVIL_STATUS_CHOICES)
    date_of_birth = models.DateField("Date of Birth", null=True, blank=True)
    place_of_birth = models.CharField("Place of Birth", max_length=150, blank=True)
    citizenship = models.CharField("Citizenship", max_length=60, blank=True)
    tin = models.CharField("TIN (Tax Identification Number)", max_length=20, blank=True)
    # Annual income is only used for a Cedula: it sets the Cedula fee
    # (P5 + P1 per P1,000 of income). It stays blank for other requests.
    annual_income = models.DecimalField("Annual Income", max_digits=12, decimal_places=2, null=True, blank=True)

    # --- Collections record (filled in when staff click "Mark as Paid") ---
    # The barangay's paper Official Receipt is still the legal document;
    # these fields only RECORD it so the Collections Report can list it.
    # Older paid requests keep these blank/empty (no data is lost).
    or_number = models.CharField(max_length=30, blank=True)
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    date_paid = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='confirmed_payments',
    )

    @property
    def days_waiting(self):
        return (timezone.now() - self.date_requested).days

    @property
    def fee(self):
        # How much this request costs. A Cedula is priced from the
        # resident's annual income; every other certificate is the flat P50.
        # The price is set on the day the resident requests it, so it never
        # changes after that (a late request already has its interest in it).
        if self.certificate_type and self.certificate_type.name == 'Cedula':
            return cedula_fee(self.annual_income, on_date=self._fee_date())
        return CERTIFICATE_FEE

    @property
    def fee_breakdown(self):
        # The "why" behind the Cedula fee: base, months late, interest,
        # total. Only for a Cedula; every other certificate has none.
        if self.certificate_type and self.certificate_type.name == 'Cedula':
            return cedula_fee_breakdown(self.annual_income, on_date=self._fee_date())
        return None

    @property
    def fee_breakdown_text(self):
        # One plain line that says why the Cedula fee is what it is, for
        # the payment popup. Example: "P5 basic + P120 income = P125,
        # plus 9 months late x 2% (P22.50)".
        breakdown = self.fee_breakdown
        if not breakdown:
            return ''
        line = (
            f"P5 basic + P{breakdown['additional']} for income"
            f" = P{breakdown['base']}"
        )
        if breakdown['months_late']:
            line += (
                f", plus {breakdown['months_late']} months late x 2%"
                f" (P{breakdown['interest']})"
            )
        else:
            line += ", no late interest"
        return line

    def _fee_date(self):
        # The date the fee is worked out from: the day the request was
        # made. A request that is not saved yet has no date, so use today.
        if self.date_requested:
            return timezone.localdate(self.date_requested)
        return timezone.localdate()

    @property
    def days_since_approved(self):
        return (timezone.now() - self.date_updated).days

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