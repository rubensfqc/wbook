import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledForm, StyledFormMixin

from .models import User

UF_CHOICES = [(uf, uf) for uf in (
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)]


USERNAME_HELP = _("3 a 40 caracteres: letras minúsculas, números, ponto, hífen ou _. Você poderá entrar com ele ou com o e-mail.")


def clean_username_value(value, exclude_pk=None):
    """Shared validation for username fields (registration and settings). Returns the normalized value or ''."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    User._meta.get_field("username").run_validators(value)
    if User.objects.filter(username__iexact=value).exclude(pk=exclude_pk).exists():
        raise forms.ValidationError(_("Este nome de usuário já está em uso."))
    return value


class LoginForm(StyledFormMixin, AuthenticationForm):
    """`username` accepts the e-mail OR the username (see apps.accounts.backends)."""

    username = forms.CharField(
        label=_("E-mail ou nome de usuário"), max_length=254,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"}),
    )
    error_messages = {
        "invalid_login": _("E-mail/usuário ou senha incorretos."),
        "inactive": _("Esta conta ainda não foi ativada. Confira seu e-mail."),
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class RegisterForm(StyledForm):
    """Short sign-up: only what's needed to contact the dentist. Clinic, CRO, address etc. are filled in later in Settings."""

    name = forms.CharField(label=_("Seu nome"), max_length=120, widget=forms.TextInput(attrs={"autocomplete": "name"}),
                           help_text=_('Ex.: "Dra. Ana Lima"'))
    email = forms.EmailField(label=_("E-mail"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    whatsapp = forms.CharField(
        label=_("WhatsApp"), max_length=30,
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel", "inputmode": "tel", "placeholder": "(11) 99999-8888"}),
    )
    password = forms.CharField(label=_("Senha"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), min_length=8)
    username = forms.CharField(
        label=_("Nome de usuário (opcional)"), max_length=40, required=False, help_text=USERNAME_HELP,
        widget=forms.TextInput(attrs={"autocapitalize": "none", "spellcheck": "false", "placeholder": "ana.lima"}),
    )
    accept = forms.BooleanField(label=_("Li e aceito os termos de uso e a política de privacidade"))
    website = forms.CharField(required=False, widget=forms.HiddenInput)  # honeypot

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Já existe uma conta com este e-mail."))
        return email

    def clean_whatsapp(self):
        value = self.cleaned_data["whatsapp"].strip()
        if len(re.sub(r"\D", "", value)) < 10:
            raise forms.ValidationError(_("Informe o WhatsApp com DDD."))
        return value

    def clean_username(self):
        return clean_username_value(self.cleaned_data.get("username"))

    def clean(self):
        data = super().clean()
        pw = data.get("password")
        if pw:
            try:
                password_validation.validate_password(pw, User(email=data.get("email", ""), name=data.get("name", "")))
            except forms.ValidationError as e:
                self.add_error("password", e)
        return data


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
