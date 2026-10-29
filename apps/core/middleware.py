from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class DefaultLanguageMiddleware:
    """First visit → pt-BR, so a browser in English doesn't switch Brazilian visitors to English.

    Runs before LocaleMiddleware: when there is no language cookie yet, it injects one for this request
    and sets it on the response. The switcher (/idioma/) overrides it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = settings.LANGUAGE_COOKIE_NAME
        missing = name not in request.COOKIES
        if missing:
            lang = settings.LANGUAGE_CODE
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                lang = user.language
            request.COOKIES[name] = lang
        response = self.get_response(request)
        login_lang = getattr(request, "_wb_login_language", None)
        if login_lang:
            response.set_cookie(name, login_lang, max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax")
        elif missing and name not in response.cookies:
            response.set_cookie(name, request.COOKIES[name], max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax")
        return response


class SubscriptionMiddleware:
    """Expired dentists can only reach settings and the subscription page inside /app/."""

    ALLOWED = ("/app/assinatura/", "/app/configuracoes/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        user = getattr(request, "user", None)
        if (
            path.startswith("/app/")
            and user is not None
            and user.is_authenticated
            and getattr(user, "is_dentist", False)
            and hasattr(user, "dentist_profile")
            and not user.dentist_profile.can_access
            and not path.startswith(self.ALLOWED)
        ):
            return redirect(reverse("clinic:expired"))
        return self.get_response(request)
