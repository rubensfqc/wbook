"""Clinical photos: HEIC/WEBP/PNG/JPEG → JPEG, EXIF removed, orientation applied, 480 px thumbnail."""

import io

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    pass

MAX_SIDE = 3000
THUMB_SIDE = 480


def _jpeg(img, side):
    img = img.copy()
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, optimize=True)  # no exif= → metadata dropped
    return buf.getvalue()


def process_upload(uploaded):
    """Returns (main_bytes, thumb_bytes). Raises ValidationError."""
    if uploaded.size > settings.MAX_PHOTO_MB * 1024 * 1024:
        raise ValidationError(_("A foto passa do limite de %(mb)s MB.") % {"mb": settings.MAX_PHOTO_MB})
    try:
        img = Image.open(uploaded)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError(_("Não foi possível ler esta imagem. Envie JPG, PNG, WEBP ou HEIC.")) from exc
    return _jpeg(img, MAX_SIDE), _jpeg(img, THUMB_SIDE)


def save_photo(treatment_file, uploaded):
    main, thumb = process_upload(uploaded)
    treatment_file.file.save("photo.jpg", ContentFile(main), save=False)
    treatment_file.thumb.save("thumb.jpg", ContentFile(thumb), save=False)
    treatment_file.size = len(main)
