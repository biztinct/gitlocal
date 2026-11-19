# -*- coding: utf-8 -*-
"""Singapore — the CPF EZPay file (WDGAP S2-B2 item 3).

SOURCE (published by CPF Board): "CPF EZPay (FTP) File Specifications
(effective from 16 January 2025)", FTPSPEC/FILESPEC, last updated Jan 2025,
https://www.cpf.gov.sg/content/dam/web/employer/making-cpf-contributions/documents/CPFEZPayFTPSpecifications.pdf

Fixed length, 150 bytes a record. One payment advice =
  * Employer Header Record   'F' ' '  UEN(10) type(3) Sno(2) ' ' advice(2)
                             date YYYYMMDD, time HHMMSS, 'FTP.DTL'(13), spaces
  * Contribution Summary     'F' '0'  ... month YYYYMM, payment code(2),
                             amount 9(10)V99, donor count 9(7), spaces — one
                             per payment code: 01 CPF, 02 MBMF, 03 SINDA,
                             04 CDAC, 05 ECF, 10 Community Chest, 11 SDL (the
                             published sample lists them all, zero or not)
  * Contribution Detail      'F' '1'  ... month, code(2), CPF account no.(9),
                             amount 9(10)V99, ordinary wages 9(8)V99,
                             additional wages 9(8)V99, status E/L/N/O
                             (space for a fund record), name X(66), spaces
  * Employer Trailer         'F' '9'  ... record count 9(7) incl. header and
                             trailer, amount 9(13)V99 = sum of the summaries,
                             spaces
Sorted by record type, then CPF account number, then payment code (the
spec's "Sequence"). No negative amounts; none of _+$<>:;?!=[]`^|"~ anywhere.
File name <CSN><Month Paid><Advice Code>.DTL.

Choices made here (INFERRED, on the form record and in the report):
  * the CPF detail amount is the person's employee + employer CPF as their
    payslips carry it (the spec's rounding rules are the scheme's to keep;
    nothing is re-rounded or worked out here);
  * "Month Paid" in the file name = the contribution month; advice code 01;
    records end with CR LF;
  * employment status from the person's contracts in the company: joined in
    the month → N, left in the month → L, both → O, else E;
  * SDL is a summary record only (the spec has no SDL detail record) and is
    the SDL of every person in the file, including people who pay no CPF.

The CPF account number is the NRIC/FIN of a citizen or permanent resident
(S or T prefix, spec note 4), read by probe: `pb_sg_nric` / `singapore_nric_fin`
on the employee, the legacy contract field `singapore_nric_fin`, then the
national ID when it has that exact shape. Never made up.
"""
import re
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:          # pragma: no cover
    ZoneInfo = None

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .fund_common import XLSX, cents

RECORD = 150
SUMMARY_CODES = ('01', '02', '03', '04', '05', '10', '11')
FUND_CODES = {'MBMF': '02', 'SINDA': '03', 'CDAC': '04', 'ECF': '05'}
FORBIDDEN = set('_+$<>:;?!=[]`^|"~')
CPF_ACCOUNT = re.compile(r'^[ST]\d{7}[A-Z]$')
CSN = re.compile(r'^([A-Z0-9]{9,10})([A-Z]{3})(\d{2})$')
#: THE ONE PLACE the CPF account number (NRIC/FIN) is looked for, by field
#: name; then the national ID when it has the S/T shape.
NRIC_EMPLOYEE_FIELDS = ('pb_sg_nric', 'singapore_nric_fin')
NRIC_CONTRACT_FIELDS = ('singapore_nric_fin',)              # legacy pb_hr_payroll_singapore
MONTHS = ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC')


def _num(value, width):
    """An amount with two implied decimals, zero padded; None when it does
    not fit or is below zero."""
    c = cents(value)
    if c < 0:
        return None
    text = str(c).zfill(width)
    return text if len(text) == width else None


class PbGovFormReaderFundSG(models.AbstractModel):
    _inherit = 'pb.gov.form.reader'

    @api.model
    def _pb_fund_identity_sg_cpf_ezpay(self, form, employee):
        """No reader warning here: a person who pays no CPF (a foreign
        employee with SDL only) needs no CPF account number. Whether someone
        is left out is decided with their figures (`_pb_fund_reasons_…`)."""
        account = ''
        for raw in (self._pb_probe(employee, NRIC_EMPLOYEE_FIELDS, NRIC_CONTRACT_FIELDS),
                    employee.sudo().identification_id or ''):
            text = re.sub(r'\s+', '', raw or '').upper()
            if CPF_ACCOUNT.match(text):
                account = text
                break
        answer = self._pb_fund_answer(employee, {'member': account}, [])
        answer['values']['status'] = self._pb_sg_status(form, employee)
        return answer

    @api.model
    def _pb_sg_status(self, form, employee):
        """E / L / N / O for the period the reader is reading (context
        `pb_fund_period` set by the renderer and the check); E when unknown."""
        period = self.env.context.get('pb_fund_period')
        if not period or 'hr.contract' not in self.env:
            return 'E'
        start, end = (fields.Date.to_date(d) for d in period)
        contracts = self.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id), ('state', '!=', 'cancel')])
        if not contracts:
            return 'E'
        first = min(c.date_start for c in contracts if c.date_start) if contracts.filtered('date_start') else None
        ended = all(c.date_end for c in contracts)
        last = max(c.date_end for c in contracts) if ended else None
        joined = bool(first and start <= first <= end)
        left = bool(last and start <= last <= end)
        if joined and left:
            return 'O'
        if joined:
            return 'N'
        if left:
            return 'L'
        return 'E'


