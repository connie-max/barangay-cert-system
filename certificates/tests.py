"""Simple tests for the Cedula personal details (ma'am's feedback).

Run from the project folder:
    python manage.py test certificates
"""
from datetime import datetime
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from .models import (
    Resident, CertificateType, CertificateRequest,
    cedula_fee, cedula_fee_breakdown, cedula_months_late,
)

# A tiny real 1x1 PNG, so the image fields accept it as a photo.
TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def photo(name='test.png'):
    return SimpleUploadedFile(name, TINY_PNG, content_type='image/png')


def make_resident():
    user = User.objects.create_user(username='juan', password='juan123')
    resident = Resident.objects.create(
        user=user, full_name='Juan Dela Cruz',
        address='Purok 1, Barangay Sasa', contact_number='09123456789',
    )
    return user, resident


def make_types():
    names = [
        "Certificate of Residency",
        "Certificate of Barangay Clearance",
        "Cedula",
        "Certificate of Loan",
    ]
    return {n: CertificateType.objects.create(name=n) for n in names}


CEDULA_DETAILS = {
    'occupation': 'Teacher',
    'civil_status': 'Single',
    'date_of_birth': '1998-05-10',
    'place_of_birth': 'Nabunturan, Davao de Oro',
    'citizenship': 'Filipino',
    'tin': '123-456-789-000',
    # P120,000 income -> Cedula fee P5 + P120 = P125 (in February, no
    # late interest; in November it is P147.50 with 9 months x 2%).
    'annual_income': '120000',
}


def set_request_date(req, year, month, day):
    # The fee is set on the day the request was made, so move the request
    # to that date to test it. update() writes straight to the database,
    # so the auto date does not overwrite it.
    when = timezone.make_aware(datetime(year, month, day))
    CertificateRequest.objects.filter(pk=req.pk).update(date_requested=when)
    req.refresh_from_db()


