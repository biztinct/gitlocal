# -*- coding: utf-8 -*-
"""`pb.hiring.stage.log` — every time a candidate moved, and when.

WHY THIS EXISTS AT ALL. The standard applicant carries which stage it is on
and, once somebody is hired, the date that happened. It does not carry how
long anybody spent in Qualification, because a stored current value can never
answer a question about the past. "Time to fill" and "where candidates get
stuck" are the two numbers a hiring process is actually judged on, and neither
can be reconstructed afterwards from a column that only remembers today.

So the row is written at the moment of the move, by everything that moves
anybody — this module's screening, this module's interview scheduling, the
standard kanban a recruiter drags a card across, and a mass edit. That is why
it hangs off `write` rather than off any one of our own buttons.

IT IS A LEDGER AND NOTHING ELSE. Nothing reads it to make a decision; A3's
analytics read it to report. A row that is missing costs a number; a row that
raises costs somebody their afternoon, which is why the writing is a savepoint
leg that can only ever fail quietly (R131).
"""

from odoo import _, api, fields, models


class PbHiringStageLog(models.Model):
    _name = 'pb.hiring.stage.log'
    _description = 'Candidate stage move'
    _order = 'at desc, id desc'

    applicant_id = fields.Many2one(
        'hr.applicant', string='Candidate', required=True, index=True,
        ondelete='cascade')
    job_id = fields.Many2one('hr.job', string='The job', index=True,
                             ondelete='set null')
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', index=True,
        ondelete='set null')
    from_stage_id = fields.Many2one('hr.recruitment.stage', string='From',
                                    ondelete='set null')
    to_stage_id = fields.Many2one('hr.recruitment.stage', string='To',
                                  index=True, ondelete='set null')
    at = fields.Datetime(string='When', required=True, index=True,
                         default=fields.Datetime.now)
    by_user_id = fields.Many2one('res.users', string='Moved by',
                                 default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                '%(who)s → %(stage)s',
                who=rec.applicant_id.sudo().partner_name or _('a candidate'),
                stage=rec.to_stage_id.name or '')

    @api.model
    def note_move(self, applicant, from_stage_id, to_stage_id):
        """Write one row. Called from the `hr.applicant` write override
        inside a savepoint, so it is allowed to be strict about its own
        arguments."""
        if not applicant or from_stage_id == to_stage_id:
            return self.browse()
        app = applicant.sudo()
        return self.sudo().create({
            'applicant_id': app.id,
            'job_id': app.job_id.id or False,
            'requisition_id': app.pb_requisition_id.id or False,
            'from_stage_id': from_stage_id or False,
            'to_stage_id': to_stage_id or False,
            'at': fields.Datetime.now(),
            'by_user_id': self.env.uid,
            'company_id': app.company_id.id or self.env.company.id,
        })
