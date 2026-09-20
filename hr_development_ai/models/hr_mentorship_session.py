# -*- coding: utf-8 -*-

from odoo import models, fields


class HRMentorshipSession(models.Model):
    _name = 'hr.mentorship.session'
    _description = 'Mentorship Session'
    _inherit = ['mail.thread']
    _order = 'session_date desc'

    mentorship_id = fields.Many2one(
        'hr.mentorship',
        string='Mentorship',
        required=True,
        ondelete='cascade',
        index=True
    )

    mentor_id = fields.Many2one(
        related='mentorship_id.mentor_id',
        string='Mentor',
        store=True,
        readonly=True
    )

    mentee_id = fields.Many2one(
        related='mentorship_id.mentee_id',
        string='Mentee',
        store=True,
        readonly=True
    )

    session_date = fields.Datetime(
        string='Session Date',
        required=True,
        default=fields.Datetime.now
    )

    duration = fields.Integer(
        string='Duration (minutes)',
        default=60
    )

    topic = fields.Char(string='Topic', required=True)

    discussion_notes = fields.Html(string='Discussion Notes')

    skills_practiced = fields.Many2many(
        'hr.skill',
        string='Skills Practiced',
        help='Skills discussed or practiced in this session'
    )

    action_items_mentor = fields.Html(string='Mentor Action Items')
    action_items_mentee = fields.Html(string='Mentee Action Items')

    next_session_date = fields.Datetime(string='Next Session Date')

    mentee_feedback = fields.Text(string='Mentee Feedback')
    mentor_feedback = fields.Text(string='Mentor Feedback')

    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='scheduled', required=True, tracking=True)

    def action_complete(self):
        """Mark session as completed"""
        self.ensure_one()
        self.state = 'completed'

    def action_cancel(self):
        """Cancel session"""
        self.ensure_one()
        self.state = 'cancelled'
