# -*- coding: utf-8 -*-

import json
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HRCoachingSession(models.Model):
    _name = 'hr.coaching.session'
    _description = 'Coaching Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc'

    name = fields.Char(string='Session Title', required=True, tracking=True)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Coachee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    coach_id = fields.Many2one(
        'hr.employee',
        string='Coach',
        ondelete='set null',
        tracking=True,
        help='Human coach (manager, mentor, or external coach)'
    )

    session_type = fields.Selection([
        ('ai', 'AI Coaching'),
        ('human', 'Human Coaching'),
        ('hybrid', 'Hybrid (AI + Human)')
    ], string='Type', required=True, default='ai', tracking=True)

    session_date = fields.Datetime(
        string='Session Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )

    duration = fields.Integer(
        string='Duration (minutes)',
        default=30
    )

    # Session content
    topic = fields.Selection([
        ('skill_development', 'Skill Development'),
        ('performance', 'Performance Improvement'),
        ('career_planning', 'Career Planning'),
        ('goal_setting', 'Goal Setting'),
        ('feedback', 'Feedback Discussion'),
        ('conflict_resolution', 'Conflict Resolution'),
        ('leadership', 'Leadership Development'),
        ('other', 'Other')
    ], string='Topic', required=True, default='skill_development')

    description = fields.Html(string='Description')

    discussion_notes = fields.Html(
        string='Discussion Notes',
        help='Notes from the coaching conversation'
    )

    ai_transcript = fields.Text(
        string='AI Transcript',
        help='Transcript of AI coaching conversation (stored as JSON)'
    )

    # Helper fields for chat dialog
    ai_chat_input = fields.Text(
        string='Your Message',
        help='Type your message to the AI coach here'
    )

    ai_chat_history = fields.Html(
        string='Chat History',
        compute='_compute_ai_chat_history',
        sanitize=False,
        help='Formatted chat conversation history'
    )

    action_items = fields.Html(
        string='Action Items',
        help='Follow-up actions agreed upon'
    )

    # Outcomes
    outcome = fields.Selection([
        ('excellent', 'Excellent Progress'),
        ('good', 'Good Progress'),
        ('moderate', 'Moderate Progress'),
        ('needs_improvement', 'Needs Improvement')
    ], string='Outcome')

    employee_satisfaction = fields.Selection([
        ('5', 'Very Satisfied'),
        ('4', 'Satisfied'),
        ('3', 'Neutral'),
        ('2', 'Dissatisfied'),
        ('1', 'Very Dissatisfied')
    ], string='Employee Satisfaction')

    # Follow-up
    next_session_date = fields.Datetime(string='Next Session')

    skill_ids = fields.Many2many(
        'hr.skill',
        string='Skills Discussed',
        help='Skills addressed in this session'
    )

    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='scheduled', required=True, tracking=True)

    is_self_coaching = fields.Boolean(
        string='Is Self Coaching',
        compute='_compute_is_self_coaching',
        help='True if the current user is the coachee (self-coaching session)'
    )

    # ===================
    # BFSI-Specific Fields
    # ===================
    kpi_context = fields.Text(
        string='KPI Context',
        help='JSON snapshot of performance data at time of session'
    )

    coaching_strategy_id = fields.Many2one(
        'bfsi.coaching.strategy',
        string='Coaching Strategy',
        help='AI-generated strategy used for this session'
    )

    # Related fields from coaching strategy for form display
    strategy_opening_questions = fields.Text(
        related='coaching_strategy_id.opening_questions', string='Opening Questions', readonly=True
    )
    strategy_probing_questions = fields.Text(
        related='coaching_strategy_id.probing_questions', string='Probing Questions', readonly=True
    )
    strategy_closing_questions = fields.Text(
        related='coaching_strategy_id.closing_questions', string='Closing Questions', readonly=True
    )
    strategy_coaching_tips = fields.Text(
        related='coaching_strategy_id.coaching_tips', string='Coaching Tips', readonly=True
    )
    strategy_session_guide = fields.Html(
        related='coaching_strategy_id.session_guide', string='Session Guide', readonly=True
    )

    action_plan_id = fields.Many2one(
        'bfsi.action.plan',
        string='Action Plan',
        help='Action plan created from this session'
    )

    coached_by_type = fields.Selection([
        ('ai_direct', 'AI Direct (Self-Service)'),
        ('ai_assisted', 'AI-Assisted Manager Coaching'),
        ('human', 'Human Only')
    ], string='Coaching Method', default='ai_direct')

    is_bfsi_session = fields.Boolean(
        string='Is BFSI Session',
        default=False,
        help='Whether this is a BFSI performance coaching session'
    )

    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True
    )

    ai_suggested_questions = fields.Html(
        string='AI Suggested Questions',
        help='AI-generated coaching questions for the manager to ask during the session',
        sanitize=False
    )

    # AI Coaching Suggestions per question category
    ai_suggestion_opening = fields.Html(
        string='AI Suggestions - Opening',
        sanitize=False,
        help='AI-generated talking points for opening questions'
    )
    ai_suggestion_probing = fields.Html(
        string='AI Suggestions - Probing',
        sanitize=False,
        help='AI-generated talking points for probing questions'
    )
    ai_suggestion_closing = fields.Html(
        string='AI Suggestions - Closing',
        sanitize=False,
        help='AI-generated talking points for closing questions'
    )
    ai_suggestion_tips = fields.Html(
        string='AI Suggestions - Tips',
        sanitize=False,
        help='AI-generated coaching tips and talking points'
    )

    @api.depends('employee_id')
    def _compute_is_self_coaching(self):
        """Determine if the current user is the coachee (self-coaching)"""
        for session in self:
            if session.employee_id and session.employee_id.user_id:
                session.is_self_coaching = (session.employee_id.user_id.id == self.env.uid)
            else:
                session.is_self_coaching = False

    @api.onchange('employee_id', 'session_type', 'session_date')
    def _onchange_auto_name(self):
        """Auto-generate session name with employee name and date"""
        if self.employee_id:
            type_label = dict(self._fields['session_type'].selection).get(self.session_type, 'Coaching')
            date_str = ''
            if self.session_date:
                date_str = f" ({self.session_date.strftime('%Y-%m-%d')})"
            self.name = f"{type_label}: {self.employee_id.name}{date_str}"

    @api.onchange('employee_id')
    def _onchange_employee_default_strategy(self):
        """Default coaching_strategy_id to the latest strategy for the selected employee"""
        if self.employee_id:
            latest_strategy = self.env['bfsi.coaching.strategy'].search([
                ('banker_id', '=', self.employee_id.id)
            ], order='create_date desc', limit=1)
            if latest_strategy:
                self.coaching_strategy_id = latest_strategy.id
            else:
                self.coaching_strategy_id = False
        else:
            self.coaching_strategy_id = False

    @api.depends('ai_transcript')
    def _compute_ai_chat_history(self):
        """Format AI transcript into rich HTML chat history"""
        import re

        def _md_to_html(text):
            """Convert markdown-like text to HTML"""
            if not text:
                return ''
            # Escape HTML
            html = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            # Bold
            html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
            html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
            # Italic
            html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
            # Numbered items
            html = re.sub(r'^(\d+)\.\s+(.+)$', r'<div style="padding:4px 0 4px 24px;position:relative;"><span style="position:absolute;left:0;color:#4F46E5;font-weight:700;">\1.</span>\2</div>', html, flags=re.MULTILINE)
            # Bullet items
            html = re.sub(r'^[\-\*•]\s+(.+)$', r'<div style="padding:2px 0 2px 18px;position:relative;color:#6B7280;font-size:13px;"><span style="position:absolute;left:4px;top:9px;width:5px;height:5px;background:#7C3AED;border-radius:50%;display:inline-block;"></span>\1</div>', html, flags=re.MULTILINE)
            # Line breaks
            html = html.replace('\n\n', '</p><p style="margin:6px 0;">')
            html = html.replace('\n', '<br/>')
            return html

        for record in self:
            if not record.ai_transcript:
                record.ai_chat_history = '<div style="text-align:center;padding:40px 20px;color:#9CA3AF;"><i class="fa fa-comments" style="font-size:2rem;margin-bottom:8px;display:block;"></i><p>No messages yet. Start a conversation with your AI coach!</p></div>'
                continue

            try:
                # Parse JSON transcript
                transcript_data = json.loads(record.ai_transcript)
                messages = transcript_data.get('messages', [])

                if not messages:
                    record.ai_chat_history = '<div style="text-align:center;padding:40px 20px;color:#9CA3AF;"><p>No messages yet.</p></div>'
                    continue

                # Build rich HTML chat — newest messages first so latest is visible on dialog reload
                html_parts = ['<div style="display:flex;flex-direction:column;gap:16px;padding:8px 0;">']

                for msg in reversed(messages):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    timestamp = msg.get('timestamp', '')

                    time_str = ''
                    if timestamp:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = dt.strftime('%H:%M')
                        except Exception:
                            pass

                    if role == 'user':
                        html_parts.append(f'''
                        <div style="display:flex;gap:10px;align-items:flex-start;">
                            <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#4F46E5,#7C3AED);color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:13px;">
                                <i class="fa fa-user"></i>
                            </div>
                            <div style="flex:1;">
                                <div style="font-size:12px;font-weight:600;color:#4F46E5;margin-bottom:3px;"><i class="fa fa-user" style="margin-right:4px;"></i> You {f'<span style="color:#9CA3AF;font-weight:400;margin-left:6px;">{time_str}</span>' if time_str else ''}</div>
                                <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED);color:white;padding:10px 14px;border-radius:14px 14px 14px 4px;font-size:13.5px;line-height:1.5;">
                                    {content}
                                </div>
                            </div>
                        </div>''')
                    else:
                        formatted_content = _md_to_html(content)
                        html_parts.append(f'''
                        <div style="display:flex;gap:10px;align-items:flex-start;">
                            <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#312e81,#7C3AED);color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:13px;">
                                <i class="fa fa-robot"></i>
                            </div>
                            <div style="flex:1;">
                                <div style="font-size:12px;font-weight:600;color:#312e81;margin-bottom:3px;"><i class="fa fa-magic" style="margin-right:4px;color:#A78BFA;"></i> AI Coach {f'<span style="color:#9CA3AF;font-weight:400;margin-left:6px;">{time_str}</span>' if time_str else ''}</div>
                                <div style="background:linear-gradient(135deg,#ffffff,#f5f3ff);border:1px solid rgba(79,70,229,0.1);padding:12px 14px;border-radius:14px 14px 14px 4px;font-size:13.5px;line-height:1.6;color:#1e1b4b;">
                                    <p style="margin:0;">{formatted_content}</p>
                                </div>
                            </div>
                        </div>''')

                html_parts.append('</div>')
                record.ai_chat_history = ''.join(html_parts)

            except (json.JSONDecodeError, ValueError):
                # If not valid JSON, try to format plain text
                text = record.ai_transcript or ''
                formatted = _md_to_html(text)
                record.ai_chat_history = f'<div style="padding:8px;font-size:13.5px;line-height:1.6;white-space:pre-wrap;">{formatted}</div>'

    def action_start_session(self):
        """Start coaching session"""
        self.ensure_one()
        self.state = 'in_progress'

    def action_complete_session(self):
        """Complete coaching session"""
        self.ensure_one()
        self.state = 'completed'

        # Create follow-up activity if next session scheduled
        if self.next_session_date:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=self.next_session_date.date(),
                summary=f'Next coaching session: {self.name}',
                user_id=self.coach_id.user_id.id if self.coach_id else self.env.user.id
            )

    def action_cancel_session(self):
        """Cancel coaching session"""
        self.ensure_one()
        self.state = 'cancelled'

    def action_suggest_questions(self):
        """Use AI to generate real-time coaching questions based on banker's KPIs and session topic"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            topic = dict(self._fields['topic'].selection).get(self.topic, 'General')

            # Get KPI context
            kpi_context = ''
            if self.kpi_context:
                kpi_context = self.kpi_context
            elif self.employee_id:
                try:
                    context = self.employee_id.get_performance_context_for_ai()
                    kpi_context = json.dumps(context, indent=2, default=str)
                except Exception:
                    kpi_context = 'No KPI data available'

            # Get strategy context if linked
            strategy_context = ''
            if self.coaching_strategy_id:
                strategy = self.coaching_strategy_id
                strategy_context = f"""
