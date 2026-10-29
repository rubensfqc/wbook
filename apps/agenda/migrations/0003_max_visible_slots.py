# Replaces the "only 4 times on empty days" switch with a per-dentist number of visible times per day.

import django.core.validators
from django.db import migrations, models


def forwards(apps, schema_editor):
    BookingSettings = apps.get_model("agenda", "BookingSettings")
    BookingSettings.objects.filter(limit_empty_days=False).update(max_visible_slots=0)


def backwards(apps, schema_editor):
    BookingSettings = apps.get_model("agenda", "BookingSettings")
    BookingSettings.objects.filter(max_visible_slots=0).update(limit_empty_days=False)


class Migration(migrations.Migration):

    dependencies = [
        ("agenda", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingsettings",
            name="max_visible_slots",
            field=models.PositiveSmallIntegerField(
                default=4,
                help_text="Quantos horários livres visitantes e pacientes veem em cada dia. 0 = mostrar todos.",
                validators=[django.core.validators.MaxValueValidator(50)],
                verbose_name="horários visíveis por dia para pacientes",
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="bookingsettings",
            name="limit_empty_days",
        ),
    ]
