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

    # --- Vision (document OCR) — additive, C18.6 -------------------------
    def supports_vision(self):
        return True

    def generate_vision(self, prompt, images, max_tokens=1500, **kwargs):
        """Vision via Chat Completions image_url data-URI content parts.

        OpenAI's chat endpoint does not read application/pdf directly — the
        caller (biz.doc.ocr) gates PDFs on accepts_pdf() (False here) and
        surfaces a clear message rather than half-working (§5.6)."""
        try:
            client = self._get_client()
            content = [{"type": "text", "text": prompt}]
            for img in images or []:
                mime = img.get('mime', 'image/png')
                if mime == 'application/pdf':
                    raise ValueError(
                        "OpenAI vision cannot read PDFs directly — supply page images.")
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{img.get('data_b64', '')}",
                    },
                })
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            _logger.error(f"OpenAI vision error: {e}")
            raise

    def transcribe_audio(self, audio_bytes, language='en'):
        """
        Transcribe audio to text using OpenAI Whisper API.

        Args:
            audio_bytes: Raw audio file bytes (webm, mp3, wav, etc.)
            language: Language hint for Whisper (default: 'en')

        Returns:
            str: Transcribed text
        """
        try:
            import io
            client = self._get_client()

            # Wrap bytes in a file-like object with a name
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice_recording.webm"

            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
            )
            text = response.text.strip()
            _logger.info("PayAI Whisper: transcribed %d bytes → '%s'",
                         len(audio_bytes), text[:80])
            return text
        except Exception as e:
            _logger.error("PayAI Whisper transcription error: %s", e)
            raise

    def text_to_speech(self, text, voice='alloy'):
        """
        Convert text to speech using OpenAI TTS API.

        Args:
            text: Text to synthesize (max ~4096 chars)
            voice: Voice preset: alloy, echo, fable, onyx, nova, shimmer

        Returns:
            bytes: MP3 audio bytes
        """
        try:
            client = self._get_client()
            # Truncate long text for TTS
            tts_text = text[:4000] if len(text) > 4000 else text

            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=tts_text,
            )
            audio_bytes = response.content
            _logger.info("PayAI TTS: generated %d bytes audio for %d chars",
                         len(audio_bytes), len(tts_text))
            return audio_bytes
        except Exception as e:
            _logger.error("PayAI TTS error: %s", e)
            raise
