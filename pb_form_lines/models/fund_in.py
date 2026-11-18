# -*- coding: utf-8 -*-
"""India — the provident fund ECR file and the ESI monthly contribution sheet
(WDGAP S2-B2 item 2).

IN_EPF_ECR  EPFO "Electronic Challan cum Return" version 2.0, the text file
            uploaded on the EPFO employer portal: one line per member, no
            header line, eleven fields separated by `#~#`, in this order —
              UAN, member name, gross wages, EPF wages, EPS wages, EDLI wages,
              EPF contribution remitted, EPS contribution remitted,
              EPF-EPS difference remitted, NCP days, refund of advances.
            Amounts and NCP days are whole numbers (rupees rounded half up;
            NCP days may not be a half day). EPFO's own document
            (Introduction_ECR2.0.pdf) answered 403 from here; the layout is
            the one every published guide repeats → INFERRED on the record.
IN_ESI      ESIC monthly contribution upload (the "MC template"): IP number
            (10 digits), IP name, days for which wages were paid, total
            monthly wages, reason code for zero working days, last working
            day. The template is downloaded on the ESIC portal after login →
            INFERRED.

Member numbers by probe: UAN `pb_in_uan_number` (pb_me_tax, S2-D) then the
legacy contract field `uan_number`; ESI insurance number (IP number) on the
employee (`pb_in_esi_number`, `esi_ip_number`, `esi_number`) then the legacy
contract field `esi_number`. Nothing is worked out: wages, contributions and
days are the customer's own pay items.
"""
from odoo import _, api, fields, models

from .fund_common import XLSX, digits, whole

ECR_SEP = '#~#'
ESI_HEADS = [
    'IP Number (10 Digits)',
    'IP Name( Only alphabets and space )',
    'No of Days for which wages paid/payable during the month',
    'Total Monthly Wages',
    'Reason Code for Zero workings days(numeric only; provide 0 for all other reasons- Click on the link for reference)',
    'Last Working Day( Format DD/MM/YYYY  or DD-MM-YYYY)',
]


def _ascii_name(text):
    text = ' '.join((text or '').split())
    try:
        text.encode('ascii')
    except UnicodeEncodeError:
        return None
    return text


class PbGovFormReaderFundIN(models.AbstractModel):
    _inherit = 'pb.gov.form.reader'

    @api.model
    def _pb_fund_identity_in_epf_ecr(self, form, employee):
        uan = digits(self._pb_probe(employee, ('pb_in_uan_number', 'uan_number'),
                                    ('uan_number',)))
        missing = [] if uan else [_("UAN (provident fund number)")]
        return self._pb_fund_answer(employee, {'member': uan}, missing)

    @api.model
    def _pb_fund_identity_in_esi(self, form, employee):
        ip = digits(self._pb_probe(employee, ('pb_in_esi_number', 'esi_ip_number', 'esi_number'),
                                   ('esi_number',)))
        missing = [] if ip else [_("ESI insurance number")]
        return self._pb_fund_answer(employee, {'member': ip}, missing)


