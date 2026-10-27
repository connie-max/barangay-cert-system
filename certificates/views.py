import json
import mimetypes
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404, FileResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import CertificateRequestForm, ResidentSignUpForm
from .models import Resident, CertificateRequest, RequestAttachment, CERTIFICATE_REQUIREMENTS, CERTIFICATE_FEE
from . import report_exports
from . import notifications

ID_TYPE_SIDES = {
    "PhilSys National ID": ["Front", "Back"],
    "Driver's License": ["Front", "Back"],
    "Passport": ["Photo Page"],
    "UMID": ["Front", "Back"],
    "SSS ID": ["Front", "Back"],
    "PhilHealth ID": ["Front", "Back"],
    "Postal ID": ["Front", "Back"],
    "Voter's ID": ["Front", "Back"],
    "PRC ID": ["Front", "Back"],
    "Senior Citizen ID": ["Front", "Back"],
    "PWD ID": ["Front", "Back"],
    "TIN ID": ["Front", "Back"],
    "Barangay ID": ["Front", "Back"],
    "Other": ["Front", "Back"],
}

@login_required
def home(request):
    if request.user.is_staff:
        # Staff/admin see system-wide stats across all residents
        requests = CertificateRequest.objects.all()
    else:
        # Residents see only their own stats
        resident = Resident.objects.get(user=request.user)
        requests = CertificateRequest.objects.filter(resident=resident)

    context = {
        'total_requests': requests.count(),
        'pending_count': requests.filter(status='pending').count(),
        # "Approved" includes requests already marked ready for pickup
        'approved_count': requests.filter(status__in=['approved', 'ready_for_pickup']).count(),
        'rejected_count': requests.filter(status='rejected').count(),
        'form': CertificateRequestForm(),
        'my_requests_list': requests,
        'certificate_requirements_json': json.dumps(CERTIFICATE_REQUIREMENTS),
    }
    return render(request, 'certificates/home.html', context)

@login_required
def request_certificate(request):
    resident = Resident.objects.get(user=request.user)

    if request.method == 'POST':
        form = CertificateRequestForm(request.POST, request.FILES)
        if form.is_valid():
            cert_type_name = str(form.cleaned_data['certificate_type'])
            required_labels = CERTIFICATE_REQUIREMENTS.get(cert_type_name, [])

            needs_id = 'Valid ID' in required_labels
            other_labels = [l for l in required_labels if l != 'Valid ID']

            errors = []

            missing = [
                label for label in other_labels
                if f'attachment_{label}' not in request.FILES
            ]
            if missing:
                errors.append("Missing required upload(s): " + ", ".join(missing) + ".")

            # Valid ID: the server decides which sides are required
            id_type = request.POST.get('id_type', '').strip()
            id_sides = []
            if needs_id:
                if id_type not in ID_TYPE_SIDES:
                    errors.append("Please select a valid ID type.")
                else:
                    id_sides = ID_TYPE_SIDES[id_type]
                    missing_sides = [
                        s for s in id_sides
                        if f'id_file_{s}' not in request.FILES
                    ]
                    if missing_sides:
                        errors.append(
                            f"Missing {id_type} upload(s): " + ", ".join(missing_sides) + "."
                        )

            if errors:
                if request.user.is_staff:
                    requests_qs = CertificateRequest.objects.all()
                else:
                    requests_qs = CertificateRequest.objects.filter(resident=resident)
                context = {
                    'total_requests': requests_qs.count(),
                    'pending_count': requests_qs.filter(status='pending').count(),
                    'approved_count': requests_qs.filter(status__in=['approved', 'ready_for_pickup']).count(),
                    'rejected_count': requests_qs.filter(status='rejected').count(),
                    'form': form,
                    'my_requests_list': requests_qs,
                    'certificate_requirements_json': json.dumps(CERTIFICATE_REQUIREMENTS),
                    'attachment_error': " ".join(errors),
                }
                return render(request, 'certificates/home.html', context)

            new_request = form.save(commit=False)
            new_request.resident = resident
            new_request.save()

            for label in other_labels:
                RequestAttachment.objects.create(
                    request=new_request,
                    label=label,
                    image=request.FILES[f'attachment_{label}'],
                )

            for side in id_sides:
                RequestAttachment.objects.create(
                    request=new_request,
                    label=f'Valid ID ({id_type}) - {side}',
                    image=request.FILES[f'id_file_{side}'],
                )

            return redirect('home')
    else:
        form = CertificateRequestForm()

    return render(request, 'certificates/request_form.html', {'form': form})

