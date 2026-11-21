# -*- coding: utf-8 -*-
"""The unspent part of a settled trip advance, taken back from the next
regular pay — through the same appended-lines seam as the claims
(`pb_expense_payroll/models/hr_payslip.py`), AFTER the claims (they raise
take-home first).

TAKE-HOME NEVER BELOW ZERO (owner ruling E6; the PR-E rule "take what fits,
move the rest to next month"). The deduction is not fed into the formulas,
so the payslip's take-home before it is already known: the pay run takes
min(what is left, take-home), never more, and the rest waits for the next
regular run. No second pass of the formulas, no loop.

The person saw the figure first: only a payslip whose pay period ends on or
after the day the advance was settled takes it (the figure is on My Payobook
from that day).
"""
from odoo import _, fields, models
from odoo.tools import float_compare

from odoo.addons.pb_expense_payroll.models.common import (ADVANCE_CODE, LIVE_STATES,
                                                          month_of)


class HrPayslipAdvance(models.Model):
    _inherit = 'hr.payslip'

    pb_advance_line_ids = fields.One2many(
        'pb.trip.advance.recovery', 'payslip_id', string='Trip advances taken back',
        readonly=True)

    def _pb_extras_wanted(self):
        if super()._pb_extras_wanted():
            return True
        slip = self.sudo()
        if self.env['pb.trip.advance.recovery'].sudo().search_count(
                [('payslip_id', '=', slip.id), ('state', 'in', LIVE_STATES)], limit=1):
            return True
        return bool(self.env['pb.trip.advance'].sudo().search_count(
            [('employee_id', '=', slip.employee_id.id), ('state', '=', 'settled'),
             ('recover_how', '=', 'pay')], limit=1))

    def _pb_extras_steps(self, ctx):
        super()._pb_extras_steps(ctx)
        self._pb_advance_step(ctx)

    def _pb_advance_step(self, ctx):
        slip = self.sudo()
        Rec = self.env['pb.trip.advance.recovery'].sudo()
        Adv = self.env['pb.trip.advance'].sudo()
        held = Rec.search([('payslip_id', '=', slip.id), ('kind', '=', 'payroll'),
                           ('state', 'in', LIVE_STATES)])
        advs = Adv.search([('employee_id', '=', slip.employee_id.id),
                           ('company_id', '=', slip.company_id.id),
                           ('state', '=', 'settled'), ('recover_how', '=', 'pay')],
                          order='settled_on, id')
        if not advs and not held:
            return
        why = slip._pb_extras_why_not()
        note = {}
        items = []
        if advs and why == 'file':
            note['file'] = advs.ids
        elif advs and not why:
            self.env.cr.execute('SELECT id FROM pb_trip_advance WHERE id IN %s '
                                'ORDER BY id FOR UPDATE', (tuple(advs.ids),))
            advs.invalidate_recordset()
            advs.recovery_ids.invalidate_recordset()
            currency = slip._pb_scheme_currency()
            month = month_of(slip.date_to)
            net = slip._pb_net_line()
            if not net:
                note['no_net'] = advs.ids
                advs = Adv.browse()
            room = currency.round(max((net.total if net else 0.0), 0.0))
            for adv in advs:
                if adv.settled_on and slip.date_to and adv.settled_on > slip.date_to:
                    continue          # settled after this pay month: next one
                if adv.currency_id != currency:
                    note.setdefault('currency', []).append(adv.id)
                    continue
                others = adv.recovery_ids.filtered(
                    lambda l: l.kind == 'payroll' and l.state in LIVE_STATES
                    and l.payslip_id != slip)
                if others.filtered(lambda l: l.pay_month == month):
                    continue          # another payslip took this month's part
                pending = sum(others.filtered(lambda l: l.state == 'reserved').mapped('amount'))
                left = currency.round(adv.left - pending)
                if float_compare(left, 0.0, precision_rounding=currency.rounding or 0.01) <= 0:
                    continue
                take = currency.round(min(left, room))
                if float_compare(take, 0.0, precision_rounding=currency.rounding or 0.01) <= 0:
                    note.setdefault('waits', []).append([adv.id, left])
                    continue
                room = currency.round(room - take)
                items.append((adv, take))
                if float_compare(take, left, precision_rounding=currency.rounding or 0.01) < 0:
                    note.setdefault('waits', []).append([adv.id, currency.round(left - take)])
            if items:
                slip._pb_extras_add_lines('advance', [
                    {'name': _("Unspent trip advance taken back · %s", adv.trip_id.name),
                     'amount': take} for adv, take in items], currency, code=ADVANCE_CODE)
        keep = Rec.browse()
        for adv, take in items:
            line = held.filtered(lambda l, a=adv: l.advance_id == a)[:1]
            vals = {'amount': take, 'payslip_id': slip.id,
                    'run_id': slip.payslip_run_id.id or False,
                    'pay_month': month_of(slip.date_to), 'state': 'reserved',
                    'paid_on': False}
            if line:
                line._pb_write(vals)
            else:
                line = Rec._pb_create(dict(vals, advance_id=adv.id, kind='payroll'))
            keep |= line
        (held - keep)._pb_release(_("payslip %s no longer takes it", slip.name or slip.id))
        if note:
            ctx['note']['advance'] = note

    def _pb_extras_follow(self, before, state):
        super()._pb_extras_follow(before, state)
        self.env['pb.trip.advance.recovery'].sudo()._pb_slips_follow(self, before, state)

    def _pb_extras_gone(self, why):
        super()._pb_extras_gone(why)
        self.env['pb.trip.advance.recovery'].sudo()._pb_slips_gone(self, why)


class HrPayslipRunAdvance(models.Model):
    _inherit = 'hr.payslip.run'

    def _pb_extras_more_notes(self, slip, note):
        said = list(super()._pb_extras_more_notes(slip, note))
        lines = self.env['pb.trip.advance.recovery'].sudo().search(
            [('payslip_id', '=', slip.id), ('state', 'in', LIVE_STATES)])
        money = self.env['pb.expense.claim']._pb_money
        if lines:
            said.append(_("Unspent trip advance taken back: %s",
                          money(sum(lines.mapped('amount')), lines[:1].currency_id)))
        adv = note.get('advance') or {}
        Adv = self.env['pb.trip.advance'].sudo()
        if adv.get('waits'):
            first = Adv.browse(adv['waits'][0][0]).exists()
            total = sum(w[1] for w in adv['waits'])
            if first:
                said.append(_("%s of an unspent trip advance waits for the next pay run "
                              "so take-home is not below zero",
                              money(total, first.currency_id)))
        if adv.get('file'):
            advs = Adv.browse(adv['file']).exists()
            if advs:
                said.append(_("An unspent trip advance of %s is not taken back here: this "
                              "pay scheme is paid from a pay data file. Include it in "
                              "the file.", money(sum(advs.mapped('left')),
                                                 advs[:1].currency_id)))
        if adv.get('currency'):
            said.append(_("An unspent trip advance is in another currency than this pay "
                          "scheme, so it is not taken back here"))
        return said
