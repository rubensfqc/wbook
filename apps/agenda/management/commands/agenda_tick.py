"""Reminders (24 h before), expiry of PENDING requests, operator alert for dentists expiring in 3 days. Idempotent."""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.agenda import notify, services
from apps.agenda.models import Appointment
from apps.clinic.models import Dentist
from apps.core.activity import log_action
from apps.core.notifications import notify_operator


class Command(BaseCommand):
    help = "Lembretes 24 h antes, expiração de pedidos pendentes e alerta de acesso acabando."

    def handle(self, *args, **opts):
        now = timezone.now()
        expired = services.expire_pending(now)

        reminders = 0
        qs = Appointment.objects.filter(status="CONFIRMED", start__gt=now, start__lte=now + timedelta(hours=24),
                                        reminder_sent_at__isnull=True).select_related("dentist__user", "type", "patient__user", "lead")
        for appt in qs:
            notify.reminder(appt)
            appt.reminder_sent_at = timezone.now()
            appt.save(update_fields=["reminder_sent_at"])
            reminders += 1

        expiring = 0
        marker = Path(settings.BASE_DIR) / "var" / f"expiring-alert-{timezone.localdate()}"
        if not marker.exists():
            target = timezone.localdate() + timedelta(days=3)
            for d in Dentist.objects.filter(is_suspended=False).select_related("user"):
                if d.access_until == target:
                    notify_operator("alert_dentist_expiring", f"Acesso de {d.clinic_name} acaba em 3 dias",
                                    "operator_dentist_expiring", {"dentist": d})
                    expiring += 1
            marker.parent.mkdir(parents=True, exist_ok=True)
            for old in marker.parent.glob("expiring-alert-*"):
                old.unlink(missing_ok=True)
            marker.touch()

        log_action(None, "agenda", "agenda_tick: %(e)s expirados, %(r)s lembretes, %(x)s alertas de acesso",
                   e=expired, r=reminders, x=expiring)
        self.stdout.write(f"expired={expired} reminders={reminders} expiring_alerts={expiring}")