@login_required
def my_requests(request):
    resident = Resident.objects.get(user=request.user)
    requests = CertificateRequest.objects.filter(resident=resident)
    return render(request, 'certificates/my_requests.html', {'requests': requests})

@login_required
@require_POST
def cancel_request(request, request_id):
    # Cancelling deletes the request, so it must be a deliberate POST (with CSRF),
    # never a link. A GET now returns 405 Method Not Allowed.
    resident = Resident.objects.get(user=request.user)
    cert_request = get_object_or_404(CertificateRequest, id=request_id, resident=resident, status='pending')
    cert_request.delete()
    return redirect('home')

def signup(request):
    if request.method == 'POST':
        form = ResidentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # pending staff approval
            user.save()
            Resident.objects.create(
                user=user,
                full_name=form.cleaned_data.get('full_name'),
                address=form.cleaned_data.get('address'),
                contact_number=form.cleaned_data.get('contact_number')
            )
            return render(request, 'certificates/signup_pending.html')
    else:
        form = ResidentSignUpForm()

    return render(request, 'certificates/signup.html', {'form': form})

@login_required
def submit_payment_reference(request, request_id):
    resident = Resident.objects.get(user=request.user)
    cert_request = get_object_or_404(
        CertificateRequest,
        id=request_id,
        resident=resident,
        status='approved',
    )
    if request.method == 'POST':
        reference = request.POST.get('payment_reference', '').strip()
        if reference:
            cert_request.payment_reference = reference
            cert_request.payment_status = 'pending_verification'
            cert_request.save()
    return redirect('home')

def is_staff_user(user):
    return user.is_staff

@login_required
def attachment_image(request, attachment_id):
    # Uploaded requirement photos (IDs, signatures, etc.) are private.
    # They are NOT served from a public /media/ URL. This view is the only
    # way to open them, and it only allows staff or the resident who uploaded
    # the photo. Everyone else gets a 404 (we don't even confirm it exists).
    attachment = get_object_or_404(RequestAttachment, id=attachment_id)
    is_owner = attachment.request.resident.user_id == request.user.id
    if not (request.user.is_staff or is_owner):
        raise Http404("Not found")

    try:
        file_handle = attachment.image.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404("File not found")

    content_type, _ = mimetypes.guess_type(attachment.image.name)
    response = FileResponse(file_handle, content_type=content_type or 'application/octet-stream')
    # Keep browsers and proxies from storing a copy of someone's ID
    response['Cache-Control'] = 'private, no-store'
    return response

def build_manage_context():
    # One place that builds the three staff lists, so manage_requests and the
    # "OR number problem" re-render in mark_as_paid always show the same data.
    pending = CertificateRequest.objects.filter(status='pending')
    awaiting_payment = CertificateRequest.objects.filter(status='approved').exclude(payment_status='paid')
    # Paid but not yet released: staff prints/signs the certificate, then marks it ready
    ready_to_release = CertificateRequest.objects.filter(status='approved', payment_status='paid')
    return {
        'requests': pending,
        'awaiting_payment': awaiting_payment,
        'ready_to_release': ready_to_release,
        'certificate_fee': CERTIFICATE_FEE,
    }

