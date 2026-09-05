from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from .forms import CertificateRequestForm, ResidentSignUpForm
from .models import Resident, CertificateRequest

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