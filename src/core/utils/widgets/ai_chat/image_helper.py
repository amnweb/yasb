"""Image processing utilities for AI chat widget."""

import logging
from typing import Any

from PyQt6.QtCore import QBuffer, QIODevice, QSize
from PyQt6.QtGui import QImage, QImageReader

from settings import DEBUG

FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

FORMAT_TO_EXT = {
    "PNG": "png",
    "JPEG": "jpg",
    "JPG": "jpg",
    "GIF": "gif",
    "WEBP": "webp",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# For the OpenAI Vision API, the recommended maximum dimension for optimal processing and token efficiency
# is to resize the image so that the longest side is no more than 2048 pixels
MAX_IMAGE_DIMENSION = 2048


def process_image(
    image_bytes: bytes,
    max_bytes: int = 0,
) -> dict[str, Any] | None:
    """Process image bytes: scale down if exceeds MAX_IMAGE_DIMENSION, compress to fit max_bytes.

    Auto-detects format from image data. Tries to preserve original format first,
    falls back to JPEG if still too large.

    Args:
        image_bytes: Raw image bytes.
        max_bytes: Maximum allowed size in bytes (0 means no limit).

    Returns:
        dict with keys: "bytes", "format", "ext", "mime_type", "compressed", "scaled"
        or None if processing fails or image cannot fit within max_bytes.
    """
    try:
        buffer = QBuffer()
        buffer.setData(image_bytes)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        reader.setAllocationLimit(1024)

        # Auto-detect format from image data
        detected = reader.format().data().decode().upper() if reader.format() else ""
        original_format = detected if detected in FORMAT_TO_MIME else "PNG"
        if original_format == "JPG":
            original_format = "JPEG"
        if DEBUG:
            logging.debug(
                "Image detected: format=%s, input_size=%d bytes",
                original_format,
                len(image_bytes),
            )

        # Scale down anything larger than MAX_IMAGE_DIMENSION to avoid memory issues
        size = reader.size()
        scaled = False
        if size.isValid():
            if DEBUG:
                logging.debug(
                    "Image dimensions: %dx%d",
                    size.width(),
                    size.height(),
                )
            if size.width() > MAX_IMAGE_DIMENSION or size.height() > MAX_IMAGE_DIMENSION:
                ratio = MAX_IMAGE_DIMENSION / max(size.width(), size.height())
                new_width = max(1, int(size.width() * ratio))
                new_height = max(1, int(size.height() * ratio))
                reader.setScaledSize(QSize(new_width, new_height))
                scaled = True
                if DEBUG:
                    logging.debug(
                        "Scaling image to %dx%d from %dx%d",
                        new_width,
                        new_height,
                        size.width(),
                        size.height(),
                    )

        img = reader.read()
        buffer.close()

        if img.isNull():
            logging.warning("Failed to read image")
            return None
        if DEBUG:
            logging.debug(
                "Image loaded: depth=%d bits, size=%dx%d",
                img.depth(),
                img.width(),
                img.height(),
            )

        def try_save(fmt: str, quality: int = -1) -> bytes:
            """Save image to bytes in given format."""
            qbuf = QBuffer()
            qbuf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(qbuf, fmt, quality)
            data = qbuf.data().data()
            qbuf.close()
            return data

        # Try original format first
        if DEBUG:
            logging.debug("Trying to save in original format: %s", original_format)
        out_bytes = try_save(original_format)
        if DEBUG:
            logging.debug(
                "Encoded original format: format=%s, size=%d bytes (limit=%d)",
                original_format,
                len(out_bytes),
                max_bytes,
            )
        if len(out_bytes) <= max_bytes:
            if DEBUG:
                logging.debug("Original format fits within limit")
            return {
                "bytes": out_bytes,
                "format": original_format,
                "ext": FORMAT_TO_EXT.get(original_format, "png"),
                "mime_type": FORMAT_TO_MIME.get(original_format, "image/png"),
                "compressed": scaled,
                "scaled": scaled,
            }

        # Try original format with quality reduction if supported (JPEG, WEBP)
        if original_format in ("JPEG", "WEBP"):
            if DEBUG:
                logging.debug("Trying quality reduction for %s", original_format)
            for quality in range(80, 0, -10):
                out_bytes = try_save(original_format, quality)
                if len(out_bytes) <= max_bytes:
                    if DEBUG:
                        logging.debug(
                            "Compressed to fit: format=%s, quality=%d, size=%d bytes",
                            original_format,
                            quality,
                            len(out_bytes),
                        )
                    return {
                        "bytes": out_bytes,
                        "format": original_format,
                        "ext": FORMAT_TO_EXT.get(original_format, "jpg"),
                        "mime_type": FORMAT_TO_MIME.get(original_format, "image/jpeg"),
                        "compressed": True,
                        "scaled": scaled,
                    }

        # Fall back to JPEG compression
        if DEBUG:
            logging.debug("Falling back to JPEG compression")
        for quality in range(85, 0, -5):
            out_bytes = try_save("JPEG", quality)
            if len(out_bytes) <= max_bytes:
                if DEBUG:
                    logging.debug(
                        "JPEG fallback successful: quality=%d, size=%d bytes",
                        quality,
                        len(out_bytes),
                    )
                return {
                    "bytes": out_bytes,
                    "format": "JPEG",
                    "ext": "jpg",
                    "mime_type": "image/jpeg",
                    "compressed": True,
                    "scaled": scaled,
                }

        logging.warning("Image could not be compressed to fit %d bytes", max_bytes)
        return None

    except Exception as e:
        logging.exception("Failed to process image: %s", e)
        return None


def qimage_to_bytes(qimage: QImage, fmt: str = "PNG") -> bytes | None:
    """Convert a QImage to bytes in the specified format.

    Args:
        qimage: The QImage to convert.
        fmt: Output format (default: "PNG").

    Returns:
        Image bytes or None if conversion fails.
    """
    try:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buffer, fmt)
        data = buffer.data().data()
        buffer.close()
        return data
    except Exception as e:
        logging.exception("Failed to convert QImage to bytes: %s", e)
        return None


def is_image_extension(suffix: str) -> bool:
    """Check if a file extension is a supported image format.

    Args:
        suffix: File extension including the dot (e.g. ".png").

    Returns:
        True if the extension is a supported image format.
    """
    return suffix.lower() in IMAGE_EXTENSIONS