@user_passes_test(is_staff_user)
def manage_requests(request):
    return render(request, 'certificates/manage_requests.html', build_manage_context())

# The four staff actions below change data, so they accept POST only.
# A plain link (GET) now returns "405 Method Not Allowed", and the form
# must carry a CSRF token. This stops mis-taps, link prefetching, and
# someone tricking a logged-in staff member into clicking a hidden link.

@user_passes_test(is_staff_user)
@require_POST
def update_request_status(request, request_id, new_status):
    # Only these two decisions are allowed from the URL, and only on pending requests
    if new_status not in ('approved', 'rejected'):
        raise Http404("Invalid status")
    cert_request = CertificateRequest.objects.filter(id=request_id, status='pending').first()
    if cert_request:
        cert_request.status = new_status
        cert_request.save()
        if new_status == 'approved':
            notifications.notify_request_approved(cert_request)
        else:
            notifications.notify_request_rejected(cert_request)
    return redirect('manage_requests')

@user_passes_test(is_staff_user)
@require_POST
def mark_as_paid(request, request_id):
    cert_request = get_object_or_404(CertificateRequest, id=request_id, status='approved')

    # Already paid? Do nothing, so a double-tap can never overwrite the saved OR number.
    if cert_request.payment_status == 'paid':
        return redirect('manage_requests')

    # The server re-checks everything the browser sends.
    # " ".join(split()) tidies extra spaces: "DDO   4348601 " -> "DDO 4348601"
    or_number = " ".join(request.POST.get('or_number', '').split())

    error = None
    if not or_number:
        error = "Please enter the Official Receipt (OR) number."
    elif len(or_number) > 30:
        error = "The OR number is too long (30 characters max)."
    elif CertificateRequest.objects.filter(or_number__iexact=or_number).exists():
        # Each paper OR number is used once, so a repeat is almost always a typo.
        error = f"OR number {or_number} is already recorded on another request."

    if error:
        context = build_manage_context()
        context['payment_error'] = error
        return render(request, 'certificates/manage_requests.html', context)

    cert_request.payment_status = 'paid'
    cert_request.or_number = or_number
    cert_request.amount_paid = CERTIFICATE_FEE
    cert_request.date_paid = timezone.now()
    cert_request.confirmed_by = request.user
    cert_request.save()
    return redirect('manage_requests')

@user_passes_test(is_staff_user)
@require_POST
def mark_ready_for_pickup(request, request_id):
    # Only approved + paid requests can be released
    cert_request = CertificateRequest.objects.filter(
        id=request_id, status='approved', payment_status='paid'
    ).first()
    if cert_request:
        cert_request.status = 'ready_for_pickup'
        cert_request.save()
        notifications.notify_ready_for_pickup(cert_request)
    return redirect('manage_requests')

# ---------------------------------------------------------------------------
# Collections Report: every payment that staff recorded with an OR number.
# Read-only (GET), staff only, and it never shows ID photos.
# The two helpers below are shared with the Excel/PDF downloads (next step),
# so the screen and the downloaded files always show exactly the same rows.
# ---------------------------------------------------------------------------

def get_collections_period(request):
    """Turn the ?period=... &start=... &end=... in the URL into (period, start, end, error)."""
    today = timezone.localdate()
    first_this_month = today.replace(day=1)
    first_next_month = (first_this_month + timedelta(days=32)).replace(day=1)
    period = request.GET.get('period', 'this_month')
    error = None

    if period == 'last_month':
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif period == 'custom':
        try:
            start = date.fromisoformat(request.GET.get('start', ''))
            end = date.fromisoformat(request.GET.get('end', ''))
            if start > end:
                raise ValueError
        except ValueError:
            error = "Please pick a valid date range (the start date can't be after the end date)."
            period = 'this_month'
            start, end = first_this_month, first_next_month - timedelta(days=1)
    else:
        period = 'this_month'
        start, end = first_this_month, first_next_month - timedelta(days=1)

    return period, start, end, error


