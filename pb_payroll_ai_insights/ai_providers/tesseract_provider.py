# -*- coding: utf-8 -*-
"""Tesseract OCR provider — the keyless, offline no-AI fallback.

Vision-capable but returns PROSE (raw OCR text), not structured JSON — the
biz.doc.ocr service hands that prose to a deterministic post-processor. Imports
are guarded (C18.6): a server without pytesseract/PIL or the binary reports
``is_available() == False``.
"""

import base64
import io
import logging

from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)


class TesseractProvider(BaseAIProvider):

    def __init__(self, config=None):
        super().__init__(config)

    # ------------------------------------------------------------- plumbing
    @staticmethod
    def _deps():
        try:
            import pytesseract
            from PIL import Image
            return pytesseract, Image
        except ImportError:
            return None, None

    def _lang(self, pytesseract):
        """'vie+eng' when the Vietnamese traineddata is present, else 'eng'."""
        try:
            langs = pytesseract.get_languages(config='')
            return 'vie+eng' if 'vie' in langs else 'eng'
        except Exception:
            return 'eng'

    # ------------------------------------------------------------ capability
    def is_available(self):
        pytesseract, _ = self._deps()
        if not pytesseract:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def supports_vision(self):
        return True

    # -------------------------------------------------------------- vision
    def generate_vision(self, prompt, images, max_tokens=1500, **kwargs):
        pytesseract, Image = self._deps()
        if not pytesseract:
            raise ImportError("pytesseract / PIL not installed.")
        lang = self._lang(pytesseract)
        chunks = []
        for img in images or []:
            if img.get('mime') == 'application/pdf':
                continue  # PDFs need page rasterization (gated on accepts_pdf)
            raw = base64.b64decode(img.get('data_b64', ''))
            im = Image.open(io.BytesIO(raw))
            chunks.append(pytesseract.image_to_string(im, lang=lang))
        return "\n".join(chunks)

    # --------------------------------------------------- unsupported (OCR-only)
    def generate_text(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        raise NotImplementedError("Tesseract is OCR-only (no text generation).")

    def generate_chat(self, messages, max_tokens=2000, temperature=0.7, **kwargs):
        raise NotImplementedError("Tesseract is OCR-only (no chat).")
