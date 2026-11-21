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
from odoo.exceptions import AccessError
from odoo.tools.misc import format_date

from .comp_common import BENEFIT_KINDS

_logger = logging.getLogger(__name__)

#: WDGAP QF4 (B1) — who a plan covers without HR adding them one by one.
AUTO_COVER = [
    ('none', 'Nobody (HR adds people)'),
    ('join', 'Everyone, from the day they join'),
    ('probation', 'Everyone, once the trial period is passed'),
]

#: How an enrollment started (B2) and why its end date is set (B4).
STARTED_BY = [
    ('manual', 'Added by HR'),
    ('auto', 'Started automatically'),
]
END_REASONS = [
    ('manual', 'Set by HR'),
    ('leaving', 'Leaving'),
]

#: The head of pay — the only role that may cover a whole company at once.
GROUP_HEAD = 'pb_comp_ben.group_comp_head'


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

    # WDGAP QF4 (B1). "Nobody" is the default, so every existing plan keeps
    # behaving exactly as it did until somebody chooses otherwise.
    auto_cover = fields.Selection(
        AUTO_COVER, string='Who is covered automatically', default='none',
        required=True,
        help='Payobook can put people on this plan by itself: everyone in the '
             'plan\'s company (and its country, if it has one) from the day '
             'they join, or once their trial period is passed. People who '
             'are here already are added with "Cover everyone who qualifies '
             'now".')

    def _compute_enrolled(self):
        for plan in self:
            plan.enrolled_count = len(plan.enrollment_ids.filtered(
                lambda e: e.state == 'active'))

    # ================================================== WDGAP QF4: who is in
    @api.model
    def _employee_country_code(self, employee):
        """The country somebody works in — the leave screens' answer.

        A probed clone of `pb.timeoff._emp_country` (pb_timeoff is not a
        dependency here): their absence policy's country, else their payroll
        country, else their company's.
        """
        emp = employee.sudo()
        if 'pb_leave_policy_id' in emp._fields and emp.pb_leave_policy_id \
                and emp.pb_leave_policy_id.country_id:
            return emp.pb_leave_policy_id.country_id.code or ''
        if 'payroll_country' in emp._fields and emp.payroll_country:
            return str(emp.payroll_country or '').upper()
        return emp.company_id.country_id.code or ''

    @api.model
    def _joining_date(self, employee):
        emp = employee.sudo()
        day = False
        try:
            day = emp._get_first_contract_date()
        except Exception:                   # noqa: BLE001 — a date, not a fault
            day = False
        if not day and 'contract_date_start' in emp._fields:
            day = emp.contract_date_start
        return day or fields.Date.context_today(self)

    @api.model
    def _trial_passed(self, employee):
        """Has this person's trial period been passed (or is there none)?"""
        emp = employee.sudo()
        if 'pb_probation_state' in emp._fields and emp.pb_probation_state:
            return emp.pb_probation_state in ('passed', 'na')
        end = emp.trial_date_end if 'trial_date_end' in emp._fields else False
        return not end or end < fields.Date.context_today(self)

    def _qualifies(self, employee, country_code=None):
        """In this plan's company, and its country when it has one."""
        self.ensure_one()
        emp = employee.sudo()
        if not emp or not emp.active:
            return False
        if not self.company_id or emp.company_id.id != self.company_id.id:
            return False
        if self.country_id:
            code = country_code if country_code is not None \
                else self._employee_country_code(emp)
            if (code or '').upper() != (self.country_id.code or '').upper():
                return False
        return True

    @api.model
    def _enrol_who_qualifies(self, employee, moment, on_date=None):
        """Put somebody on every plan that covers them at this moment.

        `moment` is ``'join'`` (they became an employee) or ``'probation'``
        (their trial period was passed). Never makes a second active
        enrollment for the same plan and person; returns what it made.
        Called by the hooks as the system, inside their own try/except.
        """
        Enrollment = self.env['pb.benefit.enrollment'].sudo()
        emp = employee.sudo() if employee else employee
        if not emp or moment not in ('join', 'probation'):
            return Enrollment.browse()
        plans = self.sudo().search([
            ('auto_cover', '=', moment), ('active', '=', True),
            ('company_id', '=', emp.company_id.id)])
        if not plans:
            return Enrollment.browse()
        code = self._employee_country_code(emp)
        have = set(Enrollment.search([
            ('employee_id', '=', emp.id), ('state', '=', 'active'),
            ('plan_id', 'in', plans.ids)]).mapped('plan_id').ids)
        start = fields.Date.to_date(on_date) if on_date else (
            self._joining_date(emp) if moment == 'join'
            else fields.Date.context_today(self))
        made = []
        for plan in plans:
            if plan.id in have or not plan._qualifies(emp, code):
                continue
            made.append({'plan_id': plan.id, 'employee_id': emp.id,
                         'start_date': start, 'started_by': 'auto',
                         'company_id': plan.company_id.id})
        if not made:
            return Enrollment.browse()
        rows = Enrollment.create(made)
        _logger.info('pb_comp_ben: %s plan(s) started automatically for '
                     'employee %s (%s)', len(rows), emp.id, moment)
        return rows

    # ----------------------------------------- B3: "Cover everyone ... now"
    def _require_head(self):
        if not self.env.user.has_group(GROUP_HEAD):
            raise AccessError(_(
                "Only the head of pay can put everybody on a plan at once."))

    def _cover_everyone_plan(self):
        """(qualifying people, already covered, to add) for one plan."""
        self.ensure_one()
        plan = self.sudo()
        Employee = self.env['hr.employee'].sudo()
        if plan.auto_cover == 'none' or not plan.company_id:
            return Employee.browse(), Employee.browse(), Employee.browse()
        people = Employee.search([('company_id', '=', plan.company_id.id)])
        if plan.country_id:
            people = people.filtered(lambda e: plan._qualifies(e))
        if plan.auto_cover == 'probation':
            people = people.filtered(lambda e: self._trial_passed(e))
        covered_ids = set(self.env['pb.benefit.enrollment'].sudo().search([
            ('plan_id', '=', plan.id), ('state', '=', 'active'),
            ('employee_id', 'in', people.ids)]).mapped('employee_id').ids)
        covered = people.filtered(lambda e: e.id in covered_ids)
        return people, covered, people - covered

    def cover_everyone_preview(self):
        self.ensure_one()
        self._require_head()
        people, covered, missing = self._cover_everyone_plan()
        if self.auto_cover == 'none':
            sentence = _("This plan covers nobody automatically. Choose who "
                         "it covers first.")
        elif not people:
            sentence = _("Nobody qualifies for this plan right now.")
        elif not missing:
            sentence = _("%(count)s people qualify and every one of them is "
                         "already covered.", count=len(people))
        else:
            sentence = _(
                "%(people)s people qualify, %(covered)s are already covered, "
                "%(add)s will be added.", people=len(people),
                covered=len(covered), add=len(missing))
        return {'qualify': len(people), 'covered': len(covered),
                'add': len(missing), 'sentence': sentence,
                'names': [e.name or '' for e in missing[:12]]}

    def cover_everyone(self):
        """Add everybody who qualifies and is not on it yet. Idempotent."""
        self.ensure_one()
        self._require_head()
        _people, _covered, missing = self._cover_everyone_plan()
        if not missing:
            return 0
        today = fields.Date.context_today(self)
        rows = []
        for emp in missing:
            start = today
            if self.auto_cover == 'join':
                joined = self._joining_date(emp)
                start = joined if joined and joined > today else today
            rows.append({'plan_id': self.id, 'employee_id': emp.id,
                         'start_date': start, 'started_by': 'auto',
                         'company_id': self.company_id.id})
        self.env['pb.benefit.enrollment'].sudo().create(rows)
        return len(rows)

    def action_cover_everyone(self):
        """The plan form's button: the preview first, in a small window."""
        self.ensure_one()
        self._require_head()
        wizard = self.env['pb.benefit.cover.wizard'].create(
            {'plan_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cover everyone who qualifies now'),
            'res_model': 'pb.benefit.cover.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    # ------------------------------------------------ B4: leavers' cover ends
    @api.model
    def _leaving_rows(self, employee):
        return self.env['pb.benefit.enrollment'].sudo().search([
            ('employee_id', '=', employee.id), ('state', '=', 'active')])

    @api.model
    def _stamp_leaving(self, employee, last_day):
        """Cover ends on the person's last working day. Returns rows moved.

        Touches only rows still covered that have no end date, or whose end
        date was stamped by a departure before ("leaving"). An end date HR set
        by hand, and any row HR already ended, are never touched.
        """
        emp = employee.sudo() if employee else employee
        day = fields.Date.to_date(last_day) if last_day else False
        if not emp or not day:
            return 0
        moved = 0
        for row in self._leaving_rows(emp):
            if row.end_date and row.end_reason != 'leaving':
                continue
            if row.end_date == day and row.end_reason == 'leaving':
                continue
            row.write({'end_date': day, 'end_reason': 'leaving'})
            moved += 1
        return moved

    @api.model
    def _clear_leaving(self, employee, only_day=None):
        """The exit was called off: the stamped end dates go, nothing else.

        `only_day` narrows it to the rows stamped with that last day, so
        calling off ONE exit (a resignation withdrawn, a leaving checklist
        cancelled) never undoes a different departure on the record.
        """
        emp = employee.sudo() if employee else employee
        if not emp:
            return 0
        day = fields.Date.to_date(only_day) if only_day else None
        rows = self._leaving_rows(emp).filtered(
            lambda r: r.end_reason == 'leaving'
            and (day is None or r.end_date == day))
        if rows:
            rows.write({'end_date': False, 'end_reason': 'manual'})
        return len(rows)

    @api.model
    def _cron_end_due(self):
        """Daily: cover whose last day has passed shows as Ended. State only."""
        today = fields.Date.context_today(self)
        rows = self.env['pb.benefit.enrollment'].sudo().search([
            ('state', '=', 'active'), ('end_date', '!=', False),
            ('end_date', '<', today)])
        if rows:
            rows.write({'state': 'ended'})
        _logger.info('pb_comp_ben: %s benefit enrollment(s) ended today',
                     len(rows))
        return len(rows)


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
    # WDGAP QF4 (B2, B4)
    started_by = fields.Selection(STARTED_BY, string='How it started',
                                  default='manual', required=True)
    end_reason = fields.Selection(
        END_REASONS, string='Why it ends', default='manual', required=True,
        help='"Leaving" means Payobook set the end date from the person\'s '
             'last working day, and moves it if that day changes.')
    end_note = fields.Char(string='Ends', compute='_compute_end_note')

    @api.depends('end_date', 'end_reason', 'state')
    def _compute_end_note(self):
        for rec in self:
            if rec.state != 'active' or not rec.end_date:
                rec.end_note = ''
                continue
            day = format_date(rec.env, rec.end_date, date_format='d MMM y')
            rec.end_note = _("Ends %(day)s · leaving", day=day) \
                if rec.end_reason == 'leaving' else _("Ends %(day)s", day=day)

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
