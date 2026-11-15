# -*- coding: utf-8 -*-
"""`pb.job.change` — a promotion, a transfer and a pay change as ONE request.

WHAT WAS TRUE BEFORE (WDGAP S8 facts §2). Four screens, four writers, three
approvals: Pay › Changes wrote the wage at once whatever its start date said
and put the job on the contract only; the Records desk wrote the job on the
person only; the org chart moved the manager with no approval; the contract
drawer wrote the contract's team with no date. A promotion that also moved a
person to another team was two or three requests that could be decided
differently.

WHAT IS TRUE NOW. One record holds every new value, one start date, one reason
and one sign-off route (owner ruling J1: their manager, then HR, then Finance
only when the rise is above the guidance — process key ``jobchange``). On
approval everything is written together:

  * the PERSON (their current version, in place — the standing ruling: no new
    contract, no new `hr.version`) and the running CONTRACT's job, team,
    working hours and company, so no two screens disagree (facts §1.1);
  * the wage, with a `pb.pay.apply` row so the old figure is kept for the
    24-hour take-back exactly the way Pay keeps it;
  * every pay line, get-or-create on the contract, each with a DATED
    `hr.contract.advantage.change` row — the one record proration and the
    Past-month re-work read (facts §1.2 #5). A wage change is logged the same
    way when the paying scheme has a wage input (BASIC / WAGE / BASE);
  * one letter, one event on the person's trail.

NOTHING IS WRITTEN BEFORE THE START DATE. A future change is approved and
held as "Scheduled"; the hourly job writes it on the day, in the company's own
time zone, after checking nothing it covers was changed by somebody else in
the meantime. A change that starts in a month already paid is allowed (ruling
J2) and says so, with a door to a new Past-month re-work for that person and
those months. This module writes NO back-pay input (cross-step contract C-6).
"""

import json
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from psycopg2 import errors as pg_errors

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules import module as odoo_module
from odoo.tools.misc import format_date

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, role_step, route,
)

_logger = logging.getLogger(__name__)

JOBCHANGE_PROCESS_KEY = 'jobchange'

