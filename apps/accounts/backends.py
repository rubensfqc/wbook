from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login = (username or kwargs.get("email") or "").strip().lower()
        if not login or not password:
            return None
        field = "email" if "@" in login else "username"
        try:
            user = User.objects.get(**{field: login})
        except User.DoesNotExist:
            User().set_password(password)  # timing
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
