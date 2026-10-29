from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


def set_language_cookie(response, lang):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax")
    return response


@require_POST
def set_language(request):
    lang = request.POST.get("language", "")
    nxt = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        nxt = "/"
    response = HttpResponseRedirect(nxt)
    if lang in dict(settings.LANGUAGES):
        set_language_cookie(response, lang)
        if request.user.is_authenticated and request.user.language != lang:
            request.user.language = lang
            request.user.save(update_fields=["language"])
    return response
