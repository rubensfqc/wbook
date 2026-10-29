"""UI-only receiver: remember that the user's saved language must be applied after login (see views.login_view)."""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def remember_language(sender, request, user, **kwargs):
    if request is not None:
        request._wb_login_language = user.language