class PbGovFilingFundIN(models.Model):
    _inherit = 'pb.gov.filing'

    # ---------------------------------------------------------------- EPF
    @api.model
    def _pb_fund_reasons_in_epf_ecr(self, emp, data):
        lines = emp.get('lines') or {}
        ident = emp.get('identity') or {}
        reasons = []
        if len(ident.get('member') or '') != 12:
            reasons.append(_("The UAN is not 12 digits"))
        if _ascii_name(emp.get('name')) is None:
            reasons.append(_("The name has letters the file cannot carry"))
        values = [lines.get(c) or 0.0 for c in ('GROSS', 'EPF_WAGES', 'EPS_WAGES', 'EDLI_WAGES',
                                                'EPF_EE', 'EPS_ER', 'DIFF_ER', 'NCP_DAYS', 'REFUND')]
        if any(float(v) < 0 for v in values):
            reasons.append(_("A figure is below zero"))
        if whole(lines.get('EPF_WAGES')) > whole(lines.get('GROSS')):
            reasons.append(_("EPF wages are more than gross wages"))
        return reasons

    @api.model
    def _pb_ecr_fields(self, row):
        lines = row.get('lines') or {}
        ident = row.get('identity') or {}
        return [ident.get('member') or '', _ascii_name(row.get('name')) or ''] + [
            str(whole(lines.get(code))) for code in (
                'GROSS', 'EPF_WAGES', 'EPS_WAGES', 'EDLI_WAGES', 'EPF_EE', 'EPS_ER',
                'DIFF_ER', 'NCP_DAYS', 'REFUND')]

    def _pb_render_in_epf_ecr(self, data):
        self.ensure_one()
        form = self.form_id.sudo()
        kept, left = self._pb_fund_split(form, data)
        if not kept:
            raise self._pb_fund_nobody(left)
        text = ''.join(ECR_SEP.join(self._pb_ecr_fields(r)) + '\n' for r in kept)
        for row in kept:
            ncp = float((row.get('lines') or {}).get('NCP_DAYS') or 0.0)
            if ncp != int(ncp):
                row.setdefault('checks', []).append(_("Days not paid rounded to a whole day"))
        summary = self._pb_fund_summary(data, kept, left, [(_("UAN"), 'member')], extra_lines=[
            (_("In the file"), _("Whole rupees, rounded half up"))])
        return [
            (self._pb_filename(data, 'EPF_ECR', 'txt'), text.encode('ascii'), 'text/plain'),
            (self._pb_filename(data, 'EPF_ECR_summary', 'xlsx'), summary, XLSX),
        ]

    # ---------------------------------------------------------------- ESI
    @api.model
    def _pb_fund_reasons_in_esi(self, emp, data):
        ident = emp.get('identity') or {}
        lines = emp.get('lines') or {}
        reasons = []
        if len(ident.get('member') or '') != 10:
            reasons.append(_("The ESI insurance number is not 10 digits"))
        if float(lines.get('WAGES') or 0.0) < 0 or float(lines.get('DAYS') or 0.0) < 0:
            reasons.append(_("A figure is below zero"))
        return reasons

    def _pb_render_in_esi(self, data):
        self.ensure_one()
        form = self.form_id.sudo()
        kept, left = self._pb_fund_split(form, data)
        if not kept:
            raise self._pb_fund_nobody(left)
        buf, book = self._pb_fund_book('ESI')
        text = book.add_format({'num_format': '@'})
        bold = book.add_format({'bold': True, 'text_wrap': True})
        ws = book.add_worksheet('Sheet1')
        for col, head in enumerate(ESI_HEADS):
            ws.write_string(0, col, head, bold)
        for i, row in enumerate(kept, start=1):
            ident = row.get('identity') or {}
            lines = row.get('lines') or {}
            days = float(lines.get('DAYS') or 0.0)
            # whole days, a part day counts as a day (published guides)
            n_days = int(days) if days == int(days) else int(days) + 1
            ws.write_string(i, 0, ident.get('member') or '', text)
            ws.write_string(i, 1, ' '.join(''.join(
                ch if ch.isalpha() or ch == ' ' else ' ' for ch in (row.get('name') or '')).split()))
            ws.write_number(i, 2, n_days)
            ws.write_number(i, 3, float(lines.get('WAGES') or 0.0))
            if n_days:
                ws.write_number(i, 4, 0)
            else:
                ws.write_string(i, 4, '')
                row.setdefault('checks', []).append(
                    _("No days paid: type the reason code for zero working days on the portal"))
            ws.write_string(i, 5, '', text)
        ws.set_column(0, 0, 16)
        ws.set_column(1, 1, 32)
        ws.set_column(2, 5, 22)
        self._pb_fund_check_sheet(book, data)
        book.close()
        summary = self._pb_fund_summary(data, kept, left, [(_("ESI insurance number"), 'member')])
        return [
            (self._pb_filename(data, 'ESI_monthly', 'xlsx'), buf.getvalue(), XLSX),
            (self._pb_filename(data, 'ESI_monthly_summary', 'xlsx'), summary, XLSX),
        ]

