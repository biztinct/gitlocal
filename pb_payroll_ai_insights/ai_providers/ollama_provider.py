# -*- coding: utf-8 -*-
"""Ollama (local) provider — text + chat + vision via a plain HTTP call.

No SDK: talks to the Ollama daemon over ``requests`` (C18.6 — a missing daemon
is reported by ``is_available()``, never an ImportError). Default model ``llava``
is vision-capable (``qwen-vl`` / ``llama3.2-vision`` also work).
"""

import logging

import requests

from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)

_DEFAULT_URL = 'http://localhost:11434'
_DEFAULT_MODEL = 'llava'


class OllamaProvider(BaseAIProvider):

    def __init__(self, config=None):
        super().__init__(config)
        self.base_url = (self.config.get('base_url') or _DEFAULT_URL).rstrip('/')
        self.model = self.config.get('model_name') or _DEFAULT_MODEL
        self.timeout = self.config.get('timeout', 120)

    # ------------------------------------------------------------ capability
    def is_available(self):
        """One cheap GET /api/tags with a short timeout."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def supports_vision(self):
        return True

    # ------------------------------------------------------------- plumbing
    def _chat(self, messages, max_tokens):
        r = requests.post(
            f"{self.base_url}/api/chat",
            json={'model': self.model, 'messages': messages, 'stream': False,
                  'options': {'num_predict': max_tokens}},
            timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return (data.get('message') or {}).get('content', '')

    # --------------------------------------------------------------- text
    def generate_text(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        return self._chat([{'role': 'user', 'content': prompt}], max_tokens)

    def generate_chat(self, messages, max_tokens=2000, temperature=0.7, **kwargs):
        conv = [{'role': m.get('role', 'user'), 'content': m.get('content', '')}
                for m in messages]
        return self._chat(conv, max_tokens)

    # -------------------------------------------------------------- vision
    def generate_vision(self, prompt, images, max_tokens=1500, **kwargs):
        # Ollama takes raw base64 strings in message['images'] (no data: prefix);
        # PDFs are not image data and are gated upstream on accepts_pdf() (False).
        imgs = [img.get('data_b64', '') for img in (images or [])
                if img.get('mime') != 'application/pdf' and img.get('data_b64')]
        msg = {'role': 'user', 'content': prompt, 'images': imgs}
        return self._chat([msg], max_tokens)