def get_collections_rows(start, end):
    """Paid requests that have a recorded OR number, between start and end (inclusive)."""
    return (
        CertificateRequest.objects
        .filter(payment_status='paid', date_paid__isnull=False,
                date_paid__date__gte=start, date_paid__date__lte=end)
        .select_related('resident', 'certificate_type')
        .order_by('date_paid', 'id')
    )


@user_passes_test(is_staff_user)
def collections_report(request):
    period, start, end, error = get_collections_period(request)
    rows = list(get_collections_rows(start, end))
    total = sum((r.amount_paid or 0) for r in rows)
    # Requests paid BEFORE OR numbers were recorded have no OR/date, so they can't be listed.
    older_paid_count = CertificateRequest.objects.filter(
        payment_status='paid', date_paid__isnull=True
    ).count()
    return render(request, 'certificates/collections_report.html', {
        'rows': rows,
        'total': total,
        'period': period,
        'start': start,
        'end': end,
        'period_error': error,
        'older_paid_count': older_paid_count,
        # Download buttons carry the exact dates shown on screen, so the files match the page.
        'export_query': f"period=custom&start={start.isoformat()}&end={end.isoformat()}",
    })

def _report_rows_as_plain_data(start, end):
    """Rows as simple dicts so report_exports.py needs no Django knowledge."""
    return [
        {
            'date': timezone.localtime(r.date_paid).date(),
            'or_number': r.or_number,
            'payor': str(r.resident),
            'nature': str(r.certificate_type),
            'amount': r.amount_paid or 0,
        }
        for r in get_collections_rows(start, end)
    ]


def _download_response(content, content_type, filename):
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # The file lists names and amounts, so keep browsers/proxies from storing a copy.
    response['Cache-Control'] = 'private, no-store'
    return response


@user_passes_test(is_staff_user)
def collections_report_xlsx(request):
    period, start, end, error = get_collections_period(request)
    rows = _report_rows_as_plain_data(start, end)
    content = report_exports.build_xlsx(rows, start, end)
    return _download_response(
        content,
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        f'collections_report_{start.isoformat()}_to_{end.isoformat()}.xlsx',
    )


@user_passes_test(is_staff_user)
def collections_report_pdf(request):
    period, start, end, error = get_collections_period(request)
    rows = _report_rows_as_plain_data(start, end)
    content = report_exports.build_pdf(rows, start, end, timezone.localdate())
    return _download_response(
        content,
        'application/pdf',
        f'collections_report_{start.isoformat()}_to_{end.isoformat()}.pdf',
    )

@user_passes_test(is_staff_user)
def pending_accounts(request):
    pending_users = User.objects.filter(is_active=False, is_staff=False)
    return render(request, 'certificates/pending_accounts.html', {'pending_users': pending_users})

@user_passes_test(is_staff_user)
@require_POST
def approve_account(request, user_id):
    account = get_object_or_404(User, id=user_id, is_active=False)
    account.is_active = True
    account.save()
    notifications.notify_account_approved(account)
    return redirect('pending_accounts')

@user_passes_test(is_staff_user)
@require_POST
def reject_account(request, user_id):
    account = get_object_or_404(User, id=user_id, is_active=False)
    account.delete()
    return redirect('pending_accounts')

@user_passes_test(is_staff_user)
def residents_list(request):
    # Read-only list of approved residents (no ID photos). Pending accounts are on their own page.
    query = request.GET.get('q', '').strip()
    residents = (
        Resident.objects.select_related('user')
        .filter(user__is_active=True, user__is_staff=False)
        .order_by('full_name')
    )
    if query:
        residents = residents.filter(
            Q(full_name__icontains=query)
            | Q(address__icontains=query)
            | Q(contact_number__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__username__icontains=query)
        )
    return render(request, 'certificates/residents_list.html', {
        'residents': residents,
        'query': query,
    })