# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AIProviderConfig(models.Model):
    _name = 'hr.ai.provider.config'
    _description = 'AI Provider Configuration'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade'
    )

    provider = fields.Selection([
        ('llama', 'Llama (Open Source via Ollama)'),
        ('mistral', 'Mistral (Open Source)'),
        ('openai', 'OpenAI ChatGPT'),
        ('odoo_native', 'Native AI')
    ], string='AI Provider', required=True, default='odoo_native',
        help="Select the AI provider to use for talent intelligence, coaching, and recommendations")

    # Provider-specific configurations
    llama_endpoint = fields.Char(
        string='Llama/Ollama Endpoint',
        default='http://localhost:11434',
        help='URL of Ollama server (e.g., http://localhost:11434)'
    )

    mistral_endpoint = fields.Char(
        string='Mistral Endpoint',
        default='http://localhost:11434',
        help='URL of Mistral server'
    )

    openai_api_key = fields.Char(
        string='OpenAI API Key',
        help='Your OpenAI API key for ChatGPT access'
    )

    model_name = fields.Char(
        string='Model Name',
        help='Specific model to use (e.g., llama3.1, gpt-4o-mini, mistral-large)'
    )

    timeout = fields.Integer(
        string='Timeout (seconds)',
        default=60,
        help='Request timeout in seconds'
    )

    # Status and testing
    is_active = fields.Boolean(string='Active', default=True)
    last_test_date = fields.Datetime(string='Last Tested', readonly=True)
    last_test_result = fields.Text(string='Last Test Result', readonly=True)
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('success', 'Connected'),
        ('failed', 'Connection Failed')
    ], string='Status', default='not_tested', readonly=True)

    # AI Coach Appearance
    ai_coach_icon = fields.Image(
        string='AI Coach Avatar',
        help='Upload a custom icon/avatar for the AI Coach panel. '
             'Recommended size: 128x128 pixels. If not set, default robot icon is used.',
        max_width=256, max_height=256,
    )

    _sql_constraints = [
        ('company_uniq', 'unique(company_id)', 'Only one AI provider configuration per company!')
    ]

    @api.model
    def get_ai_coach_icon_url(self):
        """Return the AI coach icon as a data URL for the frontend."""
        config = self.search([
            ('company_id', '=', self.env.company.id),
            ('is_active', '=', True),
        ], limit=1)
        if config and config.ai_coach_icon:
            import base64
            icon_b64 = config.ai_coach_icon
            if isinstance(icon_b64, bytes):
                icon_b64 = icon_b64.decode('utf-8')
            return 'data:image/png;base64,' + icon_b64
        return False

    @api.model
    def get_config(self, company_id=None):
        """
        Get AI provider configuration for company

        Args:
            company_id: Company ID (uses current company if not provided)

        Returns:
            hr.ai.provider.config: Configuration record
        """
        if not company_id:
            company_id = self.env.company.id

        config = self.search([('company_id', '=', company_id), ('is_active', '=', True)], limit=1)

        if not config:
            # Create default configuration
            config = self.create({
                'company_id': company_id,
                'provider': 'odoo_native'
            })

        return config

    def action_test_connection(self):
        """Test connection to AI provider"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import AIProviderFactory

            provider = AIProviderFactory.get_provider(
                env=self.env,
                company_id=self.company_id.id
            )

            result = provider.test_connection()

            self.last_test_date = fields.Datetime.now()
            self.last_test_result = result.get('message', '')

            if result.get('success'):
                self.connection_status = 'success'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('AI Provider is available. Latency: %s ms') % result.get('latency_ms', 0),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.connection_status = 'failed'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': result.get('message', 'Unknown error'),
                        'type': 'danger',
                        'sticky': True,
                    }
                }

        except Exception as e:
            self.connection_status = 'failed'
            self.last_test_result = str(e)
            _logger.error(f"AI Provider test failed: {e}")
            raise ValidationError(_('Connection test failed: %s') % str(e))

    def action_test_all_providers(self):
        """Test all available providers"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import AIProviderFactory

            results = AIProviderFactory.test_all_providers(self.env)

            message_lines = []
            for provider_name, result in results.items():
                status = '✓' if result.get('success') else '✗'
                latency = result.get('latency_ms', 0)
                msg = result.get('message', '')
                message_lines.append(f"{status} {provider_name}: {msg} ({latency}ms)")

            message = '\n'.join(message_lines)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Provider Test Results'),
                    'message': message,
                    'type': 'info',
                    'sticky': True,
                }
            }

        except Exception as e:
            _logger.error(f"Provider tests failed: {e}")
            raise ValidationError(_('Provider tests failed: %s') % str(e))

    @api.model_create_multi
    def create(self, vals_list):
        """Set default model names based on provider"""
        for vals in vals_list:
            if not vals.get('model_name'):
                provider = vals.get('provider', 'odoo_native')
                if provider == 'llama':
                    vals['model_name'] = 'llama3.1'
                elif provider == 'mistral':
                    vals['model_name'] = 'mistral-large'
                elif provider == 'openai':
                    vals['model_name'] = 'gpt-4o-mini'

        return super().create(vals_list)
