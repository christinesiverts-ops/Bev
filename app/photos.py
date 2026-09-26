"""Photo intake: validate, fix rotation, strip metadata, downsize, store as JPEG."""
import io
import uuid

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

Image.MAX_IMAGE_PIXELS = 60_000_000
MAX_SIDE = 2000


async def save_upload(upload) -> str:
    raw = await upload.read()
    if not raw:
        return ""
    if len(raw) > config.MAX_PHOTO_MB * 1024 * 1024:
        raise HTTPException(400, f"Photo '{upload.filename}' is over {config.MAX_PHOTO_MB} MB.")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, f"'{upload.filename}' is not a supported image (use JPEG, PNG, HEIC-converted, WEBP).")
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    name = f"{uuid.uuid4().hex}.jpg"
    config.PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    img.save(config.PHOTO_DIR / name, "JPEG", quality=82, optimize=True)  # re-encode drops EXIF (incl. GPS)
    return name


def uploads_from(form, field: str) -> list:
    return [u for u in form.getlist(field) if hasattr(u, "read") and getattr(u, "filename", "")]
