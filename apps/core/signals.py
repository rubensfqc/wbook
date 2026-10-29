"""The only business-independent signals: delete stored files when rows are deleted or a file is replaced."""

import threading
from contextlib import contextmanager

from django.apps import apps
from django.db.models.signals import post_delete, pre_save

FILE_FIELDS = {
    "clinic.Dentist": ["logo", "photo"],
    "clinic.TreatmentFile": ["file", "thumb"],
    "landing.LandingPage": ["hero_image"],
    "landing.GalleryImage": ["image"],
    "quotes.Quote": ["attachment"],
}

_state = threading.local()


@contextmanager
def file_cleanup_suspended():
    _state.suspended = True
    try:
        yield
    finally:
        _state.suspended = False


def _suspended():
    return getattr(_state, "suspended", False)


def _delete(fieldfile):
    if fieldfile and fieldfile.name:
        try:
            fieldfile.storage.delete(fieldfile.name)
        except Exception:  # noqa: BLE001
            pass


def _on_delete(sender, instance, **kwargs):
    if _suspended():
        return
    for name in FILE_FIELDS.get(sender._meta.label, []):
        _delete(getattr(instance, name))


def _on_save(sender, instance, **kwargs):
    if _suspended() or not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    for name in FILE_FIELDS.get(sender._meta.label, []):
        old_f, new_f = getattr(old, name), getattr(instance, name)
        if old_f and old_f.name and old_f.name != (new_f.name if new_f else None):
            _delete(old_f)


def connect():
    for label in FILE_FIELDS:
        model = apps.get_model(label)
        post_delete.connect(_on_delete, sender=model, dispatch_uid=f"del-{label}")
        pre_save.connect(_on_save, sender=model, dispatch_uid=f"save-{label}")
