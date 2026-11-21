# -*- coding: utf-8 -*-
"""UPDATES P2d — one-off pay items for a pay month: the ONE store.

A bonus, a one-time deduction, an overtime amount: entered in People ›
Updates any day before the pay run exists, approved through the approval
engine exactly like a records change, read by every kind of pay run through
two resolver seams (`updates_payrun.py`), paid once, and released when the
payslip or the run that took it is cancelled or deleted.

The three stores that already exist (`hr.payroll.period.input`,
`pb.payroll.month.inputs`, `pb.incentive` / `pb.oneoff.feed`) are NOT read,
changed or migrated by this one (handover §3). Nothing here ever creates a
row in `hr.payroll.period.input`.

Key: one row per person × pay item (the rule code the engine uses) × pay
month (the 1st of the month of the payslip's END date). Life of a row:

    pending ──approved──▶ approved ──first payslip computes──▶ reserved
       │                     │  ▲                                 │
       │ cancelled /         │  └──── payslip cancelled / deleted ┘
       │ turned down /       │                                    │ payslip done
       ▼ sent back           ▼ a later sheet (replaced) / CLEAR   ▼
    cancelled · rejected · returned · replaced · cleared          paid

Approval: the named update's ONE `pb.records.apply` (flag `updates_oneoff`)
is what travels the engine — the same process key and routes as every
records change, so no company needs new set-up (handover §5.1, the smaller
of the two options). Its plan lists the one-off values so the approval
drawer shows them; `_approval_apply` approves the rows instead of writing a
record.

D11 (owner, 2026-11-11): when the pay data file carries a DIFFERENT amount
for the same person, item and month, the pay run stops and asks. The open
question is stored on the row (`clash_*`), bound to the run that met it, and
answered with `resolve_clash` — "Use the Updates amount" / "Use the file's
amount". Never silently one or the other, never the sum.
"""
import json
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

#: Rows a pay run may read, or has read (the "live" ones: at most one per key).
LIVE_STATES = ('approved', 'reserved', 'paid')
#: Payslip states that mean "this payslip has been paid".
DONE_SLIP_STATES = ('done', 'paid')
#: The no-file resolver reads these codes off the contract's wage
#: (`hr_payslip_formula._get_formula_input_values`): never a one-off.
WAGE_CODES = frozenset({'BASIC', 'WAGE', 'BASE'})
#: How a value from Updates says so in a payslip's sources. `src` stays
#: `employee_field` — the person's own approved record, not an import — and
#: `via` names WHICH record, exactly as the overtime / business-trip /
#: timesheet streams do.
UPDATES_VIA = 'updates_oneoff'
#: The pay data file's sides, as the resolver's provenance names them.
FILE_SOURCES = ('excel', 'feed', 'rule')


def _same_amount(left, right):
    try:
        return round(float(left or 0.0), 2) == round(float(right or 0.0), 2)
    except (TypeError, ValueError):
        return False


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def updates_entry(row, ignored=None):
    """The provenance entry of a value that came from Updates."""
    out = {'src': 'employee_field', 'key': 'updates:%s' % row.id,
           'via': UPDATES_VIA}
    if ignored:
        out['ignored'] = ignored
    return out


# The finer "why" words of other screens, taught the new one once at import
# (the Source Atlas and the Studio's journey buckets read `via`). Soft: a
# build without either module is unaffected.
try:  # pragma: no cover — import-time registration only
    from odoo.addons.pb_hr_payroll_formula.models import input_provenance as _ip
    if UPDATES_VIA not in _ip.VIAS:
        _ip.VIAS = tuple(_ip.VIAS) + (UPDATES_VIA,)
except Exception:  # noqa: BLE001
    pass
try:  # pragma: no cover
    from odoo.addons.pb_source_atlas.models import pb_source_atlas as _atlas
    _atlas.VIA_LABELS.setdefault(UPDATES_VIA, 'a one-off pay item entered in Updates')
except Exception:  # noqa: BLE001
    pass