EXISTING COACHING STRATEGY:
- Strengths: {strategy.strengths or 'Not analyzed'}
- Improvement Areas: {strategy.improvement_areas or 'Not analyzed'}
- Coaching Themes: {strategy.coaching_themes or 'Not analyzed'}
"""

            prompt = f"""You are an expert sales coaching consultant for a bank. Generate a structured set of coaching questions for a branch manager to use during a coaching session with a banker.

SESSION DETAILS:
- Banker: {self.employee_id.name}
- Topic: {topic}
- Session Type: {dict(self._fields['session_type'].selection).get(self.session_type, 'AI Coaching')}

PERFORMANCE DATA:
{kpi_context or 'No KPI data available'}
{strategy_context}

Generate questions in EXACTLY this HTML format (do NOT use markdown):

<h4>🎯 Opening Questions</h4>
<p>Use these to start the conversation and build rapport</p>
<ol>
<li><strong>Question text here</strong><br/><em>Purpose: why this question matters</em></li>
</ol>

<h4>🔍 Probing Questions</h4>
<p>Use these to explore root causes and deeper issues</p>
<ol>
<li><strong>Question text here</strong><br/><em>Purpose: why this question matters</em></li>
</ol>

<h4>💡 Action-Oriented Questions</h4>
<p>Use these to drive commitments and next steps</p>
<ol>
<li><strong>Question text here</strong><br/><em>Purpose: why this question matters</em></li>
</ol>

