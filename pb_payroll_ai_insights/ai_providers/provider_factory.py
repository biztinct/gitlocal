# -*- coding: utf-8 -*-

import logging
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider
from .tesseract_provider import TesseractProvider

_logger = logging.getLogger(__name__)

# Registry of available providers
PROVIDER_REGISTRY = {
    'openai': OpenAIProvider,
    'anthropic': AnthropicProvider,
    'ollama': OllamaProvider,
    'tesseract': TesseractProvider,
}


def get_provider(provider_type, config):
    """
    Factory function to create an AI provider instance.

    Args:
        provider_type (str): Provider type key ('openai', 'ollama', etc.)
        config (dict): Provider configuration (api_key, model_name, etc.)

    Returns:
        BaseAIProvider: Configured provider instance

    Raises:
        ValueError: If provider_type is not registered
    """
    provider_class = PROVIDER_REGISTRY.get(provider_type)
    if not provider_class:
        available = ', '.join(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown AI provider: '{provider_type}'. "
            f"Available providers: {available}"
        )

    provider = provider_class(config)

    if not provider.is_available():
        _logger.warning(
            f"AI provider '{provider_type}' is configured but not available. "
            f"Check API key and connectivity."
        )

    return provider
