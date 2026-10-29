from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.activity import log_action
from apps.core.emails import send_templated
from apps.core.utils import rate_limited

from .forms import ConsentForm, InclusivePasswordResetForm, LoginForm, RegisterForm, ResendForm, WbPasswordChangeForm, WbSetPasswordForm
from .models import User
from .tokens import email_verification_token, verify_link


def home(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("accounts:login")
    if user.is_operator:
        return redirect("operator:dashboard")
    if user.is_dentist:
        return redirect("clinic:dashboard")
    if user.is_patient:
        return redirect("patient:dashboard")
    return redirect("website:home")


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    dentist = None  # set by the branded login

    def form_valid(self, form):
        user = form.get_user()
        if self.dentist is not None:
            ok = (user.is_dentist and getattr(user, "dentist_profile", None) == self.dentist) or (
                user.is_patient and getattr(getattr(user, "patient_profile", None), "dentist_id", None) == self.dentist.pk
            )
            if not ok:
                form.add_error(None, _("Esta conta não pertence a este consultório. Use a página de login geral."))
                return self.form_invalid(form)
        response = super().form_valid(form)
        log_action(user, "auth", "Login")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["dentist"] = self.dentist
        return ctx


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_action(request, "auth", "Logout")
    logout(request)
    return redirect("website:home")


def register(request):
    from apps.clinic.services import create_dentist

    if request.user.is_authenticated:
        return redirect("accounts:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if rate_limited(request, "register", 5, 3600):
            messages.error(request, _("Muitas tentativas. Tente de novo em uma hora."))
        elif form.is_valid():
            d = form.cleaned_data
            dentist = create_dentist(
                email=d["email"], name=d["name"], password=d["password"], clinic_name=d["clinic_name"], slug=d["slug"],
                display_name=d["display_name"], cro_number=d["cro_number"], cro_state=d["cro_state"],
                whatsapp=d["whatsapp"], city=d["city"], state=d["state"], active=False,
                language=request.LANGUAGE_CODE,
            )
            _send_verification(dentist.user)
            from apps.core.notifications import notify_operator

            notify_operator("alert_new_dentist", _("Novo dentista: %(n)s") % {"n": dentist.clinic_name},
                            "operator_new_dentist", {"dentist": dentist})
            log_action(dentist.user, "auth", "Cadastro de dentista %(s)s", s=dentist.slug)
            request.session["verify_email"] = dentist.user.email
            return redirect("accounts:verify_email_sent")
    return render(request, "accounts/register.html", {"form": form})


def _send_verification(user):
    send_templated(user.email, _("Confirme seu e-mail — wbook"), "verify_email",
                   {"user": user, "link": verify_link(user)}, language=user.language)


def verify_email_sent(request):
    return render(request, "accounts/verify_email_sent.html",
                  {"email": request.session.get("verify_email", ""), "form": ResendForm()})


@require_POST
def resend_verification(request):
    form = ResendForm(request.POST)
    if rate_limited(request, "resend", 3, 3600):
        messages.error(request, _("Muitas tentativas. Tente de novo em uma hora."))
    elif form.is_valid():
        user = User.objects.filter(email=form.cleaned_data["email"].lower(), is_active=False).first()
        if user:
            _send_verification(user)
        messages.success(request, _("Se houver uma conta pendente com este e-mail, enviamos um novo link."))
    return redirect("accounts:verify_email_sent")


def _user_from_uid(uidb64):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None


def verify_email(request, uidb64, token):
    """GET shows a button; POST activates. E-mail scanners open links with GET."""
    user = _user_from_uid(uidb64)
    if user and user.is_active:
        return render(request, "accounts/verify_email.html", {"already": True})
    valid = user is not None and email_verification_token.check_token(user, token)
    if request.method == "POST" and valid:
        user.is_active = True
        user.save(update_fields=["is_active"])
        login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        log_action(user, "auth", "E-mail confirmado")
        messages.success(request, _("E-mail confirmado. Bem-vindo ao wbook!"))
        return redirect("accounts:home")
    return render(request, "accounts/verify_email.html", {"valid": valid})


def set_password(request, uidb64, token):
    """Invites and resets. Logs in after."""
    user = _user_from_uid(uidb64)
    valid = user is not None and default_token_generator.check_token(user, token)
    form = WbSetPasswordForm(user, request.POST or None) if valid else None
    if request.method == "POST" and valid and form.is_valid():
        form.save()
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        log_action(user, "auth", "Senha definida")
        messages.success(request, _("Senha definida."))
        return redirect("accounts:home")
    return render(request, "accounts/set_password.html", {"form": form, "valid": valid, "target_user": user})


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = InclusivePasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        if rate_limited(self.request, "reset", 5, 3600):
            messages.error(self.request, _("Muitas tentativas. Tente de novo em uma hora."))
            return redirect("accounts:password_reset")
        return super().form_valid(form)


def password_reset_done(request):
    return render(request, "accounts/password_reset_done.html")


@login_required
def change_password(request):
    form = WbPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        log_action(request, "auth", "Senha alterada")
        messages.success(request, _("Senha alterada."))
        return redirect("accounts:home")
    return render(request, "accounts/change_password.html", {"form": form})


@login_required
def consent(request):
    from django.conf import settings

    if not request.user.is_patient:
        return redirect("accounts:home")
    patient = request.user.patient_profile
    form = ConsentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        patient.consent_at = timezone.now()
        patient.consent_version = settings.CONSENT_VERSION
        patient.save(update_fields=["consent_at", "consent_version"])
        log_action(request, "patient", "Consentimento LGPD aceito (%(v)s)", v=settings.CONSENT_VERSION)
        return redirect(reverse("patient:dashboard"))
    return render(request, "accounts/consent.html", {"form": form, "dentist": patient.dentist})
