import re

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


def unique_username(email, exclude_pk=None):
    base = re.sub(r"[^a-z0-9._-]", "", (email or "user").split("@")[0].lower())[:30] or "user"
    candidate, n = base, 1
    qs = User.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(username=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


class WbUserManager(UserManager):
    def _create_user(self, username, email, password, **extra):
        email = self.normalize_email(email).lower()
        user = self.model(email=email, username=(username or "").lower() or None, **extra)
        user.set_password(password) if password else user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, username=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra)

    def create_superuser(self, email=None, password=None, username=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role=User.Role.OPERATOR)
        return self._create_user(username, email, password, **extra)

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)


class User(AbstractUser):
    class Role(models.TextChoices):
        DENTIST = "DENTIST", _("Dentista")
        PATIENT = "PATIENT", _("Paciente")
        OPERATOR = "OPERATOR", _("Operador")

    first_name = None
    last_name = None
    username = models.CharField(_("usuário"), max_length=60, unique=True, null=True, blank=True)
    email = models.EmailField(_("e-mail"), unique=True)
    name = models.CharField(_("nome"), max_length=120, blank=True)
    phone = models.CharField(_("telefone"), max_length=30, blank=True)
    role = models.CharField(_("papel"), max_length=10, choices=Role.choices, default=Role.PATIENT)
    language = models.CharField(_("idioma"), max_length=8, choices=[("pt-br", "Português"), ("en", "English")], default="pt-br")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = WbUserManager()

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")

    def __str__(self):
        return self.name or self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").lower().strip()
        if self.username:
            self.username = self.username.lower().strip()
        else:
            self.username = unique_username(self.email, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    @property
    def is_dentist(self):
        return self.role == self.Role.DENTIST

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT

    @property
    def is_operator(self):
        return self.role == self.Role.OPERATOR

    @property
    def first_name_display(self):
        return (self.name or self.email).split()[0]
