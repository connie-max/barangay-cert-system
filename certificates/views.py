from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import CertificateRequestForm
from .models import Resident, CertificateRequest

@login_required
def home(request):
    return render(request, 'certificates/home.html')

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