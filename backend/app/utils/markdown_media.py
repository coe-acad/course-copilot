"""
Shared helpers for handling markdown media (images) when converting
markdown content to PDF/DOCX. Used by both text_to_pdf and text_to_docx so
that images render identically in either download format.
"""

from __future__ import annotations

import base64
import re
from io import BytesIO
from typing import Optional, Tuple

import requests

# Matches a standalone markdown image line: ![alt](src)
_IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)$")

_FETCH_TIMEOUT = 8.0  # seconds — best-effort; never block a download for long


def parse_image_line(stripped_line: str) -> Optional[Tuple[str, str]]:
    """Return (alt, src) if the line is a standalone markdown image, else None."""
    match = _IMAGE_LINE.match(stripped_line.strip())
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def fetch_image_stream(src: str) -> Optional[BytesIO]:
    """Best-effort fetch of an image into a BytesIO stream.

    Supports base64 data URIs and http(s) URLs. Returns None on any failure so
    the caller can gracefully fall back to rendering the image as a link/alt
    text instead of breaking the whole document.
    """
    try:
        if src.startswith("data:"):
            header, _, data = src.partition(",")
            if ";base64" in header and data:
                return BytesIO(base64.b64decode(data))
            return None
        if src.startswith("http://") or src.startswith("https://"):
            response = requests.get(src, timeout=_FETCH_TIMEOUT)
            response.raise_for_status()
            if not response.content:
                return None
            return BytesIO(response.content)
    except Exception:
        return None
    return None
