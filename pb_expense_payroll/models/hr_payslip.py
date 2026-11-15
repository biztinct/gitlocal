# -*- coding: utf-8 -*-
"""WDGAP S6-C — approved claims as their own line on the next regular payslip.

THE SEAM (no engine edit; the precedent is W2-D2's back pay, branch
`wdgap-w2d2`). The no-file line producer
`hr.payslip._create_payslip_lines_from_formulas` deletes every line of the
payslip and rebuilds them from the scheme's results on EVERY compute
(compute, "Recalculate" without a file, application-data mode, the demo
division path). This module overrides it — super() first, then
`_pb_extras_apply()` appends one line per claim AFTER the scheme's own lines
and adds the claims to the payslip's one take-home line. Nothing is fed into
the formulas, so no tax or insurance formula ever sees a claim: the line is
untaxed by construction, on every scheme, without set-up. A recompute
replaces the line (the producer has just deleted it), never doubles it.

The pay data file producer (`hr.payroll.import.batch.
_compute_and_create_payslip_lines`) is NOT overridden: schemes paid from a
pay data file are left exactly as they are (handover S6-C); their payslips
never take a claim, and the run's review says so.

HOW THE LINE IS TYPED so every band reader (`pb_pay_totals`, the run's SQL
twin `_pb_slip_totals`, `pb_net_line`, the review flags' SQL) reads it with no
change to any of them:
  * a payslip whose lines carry a pay role (classified scheme): pay role
    `earning` → counted in gross; take-home goes up by the same amount, so
    gross − deductions = take-home still holds;
  * a payslip whose lines carry no pay role (an older scheme): NO pay role
    (one role on such a payslip would make `pb_net_line` read "classified,
    no net line" and take-home 0) and the category its gross is read from
    (GROSS when the payslip has a gross line, else ALW, which is added to
    BASIC);
  * never a "detail" line, so it is counted once.

GOLDEN RAIL. A payslip whose person has no approved pay-run claim and that
holds none gets exactly the lines the producer made — this module writes
nothing at all (not even its note field).

WHO TAKES A CLAIM: a payslip being worked out, in a REGULAR run (never a
top-up, an Extra run, a payslip outside a run), on a scheme that is not a
mid-month advance scheme, not paid from a pay data file, and is the scheme
the scheme map says pays the person; the claim's company and currency are the
payslip's; the claim was approved in this pay month or before.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.tools import float_compare, float_is_zero

from .common import (CLAIM_CODE, COMPUTING_STATES, DONE_STATES, EXTRA_KINDS,
                     LINE_SEQUENCE, LIVE_STATES, month_of, scheme_asks_file,
                     scheme_pays)

_logger = logging.getLogger(__name__)

#: What the salary rule an appended line points at is called, per kind.
RULE_NAMES = {
    'claim': 'Expense claims paid back',
    'advance': 'Unspent trip advance taken back',
}
RULE_CODES = {'claim': CLAIM_CODE}


class HrPayslipLineExtras(models.Model):
    _inherit = 'hr.payslip.line'

    #: Only ever written on an appended line; every other line keeps NULL,
    #: so the partial index holds appended lines only.
    pb_extra_kind = fields.Selection(EXTRA_KINDS, string='Added after the pay items',
                                     readonly=True, copy=False,
                                     index='btree_not_null')


class HrPayslipExtras(models.Model):
    _inherit = 'hr.payslip'

    #: What was NOT taken and why (JSON; empty for almost every payslip).
    pb_extras_note = fields.Text(string='Claims and advances not taken',
                                 readonly=True, copy=False)
    pb_claim_payline_ids = fields.One2many('pb.expense.payline', 'payslip_id',
                                           string='Claims paid back', readonly=True)

    # =================================================================
    #  the seam
    # =================================================================
    def _create_payslip_lines_from_formulas(self, rules, computed_values):
        res = super()._create_payslip_lines_from_formulas(rules, computed_values)
        for slip in self:
            slip._pb_extras_apply()
        return res

    def _pb_extras_apply(self):
        """Append this payslip's claims (and, with `pb_trip_advance`, the
        unspent trip advance it takes back) after its scheme's lines.

        NEVER RAISES INTO THE RUN, NEVER LEAVES A CLAIM HELD THAT IS NOT ON
        THE PAYSLIP. Everything happens in one savepoint; if it fails, what
        this payslip held is given back (so the next run takes it) and the
        failure is noted for the run's review."""
        self.ensure_one()
        slip = self.sudo()
        if not slip.id or not slip.employee_id:
            return
        if not slip._pb_extras_wanted():
            # THE GOLDEN RAIL, cheaply: nobody to pay or take back and nothing
            # held — not a write, not a savepoint (a stale note is cleared).
            if slip.pb_extras_note:
                slip.pb_extras_note = False
            return
        ctx = {'note': {}}
        try:
            with self.env.cr.savepoint():
                slip._pb_extras_steps(ctx)
        except Exception:       # noqa: BLE001 — a claim never breaks a pay run
            _logger.exception('pb_expense_payroll: claims could not be added to '
                              'payslip %s', slip.id)
            with self.env.cr.savepoint():
                slip._pb_extras_gone(_("it could not be added to payslip %s",
                                       slip.name or slip.id))
            ctx = {'note': {'error': True}}
        value = json.dumps(ctx['note'], sort_keys=True) if ctx['note'] else False
        if (slip.pb_extras_note or False) != value:
            slip.pb_extras_note = value

    def _pb_extras_wanted(self):
        """Is there anything for this payslip to pay, take back or give
        back? Two counts on small indexed tables (hook: `pb_trip_advance`)."""
        self.ensure_one()
        slip = self.sudo()
        if self.env['pb.expense.payline'].sudo().search_count(
                [('payslip_id', '=', slip.id), ('state', 'in', LIVE_STATES)], limit=1):
            return True
        return bool(self.env['pb.expense.claim'].sudo().search_count(
            [('employee_id', '=', slip.employee_id.id), ('state', '=', 'approved'),
             ('pb_pay_route', '=', 'payrun')], limit=1))

    def _pb_extras_steps(self, ctx):
        """The steps, in order: claims first (they raise take-home), then
        what is taken back (`pb_trip_advance` appends its step after
        super())."""
        self._pb_claims_step(ctx)

    # =================================================================
    #  what a payslip may take
    # =================================================================
    def _pb_extras_why_not(self):
        """'' when this payslip may take claims / advances, else a key."""
        self.ensure_one()
        slip = self.sudo()
        if slip.state not in COMPUTING_STATES:
            return 'state'
        run = slip.payslip_run_id
        if not run:
            return 'no_run'
        kind = (run.pb_run_kind if 'pb_run_kind' in run._fields else '') or 'regular'
        if kind != 'regular':
            return 'kind'
        config = slip.formula_config_id
        if not config:
            return 'no_scheme'
        if config.sudo().cycle_type == 'mid_cycle':
            return 'mid'
        if scheme_asks_file(self.env, config):
            return 'file'
        if not scheme_pays(self.env, slip.employee_id, config.sudo(), slip.date_to):
            return 'other_scheme'
        return ''

    def _pb_scheme_currency(self):
        self.ensure_one()
        config = self.sudo().formula_config_id
        return (config.currency_id or config.company_id.currency_id
                or self.company_id.currency_id)

    def _pb_net_line(self):
        """The payslip's one take-home line (never an appended line)."""
        self.ensure_one()
        return self.sudo().line_ids.filtered(lambda l: not l.pb_extra_kind).pb_net_line()

    # =================================================================
    #  claims
    # =================================================================
    def _pb_claims_step(self, ctx):
        slip = self.sudo()
        Payline = self.env['pb.expense.payline'].sudo()
        Claim = self.env['pb.expense.claim'].sudo()
        held = Payline.search([('payslip_id', '=', slip.id), ('kind', '=', 'payroll'),
                               ('state', 'in', LIVE_STATES)])
        claims = Claim.search([('employee_id', '=', slip.employee_id.id),
                               ('company_id', '=', slip.company_id.id),
                               ('state', '=', 'approved'),
                               ('pb_pay_route', '=', 'payrun')], order='id')
        if not claims and not held:
            return                   # the golden rail: nothing written
        why = slip._pb_extras_why_not()
        note = {}
        taken = []
        if claims and why == 'file':
            waiting = claims.filtered(lambda c: not c._pb_live_payline())
            if waiting:
                note['file'] = waiting.ids
        elif claims and not why:
            self.env.cr.execute(
                'SELECT id FROM pb_expense_claim WHERE id IN %s ORDER BY id FOR UPDATE',
                (tuple(claims.ids),))
            claims.invalidate_recordset()
            claims.pb_payline_ids.invalidate_recordset()
            currency = slip._pb_scheme_currency()
            for claim in claims:
                live = claim._pb_live_payline()
                if live and live.payslip_id != slip:
                    continue         # another payslip (or the file) has it
                decided = claim.decided_on and month_of(claim.decided_on.date())
                if decided and slip.date_to and decided > slip.date_to:
                    continue         # approved after this pay month
                hold = claim._pb_pay_hold_reason()
                if hold:
                    note.setdefault('held', []).append(claim.id)
                    continue
                if claim.currency_id != currency:
                    note.setdefault('currency', []).append(claim.id)
                    continue
                amount = claim.currency_id.round(claim._pb_payable_amount())
                if float_compare(amount, 0.0, precision_rounding=claim.currency_id.rounding
                                 or 0.01) <= 0:
                    continue
                taken.append((claim, amount))
        if taken and not slip._pb_net_line():
            note['no_net'] = [c.id for c, _a in taken]
            taken = []
        if taken:
            currency = slip._pb_scheme_currency()
            slip._pb_extras_add_lines('claim', [
                {'name': _("Expense claim paid back · %s", claim.name), 'amount': amount}
                for claim, amount in taken], currency)
        # the reservation
        today_month = month_of(slip.date_to)
        keep = Payline.browse()
        for claim, amount in taken:
            line = held.filtered(lambda l, c=claim: l.claim_id == c)[:1]
            vals = {'amount': amount, 'payslip_id': slip.id,
                    'run_id': slip.payslip_run_id.id or False,
                    'pay_month': today_month, 'state': 'reserved', 'paid_on': False}
            if line:
                changes = {k: v for k, v in vals.items()
                           if (line[k].id if hasattr(line[k], 'id') else line[k]) != v}
                if changes:
                    line._pb_write(changes)
            else:
                line = Payline._pb_create(dict(vals, claim_id=claim.id, kind='payroll'))
            keep |= line
        (held - keep)._pb_release(_("payslip %s no longer takes it",
                                    slip.name or slip.id))
        if note:
            ctx['note']['claims'] = note

    # =================================================================
    #  appending lines (shared with pb_trip_advance)
    # =================================================================
    @api.model
    def _pb_category(self, code, name):
        Category = self.env['hr.salary.rule.category'].sudo()
        category = Category.search([('code', '=', code)], limit=1)
        return category or Category.create({'name': name, 'code': code})

    def _pb_extra_rule(self, kind, code, category):
        """The (archived) salary rule an appended line points at — a payslip
        line needs one. One per company and kind, made the first time it is
        needed (nothing is made at install). Archived, so no structure and no
        rule list ever offers it."""
        self.ensure_one()
        Rule = self.env['hr.salary.rule'].sudo().with_context(active_test=False)
        company = self.company_id
        rule = Rule.search([('code', '=', code), ('company_id', '=', company.id)],
                           limit=1)
        if rule:
            return rule
        return Rule.create({
            'name': RULE_NAMES.get(kind) or code, 'code': code,
            'sequence': LINE_SEQUENCE, 'category_id': category.id,
            'company_id': company.id, 'condition_select': 'none',
            'amount_select': 'fix', 'amount_fix': 0.0, 'quantity': '1.0',
            'appears_on_payslip': True, 'active': False,
        })

    def _pb_extra_typing(self, band):
        """`(pay_role, category, sign)` an appended line of `band` ('earning'
        or 'deduction') must carry so every band reader counts it rightly on
        THIS payslip (see the module docstring)."""
        self.ensure_one()
        lines = self.sudo().line_ids.filtered(lambda l: not l.pb_extra_kind)
        classified = 'pay_role' in lines._fields and any(l.pay_role for l in lines)
        counted = lines.filtered(lambda l: l.pb_counts_in_totals())
        if band == 'earning':
            if classified:
                return 'earning', self._pb_category('ALW', 'Allowance'), 1.0
            has_gross = any(l.pb_pay_band() == 'GROSS' for l in counted)
            if has_gross:
                return False, self._pb_category('GROSS', 'Gross'), 1.0
            return False, self._pb_category('ALW', 'Allowance'), 1.0
        deductions = counted.filtered(lambda l: l.pb_pay_band() == 'DED')
        negative = sum(1 for l in deductions if (l.total or 0.0) < 0)
        sign = -1.0 if deductions and negative * 2 > len(deductions) else 1.0
        return ('deduction' if classified else False,
                self._pb_category('DED', 'Deduction'), sign)

    def _pb_extras_add_lines(self, kind, items, currency, code=None):
        """Append one line per item ({'name', 'amount'} — amounts positive)
        and move take-home by their total (up for a claim, down for what is
        taken back). Returns the lines."""
        self.ensure_one()
        slip = self.sudo()
        band = 'earning' if kind == 'claim' else 'deduction'
        role, category, sign = slip._pb_extra_typing(band)
        code = code or RULE_CODES.get(kind)
        rule = slip._pb_extra_rule(kind, code, category)
        Line = self.env['hr.payslip.line'].sudo()
        line_fields = Line._fields
        top = max(slip.line_ids.mapped('sequence') or [0])
        vals_list = []
        total = 0.0
        for i, item in enumerate(items):
            amount = currency.round(item['amount'])
            total += amount
            vals = {
                'slip_id': slip.id, 'name': item['name'], 'code': code,
                'category_id': category.id,
                'sequence': max(LINE_SEQUENCE, top + 1) + i,
                'amount': sign * amount, 'quantity': 1.0, 'rate': 100.0,
                'salary_rule_id': rule.id,
                'contract_id': slip.contract_id.id or False,
                'employee_id': slip.employee_id.id,
                'pb_extra_kind': kind,
            }
            if 'pay_role' in line_fields:
                vals['pay_role'] = role or False
            if 'component_detail' in line_fields:
                vals['component_detail'] = False
            if 'report_visible' in line_fields:
                vals['report_visible'] = True
            vals_list.append(vals)
        lines = Line.create(vals_list) if vals_list else Line
        total = currency.round(total)
        if not float_is_zero(total, precision_rounding=currency.rounding or 0.01):
            net = slip._pb_net_line()
            factor = (net.quantity or 0.0) * (net.rate or 0.0) / 100.0
            delta = total if kind == 'claim' else -total
            net.amount = (net.amount or 0.0) + (delta / factor if factor else delta)
        return lines

    # =================================================================
    #  following the payslip
    # =================================================================
    def _pb_extras_follow(self, before, state):
        self.env['pb.expense.payline'].sudo()._pb_slips_follow(self, before, state)

    def _pb_extras_gone(self, why):
        self.env['pb.expense.payline'].sudo()._pb_slips_gone(self, why)

    def write(self, vals):
        state = vals.get('state')
        before = {s.id: s.state for s in self} if state else {}
        res = super().write(vals)
        if state:
            self._pb_extras_follow(before, state)
        return res

    def unlink(self):
        self._pb_extras_gone(_("payslip deleted"))
        return super().unlink()

    # =================================================================
    #  the printed payslip
    # =================================================================
    def _themed_payslip_render(self):
        """The printed payslip: the appended lines sit in their own block
        (take-home, the big figure, already includes them). Payslips without
        an appended line: the untouched render."""
        render = super()._themed_payslip_render()
        slip = self.sudo()
        extra = slip.line_ids.filtered(lambda l: l.pb_extra_kind)
        if not extra:
            return render
        try:
            from markupsafe import Markup
            lines = []
            effect = 0.0
            for line in extra.sorted(lambda l: (l.sequence, l.id)):
                value = abs(line.total or 0.0)
                taken = line.pb_extra_kind != 'claim'
                effect += -value if taken else value
                lines.append({'name': line.name, 'total': -value if taken else value,
                              'is_deduction': taken})
            render.setdefault('sections', []).append({
                'title': _("Expenses and trip advances"),
                'color_hex': '#5A4BB0',
                'note_html': Markup(''),
                'lines': lines,
                'subtotal': effect,
            })
        except Exception:       # noqa: BLE001 — a print never fails on this block
            _logger.exception('pb_expense_payroll: block not printed for payslip %s',
                              slip.id)
        return render


