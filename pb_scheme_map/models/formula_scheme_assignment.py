# -*- coding: utf-8 -*-
"""The map row: a part of the workforce, and the scheme that pays it.

WHY THIS IS AN EXTENSION AND NOT A NEW TABLE
--------------------------------------------
`hr.formula.scheme.assignment` already existed and already carried
`config_id`, `department_id`, `domain` and `sequence`; the Mapping canvas has
been writing it since F10. Building a second table beside it would mean two
answers to "which scheme pays Bread" and a migration nobody asked for. So the
row grows three ideas instead:

  * **which KIND OF RUN it answers** (`cycle_type`). A division is normally
    paid twice — a mid-month advance and an end-of-month payroll — by two
    different schemes. One row per department could never say that. `any` is
    the default and means "whatever kind of run you are doing"; a row naming a
    kind beats a row that does not.

  * **a DIVISION as well as a department** (`division_id`). Divisions are the
    parts of the business that do not stop at a company border (ruling G2), and
    a group with a department tree per country would otherwise attach the same
    scheme forty times.

  * **where the row CAME FROM** (`source`, `confidence`, `note`). A row a
    person drew and a row this system proposed from what was actually paid are
    different kinds of fact, and a screen that cannot tell them apart cannot
    ask "is this right?".

`company_id` is stored and related from the scheme, because every question this
programme asks — coverage, the pay run's population, the exceptions queue — is
asked of ONE company, and a related-but-unstored field cannot be searched
(ledger gotcha GR3: the canvas had no company domain at all, which on a group
makes it cross-company on day one).

ONE ROW PER (SEGMENT, KIND OF RUN)
----------------------------------
Enforced in Python rather than in the database, because the sentence matters:
"Bread already has a scheme for end-of-month runs" is something a person can
act on and `duplicate key value violates unique constraint` is not. Archived
rows are ignored — a map that cannot keep its history is a map nobody dares
change.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

#: The kinds of run a map row can answer. `any` first: it is the default and
#: the answer for every company that runs payroll once a month.
CYCLE_SELECTION = [
    ('any', 'Any kind of run'),
    ('regular', 'Regular payroll'),
    ('mid_cycle', 'Mid-month advance'),
    ('end_cycle', 'End of month'),
    ('full_final', 'Final settlement'),
]

#: The same words, for a sentence rather than for a field label.
CYCLE_WORDS = {
    'any': 'any kind of run',
    'regular': 'regular payroll',
    'mid_cycle': 'mid-month advance',
    'end_cycle': 'end-of-month',
    'full_final': 'final settlement',
}


class HrFormulaSchemeAssignment(models.Model):
    _inherit = 'hr.formula.scheme.assignment'

    division_id = fields.Many2one(
        'pb.division', string='Division', index=True, ondelete='cascade',
        help="Attach a whole division — every department in it, in every "
             "company — to this scheme.")
    cycle_type = fields.Selection(
        CYCLE_SELECTION, string='Kind of run', default='any', required=True,
        index=True,
        help="Which kind of pay run this line answers. A line that names a "
             "kind of run is used for that kind; a line that says any kind is "
             "used when nothing more specific applies.")
    company_id = fields.Many2one(
        'res.company', string='Company', related='config_id.company_id',
        store=True, index=True)
    source = fields.Selection([
        ('manual', 'Drawn by hand'),
        ('drafted', 'Proposed'),
        ('accepted', 'Proposed and accepted'),
    ], string='Where this line came from', default='manual', required=True)
    confidence = fields.Float(
        string='Agreement', default=0.0,
        help="For a proposed line: the share of this team's people who were "
             "actually paid under this scheme.")
    note = fields.Char(string='Why')

    # ------------------------------------------------------------ the sentence
    @api.depends('department_id', 'division_id', 'config_id', 'cycle_type')
    def _compute_name(self):
        """The row's own words. Overrides the base compute, which knew only
        about departments and would print "All employees" for a division."""
        for row in self:
            row.name = '%s → %s' % (row._segment_label(),
                                         row.config_id.name or '')

    def _segment_label(self):
        self.ensure_one()
        if self.division_id:
            return self.division_id.name or _("Division")
        if self.department_id:
            return (self.department_id.complete_name
                    or self.department_id.name or _("Department"))
        if self.domain:
            return _("A rule")
        return _("Everyone")

    # -------------------------------------------------------------- the rules
    @api.constrains('department_id', 'division_id', 'domain')
    def _check_one_segment(self):
        """Exactly one of a department, a division or a rule."""
        for row in self:
            picked = [bool(row.department_id), bool(row.division_id),
                      bool(row.domain)]
            if sum(1 for p in picked if p) != 1:
                raise ValidationError(_(
                    "A line on the map covers exactly one thing: a "
                    "department, a division, or a rule. Pick one of them."))

    @api.constrains('department_id', 'division_id', 'cycle_type', 'active',
                    'config_id')
    def _check_one_scheme_per_kind_of_run(self):
        """One department (or division), one scheme, per kind of run."""
        for row in self:
            if not row.active:
                continue
            base = [('id', '!=', row.id), ('active', '=', True),
                    ('cycle_type', '=', row.cycle_type)]
            if row.department_id:
                base.append(('department_id', '=', row.department_id.id))
                what = (row.department_id.complete_name
                        or row.department_id.name)
            elif row.division_id:
                base.append(('division_id', '=', row.division_id.id))
                what = row.division_id.name
            else:
                continue
            clash = self.sudo().search(base, limit=1)
            if clash:
                raise ValidationError(_(
                    "%(what)s already has a scheme for %(kind)s: "
                    "%(scheme)s. Take that one off first, or attach this one "
                    "for a different kind of run.",
                    what=what, kind=_(CYCLE_WORDS.get(row.cycle_type, 'runs')),
                    scheme=clash.config_id.name or ''))

    # ------------------------------------------------------------- the domain
    def _employee_domain(self):
        """Who this line covers, as an employee domain.

        A division has no employee field of its own: it is a set of
        departments, so it resolves to the departments attached to it today
        and everything under them.
        """
        self.ensure_one()
        if self.division_id:
            Division = self.env['pb.division'].sudo()
            links = self.division_id.link_ids.filtered('active')
            dept_ids = links.mapped('department_id').ids
            if not dept_ids:
                return [('id', '=', 0)]
            children = Division.env['hr.department'].sudo().search(
                [('id', 'child_of', dept_ids)]).ids
            return [('department_id', 'in', children or dept_ids)]
        return super()._employee_domain()

    # --------------------------------------------------- keeping people fresh
    def _mark_people_stale(self):
        """Whoever this row could change now needs "Paid by" worked out again."""
        Employee = self.env.get('hr.employee')
        if Employee is None:
            return
        companies = self.mapped('company_id').ids
        try:
            Employee.sudo()._pb_mark_paid_by_stale(companies)
        except Exception:       # noqa: BLE001 — never block a map edit
            _logger.exception('Could not mark "paid by" as needing a refresh')

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        rows._mark_people_stale()
        return rows

    def write(self, vals):
        before = self.mapped('company_id').ids
        res = super().write(vals)
        self._mark_people_stale()
        if before:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(before)
        return res

    def unlink(self):
        companies = self.mapped('company_id').ids
        res = super().unlink()
        if companies:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(companies)
        return res