class PbGovFilingFundSG(models.Model):
    _inherit = 'pb.gov.filing'

    @api.model
    def _pb_sg_name(self, text):
        """(name, changed) — upper case, the forbidden characters taken out;
        None when the name has letters the file cannot carry."""
        clean = ''.join(' ' if ch in FORBIDDEN else ch for ch in (text or ''))
        clean = ' '.join(clean.split()).upper()
        try:
            clean.encode('ascii')
        except UnicodeEncodeError:
            return None, False
        changed = clean != ' '.join((text or '').split()).upper()
        return clean[:66], changed or len(clean) > 66

    @api.model
    def _pb_sg_owes(self, emp):
        lines = emp.get('lines') or {}
        return any(float(lines.get(c) or 0.0) for c in ('CPF_TOTAL', 'MBMF', 'SINDA', 'CDAC', 'ECF'))

    @api.model
    def _pb_fund_reasons_sg_cpf_ezpay(self, emp, data):
        lines = emp.get('lines') or {}
        ident = emp.get('identity') or {}
        reasons = []
        if self._pb_sg_owes(emp) and not ident.get('member'):
            reasons.append(_("No CPF account number (NRIC starting S or T) on the employee record"))
        if self._pb_sg_owes(emp) and self._pb_sg_name(emp.get('name'))[0] is None:
            reasons.append(_("The name has letters the file cannot carry"))
        for code, width in (('CPF_TOTAL', 12), ('OW', 10), ('AW', 10), ('MBMF', 12),
                            ('SINDA', 12), ('CDAC', 12), ('ECF', 12), ('SDL', 12)):
            if _num(lines.get(code), width) is None:
                reasons.append(_("A figure is below zero or too large for the file"))
                break
        return reasons

    @api.model
    def _pb_sg_csn(self, data):
        raw = re.sub(r'\s+', '', (data.get('settings') or {}).get('employer_tax_id') or '').upper()
        m = CSN.match(raw)
        if not m:
            raise UserError(_("Fill in the CPF submission number (CSN) for this form on Form lines first: the company's UEN, the payment type and the serial number, for example 201912345APTE01."))
        return m.groups()

    def _pb_render_sg_cpf_ezpay(self, data):
        self.ensure_one()
        uen, ptype, sno = self._pb_sg_csn(data)
        form = self.form_id.sudo()
        kept, left = self._pb_fund_split(form, data)
        if not kept:
            raise self._pb_fund_nobody(left)
        start = fields.Date.to_date(data['period_start'])
        month = start.strftime('%Y%m')
        advice = '01'
        key = 'F%%s%s%s%s %s' % (uen.ljust(10), ptype, sno, advice)
        now = datetime.now(ZoneInfo('Asia/Singapore')) if ZoneInfo else datetime.now()

        header = (key % ' ') + now.strftime('%Y%m%d') + now.strftime('%H%M%S') + 'FTP.DTL'.ljust(13)
        details, sums, donors = [], {c: 0 for c in SUMMARY_CODES}, {c: 0 for c in SUMMARY_CODES}
        for row in kept:
            lines = row.get('lines') or {}
            ident = row.get('identity') or {}
            sums['11'] += cents(lines.get('SDL'))
            if not self._pb_sg_owes(row):
                continue
            name, changed = self._pb_sg_name(row.get('name'))
            if changed:
                row.setdefault('checks', []).append(_("Name written without the characters the file cannot carry"))
            account = ident.get('member') or ''
            cpf = cents(lines.get('CPF_TOTAL'))
            if cpf or float(lines.get('OW') or 0.0) or float(lines.get('AW') or 0.0):
                details.append((account, '01', (key % '1') + month + '01' + account
                                + _num(lines.get('CPF_TOTAL'), 12) + _num(lines.get('OW'), 10)
                                + _num(lines.get('AW'), 10) + (ident.get('status') or 'E')
                                + name.ljust(66)))
                sums['01'] += cpf
            for fund, code in FUND_CODES.items():
                amount = cents(lines.get(fund))
                if not amount:
                    continue
                details.append((account, code, (key % '1') + month + code + account
                                + _num(lines.get(fund), 12) + '0' * 10 + '0' * 10 + ' '
                                + name.ljust(66)))
                sums[code] += amount
                donors[code] += 1
        summaries = [(key % '0') + month + code + str(sums[code]).zfill(12)
                     + str(donors[code] if code in ('02', '03', '04', '05', '10') else 0).zfill(7)
                     for code in SUMMARY_CODES]
        details.sort(key=lambda d: (d[0], d[1]))
        count = 1 + len(summaries) + len(details) + 1
        trailer = (key % '9') + str(count).zfill(7) + str(sum(sums.values())).zfill(15)
        records = [header] + summaries + [d[2] for d in details] + [trailer]
        for rec in records:
            if len(rec) > RECORD:
                raise UserError(_("The file could not be made."))
        text = ''.join(rec.ljust(RECORD) + '\r\n' for rec in records)
        filename = '%s%s%s%s%s.DTL' % (uen, ptype, sno, MONTHS[start.month - 1] + str(start.year),
                                        advice)
        summary = self._pb_fund_summary(data, kept, left, [(_("CPF account number"), 'member')],
                                        extra_lines=[(_("CPF submission number (CSN)"),
                                                      uen + ptype + sno)])
        return [
            (filename, text.encode('ascii'), 'text/plain'),
            (self._pb_filename(data, 'CPF_EZPay_summary', 'xlsx'), summary, XLSX),
        ]
