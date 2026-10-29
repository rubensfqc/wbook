import os
import secrets

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.utils import timezone
from django.utils.deconstruct import deconstructible


@deconstructible
class UploadTo:
    """Random file names: <prefix>/YYYY/MM/<hex>.<ext>."""

    def __init__(self, prefix):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()[:10] or ".bin"
        now = timezone.now()
        return f"{self.prefix}/{now:%Y}/{now:%m}/{secrets.token_hex(12)}{ext}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and other.prefix == self.prefix


class HashedStaticStorage(ManifestStaticFilesStorage):
    manifest_strict = False
