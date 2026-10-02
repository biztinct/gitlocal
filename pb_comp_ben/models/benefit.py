# -*- coding: utf-8 -*-
"""Benefit plans, and who is on them.

A plan is a thing the company buys; an enrollment is one person's place on it,
with the number the provider knows them by. The employee's own page shows the
plan card and a button through to the provider's site — a real link, opened in a
new tab, and NOT a single-sign-on hop, because pretending to sign somebody in
and landing them on a login screen is worse than saying "open the provider site".

Dependants are kept as a small JSON list rather than a fourth table. They are
read on one page, written on one form, never searched and never reported on;
a table would be three files of machinery for a list of names.
"""

import json
import logging

from odoo import _, api, fields, models

from .comp_common import BENEFIT_KINDS

_logger = logging.getLogger(__name__)


class PbBenefitPlan(models.Model):
    _name = 'pb.benefit.plan'
    _description = 'Benefit plan'
    _order = 'sequence, name, id'

    name = fields.Char(string='Plan', required=True, translate=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(BENEFIT_KINDS, string='Kind', default='health',
                            required=True)
    provider_name = fields.Char(string='Provided by')
    provider_url = fields.Char(
        string='Provider website',
        help='Where the person goes to make a claim or read their cover. Shown '
             'on their own page as a button.')
    country_id = fields.Many2one('res.country', string='Country')
    coverage_html = fields.Html(
        string='What it covers', sanitize=True, translate=True,
        help='Written for the person on the plan, not for the broker.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    enrollment_ids = fields.One2many('pb.benefit.enrollment', 'plan_id',
                                     string='People on it')
    enrolled_count = fields.Integer(compute='_compute_enrolled',
                                    string='On this plan')

    def _compute_enrolled(self):
        for plan in self:
            plan.enrolled_count = len(plan.enrollment_ids.filtered(
                lambda e: e.state == 'active'))


class PbBenefitEnrollment(models.Model):
    _name = 'pb.benefit.enrollment'
    _description = 'Benefit enrollment'
    _order = 'start_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Reference')
    plan_id = fields.Many2one('pb.benefit.plan', string='Plan', required=True,
                              index=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Person', required=True,
                                  index=True, ondelete='cascade')
    member_ref = fields.Char(string='Membership number')
    start_date = fields.Date(string='Covered from',
                             default=fields.Date.context_today)
    end_date = fields.Date(string='Covered until')
    dependants_json = fields.Text(
        string='Family covered',
        help='Who else is covered, as a list of name and relationship.')
    state = fields.Selection(
        [('active', 'Covered'), ('ended', 'Ended')],
        default='active', required=True, string='Status')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('plan_id', 'employee_id')
    def _compute_name(self):
        for rec in self:
            # R56 — one field of an hr.employee prefetches forty, and forty of
            # those sit behind payroll groups.
            who = rec.employee_id.sudo().name or ''
            rec.name = ('%s — %s' % (rec.plan_id.name or '', who)).strip(' —')

    def dependants(self):
        """The family list, as rows a page can print. Never raises."""
        self.ensure_one()
        # The FIELD READ is outside the try on purpose. Inside it, an
        # AccessError from a missing record rule was swallowed and logged as
        # "unreadable family list" — a masked permission problem reported as a
        # data problem, which is how an afternoon gets spent on the wrong file.
        # The try covers the parse, which is the only thing that can be bad data.
        raw = self.dependants_json or '[]'
        try:
            rows = json.loads(raw)
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_comp_ben: enrollment %s has an unreadable '
                            'family list', self.id)
            return []
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if isinstance(row, dict) and (row.get('name') or '').strip():
                out.append({'name': str(row.get('name') or '').strip(),
                            'relation': str(row.get('relation') or '').strip()})
        return out

    def action_end(self):
        for rec in self:
            rec.write({'state': 'ended',
                       'end_date': rec.end_date or fields.Date.context_today(rec)})
        return True

    @api.model
    def active_for_employee(self, employee_id):
        """R43 — an integer over the wire is what this actually receives."""
        emp_id = employee_id.id if hasattr(employee_id, 'id') else int(
            employee_id or 0)
        if not emp_id:
            return self.browse()
        return self.search([('employee_id', '=', emp_id),
                            ('state', '=', 'active')],
                           order='start_date desc, id desc')
