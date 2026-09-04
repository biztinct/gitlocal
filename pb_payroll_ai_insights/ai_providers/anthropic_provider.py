# -*- coding: utf-8 -*-
"""Anthropic Claude provider (text + chat + vision).

SDK import is guarded (C18.6): a server without the ``anthropic`` package
installs and runs — this provider just reports ``is_available() == False``.
Vision uses base64 image blocks; PDFs ride Anthropic's native document block.
"""

import logging

from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)

_DEFAULT_MODEL = 'claude-sonnet-5'


class AnthropicProvider(BaseAIProvider):
    """Anthropic Messages API provider."""

    def __init__(self, config=None):
        super().__init__(config)
        self.api_key = self.config.get('api_key', '')
        self.model = self.config.get('model_name') or _DEFAULT_MODEL
        self.timeout = self.config.get('timeout', 120)
        self.max_tokens = self.config.get('max_tokens', 2000)
        self._client = None

    # ------------------------------------------------------------- plumbing
    @staticmethod
    def _has_sdk():
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Anthropic SDK not installed. Install with: pip install anthropic")
        self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        return self._client

    @staticmethod
    def _text_from(resp):
        """Concatenate the text blocks of a Messages response."""
        try:
            return ''.join(
                getattr(p, 'text', '') for p in (resp.content or [])
                if getattr(p, 'type', '') == 'text')
        except Exception:  # pragma: no cover - defensive
            return str(resp)

    # ------------------------------------------------------------ capability
    def is_available(self):
        return bool(self.api_key) and self._has_sdk()

    def supports_vision(self):
        return True

    def accepts_pdf(self):
        return True  # Anthropic reads PDFs natively via the document block

    # --------------------------------------------------------------- text
    def generate_text(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        return self.generate_chat(
            [{'role': 'user', 'content': prompt}],
            max_tokens=max_tokens, temperature=temperature)

    def generate_chat(self, messages, max_tokens=2000, temperature=0.7, **kwargs):
        client = self._get_client()
        system = None
        conv = []
        for m in messages:
            role = m.get('role', 'user')
            if role == 'system':
                system = m.get('content', '')
                continue
            conv.append({
                'role': 'assistant' if role == 'assistant' else 'user',
                'content': m.get('content', ''),
            })
        kw = {'model': self.model, 'max_tokens': max_tokens, 'messages': conv}
        if system:
            kw['system'] = system
        return self._text_from(client.messages.create(**kw))

    # -------------------------------------------------------------- vision
    def generate_vision(self, prompt, images, max_tokens=1500, **kwargs):
        client = self._get_client()
        content = []
        for img in images or []:
            mime = img.get('mime', 'image/png')
            b64 = img.get('data_b64', '')
            if mime == 'application/pdf':
                content.append({
                    'type': 'document',
                    'source': {'type': 'base64',
                               'media_type': 'application/pdf', 'data': b64},
                })
            else:
                content.append({
                    'type': 'image',
                    'source': {'type': 'base64', 'media_type': mime, 'data': b64},
                })
        content.append({'type': 'text', 'text': prompt})
        resp = client.messages.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': content}])
        return self._text_from(resp)
