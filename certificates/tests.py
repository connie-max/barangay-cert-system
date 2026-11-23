"""Simple tests for the Cedula personal details (ma'am's feedback).

Run from the project folder:
    python manage.py test certificates
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from .models import Resident, CertificateType, CertificateRequest

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
    # P120,000 income -> Cedula fee P5 + P120 = P125.
    'annual_income': '120000',
}


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
        self.post_request(self.types['Cedula'], CEDULA_DETAILS)
        req = CertificateRequest.objects.get()
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
        # (Decimals here: creating a model directly does not convert strings.)
        cases = [(None, '5.00'), (Decimal('0'), '5.00'), (Decimal('1500'), '6.00'),
                 (Decimal('60000'), '65.00'), (Decimal('120000'), '125.00')]
        for income, expected in cases:
            req = CertificateRequest.objects.create(
                resident=self.resident, certificate_type=self.types['Cedula'],
                annual_income=income)
            self.assertEqual(req.fee, Decimal(expected))
            req.delete()

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
        # A Cedula for P120,000 income costs P125, and that is the amount
        # staff record when they mark it paid (not the flat P50).
        self.post_request(self.types['Cedula'], CEDULA_DETAILS)
        req = CertificateRequest.objects.get()
        staff = User.objects.create_user(username='staff', password='staff123', is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse('update_request_status', args=[req.id, 'approved']))
        self.client.post(reverse('mark_as_paid', args=[req.id]), {'or_number': 'DDO 111'})
        req.refresh_from_db()
        self.assertEqual(req.payment_status, 'paid')
        self.assertEqual(req.amount_paid, Decimal('125.00'))