class HrPayslipRunExtras(models.Model):
    _inherit = 'hr.payslip.run'

    def unlink(self):
        self.mapped('slip_ids')._pb_extras_gone(_("pay run deleted"))
        return super().unlink()

    # ------------------------------------------------------------ review notes
    def pb_review_flags(self, slip_ids=None):
        out = super().pb_review_flags(slip_ids=slip_ids)
        try:
            self._pb_extras_notes(out)
        except Exception:       # noqa: BLE001 — a note never breaks a screen
            _logger.exception('pb_expense_payroll: notes failed on run %s', self.id)
        return out

    def _pb_extras_notes(self, out):
        """Quiet notes (W2-F `note`: shown, never counted as a flag)."""
        if not out:
            return out
        Slip = self.env['hr.payslip'].sudo()
        slips = Slip.browse(list(out)).exists()
        words = {}
        Claim = self.env['pb.expense.claim'].sudo()
        money = Claim._pb_money
        for line in self.env['pb.expense.payline'].sudo().search(
                [('payslip_id', 'in', slips.ids), ('state', 'in', LIVE_STATES)]):
            words.setdefault(line.payslip_id.id, {}).setdefault(
                'paid', []).append(line)
        for slip in slips:
            row = out.get(slip.id)
            if row is None or slip.state == 'cancel':
                continue
            said = []
            mine = (words.get(slip.id) or {}).get('paid') or []
            if mine:
                said.append(_("Expense claims paid back: %s (no tax)",
                              money(sum(l.amount for l in mine), mine[0].currency_id)))
            try:
                note = json.loads(slip.pb_extras_note or 'null') or {}
            except (TypeError, ValueError):
                note = {}
            claims_note = note.get('claims') or {}
            file_claims = Claim.browse(claims_note.get('file') or []).exists()
            if not file_claims and slip.state in COMPUTING_STATES + DONE_STATES:
                file_claims = self._pb_file_claims(slip)
            if file_claims:
                said.append(_("Approved expense claims of %s are not in this payslip: "
                              "this pay scheme is paid from a pay data file. Include "
                              "them in the file.",
                              money(sum(c._pb_payable_amount() for c in file_claims),
                                    file_claims[:1].currency_id)))
            if claims_note.get('currency'):
                said.append(_("An approved expense claim is in another currency than "
                              "this pay scheme, so it is not paid here"))
            if claims_note.get('no_net'):
                said.append(_("Approved expense claims are not paid here: this payslip "
                              "has no take-home line"))
            if claims_note.get('held'):
                said.append(_("An expense claim waits until its trip's cash advance is "
                              "settled"))
            if note.get('error'):
                said.append(_("Expense claims could not be added to this payslip; they "
                              "wait for the next pay run"))
            said.extend(self._pb_extras_more_notes(slip, note))
            if said:
                row['note'] = ' · '.join(r for r in [row.get('note') or ''] + said if r)
        return out

    def _pb_extras_more_notes(self, slip, note):
        """Hook for `pb_trip_advance` (its sentences for one payslip)."""
        return []

    @api.model
    def _pb_file_claims(self, slip):
        """The approved pay-run claims of a person whose payslip came from a
        pay data file (that path never takes a claim by itself)."""
        run = slip.payslip_run_id
        if not run or (run.pb_run_kind or 'regular') != 'regular':
            return self.env['pb.expense.claim']
        if not scheme_asks_file(self.env, slip.formula_config_id):
            return self.env['pb.expense.claim']
        claims = self.env['pb.expense.claim'].sudo().search([
            ('employee_id', '=', slip.employee_id.id),
            ('company_id', '=', slip.company_id.id),
            ('state', '=', 'approved'), ('pb_pay_route', '=', 'payrun')])
        return claims.filtered(lambda c: not c._pb_live_payline())
