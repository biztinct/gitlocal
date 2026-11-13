# -*- coding: utf-8 -*-
"""The course somebody has to finish before their trial period can be passed.

THE REAL CASE THIS EXISTS FOR is an agronomist who may not sign off a field
report until they have done the company's own soil course. Nobody wants that
written into code, so it is three small tables instead:

    pb.training.track    a course, bound to the jobs that need it
    pb.training.item     one thing inside it, required or not
    pb.training.status   whether one person has done one item

and the gate is a single question asked at the verdict: is anything REQUIRED
still outstanding for this person? If it is, the pass is refused in plain
English naming the item, rather than confirming somebody who has not done it.

A GATE THAT HAS NOTHING TO CHECK PASSES, and that is correct here (R44 is
about the other case — a gate whose rows were never created). A person whose
job is bound to no track has no course to do, so "nothing outstanding" is the
true answer rather than an accident. The rows for a person whose job IS bound
are created idempotently in two places — when their joining checklist opens and
again when their review is created — so a track added after somebody joined
still reaches them.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

TRAINING_STATES = [
    ('todo', 'Not done yet'),
    ('done', 'Done'),
]
TRAINING_STATE_LABEL = dict(TRAINING_STATES)


class PbTrainingTrack(models.Model):
    _name = 'pb.training.track'
    _description = 'Training Track'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True, string='Course')
    sequence = fields.Integer(default=10)
    description = fields.Text(
        string='What it is for',
        help='One or two sentences a new joiner would understand.')
    job_ids = fields.Many2many(
        'hr.job', 'pb_training_track_job_rel', 'track_id', 'job_id',
        string='Jobs that need it',
        help='Leave empty and nobody is asked to do this automatically — it '
             'is then an example rather than a requirement.')
    item_ids = fields.One2many(
        'pb.training.item', 'track_id', string='What is in it')
    item_count = fields.Integer(compute='_compute_item_count', string='Items')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('item_ids')
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Course')

    # ------------------------------------------------------------- the rows
    @api.model
    def _as_employee(self, employee):
        """Accept a record OR an id.

        Both public methods below are reachable over JSON-RPC, where a
        recordset argument arrives as a plain integer (R43) — and an integer
        does not have a `job_id`, so the call raises rather than quietly
        answering the fallback. Coerce once, at the door.
        """
        if isinstance(employee, int):
            return self.env['hr.employee'].sudo().browse(employee).exists()
        if isinstance(employee, (list, tuple)) and employee:
            return self.env['hr.employee'].sudo().browse(
                int(employee[0])).exists()
        return employee

    @api.model
    def tracks_for(self, employee):
        """The courses this person's job requires.

        A track with NO jobs on it is deliberately not returned: it is an
        example somebody can copy, not a requirement everybody inherits.
        """
        employee = self._as_employee(employee)
        if not employee or not employee.job_id:
            return self.browse()
        company_id = (employee.company_id or self.env.company).id
        return self.sudo().search([
            ('active', '=', True),
            ('company_id', 'in', [False, company_id]),
            ('job_ids', 'in', employee.job_id.id),
        ])

    @api.model
    def ensure_for_employee(self, employee):
        """Make sure this person has a row for every item their job needs.

        Idempotent on (employee, item): a second call finds the rows already
        there and adds nothing, so it is safe from the joining hook, from the
        review's own create and from the daily job all at once (R30).
        """
        employee = self._as_employee(employee)
        if not employee:
            return 0
        Status = self.env['pb.training.status'].sudo()
        made = 0
        for track in self.tracks_for(employee):
            for item in track.item_ids:
                try:
                    if Status.search_count([('employee_id', '=', employee.id),
                                            ('item_id', '=', item.id)]):
                        continue
                    Status.create({
                        'employee_id': employee.id,
                        'item_id': item.id,
                        'state': 'todo',
                        'company_id': (employee.company_id
                                       or self.env.company).id,
                    })
                    made += 1
                except Exception:       # noqa: BLE001 — one item, one grave
                    _logger.exception(
                        'pb_probation: could not plan training item %s for '
                        'employee %s', item.id, employee.id)
        return made


class PbTrainingItem(models.Model):
    _name = 'pb.training.item'
    _description = 'Training Item'
    _order = 'sequence, id'

    track_id = fields.Many2one(
        'pb.training.track', string='Course', required=True, index=True,
        ondelete='cascade')
    name = fields.Char(required=True, translate=True, string='Item')
    sequence = fields.Integer(default=10)
    description = fields.Text(string='What it covers')
    required = fields.Boolean(
        string='Must be done before confirming', default=True,
        help='A required item stops the trial period being passed until it is '
             'ticked. Leave it off for something worth doing but not worth '
             'blocking somebody over.')
    company_id = fields.Many2one(
        related='track_id.company_id', store=True, string='Company')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.track_id.name or _('Course'), rec.name or '')


class PbTrainingStatus(models.Model):
    _name = 'pb.training.status'
    _description = 'Training Status'
    _order = 'employee_id, id'

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    item_id = fields.Many2one(
        'pb.training.item', string='Item', required=True, index=True,
        ondelete='cascade')
    track_id = fields.Many2one(
        related='item_id.track_id', store=True, string='Course', index=True)
    required = fields.Boolean(related='item_id.required', store=True,
                              string='Required')
    state = fields.Selection(
        TRAINING_STATES, string='Status', default='todo', required=True,
        index=True)
    score = fields.Float(string='Score', digits=(5, 1))
    done_at = fields.Date(string='Done on')
    note = fields.Char(string='Note')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    _employee_item_uniq = models.Constraint(
        'unique(employee_id, item_id)',
        'A person can only have one row per training item.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.employee_id.name or _('Employee'),
                rec.item_id.name or _('Item'))

    def action_done(self, score=None):
        for rec in self:
            vals = {'state': 'done', 'done_at': fields.Date.context_today(rec)}
            if score is not None:
                try:
                    vals['score'] = float(score)
                except (TypeError, ValueError):
                    pass
            rec.write(vals)
        return True

    def action_reopen(self):
        self.write({'state': 'todo', 'done_at': False})
        return True

    # ------------------------------------------------------------- the gate
    @api.model
    def pending_required_for(self, employee):
        """What is still outstanding, as NAMES a person can act on.

        A list of strings and never a boolean: "the pass was blocked" is not
        something anybody can do anything about, and "Soil sampling — module 2
        is still outstanding" is.
        """
        if isinstance(employee, int):
            employee = self.env['hr.employee'].sudo().browse(employee).exists()
        if not employee:
            return []
        try:
            rows = self.sudo().search([
                ('employee_id', '=', employee.id),
                ('required', '=', True),
                ('state', '!=', 'done'),
            ])
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: training gate for employee %s',
                              employee.id)
            return []
        return [r.item_id.name or '' for r in rows if r.item_id]

    @api.model
    def summary_for(self, employee):
        """The gate as the lens shows it: done, total, and what is left."""
        if isinstance(employee, int):
            employee = self.env['hr.employee'].sudo().browse(employee).exists()
        blank = {'total': 0, 'done': 0, 'pending': [], 'ok': True,
                 'has_track': False}
        if not employee:
            return blank
        try:
            rows = self.sudo().search([('employee_id', '=', employee.id)])
        except Exception:               # noqa: BLE001
            _logger.exception('pb_probation: training summary for %s',
                              employee.id)
            return blank
        pending = [r.item_id.name or '' for r in rows
                   if r.required and r.state != 'done']
        return {
            'total': len(rows),
            'done': len([r for r in rows if r.state == 'done']),
            'pending': pending,
            'ok': not pending,
            'has_track': bool(rows),
        }
