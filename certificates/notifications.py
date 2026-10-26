import logging

from django.core.mail import send_mail

from .models import CERTIFICATE_FEE

logger = logging.getLogger(__name__)

SITE_URL = 'https://brgyonline.pythonanywhere.com'

FOOTER = (
    "\n\nBarangay Certificate Request System\n"
    "This is an automatic message. Please do not reply to this email."
)


def _name(user):
    resident = getattr(user, 'resident', None)
    if resident and resident.full_name:
        return resident.full_name
    return user.username


def _send(user, subject, body):
    # Sending must never break a staff action: if the email fails, we only log it.
    if not user.email:
        return
    try:
        send_mail(subject, body + FOOTER, None, [user.email])
    except Exception:
        logger.exception("Could not send an email to user id %s", user.id)


def notify_account_approved(user):
    _send(
        user,
        "Your account has been approved",
        f"Hi {_name(user)},\n\n"
        "Your account has been approved. You can now log in and request a certificate:\n"
        f"{SITE_URL}/login/",
    )


def notify_request_approved(cert_request):
    user = cert_request.resident.user
    _send(
        user,
        f"Your {cert_request.certificate_type} request was approved",
        f"Hi {_name(user)},\n\n"
        f"Your request for {cert_request.certificate_type} has been APPROVED.\n\n"
        f"Next step: pay {'₱'}{CERTIFICATE_FEE} through GCash, then enter your GCash "
        f"reference number on your request in the system:\n{SITE_URL}",
    )


def notify_request_rejected(cert_request):
    user = cert_request.resident.user
    _send(
        user,
        f"Your {cert_request.certificate_type} request was not approved",
        f"Hi {_name(user)},\n\n"
        f"Your request for {cert_request.certificate_type} was NOT approved.\n"
        "Please visit the barangay hall for details, or submit a new request "
        "with the correct requirements:\n"
        f"{SITE_URL}",
    )


def notify_ready_for_pickup(cert_request):
    user = cert_request.resident.user
    _send(
        user,
        f"Your {cert_request.certificate_type} is ready for pickup",
        f"Hi {_name(user)},\n\n"
        f"Your {cert_request.certificate_type} is READY FOR PICKUP.\n"
        "Please go to the barangay hall to claim it.",
    )