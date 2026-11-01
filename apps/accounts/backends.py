from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailOrUsernameBackend(ModelBackend):
    """Log in with the e-mail address or the username (case-insensitive)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        login = (username or kwargs.get("email") or "").strip()
        if not login or not password:
            return None
        lookup = {"email__iexact": login} if "@" in login else {"username__iexact": login}
        user = User.objects.filter(**lookup).first()
        if user is None:
            User().set_password(password)  # same work as a real check: no timing hint that the account doesn't exist
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
