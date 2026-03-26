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
