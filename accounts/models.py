from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Seller(AbstractUser):
    """
    Base user for wbook365.
    Doctors, Patients and Operators all share this user table.
    The profile model (DoctorProfile / PatientProfile / OperatorProfile)
    holds the role-specific data.
    """

    class Roles(models.TextChoices):
        DOCTOR   = 'DOCTOR',   _('Doctor')
        PATIENT  = 'PATIENT',  _('Patient')
        OPERATOR = 'OPERATOR', _('Operator')

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.DOCTOR,
    )

    email = models.EmailField(unique=True, verbose_name=_('Email'))
    name  = models.CharField(max_length=150, default='', blank=True, verbose_name=_('Full Name'))
    phone_number    = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Phone'))
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address         = models.CharField(max_length=255, blank=True, null=True)
    slug            = models.SlugField(unique=True, blank=True)

    # Override M2M to avoid clashes with auth.User
    groups = models.ManyToManyField(
        Group,
        related_name='seller_set',
        blank=True,
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='seller_user_permissions',
        blank=True,
        verbose_name='user permissions',
    )

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name        = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.name or self.email

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.username or self.email.split('@')[0])
            slug = base
            counter = 1
            while Seller.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # ── Role helpers ──────────────────────────────────────────────────────────

    @property
    def is_doctor(self):
        return self.role == self.Roles.DOCTOR

    @property
    def is_patient(self):
        return self.role == self.Roles.PATIENT

    @property
    def is_operator(self):
        return self.role == self.Roles.OPERATOR
