from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib.auth.models import User
from .forms import CertificateRequestForm, ResidentSignUpForm
from .models import Resident, CertificateRequest
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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
        'approved_count': requests.filter(status='approved').count(),
        'rejected_count': requests.filter(status='rejected').count(),
        'form': CertificateRequestForm(),
        'my_requests_list': requests,
    }
    return render(request, 'certificates/home.html', context)

@login_required
def request_certificate(request):
    resident = Resident.objects.get(user=request.user)

    if request.method == 'POST':
        form = CertificateRequestForm(request.POST)
        if form.is_valid():
            new_request = form.save(commit=False)
            new_request.resident = resident
            new_request.save()
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
    return render(request, 'certificates/manage_requests.html', {
        'requests': pending,
        'awaiting_payment': awaiting_payment,
    })

@user_passes_test(is_staff_user)
def update_request_status(request, request_id, new_status):
    cert_request = get_object_or_404(CertificateRequest, id=request_id)
    cert_request.status = new_status
    cert_request.save()
    return redirect('manage_requests')

@user_passes_test(is_staff_user)
def mark_as_paid(request, request_id):
    cert_request = get_object_or_404(CertificateRequest, id=request_id, status='approved')
    cert_request.payment_status = 'paid'
    cert_request.save()
    return redirect('manage_requests')

@user_passes_test(is_staff_user)
def pending_accounts(request):
    pending_users = User.objects.filter(is_active=False, is_staff=False)
    return render(request, 'certificates/pending_accounts.html', {'pending_users': pending_users})

@user_passes_test(is_staff_user)
def approve_account(request, user_id):
    account = get_object_or_404(User, id=user_id, is_active=False)
    account.is_active = True
    account.save()
    return redirect('pending_accounts')

@user_passes_test(is_staff_user)
def reject_account(request, user_id):
    account = get_object_or_404(User, id=user_id, is_active=False)
    account.delete()
    return redirect('pending_accounts')

@login_required
def download_certificate(request, request_id):
    resident = Resident.objects.get(user=request.user)
    cert_request = get_object_or_404(
        CertificateRequest,
        id=request_id,
        resident=resident,
        status='approved',
        payment_status='paid',
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{cert_request.id}.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width / 2, height - 100, "Barangay Certificate")

    p.setFont("Helvetica", 14)
    p.drawCentredString(width / 2, height - 150, str(cert_request.certificate_type))

    p.setFont("Helvetica", 12)
    p.drawString(100, height - 220, f"This is to certify that:")
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, height - 250, resident.full_name or resident.user.username)
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 280, f"Address: {resident.address}")
    p.drawString(100, height - 310, f"Is a resident in good standing as of {cert_request.date_updated.strftime('%B %d, %Y')}.")

    p.setFont("Helvetica-Oblique", 10)
    p.drawString(100, height - 400, "This is a system-generated certificate for prototype purposes.")

    p.showPage()
    p.save()

    return response