# -*- coding: utf-8 -*-

import json

from odoo import models, fields, api, _


class AICoachingWizard(models.TransientModel):
    _name = 'ai.coaching.wizard'
    _description = 'AI Coaching Chat Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env.user.employee_id
    )

    topic = fields.Selection([
        ('skill_development', 'Skill Development'),
        ('career_planning', 'Career Planning'),
        ('performance', 'Performance Improvement'),
        ('goal_setting', 'Goal Setting'),
        ('general', 'General Coaching')
    ], string='Topic', required=True, default='general')

    user_message = fields.Text(
        string='Your Question/Situation',
        required=True
    )

    ai_response = fields.Html(
        string='AI Coach Response',
        readonly=True
    )

    ai_transcript = fields.Text(
        string='AI Transcript',
        help='Transcript of the AI coaching conversation (stored as JSON)'
    )

    conversation_history = fields.Text(
        string='Conversation History',
        readonly=True
    )

    ai_provider = fields.Char(
        string='AI Provider',
        compute='_compute_ai_provider'
    )

    def _compute_ai_provider(self):
        """Show which AI provider will be used"""
        for wizard in self:
            config = self.env['hr.ai.provider.config'].get_config()
            wizard.ai_provider = dict(config._fields['provider'].selection).get(config.provider, 'Unknown')

    def _format_conversation_history(self, messages):
        """Format transcript messages into readable history"""
        lines = []
        for message in messages:
            role = message.get('role', 'assistant')
            content = message.get('content', '')
            label = 'You' if role == 'user' else 'AI Coach'
            lines.append(f"{label}: {content}")
            lines.append("")
        return "\n".join(lines).strip()

    def _build_coaching_response(self, message):
        """Generate response and metadata for the coaching message"""
        from ..ai_providers.provider_factory import get_ai_provider

        ai_provider = get_ai_provider(self.env)
        context = {
            'employee_name': self.employee_id.name,
            'situation': self.topic,
            'relevant_data': {
                'question': message,
                'job': self.employee_id.job_id.name if self.employee_id.job_id else '',
                'skills': [s.skill_id.name for s in self.employee_id.skill_ids[:10]],
                'recent_coaching': []
            },
            'tone': 'supportive'
        }

        result = ai_provider.generate_coaching_nudge(context)
        response_text = result.get('message', '')
        action_items = result.get('action_items', [])
        priority = result.get('priority', 'medium')

        if action_items:
            response_text += "\n\nSuggested Actions:\n" + "\n".join(
                f"- {item}" for item in action_items
            )
        response_text += f"\n\nPriority: {priority.title()}"

        return response_text, result

    def action_get_ai_response(self):
        """Get AI coaching response"""
        self.ensure_one()

        try:
            message = (self.user_message or '').strip()
            response_text, result = self._build_coaching_response(message)

            # Format response
            response_html = f"""
            <div class="ai_coaching_response">
                <h4>{result.get('message', '')}</h4>

                <h5>Suggested Actions:</h5>
                <ul>
                    {''.join(f'<li>{action}</li>' for action in result.get('action_items', []))}
                </ul>

                <p><em>Priority: {result.get('priority', 'medium').title()}</em></p>
            </div>
            """

            self.ai_response = response_html

            # Update transcript
            messages = []
            if self.ai_transcript:
                try:
                    messages = json.loads(self.ai_transcript).get('messages', [])
                except (json.JSONDecodeError, ValueError):
                    messages = []

            messages.extend([
                {
                    'role': 'user',
                    'content': message,
                    'timestamp': fields.Datetime.now().isoformat()
                },
                {
                    'role': 'assistant',
                    'content': response_text,
                    'timestamp': fields.Datetime.now().isoformat()
                }
            ])

            self.ai_transcript = json.dumps({
                'messages': messages,
                'updated_at': fields.Datetime.now().isoformat()
            })
            self.conversation_history = self._format_conversation_history(messages)

            # Clear user message for next question
            self.user_message = ''

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ai.coaching.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Coaching Error',
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_send_ai_message(self, message):
        """Send message to AI coach and return response (for chat widget)"""
        self.ensure_one()

        if not message or not message.strip():
            return {'response': 'Please enter a question or topic to discuss.'}

        response_text, _result = self._build_coaching_response(message.strip())
        return {'response': response_text}

    def action_save_as_session(self):
        """Save conversation as coaching session"""
        self.ensure_one()

        if not self.ai_transcript and not self.conversation_history:
            return

        session = self.env['hr.coaching.session'].create({
            'name': f'AI Coaching: {self.topic.replace("_", " ").title()}',
            'employee_id': self.employee_id.id,
            'session_type': 'ai',
            'topic': self.topic,
            'ai_transcript': self.ai_transcript or self.conversation_history,
            'state': 'completed'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.coaching.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current'
        }
