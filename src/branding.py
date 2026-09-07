from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_PIXEL_SIZE = 1600
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}


def prepare_logo(logo_bytes: bytes | None, filename: str | None = None) -> bytes | None:
    """Validate a local logo upload and normalize it to PNG bytes.

    The function preserves aspect ratio and transparency. Very large images are
    resized so the PDF generator does not carry unnecessary image data.
    """
    if not logo_bytes:
        return None
    if len(logo_bytes) > MAX_LOGO_BYTES:
        raise ValueError("Logo must be 5 MB or smaller")
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError("Logo must be JPG, JPEG or PNG")

    try:
        image = Image.open(BytesIO(logo_bytes))
        image.load()
    except Exception as exc:
        raise ValueError("The uploaded logo is not a valid image") from exc

    if image.width < 10 or image.height < 10:
        raise ValueError("Logo image is too small")

    image.thumbnail((MAX_PIXEL_SIZE, MAX_PIXEL_SIZE), Image.Resampling.LANCZOS)

    # Preserve transparency for PNG; otherwise normalize to RGB.
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")

    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()
