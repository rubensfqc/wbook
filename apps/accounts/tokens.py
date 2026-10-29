from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.core.emails import absolute


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()


def uidb64(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def verify_link(user):
    return absolute(reverse("accounts:verify_email", args=[uidb64(user), email_verification_token.make_token(user)]))


def set_password_link(user):
    return absolute(reverse("accounts:set_password", args=[uidb64(user), default_token_generator.make_token(user)]))
