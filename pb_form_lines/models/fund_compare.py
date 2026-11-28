# -*- coding: utf-8 -*-
"""WDGAP S2-B2 item 5 — the check step of a fund file, and Fund payments.

On the check step of a fund file the screen says, beside the figures:

  * who is LEFT OUT of the upload file and why (no member number…), and what
    the file's total is without them;
  * when `pb_fund_payments` is installed (read by probe — this module does
    not depend on it): the Fund payments total for the same month and
    currency, for the funds whose pay items are on this form's lines, and
    whether it is the same as the file's total. A month Fund payments has
    already worked out is read from its rows; a month it has not is read the
    way it would work it out (`pb.fund.payment._pb_read`), and the sentence
    says which. READ ONLY: nothing is written to Fund payments.

Everything is added as plain warning rows of the existing check answer, so
the S2-A flow screen shows them as they are (no screen code changes).
"""
import logging

from odoo import _, api, fields, models
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

LIVE_STATES = ('to_pay', 'waiting', 'approved', 'paid')


class PbGovFormBoardFundCheck(models.AbstractModel):
    _inherit = 'pb.gov.form.board'

    @api.model
    def flow_check(self, form_id, period, scheme_ids=None, currency_id=None):
        out = super().flow_check(form_id, period, scheme_ids=scheme_ids, currency_id=currency_id)
        form = self._form(form_id)
        if form.filing_section != 'fund' or out.get('blocked') or not out.get('people'):
            return out
        company = self.env.company
        start = fields.Date.to_date(out['period_start'])
        end = fields.Date.to_date(out['period_end'])
        try:
            extra = self._pb_fund_check(form, company, start, end, scheme_ids, currency_id)
        except Exception:      # noqa: BLE001 — the comparison never breaks the check
            _logger.exception('pb_form_lines: fund check failed for form %s', form.code)
            extra = []
        out['warnings'] = list(out.get('warnings') or []) + extra
        return out

    @api.model
    def _pb_money(self, value, currency):
        return formatLang(self.env, float(value or 0.0), currency_obj=currency)

    @api.model
    def _pb_fund_check(self, form, company, start, end, scheme_ids=None, currency_id=None):
        Reader = self.env['pb.gov.form.reader'].with_context(
            pb_fund_period=(fields.Date.to_string(start), fields.Date.to_string(end)))
        data = Reader._pb_read(form, company, start, end, scheme_ids=scheme_ids or None,
                               currency_id=currency_id or None)
        currency = self.env['res.currency'].browse(data.get('currency_id') or company.currency_id.id)
        Filing = self.env['pb.gov.filing']
        kept, left = Filing._pb_fund_split(form, data)
        code = form.total_line_code
        file_total = currency.round(Filing._pb_fund_total(kept, code))
        out = []
        if left:
            left_total = currency.round(Filing._pb_fund_total(left, code))
            if len(left) == 1:
                text = _("1 person is left out of the file (%(why)s). The file's total leaves out their %(amount)s: %(total)s.",
                         why='; '.join(left[0]['reasons']),
                         amount=self._pb_money(left_total, currency),
                         total=self._pb_money(file_total, currency))
            else:
                text = _("%(n)s people are left out of the file — the summary lists each with the reason. The file's total leaves out their %(amount)s: %(total)s.",
                         n=len(left), amount=self._pb_money(left_total, currency),
                         total=self._pb_money(file_total, currency))
            out.append({'code': 'fund_left_out', 'level': 'warn', 'message': text,
                        'employee_ids': sorted(r['employee_id'] for r in left)})
        compare = self._pb_fund_payments_total(form, company, start, currency)
        if compare is not None:
            fund_total, worked_out = compare
            month = format_date(self.env, start, date_format='MMMM y')
            if currency.compare_amounts(fund_total, file_total) == 0:
                text = _("Fund payments for %(month)s: %(amount)s — the same as this file.",
                         month=month, amount=self._pb_money(fund_total, currency))
                level = 'info'
            else:
                text = _("Fund payments for %(month)s: %(amount)s. This file: %(file)s. They differ by %(diff)s.",
                         month=month, amount=self._pb_money(fund_total, currency),
                         file=self._pb_money(file_total, currency),
                         diff=self._pb_money(abs(fund_total - file_total), currency))
                level = 'warn'
            if not worked_out:
                text += ' ' + _("Fund payments has not worked out this month yet: its figure is what it would work out today.")
            out.append({'code': 'fund_payments', 'level': level, 'message': text,
                        'employee_ids': []})
        return out

    @api.model
    def _pb_fund_payments_total(self, form, company, month_start, currency):
        """(total, worked_out) of the Fund payments rows for the funds whose
        pay items are on this form's compared lines, or None when Fund
        payments is not installed or no fund shares an item with the form."""
        if 'pb.fund.payee' not in self.env or 'pb.fund.payment' not in self.env:
            return None
        codes = form._pb_compare_codes()
        maps = self.env['pb.gov.form.map'].sudo().search([
            ('form_id', '=', form.id), ('company_id', '=', company.id)])
        if codes:
            maps = maps.filtered(lambda m: m.line_id.code in codes)
        rules = maps.mapped('rule_id')
        if not rules:
            return None
        Item = self.env['pb.fund.payee.item'].sudo()
        payees = Item.search([('rule_id', 'in', rules.ids),
                              ('company_id', '=', company.id)]).mapped('payee_id')
        payees = payees.filtered('active')
        if not payees:
            return None
        month = month_start.replace(day=1)
        rows = self.env['pb.fund.payment'].sudo().search([
            ('payee_id', 'in', payees.ids), ('company_id', '=', company.id),
            ('month', '=', month), ('currency_id', '=', currency.id),
            ('state', 'in', LIVE_STATES)])
        if rows:
            return currency.round(sum(rows.mapped('amount_owed'))), True
        reading = self.env['pb.fund.payment'].sudo()._pb_read(payees, month)
        total = sum(row['employee'] + row['employer'] for (pid, cid), row in reading.items()
                    if cid == currency.id)
        return currency.round(total), False