class CedulaRequestTests(TestCase):
    def setUp(self):
        self.user, self.resident = make_resident()
        self.types = make_types()
        self.client = Client()
        self.client.force_login(self.user)

    def post_request(self, cert_type, extra=None, files=None):
        data = {'certificate_type': cert_type.id}
        if extra:
            data.update(extra)
        if files:
            data.update(files)
        return self.client.post('/request/', data)

    def test_cedula_without_details_is_rejected(self):
        # No personal details typed in: no request is saved.
        self.post_request(self.types['Cedula'])
        self.assertEqual(CertificateRequest.objects.count(), 0)

    def test_cedula_with_details_is_saved(self):
        # All 6 personal details + annual income typed in: the request is
        # saved with them, and the Cedula fee follows the income (P125).
        # The request is moved to 15 Feb, so no late interest applies.
        self.post_request(self.types['Cedula'], CEDULA_DETAILS)
        req = CertificateRequest.objects.get()
        set_request_date(req, 2026, 2, 15)
        self.assertEqual(req.occupation, 'Teacher')
        self.assertEqual(req.civil_status, 'Single')
        self.assertEqual(str(req.date_of_birth), '1998-05-10')
        self.assertEqual(req.place_of_birth, 'Nabunturan, Davao de Oro')
        self.assertEqual(req.citizenship, 'Filipino')
        self.assertEqual(req.tin, '123-456-789-000')
        self.assertEqual(req.annual_income, Decimal('120000'))
        self.assertEqual(req.fee, Decimal('125.00'))

    def test_loan_financing_company_is_saved(self):
        # The loan company name used to be lost; now it is saved.
        # A Loan also needs its Certificate of Residency photo attached.
        self.post_request(self.types['Certificate of Loan'],
                          {'financing_company': 'BPI Auto Loan'},
                          {'attachment_Certificate of Residency': photo()})
        req = CertificateRequest.objects.get()
        self.assertEqual(req.financing_company, 'BPI Auto Loan')

    def test_residency_needs_no_extra_fields(self):
        # Other certificates still work with only the type picked, plus
        # their normal requirement (here, a Valid ID, front and back).
        self.post_request(
            self.types['Certificate of Residency'], None,
            {'id_type': 'PhilSys National ID',
             'id_file_Front': photo('front.png'),
             'id_file_Back': photo('back.png')})
        self.assertEqual(CertificateRequest.objects.count(), 1)
        req = CertificateRequest.objects.get()
        self.assertEqual(req.occupation, '')

    def test_cedula_fee_follows_income(self):
        # P5 basic + P1 for every P1,000 of annual income (whole thousands).
        # Tested on 15 Feb, so no late interest applies.
        from datetime import date
        feb = date(2026, 2, 15)
        cases = [(None, '5.00'), (Decimal('0'), '5.00'), (Decimal('1500'), '6.00'),
                 (Decimal('60000'), '65.00'), (Decimal('120000'), '125.00')]
        for income, expected in cases:
            self.assertEqual(cedula_fee(income, on_date=feb), Decimal(expected))

    def test_cedula_months_late(self):
        # January and February are never late. March is 1 month late,
        # April is 2, ... November is 9, December is 10.
        from datetime import date
        cases = [(1, 0), (2, 0), (3, 1), (4, 2), (11, 9), (12, 10)]
        for month, expected in cases:
            self.assertEqual(cedula_months_late(date(2026, month, 15)), expected)

    def test_cedula_fee_late_interest(self):
        # After February, add 2% interest for every month late.
        # P120,000 in November: base P125, 9 months x 2% = P22.50, P147.50.
        from datetime import date
        self.assertEqual(cedula_fee(Decimal('120000'), on_date=date(2026, 11, 28)), Decimal('147.50'))
        self.assertEqual(cedula_fee(Decimal('60000'), on_date=date(2026, 11, 28)), Decimal('76.70'))
        self.assertEqual(cedula_fee(Decimal('120000'), on_date=date(2026, 3, 1)), Decimal('127.50'))
        self.assertEqual(cedula_fee(Decimal('120000'), on_date=date(2026, 2, 28)), Decimal('125.00'))

    def test_cedula_fee_cap(self):
        # The extra tax for income never goes past P5,000, so the most
        # anyone pays before interest is P5,005.
        from datetime import date
        feb = date(2026, 2, 15)
        self.assertEqual(cedula_fee(Decimal('5000000'), on_date=feb), Decimal('5005.00'))
        self.assertEqual(cedula_fee(Decimal('6000000'), on_date=feb), Decimal('5005.00'))

    def test_cedula_fee_breakdown(self):
        # The "why" behind the fee: base, months late, interest, total.
        from datetime import date
        late = cedula_fee_breakdown(Decimal('120000'), on_date=date(2026, 11, 28))
        self.assertEqual(late['base'], Decimal('125.00'))
        self.assertEqual(late['additional'], Decimal('120.00'))
        self.assertEqual(late['months_late'], 9)
        self.assertEqual(late['interest'], Decimal('22.50'))
        self.assertEqual(late['total'], Decimal('147.50'))
        early = cedula_fee_breakdown(Decimal('120000'), on_date=date(2026, 2, 15))
        self.assertEqual(early['months_late'], 0)
        self.assertEqual(early['interest'], Decimal('0.00'))
        self.assertEqual(early['total'], Decimal('125.00'))

    def test_cedula_fee_locks_at_request_date(self):
        # The price is set on the day the request was made, so it never
        # changes after that. The same P120,000 request costs P125 in
        # February and P147.50 in November.
        req = CertificateRequest.objects.create(
            resident=self.resident, certificate_type=self.types['Cedula'],
            annual_income=Decimal('120000'))
        set_request_date(req, 2026, 2, 15)
        self.assertEqual(req.fee, Decimal('125.00'))
        set_request_date(req, 2026, 11, 28)
        self.assertEqual(req.fee, Decimal('147.50'))
        self.assertEqual(req.fee_breakdown['months_late'], 9)

    def test_other_certificate_fee_is_50(self):
        # Every other certificate is the flat P50.
        req = CertificateRequest.objects.create(
            resident=self.resident,
            certificate_type=self.types['Certificate of Residency'])
        self.assertEqual(req.fee, Decimal('50.00'))

    def test_cedula_without_income_is_rejected(self):
        # Income is required for a Cedula: without it the fee cannot be set.
        details = dict(CEDULA_DETAILS)
        del details['annual_income']
        self.post_request(self.types['Cedula'], details)
        self.assertEqual(CertificateRequest.objects.count(), 0)

    def test_mark_as_paid_records_cedula_fee(self):
        # A Cedula for P120,000 income requested in November costs P147.50
        # (base P125 + 9 months late x 2% = P22.50), and that is the amount
        # staff record when they mark it paid (not the flat P50).
        self.post_request(self.types['Cedula'], CEDULA_DETAILS)
        req = CertificateRequest.objects.get()
        staff = User.objects.create_user(username='staff', password='staff123', is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse('update_request_status', args=[req.id, 'approved']))
        self.client.post(reverse('mark_as_paid', args=[req.id]), {'or_number': 'DDO 111'})
        req.refresh_from_db()
        self.assertEqual(req.payment_status, 'paid')
        self.assertEqual(req.amount_paid, Decimal('147.50'))

