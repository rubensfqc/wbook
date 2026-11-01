import re

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

USERNAME_RE = r"^[a-z0-9][a-z0-9._-]{2,39}$"


def unique_username(base, exclude_pk=None):
    """'Ana.Lima+x@…' -> 'ana.lima-x', made unique with -2, -3… Always matches USERNAME_RE."""
    root = re.sub(r"[^a-z0-9._-]+", "-", (base or "").split("@")[0].lower()).strip("._-")[:34] or "usuario"
    if len(root) < 3:
        root = (root + "-usr")[:3] if root else "usr"
    qs = User.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    candidate, n = root, 2
    while qs.filter(username__iexact=candidate).exists():
        candidate = f"{root}-{n}"
        n += 1
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
    username = models.CharField(
        _("nome de usuário"), max_length=60, unique=True, null=True, blank=True,
        validators=[RegexValidator(USERNAME_RE, _("Use 3 a 40 letras minúsculas, números, ponto, hífen ou _ (sem espaços)."))],
        help_text=_("Pode ser usado no lugar do e-mail para entrar."),
    )
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
