# -*- coding: utf-8 -*-
"""WDGAP W2-D2 — pay a past-month difference as back-pay lines in this
month's pay run.

OWNER RULING R1 (2026-11-15). A worked-out re-work (`pb.retro.review`) shows,
per person, per past month, per pay item: was / would be / difference. That
difference is PAID IN THE NEXT REGULAR PAY RUN as its own lines, carrying the
exact tax and insurance worked out for the past months — never re-taxed by
this month's formulas. Past months stay closed.

THE LIFE OF IT
  worked out → "Pay the difference in the next pay run" (pre-check per person,
  `pb.retro.person`) → waiting for approval (process `backpay`, one step: Head
  of pay) → approved: one ENTRY per person × pay item × past month
  (`pb.retro.backpay`), made from the STORED result lines, never worked out
  again → the next regular run of the same scheme takes every open entry of
  its people → paid when that payslip is finished → the re-work closes itself
  when everything is paid.

THE SEAM (the smallest one there is). The engine has exactly two producers of
payslip lines from formulas, and both rebuild ALL lines on every compute:
  * `hr.payslip._create_payslip_lines_from_formulas` (compute, recompute
    without a file, application-data mode, the demo division path);
  * `hr.payroll.import.batch._compute_and_create_payslip_lines` (a run with a
    pay data file, its "recalculate").
`pb_retro` overrides both — super() first, then `_pb_backpay_apply(fresh=True)`
appends the back-pay lines. Nothing is fed into the formulas, so this month's
formulas neither see the amounts nor tax them again, and a recompute replaces
the lines (never doubles them) because the producer has just deleted every
line. No line of `pb_hr_payroll_formula` was edited.

HOW A LINE IS TYPED. One line per pay item with a difference ("Back pay ·
Income tax · Aug–Oct 2026", months collapsed per item), with the SAME code,
category, pay role and "included in another total" flag as the item's line on
the past payslip — so year-to-date readers that sum a code, fund payments
that read a code, and every band reader count it as that item. The ONE
exception is the take-home item: its difference is added to this payslip's
own take-home line (`hr.payslip.pb_backpay_net` says how much), because every
take-home reader reads the ONE net line (`pb_net_line`) and a second one would
never be read.

MONEY TAKEN OFF IS TAKEN OFF (band readers). A deduction that goes DOWN (a
person who owes money: less insurance, less tax) is a negative difference in
magnitude, which the readers' `abs()` per line cannot express. So each line
also carries `pb_backpay_band_amount` (|would be| − |was|, summed) and the
band readers are extended here, for payslips that hold back pay only:
`hr.payslip.line.pb_pay_totals` (ORM), `hr.payslip.run._pb_slip_totals`
(SQL twin) and `pb.fund.payment._pb_read` (fund payments). A payslip without
back pay goes through the untouched code.

PAID ONCE (the loans' reservation pattern). An entry is `open` until a payslip
takes it (`reserved`, linked to that payslip), `paid` when that payslip is
finished, back to `reserved` when it is set back, back to `open` when the
payslip is deleted or cancelled or a recompute no longer takes it. Rows are
locked (`FOR UPDATE`) while a payslip takes them, so two pay runs never take
the same entry.

NEVER BELOW ZERO TAKE-HOME. Months are taken whole (a month's earning never
without its tax): every month that raises take-home first, then the months
that lower it, oldest first, while take-home stays at or above zero. The first
month that does not fit, and every later one, wait for the next regular run.
One pass, no loop.
"""
import json
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import format_date

from odoo.addons.biz_approval_workflow.models.chain_shim import role_step, route

_logger = logging.getLogger(__name__)

BACKPAY_PROCESS_KEY = 'backpay'
WORKFLOW_NAME = 'Back pay for past months'
ROLES = ('pay_head',)
PAY_HEAD_GROUPS = ('pb_hr_payroll_base.group_payroll_base_manager',)
#: Context key the module's own writes carry; nothing else may write an entry.
TOKEN = 'pb_retro_backpay_write'
DONE_STATES = ('done', 'paid')
#: Pay states in which the re-work itself is frozen.
LOCKED_PAY = ('waiting', 'approved', 'partly', 'paid')
#: The sequence the back-pay lines start at: after every pay item.
LINE_SEQUENCE = 9000

PAY_STATES = [
    ('waiting', 'Waiting for approval'),
    ('approved', 'Approved'),
    ('partly', 'Partly paid'),
    ('paid', 'Paid'),
    ('cancelled', 'Payment cancelled'),
]
ENTRY_STATES = [
    ('open', 'Waiting for a pay run'),
    ('reserved', 'In a pay run'),
    ('paid', 'Paid'),
    ('cancelled', 'Cancelled'),
]
PERSON_STATUS = [
    ('payable', 'Can be paid'),
    ('not_payable', 'Not paid automatically'),
    ('nothing', 'Nothing to pay'),
]
PERSON_WHY = [
    ('drift', 'Cannot be compared exactly'),
    ('error', 'Could not be worked out'),
    ('left', 'Has left'),
    ('moved', 'Moved to another pay scheme'),
    ('currency', 'Paid in another currency now'),
    ('no_net', 'No take-home line'),
    ('zero', 'No difference'),
    ('already', 'Already paid by another re-work'),
]
#: Retro line band -> does its size count, not its sign?
MAGNITUDE_BANDS = ('deduction', 'employer')


def _month_end(day):
    return day + relativedelta(months=1, days=-1)


def months_text(env, months):
    """'Aug–Oct 2026', 'Nov 2025–Jan 2026', 'Oct 2026', 'Aug, Oct 2026'."""
    days = sorted({fields.Date.to_date(m).replace(day=1) for m in months if m})
    if not days:
        return ''

    def mon(d):
        return format_date(env, d, date_format='MMM')

    def full(d):
        return format_date(env, d, date_format='MMM y')

    if len(days) == 1:
        return full(days[0])
    contiguous = all(days[i] + relativedelta(months=1) == days[i + 1]
                     for i in range(len(days) - 1))
    if contiguous:
        if days[0].year == days[-1].year:
            return '%s–%s' % (mon(days[0]), full(days[-1]))
        return '%s–%s' % (full(days[0]), full(days[-1]))
    if len({d.year for d in days}) == 1:
        return '%s %s' % (', '.join(mon(d) for d in days), days[0].year)
    return ', '.join(full(d) for d in days)


# =====================================================================
# One person of a re-work sent for payment — the pre-check
# =====================================================================
class PbRetroPerson(models.Model):
    _name = 'pb.retro.person'
    _description = 'Past-month re-work: one person sent for payment'
    _order = 'review_id, employee_name, id'

    review_id = fields.Many2one('pb.retro.review', required=True, ondelete='cascade',
                                index=True)
    company_id = fields.Many2one(related='review_id.company_id', store=True, index=True)
    employee_id = fields.Many2one('hr.employee', ondelete='set null', index=True)
    employee_name = fields.Char()
    currency_id = fields.Many2one('res.currency')
    status = fields.Selection(PERSON_STATUS, required=True, index=True)
    why = fields.Selection(PERSON_WHY)
    net = fields.Float(string='Take-home difference', digits=(16, 4))
    months_label = fields.Char()