#: Who may prepare a job change and read the board.
GATE_GROUPS = (
    'hr.group_hr_manager',
    'pb_pay.group_pay_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)
#: Who may see and change pay figures inside one.
PAY_GROUPS = (
    'pb_pay.group_pay_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('scheduled', 'Approved, starts later'),
    ('applied', 'Done'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('cancelled', 'Cancelled'),
    ('undone', 'Taken back'),
]
OPEN_STATES = ('draft', 'pending', 'scheduled', 'returned')
LIVE_STATES = ('pending', 'scheduled')

REASON_KINDS = [
    ('promotion', 'Promotion'),
    ('transfer', 'Transfer'),
    ('pay', 'Pay change'),
    ('other', 'Something else'),
]

#: (field on this record, field on hr.employee) — what a change can move on
#: the person. Order matters: the company first, then the job before its
#: title (Odoo recomputes the title from the job).
EMPLOYEE_MAP = (
    ('new_company_id', 'company_id'),
    ('new_job_id', 'job_id'),
    ('new_job_title', 'job_title'),
    ('new_department_id', 'department_id'),
    ('new_parent_id', 'parent_id'),
    ('new_work_location_id', 'work_location_id'),
    ('new_resource_calendar_id', 'resource_calendar_id'),
)
#: The same values written on the running contract (facts §1.1: a job or team
#: change writes BOTH, or screens disagree).
CONTRACT_MAP = (
    ('new_company_id', 'company_id'),
    ('new_job_id', 'job_id'),
    ('new_department_id', 'department_id'),
    ('new_resource_calendar_id', 'resource_calendar_id'),
)
#: The scheme input codes that read the contract wage
#: (`hr_payslip_formula.py`, contract_mapping BASIC/WAGE/BASE).
WAGE_CODES = ('BASIC', 'WAGE', 'BASE')

#: How far ahead / back a start date may be.
MAX_AHEAD_DAYS = 366
MAX_BACK_DAYS = 366
UNDO_HOURS = 24

#: The letter types this module adds (selection_add on pb_lifecycle's list).
LETTER_PROMOTION = 'promotion'
LETTER_TRANSFER = 'transfer'
LETTER_JOB_CHANGE = 'job_change'

LOCK_ERRORS = (pg_errors.LockNotAvailable,)


def _id(record):
    return record.id if record else False


class PbJobChange(models.Model):
    _name = 'pb.job.change'
    _description = 'Job change'
    _inherit = ['mail.thread', 'biz.approval.adapter.mixin']
    _order = 'id desc'

    _approval_process_key = JOBCHANGE_PROCESS_KEY

    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default='/', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Person', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda s: s.env.company)
    contract_id = fields.Many2one(
        'hr.contract', string='Running contract', ondelete='set null',
        index=True)
    user_id = fields.Many2one('res.users', string='Prepared by', index=True,
                              default=lambda s: s.env.user, readonly=True)
    reason_kind = fields.Selection(REASON_KINDS, string='What kind of change',
                                   default='promotion', required=True)
    reason = fields.Text(string='Why')
    effective_date = fields.Date(string='Starts on', index=True)
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False,
                             tracking=True)
    #: Where the request came from: typed here, or opened prefilled by another
    #: module through `pb_start_for_employee` (an internal hire, for one).
    source = fields.Char(string='Started from', readonly=True)
    source_ref = fields.Char(string='Started from (reference)', readonly=True)

    # ------------------------------------------------------------ new values
    new_job_id = fields.Many2one('hr.job', string='New job')
    new_job_title = fields.Char(string='New job title')
    new_department_id = fields.Many2one('hr.department', string='New team')
    new_parent_id = fields.Many2one('hr.employee', string='New manager')
    new_work_location_id = fields.Many2one('hr.work.location',
                                           string='New place of work')
    new_resource_calendar_id = fields.Many2one('resource.calendar',
                                               string='New working hours')
    new_company_id = fields.Many2one('res.company', string='New company')
    change_pay = fields.Boolean(string='Changes pay')
    new_wage = fields.Monetary(string='New monthly pay',
                               currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency')
    line_ids = fields.One2many('pb.job.change.line', 'change_id',
                               string='Pay lines', copy=True)

    # ------------------------------------------------ what it was, when sent
    #: `{field: [id, label] | value}` of every value the change covers, read
    #: off the person and the contract when it was sent in. The apply re-reads
    #: the same values and refuses if any of them moved since.
    before_json = fields.Text(string='How it looked (JSON)', readonly=True,
                              copy=False)
    facts_json = fields.Text(string='Facts (JSON)', readonly=True, copy=False)

    # -------------------------------------------------------------- outcome
    applied_at = fields.Datetime(string='Done on', readonly=True, copy=False)
    applied_by = fields.Many2one('res.users', string='Done by', readonly=True,
                                 copy=False)
    started_by_job = fields.Boolean(string='Started automatically',
                                    readonly=True, copy=False)
    undo_until = fields.Datetime(string='Can be taken back until',
                                 readonly=True, copy=False)
    undone_at = fields.Datetime(string='Taken back on', readonly=True,
                                copy=False)
    undone_by = fields.Many2one('res.users', string='Taken back by',
                                readonly=True, copy=False)
    block_note = fields.Text(string='Why it could not be done', readonly=True,
                             copy=False)
    start_fail_days = fields.Integer(readonly=True, copy=False)
    start_last_fail = fields.Date(readonly=True, copy=False)
    letter_id = fields.Many2one('pb.hr.letter', string='Letter',
                                readonly=True, copy=False,
                                ondelete='set null')
    apply_ids = fields.One2many('pb.pay.apply', 'job_change_id',
                                string='Pay written')
    #: `[{month: 'YYYY-MM-01', config_id, config, payslips}]` — finished
    #: payslips whose period ends on or after the start date, read when it was
    #: written. A count only: nothing is recalculated (ruling J2, C-6).
    paid_months_json = fields.Text(string='Months already paid (JSON)',
                                   readonly=True, copy=False)
    #: The draft Past-month re-work opened from here, if any (an id, not a
    #: link: `pb_retro` is optional).
    rework_id = fields.Integer(string='Re-work', readonly=True, copy=False)
    #: The trail lines the write produced, folded into one event on the
    #: person's timeline.
    audit_ids_json = fields.Text(readonly=True, copy=False)
    #: What was written, so "Take it back" restores exactly that.
    written_json = fields.Text(readonly=True, copy=False)

    seat_user_ids = fields.Many2many(
        'res.users', 'pb_job_change_seat_rel', 'change_id', 'user_id',
        string='Asked to decide', copy=False)

    # ==================================================================
    # Small readers
    # ==================================================================
    def _json(self, name, default):
        self.ensure_one()
        try:
            value = json.loads(self[name] or 'null')
        except (TypeError, ValueError):
            return default
        return value if isinstance(value, type(default)) else default

    def facts(self):
        return self._json('facts_json', {})

    def before(self):
        return self._json('before_json', {})

    def paid_months(self):
        return self._json('paid_months_json', [])

    @api.model
    def _may_prepare(self, user=None):
        user = user or self.env.user
        return bool(self.env.su or user._is_admin()
                    or any(user.has_group(g) for g in GATE_GROUPS))

    @api.model
    def _may_see_pay(self, user=None):
        user = user or self.env.user
        return bool(self.env.su or user._is_admin()
                    or any(user.has_group(g) for g in PAY_GROUPS))

    @api.model
    def _require_prepare(self):
        if not self._may_prepare():
            raise AccessError(_(
                "Changing somebody's job is for HR and the pay team. Ask your "
                "administrator for the HR manager role."))

    @api.model
    def _today_for(self, company=None):
        """The date it is for a company (its time zone) — the one reading every
        dated change in this product uses (`pb.records.apply._today_for`)."""
        return self.env['pb.records.apply']._today_for(
            company or self.env.company)

    def _company_today(self):
        self.ensure_one()
        return self._today_for(self.company_id)

    @api.model
    def _running_contract(self, employee):
        if not employee:
            return self.env['hr.contract']
        return self.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id), ('state', '=', 'open'),
        ], order='date_start desc, id desc', limit=1)

    def _day(self, value):
        return format_date(self.env, value, date_format='d MMM y') \
            if value else ''

    def _month(self, value):
        return format_date(self.env, value, date_format='MMMM y') \
            if value else ''

    # ==================================================================
    # What changes
    # ==================================================================
    def _target_company(self):
        self.ensure_one()
        return self.new_company_id or self.employee_id.company_id \
            or self.company_id

    def _employee_vals(self):
        """`{employee field: new value id/text}` for every value that moves."""
        self.ensure_one()
        vals = {}
        emp = self.employee_id.sudo()
        for mine, theirs in EMPLOYEE_MAP:
            new = self[mine]
            if not new:
                continue
            new_value = new.id if isinstance(new, models.BaseModel) else new
            old = emp[theirs]
            old_value = old.id if isinstance(old, models.BaseModel) else old
            if new_value != old_value:
                vals[theirs] = new_value
        return vals

    def _contract_vals(self, contract):
        self.ensure_one()
        vals = {}
        if not contract:
            return vals
        for mine, theirs in CONTRACT_MAP:
            new = self[mine]
            if not new or theirs not in contract._fields:
                continue
            if contract[theirs].id != new.id:
                vals[theirs] = new.id
        if self.change_pay and self.new_wage and \
                float(self.new_wage) != float(contract.wage or 0.0):
            vals['wage'] = float(self.new_wage)
        return vals

    def _line_plan(self, contract):
        """`[{line, template, code, name, old, new}]` — pay lines that move."""
        self.ensure_one()
        out = []
        if not self.change_pay or not contract:
            return out
        Advantage = self.env['hr.contract.advantage'].sudo()
        for row in self.line_ids:
            code = (row.code or '').strip()
            if not code:
                continue
            line = Advantage.search([('contract_id', '=', contract.id),
                                     ('advantage_template_code', '=', code)],
                                    limit=1)
            old = float(line.amount or 0.0) if line else 0.0
            new = float(row.new_amount or 0.0)
            if abs(new - old) < 1e-9:
                continue
            out.append({'line': line, 'code': code,
                        'name': row.name or code, 'old': old, 'new': new})
        return out

    def _changes_team(self):
        self.ensure_one()
        vals = self._employee_vals()
        return any(k in vals for k in ('department_id', 'company_id',
                                       'parent_id'))

    def _pct(self, contract=None):
        self.ensure_one()
        contract = contract if contract is not None else (
            self.contract_id.sudo() or self._running_contract(self.employee_id))
        old = float(contract.wage or 0.0) if contract else 0.0
        if not self.change_pay or not self.new_wage or not old:
            return 0.0
        return round((float(self.new_wage) - old) / old * 100.0, 2)

    def _above_guidance(self, pct):
        """Bigger than the company's pay-change guidance (Pay settings:
        "Finance signs pay changes above …%") — the fact `pb.pay.change`
        routes Finance on."""
        self.ensure_one()
        settings = self.env['pb.pay.settings'].sudo().for_company(
            self._target_company())
        threshold = float(settings.change_finance_pct or 0.0)
        return bool(threshold) and abs(float(pct or 0.0)) > threshold

    def _above_band(self):
        """Above the top of the band of the (new) job, where bands are kept."""
        self.ensure_one()
        if not self.change_pay or not self.new_wage:
            return False
        job = self.new_job_id or self.employee_id.sudo().job_id
        if not job or 'pb.pay.band.job' not in self.env:
            return False
        link = self.env['pb.pay.band.job'].sudo().search(
            [('job_id', '=', job.id)], limit=1)
        band = link.band_id if link else False
        top = float(band.max_amount or 0.0) if band else 0.0
        return bool(top) and float(self.new_wage) > top

    def _manager_user(self):
        """Their manager's login TODAY (before the change) — the first step."""
        self.ensure_one()
        manager = self.employee_id.sudo().parent_id
        user = manager.user_id if manager else False
        if user and user.active and user != self.employee_id.sudo().user_id:
            return user
        return self.env['res.users']

    # ------------------------------------------------------------ the scheme
    def _scheme_now_and_after(self):
        """`(now {id,name}, after {id,name})` — who pays them, today and with
        the new team/company (`pb.scheme.map`, the pay run's own ladder)."""
        self.ensure_one()
        Map = self.env.get('pb.scheme.map')
        blank = {'id': 0, 'name': ''}
        if Map is None:
            return blank, blank
        emp = self.employee_id
        try:
            now = Map.sudo().resolve(emp)
        except Exception:       # noqa: BLE001 — a preview must never raise
            _logger.debug('job change: scheme read failed', exc_info=True)
            return blank, blank
        now_row = {'id': now.get('config_id') or 0,
                   'name': now.get('config_name') or ''}
        vals = self._employee_vals()
        if 'department_id' not in vals and 'company_id' not in vals:
            return now_row, now_row
        dept = vals.get('department_id') or emp.sudo().department_id.id
        company = vals.get('company_id') or emp.sudo().company_id.id
        try:
            after = Map.sudo().with_context(
                pb_jc_department_override={emp.id: (dept, company)}
            ).resolve(emp)
        except Exception:       # noqa: BLE001
            _logger.debug('job change: scheme what-if failed', exc_info=True)
            return now_row, now_row
        return now_row, {'id': after.get('config_id') or 0,
                         'name': after.get('config_name') or ''}

    def _scheme_reads(self, config_id):
        """The pay items of the person's scheme that READ a value this change
        moves (facts §1.2 #4: application-data schemes read job, team, level,
        cost centre…). Names only."""
        self.ensure_one()
        if not config_id or 'hr.formula.config' not in self.env:
            return []
        config = self.env['hr.formula.config'].sudo().browse(
            int(config_id)).exists()
        if not config:
            return []
        moving = set(self._employee_vals())
        if self.change_pay:
            moving.add('wage')
        if 'parent_id' in moving:
            moving.update({'manager_name', 'manager_email'})
        if 'work_location_id' in moving:
            moving.update({'work_location', 'work_country', 'work_city'})
        found = []
        for rule in config.rule_ids:
            keys = []
            key = getattr(rule, 'application_source_key', False)
            if key:
                keys.append(key.split('.', 1)[-1])
            for source in getattr(rule, 'source_ids', []):
                if source.kind in ('employee_field', 'contract_field') \
                        and source.key:
                    keys.append(source.key.strip())
            if any(k in moving for k in keys):
                if (rule.code or '').upper() in WAGE_CODES \
                        and set(keys) <= {'wage'}:
                    continue    # the wage itself is not a surprise
                found.append(rule.name or rule.code or '')
        return sorted({f for f in found if f})

    # ------------------------------------------------- months already paid
    def _paid_months(self):
        """Finished payslips of a REGULAR run whose period ends on or after the
        start date, one row per month and scheme."""
        self.ensure_one()
        if not self.effective_date or 'hr.payslip' not in self.env:
            return []
        Payslip = self.env['hr.payslip'].sudo()
        known = dict(Payslip._fields['state']._description_selection(self.env))
        finished = [s for s in ('done', 'paid') if s in known] or ['done']
        slips = Payslip.search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', finished),
            ('date_to', '>=', self.effective_date),
        ], order='date_to')
        out = {}
        for slip in slips:
            run = slip.payslip_run_id
            kind = getattr(run, 'pb_run_kind', False) if run else False
            if kind and kind != 'regular':
                continue
            month = slip.date_to.replace(day=1)
            config = getattr(slip, 'formula_config_id', False)
            key = (fields.Date.to_string(month), config.id if config else 0)
            row = out.setdefault(key, {
                'month': key[0], 'month_label': self._month(month),
                'config_id': key[1],
                'config': config.name if config else '', 'payslips': 0})
            row['payslips'] += 1
        return [out[k] for k in sorted(out)]

    # ==================================================================
    # Checking a draft before it is sent
    # ==================================================================
    def _problems(self):
        """Every reason this cannot be sent, as sentences."""
        self.ensure_one()
        out = []
        emp = self.employee_id.sudo()
        if not emp or not emp.active:
            return [_("Pick somebody who still works here.")]
        contract = self._running_contract(emp)
        emp_vals = self._employee_vals()
        lines = self._line_plan(contract) if contract else []
        wage_moves = bool(self.change_pay and self.new_wage and contract and
                          float(self.new_wage) != float(contract.wage or 0.0))
        if not emp_vals and not wage_moves and not lines:
            out.append(_("Nothing changes yet. Choose a new job, team, manager "
                         "or pay."))
        if self.change_pay and not contract:
            out.append(_("%s has no running contract, so their pay cannot be "
                         "changed here.", emp.name))
        if self.change_pay and contract and not wage_moves and not lines:
            out.append(_("Type the new monthly pay or a pay line, or leave pay "
                         "unchanged."))
        if self.change_pay and float(self.new_wage or 0.0) < 0.0:
            out.append(_("The new monthly pay cannot be below zero."))
        if not self.effective_date:
            out.append(_("Choose the day the change starts."))
        else:
            today = self._today_for(self._target_company())
            if self.effective_date > today + timedelta(days=MAX_AHEAD_DAYS):
                out.append(_("A change can start at most a year ahead."))
            if self.effective_date < today - timedelta(days=MAX_BACK_DAYS):
                out.append(_("A change can start at most a year back."))
        if not (self.reason or '').strip():
            out.append(_("Say why, in a few words. The people who sign it off "
                         "read this first."))
        manager = self.new_parent_id
        if manager:
            if manager == emp:
                out.append(_("Somebody cannot be their own manager."))
            else:
                walk, seen = manager.sudo(), set()
                while walk and walk.id not in seen:
                    seen.add(walk.id)
                    if walk.parent_id == emp:
                        out.append(_("%(m)s reports to %(p)s, so %(p)s cannot "
                                     "report to %(m)s.", m=manager.name,
                                     p=emp.name))
                        break
                    walk = walk.parent_id
        target = self._target_company()
        for rec, label in ((self.new_department_id, _('The new team')),
                           (self.new_job_id, _('The new job')),
                           (self.new_parent_id, _('The new manager')),
                           (self.new_work_location_id,
                            _('The new place of work')),
                           (self.new_resource_calendar_id,
                            _('The new working hours'))):
            company = rec.sudo().company_id if rec and \
                'company_id' in rec._fields else False
            if company and company != target:
                out.append(_("%(what)s belongs to %(co)s, not %(target)s.",
                             what=label, co=company.name,
                             target=target.name))
        if self.new_company_id and contract and \
                self.new_company_id.currency_id != \
                (contract.company_id or emp.company_id).currency_id and \
                not wage_moves:
            out.append(_("%(co)s pays in %(cur)s. Type the new monthly pay in "
                         "%(cur)s too.", co=self.new_company_id.name,
                         cur=self.new_company_id.currency_id.name))
        other = self.sudo().search([
            ('employee_id', '=', emp.id), ('state', 'in', LIVE_STATES),
            ('id', '!=', self._origin.id or 0)], limit=1)
        if other:
            out.append(_("%(who)s already has a job change waiting "
                         "(%(ref)s). Finish or cancel that one first.",
                         who=emp.name, ref=other.name))
        return out

    # ==================================================================
    # Sending it in
    # ==================================================================
    def _snapshot(self):
        """Every value this change covers, as it is right now."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        contract = self._running_contract(emp)
        out = {'contract_id': contract.id if contract else 0}
        for _mine, theirs in EMPLOYEE_MAP:
            value = emp[theirs]
            out['e.' + theirs] = value.id if isinstance(
                value, models.BaseModel) else (value or '')
        if contract:
            for _mine, theirs in CONTRACT_MAP:
                if theirs in contract._fields:
                    out['c.' + theirs] = contract[theirs].id or 0
            out['c.wage'] = float(contract.wage or 0.0)
            Advantage = self.env['hr.contract.advantage'].sudo()
            for row in self.line_ids:
                line = Advantage.search([
                    ('contract_id', '=', contract.id),
                    ('advantage_template_code', '=', row.code)], limit=1)
                out['l.' + (row.code or '')] = float(line.amount or 0.0) \
                    if line else 0.0
        return out

    def _covered_keys(self):
        """The snapshot keys this change actually moves — only those must not
        have moved underneath it."""
        self.ensure_one()
        contract = self.contract_id.sudo()
        keys = {'e.' + k for k in self._employee_vals()}
        keys |= {'c.' + k for k in self._contract_vals(contract)}
        keys |= {'l.' + r['code'] for r in self._line_plan(contract)}
        keys.add('contract_id')
        return keys

    def _compute_facts(self):
        self.ensure_one()
        contract = self._running_contract(self.employee_id)
        pct = self._pct(contract)
        now, after = self._scheme_now_and_after()
        lines = self._line_plan(contract) if contract else []
        wage_moves = 'wage' in self._contract_vals(contract)
        return {
            'kind': {'value': self.reason_kind or '', 'unit': ''},
            'changes_pay': {'value': bool(wage_moves or lines), 'unit': ''},
            'pay_rise_pct': {'value': pct, 'unit': '%'},
            'above_guidance': {'value': bool(self._above_guidance(pct)),
                               'unit': ''},
            'above_band': {'value': bool(self._above_band()), 'unit': ''},
            'changes_team': {'value': bool(self._changes_team()), 'unit': ''},
            'changes_scheme': {'value': bool(now['id'] != after['id']),
                               'unit': ''},
            'has_manager': {'value': bool(self._manager_user()), 'unit': ''},
            'new_wage': {'value': float(self.new_wage or 0.0)
                         if self.change_pay else 0.0,
                         'unit': (self.currency_id.name or '')},
        }

    def action_send(self):
        """Check, freeze and ask. Under "No approval needed" it is done (or
        scheduled) inside this call."""
        self.ensure_one()
        self._require_prepare()
        if self.state not in ('draft', 'returned'):
            raise UserError(_("This job change has already been sent in."))
        problems = self._problems()
        if problems:
            raise UserError('\n'.join(problems))
        contract = self._running_contract(self.employee_id)
        currency = (self.new_company_id or contract.company_id
                    or self.employee_id.company_id).currency_id
        vals = {
            'contract_id': contract.id or False,
            'currency_id': currency.id,
            'company_id': (self.employee_id.company_id or self.company_id).id,
        }
        self.sudo().write(vals)
        self.sudo().write({
            'before_json': json.dumps(self._snapshot(), default=str),
            'facts_json': json.dumps(self._compute_facts(), default=str),
            'block_note': False,
        })
        if self.name in (False, '/'):
            self.sudo().name = 'JC%05d' % self.id
        self.env['biz.approval.engine'].sudo().submit(self)
        self.invalidate_recordset()
        return self.answer()

    def answer(self):
        self.ensure_one()
        request = self.approval_request_id
        if self.state == 'applied':
            message = _("Done. %s's new job details are in place.",
                        self.employee_id.name)
        elif self.state == 'scheduled':
            message = _("Approved. It starts on %s and is written that morning.",
                        self._day(self.effective_date))
        elif self.state == 'pending':
            who = self._waiting_for()
            message = _("Sent for approval — %s", who) if who \
                else _("Sent for approval.")
        elif request and request.state == 'blocked':
            message = _("It could not be sent: %s",
                        request.block_reason or '')
        else:
            message = self.block_note or ''
        return {'ok': True, 'id': self.id, 'reference': self.name,
                'state': self.state, 'message': message,
                'request_id': request.id if request else 0}

    def _waiting_for(self):
        self.ensure_one()
        request = self.sudo().approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        names = sorted({seat.acting_user_id.name or ''
                        for seat in step.seat_ids if seat.status == 'open'})
        return ', '.join(n for n in names if n)

    # ==================================================================
    # The adapter contract
    # ==================================================================
    def _headline(self):
        self.ensure_one()
        label = dict(REASON_KINDS).get(self.reason_kind) or _('Job change')
        return _("%(what)s · %(who)s", what=_(label),
                 who=self.employee_id.sudo().name or '')

    def _approval_validate(self):
        self.ensure_one()
        if self.state not in ('draft', 'returned'):
            raise UserError(_("This job change has already been sent in."))
        return True

    def _approval_context(self):
        # Read under sudo: the engine calls this as whoever decided the last
        # step, and a line manager holds no HR rights (ledger W2B-2).
        self.ensure_one()
        rec = self.sudo()
        company = rec.company_id or self.env.company
        emp = rec.employee_id
        makers = {rec.user_id.id} if rec.user_id else set()
        payload = {
            'employee': emp.id,
            'date': fields.Date.to_string(rec.effective_date),
            'employee_vals': rec._payload_vals(),
            'wage': float(rec.new_wage or 0.0) if rec.change_pay else 0.0,
            'lines': [(r.code, float(r.new_amount or 0.0))
                      for r in rec.line_ids],
            'kind': rec.reason_kind,
        }
        return {
            'company_id': company.id,
            'title': rec._headline(),
            'scope_keys': [''],
            'scope_label': company.name,
            'scope_date': fields.Date.to_string(fields.Date.context_today(rec)),
            'kind_key': rec.reason_kind or 'any',
            'facts': rec.facts(),
            'amount': float(rec.new_wage or 0.0) if rec.change_pay else 0.0,
            'currency_id': (rec.currency_id or company.currency_id).id,
            'maker_uids': sorted(m for m in makers if m),
            'submitter_uid': self.env.uid,
            'subject_uids': [emp.user_id.id] if emp.user_id else [],
            'source_revision': self._approval_revision_of(payload),
            'evidence': [{
                'key': 'reason_given', 'name': _('A reason was written down'),
                'ok': bool((rec.reason or '').strip()),
                'note': (rec.reason or '')[:240]}],
        }

    def _payload_vals(self):
        self.ensure_one()
        out = {}
        for mine, _theirs in EMPLOYEE_MAP:
            value = self[mine]
            out[mine] = value.id if isinstance(value, models.BaseModel) \
                else (value or '')
        return out

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': self._fact_specs(),
            'kinds': [{'key': k, 'label': _(v)} for k, v in REASON_KINDS],
            'evidence': [{'key': 'reason_given',
                          'label': _('A reason was written down')}],
            'scope_levels': [_('Whole company')],
            'manager_mode': True,
        }

    @api.model
    def _fact_specs(self):
        return {
            'kind': {'type': 'selection', 'label': _('What kind of change')},
            'changes_pay': {'type': 'bool', 'label': _('Changes pay')},
            'pay_rise_pct': {'type': 'percent', 'label': _('How big the rise is')},
            'above_guidance': {'type': 'bool',
                               'label': _('Bigger than the guidance allows')},
            'above_band': {'type': 'bool',
                           'label': _('Above the top of the band')},
            'changes_team': {'type': 'bool',
                             'label': _('Moves them to another team or manager')},
            'changes_scheme': {'type': 'bool',
                               'label': _('Moves them to another pay scheme')},
            'has_manager': {'type': 'bool',
                            'label': _('Their manager has a login')},
            'new_wage': {'type': 'decimal', 'label': _('New monthly pay')},
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_manager_uids(self):
        self.ensure_one()
        return self.sudo()._manager_user().ids

    def _approval_skip_manager_uids(self):
        self.ensure_one()
        manager = self.sudo().employee_id.parent_id.parent_id
        return manager.user_id.ids if manager and manager.user_id else []

    def _approval_card_count(self, request):
        self.ensure_one()
        return _(dict(REASON_KINDS).get(self.sudo().reason_kind) or '')

    def _rows(self, show_pay=True):
        """`[(label, now, new)]` — every value that moves, in words."""
        self.ensure_one()
        rec = self.sudo()
        before = rec.before()
        emp = rec.employee_id
        contract = rec.contract_id
        rows = []
        words = {
            'company_id': _('Company'), 'job_id': _('Job'),
            'job_title': _('Job title'), 'department_id': _('Team'),
            'parent_id': _('Manager'), 'work_location_id': _('Place of work'),
            'resource_calendar_id': _('Working hours'),
        }
        models_of = {
            'company_id': 'res.company', 'job_id': 'hr.job',
            'department_id': 'hr.department', 'parent_id': 'hr.employee',
            'work_location_id': 'hr.work.location',
            'resource_calendar_id': 'resource.calendar',
        }
        for mine, theirs in EMPLOYEE_MAP:
            new = rec[mine]
            if not new:
                continue
            if 'e.' + theirs in before:
                old_value = before['e.' + theirs]
            else:
                old = emp[theirs]
                old_value = old.id if isinstance(old, models.BaseModel) else old
            new_value = new.id if isinstance(new, models.BaseModel) else new
            if new_value == old_value and rec.state not in ('applied', 'undone'):
                continue
            if theirs in models_of:
                old_label = self._label(models_of[theirs], old_value)
                new_label = new.display_name
            else:
                old_label, new_label = old_value or '', new_value or ''
            if old_label == new_label:
                continue
            rows.append((words[theirs], old_label or '—', new_label or '—'))
        if rec.change_pay and show_pay:
            cur = rec.currency_id or (contract.company_id
                                      or emp.company_id).currency_id
            old_wage = before.get('c.wage', float(contract.wage or 0.0)
                                  if contract else 0.0)
            if rec.new_wage and float(rec.new_wage) != float(old_wage or 0.0):
                rows.append((_('Monthly pay'), self._money(old_wage, cur),
                             self._money(rec.new_wage, cur)))
            for line in rec.line_ids:
                old = before.get('l.' + (line.code or ''), line.old_amount)
                if abs(float(line.new_amount or 0.0) - float(old or 0.0)) \
                        < 1e-9:
                    continue
                rows.append((line.name or line.code, self._money(old, cur),
                             self._money(line.new_amount, cur)))
        elif rec.change_pay:
            rows.append((_('Pay'), '', _('Changes (shown to the pay team)')))
        return rows

    def _label(self, model, res_id):
        if not res_id or model not in self.env:
            return ''
        found = self.env[model].sudo().browse(int(res_id)).exists()
        return found.display_name if found else ''

    @api.model
    def _money(self, amount, currency):
        currency = currency or self.env.company.currency_id
        try:
            return self.env['pb.pay.bands']._money(float(amount or 0.0),
                                                   currency)
        except Exception:       # noqa: BLE001
            return '{:,.{d}f} {c}'.format(float(amount or 0.0),
                                          d=currency.decimal_places or 0,
                                          c=currency.name or '')

    def _approval_detail(self, request):
        self.ensure_one()
        rec = self.sudo()
        rows = [{'head': str(label)[:60], 'sub': '',
                 'cells': [str(old)[:60], str(new)[:60]], 'tone': 'on'}
                for label, old, new in rec._rows()[:40]]
        facts = rec.facts()
        chips = [{'label': _('Who'), 'value': rec.employee_id.name or ''},
                 {'label': _('Starts on'),
                  'value': self._day(rec.effective_date)},
                 {'label': _('What'),
                  'value': _(dict(REASON_KINDS).get(rec.reason_kind) or '')}]
        pct = (facts.get('pay_rise_pct') or {}).get('value') or 0.0
        if pct:
            chips.append({'label': _('Rise'), 'value': '{:+.1f}%'.format(pct)})
        if (facts.get('changes_scheme') or {}).get('value'):
            chips.append({'label': _('Pay scheme'), 'value': _('Changes')})
        note = rec.reason or ''
        if rec.effective_date and rec.effective_date < \
                rec._company_today():
            note = (note + '\n' if note else '') + _(
                "This change starts on a date in the past.")
        return {'title': _('What would change'),
                'columns': [_('Now'), _('New')], 'rows': rows,
                'chips': chips, 'note': note}

    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending', 'block_note': False})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected'})
        return True

    def _approval_withdraw(self, request, reason):
        self.ensure_one()
        if self.state in ('pending', 'scheduled'):
            self.sudo().write({'state': 'cancelled'})
        return True

    def _approval_apply(self, request):
        """Approved. Written now when the day has come, held otherwise."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state in ('applied', 'scheduled', 'undone'):
            return True
        if rec.state == 'cancelled':
            raise UserError(_("This job change was cancelled, so nothing was "
                              "written."))
        moved = rec._moved()
        if moved:
            note = rec._moved_sentence(moved)
            rec.write({'block_note': note})
            raise UserError(note)
        if rec.effective_date and rec.effective_date > rec._company_today():
            rec.write({'state': 'scheduled', 'block_note': False})
            return True
        rec._write_change(actor=self.env.user, by_job=False)
        return True

    # ==================================================================
    # Carrying it out
    # ==================================================================
    def _moved(self):
        """Values this change covers that somebody else moved since it was
        sent in."""
        self.ensure_one()
        before = self.before()
        if not before:
            return []
        now = self._snapshot()
        moved = []
        for key in sorted(self._covered_keys()):
            if key not in before:
                continue
            was, is_now = before.get(key), now.get(key)
            if isinstance(was, float) or isinstance(is_now, float):
                same = abs(float(was or 0.0) - float(is_now or 0.0)) < 1e-6
            else:
                same = (was or False) == (is_now or False)
            if not same:
                moved.append(key)
        return moved

    def _moved_sentence(self, moved):
        words = {'contract_id': _('the running contract'),
                 'e.job_id': _('job'), 'e.job_title': _('job title'),
                 'e.department_id': _('team'), 'e.parent_id': _('manager'),
                 'e.work_location_id': _('place of work'),
                 'e.resource_calendar_id': _('working hours'),
                 'e.company_id': _('company'), 'c.wage': _('monthly pay'),
                 'c.job_id': _('job on the contract'),
                 'c.department_id': _('team on the contract'),
                 'c.resource_calendar_id': _('working hours on the contract'),
                 'c.company_id': _('company on the contract')}
        names = [words.get(k) or k.split('.', 1)[-1] for k in moved[:6]]
        return _("Nothing was changed: somebody else changed %s since this "
                 "was sent in. Send it back and prepare it again against what "
                 "is there now.", ', '.join(names))

    @api.model
    def _template_for(self, code):
        """Get-or-create the pay-line catalogue row for one code — the same
        shape the contract drawer writes (`_cd_template_for_code`)."""
        Template = self.env['hr.contract.advantage.template'].sudo()
        found = Template.search([('code', '=', code)], limit=1)
        if found:
            return found
        vals = {'name': code, 'code': code, 'lower_bound': 0.0,
                'upper_bound': 0.0, 'default_value': 0.0}
        if 'value_type' in Template._fields:
            vals['value_type'] = 'amount'
        return Template.create(vals)

    def _wage_code(self, config_id):
        """The scheme input that reads the contract wage, if it has one."""
        self.ensure_one()
        if not config_id or 'hr.formula.config' not in self.env:
            return ''
        config = self.env['hr.formula.config'].sudo().browse(
            int(config_id)).exists()
        for rule in config.rule_ids if config else []:
            code = (rule.code or '').upper()
            if code in WAGE_CODES and rule.column_type == 'input':
                return rule.code
        return ''

    def _write_change(self, actor, by_job=False):
        """Write every value together, as `actor`. All or nothing."""
        self.ensure_one()
        rec = self.sudo()
        emp = rec.employee_id
        contract = rec._running_contract(emp)
        if rec.contract_id and contract != rec.contract_id:
            raise UserError(_("Nothing was changed: %s's running contract is "
                              "not the one this change was prepared on.",
                              emp.name))
        emp_vals = rec._employee_vals()
        contract_vals = rec._contract_vals(contract)
        line_plan = rec._line_plan(contract)
        effective = rec.effective_date or rec._company_today()
        scheme_now, _after = rec._scheme_now_and_after()
        Entry = self.env['biz.audit.entry'].sudo()
        self.env.cr.execute('SELECT COALESCE(MAX(id), 0) FROM biz_audit_entry')
        audit_floor = self.env.cr.fetchone()[0]
        me = self.env(user=actor.id, su=True)
        E = me['hr.employee'].with_context(tracking_disable=False)
        C = me['hr.contract'].with_context(pb_pay_no_rebuild=True)
        written = {'employee': {}, 'contract': {}, 'lines': [],
                   'old_employee': {}, 'old_contract': {}}
        with self.env.cr.savepoint():
            if emp_vals:
                employee = E.browse(emp.id)
                for key in emp_vals:
                    old = employee[key]
                    written['old_employee'][key] = old.id if isinstance(
                        old, models.BaseModel) else (old or False)
                # The job first, then its title (Odoo fills the title from
                # the job); the company before anything that belongs to it.
                ordered = [k for _m, k in EMPLOYEE_MAP if k in emp_vals]
                head = {k: emp_vals[k] for k in ordered if k != 'job_title'}
                if head:
                    employee.write(head)
                if 'job_title' in emp_vals:
                    employee.write({'job_title': emp_vals['job_title']})
                written['employee'] = emp_vals
            if contract_vals and contract:
                record = C.browse(contract.id)
                for key in contract_vals:
                    old = record[key]
                    written['old_contract'][key] = old.id if isinstance(
                        old, models.BaseModel) else (float(old or 0.0)
                                                     if key == 'wage'
                                                     else old or False)
                record.write(contract_vals)
                written['contract'] = contract_vals
            Advantage = me['hr.contract.advantage']
            Change = me['hr.contract.advantage.change']
            note = _("Change job %(ref)s, from %(day)s", ref=rec.name,
                     day=self._day(effective))
            for row in line_plan:
                template = row['line'].advantage_template_id if row['line'] \
                    else self._template_for(row['code'])
                if row['line']:
                    row['line'].sudo().write({'amount': row['new']})
                    line_id = row['line'].id
                else:
                    line_id = Advantage.create({
                        'contract_id': contract.id,
                        'advantage_template_id': template.id,
                        'amount': row['new']}).id
                Change.log(contract, template, row['old'], row['new'],
                           'manual', notes=note, user=actor,
                           effective_date=effective)
                written['lines'].append({'line_id': line_id,
                                         'code': row['code'],
                                         'old': row['old'], 'new': row['new'],
                                         'created': not row['line']})
            if 'wage' in contract_vals:
                old_wage = written['old_contract'].get('wage', 0.0)
                code = rec._wage_code(scheme_now.get('id'))
                if code:
                    # The scheme reads the wage through this input: a dated
                    # row is the one way the re-work and proration see it.
                    Change.log(contract, self._template_for(code), old_wage,
                               contract_vals['wage'], 'manual', notes=note,
                               user=actor, effective_date=effective)
                now = fields.Datetime.now()
                me['pb.pay.apply'].create({
                    'job_change_id': rec.id,
                    'employee_id': emp.id,
                    'contract_id': contract.id,
                    'company_id': (contract.company_id or emp.company_id).id,
                    'currency_id': (rec.currency_id
                                    or contract.currency_id).id,
                    'old_wage': old_wage,
                    'new_wage': contract_vals['wage'],
                    'effective_date': effective,
                    'applied_at': now,
                    'applied_by': actor.id,
                    'undo_until': now + timedelta(hours=UNDO_HOURS),
                    # The letter is this change's own (promotion / transfer),
                    # never the pay-review letter the Pay job would print.
                    'letter_state': 'none',
                    'note': rec.name,
                })
        now = fields.Datetime.now()
        rec.write({
            'state': 'applied',
            'applied_at': now,
            'applied_by': actor.id,
            'started_by_job': bool(by_job),
            'undo_until': now + timedelta(hours=UNDO_HOURS),
            'block_note': False,
            'start_fail_days': 0,
            'contract_id': contract.id or False,
            'written_json': json.dumps(written, default=str),
            'paid_months_json': json.dumps(
                rec._paid_months() if (contract_vals.get('wage')
                                       or line_plan) else [],
                default=str),
        })
        rec._trail(audit_floor, emp, contract)
        rec._make_letter()
        try:
            self.env['pb.pay.apply']._recompute_positions(
                contract.company_id or emp.company_id)
        except Exception:       # noqa: BLE001 — positions are a report
            _logger.info('job change: pay positions not rebuilt')
        rec.message_post(body=_("Done. %(who)s's change from %(day)s is in "
                                "place.", who=emp.name,
                                day=self._day(effective)))
        return True

    def _trail(self, floor, emp, contract):
        """One event on the person's trail: every line the write produced is
        folded into it (the timeline hides them and shows this one)."""
        self.ensure_one()
        Entry = self.env['biz.audit.entry'].sudo()
        versions = self.env['hr.version'].sudo().search(
            [('employee_id', '=', emp.id)]).ids \
            if 'hr.version' in self.env else []
        domain = [('id', '>', floor), '|', '|',
                  '&', ('model_name', '=', 'hr.employee'),
                  ('res_id', '=', emp.id),
                  '&', ('model_name', '=', 'hr.contract'),
                  ('res_id', '=', contract.id or 0),
                  '&', ('model_name', '=', 'hr.version'),
                  ('res_id', 'in', versions or [0])]
        ids = Entry.search(domain).ids
        summary = '; '.join('%s: %s → %s' % (label, old, new)
                            for label, old, new in self._rows(show_pay=False))
        try:
            with self.env.cr.savepoint():
                entry = Entry.create({
                    'model_name': 'hr.employee', 'res_id': emp.id,
                    'res_display': (emp.name or '')[:512],
                    'field_name': 'pb_job_change',
                    'field_label': _('Job change'),
                    'old_value': (self.name or '')[:256],
                    'new_value': summary[:256] or _('Pay changed'),
                    'company_id': (emp.company_id or self.env.company).id,
                })
                ids.append(entry.id)
        except Exception:       # noqa: BLE001 — a trail never undoes a write
            _logger.exception('job change: trail line failed for %s', self.name)
        self.write({'audit_ids_json': json.dumps(sorted(ids))})

    # --------------------------------------------------------------- letter
    def _letter_type(self):
        self.ensure_one()
        return {'promotion': LETTER_PROMOTION,
                'transfer': LETTER_TRANSFER}.get(self.reason_kind,
                                                  LETTER_JOB_CHANGE)

    @api.model
    def _letter_template(self, letter_type):
        if 'pb.letter.template' not in self.env:
            return None
        Template = self.env['pb.letter.template'].sudo()
        found = Template.search([('letter_type', '=', letter_type),
                                 ('active', '=', True)],
                                order='sequence, id', limit=1)
        if found:
            return found
        names = {LETTER_PROMOTION: _('Promotion letter'),
                 LETTER_TRANSFER: _('Transfer letter'),
                 LETTER_JOB_CHANGE: _('Job change letter')}
        opening = {
            LETTER_PROMOTION: '<p>We are pleased to confirm your promotion, '
                              'with effect from ${effective_date}.</p>',
            LETTER_TRANSFER: '<p>This letter confirms your transfer, with '
                             'effect from ${effective_date}.</p>',
            LETTER_JOB_CHANGE: '<p>This letter confirms the changes to your '
                               'employment, with effect from '
                               '${effective_date}.</p>',
        }[letter_type]
        body = ('<div><p>Dear ${employee_name},</p>' + opening +
                '<p>${changes}</p><p>${pay_line}</p><p>${reason}</p>'
                '<p>Everything else in your terms of employment is '
                'unchanged.</p><p>${company}</p><p>${date}</p></div>')
        category = self.env.ref('pb_employee_vault.cat_other',
                                raise_if_not_found=False)
        return Template.create({
            'name': names[letter_type], 'letter_type': letter_type,
            'subject': names[letter_type], 'sequence': 50, 'body_html': body,
            'company_id': False,
            'vault_category_id': category.id if category else False,
        })

    def _make_letter(self):
        """One letter, generated and filed. Never fatal."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                template = self._letter_template(self._letter_type())
                if not template:
                    return False
                rows = self._rows(show_pay=False)
                changes = '; '.join('%s: %s' % (label, new)
                                    for label, _old, new in rows)
                pay_line = ''
                if self.change_pay:
                    pay = [r for r in self._rows() if r not in rows]
                    pay_line = '; '.join('%s: %s → %s' % r for r in pay)
                letter = self.env['pb.hr.letter'].sudo().create({
                    'employee_id': self.employee_id.id,
                    'template_id': template.id,
                    'subject': template.subject or template.name,
                    'context_json': json.dumps({
                        'effective_date': self._day(self.effective_date),
                        'changes': changes, 'pay_line': pay_line,
                        'reason': self.reason or '',
                    }, default=str),
                    'company_id': (self.employee_id.company_id
                                   or self.env.company).id,
                })
                letter.action_generate()
                self.write({'letter_id': letter.id})
                return letter
        except Exception:       # noqa: BLE001 — the paperwork is not the change
            _logger.exception('job change: no letter for %s', self.name)
        return False

    # ==================================================================
    # The day comes: the hourly job and "Start now"
    # ==================================================================
    def _lock(self, wait=False):
        self.ensure_one()
        self.env.flush_all()
        query = ('SELECT id FROM pb_job_change WHERE id = %s FOR UPDATE '
                 + ('NOWAIT' if wait else 'SKIP LOCKED'))
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(query, [self.id])
                got = self.env.cr.fetchone()
        except LOCK_ERRORS:
            return False
        self.invalidate_recordset()
        return bool(got)

    def _start_user(self):
        self.ensure_one()
        if self.user_id and self.user_id.active:
            return self.user_id
        request = self.sudo().approval_request_id
        if request:
            for decision in self.env['biz.approval.decision'].sudo().search(
                    [('request_id', '=', request.id)], order='id desc'):
                if decision.create_uid and decision.create_uid.active:
                    return decision.create_uid
        return self.env.user

    def _send_back(self, note):
        self.ensure_one()
        self.sudo().write({'state': 'returned', 'block_note': note})
        user = self.user_id
        if not user or not user.active:
            return True
        todo = self.env.ref('mail.mail_activity_data_todo',
                            raise_if_not_found=False)
        try:
            with self.env.cr.savepoint():
                self.env['mail.activity'].sudo().with_context(
                    mail_activity_quick_update=True).create({
                        'res_model_id': self.env['ir.model']._get_id(
                            self._name),
                        'res_id': self.id,
                        'activity_type_id': todo.id if todo else False,
                        'summary': _("A job change was not made: %s",
                                     self.name),
                        'note': note,
                        'user_id': user.id,
                        'date_deadline': self._company_today(),
                    })
        except Exception:       # noqa: BLE001
            _logger.info('job change: no reminder for %s', self.name)
        return True

    def _start_scheduled(self, by_job=True):
        """`(outcome, sentence)`: started / busy / gone / returned / refused."""
        self.ensure_one()
        if not self._lock(wait=not by_job):
            return 'busy', _("This change is being written right now. Look "
                             "again in a minute.")
        rec = self.sudo()
        if rec.state != 'scheduled':
            return 'gone', _("This change is no longer waiting for its day.")
        if by_job and rec.effective_date and \
                rec.effective_date > rec._company_today():
            return 'gone', _("Its day has not come yet.")
        moved = rec._moved()
        if moved:
            note = rec._moved_sentence(moved)
            if by_job:
                rec._send_back(note)
                return 'returned', note
            return 'refused', note
        actor = rec._start_user() if by_job else self.env.user
        try:
            with self.env.cr.savepoint():
                rec._write_change(actor=actor, by_job=by_job)
        except UserError as error:
            self.env.invalidate_all()
            note = str(error.args[0] if error.args else error)
            if by_job:
                rec._send_back(note)
                return 'returned', note
            return 'refused', note
        return 'started', ''

    @api.model
    def _cron_start_due(self, limit=200):
        """The quiet hourly job: write every approved change whose day has
        come, one transaction each. Safe on an empty database (one search)."""
        testing = bool(odoo_module.current_test)
        todo = self.sudo().search([('state', '=', 'scheduled'),
                                   ('effective_date', '!=', False)],
                                  order='effective_date, id',
                                  limit=int(limit or 200))
        tally = {}
        for rec in todo:
            if rec.effective_date > rec._company_today():
                continue
            try:
                with self.env.cr.savepoint():
                    outcome, _sentence = rec._start_scheduled(by_job=True)
            except LOCK_ERRORS:
                self.env.invalidate_all()
                outcome = 'busy'
            except Exception:   # noqa: BLE001 — one never stops the rest
                self.env.invalidate_all()
                _logger.exception('job change: could not start %s', rec.name)
                rec._record_start_failure()
                outcome = 'failed'
            tally[outcome] = tally.get(outcome, 0) + 1
            if not testing:
                self.env.cr.commit()
        if tally:
            _logger.info('pb_job_change: scheduled changes %s', tally)
        return tally

    def _record_start_failure(self):
        self.ensure_one()
        rec = self.sudo()
        today = rec._company_today()
        days = rec.start_fail_days or 0
        if rec.start_last_fail != today:
            days += 1
        rec.write({'start_fail_days': days, 'start_last_fail': today,
                   'block_note': _("Could not be started on %s; it will be "
                                   "tried again.", self._day(today))})
        if days >= 3:
            rec._send_back(_("Could not be started on three different days, "
                             "so nothing was written. Prepare it again."))
        return days

    # ==================================================================
    # Cancel and take back
    # ==================================================================
    def _may_act(self):
        self.ensure_one()
        user = self.env.user
        return bool(self.user_id == user or self._may_prepare(user))

    def action_cancel(self):
        self.ensure_one()
        if not self._may_act():
            raise AccessError(_("Only the person who prepared it, HR or the "
                                "pay team can cancel a job change."))
        if self.state not in ('draft', 'pending', 'scheduled', 'returned'):
            raise UserError(_("Only a change that has not been written yet can "
                              "be cancelled."))
        request = self.sudo().approval_request_id
        if request and request.state in ('pending', 'blocked'):
            try:
                self.env['biz.approval.engine'].sudo().cancel(
                    request, _("Cancelled from the job change."))
            except Exception:   # noqa: BLE001 — the change still stops
                _logger.info('job change: request %s not withdrawn',
                             request.id)
        self.sudo().write({'state': 'cancelled', 'block_note': False})
        return True

    def action_undo(self):
        """Put every value back, within 24 hours, when nothing moved since."""
        self.ensure_one()
        if not self._may_act():
            raise AccessError(_("Only the person who prepared it, HR or the "
                                "pay team can take a job change back."))
        rec = self.sudo()
        if rec.state != 'applied':
            raise UserError(_("There is nothing here to take back."))
        if rec.undo_until and fields.Datetime.now() > rec.undo_until:
            raise UserError(_(
                "The time to take this back ran out on %s. Prepare another job "
                "change instead, which keeps a record of both.",
                format_date(self.env, rec.undo_until.date(),
                            date_format='d MMM y')))
        written = rec._json('written_json', {})
        emp = rec.employee_id
        contract = rec.contract_id
        # Nothing moved since it was written?
        for key, value in (written.get('employee') or {}).items():
            live = emp[key]
            live = live.id if isinstance(live, models.BaseModel) else live
            if (live or False) != (value or False):
                raise UserError(_("Somebody has changed %s's details since, so "
                                  "this cannot be taken back here.", emp.name))
        for key, value in (written.get('contract') or {}).items():
            live = contract[key] if contract else False
            live = live.id if isinstance(live, models.BaseModel) else live
            if key == 'wage':
                if abs(float(live or 0.0) - float(value or 0.0)) > 1e-6:
                    raise UserError(_("The pay on the contract has changed "
                                      "since, so this cannot be taken back "
                                      "here."))
            elif (live or False) != (value or False):
                raise UserError(_("The contract has changed since, so this "
                                  "cannot be taken back here."))
        actor = self.env.user
        me = self.env(user=actor.id, su=True)
        with self.env.cr.savepoint():
            old_emp = written.get('old_employee') or {}
            if old_emp:
                employee = me['hr.employee'].browse(emp.id)
                head = {k: v for k, v in old_emp.items() if k != 'job_title'}
                if head:
                    employee.write(head)
                if 'job_title' in old_emp:
                    employee.write({'job_title': old_emp['job_title']})
            old_contract = {k: v for k, v in (written.get('old_contract')
                                               or {}).items() if k != 'wage'}
            if old_contract and contract:
                me['hr.contract'].with_context(pb_pay_no_rebuild=True).browse(
                    contract.id).write(old_contract)
            rec.apply_ids.filtered(lambda a: a.state == 'applied')._restore()
            Change = me['hr.contract.advantage.change']
            Advantage = me['hr.contract.advantage']
            note = _("Taken back: change job %s", rec.name)
            effective = rec.effective_date or rec._company_today()
            for row in written.get('lines') or []:
                line = Advantage.browse(int(row.get('line_id') or 0)).exists()
                if not line:
                    continue
                template = line.advantage_template_id
                line.write({'amount': row.get('old') or 0.0})
                Change.log(contract, template, row.get('new') or 0.0,
                           row.get('old') or 0.0, 'manual', notes=note,
                           user=actor, effective_date=effective)
            if 'wage' in (written.get('contract') or {}):
                code = rec._wage_code(rec._scheme_now_and_after()[0].get('id'))
                if code:
                    Change.log(contract, self._template_for(code),
                               written['contract']['wage'],
                               (written.get('old_contract') or {}).get('wage',
                                                                       0.0),
                               'manual', notes=note, user=actor,
                               effective_date=effective)
        if rec.letter_id:
            try:
                rec.letter_id.message_post(body=_(
                    "This job change was taken back, so this letter no longer "
                    "describes what happened."))
                rec.letter_id.write({'state': 'draft'})
            except Exception:   # noqa: BLE001
                _logger.info('job change: letter not voided')
        rec.write({'state': 'undone', 'undone_at': fields.Datetime.now(),
                   'undone_by': actor.id, 'undo_until': False})
        rec.message_post(body=_("Taken back. The old details are in place "
                                "again."))
        return True

    # ==================================================================
    # The Past-month re-work door (ruling J2; C-6: deep link only)
    # ==================================================================
    @api.model
    def _retro_installed(self):
        return 'pb.retro.review' in self.env and 'pb.retro.board' in self.env

    def action_open_rework(self):
        """Open a NEW draft Past-month re-work for this person and the paid
        months, through the re-work's own door and gate. Writes nothing else."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'applied':
            raise UserError(_("This change has not been written yet."))
        if not self._retro_installed():
            raise UserError(_("Past-month re-work is not part of this "
                              "database. Tell the pay team: they can work out "
                              "any difference by hand on the next pay run."))
        months = rec.paid_months()
        if not months:
            raise UserError(_("No month already paid is affected."))
        if rec.rework_id and self.env['pb.retro.review'].sudo().browse(
                rec.rework_id).exists():
            return {'ok': True, 'review_id': rec.rework_id}
        by_scheme = {}
        for row in months:
            if row.get('config_id'):
                by_scheme.setdefault(row['config_id'], []).append(row['month'])
        if not by_scheme:
            raise UserError(_("The paid months have no pay scheme on them, so "
                              "they cannot be re-worked here."))
        config_id = sorted(by_scheme, key=lambda c: -len(by_scheme[c]))[0]
        picked = sorted(by_scheme[config_id])
        last = fields.Date.to_date(picked[-1])
        first = fields.Date.to_date(picked[0])
        if (last.year - first.year) * 12 + last.month - first.month >= 12:
            first = last - relativedelta(months=11)
        answer = self.env['pb.retro.board'].save_review({
            'config_id': config_id,
            'month_from': fields.Date.to_string(first),
            'month_to': fields.Date.to_string(last),
            'people': 'picked',
            'employee_ids': [rec.employee_id.id],
            'reason': _("Change job %(ref)s: %(who)s's change starts on "
                        "%(day)s, in a month already paid.",
                        ref=rec.name, who=rec.employee_id.name,
                        day=self._day(rec.effective_date)),
        })
        review_id = int((answer or {}).get('id') or 0)
        rec.write({'rework_id': review_id})
        return {'ok': True, 'review_id': review_id}

    # ==================================================================
    # Cross-step contract C-1
    # ==================================================================
    #: The `vals` keys `pb_start_for_employee` accepts (documented in the
    #: S8-B report). Anything else is ignored.
    START_KEYS = ('job_id', 'job_title', 'department_id', 'parent_id',
                  'work_location_id', 'resource_calendar_id', 'company_id',
                  'wage', 'lines', 'effective_date', 'reason', 'reason_kind',
                  'source', 'source_ref')

    @api.model
    def pb_start_for_employee(self, employee_id, vals=None):
        """C-1 (binding): the action that opens the guided Change job flow for
        one person, prefilled with `vals`. Creates nothing — the person
        reviews every value and sends it in from the screen."""
        try:
            emp_id = int(employee_id.id if isinstance(
                employee_id, models.BaseModel) else employee_id or 0)
        except (TypeError, ValueError):
            emp_id = 0
        emp = self.env['hr.employee'].sudo().browse(emp_id).exists()
        if not emp:
            raise UserError(_("That person is not on the system any more."))
        clean = {}
        for key, value in (vals or {}).items():
            if key not in self.START_KEYS or value in (None, False, ''):
                continue
            if key == 'lines':
                rows = []
                for row in value or []:
                    if isinstance(row, dict) and row.get('code'):
                        try:
                            rows.append({'code': str(row['code']),
                                         'amount': float(row.get('amount')
                                                         or 0.0)})
                        except (TypeError, ValueError):
                            continue
                if rows:
                    clean['lines'] = rows
            elif key in ('job_title', 'reason', 'source', 'source_ref',
                         'reason_kind'):
                clean[key] = str(value)[:2000]
            elif key == 'effective_date':
                clean[key] = fields.Date.to_string(fields.Date.to_date(value))
            elif key == 'wage':
                clean[key] = float(value)
            else:
                clean[key] = int(value.id if isinstance(
                    value, models.BaseModel) else value)
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_job_change',
            'name': _('Change job'),
            'target': 'current',
            'params': {'employee_id': emp.id, 'vals': clean},
        }

    # ==================================================================
    # The route
    # ==================================================================
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', ('hr.group_hr_manager',))
        Seed.fill_role_from_group(
            company, 'finance', ('om_hr_payroll.group_hr_payroll_manager',))
        return Seed.lay(
            company, JOBCHANGE_PROCESS_KEY, 'Job changes', _jobchange_route(),
            binding_note='The route every job change follows: their manager, '
                         'then HR, then Finance when the rise is above the '
                         'guidance.',
            model_name='pb.job.change',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when Change job was installed')


def _jobchange_route():
    """Owner ruling J1: their manager (when they have one with a login), then
    the HR lead, then the Finance approver only when the rise is above the
    guidance."""
    return route(
        manager_step(_('Their manager'), key='mgr',
                     condition={'fact': 'has_manager', 'op': 'eq',
                                'value': True}),
        role_step(_('HR lead'), 'hr_lead', key='hr'),
        role_step(_('Finance approver'), 'finance', key='fin',
                  condition={'fact': 'above_guidance', 'op': 'eq',
                             'value': True}),
    )


class PbJobChangeLine(models.Model):
    _name = 'pb.job.change.line'
    _description = 'Job change pay line'
    _order = 'sequence, id'

    change_id = fields.Many2one('pb.job.change', required=True,
                                ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(string='Pay item code', required=True)
    name = fields.Char(string='Pay item')
    old_amount = fields.Float(string='Now')
    new_amount = fields.Float(string='New')


class BizApprovalRequestSeatJobChange(models.Model):
    """A seat on a job change is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.job.change' or not request.res_id:
                continue
            record = self.env['pb.job.change'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyJobChangeSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.job.change']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('job change: %s has no route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.job.change']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('job change: %s has no route yet', company.name)
    _logger.info('pb_job_change: %s companies have a job change route', done)
    return done


def post_init_hook(env):
    seed_all(env)