<h4>📋 Coaching Tips</h4>
<ul>
<li>Tip text here</li>
</ul>

Generate 3-4 questions per category. Reference the banker's actual performance numbers where possible. Keep questions open-ended and non-judgmental."""

            response_text = ai_provider.generate_text(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.7
            )

            if response_text:
                self.ai_suggested_questions = response_text
            else:
                self.ai_suggested_questions = '<p class="text-warning">Could not generate questions. Please try again.</p>'

        except ImportError:
            self.ai_suggested_questions = '<p class="text-danger">AI provider not configured. Please set up an AI provider in Configuration.</p>'
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"AI suggest questions failed: {e}")
            self.ai_suggested_questions = f'<p class="text-danger">Error generating questions: {str(e)}</p>'

    def action_ai_suggest_opening(self):
        """AI suggest for opening questions"""
        return self._get_ai_coaching_suggestion('opening')

    def action_ai_suggest_probing(self):
        """AI suggest for probing questions"""
        return self._get_ai_coaching_suggestion('probing')

    def action_ai_suggest_closing(self):
        """AI suggest for closing questions"""
        return self._get_ai_coaching_suggestion('closing')

    def action_ai_suggest_tips(self):
        """AI suggest for coaching tips"""
        return self._get_ai_coaching_suggestion('tips')

    def _get_ai_coaching_suggestion(self, category):
        """Generate AI coaching suggestions for a specific question category.

        Args:
            category: one of 'opening', 'probing', 'closing', 'tips'
        """
        self.ensure_one()

        field_map = {
            'opening': 'ai_suggestion_opening',
            'probing': 'ai_suggestion_probing',
            'closing': 'ai_suggestion_closing',
            'tips': 'ai_suggestion_tips',
        }
        target_field = field_map.get(category)
        if not target_field:
            return

        category_labels = {
            'opening': 'Opening Phase — Building Rapport',
            'probing': 'Probing Phase — Exploring Root Causes',
            'closing': 'Closing Phase — Driving Commitments',
            'tips': 'General Coaching Tips & Techniques',
        }

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get the questions for this category
            questions_field_map = {
                'opening': self.strategy_opening_questions,
                'probing': self.strategy_probing_questions,
                'closing': self.strategy_closing_questions,
                'tips': self.strategy_coaching_tips,
            }
            questions_text = questions_field_map.get(category, '') or 'No specific questions available'

            # Get KPI context
            kpi_context = ''
            if self.kpi_context:
                kpi_context = self.kpi_context
            elif self.employee_id:
                try:
                    context = self.employee_id.get_performance_context_for_ai()
                    kpi_context = json.dumps(context, indent=2, default=str)
                except Exception:
                    kpi_context = 'No KPI data available'

            # Get strategy context
            strategy_context = ''
            if self.coaching_strategy_id:
                s = self.coaching_strategy_id
                strategy_context = f"""
COACHING STRATEGY:
- Strengths: {s.strengths or 'Not analyzed'}
- Improvement Areas: {s.improvement_areas or 'Not analyzed'}
- Themes: {s.coaching_themes or 'Not analyzed'}
- AI Strategy: {s.ai_strategy or 'Not available'}
"""

            # Get discussion notes context (for live session suggestions)
            notes_context = ''
            if self.discussion_notes:
                notes_context = f"\nDISCUSSION NOTES SO FAR:\n{self.discussion_notes}\n"

            prompt = f"""You are an expert sales performance coaching consultant for a bank. A branch manager is about to conduct a coaching session with a banker and needs your help with the **{category_labels.get(category, category)}** phase.

BANKER: {self.employee_id.name}
ROLE: {self.employee_id.job_id.name if self.employee_id.job_id else 'Banker'}

PERFORMANCE DATA:
{kpi_context or 'No KPI data available'}
{strategy_context}
{notes_context}

THE QUESTIONS THE MANAGER HAS FOR THIS PHASE:
{questions_text}

Generate coaching suggestions in EXACTLY this HTML format:

<div class="ai-suggest-section">
<h5>🗣️ Talking Points</h5>
<ul>
<li><strong>Point 1:</strong> What to say, referencing specific data from the banker's performance</li>
<li><strong>Point 2:</strong> Another talking point with concrete examples</li>
<li><strong>Point 3:</strong> ...</li>
</ul>

<h5>🔢 Data to Reference</h5>
<ul>
<li><strong>Metric:</strong> Specific number and what it means</li>
<li><strong>Comparison:</strong> How it compares to team/target</li>
</ul>

<h5>⚡ Handling Pushback</h5>
<ul>
<li><strong>If they say:</strong> "<em>common pushback</em>"<br/><strong>Respond with:</strong> "suggested response with empathy and data"</li>
<li><strong>If they say:</strong> "<em>another common pushback</em>"<br/><strong>Respond with:</strong> "suggested response"</li>
</ul>

<h5>✅ Key Message to Drive Home</h5>
<p><strong>The one takeaway:</strong> A clear, motivating message the banker should remember from this part of the conversation.</p>
</div>

CRITICAL RULES:
- Use the banker's ACTUAL performance numbers in your suggestions
- Be specific and actionable, not generic
- Tone should be supportive and growth-oriented, never punitive
- Reference real metrics from their KPI data
- Keep each section concise (3-4 bullets max)
"""

            response_text = ai_provider.generate_text(
                prompt=prompt,
                max_tokens=1200,
                temperature=0.7
            )

            if response_text:
                # Strip markdown code fences that AI often wraps around HTML
                import re
                cleaned = re.sub(r'^```\w*\n?', '', response_text.strip())
                cleaned = re.sub(r'\n?```$', '', cleaned.strip())
                self.write({target_field: cleaned})
            else:
                self.write({target_field: '<p class="text-warning">Could not generate suggestions. Please try again.</p>'})

        except ImportError:
            self.write({target_field: '<p class="text-danger">AI provider not configured. Please set up an AI provider in Configuration.</p>'})
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"AI suggestion ({category}) failed: {e}")
            self.write({target_field: f'<p class="text-danger">Error: {str(e)}</p>'})

        # Return False to trigger form auto-refresh (Odoo re-reads record on False return)
        return False

    def action_send_ai_message(self, message):
        """Send message to AI coach and get response

        Args:
            message (str): Message from user

        Returns:
            dict: Response containing AI message
        """
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Build coaching prompt with context
            session_type = dict(self._fields['session_type'].selection).get(self.session_type)
            topic = dict(self._fields['topic'].selection).get(self.topic)

            prompt = f"""You are an AI coaching assistant helping with a {session_type} coaching session.
Session Topic: {topic}
Employee: {self.employee_id.name}
Coach: {self.coach_id.name if self.coach_id else 'AI Coach'}

The employee asks: {message}

Provide a supportive, professional coaching response that:
- Addresses their question or concern
- Offers constructive guidance
- Encourages growth and development
- Is specific and actionable

Response:"""

            # Get AI response using generate_text
            response_text = ai_provider.generate_text(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )

            return {
                'response': response_text if response_text else 'I apologize, I could not generate a response at this time.',
                'suggestions': []
            }

        except ImportError:
            # AI provider not available, return fallback response
            return {
                'response': 'AI coaching is not currently available. Please consult with your manager or HR for coaching support.',
                'suggestions': []
            }
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"AI message failed: {e}")

            return {
                'response': 'I apologize, I encountered an error processing your message. Please try again or contact your manager.',
                'suggestions': []
            }

    def action_generate_ai_summary(self):
        """Generate AI summary of session and identify skills discussed"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get transcript text — handle both JSON (legacy) and formatted text
            transcript_text = ''
            if self.ai_transcript:
                try:
                    import json
                    transcript_data = json.loads(self.ai_transcript)
                    messages = transcript_data.get('messages', [])
                    transcript_text = '\n'.join([
                        f"{msg['role'].upper()}: {msg['content']}"
                        for msg in messages
                    ])
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Already formatted text — use directly
                    transcript_text = self.ai_transcript

            if not transcript_text:
                transcript_text = self.discussion_notes or ''

            if transcript_text:
                summary = ai_provider.summarize_meeting(transcript_text)

                summary_html = f"""
                <h4>AI-Generated Summary</h4>
                <p><strong>Summary:</strong> {summary.get('summary', '')}</p>

                <p><strong>Key Points:</strong></p>
                <ul>
                    {''.join(f'<li>{point}</li>' for point in summary.get('key_points', []))}
                </ul>

                <p><strong>Recommended Next Steps:</strong></p>
                <ul>
                    {''.join(f'<li>{action}</li>' for action in summary.get('action_items', []))}
                </ul>
                """

                self.action_items = summary_html

                # --- Also identify skills discussed ---
                self._identify_skills_from_transcript(ai_provider, transcript_text)

                return {
                    'message': 'Summary and skills generated successfully',
                    'success': True
                }
            else:
                return {
                    'message': 'No transcript available to summarize',
                    'success': False
                }

        except ImportError:
            return {
                'message': 'AI provider not available',
                'success': False
            }
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"AI summary generation failed: {e}")

            return {
                'message': f'Failed to generate summary: {str(e)}',
                'success': False
            }

    def _identify_skills_from_transcript(self, ai_provider, transcript_text):
        """Use AI to identify skills discussed and populate skill_ids.

        Only matches skills from 'Soft Skills' and 'Marketing' categories.
        """
        try:
            # Get available skills from Soft Skills and Marketing skill types
            allowed_types = self.env['hr.skill.type'].search([
                ('name', 'in', ['Soft Skills', 'Marketing'])
            ])
            if not allowed_types:
                return

            available_skills = self.env['hr.skill'].search([
                ('skill_type_id', 'in', allowed_types.ids)
            ])
            if not available_skills:
                return

            skill_list = ', '.join(available_skills.mapped('name'))

            prompt = f"""Analyze this coaching conversation and identify which skills from the list below were discussed, practiced, or are relevant.