# =====================================================================
# One back-pay entry: one person × one pay item × one past month
# =====================================================================
class PbRetroBackpay(models.Model):
    _name = 'pb.retro.backpay'
    _description = 'Back pay for a past month'
    _order = 'review_id, employee_id, month, sequence, id'

    review_id = fields.Many2one('pb.retro.review', required=True, ondelete='restrict',
                                index=True)
    person_id = fields.Many2one('pb.retro.person', ondelete='set null')
    company_id = fields.Many2one('res.company', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='restrict',
                                  index=True)
    config_id = fields.Many2one('hr.formula.config', required=True, ondelete='restrict',
                                index=True)
    currency_id = fields.Many2one('res.currency', required=True)
    month = fields.Date(string='Past month', required=True)
    source_payslip_id = fields.Many2one('hr.payslip', string='Past payslip',
                                        ondelete='set null')
    code = fields.Char(required=True)
    name = fields.Char(string='Pay item')
    sequence = fields.Integer()
    band = fields.Char(string='Kind of line')
    counts = fields.Boolean(string='Counted in totals')
    is_net = fields.Boolean(string='Take-home')
    amount = fields.Float(string='Difference', digits=(16, 4))
    band_amount = fields.Float(string='Difference counted in its total', digits=(16, 4))
    # the typing of the item's line on the past payslip
    category_id = fields.Many2one('hr.salary.rule.category', ondelete='set null')
    salary_rule_id = fields.Many2one('hr.salary.rule', ondelete='set null')
    pay_role = fields.Char()
    component_detail = fields.Boolean()
    component_type = fields.Char()
    report_visible = fields.Boolean()
    state = fields.Selection(ENTRY_STATES, required=True, default='open', index=True)
    payslip_id = fields.Many2one('hr.payslip', string='Payslip that took it',
                                 ondelete='set null', index=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run that took it',
                             ondelete='set null')
    paid_on = fields.Date()
    waited = fields.Boolean(string='Waited for a later pay run',
                            help='A pay run did not take it so take-home would not go '
                                 'below zero.')
    cancel_reason = fields.Char()
    cancelled_by = fields.Many2one('res.users')

    # ------------------------------------------------------------ R2/R6 guard
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(TOKEN):
            raise UserError(_("Back pay is made from an approved re-work, never typed."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(TOKEN):
            raise UserError(_("Back pay changes only through its pay run or its re-work."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Back pay is never deleted. Cancel it from its re-work, with a "
                          "reason."))

    def _w(self):
        return self.sudo().with_context(**{TOKEN: True})


# =====================================================================
# The re-work: send for payment, the approval adapter, undo
# =====================================================================
class PbRetroReviewPay(models.Model):
    _name = 'pb.retro.review'
    _inherit = ['pb.retro.review', 'biz.approval.adapter.mixin', 'pb.money.approval.mixin']

    _approval_process_key = BACKPAY_PROCESS_KEY

    pay_state = fields.Selection(PAY_STATES, string='Payment', readonly=True, copy=False,
                                 index=True)
    pay_sent_on = fields.Datetime(readonly=True, copy=False)
    pay_sent_by = fields.Many2one('res.users', readonly=True, copy=False)
    pay_approved_on = fields.Datetime(readonly=True, copy=False)
    pay_cancel_reason = fields.Char(readonly=True, copy=False)
    person_ids = fields.One2many('pb.retro.person', 'review_id', string='People sent for payment')
    backpay_ids = fields.One2many('pb.retro.backpay', 'review_id', string='Back pay')
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_retro_review_seat_rel', 'review_id', 'user_id',
        string='Asked to decide', copy=False,
        help='Technical: the people a published route asked to decide the payment. '
             'It lets them read this re-work, nothing more.')

    # ------------------------------------------------------------ the lock
    def _pb_pay_lock(self):
        for rec in self:
            if rec.pay_state in LOCKED_PAY:
                raise UserError(_(
                    "This re-work has been sent for payment, so it cannot be changed or "
                    "worked out again. Cancel the payment first, or start a new re-work."))

    def write(self, vals):
        shape = {'config_id', 'month_from', 'month_to', 'people', 'employee_ids',
                 'whatif_ids', 'excluded_change_ids', 'reason'}
        if shape & set(vals) and not self.env.context.get('pb_retro_internal'):
            self._pb_pay_lock()
        return super().write(vals)

    def pb_work_start(self):
        self._pb_pay_lock()
        return super().pb_work_start()

    def pb_work_chunk(self, slip_ids):
        self._pb_pay_lock()
        return super().pb_work_chunk(slip_ids)

    def action_back_to_draft(self):
        self._pb_pay_lock()
        return super().action_back_to_draft()

    def action_cancel(self):
        self._pb_pay_lock()
        return super().action_cancel()

    def action_close(self):
        for rec in self:
            if rec.pay_state in ('waiting', 'approved', 'partly'):
                raise UserError(_("This re-work's back pay is not paid yet, so it cannot "
                                  "be closed."))
        return super().action_close()

    def unlink(self):
        for rec in self:
            if rec.sudo().backpay_ids or rec.pay_state:
                raise UserError(_("A re-work sent for payment stays as a record."))
        return super().unlink()

    # ------------------------------------------------------------ net item
    def _pb_net_code(self):
        """The code of the scheme's take-home item — the ONE net line, read
        the way `pb_net_line` reads it (pay role first)."""
        self.ensure_one()
        rules = self.config_id.sudo().rule_ids.filtered(
            lambda r: r.code and r.appears_on_payslip).sorted(lambda r: (r.sequence, r.id))
        net = rules.filtered(lambda r: r.net_role == 'net')
        if net:
            return net[0].code
        if any(r.net_role for r in rules):
            return False
        by_code = rules.filtered(lambda r: (r.code or '').upper() == 'NET')
        if by_code:
            return by_code[0].code
        by_cat = rules.filtered(lambda r: r.category_id and
                                (r.category_id.code or '').upper() == 'NET')
        return by_cat[0].code if by_cat else False

    def _pb_scheme_currency(self):
        self.ensure_one()
        cfg = self.config_id.sudo()
        return cfg.currency_id or cfg.company_id.currency_id or self.currency_id

    # ------------------------------------------------------------ pre-check
    def _pb_pay_check(self):
        """[{employee, name, status, why, net, months}] — per person: can the
        difference be paid automatically, and if not, why (plain reasons)."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        net_code = self._pb_net_code()
        currency_now = self._pb_scheme_currency()
        by_emp = {}
        for row in self.slip_ids.filtered(lambda s: s.status != 'skipped'):
            by_emp.setdefault(row.employee_id.id or 0, []).append(row)
        Map = self.env.get('pb.scheme.map')
        # payslips another live re-work already pays back pay for: their
        # difference was measured without that back pay, so it is never paid
        # automatically a second time (one-off in Updates instead)
        taken = set(self.env['pb.retro.backpay'].sudo().search([
            ('source_payslip_id', 'in', self.slip_ids.mapped('payslip_id').ids),
            ('state', '!=', 'cancelled'), ('review_id', '!=', self.id)]
        ).mapped('source_payslip_id').ids)
        out = []
        for emp_id, rows in by_emp.items():
            emp = self.env['hr.employee'].sudo().with_context(active_test=False).browse(emp_id)
            months = [r.month for r in rows if r.line_ids]
            entry = {'employee': emp, 'name': rows[0].employee_name or emp.name or '',
                     'net': sum(r.diff_net or 0.0 for r in rows),
                     'months': months_text(self.env, months), 'status': 'payable',
                     'why': False}
            has_lines = any(r.line_ids for r in rows)
            if any(r.status == 'drift' for r in rows):
                entry.update(status='not_payable', why='drift')
            elif any(r.status == 'error' for r in rows):
                entry.update(status='not_payable', why='error')
            elif not has_lines:
                entry.update(status='nothing', why='zero')
            elif any(r.payslip_id.id in taken for r in rows if r.line_ids):
                entry.update(status='not_payable', why='already')
            elif not emp or not emp.active or (
                    'departure_date' in emp._fields and emp.departure_date
                    and emp.departure_date <= today):
                entry.update(status='not_payable', why='left')
            elif currency_now != self.currency_id:
                entry.update(status='not_payable', why='currency')
            elif not net_code:
                entry.update(status='not_payable', why='no_net')
            else:
                other = 0
                if Map is not None:
                    try:
                        answer = Map.sudo().resolve(emp, self.config_id.sudo().cycle_type
                                                    or 'any', today) or {}
                        other = answer.get('config_id') or 0
                    except Exception:       # noqa: BLE001 — a resolver never stops this
                        other = 0
                if other and other != self.config_id.id:
                    entry.update(status='not_payable', why='moved')
                elif not other:
                    last = self.env['hr.payslip'].sudo().search(
                        [('employee_id', '=', emp.id), ('state', '!=', 'cancel'),
                         ('formula_config_id', '!=', False)],
                        order='date_to desc, id desc', limit=1)
                    if last and last.formula_config_id != self.config_id:
                        entry.update(status='not_payable', why='moved')
            out.append(entry)
        out.sort(key=lambda e: ((e['name'] or '').lower(), e['employee'].id))
        return out

    def _pb_write_people(self, checks):
        self.ensure_one()
        People = self.env['pb.retro.person'].sudo()
        self.sudo().person_ids.unlink()
        return People.create([{
            'review_id': self.id, 'employee_id': c['employee'].id or False,
            'employee_name': c['name'], 'currency_id': self.currency_id.id,
            'status': c['status'], 'why': c['why'], 'net': c['net'],
            'months_label': c['months'],
        } for c in checks])

    # ------------------------------------------------------------ send
    def action_send_for_payment(self):
        """"Pay the difference in the next pay run": the pre-check per person,
        then the approval route (Head of pay)."""
        self.ensure_one()
        self._pb_require()
        self.require_pay(_('sending back pay for approval'))
        if self.state != 'done':
            raise UserError(_("Only a worked-out re-work can be sent for payment."))
        if self.pay_state in LOCKED_PAY:
            raise UserError(_("This re-work has already been sent for payment."))
        if self.scheme_hash and self.scheme_hash != self.config_id.sudo()._content_hash():
            raise UserError(_("The scheme changed after this was worked out. Work it out "
                              "again, then send it for payment."))
        checks = self._pb_pay_check()
        if not any(c['status'] == 'payable' for c in checks):
            raise UserError(_("Nobody in this re-work can be paid automatically. The list "
                              "says why for each person; a one-off in Updates is still "
                              "possible."))
        self._pb_write_people(checks)
        self.with_context(pb_retro_internal=True).write({
            'pay_sent_on': fields.Datetime.now(), 'pay_sent_by': self.env.uid,
            'pay_cancel_reason': False})
        return self.env['biz.approval.engine'].submit(self)

    def action_withdraw_payment(self, reason=None):
        """Take back a payment that is still waiting for approval."""
        self.ensure_one()
        self._pb_require()
        if self.pay_state != 'waiting' or not self.approval_request_id:
            raise UserError(_("This back pay is not waiting for approval."))
        return self.env['biz.approval.engine'].cancel(
            self.approval_request_id, reason or _("Withdrawn from the re-work"))

    def action_cancel_backpay(self, reason, employee_ids=None):
        """Undo (handover §2.7): cancel approved back pay no pay run has taken
        — or that sits in a payslip that is not finished (a reopened run): it
        is then taken out of that payslip at once. Reason required. Paid back
        pay can only move by reopening its pay run."""
        self.ensure_one()
        self._pb_require()
        self.require_pay(_('cancelling back pay'))
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_("Say why this back pay is cancelled, in a few words."))
        if self.pay_state not in ('approved', 'partly'):
            raise UserError(_("Only approved back pay can be cancelled."))
        entries = self.sudo().backpay_ids.filtered(lambda e: e.state in ('open', 'reserved'))
        if employee_ids:
            wanted = {int(i) for i in employee_ids}
            entries = entries.filtered(lambda e: e.employee_id.id in wanted)
        stuck = entries.filtered(lambda e: e.state == 'reserved'
                                 and e.payslip_id.state in DONE_STATES)
        if stuck:
            raise UserError(_("Part of it is already paid in %s. Reopen that pay run first.",
                              stuck[0].run_id.name or stuck[0].payslip_id.name or ''))
        if not entries:
            raise UserError(_("There is no back pay left to cancel here."))
        slips = entries.filtered(lambda e: e.state == 'reserved').mapped('payslip_id')
        entries._w().write({'state': 'cancelled', 'payslip_id': False, 'run_id': False,
                            'cancel_reason': reason[:240], 'cancelled_by': self.env.uid})
        for slip in slips:
            slip.sudo()._pb_backpay_apply(fresh=False)
        self.with_context(pb_retro_internal=True).write({'pay_cancel_reason': reason[:240]})
        self._pb_pay_refresh()
        return {'cancelled': len(entries)}

    # ------------------------------------------------------------ entries
    def _pb_make_entries(self):
        """On approval: one entry per payable person × pay item × past month,
        from the STORED result lines (never worked out again)."""
        self.ensure_one()
        rec = self.sudo()
        checks = rec._pb_pay_check()
        people = rec._pb_write_people(checks)
        payable = {p.employee_id.id: p for p in people if p.status == 'payable'}
        net_code = rec._pb_net_code()
        currency = rec.currency_id
        rules = {r.code: r for r in rec.config_id.rule_ids if r.code}
        vals = []
        for row in rec.slip_ids.filtered(lambda s: s.employee_id.id in payable
                                         and s.status == 'changed'):
            stored = {}
            for line in row.payslip_id.line_ids:
                if line.code and line.code not in stored and not line.pb_backpay:
                    stored[line.code] = line
            for line in row.line_ids:
                if float_is_zero(line.diff, precision_rounding=currency.rounding or 0.01):
                    continue
                past = stored.get(line.code)
                rule = rules.get(line.code)
                magnitude = line.band in MAGNITUDE_BANDS
                vals.append({
                    'review_id': rec.id, 'person_id': payable[row.employee_id.id].id,
                    'company_id': rec.company_id.id, 'employee_id': row.employee_id.id,
                    'config_id': rec.config_id.id, 'currency_id': currency.id,
                    'month': row.month, 'source_payslip_id': row.payslip_id.id,
                    'code': line.code, 'name': line.name or line.code,
                    'sequence': line.sequence, 'band': line.band, 'counts': line.counts,
                    'is_net': bool(net_code) and line.code == net_code,
                    'amount': line.diff,
                    'band_amount': currency.round(abs(line.would_be) - abs(line.was))
                    if magnitude else line.diff,
                    'category_id': (past.category_id.id if past and past.category_id
                                    else rule.category_id.id if rule and rule.category_id
                                    else False),
                    'salary_rule_id': (past.salary_rule_id.id if past and past.salary_rule_id
                                       else rule.salary_rule_id.id if rule else False),
                    'pay_role': (past.pay_role if past else (rule.net_role if rule else False))
                    or False,
                    'component_detail': bool(past.component_detail if past
                                             else (rule.net_role_detail if rule else False)),
                    'component_type': (past.component_type if past else
                                       (rule.component_type if rule else False)) or False,
                    'report_visible': bool(past.report_visible if past else
                                           (rule.report_visible if rule else False)),
                    'state': 'open',
                })
        if vals:
            self.env['pb.retro.backpay'].with_context(**{TOKEN: True}).sudo().create(vals)
        return len(vals)

    def _pb_pay_refresh(self):
        """The re-work's payment state follows its entries; fully paid closes it."""
        for rec in self.sudo():
            if rec.pay_state not in ('approved', 'partly', 'paid'):
                continue
            live = rec.backpay_ids.filtered(lambda e: e.state != 'cancelled')
            if not live:
                state = 'cancelled'
            elif all(e.state == 'paid' for e in live):
                state = 'paid'
            elif any(e.state == 'paid' for e in live):
                state = 'partly'
            else:
                state = 'approved'
            vals = {}
            if state != rec.pay_state:
                vals['pay_state'] = state
            if state == 'paid' and rec.state == 'done':
                vals.update(state='closed', closed_on=fields.Datetime.now(),
                            closed_by=self.env.uid)
            elif state != 'paid' and rec.state == 'closed' and rec.pay_state == 'paid':
                vals['state'] = 'done'      # a finished run was reopened
            if vals:
                rec.with_context(pb_retro_internal=True).write(vals)

    # ================================================================ adapter
    def _pb_payable(self):
        return self.sudo().person_ids.filtered(lambda p: p.status == 'payable')

    def _approval_revision(self):
        self.ensure_one()
        rec = self.sudo()
        return self._approval_revision_of([
            rec.id, rec.scheme_hash or '', str(rec.worked_out_on or ''),
            sorted([p.employee_id.id, round(float(p.net or 0.0), 2)]
                   for p in rec._pb_payable())])

    def _approval_validate(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("Only a worked-out re-work can be sent for payment."))
        if self.pay_state in LOCKED_PAY:
            raise UserError(_("This re-work has already been sent for payment."))
        if not self._pb_payable():
            raise UserError(_("Nobody in this re-work can be paid automatically."))
        return True

    def _approval_context(self):
        self.ensure_one()
        self = self.sudo()      # read for the engine (AM40): a seat may hold no payroll role
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        payable = self._pb_payable()
        total = currency.round(sum(payable.mapped('net')))
        makers = {u for u in (self.create_uid.id, self.worked_out_by.id,
                              self.pay_sent_by.id) if u}
        return {
            'company_id': company.id,
            'title': _("Back pay · %(scheme)s · %(months)s",
                       scheme=self.config_id.name or '', months=self._pb_months_label()),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': 'any',
            'facts': {
                'amount': {'value': float(total), 'unit': currency.name or ''},
                'people': {'value': len(payable), 'unit': ''},
            },
            'amount': float(total),
            'currency_id': currency.id,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._approval_revision(),
            'evidence': [
                {'key': 'worked_out', 'name': _('Worked out from finished payslips'),
                 'ok': bool(self.slip_ids),
                 'note': _("%s payslips", len(self.slip_ids))},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'amount': {'type': 'decimal', 'label': _('Take-home difference'),
                           'unit': 'currency'},
                'people': {'type': 'int', 'label': _('People')},
            },
            'kinds': [],
            'evidence': [{'key': 'worked_out',
                          'label': _('Worked out from finished payslips')}],
            'scope_levels': [],
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        return []

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        n = len(self._pb_payable())
        return _("1 person") if n == 1 else _("%s people", n)

    def _approval_detail(self, request):
        """Per person: the take-home difference and the months — what the
        approver agrees to put in the next pay run."""
        self.ensure_one()
        self = self.sudo()      # the approver may hold no payroll role (AM60)
        board = self.env['pb.retro.board']
        cur = board._cur(self.currency_id)
        rows = []
        for p in self.person_ids:
            if p.status == 'payable':
                rows.append({'head': p.employee_name or '', 'sub': p.months_label or '',
                             'cells': [board._signed(p.net, cur), _('Next pay run')],
                             'tone': ''})
        for p in self.person_ids.filtered(lambda x: x.status == 'not_payable'):
            rows.append({'head': p.employee_name or '', 'sub': p.months_label or '',
                         'cells': [board._signed(p.net, cur), self._pb_why_text(p.why)],
                         'tone': 'muted'})
        payable = self._pb_payable()
        chips = [
            {'label': _('Pay scheme'), 'value': self.config_id.name or ''},
            {'label': _('Months'), 'value': self._pb_months_label()},
            {'label': _('People paid'), 'value': str(len(payable))},
            {'label': _('Take-home difference'),
             'value': board._signed(sum(payable.mapped('net')), cur)},
            {'label': _('Why'), 'value': (self.reason or '').strip()[:140]},
        ]
        return {
            'title': _('Back pay in the next pay run'),
            'columns': [_('Take-home difference'), _('Paid in')],
            'rows': rows[:200],
            'chips': chips,
            'note': _("Each person's tax and insurance are the figures worked out for "
                      "those months; this month's formulas do not tax them again."),
        }

    @api.model
    def _pb_why_text(self, why):
        return {
            'drift': _("Cannot be compared exactly — add a one-off in Updates if needed"),
            'error': _("Could not be worked out"),
            'left': _("Has left — not paid automatically"),
            'moved': _("Now paid by another pay scheme — not paid automatically"),
            'currency': _("The pay scheme pays in another currency now"),
            'no_net': _("The pay scheme has no take-home line"),
            'zero': _("No difference"),
            'already': _("Already paid as back pay by another re-work — add a one-off in "
                         "Updates if more is owed"),
        }.get(why or '', '')

    def _approval_freeze(self, request):
        self.ensure_one()
        self.with_context(pb_retro_internal=True).sudo().write({'pay_state': 'waiting'})
        return True

    def _pb_unsend(self):
        if self.pay_state == 'waiting':
            self.with_context(pb_retro_internal=True).sudo().write({'pay_state': False})

    def _approval_return(self, request, reason):
        self.ensure_one()
        self._pb_unsend()
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self._pb_unsend()
        return True

    def _approval_withdraw(self, request, reason):
        self.ensure_one()
        self._pb_unsend()
        return True

    def _approval_apply(self, request):
        """Approved: the entries are made and wait for the next regular run.
        Idempotent; not gated on the money role (nothing leaves the company
        now — it is paid with the pay run, whose own approval moves money)."""
        self.ensure_one()
        rec = self.sudo()
        if rec.pay_state in ('approved', 'partly', 'paid'):
            return True
        if rec.pay_state != 'waiting':
            raise UserError(_("This back pay is no longer waiting for approval."))
        if rec.backpay_ids:
            raise UserError(_("This re-work already has back pay."))
        rec._pb_make_entries()
        rec.with_context(pb_retro_internal=True).write({
            'pay_state': 'approved', 'pay_approved_on': fields.Datetime.now()})
        if not rec.backpay_ids:
            rec.with_context(pb_retro_internal=True).write({'pay_state': 'cancelled'})
        return True

    # ------------------------------------------------------------ approval seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'pay_head', PAY_HEAD_GROUPS)
        return Seed.lay(
            company, BACKPAY_PROCESS_KEY, WORKFLOW_NAME,
            route(role_step(_('Head of pay'), 'pay_head')),
            binding_note='The route back pay for past months follows unless '
                         'somebody publishes another one.',
            model_name='pb.retro.review', role_keys=ROLES,
            reason='Set up when back pay for past months was switched on')


class BizApprovalRequestSeatRetro(models.Model):
    """A seat on a back-pay request is also a read of that re-work (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.retro.review' or not request.res_id:
                continue
            record = self.env['pb.retro.review'].sudo().browse(request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.with_context(pb_retro_internal=True).write(
                    {'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyBackpaySeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.retro.review'].sudo()._approval_seed_default(company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_retro: %s has no back-pay route', company.name)
        return companies


def seed_all(env):
    """Every company gets the one-step route (install hook and the 19.0.1.1.0
    migration). A failure is logged and never stops an install."""
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.retro.review'].sudo()._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001
            _logger.exception('pb_retro: %s has no back-pay route', company.name)
    _logger.info('pb_retro: %s back-pay routes published', done)
    return done


# =====================================================================
# The pay run takes it: the seam, the reservation, the floor
# =====================================================================
class HrPayslipLineBackpay(models.Model):
    _inherit = 'hr.payslip.line'

    #: Only ever written True (on back-pay lines); every other line keeps NULL,
    #: so the partial index holds back-pay lines only.
    pb_backpay = fields.Boolean(string='Back pay', readonly=True, copy=False,
                                index='btree_not_null')
    pb_backpay_band_amount = fields.Float(
        string='Back pay counted in its total', digits=(16, 4), readonly=True, copy=False,
        help='For money taken off or paid by the employer: how much this back pay '
             'changes that total (a negative figure lowers it).')

    def pb_pay_totals(self):
        """The one band reading, with back-pay lines counted by what they do
        to their total (`pb_backpay_band_amount`) where the reading counts a
        line by its size. Lines of payslips without back pay: unchanged."""
        if not self or 'pb_backpay' not in self._fields:
            return super().pb_pay_totals()
        backpay = self.filtered(lambda l: l.pb_backpay)
        if not backpay:
            return super().pb_pay_totals()
        result = super(HrPayslipLineBackpay, self - backpay).pb_pay_totals()
        result = dict(result)
        key_of = {'GROSS': 'gross', 'BASIC': 'gross', 'ALW': 'gross', 'DED': 'deductions',
                  'NET': 'net', 'ERCOST': 'employer_cost'}
        for slip in backpay.mapped('slip_id'):
            mine = backpay.filtered(lambda l, s=slip: l.slip_id == s)
            regular = (self - backpay).filtered(lambda l, s=slip: l.slip_id == s)
            has_gross = any(l.pb_counts_in_totals() and l.pb_pay_band() == 'GROSS'
                            for l in regular | mine)
            for line in mine:
                if not line.pb_counts_in_totals():
                    continue
                band = line.pb_pay_band()
                if band in ('BASIC', 'ALW') and has_gross:
                    continue
                amount = line.pb_backpay_band_amount if band in ('DED', 'ERCOST') \
                    else (line.total or 0.0)
                key = key_of.get(band)
                if key:
                    result[key] = result.get(key, 0.0) + amount
        return result


class HrPayslipBackpay(models.Model):
    _inherit = 'hr.payslip'

    pb_backpay_net = fields.Float(
        string='Back pay in take-home', digits=(16, 4), readonly=True, copy=False,
        help='How much back pay for past months is inside this payslip\'s take-home.')
    pb_backpay_note = fields.Text(readonly=True, copy=False)

    # ------------------------------------------------------------ the seam
    def _create_payslip_lines_from_formulas(self, rules, computed_values):
        res = super()._create_payslip_lines_from_formulas(rules, computed_values)
        self._pb_backpay_apply(fresh=True)
        return res

    # ------------------------------------------------------------ taking it
    def _pb_backpay_eligible(self):
        """'' when this payslip may take back pay, else why not (a word)."""
        self.ensure_one()
        slip = self.sudo()
        if not slip.id or slip.state in DONE_STATES or slip.state == 'cancel':
            return 'state'
        run = slip.payslip_run_id
        if not run:
            return 'no_run'
        kind = (run.pb_run_kind if 'pb_run_kind' in run._fields else '') or 'regular'
        if kind != 'regular':
            return 'kind'
        return ''

    def _pb_backpay_strip(self):
        """Take the back pay out of this payslip's lines (rebuild path)."""
        self.ensure_one()
        slip = self.sudo()
        slip.line_ids.filtered(lambda l: l.pb_backpay).unlink()
        if slip.pb_backpay_net:
            net = slip.line_ids.pb_net_line()
            if net:
                net.amount = (net.amount or 0.0) - slip.pb_backpay_net
            slip.pb_backpay_net = 0.0

    def _pb_backpay_apply(self, fresh=True):
        """Append this payslip's back pay after its formula lines.

        `fresh`: the producer has just rebuilt every line (the take-home line
        holds no back pay). Otherwise the back pay already on the payslip is
        taken out first (cancel of an entry in a reopened run).

        A payslip whose person has no back pay waiting and that holds none
        gets nothing written at all (R1)."""
        for slip in self:
            slip._pb_backpay_apply_one(fresh)

    def _pb_backpay_apply_one(self, fresh):
        slip = self.sudo()
        if not slip.id or not slip.employee_id:
            return
        Entry = self.env['pb.retro.backpay'].sudo()
        if not fresh:
            # the lines were not rebuilt: take the back pay already on them out
            slip._pb_backpay_strip()
        live = Entry.search([('employee_id', '=', slip.employee_id.id),
                             ('state', 'in', ('open', 'reserved'))], limit=1)
        if not live:
            # Nothing waiting for this person and nothing held: untouched.
            if fresh and slip.pb_backpay_net:
                slip.pb_backpay_net = 0.0
            if slip.pb_backpay_note:
                slip.pb_backpay_note = False
            return
        held = Entry.search([('payslip_id', '=', slip.id), ('state', '=', 'reserved')])
        why_not = slip._pb_backpay_eligible()
        candidates = Entry.browse()
        if not why_not and slip.formula_config_id:
            candidates = Entry.search([
                ('employee_id', '=', slip.employee_id.id),
                ('config_id', '=', slip.formula_config_id.id),
                ('company_id', '=', slip.company_id.id),
                ('state', 'in', ('open', 'reserved'))], order='month, sequence, id')
        if candidates:
            self.env.cr.execute(
                'SELECT id FROM pb_retro_backpay WHERE id IN %s ORDER BY id FOR UPDATE',
                (tuple(candidates.ids),))
            candidates.invalidate_recordset()
            candidates = candidates.filtered(
                lambda e: e.state == 'open' or (e.state == 'reserved'
                                                and e.payslip_id.id == slip.id))
        cfg = slip.formula_config_id.sudo()
        currency = cfg.currency_id or cfg.company_id.currency_id or slip.company_id.currency_id
        candidates = candidates.filtered(
            lambda e: e.currency_id == currency and slip.date_from
            and slip.date_from > _month_end(e.review_id.month_to or e.month))
        take, wait, note = slip._pb_backpay_fit(candidates, currency)
        slip._pb_backpay_lines(take, currency)
        # the reservation
        keep = take
        release = (held | candidates) - keep
        if keep:
            keep._w().write({'state': 'reserved', 'payslip_id': slip.id,
                             'run_id': slip.payslip_run_id.id or False, 'waited': False})
        if release:
            release._w().write({'state': 'open', 'payslip_id': False, 'run_id': False})
        if wait:
            wait._w().write({'waited': True})
        value = json.dumps(note, sort_keys=True) if note else False
        if (slip.pb_backpay_note or False) != value:
            slip.pb_backpay_note = value
        (keep | release).mapped('review_id')._pb_pay_refresh()

    def _pb_backpay_fit(self, entries, currency):
        """(taken, waiting, note) — whole months, take-home never below zero."""
        self.ensure_one()
        if not entries:
            return entries, entries, None
        net_line = self.sudo().line_ids.pb_net_line()
        months = {}
        for e in entries:
            months.setdefault(e.month, self.env['pb.retro.backpay'].browse())
            months[e.month] |= e
        if not net_line:
            return entries.browse(), entries, {'issue': 'no_net',
                                               'waiting': [str(m) for m in sorted(months)]}
        net = net_line.total or 0.0
        groups = []
        for month, group in months.items():
            effect = currency.round(sum(group.filtered('is_net').mapped('amount')))
            groups.append((effect < 0, month, effect, group))
        groups.sort(key=lambda g: (g[0], g[1]))
        taken = entries.browse()
        waiting = entries.browse()
        stop = False
        for lowers, month, effect, group in groups:
            if not stop and float_compare(net + effect, 0.0,
                                          precision_rounding=currency.rounding or 0.01) >= 0:
                taken |= group
                net = currency.round(net + effect)
                continue
            stop = True
            waiting |= group
        note = None
        if waiting:
            note = {'issue': 'floor', 'waiting': sorted({str(e.month) for e in waiting}),
                    'taken': sorted({str(e.month) for e in taken})}
        return taken, waiting, note

    def _pb_backpay_lines(self, entries, currency):
        """One line per pay item (months collapsed); the take-home item goes
        into the payslip's own take-home line."""
        self.ensure_one()
        slip = self.sudo()
        net_total = 0.0
        by_code = {}
        for e in entries.sorted(lambda x: (x.sequence, x.code, x.month, x.id)):
            if e.is_net:
                net_total += e.amount
                continue
            by_code.setdefault(e.code, []).append(e)
        vals_list = []
        fallback = None
        for i, (code, group) in enumerate(by_code.items()):
            first = group[0]
            amount = currency.round(sum(x.amount for x in group))
            band_amount = currency.round(sum(x.band_amount for x in group))
            category = first.category_id
            if not category:
                fallback = fallback or slip._pb_other_category()
                category = fallback
            vals_list.append({
                'slip_id': slip.id,
                'name': _("Back pay · %(item)s · %(months)s", item=first.name or code,
                          months=months_text(self.env, [x.month for x in group])),
                'code': code,
                'category_id': category.id,
                'sequence': LINE_SEQUENCE + (first.sequence or 0) * 1 + i,
                'amount': amount,
                'quantity': 1.0,
                'rate': 100.0,
                'salary_rule_id': first.salary_rule_id.id or False,
                'contract_id': slip.contract_id.id or False,
                'employee_id': slip.employee_id.id,
                'report_visible': first.report_visible,
                'component_type': first.component_type or False,
                'component_detail': first.component_detail,
                'pay_role': first.pay_role or False,
                'pb_backpay': True,
                'pb_backpay_band_amount': band_amount,
            })
        if vals_list:
            self.env['hr.payslip.line'].sudo().create(vals_list)
        net_total = currency.round(net_total)
        if net_total:
            net = slip.line_ids.filtered(lambda l: not l.pb_backpay).pb_net_line()
            if net:
                net.amount = (net.amount or 0.0) + net_total
        if (slip.pb_backpay_net or 0.0) != net_total:
            slip.pb_backpay_net = net_total

    # ------------------------------------------------------------ the payslip PDF
    def _themed_payslip_render(self):
        """The printed payslip: each pay item shows this month's own figure,
        and the back pay sits in its own block "Back pay for past months"
        (take-home, the big card, includes it). Payslips without back pay:
        the untouched render."""
        render = super()._themed_payslip_render()
        slip = self.sudo()
        if 'pb_backpay' not in slip.line_ids._fields:
            return render
        backpay = slip.line_ids.filtered(lambda l: l.pb_backpay)
        if not backpay and not slip.pb_backpay_net:
            return render
        try:
            from markupsafe import Markup
            by_code = {}
            for line in backpay:
                by_code[line.code] = by_code.get(line.code, 0.0) + (line.total or 0.0)
            net_line = slip.line_ids.filtered(lambda l: not l.pb_backpay).pb_net_line()
            if net_line and slip.pb_backpay_net:
                by_code[net_line.code] = by_code.get(net_line.code, 0.0) + slip.pb_backpay_net
            names = {}
            for rule in slip.formula_config_id.sudo().rule_ids:
                if rule.code in by_code:
                    nm = (rule.salary_rule_id.name if rule.salary_rule_id else False) \
                        or rule.name or rule.code
                    names.setdefault(nm, rule.code)
            for section in render.get('sections') or []:
                moved = 0.0
                for line in section.get('lines') or []:
                    code = names.get(line.get('name'))
                    if code in by_code:
                        line['total'] = (line.get('total') or 0.0) - by_code[code]
                        line['is_deduction'] = line['total'] < 0
                        moved += by_code[code]
                if moved:
                    section['subtotal'] = (section.get('subtotal') or 0.0) - moved
            lines = [{'name': line.name, 'total': line.total or 0.0,
                      'is_deduction': (line.total or 0.0) < 0}
                     for line in backpay.sorted(lambda l: (l.sequence, l.id))]
            if slip.pb_backpay_net:
                lines.append({'name': _("Take-home from back pay"),
                              'total': slip.pb_backpay_net,
                              'is_deduction': slip.pb_backpay_net < 0})
            render.setdefault('sections', []).append({
                'title': _("Back pay for past months"),
                'color_hex': '#5A4BB0',
                'note_html': Markup(''),
                'lines': lines,
                'subtotal': slip.pb_backpay_net or 0.0,
            })
        except Exception:       # noqa: BLE001 — a print never fails on this block
            _logger.exception('pb_retro: back-pay block not printed for payslip %s', slip.id)
        return render

    # ------------------------------------------------------------ follow the payslip
    def write(self, vals):
        state = vals.get('state')
        before = {}
        if state:
            before = {s.id: s.state for s in self}
        res = super().write(vals)
        if state:
            self._pb_backpay_follow(before, state)
        return res

    def _pb_backpay_follow(self, before, state):
        Entry = self.env['pb.retro.backpay'].sudo()
        entries = Entry.search([('payslip_id', 'in', self.ids),
                                ('state', 'in', ('reserved', 'paid'))])
        if not entries:
            return
        if state in DONE_STATES:
            todo = entries.filtered(lambda e: e.state == 'reserved')
            if todo:
                todo._w().write({'state': 'paid',
                                 'paid_on': fields.Date.context_today(self)})
        elif state == 'cancel':
            entries._w().write({'state': 'open', 'payslip_id': False, 'run_id': False,
                                'paid_on': False})
        else:
            undone = entries.filtered(lambda e: e.state == 'paid'
                                      and before.get(e.payslip_id.id) in DONE_STATES)
            if undone:
                undone._w().write({'state': 'reserved', 'paid_on': False})
        entries.mapped('review_id')._pb_pay_refresh()

    def unlink(self):
        entries = self.env['pb.retro.backpay'].sudo().search(
            [('payslip_id', 'in', self.ids), ('state', 'in', ('reserved', 'paid'))])
        reviews = entries.mapped('review_id')
        if entries:
            entries._w().write({'state': 'open', 'payslip_id': False, 'run_id': False,
                                'paid_on': False})
        res = super().unlink()
        reviews._pb_pay_refresh()
        return res


class HrPayslipRunBackpay(models.Model):
    _inherit = 'hr.payslip.run'

    def unlink(self):
        slips = self.mapped('slip_ids')
        entries = self.env['pb.retro.backpay'].sudo().search(
            [('payslip_id', 'in', slips.ids), ('state', 'in', ('reserved', 'paid'))])
        reviews = entries.mapped('review_id')
        if entries:
            entries._w().write({'state': 'open', 'payslip_id': False, 'run_id': False,
                                'paid_on': False})
        res = super().unlink()
        reviews._pb_pay_refresh()
        return res

    # ------------------------------------------------------------ the SQL twin
    @api.model
    def _pb_slip_totals(self, run_ids):
        """The run's per-payslip money, with back-pay lines counted by what
        they do to their total. Payslips without back pay: exactly the SQL
        answer (the run's figures of a run without back pay do not move)."""
        out = super()._pb_slip_totals(run_ids)
        ids = [int(r) for r in (run_ids or []) if r]
        if not ids or not out:
            return out
        self.env['hr.payslip.line'].flush_model(['slip_id', 'pb_backpay'])
        self.env.cr.execute("""
            SELECT DISTINCT l.slip_id FROM hr_payslip_line l
              JOIN hr_payslip p ON p.id = l.slip_id AND p.state != 'cancel'
             WHERE l.pb_backpay AND p.payslip_run_id IN %s
        """, (tuple(ids),))
        affected = [r[0] for r in self.env.cr.fetchall()]
        if not affected:
            return out
        Slip = self.env['hr.payslip'].sudo()
        for slip in Slip.browse(affected).exists():
            entry = out.get(slip.id)
            if entry is None:
                continue
            entry.update(self._pb_backpay_slip_entry(slip, entry['run_id']))
        return out

    @api.model
    def _pb_backpay_slip_entry(self, slip, run_id):
        """The SQL's per-payslip figures, rebuilt in Python for one payslip that
        holds back pay (same bucket rule, same signed-deduction decision)."""
        from odoo.addons.pb_payruns.models.payslip_money import uses_signed_deductions
        buckets = self._PB_CATEGORY_BUCKETS
        role_map = {'earning': 'GROSS', 'deduction': 'DED', 'net': 'NET',
                    'employer_cost': 'ERCOST', 'info': None, 'mixed': None}
        bands = {}
        for line in slip.line_ids:
            if not line.category_id:
                continue
            ccode = line.category_id.code or ''
            role = line.pay_role or False
            bucket = role_map.get(role) if role else (ccode if ccode in buckets else None)
            if not bucket:
                continue
            is_net = role == 'net' or ccode == 'NET'
            if not is_net and line.component_detail:
                continue
            magnitude_band = bucket in ('DED', 'DEDUCTION', 'COMP', 'ERCOST')
            if line.pb_backpay and magnitude_band:
                magnitude = signed = line.pb_backpay_band_amount or 0.0
            else:
                total = line.total or 0.0
                magnitude, signed = (abs(total) if magnitude_band else total), total
            row = bands.setdefault(bucket, [0.0, 0.0, True])
            row[0] += magnitude
            row[1] += signed
            row[2] = row[2] and role == 'deduction'
        gross = bands.get('GROSS', (0,))[0] or (
            bands.get('BASIC', (0,))[0] + bands.get('ALW', (0,))[0])
        net = bands.get('NET', (0,))[0]
        deductions = [bands[b] for b in ('DED', 'DEDUCTION', 'COMP') if b in bands]
        apply_signed = uses_signed_deductions(
            gross, net, sum(b[1] for b in deductions), sum(b[0] for b in deductions),
            bool(deductions) and all(b[2] for b in deductions),
            any(b in bands for b in ('GROSS', 'BASIC', 'ALW')), 'NET' in bands)
        counted = {}
        for code, (magnitude, signed, _explicit) in bands.items():
            counted[code] = (signed if apply_signed and code in ('DED', 'DEDUCTION', 'COMP')
                             else magnitude)
        return {
            'run_id': run_id,
            'gross': counted.get('GROSS') or (counted.get('BASIC', 0.0)
                                              + counted.get('ALW', 0.0)),
            'deductions': (counted.get('DED', 0.0) + counted.get('DEDUCTION', 0.0)
                           + counted.get('COMP', 0.0)),
            'net': counted.get('NET', 0.0),
            'employer_cost': counted.get('ERCOST', 0.0),
            'bands': counted,
        }

    # ------------------------------------------------------------ review notes
    def pb_review_flags(self, slip_ids=None):
        out = super().pb_review_flags(slip_ids=slip_ids)
        try:
            self._pb_backpay_notes(out)
        except Exception:       # noqa: BLE001 — a note never breaks a screen
            _logger.exception('pb_retro: back-pay notes failed on run %s', self.id)
        return out

    def _pb_backpay_notes(self, out):
        if not out:
            return out
        Entry = self.env['pb.retro.backpay'].sudo()
        entries = Entry.search([('payslip_id', 'in', list(out)),
                                ('state', 'in', ('reserved', 'paid'))])
        noted = self.env['hr.payslip'].sudo().search(
            [('id', 'in', list(out)), ('pb_backpay_note', '!=', False)])
        if not entries and not noted:
            return out
        board = self.env['pb.retro.board']
        by_slip = {}
        for e in entries:
            by_slip.setdefault(e.payslip_id.id, Entry.browse())
            by_slip[e.payslip_id.id] |= e
        for slip_id in set(by_slip) | set(noted.ids):
            row = out.get(slip_id)
            if row is None:
                continue
            mine = by_slip.get(slip_id) or Entry.browse()
            words = []
            if mine:
                cur = board._cur(mine[0].currency_id)
                net = sum(mine.filtered('is_net').mapped('amount'))
                words.append(_("Back pay for %(months)s: %(net)s take-home",
                               months=months_text(self.env, mine.mapped('month')),
                               net=board._signed(net, cur)))
                row['backpay'] = True
            slip = self.env['hr.payslip'].sudo().browse(slip_id)
            try:
                note = json.loads(slip.pb_backpay_note or 'null') or {}
            except (TypeError, ValueError):
                note = {}
            if note.get('waiting'):
                waiting = months_text(self.env, [fields.Date.to_date(m)
                                                 for m in note['waiting']])
                if note.get('issue') == 'no_net':
                    words.append(_("Back pay for %s waits: this payslip has no take-home "
                                   "line", waiting))
                else:
                    words.append(_("Back pay for %s waits for the next pay run so "
                                   "take-home is not below zero", waiting))
            if words:
                row['note'] = ' · '.join(r for r in [row.get('note') or ''] + words if r)
        return out


class PayrollImportBatchBackpay(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def _compute_and_create_payslip_lines(self, payslip, input_values):
        res = super()._compute_and_create_payslip_lines(payslip, input_values)
        payslip._pb_backpay_apply(fresh=True)
        return res


# =====================================================================
# The readers that count a code once — year-to-date and fund payments
# =====================================================================
class HrFormulaConfigBackpay(models.Model):
    _inherit = 'hr.formula.config'

    def _pb_history_read(self, emp_ids, start):
        """Running totals (`history.ytd/qtd/mtd`) count back pay in the month
        it was PAID: a finished payslip that took back pay reads its stored
        results plus the back pay of each item. Payslips without back pay:
        the untouched rows."""
        out = super()._pb_history_read(emp_ids, start)
        ids = [row['id'] for rows in out.values() for row in rows]
        if not ids:
            return out
        Entry = self.env['pb.retro.backpay'].sudo()
        Entry.flush_model(['payslip_id', 'state', 'code', 'amount'])
        self.env.cr.execute("""
            SELECT payslip_id, code, SUM(amount) FROM pb_retro_backpay
             WHERE payslip_id = ANY(%s) AND state IN ('reserved', 'paid')
             GROUP BY payslip_id, code
        """, [ids])
        extra = {}
        for slip_id, code, amount in self.env.cr.fetchall():
            extra.setdefault(slip_id, {})[code] = float(amount or 0.0)
        if not extra:
            return out
        for rows in out.values():
            for row in rows:
                add = extra.get(row['id'])
                if not add:
                    continue
                try:
                    payload = json.loads(row['text'] or '{}')
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                for code, amount in add.items():
                    value = payload.get(code, 0.0)
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        continue
                    payload[code] = value + amount
                row['payload'] = payload
        return out


class PbFundPaymentBackpay(models.Model):
    _inherit = 'pb.fund.payment'

    @api.model
    def _pb_read(self, payees, month):
        """What is owed to a fund includes the back-pay tax and insurance of
        the month it was paid, by what it does to the amount owed — a back
        pay that lowers insurance lowers what is owed."""
        out = super()._pb_read(payees, month)
        if not out:
            return out
        payees = payees.sudo()
        items = payees.mapped('item_ids').filtered(lambda i: i.rule_id and i.config_id)
        by_key = {}
        for item in items:
            by_key.setdefault((item.config_id.id, item.code), []).append(item)
        slip_ids = set()
        for row in out.values():
            slip_ids |= set(row['slips'])
        if not slip_ids:
            return out
        Line = self.env['hr.payslip.line'].sudo()
        lines = Line.search([('slip_id', 'in', list(slip_ids)), ('pb_backpay', '=', True)])
        for line in lines:
            if line.pb_pay_band() not in ('DED', 'ERCOST'):
                continue
            slip = line.slip_id
            for item in by_key.get((slip.formula_config_id.id, line.code), []):
                cfg = item.config_id
                currency = cfg.currency_id or cfg.company_id.currency_id
                row = out.get((item.payee_id.id, currency.id))
                if row is None or slip.id not in row['slips']:
                    continue
                fix = (line.pb_backpay_band_amount or 0.0) - abs(line.total or 0.0)
                row[item.share] += fix
                it = row['items'].get(item.rule_id.id)
                if it is not None:
                    it['amount'] += fix
        for row in out.values():
            cur = row['currency']
            row['employee'] = cur.round(row['employee'])
            row['employer'] = cur.round(row['employer'])
        return out
