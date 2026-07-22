# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
import json
import logging

_logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers used in PayAI.
    Provides the interface for text generation and chart-aware responses.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.logger = _logger

    @abstractmethod
    def generate_text(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        """
        Generate text completion from prompt.

        Args:
            prompt (str): Input prompt text
            max_tokens (int): Maximum tokens to generate
            temperature (float): Sampling temperature (0-1)

        Returns:
            str: Generated text
        """
        pass

    def generate_chat(self, messages, max_tokens=2000, temperature=0.7, **kwargs):
        """
        Generate chat completion from message history.

        Args:
            messages (list): List of dicts with 'role' and 'content' keys
            max_tokens (int): Maximum tokens
            temperature (float): Sampling temperature

        Returns:
            str: Generated response text
        """
        # Default: convert messages to single prompt
        prompt = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages
        )
        return self.generate_text(prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)

    def generate_structured(self, prompt, schema_hint=None, max_tokens=2000, temperature=0.3):
        """
        Generate a structured JSON response.

        Args:
            prompt (str): Input prompt
            schema_hint (str): Optional JSON schema hint for the LLM
            max_tokens (int): Maximum tokens
            temperature (float): Low temperature for structured output

        Returns:
            dict: Parsed JSON response
        """
        full_prompt = prompt
        if schema_hint:
            full_prompt += f"\n\nRespond ONLY with valid JSON matching this schema:\n{schema_hint}"

        response = self.generate_text(full_prompt, max_tokens=max_tokens, temperature=temperature)
        return self._parse_json_response(response)

    def is_available(self):
        """Check if provider is available and configured."""
        return True

    # --- Vision (document OCR) — additive, C18.6 -------------------------
    def supports_vision(self):
        """Whether this provider can read images / documents. Default False."""
        return False

    def accepts_pdf(self):
        """Whether generate_vision can take an application/pdf image directly
        (without page-to-image rasterization). Default False — only providers
        with native PDF support override to True."""
        return False

    def generate_vision(self, prompt, images, max_tokens=1500, **kwargs):
        """Vision completion over one or more document images.

        Args:
            prompt (str): the extraction instruction.
            images (list): ``[{'mime': 'image/png'|'image/jpeg'|'application/pdf',
                              'data_b64': str}]``.

        Returns:
            str: raw model text (the caller parses it — e.g. via
            ``_parse_json_response``).
        """
        raise NotImplementedError

    def test_connection(self):
        """
        Test connection to AI service.

        Returns:
            dict: {'success': bool, 'message': str, 'latency_ms': float}
        """
        try:
            import time
            start = time.time()
            response = self.generate_text("Say 'OK' if you can hear me.", max_tokens=10)
            latency = round((time.time() - start) * 1000)

            return {
                'success': True,
                'message': f'Connection successful. Response: {response[:50]}',
                'latency_ms': latency,
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'latency_ms': 0,
            }

    def _parse_json_response(self, text):
        """
        Parse JSON from AI response, handling markdown code blocks.

        Args:
            text (str): AI response that may contain JSON

        Returns:
            dict or list: Parsed JSON data
        """
        if not text:
            return {}

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*([\[{].*?[\]}])\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding first { or [ to last } or ]
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")
