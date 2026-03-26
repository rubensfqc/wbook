from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import Seller


class DoctorRegistrationForm(UserCreationForm):
    name  = forms.CharField(max_length=150, label=_('Full Name'))
    email = forms.EmailField(label=_('Email'))

    class Meta:
        model  = Seller
        fields = ('username', 'name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role  = Seller.Roles.DOCTOR
        user.name  = self.cleaned_data['name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={'autofocus': True}),
    )


class SellerUpdateForm(forms.ModelForm):
    class Meta:
        model  = Seller
        fields = ('name', 'phone_number', 'address', 'profile_picture')
