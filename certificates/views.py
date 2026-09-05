from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from .forms import CertificateRequestForm, ResidentSignUpForm
from .models import Resident, CertificateRequest
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

@login_required
def home(request):
    resident = Resident.objects.get(user=request.user)
    requests = CertificateRequest.objects.filter(resident=resident)

    context = {
        'total_requests': requests.count(),
        'pending_count': requests.filter(status='pending').count(),
        'approved_count': requests.filter(status='approved').count(),
        'rejected_count': requests.filter(status='rejected').count(),
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
            return redirect('my_requests')
    else:
        form = CertificateRequestForm()

    return render(request, 'certificates/request_form.html', {'form': form})

@login_required
def my_requests(request):
    resident = Resident.objects.get(user=request.user)
    requests = CertificateRequest.objects.filter(resident=resident)
    return render(request, 'certificates/my_requests.html', {'requests': requests})

def signup(request):
    if request.method == 'POST':
        form = ResidentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Resident.objects.create(
                user=user,
                address=form.cleaned_data.get('address'),
                contact_number=form.cleaned_data.get('contact_number')
            )
            login(request, user)
            return redirect('home')
    else:
        form = ResidentSignUpForm()

    return render(request, 'certificates/signup.html', {'form': form})

def is_staff_user(user):
    return user.is_staff

@user_passes_test(is_staff_user)
def manage_requests(request):
    pending = CertificateRequest.objects.filter(status='pending')
    return render(request, 'certificates/manage_requests.html', {'requests': pending})

@user_passes_test(is_staff_user)
def update_request_status(request, request_id, new_status):
    cert_request = get_object_or_404(CertificateRequest, id=request_id)
    cert_request.status = new_status
    cert_request.save()
    return redirect('manage_requests')

@login_required
def download_certificate(request, request_id):
    resident = Resident.objects.get(user=request.user)
    cert_request = get_object_or_404(CertificateRequest, id=request_id, resident=resident, status='approved')

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
    p.drawString(100, height - 250, resident.user.username)
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 280, f"Address: {resident.address}")
    p.drawString(100, height - 310, f"Is a resident in good standing as of {cert_request.date_updated.strftime('%B %d, %Y')}.")

    p.setFont("Helvetica-Oblique", 10)
    p.drawString(100, height - 400, "This is a system-generated certificate for prototype purposes.")

    p.showPage()
    p.save()

    return response