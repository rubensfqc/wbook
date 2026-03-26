from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings as djsettings


DOCTOR_EXEMPT = [
    '/accounts/login/', '/accounts/logout/', '/accounts/register/',
    '/trial-expired/', '/admin/',
]


class DefaultLanguageMiddleware:
    """
    Sets pt-BR as the default language for first-time visitors who have no
    explicit language preference stored in their session or cookie yet.
    This runs BEFORE LocaleMiddleware so LocaleMiddleware reads our default
    instead of falling through to the browser's Accept-Language header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = getattr(djsettings, 'LANGUAGE_COOKIE_NAME', 'django_language')
        has_cookie  = cookie_name in request.COOKIES
        has_session = '_language' in request.session

        if not has_cookie and not has_session:
            # Inject the default into the request so LocaleMiddleware sees it
            request.COOKIES[cookie_name] = djsettings.LANGUAGE_CODE

        response = self.get_response(request)
        return response



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
