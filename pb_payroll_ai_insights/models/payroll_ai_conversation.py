# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollAIConversation(models.Model):
    """Chat conversation model for PayAI — persists chat sessions with chart history."""

    _name = 'payroll.ai.conversation'
    _description = 'PayAI Conversation'
    _order = 'create_date desc'

    name = fields.Char(
        string='Session Name',
        default=lambda self: _('PayAI Chat'),
        required=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
    )

    message_ids = fields.One2many(
        'payroll.ai.message',
        'conversation_id',
        string='Messages',
    )

    state = fields.Selection([
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='active', string='Status')

    message_count = fields.Integer(
        compute='_compute_message_count',
        string='Messages',
    )

    @api.depends('message_ids')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.model
    def get_or_create_session(self, user_id=None):
        """Get active session for user or create new one."""
        user_id = user_id or self.env.user.id
        session = self.search([
            ('user_id', '=', user_id),
            ('state', '=', 'active'),
        ], limit=1, order='create_date desc')

        if not session:
            session = self.create({
                'name': _('PayAI Chat'),
                'user_id': user_id,
            })

        return session

    def add_message(self, role, content, chart_config=None, insights=None, intent=None):
        """Add a message to the conversation."""
        self.ensure_one()
        return self.env['payroll.ai.message'].create({
            'conversation_id': self.id,
            'role': role,
            'content': content,
            'chart_config': json.dumps(chart_config) if chart_config else False,
            'insights': json.dumps(insights) if insights else False,
            'intent': intent or False,
        })

    def get_history(self, limit=20):
        """Get conversation history as list of dicts."""
        self.ensure_one()
        messages = self.message_ids.sorted('create_date')[-limit:]
        return [
            {
                'role': msg.role,
                'content': msg.content,
                'chart': json.loads(msg.chart_config) if msg.chart_config else None,
                'insights': json.loads(msg.insights) if msg.insights else [],
                'timestamp': msg.create_date.isoformat() if msg.create_date else '',
                'intent': msg.intent or '',
            }
            for msg in messages
        ]

    def action_clear(self):
        """Clear all messages in conversation."""
        self.ensure_one()
        self.message_ids.unlink()
        return True

    # --- RPC methods called from frontend ---

    @api.model
    def rpc_send_message(self, message, session_id=None):
        """
        RPC endpoint for the chat widget.

        Args:
            message (str): User's message
            session_id (int): Optional session ID to continue conversation

        Returns:
            dict: AI response with chart config
        """
        # Get or create session
        if session_id:
            session = self.browse(session_id).exists()
            if not session:
                session = self.get_or_create_session()
        else:
            session = self.get_or_create_session()

        # Save user message
        session.add_message('user', message)

        # Get conversation history
        history = session.get_history(limit=10)

        # Process through AI engine
        engine = self.env['payroll.ai.engine']
        result = engine.process_message(
            message,
            conversation_history=history[:-1],  # Exclude the message we just added
            context={'user_id': self.env.user.id},
        )

        # Save assistant response
        session.add_message(
            'assistant',
            result.get('response', ''),
            chart_config=result.get('chart'),
            insights=result.get('insights'),
            intent=result.get('intent'),
        )

        return {
            'session_id': session.id,
            'response': result.get('response', ''),
            'chart': result.get('chart'),
            'insights': result.get('insights', []),
            'follow_up_questions': result.get('follow_up_questions', []),
            'intent': result.get('intent', ''),
            'drilldown_model': result.get('drilldown_model', ''),
            'action': result.get('action'),
        }

    @api.model
    def rpc_get_history(self, session_id=None):
        """RPC endpoint to get chat history."""
        if session_id:
            session = self.browse(session_id).exists()
        else:
            session = self.get_or_create_session()

        if not session:
            return {'session_id': None, 'messages': []}

        return {
            'session_id': session.id,
            'messages': session.get_history(limit=50),
        }

    @api.model
    def rpc_clear_history(self, session_id=None):
        """RPC endpoint to clear chat history."""
        if session_id:
            session = self.browse(session_id).exists()
            if session:
                session.action_clear()
        return True

    @api.model
    def rpc_send_voice_message(self, audio_base64, session_id=None, tts_enabled=False):
        """
        RPC endpoint for voice input.
        Receives base64 audio → Whisper → AI engine → response (+ optional TTS).

        Args:
            audio_base64 (str): Base64-encoded audio blob (webm format from MediaRecorder)
            session_id (int): Optional session ID
            tts_enabled (bool): If True, also return TTS audio of the response

        Returns:
            dict: Same as rpc_send_message plus transcribed_text and tts_audio
        """
        import base64

        # Decode audio
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as e:
            _logger.error("PayAI voice: Failed to decode audio: %s", e)
            return {'error': 'Failed to decode audio data'}

        # Get AI provider for Whisper
        config_model = self.env['payroll.ai.config']
        config = config_model.get_active_config()
        if not config:
            return {'error': 'PayAI not configured. Go to PayAI → Configuration.'}

        provider = config.get_provider_instance()
        if not provider or not hasattr(provider, 'transcribe_audio'):
            return {'error': 'Voice feature requires OpenAI provider with Whisper support'}

        # Transcribe audio → text
        try:
            transcribed_text = provider.transcribe_audio(audio_bytes)
        except Exception as e:
            _logger.error("PayAI voice transcription failed: %s", e)
            return {'error': f'Transcription failed: {str(e)}'}

        if not transcribed_text or not transcribed_text.strip():
            return {'error': 'Could not understand audio. Please try again.'}

        # Process transcribed text through normal message flow
        result = self.rpc_send_message(transcribed_text, session_id)

        # Add the transcribed text so frontend knows what was said
        result['transcribed_text'] = transcribed_text

        # Generate TTS if requested
        if tts_enabled and result.get('response'):
            try:
                tts_bytes = provider.text_to_speech(result['response'])
                result['tts_audio'] = base64.b64encode(tts_bytes).decode('utf-8')
            except Exception as e:
                _logger.warning("PayAI TTS failed (non-critical): %s", e)
                result['tts_audio'] = False

        return result


class PayrollAIMessage(models.Model):
    """Individual message in a PayAI conversation."""

    _name = 'payroll.ai.message'
    _description = 'PayAI Message'
    _order = 'create_date asc'

    conversation_id = fields.Many2one(
        'payroll.ai.conversation',
        string='Conversation',
        required=True,
        ondelete='cascade',
    )

    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'PayAI'),
        ('system', 'System'),
    ], string='Role', required=True)

    content = fields.Text(string='Content', required=True)

    chart_config = fields.Text(
        string='Chart Configuration',
        help='JSON Chart.js configuration for inline chart rendering',
    )

    insights = fields.Text(
        string='Insights',
        help='JSON list of insight strings',
    )

    intent = fields.Char(
        string='Intent',
        help='Classified intent: payroll_data, payroll_knowledge, general',
    )
