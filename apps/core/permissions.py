"""Role guards. Wrong role → 403; anonymous → login; ownership is checked by scoped querysets (→ 404)."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def _guard(check, attach=None):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not check(user):
                raise PermissionDenied
            if attach:
                result = attach(request)
                if result is not None:
                    return result
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def _attach_dentist(request):
    request.dentist = request.user.dentist_profile


def _attach_patient(request):
    patient = request.user.patient_profile
    request.patient = patient
    request.dentist = patient.dentist
    if not patient.consent_at and request.resolver_match and request.resolver_match.url_name != "consent":
        return redirect("accounts:consent")


dentist_required = _guard(lambda u: u.is_dentist and hasattr(u, "dentist_profile"), _attach_dentist)
patient_required = _guard(lambda u: u.is_patient and hasattr(u, "patient_profile"), _attach_patient)
operator_required = _guard(lambda u: u.is_operator)
