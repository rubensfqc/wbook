from django.shortcuts import redirect
from django.urls import reverse


DOCTOR_EXEMPT = [
    '/accounts/login/', '/accounts/logout/', '/accounts/register/',
    '/trial-expired/', '/admin/',
]


class DoctorAccessMiddleware:
    """Block suspended or expired doctors from their portal."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, 'is_doctor', False):
            path = request.path
            if any(path.startswith(e) for e in DOCTOR_EXEMPT):
                return self.get_response(request)
            try:
                profile = user.doctor_profile
                if not profile.can_access:
                    return redirect('trial_expired')
            except Exception:
                pass
        return self.get_response(request)