class OneoffClash(UserError):
    """D11 — the pay data file and Updates disagree and nobody has chosen.

    Raised by the pay-file resolver only when a caller that computes a real
    payslip asked it to (context `pb_updates_token`); that caller records the
    question on the row and leaves the payslip uncomputed. Read-only callers
    (review screens) never see it."""

    def __init__(self, row, file_value, file_key, file_src, sentence):
        super().__init__(sentence)
        self.row_id = row.id
        self.file_value = file_value
        self.file_key = file_key
        self.file_src = file_src
        self.sentence = sentence


class PbUpdatesOneoff(models.Model):
    _name = 'pb.updates.oneoff'
    _description = 'One-off pay item for a pay month'
    _order = 'period_month desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  index=True, ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, readonly=True)
    code = fields.Char(string='Pay item code', required=True, index=True, readonly=True)
    label = fields.Char(string='Pay item', readonly=True)
    period_month = fields.Date(string='Pay month', required=True, index=True,
                               readonly=True, help="The 1st of the month it is paid in.")
    action = fields.Selection([('set', 'Pay this amount'), ('clear', 'Remove')],
                              string='What it does', default='set', required=True,
                              readonly=True)
    amount = fields.Float(string='Amount', required=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    net_role = fields.Selection([('earning', 'Adds to pay'),
                                 ('deduction', 'Takes from pay')],
                                string='Effect on pay', readonly=True)
    #: The pay scheme it was entered under (display, and the mid-month rule).
    config_id = fields.Many2one('hr.formula.config', string='Pay scheme',
                                ondelete='set null', readonly=True)
    config_name = fields.Char(string='Pay scheme name', readonly=True)
    batch_id = fields.Many2one('pb.updates.batch', string='Named update',
                               required=True, index=True, ondelete='cascade',
                               readonly=True)
    apply_id = fields.Many2one('pb.records.apply', string='Approval proposal',
                               index=True, ondelete='set null', readonly=True)
    state = fields.Selection([
        ('pending', 'Waiting for approval'),
        ('approved', 'Waiting for a pay run'),
        ('reserved', 'In a pay run'),
        ('paid', 'Paid'),
        ('returned', 'Sent back'),
        ('rejected', 'Turned down'),
        ('cancelled', 'Cancelled'),
        ('replaced', 'Replaced by a later update'),
        ('cleared', 'Removed'),
    ], string='Status', default='pending', required=True, index=True, readonly=True)
    reserved_slip_id = fields.Many2one('hr.payslip', string='In payslip',
                                       index=True, ondelete='set null', readonly=True)
    paid_slip_id = fields.Many2one('hr.payslip', string='Paid in payslip',
                                   index=True, ondelete='set null', readonly=True)
    replaces_id = fields.Many2one('pb.updates.oneoff', string='Replaces',
                                  ondelete='set null', readonly=True)
    #: D11 — the question a pay run asked, and its answer.
    clash_run_id = fields.Many2one('hr.payslip.run', string='Pay run that found two amounts',
                                   index=True, ondelete='set null', readonly=True)
    clash_batch_id = fields.Many2one('hr.payroll.import.batch',
                                     string='Pay data file that had another amount',
                                     ondelete='set null', readonly=True)
    clash_file_amount = fields.Float(string="Amount in the pay data file", readonly=True)
    clash_file_key = fields.Char(string='Column in the pay data file', readonly=True)
    clash_choice = fields.Selection([('updates', 'The Updates amount'),
                                     ('file', "The file's amount")],
                                    string='Chosen', readonly=True)
    clash_by = fields.Many2one('res.users', string='Chosen by', readonly=True)
    clash_at = fields.Datetime(string='Chosen at', readonly=True)
    #: What happened to it, line by line (who, when, why) — the row's own trail.
    note = fields.Text(string='History', readonly=True)

    _live_unique = models.UniqueIndex(
        "(employee_id, code, period_month) WHERE state IN ('approved', 'reserved', 'paid')",
        "This person already has this one-off pay item for that month.")
    _amount_positive = models.Constraint(
        'CHECK(amount > 0)', 'A one-off amount must be more than zero.')

    # =================================================================
    # Small helpers
    # =================================================================
    @api.model
    def _month_of(self, day):
        day = fields.Date.to_date(day) if day else None
        return day.replace(day=1) if day else None

    @api.model
    def _month_label(self, month):
        month = fields.Date.to_date(month) if month else None
        return format_date(self.env, month, date_format='MMMM y') if month else ''

    def _amount_label(self, amount=None):
        self.ensure_one()
        value = self.amount if amount is None else amount
        return self._money(value, self.currency_id or self.company_id.currency_id)

    @api.model
    def _money(self, value, currency=None):
        """An amount as a person reads it: grouped, in the scheme's money."""
        try:
            value = float(value or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        currency = currency or self.env.company.currency_id
        return formatLang(self.env, value, currency_obj=currency)

    def _log(self, text):
        stamp = fields.Datetime.now().strftime('%Y-%m-%d %H:%M')
        who = self.env.user.name or ''
        for row in self:
            line = '%s · %s · %s' % (stamp, who, text)
            row.sudo().write({'note': ((row.note + '\n') if row.note else '') + line})

    def _slip_label(self, slip=None):
        """The pay run a row is in, as a person reads it."""
        self.ensure_one()
        slip = slip or self.reserved_slip_id or self.paid_slip_id
        run = slip.payslip_run_id if slip else self.env['hr.payslip.run']
        return (run.name or slip.name or '') if slip else ''

    # =================================================================
    # Which pay items are one-off pay items (ledger U24)
    # =================================================================
    @api.model
    def _excluded_codes(self, config):
        """Codes of this scheme the pay run fills from somewhere else."""
        config = config.sudo()
        codes = set(WAGE_CODES)
        rules = config.rule_ids
        # A rule fed from a record by a field mapping is a lasting value.
        Mapping = self.env.get('hr.payslip.import.mapping')
        if Mapping is not None and rules:
            for mapping in Mapping.sudo().search([
                    ('salary_structure_id', '=', config.id),
                    ('component_id', 'in', rules.ids)]):
                if mapping.component_id.code:
                    codes.add(mapping.component_id.code)
        # The mid-month advance carried into the end-of-month run.
        Cycle = self.env.get('hr.payroll.cycle.component.mapping')
        if Cycle is not None:
            for mapping in Cycle.sudo().search([('end_cycle_config_id', '=', config.id)]):
                if mapping.end_component_id.code:
                    codes.add(mapping.end_component_id.code)
        # Recurring salary, as the monthly templates read it (their own
        # definition, so the two never disagree about what salary is).
        try:
            from odoo.addons.pb_payroll_templates.models.templates import salary_inputs
            codes |= {r.code for r in salary_inputs(config) if r.code}
        except Exception:  # noqa: BLE001 — templates absent on this build
            pass
        # The Awards board's own stream (pb.oneoff.feed) is not shared.
        Feed = self.env.get('pb.oneoff.feed')
        if Feed is not None:
            try:
                codes.add(Feed._incentive_code())
            except Exception:  # noqa: BLE001 — a setting that cannot be read
                codes.add('INCENTV')
        # A code kept as an ongoing pay item on contracts is a lasting value.
        candidate = [r.code for r in rules if r.code]
        if candidate:
            Template = self.env['hr.contract.advantage.template'].sudo()
            for tpl in Template.search_read([('code', 'in', candidate)], ['code']):
                codes.add(tpl['code'])
        return codes

    @api.model
    def _items_of(self, config):
        """`{CODE: {'rule', 'label', 'role'}}` — this scheme's one-off pay items.

        An input the pay run reads from a person's month (not a contract
        component or a text, a payroll column, money, an earning or a
        deduction, no record mapping, no application source, no settlement
        treatment), minus the codes the pay run fills from elsewhere."""
        if not config:
            return {}
        config = config.sudo()
        out = {}
        excluded = None
        for rule in config.rule_ids:
            code = (rule.code or '').strip()
            if not code or rule.column_type != 'input':
                continue
            if rule.is_contract_component or rule.is_text_component:
                continue
            if (rule.column_role or 'payroll') != 'payroll':
                continue
            if (rule.value_kind or 'money') != 'money':
                continue
            if rule.net_role not in ('earning', 'deduction'):
                continue
            if 'application_settlement_kind' in rule._fields \
                    and (rule.application_settlement_kind or 'none') != 'none':
                continue
            if 'application_source_key' in rule._fields \
                    and (rule.application_source_key or '').strip():
                continue
            if excluded is None:
                excluded = self._excluded_codes(config)
            if code in excluded:
                continue
            out[code] = {'rule': rule, 'label': rule.name or code, 'role': rule.net_role}
        return out

    # =================================================================
    # The one reader (handover §5.2)
    # =================================================================
    @api.model
    def _for_slip(self, employee, config, date_to, slip_id=None, run=None, batch=None):
        """`{CODE: row}` — the rows a payslip of this employee, scheme and end
        date reads.

        `approved` rows not taken by anybody; rows this payslip already holds
        (`reserved` / `paid` by `slip_id`); a row whose payslip vanished
        (`reserved` with no payslip) is free again. A row a pay run asked a
        question about (D11) belongs to that run until it is answered and
        recalculated. A mid-month scheme reads only rows entered for it."""
        if not employee or not config or not date_to:
            return {}
        month = self._month_of(date_to)
        rows = self.sudo().search([
            ('employee_id', '=', employee.id), ('period_month', '=', month),
            ('state', 'in', LIVE_STATES), ('action', '=', 'set')])
        if not rows:
            return {}
        items = self._items_of(config)
        if not items:
            return {}
        run = run or self.env['hr.payslip.run']
        out = {}
        for row in rows:
            if row.code not in items:
                continue
            if config.cycle_type == 'mid_cycle' and row.config_id != config:
                continue
            if row.clash_run_id or row.clash_batch_id:
                bound = (row.clash_run_id and run and row.clash_run_id == run) or \
                        (row.clash_batch_id and batch and row.clash_batch_id == batch)
                if not bound:
                    continue
            if row.state == 'approved':
                out[row.code] = row
            elif row.state == 'reserved':
                if not row.reserved_slip_id or (slip_id and row.reserved_slip_id.id == slip_id):
                    out[row.code] = row
            elif row.state == 'paid':
                if slip_id and row.paid_slip_id.id == slip_id:
                    out[row.code] = row
        return out

    # =================================================================
    # Paid once: reserve, pay, release (precedent: hr.payroll.period.input)
    # =================================================================
    @api.model
    def _sync_slip(self, slip, used):
        """After a payslip computed: hold what it used, free what it no longer
        uses. `used` is `{row id: 'updates' | 'agreed' | 'file'}` as the
        resolver filled it. Never two payslips for one row."""
        slip = slip.sudo()
        if not slip or not slip.id:
            return
        held = self.sudo().search(['|', ('reserved_slip_id', '=', slip.id),
                                   ('paid_slip_id', '=', slip.id)])
        if not used and not held:
            return
        done = slip.state in DONE_SLIP_STATES
        rows = self.sudo().browse(sorted(int(k) for k in (used or {}))).exists()
        for row in rows:
            verdict = used.get(row.id)
            other = row.reserved_slip_id or row.paid_slip_id
            if other and other != slip:
                raise UserError(_(
                    "%(item)s for %(month)s is already in pay run %(run)s, so it "
                    "is not paid again here.", item=row.label or row.code,
                    month=self._month_label(row.period_month), run=row._slip_label()))
            if verdict == 'file':
                if row.state != 'paid' or row.paid_slip_id != slip:
                    row.write({'state': 'paid', 'paid_slip_id': slip.id,
                               'reserved_slip_id': False})
                    row._log(_("Not paid: the pay data file's amount (%(file)s) was used "
                               "instead in pay run %(run)s.",
                               file=row._amount_label(row.clash_file_amount),
                               run=row._slip_label(slip)))
                continue
            if done:
                if row.state != 'paid' or row.paid_slip_id != slip:
                    row.write({'state': 'paid', 'paid_slip_id': slip.id,
                               'reserved_slip_id': False})
                    row._log(_("Paid in pay run %s.") % row._slip_label(slip))
            elif row.state != 'reserved' or row.reserved_slip_id != slip:
                row.write({'state': 'reserved', 'reserved_slip_id': slip.id})
                row._log(_("Taken into pay run %s.") % row._slip_label(slip))
        for row in held - rows:
            row._release(_("Payslip %s no longer uses it.") % (slip.name or ''))

    def _release(self, why):
        """Back to "Waiting for a pay run": the payslip or run that held it is
        gone, cancelled or no longer uses it. A question a pay run asked goes
        with that run."""
        for row in self.sudo():
            if row.state not in ('reserved', 'paid', 'approved'):
                continue
            if row.state == 'approved' and not (row.clash_run_id or row.clash_batch_id
                                                or row.clash_choice):
                continue
            row.write({'state': 'approved', 'reserved_slip_id': False,
                       'paid_slip_id': False, 'clash_run_id': False,
                       'clash_batch_id': False, 'clash_choice': False,
                       'clash_file_amount': 0.0, 'clash_file_key': False,
                       'clash_by': False, 'clash_at': False})
            row._log(_("Waiting for a pay run again: %s") % why)

    @api.model
    def _slips_done(self, slips):
        """Payslips marked done or paid: what they hold is paid."""
        for row in self.sudo().search([('reserved_slip_id', 'in', slips.ids)]):
            slip = row.reserved_slip_id
            row.write({'state': 'paid', 'paid_slip_id': slip.id,
                       'reserved_slip_id': False})
            row._log(_("Paid in pay run %s.") % row._slip_label(slip))

    @api.model
    def _slips_gone(self, slips, why):
        """Payslips cancelled or deleted: what they held waits again."""
        if not slips:
            return
        rows = self.sudo().search(['|', ('reserved_slip_id', 'in', slips.ids),
                                   ('paid_slip_id', 'in', slips.ids)])
        rows._release(why)

    @api.model
    def _runs_gone(self, runs, why):
        if not runs:
            return
        self._slips_gone(runs.mapped('slip_ids'), why)
        self.sudo().search([('clash_run_id', 'in', runs.ids)])._release(why)

    @api.model
    def _open_question_for(self, slips):
        """`{slip: [row]}` — payslips whose person has an unanswered D11
        question in that payslip's run."""
        out = {}
        runs = slips.mapped('payslip_run_id')
        if not runs:
            return out
        rows = self.sudo().search([('clash_run_id', 'in', runs.ids),
                                   ('clash_choice', '=', False),
                                   ('state', '=', 'approved')])
        for slip in slips:
            mine = rows.filtered(lambda r: r.clash_run_id == slip.payslip_run_id
                                 and r.employee_id == slip.employee_id)
            if mine:
                out[slip] = mine
        return out

    # =================================================================
    # D11 — the question and its answer
    # =================================================================
    def _clash_sentence(self, file_amount=None):
        self.ensure_one()
        return _("%(item)s for %(name)s: %(updates)s from Updates, %(file)s in the pay "
                 "data file. Choose which one to pay in this pay run.",
                 item=self.label or self.code, name=self.employee_id.name or '',
                 updates=self._amount_label(),
                 file=self._amount_label(self.clash_file_amount if file_amount is None
                                         else file_amount))

    @api.model
    def _open_clash(self, clash, run=None, batch=None):
        """Store the question a pay run met (outside any rolled-back step)."""
        row = self.sudo().browse(clash.row_id).exists()
        if not row:
            return row
        try:
            amount = float(clash.file_value or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        vals = {'clash_file_amount': amount, 'clash_file_key': clash.file_key or False,
                'clash_choice': False, 'clash_by': False, 'clash_at': False}
        if run:
            vals['clash_run_id'] = run.id
        if batch:
            vals['clash_batch_id'] = batch.id
        row.write(vals)
        row._log(_("Pay run %(run)s stopped: the pay data file says %(file)s.",
                   run=(run.name if run else '') or (batch.name if batch else ''),
                   file=row._amount_label(amount)))
        return row

    @api.model
    def _clash_rows(self, run=None, company_ids=None):
        domain = [('state', '=', 'approved'), ('clash_run_id', '!=', False)]
        if run:
            domain.append(('clash_run_id', '=', run.id))
        if company_ids:
            domain.append(('company_id', 'in', company_ids))
        return self.sudo().search(domain, order='id')

    def _clash_payload(self):
        out = []
        for row in self:
            out.append({
                'id': row.id, 'emp': row.employee_id.name or '',
                'emp_id': row.employee_id.id,
                'item': row.label or row.code,
                'month': self._month_label(row.period_month),
                'updates': row._amount_label(),
                'file': row._amount_label(row.clash_file_amount),
                'run': row.clash_run_id.name or '',
                'run_id': row.clash_run_id.id,
                'chosen': row.clash_choice or '',
                'sentence': row._clash_sentence(),
            })
        return out

    @api.model
    def _may_choose(self):
        """Choosing which amount a pay run pays is running payroll."""
        user = self.env.user
        if user._is_superuser() or user.has_group('base.group_system'):
            return True
        Wizard = self.env.get('pb.payrun.wizard')
        if Wizard is not None and hasattr(Wizard, '_may_run_payroll'):
            try:
                return bool(Wizard._may_run_payroll())
            except Exception:  # noqa: BLE001
                return False
        return user.has_group('pb_hr_payroll_base.group_payroll_base_officer')

    @api.model
    def resolve_clash(self, row_id=0, choice=''):
        """Answer the pay run's question, then let that run carry on.

        `choice` is `updates` or `file`. The choice is stored with who and
        when and the file's amount; the person's payslip in that run is then
        computed again from the pay data file with the choice applied. A
        "file" choice marks the row paid against that payslip, so it never
        comes back in a later month."""
        if choice not in ('updates', 'file'):
            return {'ok': False, 'msg': _("Pick one of the two amounts.")}
        if not self._may_choose():
            raise AccessError(_("Choosing which amount is paid needs the right to run "
                                "payroll."))
        try:
            row_id = int(row_id or 0)
        except (TypeError, ValueError):
            row_id = 0
        row = self.sudo().search([('id', '=', row_id),
                                  ('company_id', 'in', self.env.companies.ids)], limit=1)
        if not row or row.state != 'approved' or not row.clash_run_id:
            return {'ok': False, 'msg': _(
                "This choice has already been made, or the pay run that asked "
                "it is gone.")}
        run = row.clash_run_id
        if run.state in ('close', 'done', 'paid', 'cancel'):
            row._release(_("pay run %s is closed.") % (run.name or ''))
            return {'ok': False, 'msg': _(
                "Pay run %s is already finished, so the choice cannot be used "
                "there. The one-off waits for the next pay run of that month.")
                % (run.name or '')}
        row.write({'clash_choice': choice, 'clash_by': self.env.uid,
                   'clash_at': fields.Datetime.now()})
        row._log(_("Chosen for pay run %(run)s: %(what)s (Updates %(upd)s, file %(file)s).",
                   run=run.name or '',
                   what=_("the Updates amount") if choice == 'updates' else _("the file's amount"),
                   upd=row._amount_label(), file=row._amount_label(row.clash_file_amount)))
        slip = self._recompute_after_choice(row)
        state = row.state
        return {'ok': True, 'row_id': row.id, 'choice': choice, 'state': state,
                'slip_id': slip.id if slip else 0,
                'msg': _("%(item)s for %(name)s: %(amount)s is paid in pay run %(run)s.",
                         item=row.label or row.code, name=row.employee_id.name or '',
                         amount=row._amount_label() if choice == 'updates'
                         else row._amount_label(row.clash_file_amount),
                         run=run.name or '')}

    @api.model
    def _recompute_after_choice(self, row):
        """The person's payslip in the run that asked, computed again from the
        pay data file. The payslip the run made without the file (the
        compute step that met the question) becomes the file's payslip."""
        run = row.clash_run_id.sudo()
        employee = row.employee_id
        Slip = self.env['hr.payslip'].sudo()
        Line = self.env['hr.payroll.import.line'].sudo()
        batches = (row.clash_batch_id | self.env['hr.payroll.import.batch'].sudo().search(
            [('payslip_run_id', '=', run.id)])).sudo()
        line = Line.search([('batch_id', 'in', batches.ids),
                            ('employee_id', '=', employee.id)], order='id desc', limit=1)
        slip = Slip.search([('payslip_run_id', '=', run.id),
                            ('employee_id', '=', employee.id),
                            ('state', 'not in', ('cancel',) + DONE_SLIP_STATES)],
                           order='id desc', limit=1)
        if line and slip and line.payslip_id != slip:
            line.write({'payslip_id': slip.id, 'state': 'processed'})
        if slip:
            slip.with_env(self.env).action_recompute_formula_lines()
            return slip
        if line:
            batch = line.batch_id
            contract = batch._get_latest_contract(employee) if hasattr(batch, '_get_latest_contract') \
                else employee.contract_id
            slip = batch._create_payslip(employee, contract, line)
            if slip:
                slip.write({'payslip_run_id': run.id})
                line.write({'payslip_id': slip.id, 'state': 'processed'})
            return slip
        return Slip


class PbUpdatesBatchOneoff(models.Model):
    _inherit = 'pb.updates.batch'

    kind = fields.Selection([('lasting', 'Lasting changes'),
                             ('oneoff', 'One-off pay items')],
                            string='Kind of update', default='lasting', required=True)
    period_month = fields.Date(string='Pay month')
    oneoff_ids = fields.One2many('pb.updates.oneoff', 'batch_id', string='One-off pay items')


class PbRecordsApplyOneoff(models.Model):
    """The named update's ONE approval proposal, when it carries one-off pay
    items. Same process key, same routes, same inbox as every records change;
    approving it approves the rows instead of writing a record."""
    _inherit = 'pb.records.apply'

    updates_oneoff = fields.Boolean(string='One-off pay items', readonly=True, copy=False)
    oneoff_ids = fields.One2many('pb.updates.oneoff', 'apply_id', string='One-off pay items')

    def _headline(self):
        self.ensure_one()
        if not self.updates_oneoff:
            return super()._headline()
        rows = self.sudo().oneoff_ids
        month = rows[:1].period_month
        n = len(rows)
        return _("One-off pay items for %(month)s · %(amounts)s", month=self.env[
            'pb.updates.oneoff']._month_label(month),
            amounts=_("1 amount") if n == 1 else _("%s amounts") % n)

    def _approval_detail(self, request):
        detail = super()._approval_detail(request)
        if self.updates_oneoff and detail:
            detail['title'] = _('One-off pay items')
            detail['columns'] = [_('Now'), _('In this update')]
        return detail

    def _approval_apply(self, request):
        self.ensure_one()
        if not self.updates_oneoff:
            return super()._approval_apply(request)
        if self.applied:
            return True
        if self.state == 'cancelled' or self.undone:
            raise UserError(_("This change was cancelled, so nothing was written."))
        rows = self.sudo().oneoff_ids.filtered(lambda r: r.state == 'pending')
        done, people = rows._approve()
        self.sudo().write({
            'applied': True, 'applied_at': fields.Datetime.now(), 'state': 'applied',
            'count_values': done, 'count_people': people, 'block_note': False,
        })
        return True

    def write(self, vals):
        result = super().write(vals)
        state = vals.get('state')
        if state in ('cancelled', 'rejected', 'returned') and 'oneoff_ids' in self._fields:
            for rec in self.filtered('updates_oneoff'):
                rows = rec.sudo().oneoff_ids.filtered(lambda r: r.state == 'pending')
                if rows:
                    rows.write({'state': state})
                    rows._log({'cancelled': _("Cancelled before it was approved."),
                               'rejected': _("Turned down."),
                               'returned': _("Sent back.")}[state])
        return result


class PbUpdatesOneoffApprove(models.Model):
    _inherit = 'pb.updates.oneoff'

    def _approve(self):
        """`(values, people)` — pending rows become the month's truth.

        A later sheet REPLACES a row still waiting for a pay run (the old one
        is kept as "Replaced"); CLEAR removes it. A row a pay run has already
        taken is never changed: the new value is cancelled with the reason."""
        done, people = 0, set()
        for row in self.sudo().sorted('id'):
            live = self.sudo().search([
                ('employee_id', '=', row.employee_id.id), ('code', '=', row.code),
                ('period_month', '=', row.period_month), ('state', 'in', LIVE_STATES),
                ('id', '!=', row.id)], limit=1)
            if live and (live.state != 'approved' or live.clash_run_id):
                row.write({'state': 'cancelled'})
                row._log(_("Not used: %(item)s for %(month)s is already in pay run "
                           "%(run)s. Change it there.", item=row.label or row.code,
                           month=self._month_label(row.period_month),
                           run=live._slip_label() or (live.clash_run_id.name or '')))
                continue
            if live:
                if row.action == 'clear':
                    live.write({'state': 'cancelled'})
                    live._log(_("Taken back by “%s”.") % (row.batch_id.name or ''))
                else:
                    live.write({'state': 'replaced'})
                    live._log(_("Replaced by “%s”.") % (row.batch_id.name or ''))
                    row.write({'replaces_id': live.id})
                live.flush_recordset(['state'])
            if row.action == 'clear':
                row.write({'state': 'cleared'})
                row._log(_("Removed the amount waiting for this month."))
            else:
                row.write({'state': 'approved'})
                row._log(_("Approved. Waits for the %s pay run.")
                         % self._month_label(row.period_month))
            done += 1
            people.add(row.employee_id.id)
        return done, len(people)

    def _plan_row(self):
        """One row of the approval proposal's plan (the drawer's table)."""
        self.ensure_one()
        old = self.replaces_id
        return {
            'emp_id': self.employee_id.id, 'emp_name': self.employee_id.name or '',
            'field_id': 'o:%s' % self.code,
            'field_label': '%s · %s' % (self.label or self.code,
                                        self._month_label(self.period_month)),
            'old_label': old._amount_label() if old else '',
            'new_label': (_("Removed") if self.action == 'clear' else self._amount_label()),
        }


class HrPayslipOneoffHooks(models.Model):
    """Paid once: a payslip that is done pays what it holds; one cancelled or
    deleted lets it go (clone of `hr.payroll.period.input`'s hooks). A
    payslip whose run still has an unanswered D11 question for its person
    cannot be finished."""
    _inherit = 'hr.payslip'

    def write(self, vals):
        state = vals.get('state')
        Oneoff = self.env['pb.updates.oneoff'].sudo()
        if state in DONE_SLIP_STATES:
            asked = Oneoff._open_question_for(self)
            if asked:
                slip, rows = next(iter(asked.items()))
                raise UserError(_(
                    "%(sentence)s Until then this payslip cannot be finished.",
                    sentence=rows[:1]._clash_sentence()))
        if state == 'cancel':
            Oneoff._slips_gone(self, _("payslip cancelled."))
        result = super().write(vals)
        if state in DONE_SLIP_STATES:
            Oneoff._slips_done(self)
        return result

    def unlink(self):
        self.env['pb.updates.oneoff'].sudo()._slips_gone(self, _("payslip deleted."))
        return super().unlink()


class HrPayslipRunOneoffHooks(models.Model):
    _inherit = 'hr.payslip.run'

    def unlink(self):
        self.env['pb.updates.oneoff'].sudo()._runs_gone(self, _("pay run deleted."))
        return super().unlink()


def json_dumps(value):
    return json.dumps(value, default=str)


def month_options(env, today, back=2, ahead=12):
    """The pay months a sheet can be for: 2 back to 12 ahead, this month first
    in the list's middle (handover §5.4)."""
    first = today.replace(day=1)
    out = []
    for offset in range(-back, ahead + 1):
        month = first + relativedelta(months=offset)
        out.append({'value': fields.Date.to_string(month),
                    'label': format_date(env, month, date_format='MMMM y'),
                    'current': offset == 0})
    return out
