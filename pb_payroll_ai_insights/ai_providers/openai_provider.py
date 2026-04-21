# -*- coding: utf-8 -*-

import json
import logging
from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI provider for PayAI.
    Supports GPT-4o, GPT-4o-mini, and other OpenAI chat models.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.api_key = self.config.get('api_key', '')
        self.model = self.config.get('model_name', 'gpt-4o-mini')
        self.timeout = self.config.get('timeout', 120)
        self.base_url = self.config.get('base_url', None)
        self._client = None  # Cache client instance

        if not self.api_key:
            _logger.warning("OpenAI API key not configured for PayAI")

    def _get_client(self):
        """Get OpenAI client instance (cached)."""
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
            kwargs = {'api_key': self.api_key, 'timeout': self.timeout}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self._client = OpenAI(**kwargs)
            _logger.info("PayAI: Created OpenAI client, key_len=%d, model=%s",
                         len(self.api_key) if self.api_key else 0, self.model)
            return self._client
        except ImportError:
            raise ImportError(
                "OpenAI library not installed. Install with: pip install openai"
            )

    def generate_text(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        """Generate text using OpenAI Chat Completions API."""
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            _logger.error(f"OpenAI generation error: {e}")
            raise

    def generate_chat(self, messages, max_tokens=2000, temperature=0.7, **kwargs):
        """Generate chat completion from message history."""
        try:
            client = self._get_client()

            # Convert to OpenAI format
            openai_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                if role not in ('system', 'user', 'assistant'):
                    role = 'user'
                openai_messages.append({
                    'role': role,
                    'content': msg.get('content', ''),
                })

            response = client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            _logger.error(f"OpenAI chat error: {e}")
            raise

    def is_available(self):
        """Check if OpenAI is available."""
        return bool(self.api_key)
