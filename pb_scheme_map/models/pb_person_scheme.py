# -*- coding: utf-8 -*-
"""`pb.person.scheme` — the pay scheme that belongs to a PERSON, with a date.

WHY THIS EXISTS (PSCHEME, owner ruling R1, 2026-11-26)
------------------------------------------------------
Until now the pay scheme of a person was a consequence of their TEAM: the map
attached a team (or a division) to a scheme and everybody in it followed. A
Vietnamese and an Indonesian in one team could not be paid by two schemes, and
a hire whose country of work differed from the team's had no seam at all.

This model is the seam. One row per scheme the person is on, from a date
(cloned from `pb.division.link`: dated, a history, no overlap). The kind of
run is DERIVED from the scheme (`cycle_type`, stored related, ledger A1), so a
row can never say "advance" while naming an end-of-month scheme; a person paid
a mid-month advance has two rows. No final-settlement rows (they follow the
map, ledger A3).

THE READ is `pb.scheme.map._person_schemes` (the resolver's `'person'` rung,
between the work segment and the team). THE WRITE is
`pb.scheme.board._person_set_write`, reached only through the board and the
approval route (`pb.schememap.proposal` kind `person_set`). Nobody writes a
row from a native form: the access list grants READ only, so every write runs
with `sudo()` behind the board's own gate.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

SOURCES = [
    ('fill', 'Filled in once'),
    ('hire', 'Add employee'),
    ('hand', 'Changed by hand'),
    ('team', 'Set for the whole team'),
    ('import', 'Pay data file'),
    ('sheet', 'Upload sheet'),
    ('job_change', 'Job change'),
]


class PbPersonScheme(models.Model):
    _name = 'pb.person.scheme'
    _description = 'Pay scheme of a person'
    _order = 'date_from desc, id desc'
    _rec_name = 'config_id'

    employee_id = fields.Many2one(
        'hr.employee', string='Person', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='employee_id.company_id',
        store=True, index=True)
    config_id = fields.Many2one(
        'hr.formula.config', string='Pay scheme', required=True,
        ondelete='restrict', index=True)
    cycle_type = fields.Selection(
        related='config_id.cycle_type', store=True, index=True,
        string='Kind of pay run')
    date_from = fields.Date(string='From', required=True, index=True)
    date_to = fields.Date(string='Until', index=True)
    source = fields.Selection(SOURCES, string='Where it came from',
                              default='hand', required=True)
    note = fields.Char(string='Note')
    active = fields.Boolean(default=True)
    #: The seam for "an ongoing two-country split = a second contract"
    #: (owner ruling R5, later). Empty in this programme.
    contract_id = fields.Many2one('hr.contract', string='Contract',
                                  ondelete='set null')

    # ----------------------------------------------------------- the rules
    @api.constrains('employee_id', 'config_id', 'date_from', 'date_to',
                    'active')
    def _check_person_scheme(self):
        """One pay scheme of each kind per person on any day, of their own
        company, never a final settlement, and never ending before it starts.
        Each refusal is one plain sentence naming what is in the way."""
        for row in self:
            if not row.active or not row.employee_id or not row.config_id:
                continue
            person = row.employee_id.name or ''
            scheme = row.config_id.name or ''
            if row.date_to and row.date_from and row.date_to < row.date_from:
                raise ValidationError(_(
                    "The end date is before the start date. A pay scheme "
                    "cannot end before it starts."))
            if row.config_id.cycle_type == 'full_final':
                raise ValidationError(_(
                    "%(scheme)s is a final settlement scheme. A person is not "
                    "given one of their own: final settlements are worked out "
                    "when somebody leaves.", scheme=scheme))
            company = row.config_id.company_id
            if company and company != row.employee_id.company_id:
                raise ValidationError(_(
                    "%(scheme)s belongs to %(company)s, so it cannot pay "
                    "%(person)s.", scheme=scheme, company=company.name or '',
                    person=person))
            domain = [
                ('id', '!=', row.id),
                ('employee_id', '=', row.employee_id.id),
                ('cycle_type', '=', row.config_id.cycle_type),
                ('active', '=', True),
                '|', ('date_to', '=', False), ('date_to', '>=', row.date_from),
            ]
            if row.date_to:
                domain.append(('date_from', '<=', row.date_to))
            clash = self.sudo().search(domain, limit=1)
            if clash:
                raise ValidationError(_(
                    "%(person)s already has %(scheme)s from %(since)s. A "
                    "person has one pay scheme of each kind at a time: end "
                    "that one first, or start this one later.",
                    person=person, scheme=clash.config_id.name or '',
                    since=format_date(self.env, clash.date_from,
                                      date_format='d MMM y')))

    # ------------------------------------------------- keeping "Paid by" true
    def _pb_flag(self, employee_ids=None):
        ids = set(employee_ids or []) | set(self.mapped('employee_id').ids)
        if not ids or 'hr.employee' not in self.env:
            return
        try:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                employee_ids=sorted(ids))
        except Exception:       # noqa: BLE001 — never block a scheme change
            _logger.exception('Could not flag "paid by" after a person scheme '
                              'changed')

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        rows._pb_flag()
        return rows

    def write(self, vals):
        before = self.mapped('employee_id').ids
        res = super().write(vals)
        self._pb_flag(before)
        return res

    def unlink(self):
        people = self.mapped('employee_id').ids
        res = super().unlink()
        if people and 'hr.employee' in self.env:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                employee_ids=people)
        return res

    # ------------------------------------------------------ the daily job
    @api.model
    def _cron_mark_boundaries(self):
        """Daily: a row that starts today, or ended yesterday, changes who
        pays that person from today. Mark exactly those people; the nightly
        "Paid by" job settles them (ledger PSCHEME B.3)."""
        today = fields.Date.context_today(self)
        rows = self.sudo().search([
            ('active', '=', True),
            '|', ('date_from', '=', today),
            ('date_to', '=', today - timedelta(days=1)),
        ])
        people = rows.mapped('employee_id').ids
        if people:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                employee_ids=people)
        _logger.info('Person pay schemes: %s people start or end a scheme '
                     'today', len(people))
        return len(people)
