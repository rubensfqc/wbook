from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from .forms import DoctorRegistrationForm, LoginForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get('next', 'dashboard_redirect'))
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('login')


def register(request):
    form = DoctorRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Welcome! Your doctor account has been created.')
        return redirect('doctor_dashboard')
    return render(request, 'accounts/register.html', {'form': form})


def doctor_login(request, slug):
    """
    Doctor-branded login page. Shows the doctor's logo/name at the top.
    After login, redirects the patient to their portal (or the doctor's booking page).
    """
    from booking.models import DoctorProfile
    from accounts.models import Seller
    from django.shortcuts import get_object_or_404

    doctor_user = get_object_or_404(Seller, slug=slug, role=Seller.Roles.DOCTOR)
    doctor      = get_object_or_404(DoctorProfile, user=doctor_user)

    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        # Send registered patients straight back to the booking flow
        next_url = request.GET.get('next') or 'dashboard_redirect'
        return redirect(next_url)

    return render(request, 'accounts/doctor_login.html', {
        'form':   form,
        'doctor': doctor,
    })
