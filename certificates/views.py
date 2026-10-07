import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import Http404
from django.views.decorators.http import require_POST
from .forms import CertificateRequestForm, ResidentSignUpForm
from .models import Resident, CertificateRequest, RequestAttachment, CERTIFICATE_REQUIREMENTS

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
def cancel_request(request, request_id):
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

@user_passes_test(is_staff_user)
def manage_requests(request):
    pending = CertificateRequest.objects.filter(status='pending')
    awaiting_payment = CertificateRequest.objects.filter(status='approved').exclude(payment_status='paid')
    # Paid but not yet released: staff prints/signs the certificate, then marks it ready
    ready_to_release = CertificateRequest.objects.filter(status='approved', payment_status='paid')
    return render(request, 'certificates/manage_requests.html', {
        'requests': pending,
        'awaiting_payment': awaiting_payment,
        'ready_to_release': ready_to_release,
    })

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
    return redirect('manage_requests')

@user_passes_test(is_staff_user)
@require_POST
def mark_as_paid(request, request_id):
    cert_request = get_object_or_404(CertificateRequest, id=request_id, status='approved')
    cert_request.payment_status = 'paid'
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
    return redirect('manage_requests')

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
    return redirect('pending_accounts')

@user_passes_test(is_staff_user)
@require_POST
def reject_account(request, user_id):
    account = get_object_or_404(User, id=user_id, is_active=False)
    account.delete()
    return redirect('pending_accounts')