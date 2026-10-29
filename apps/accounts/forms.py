from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledForm, StyledFormMixin
from apps.core.slugs import validate_public_slug

from .models import User

UF_CHOICES = [(uf, uf) for uf in (
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)]


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label=_("E-mail ou usuário"), max_length=254)
    error_messages = {
        "invalid_login": _("E-mail/usuário ou senha incorretos."),
        "inactive": _("Esta conta ainda não foi ativada. Confira seu e-mail."),
    }


class RegisterForm(StyledForm):
    name = forms.CharField(label=_("Seu nome"), max_length=120)
    display_name = forms.CharField(label=_("Nome profissional"), max_length=120, help_text=_('Ex.: "Dra. Ana Lima"'))
    email = forms.EmailField(label=_("E-mail"))
    password = forms.CharField(label=_("Senha"), widget=forms.PasswordInput, min_length=8)
    clinic_name = forms.CharField(label=_("Nome do consultório ou clínica"), max_length=120)
    slug = forms.CharField(
        label=_("Endereço da sua página"), max_length=50, help_text=_("wbook.com.br/seu-endereco — letras minúsculas, números e hífens")
    )
    cro_number = forms.CharField(label=_("CRO"), max_length=20)
    cro_state = forms.ChoiceField(label=_("UF do CRO"), choices=UF_CHOICES, initial="SP")
    whatsapp = forms.CharField(label=_("WhatsApp"), max_length=30)
    city = forms.CharField(label=_("Cidade"), max_length=80)
    state = forms.ChoiceField(label=_("Estado"), choices=UF_CHOICES, initial="SP")
    accept = forms.BooleanField(label=_("Li e aceito os termos de uso e a política de privacidade"))

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("Já existe uma conta com este e-mail."))
        return email

    def clean_slug(self):
        from apps.clinic.models import Dentist

        slug = self.cleaned_data["slug"].lower().strip()
        validate_public_slug(slug)
        if Dentist.objects.filter(slug=slug).exists():
            raise forms.ValidationError(_("Este endereço já está em uso."))
        return slug

    def clean_password(self):
        pw = self.cleaned_data["password"]
        password_validation.validate_password(pw)
        return pw


class ResendForm(StyledForm):
    email = forms.EmailField(label=_("E-mail"))


class InclusivePasswordResetForm(StyledFormMixin, PasswordResetForm):
    """Also reaches invited users who never set a password."""

    def get_users(self, email):
        return User.objects.filter(email__iexact=email, is_active=True)

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        from apps.core.emails import send_templated

        from .tokens import set_password_link

        user = context["user"]
        send_templated(to_email, _("Defina uma nova senha — wbook"), "password_reset",
                       {"user": user, "link": set_password_link(user)}, language=user.language)


class WbSetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass


class WbPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class ConsentForm(StyledForm):
    accept = forms.BooleanField(
        label=_("Autorizo o uso dos meus dados de saúde (fotos, exames e anotações do tratamento) pelo meu dentista para o meu atendimento.")
    )
