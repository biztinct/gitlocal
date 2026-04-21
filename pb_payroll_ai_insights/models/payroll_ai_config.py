# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PayrollAIConfig(models.Model):
    """Configuration model for PayAI provider settings."""

    _name = 'payroll.ai.config'
    _description = 'PayAI Configuration'
    _rec_name = 'provider_type'

    provider_type = fields.Selection([
        ('openai', 'OpenAI (GPT-4o / GPT-4o-mini)'),
    ], string='AI Provider', default='openai', required=True)

    api_key = fields.Char(
        string='API Key',
        help='API key for the selected AI provider',
    )

    model_name = fields.Char(
        string='Model Name',
        default='gpt-4o-mini',
        help='Model identifier (e.g., gpt-4o-mini, gpt-4o)',
    )

    base_url = fields.Char(
        string='Base URL (Optional)',
        help='Custom API base URL. Leave empty for default.',
    )

    timeout = fields.Integer(
        string='Timeout (seconds)',
        default=120,
        help='Maximum time to wait for AI response',
    )

    max_tokens = fields.Integer(
        string='Max Tokens',
        default=2000,
        help='Maximum tokens in AI response',
    )

    temperature = fields.Float(
        string='Temperature',
        default=0.7,
        help='Creativity level (0=deterministic, 1=creative)',
    )

    is_active = fields.Boolean(
        string='Active',
        default=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    # --- Helper Methods ---

    @api.model
    def get_active_config(self):
        """Get the active AI configuration for current company."""
        config = self.sudo().search([
            ('is_active', '=', True),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not config:
            # Try global config (no company filter)
            config = self.sudo().search([
                ('is_active', '=', True),
            ], limit=1)

        return config

    def get_provider_config_dict(self):
        """Return config as dict for provider factory."""
        self.ensure_one()
        # Sanitize API key — strip invisible Unicode chars (U+202F etc.)
        # that can be introduced during copy-paste
        import re
        raw_key = self.api_key or ''
        clean_key = re.sub(r'[^\x20-\x7E]', '', raw_key).strip()
        return {
            'api_key': clean_key,
            'model_name': self.model_name or 'gpt-4o-mini',
            'base_url': self.base_url or None,
            'timeout': self.timeout or 120,
            'max_tokens': self.max_tokens or 2000,
            'temperature': self.temperature or 0.7,
        }

    def get_provider(self):
        """Get an instantiated AI provider."""
        self.ensure_one()
        from ..ai_providers.provider_factory import get_provider
        return get_provider(self.provider_type, self.get_provider_config_dict())

    def action_test_connection(self):
        """Test the AI connection and show result."""
        self.ensure_one()

        if not self.api_key:
            raise UserError(_('Please configure an API key first.'))

        try:
            provider = self.get_provider()
            result = provider.test_connection()

            if result['success']:
                message = _(
                    'Connection successful!\n'
                    'Latency: %(latency)s ms\n'
                    'Response: %(message)s',
                    latency=result['latency_ms'],
                    message=result['message'],
                )
                msg_type = 'success'
            else:
                message = _(
                    'Connection failed: %(message)s',
                    message=result['message'],
                )
                msg_type = 'danger'

        except Exception as e:
            message = _('Error: %(error)s', error=str(e))
            msg_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': msg_type,
                'sticky': msg_type == 'danger',
            },
        }
