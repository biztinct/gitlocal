# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class HRCoachingNudge(models.Model):
    _name = 'hr.coaching.nudge'
    _description = 'AI Coaching Nudge'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'title'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True
    )

    title = fields.Char(string='Title', required=True)

    message = fields.Html(
        string='Coaching Message',
        required=True,
        help='AI-generated coaching suggestion'
    )

    situation = fields.Selection([
        ('missed_deadline', 'Missed Deadline'),
        ('upcoming_meeting', 'Upcoming Meeting'),
        ('skill_gap_detected', 'Skill Gap Detected'),
        ('low_performance', 'Low Performance'),
        ('goal_progress', 'Goal Progress'),
        ('learning_opportunity', 'Learning Opportunity'),
        ('recognition', 'Recognition'),
        ('general', 'General Advice')
    ], string='Situation', required=True, default='general')

    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Priority', required=True, default='medium', tracking=True)

    action_items = fields.Html(string='Suggested Actions')

    # Context data
    context_data = fields.Text(
        string='Context Data (JSON)',
        help='Contextual data used to generate nudge'
    )

    # Related records
    task_id = fields.Many2one('project.task', string='Related Task', ondelete='set null')
    goal_id = fields.Many2one('gamification.goal', string='Related Goal', ondelete='set null')
    skill_gap_id = fields.Many2one('hr.skill.gap', string='Related Skill Gap', ondelete='set null')

    # Response tracking
    state = fields.Selection([
        ('sent', 'Sent'),
        ('read', 'Read'),
        ('acted', 'Acted Upon'),
        ('dismissed', 'Dismissed')
    ], string='Status', default='sent', required=True, tracking=True)

    employee_feedback = fields.Text(string='Employee Feedback')

    read_date = fields.Datetime(string='Read Date', readonly=True)
    acted_date = fields.Datetime(string='Acted Date', readonly=True)

    # AI metadata
    ai_provider = fields.Char(string='AI Provider Used')
    ai_confidence = fields.Float(string='AI Confidence', help='AI confidence in suggestion (0-1)')

    @api.model
    def generate_nudge_for_employee(self, employee_id, situation, context_data=None):
        """
        Generate AI coaching nudge for employee

        Args:
            employee_id: Employee record ID
            situation: Situation type (missed_deadline, skill_gap_detected, etc.)
            context_data: Dictionary with contextual information

        Returns:
            hr.coaching.nudge: Created nudge record
        """
        employee = self.env['hr.employee'].browse(employee_id)

        if not context_data:
            context_data = {}

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Prepare context for AI
            ai_context = {
                'employee_name': employee.name,
                'situation': situation,
                'relevant_data': context_data,
                'tone': 'supportive'
            }

            # Generate coaching nudge
            result = ai_provider.generate_coaching_nudge(ai_context)

            # Format action items as HTML
            action_items_html = '<ul>'
            for action in result.get('action_items', []):
                action_items_html += f'<li>{action}</li>'
            action_items_html += '</ul>'

            # Create nudge record
            nudge = self.create({
                'employee_id': employee_id,
                'title': self._get_situation_title(situation),
                'message': f"<p>{result.get('message', '')}</p>",
                'situation': situation,
                'priority': result.get('priority', 'medium'),
                'action_items': action_items_html,
                'context_data': str(context_data),
                'ai_provider': ai_provider.__class__.__name__,
                'ai_confidence': result.get('confidence', 0.8)
            })

            # Send notification to employee
            nudge._send_notification()

            return nudge

        except Exception as e:
            _logger.error(f"Failed to generate coaching nudge: {e}")

            # Fallback: Create generic nudge
            return self.create({
                'employee_id': employee_id,
                'title': self._get_situation_title(situation),
                'message': f"<p>You have a {situation.replace('_', ' ')} situation. Please review and take appropriate action.</p>",
                'situation': situation,
                'priority': 'medium',
                'ai_provider': 'Fallback'
            })

    def _get_situation_title(self, situation):
        """Get human-readable title for situation"""
        titles = {
            'missed_deadline': 'Missed Deadline - Action Required',
            'upcoming_meeting': 'Prepare for Upcoming Meeting',
            'skill_gap_detected': 'New Learning Opportunity',
            'low_performance': 'Performance Coaching',
            'goal_progress': 'Goal Progress Update',
            'learning_opportunity': 'Recommended Learning Path',
            'recognition': 'Great Work!',
            'general': 'Coaching Suggestion'
        }
        return titles.get(situation, 'Coaching Nudge')

    def _send_notification(self):
        """Send notification to employee"""
        self.ensure_one()

        if self.employee_id.user_id:
            self.message_post(
                body=self.message,
                subject=self.title,
                partner_ids=[self.employee_id.user_id.partner_id.id],
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_mark_read(self):
        """Mark nudge as read"""
        self.ensure_one()
        self.write({
            'state': 'read',
            'read_date': fields.Datetime.now()
        })

    def action_mark_acted(self):
        """Mark nudge as acted upon"""
        self.ensure_one()
        self.write({
            'state': 'acted',
            'acted_date': fields.Datetime.now()
        })

    def action_dismiss(self):
        """Dismiss nudge"""
        self.ensure_one()
        self.state = 'dismissed'

    @api.model
    def generate_nudges_from_kpis(self):
        """
        Cron job: Generate coaching nudges based on KPI performance
        """
        # Get all employees with active goals
        goals = self.env['gamification.goal'].search([
            ('state', '=', 'inprogress'),
            ('current', '<', 'target_goal')  # Behind target
        ])

        for goal in goals:
            if goal.user_id and goal.user_id.employee_id:
                # Check if nudge already sent recently
                recent_nudge = self.search([
                    ('employee_id', '=', goal.user_id.employee_id.id),
                    ('goal_id', '=', goal.id),
                    ('create_date', '>=', fields.Datetime.now().replace(hour=0, minute=0, second=0))
                ], limit=1)

                if not recent_nudge:
                    self.generate_nudge_for_employee(
                        employee_id=goal.user_id.employee_id.id,
                        situation='goal_progress',
                        context_data={
                            'goal_name': goal.definition_id.name,
                            'current': goal.current,
                            'target': goal.target_goal,
                            'completeness': goal.completeness
                        }
                    )

        return True