COACHING CONVERSATION:
{transcript_text[:3000]}

AVAILABLE SKILLS (only pick from this list):
{skill_list}

Return ONLY a JSON array of skill names that were discussed. Example:
["Communication", "Leadership", "Time Management"]

If no skills match, return an empty array: []
Return ONLY the JSON array, nothing else."""

            response = ai_provider.generate_text(prompt, max_tokens=300, temperature=0.3)

            if response:
                import re
                # Extract JSON array from response
                cleaned = response.strip()
                # Remove markdown code fences if present
                cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                cleaned = re.sub(r'\n?```$', '', cleaned)
                cleaned = cleaned.strip()

                matched_names = json.loads(cleaned)
                if isinstance(matched_names, list) and matched_names:
                    # Find matching skill records (case-insensitive)
                    matched_skills = self.env['hr.skill']
                    for skill_name in matched_names:
                        skill = available_skills.filtered(
                            lambda s: s.name.lower().strip() == str(skill_name).lower().strip()
                        )
                        if skill:
                            matched_skills |= skill[:1]

                    if matched_skills:
                        self.skill_ids = [(6, 0, matched_skills.ids)]

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Skills identification failed for session {self.id}: {e}"
            )

    def action_open_ai_chat(self):
        """Open AI Chat dialog"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Coaching Chat',
            'res_model': 'hr.coaching.session',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('hr_development_ai.view_coaching_session_ai_chat_dialog').id,
            'target': 'new',
            'context': {'dialog_size': 'large'}
        }

    def action_send_quick_question(self):
        """Send a pre-built quick question to AI coach.

        Reads the question from context['quick_question'].
        Called from quick question buttons in the AI Chat dialog.

        Returns:
            dict: Action to reload dialog
        """
        self.ensure_one()
        question = self.env.context.get('quick_question', '')
        if not question:
            raise UserError(_('No question provided.'))
        self.ai_chat_input = question
        return self.action_send_ai_message_from_dialog()

    def get_quick_questions(self):
        """Get categorized quick questions for AI coaching chat

        Returns questions based on session context, linked strategy, and KPI data.

        Returns:
            list: Categories of questions, each with title, icon, and questions
        """
        self.ensure_one()

        categories = []

        # 1. Performance Review questions
        perf_questions = [
            "What are my key strengths based on current KPIs?",
            "Which KPI areas need the most improvement?",
            "How does my performance compare to team averages?",
            "What specific actions can improve my conversion rate?",
        ]
        categories.append({
            'title': '📊 Performance Review',
            'icon': 'fa-line-chart',
            'questions': perf_questions
        })

        # 2. Sales & Client Engagement
        sales_questions = [
            "How can I improve my meeting-to-conversion ratio?",
            "What techniques help in handling client objections?",
            "How do I increase my connect rate on calls?",
            "Give me tips for better client follow-up strategies.",
        ]
        categories.append({
            'title': '🎯 Sales & Client Engagement',
            'icon': 'fa-bullseye',
            'questions': sales_questions
        })

        # 3. Strategy questions from linked strategy (if available)
        if self.coaching_strategy_id:
            strategy = self.coaching_strategy_id
            strategy_questions = []
            if strategy.opening_questions:
                # Extract first question from each category
                for line in str(strategy.opening_questions).split('\n'):
                    clean = line.strip().lstrip('0123456789. ')
                    if clean and len(clean) > 10:
                        strategy_questions.append(clean)
                        break
            if strategy.probing_questions:
                for line in str(strategy.probing_questions).split('\n'):
                    clean = line.strip().lstrip('0123456789. ')
                    if clean and len(clean) > 10:
                        strategy_questions.append(clean)
                        break
            if strategy.closing_questions:
                for line in str(strategy.closing_questions).split('\n'):
                    clean = line.strip().lstrip('0123456789. ')
                    if clean and len(clean) > 10:
                        strategy_questions.append(clean)
                        break
            if strategy_questions:
                categories.append({
                    'title': '🧠 From Your Strategy',
                    'icon': 'fa-magic',
                    'questions': strategy_questions
                })

        # 4. Goal Setting & Action Planning
        goal_questions = [
            "Help me create a SMART goal for this month.",
            "What should be my top 3 priorities this week?",
            "How do I track progress on my action items?",
            "What daily habits will improve my performance?",
        ]
        categories.append({
            'title': '📋 Goals & Action Planning',
            'icon': 'fa-tasks',
            'questions': goal_questions
        })

        # 5. Skill Development
        skill_questions = [
            "What skills should I focus on developing?",
            "How can I improve my leadership abilities?",
            "Recommend training for better client management.",
            "How do I develop better time management skills?",
        ]
        categories.append({
            'title': '💡 Skill Development',
            'icon': 'fa-graduation-cap',
            'questions': skill_questions
        })

        return categories

    def action_send_ai_message_from_dialog(self):
        """Send message to AI from dialog and append response to transcript

        This method is called from the dialog's "Send to AI" button.
        It reads from ai_chat_input, sends to AI, and appends both messages to transcript.
        """
        self.ensure_one()

        # Check if user has typed a message
        if not self.ai_chat_input or not self.ai_chat_input.strip():
            raise UserError(_('Please type a message in the input field before sending to AI.'))

        user_message = self.ai_chat_input.strip()

        try:
            # Parse existing transcript - handle both JSON and formatted text
            messages = []
            if self.ai_transcript:
                try:
                    transcript_data = json.loads(self.ai_transcript)
                    messages = transcript_data.get('messages', [])
                except (json.JSONDecodeError, ValueError):
                    # Parse formatted text back into messages
                    messages = self._parse_formatted_transcript(self.ai_transcript)

            # Add user's message
            messages.append({
                'role': 'user',
                'content': user_message,
                'timestamp': fields.Datetime.now().isoformat()
            })

            # Send to AI
            result = self.action_send_ai_message(user_message)

            # Add AI response
            messages.append({
                'role': 'assistant',
                'content': result.get('response', 'No response received'),
                'timestamp': fields.Datetime.now().isoformat()
            })

            # Save as formatted readable text
            self.ai_transcript = self._format_chat_transcript(messages)

            # Clear the input field
            self.ai_chat_input = ''

            # Return action to reload the dialog form
            return {
                'type': 'ir.actions.act_window',
                'name': _('AI Coaching Chat'),
                'res_model': 'hr.coaching.session',
                'res_id': self.id,
                'view_mode': 'form',
                'views': [[self.env.ref('hr_development_ai.view_coaching_session_ai_chat_dialog').id, 'form']],
                'target': 'new',
                'context': {'dialog_size': 'large'}
            }

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"AI message from dialog failed: {e}")

            raise UserError(_(
                'Failed to send message to AI coach. Please try again.\n\n'
                'Error: %s'
            ) % str(e))

    def _format_chat_transcript(self, messages):
        """Format chat messages list into readable text"""
        if not messages:
            return ''
        lines = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                lines.append(f"👤 You:\n{content}")
            elif role == 'assistant':
                lines.append(f"🤖 AI Coach:\n{content}")
            else:
                lines.append(f"{role}:\n{content}")
        return '\n\n─────────────────────\n\n'.join(lines)

    def _parse_formatted_transcript(self, text):
        """Parse formatted chat transcript text back into messages list"""
        if not text:
            return []
        separator = '─────────────────────'
        blocks = [b.strip() for b in text.split(separator) if b.strip()]
        messages = []
        for block in blocks:
            if block.startswith('👤 You:'):
                content = block[len('👤 You:'):].strip()
                messages.append({'role': 'user', 'content': content})
            elif block.startswith('🤖 AI Coach:'):
                content = block[len('🤖 AI Coach:'):].strip()
                messages.append({'role': 'assistant', 'content': content})
            else:
                # Fallback
                messages.append({'role': 'assistant', 'content': block})
        return messages

    # ===================
    # BFSI Methods
    # ===================
    def action_capture_kpi_context(self):
        """Capture current KPI context for the session"""
        self.ensure_one()

        context = self.employee_id.get_performance_context_for_ai()
        self.kpi_context = json.dumps(context, indent=2, default=str)
        self.is_bfsi_session = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('KPI Context Captured'),
                'message': _('Performance context has been captured for this session.'),
                'type': 'success',
            }
        }

    def action_create_action_plan(self):
        """Create an action plan from this coaching session"""
        self.ensure_one()

        if self.action_plan_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Action Plan'),
                'res_model': 'bfsi.action.plan',
                'res_id': self.action_plan_id.id,
                'view_mode': 'form',
                'views': [[False, 'form']],
            }

        # Create new action plan
        plan = self.env['bfsi.action.plan'].create({
            'coaching_session_id': self.id,
            'employee_id': self.employee_id.id,
            'manager_id': self.coach_id.id if self.coach_id else False,
            'target_date': fields.Date.today() + timedelta(days=14),  # 2 weeks default
        })

        self.action_plan_id = plan.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Action Plan'),
            'res_model': 'bfsi.action.plan',
            'res_id': plan.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    def action_generate_action_items_ai(self):
        """Use AI to generate action items from the coaching conversation"""
        self.ensure_one()

        if not self.action_plan_id:
            self.action_create_action_plan()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get conversation transcript
            transcript = ''
            if self.ai_transcript:
                try:
                    transcript_data = json.loads(self.ai_transcript)
                    messages = transcript_data.get('messages', [])
                    transcript = '\n'.join([
                        f"{msg['role'].upper()}: {msg['content']}"
                        for msg in messages
                    ])
                except (json.JSONDecodeError, ValueError):
                    # Already formatted text — use directly
                    transcript = self.ai_transcript

            if not transcript:
                raise UserError(_('No coaching conversation found. Please have a conversation first.'))

            # Get KPI context
            kpi_context = self.kpi_context or '{}'

            prompt = f"""Based on the following coaching conversation and performance context, generate specific action items.

COACHING CONVERSATION:
{transcript}

PERFORMANCE CONTEXT:
{kpi_context}

Generate 3-5 specific, measurable action items in JSON format:
{{
    "action_items": [
        {{
            "name": "Action item title",
            "description": "Detailed description",
            "kpi_category": "input|behavior|output|outcome",
            "specific_kpi": "dials|connects|script_adherence|etc",
            "success_criteria": "How to measure success",
            "priority": "high|medium|low"
        }}
    ]
}}

Focus on:
1. SPECIFIC behaviors the banker can control
2. Measurable outcomes within 2 weeks
3. Addressing the root causes of performance gaps
"""

            response = ai_provider.generate_text(prompt, max_tokens=800, temperature=0.5)

            # Parse response
            try:
                data = json.loads(response)
            except:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise UserError(_('Could not parse AI response.'))

            # Valid selection values for bfsi.action.plan.item
            valid_kpi_categories = {'input', 'behavior', 'output', 'outcome'}
            valid_specific_kpis = {
                'dials', 'connects', 'meetings', 'script_adherence',
                'objection_handling', 'need_analysis', 'product_knowledge',
                'conversion', 'revenue', 'customer_satisfaction', 'other'
            }
            valid_priorities = {'high', 'medium', 'low'}

            # Create action items
            items_created = 0
            for idx, item in enumerate(data.get('action_items', []), 1):
                kpi_cat = item.get('kpi_category', '')
                spec_kpi = item.get('specific_kpi', '')
                priority = item.get('priority', 'medium')

                self.env['bfsi.action.plan.item'].create({
                    'action_plan_id': self.action_plan_id.id,
                    'sequence': idx * 10,
                    'name': item.get('name', 'Action Item'),
                    'description': item.get('description', ''),
                    'kpi_category': kpi_cat if kpi_cat in valid_kpi_categories else False,
                    'specific_kpi': spec_kpi if spec_kpi in valid_specific_kpis else 'other',
                    'success_criteria': item.get('success_criteria', ''),
                    'priority': priority if priority in valid_priorities else 'medium',
                })
                items_created += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action Items Generated'),
                    'message': _('%d action items have been created.') % items_created,
                    'type': 'success',
                }
            }

        except Exception as e:
            raise UserError(_('Failed to generate action items: %s') % str(e))

    def _get_bfsi_coaching_prompt(self, message):
        """Build enhanced coaching prompt with BFSI context"""
        self.ensure_one()

        session_type = dict(self._fields['session_type'].selection).get(self.session_type)
        topic = dict(self._fields['topic'].selection).get(self.topic)

        # Get performance context
        kpi_context = ''
        if self.kpi_context:
            kpi_context = f"\nPERFORMANCE CONTEXT:\n{self.kpi_context}"
        elif self.is_bfsi_session:
            context = self.employee_id.get_performance_context_for_ai()
            kpi_context = f"\nPERFORMANCE CONTEXT:\n{json.dumps(context, indent=2, default=str)}"

        # Get strategy if available
        strategy_context = ''
        if self.coaching_strategy_id:
            strategy_context = f"""
COACHING STRATEGY:
{self.coaching_strategy_id.ai_strategy or ''}

COACHING THEMES:
{self.coaching_strategy_id.coaching_themes or '[]'}
"""

        prompt = f"""You are an expert AI sales performance coach for a bank.

SESSION DETAILS:
- Type: {session_type}
- Topic: {topic}
- Banker: {self.employee_id.name}
- Coach: {self.coach_id.name if self.coach_id else 'AI Coach'}
{kpi_context}
{strategy_context}

The banker asks: {message}

Provide a supportive, professional coaching response that:
1. References their actual performance numbers when relevant
2. Focuses on specific behaviors they can improve
3. Offers 1-2 actionable next steps
4. Is encouraging but honest about areas for improvement
5. Asks a follow-up question to deepen the coaching conversation

Keep response under 200 words unless they ask for detailed guidance.

Response:"""

        return prompt
