# -*- coding: utf-8 -*-

import logging
from .llama_provider import LlamaProvider
from .openai_provider import OpenAIProvider
from .odoo_native_provider import OdooNativeAIProvider

_logger = logging.getLogger(__name__)


class AIProviderFactory:
    """
    Factory to create AI provider instances based on configuration
    Supports: Llama, Mistral, OpenAI, Odoo Native
    """

    @staticmethod
    def get_provider(env=None, company_id=None, provider_type=None):
        """
        Get AI provider instance based on configuration

        Args:
            env: Odoo environment
            company_id: Company ID (optional, uses current company if not provided)
            provider_type: Force specific provider type (optional)

        Returns:
            BaseAIProvider: Configured AI provider instance
        """
        if not env:
            _logger.warning("No environment provided, using Odoo Native AI")
            return OdooNativeAIProvider()

        try:
            # Get configuration
            AIConfig = env['hr.ai.provider.config']

            if company_id:
                config = AIConfig.search([('company_id', '=', company_id)], limit=1)
            else:
                config = AIConfig.search([('company_id', '=', env.company.id)], limit=1)

            if not config:
                _logger.info("No AI provider configured, using Odoo Native AI")
                return OdooNativeAIProvider({'env': env})

            # Override with forced provider type if provided
            if provider_type:
                config_dict = {
                    'provider': provider_type,
                    'env': env
                }
            else:
                config_dict = {
                    'provider': config.provider,
                    'llama_endpoint': config.llama_endpoint,
                    'mistral_endpoint': config.mistral_endpoint,
                    'openai_api_key': config.openai_api_key,
                    'model_name': config.model_name,
                    'timeout': config.timeout,
                    'env': env
                }

            # Create provider instance
            provider = AIProviderFactory._create_provider(config_dict)

            # Test availability
            if not provider.is_available():
                _logger.warning(f"{config_dict['provider']} provider not available, falling back to Odoo Native")
                return OdooNativeAIProvider({'env': env})

            return provider

        except Exception as e:
            _logger.error(f"Error creating AI provider: {e}, falling back to Odoo Native")
            return OdooNativeAIProvider({'env': env})

    @staticmethod
    def _create_provider(config_dict):
        """
        Create provider instance based on config

        Args:
            config_dict: Configuration dictionary

        Returns:
            BaseAIProvider: Provider instance
        """
        provider_type = config_dict.get('provider', 'odoo_native')

        if provider_type == 'llama':
            return LlamaProvider(config_dict)

        elif provider_type == 'mistral':
            # Mistral uses same Ollama-compatible API as Llama
            config_dict['llama_endpoint'] = config_dict.get('mistral_endpoint', 'http://localhost:11434')
            config_dict['model_name'] = config_dict.get('model_name', 'mistral')
            return LlamaProvider(config_dict)

        elif provider_type == 'openai':
            return OpenAIProvider(config_dict)

        elif provider_type == 'odoo_native':
            return OdooNativeAIProvider(config_dict)

        else:
            _logger.warning(f"Unknown provider type: {provider_type}, using Odoo Native")
            return OdooNativeAIProvider(config_dict)

    @staticmethod
    def test_all_providers(env):
        """
        Test all available providers

        Args:
            env: Odoo environment

        Returns:
            dict: Test results for each provider
        """
        results = {}

        providers = [
            ('llama', {'provider': 'llama', 'llama_endpoint': 'http://localhost:11434', 'model_name': 'llama3.1'}),
            ('openai', {'provider': 'openai', 'openai_api_key': 'test-key'}),
            ('odoo_native', {'provider': 'odoo_native', 'env': env}),
        ]

        for provider_name, config in providers:
            try:
                provider = AIProviderFactory._create_provider(config)
                test_result = provider.test_connection()
                results[provider_name] = test_result
            except Exception as e:
                results[provider_name] = {
                    'success': False,
                    'message': str(e),
                    'latency_ms': 0
                }

        return results


def get_ai_provider(env=None, company_id=None, provider_type=None):
    """
    Convenience function to get AI provider

    Args:
        env: Odoo environment
        company_id: Company ID (optional)
        provider_type: Force specific provider (optional)

    Returns:
        BaseAIProvider: Configured provider instance
    """
    return AIProviderFactory.get_provider(env, company_id, provider_type)
