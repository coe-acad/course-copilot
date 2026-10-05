"""Helpers for identifying and id-ing directly-uploaded image resources.

PDF image extraction was removed. Directly-uploaded png/jpeg images are stored in
Mongo (see ``services.mongo.save_resource_image``) rather than extracted from PDFs
here. Only the two small filename helpers below remain, shared by the upload path.
"""
from __future__ import annotations

import os
import re

# Files that are an image the user uploaded directly.
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def is_image_filename(filename: str) -> bool:
    """True if the filename looks like an image the user uploaded directly."""
    return os.path.splitext(filename or "")[1].lower() in IMAGE_EXTENSIONS


def resource_image_id(resource_name: str) -> str:
    """Stable, URL-safe id for a directly-uploaded image resource (stored in Mongo).

    Prefixed ``res_`` and includes the extension so ``a.png`` / ``a.jpg`` differ.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", resource_name or "").strip("_") or "image"
    return f"res_{slug}"
