# -*- coding: utf-8 -*-
"""India — the employer's salary tax paperwork, as FIGURES for the return
preparer (WDGAP S2-B).

  * IN_FORM16B  — Form No. 16 Part B (Annexure-I), Income-tax Rules 1962
    (Notification 28/2023 + rows 19-21 of Notification 112/2024): tax years
    up to 2025-26.
  * IN_FORM130C — Form No. 130 Part C (Annexure-I), Income-tax Rules 2026
    (G.S.R. 198(E), 20 March 2026): tax year 2026-27 onwards.
  * IN_24Q      — Form No. 24Q Annexure I (columns 314-329, every quarter) and
    Annexure II (columns 330-390, January - March quarter only): quarters up
    to January - March 2026.
  * IN_FORM138  — Form No. 138 Annexure I (columns A-O) and Annexure II
    (columns A-BQ, January - March quarter only): from April 2026.

The tax department's upload file (FVU / the portal's utility) is NOT made:
the workbooks are figures in the published column order "for your return
preparer" (handover S2-B1 item 3), said on the form and on the files.

Annexure II reads the year-end certificate form of the same tax year (Form
16 Part B or Form 130 Part C) through the reader, so HR maps the year's items
once; when that form is not set up, the sheet says so and nothing is guessed.
Nothing here works tax out: rows 13 to 17 are figures a pay scheme already
holds, or empty.
"""
import io

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from odoo.addons.pb_hr_payroll_formula.models import tax_year as TY

from .render_vn import XLSX

ANNEX1_OLD = [
    ('314', 'Sl. No.', 'n'),
    ('315', 'Employee reference number provided by employer/PPO number, if available', 'ref'),
    ('316', 'PAN of the employee/specified senior citizen', 'pan'),
    ('317', 'Name of the employee/specified senior citizen', 'name'),
    ('318', 'Section Code', 'blank'),
    ('319', 'Date of payment/credit', 'date'),
    ('320', 'Date of deduction', 'date'),
    ('321', 'Amount Paid or Credited', 'PAID'),
    ('322', 'Tax', 'TAX'),
    ('323', 'Surcharge', 'SURCH'),
    ('324', 'Health and Education Cess', 'CESS'),
    ('325', 'Total TDS (322+323+324)', 'TDS'),
    ('326', 'Total TDS deposited Rs.', 'blank'),
    ('327', 'Date of deposit', 'blank'),
    ('328', 'Reason for non-deduction/lower/higher deduction', 'blank'),
    ('329', 'Number of the certificate u/s 197 for non/lower deduction', 'blank'),
]
ANNEX1_NEW = [
    ('A', 'Sl. No.', 'n'),
    ('B', 'Challan Reference No.', 'blank'),
    ('C', 'PAN of the employee/specified senior citizen', 'pan'),
    ('D', 'Name of the employee/specified senior citizen', 'name'),
    ('E', 'Employee reference number / PPO number, if available', 'ref'),
    ('F', 'Section Code', 'blank'),
    ('G', 'Date of payment/credit', 'date'),
    ('H', 'Date of deduction', 'date'),
    ('I', 'Amount Paid or Credited', 'PAID'),
    ('J', 'Total Tax Deducted (tax + surcharge + Health and Education Cess)', 'TDS'),
    ('K', 'Whether total amount of tax deducted has been deposited (Yes/No)', 'blank'),
    ('L', 'Total Tax deposited', 'blank'),
    ('M', 'Date of deposit', 'blank'),
    ('N', 'Reason for non/lower/higher deduction', 'blank'),
    ('O', 'Certificate number under section 395(1)', 'blank'),
]
ANNEX2_OLD = [
    ('330', 'Serial number', 'n'), ('331', 'PAN of the employee', 'pan'),
    ('332A', 'Name of the employee', 'name'),
    ('332B', 'Whether opting out from taxation u/s 115BAC(1A)', 'optout'),
    ('333', 'Deductee type (Senior Citizen/Super Senior Citizen/Others)', 'dtype'),
    ('334', 'Date from and date up to employed with current employer', 'span'),
    ('335', 'Gross Salary as per section 17(1)', '1a'), ('336', 'Value of perquisites under section 17(2)', '1b'),
    ('337', 'Profits in lieu of salary under section 17(3)', '1c'),
    ('338', 'Total gross salary from current employer', '1d'),
    ('339', 'Reported salary from other employer(s)', '1e'),
    ('340', 'Travel concession or assistance 10(5)', '2a'), ('341', 'Death-cum-retirement gratuity 10(10)', '2b'),
    ('342', 'Commuted value of pension 10(10A)', '2c'), ('343', 'Leave salary encashment 10(10AA)', '2d'),
    ('344', 'House rent allowance 10(13A)', '2e'), ('345', 'PAN of landlord', 'blank'),
    ('346A', 'Other special allowances 10(14)', '2f'), ('346B', 'Any other exemption under section 10', '2h'),
    ('347', 'Total exemption under section 10', '2i'),
    ('348', 'Standard deduction 16(ia)', '4a'), ('349', 'Entertainment allowance 16(ii)', '4b'),
    ('350', 'Tax on employment 16(iii)', '4c'), ('351', 'Income chargeable under "Salaries"', '6'),
    ('352', 'Income (or admissible loss) from house property reported, 192(2B)', '7a'),
    ('353', 'PAN of lender', 'blank'), ('354', 'Income under the head other sources offered for TDS', '7b'),
    ('355', 'Gross total income', '9'),
    ('356', '80C gross', '10a'), ('357', '80C deductible', '10a'), ('358', '80CCC gross', '10b'),
    ('359', '80CCC deductible', '10b'), ('360', '80CCD(1) gross', '10c'), ('361', '80CCD(1) deductible', '10c'),
    ('362', '80CCD(1B) gross', '10e'), ('363', '80CCD(1B) deductible', '10e'),
    ('364A', '80CCD(2) gross', '10f'), ('364B', '80CCD(2) deductible', '10f'),
    ('365A', '80CCH employee gross', '10i'), ('365B', '80CCH employee deductible', '10i'),
    ('366A', '80CCH Central Government gross', '10j'), ('366B', '80CCH Central Government deductible', '10j'),
    ('367A', '80D gross', '10g'), ('367B', '80D deductible', '10g'), ('368', '80E gross', '10h'),
    ('369', '80E deductible', '10h'), ('370', '80G gross', '10k'), ('371', '80G qualifying', '10k'),
    ('372', '80G deductible', '10k'), ('373', '80TTA gross', '10l'), ('374', '80TTA qualifying', '10l'),
    ('375', '80TTA deductible', '10l'), ('376', 'Other Chapter VI-A gross', '10n'),
    ('377', 'Other Chapter VI-A qualifying', '10n'), ('378', 'Other Chapter VI-A deductible', '10n'),
    ('379', 'Total deduction under Chapter VI-A', '11'), ('380', 'Total taxable income', '12'),
    ('381', 'Income-tax on total income', '13'), ('382', 'Rebate under section 87A', '14'),
    ('383', 'Surcharge', '15'), ('384', 'Health and education cess', '16'), ('385', 'Relief under section 89', '18'),
    ('386', 'Net tax liability', 'liability'),
    ('387', 'Total amount of tax deducted at source by the current employer for the whole year', 'TDS'),
    ('388', 'Reported amount of tax deducted at source by other employer(s)', '19'),
    ('388A', 'Amount reported as per section 192(2B), other tax deducted or collected at source', '20'),
    ('389', 'Total amount of tax deducted/collected at source for the whole year', 'tds_total'),
    ('390', 'Shortfall (+) / excess (-)', 'shortfall'),
]
ANNEX2_NEW = [
    ('A', 'Sl. No.', 'n'), ('B', 'PAN of the employee', 'pan'), ('C', 'Name of the employee', 'name'),
    ('D', 'Whether opting out from taxation under section 202(1)', 'optout'),
    ('E', 'Deductee type (Senior Citizen/Super Senior Citizen/Others)', 'dtype'),
    ('F', 'Date from which employed with current employer in the current Tax Year', 'from'),
    ('G', 'Date up to which employed with current employer in the current Tax Year', 'to'),
    ('H', 'Gross Salary as per section 16', '1a'), ('I', 'Value of perquisites under section 17', '1b'),
    ('J', 'Profits in lieu of salary under section 18', '1c'), ('K', 'Total gross salary from current employer', '1d'),
    ('L', 'Reported salary from other employer(s)', '1e'), ('M', 'Travel concession', '2a'),
    ('N', 'House rent allowance', '2b'), ('O', 'PAN of landlord(s)', 'blank'),
    ('P', 'Other special allowances', '2c'), ('Q', 'Any other salary component exempt under section 11', '2e'),
    ('R', 'Total exemption', '2f'), ('S', 'Tax on employment', '4a'), ('T', 'Standard deduction', '4b'),
    ('U', 'Gratuity', '4c'), ('V', 'Commuted value of pension', '4d'), ('W', 'Compensation to workmen', '4e'),
    ('X', 'Voluntary retirement or termination', '4f'), ('Y', 'Leave salary encashment', '4g'),
    ('Z', 'Income chargeable under "Salaries"', '6'), ('AA', 'Loss from house property', '7b'),
    ('AB', 'PAN of lender(s)', 'blank'), ('AC', 'Amount chargeable under any other head offered for TDS', '7a'),
    ('AD', 'Gross Total Income', '9'),
    ('AE', 's.123 gross', '10a'), ('AF', 's.123 deductible', '10a'), ('AG', 's.124(3) gross', '10b'),
    ('AH', 's.124(3) deductible', '10b'), ('AI', 's.124(1)(a) gross', '10c'), ('AJ', 's.124(1)(a) deductible', '10c'),
    ('AK', 's.126 gross', '10d'), ('AL', 's.126 deductible', '10d'), ('AM', 's.129 gross', '10e'),
    ('AN', 's.129 deductible', '10e'), ('AO', 's.125(1) gross', '10f'), ('AP', 's.125(1) deductible', '10f'),
    ('AQ', 's.125(2) gross', '10g'), ('AR', 's.125(2) deductible', '10g'), ('AS', 's.133 gross', '10h'),
    ('AT', 's.133 qualifying', '10h'), ('AU', 's.133 deductible', '10h'), ('AV', 's.153 gross', '10i'),
    ('AW', 's.153 qualifying', '10i'), ('AX', 's.153 deductible', '10i'), ('AY', 'Other Chapter VIII: section', 'blank'),
    ('AZ', 'Other Chapter VIII gross', '10k'), ('BA', 'Other Chapter VIII qualifying', '10k'),
    ('BB', 'Other Chapter VIII deductible', '10k'), ('BC', 'Total deduction under Chapter VIII', '11'),
    ('BD', 'Total taxable income', '12'), ('BE', 'Income Tax on total income', '13'),
    ('BF', 'Rebate under section 156', '14'), ('BG', 'Surcharge', '15'), ('BH', 'Health and Education Cess', '16'),
    ('BI', 'Form 39 Acknowledgment Number', 'blank'), ('BJ', 'Income on which section 157 relief is claimed', 'blank'),
    ('BK', 'Income-tax relief under section 157', '18'), ('BL', 'Net tax liability', 'liability'),
    ('BM', 'Tax deducted by the current employer for the whole year', 'TDS'),
    ('BN', 'Reported tax deducted by other employer(s)', '19'),
    ('BO', 'Amount reported as per section 392(4), other tax deducted or collected at source', '20'),
    ('BP', 'Total tax deducted or collected for the whole tax year', 'tds_total'),
    ('BQ', 'Shortfall (+) or excess (-)', 'shortfall'),
]
TEXT_SOURCES = ('ref', 'pan', 'name', 'blank', 'date', 'optout', 'dtype', 'span', 'from', 'to')


def _age_type(birthday, year_end):
    """Senior Citizen (60+), Super Senior Citizen (80+) at the end of the tax
    year, else Others — from the date of birth (INFERRED rule of thumb)."""
    if not birthday:
        return 'Others'
    age = relativedelta(year_end, birthday).years
    if age >= 80:
        return 'Super Senior Citizen'
    if age >= 60:
        return 'Senior Citizen'
    return 'Others'


class PbGovFilingIN(models.Model):
    _inherit = 'pb.gov.filing'

    # ------------------------------------------------------------- helpers
    @api.model
    def _pb_in_derived(self, lines, source):
        g = lambda c: float(lines.get(c) or 0.0)   # noqa: E731
        if source == 'TAX':
            return g('TDS') - g('SURCH') - g('CESS')
        if source == 'liability':
            return g('13') + g('15') + g('16') - g('14') - g('18')
        if source == 'tds_total':
            return g('TDS') + g('19') + g('20')
        if source == 'shortfall':
            return (g('13') + g('15') + g('16') - g('14') - g('18')) - (g('TDS') + g('19') + g('20'))
        return g(source)

    @api.model
    def _pb_in_text(self, person, source, n, extra):
        ident = person.get('identity') or {}
        if source == 'n':
            return n
        if source == 'ref':
            return ident.get('employee_number') or ''
        if source == 'pan':
            return ident.get('pan') or ''
        if source == 'name':
            return person.get('name') or ''
        if source == 'optout':
            return 'Yes' if ident.get('regime') == 'old' else 'No'
        if source == 'dtype':
            return extra.get('dtype') or 'Others'
        if source == 'date':
            return extra.get('date') or ''
        if source == 'span':
            return '%s - %s' % (person.get('date_from') or '', person.get('date_to') or '')
        if source == 'from':
            return person.get('date_from') or ''
        if source == 'to':
            return person.get('date_to') or ''
        return ''

    def _pb_in_sheet(self, book, name, title, cols, rows, fmt):
        """One annexure: a title, the column numbers, the headings, one row
        per entry, a totals row for the amounts."""
        ws = book.add_worksheet(name)
        r = 0
        if fmt['mark_text']:
            ws.write_string(r, 0, fmt['mark_text'], fmt['note'])
            r += 1
        ws.write_string(r, 0, title, fmt['h1'])
        r += 1
        ws.write_string(r, 0, _("Figures for your return preparer: the upload file itself is made with the tax department's own utility."), fmt['muted'])
        r += 2
        for c, (code, heading, _src) in enumerate(cols):
            ws.write_string(r, c, code, fmt['code'])
            ws.write_string(r + 1, c, heading, fmt['head'])
        ws.set_row(r + 1, 60)
        r += 2
        sums = {}
        for i, (person, extra) in enumerate(rows, start=1):
            for c, (_code, _h, src) in enumerate(cols):
                if src in TEXT_SOURCES or src == 'n':
                    value = self._pb_in_text(person, src, i, extra)
                    if isinstance(value, int):
                        ws.write_number(r, c, value, fmt['cell'])
                    else:
                        ws.write_string(r, c, value, fmt['cell'])
                else:
                    value = self._pb_in_derived(extra.get('lines') or person.get('lines') or {}, src)
                    ws.write_number(r, c, value, fmt['money'])
                    sums[c] = sums.get(c, 0.0) + value
            r += 1
        if rows:
            ws.write_string(r, 1, _("Total"), fmt['head'])
            for c, value in sums.items():
                ws.write_number(r, c, value, fmt['total'])
        ws.set_column(0, len(cols), 18)
        ws.freeze_panes(6 if fmt['mark_text'] else 5, 2)
        return ws

    def _pb_in_formats(self, book, data):
        return {
            'h1': book.add_format({'bold': True, 'font_size': 14}),
            'muted': book.add_format({'italic': True, 'font_color': '#6B7280'}),
            'note': book.add_format({'italic': True, 'bold': True, 'font_color': '#B45309'}),
            'code': book.add_format({'bold': True, 'align': 'center', 'bg_color': '#EEF0F8', 'border': 1}),
            'head': book.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'border': 1,
                                     'bg_color': '#F4F3FB'}),
            'cell': book.add_format({'border': 1}),
            'money': book.add_format({'border': 1, 'num_format': '#,##0.00'}),
            'total': book.add_format({'border': 1, 'num_format': '#,##0.00', 'bold': True,
                                      'bg_color': '#F4F3FB'}),
            'mark_text': data.get('adviser_text') if data.get('adviser_mark') else '',
        }

    # ---------------------------------------------- Form 16 B / Form 130 C
    def _pb_render_in_form16b(self, data):
        self.ensure_one()
        return self._pb_in_certificate_workbook(data, 'Form 16 Part B')

    def _pb_render_in_form130c(self, data):
        self.ensure_one()
        return self._pb_in_certificate_workbook(data, 'Form 130 Part C')

    def _pb_in_certificate_workbook(self, data, title):
        import xlsxwriter
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        book.set_properties({'title': title, 'author': '', 'company': ''})
        fmt = self._pb_in_formats(book, data)
        form = self.form_id.sudo()
        lines = [l for l in form._pb_ordered_lines() if l.scope == 'employee' and l.kind != 'text']
        ws = book.add_worksheet(_("Summary"))
        r = 0
        if fmt['mark_text']:
            ws.write_string(r, 0, fmt['mark_text'], fmt['note'])
            r += 1
        ws.write_string(r, 0, '%s — %s' % (title, form.name or ''), fmt['h1'])
        r += 1
        ws.write_string(r, 0, _("Figures for your return preparer: the upload file itself is made with the tax department's own utility."), fmt['muted'])
        r += 2
        for label, value in ((_("Company"), data.get('company_name') or ''),
                             (_("Tax year"), data.get('period_label') or ''),
                             (_("Currency"), data.get('currency') or '')):
            ws.write_string(r, 0, label, fmt['head'])
            ws.write_string(r, 1, value)
            r += 1
        r += 1
        totals = data.get('lines') or {}
        for line in form._pb_ordered_lines():
            if line.code not in totals:
                continue
            ws.write_string(r, 0, '%s — %s' % (line.code, line.label))
            ws.write_number(r, 1, float(totals[line.code] or 0.0), fmt['money'])
            r += 1
        r += 1
        for warn in data.get('warnings') or []:
            ws.write_string(r, 0, warn.get('message') or '')
            r += 1
        ws.set_column(0, 0, 70)
        ws.set_column(1, 1, 22)

        ws2 = book.add_worksheet(_("Employees"))
        heads = [_("Name"), 'PAN', _("Opting out of the new regime")] + \
            ['%s %s' % (l.code, l.label) for l in lines] + [_("Check")]
        for c, head in enumerate(heads):
            ws2.write_string(0, c, head, fmt['head'])
        ws2.set_row(0, 60)
        for i, person in enumerate(data.get('employees') or [], start=1):
            ident = person.get('identity') or {}
            ws2.write_string(i, 0, person.get('name') or '')
            ws2.write_string(i, 1, ident.get('pan') or '')
            ws2.write_string(i, 2, 'Yes' if ident.get('regime') == 'old' else 'No')
            for c, line in enumerate(lines, start=3):
                ws2.write_number(i, c, float((person.get('lines') or {}).get(line.code) or 0.0), fmt['money'])
            ws2.write_string(i, 3 + len(lines), '; '.join(person.get('checks') or []))
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, 2 + len(lines), 14)
        ws2.freeze_panes(1, 1)
        book.close()
        return [(self._pb_filename(data, title.replace(' ', '_'), 'xlsx'), buf.getvalue(), XLSX)]

    def _pb_in_cert(self, data, person, title, official):
        self.ensure_one()
        out = self._pb_cert_base(data, person, title, official)
        out['file_stem'] = 'Form16' if 'Form 16' in title else 'Form130'
        ident = person.get('identity') or {}
        out['blocks'].append({'title': _("Employee"), 'rows': [
            (_("Name"), person.get('name') or ''),
            ('PAN', ident.get('pan') or ''),
            (_("Employee number"), ident.get('employee_number') or ''),
            (_("Position"), ident.get('position') or ''),
            (_("Opting out of the new regime"), 'Yes' if ident.get('regime') == 'old' else 'No'),
            (_("Paid from – to"), '%s – %s' % (person.get('date_from') or '', person.get('date_to') or '')),
        ]})
        out['tables'].append({
            'title': _("Salary, deductions and tax"),
            'head': [_("Row"), _("What it is"), data.get('currency') or ''],
            'rows': self._pb_cert_lines(person, totals={'1d', '6', '9', '12', '17', '21', 'TDS'}),
        })
        out['notes'].insert(0, _("Figures for your return preparer. The official certificate's Part A comes from the tax department's portal; rows 13 to 17 show only figures your pay scheme holds."))
        return out

    def _pb_certificate_in_form16b(self, data, person):
        return self._pb_in_cert(data, person, _("Salary and tax deducted — Form 16 Part B (figures)"),
                                'Form No. 16, Part B (Annexure-I)')

    def _pb_certificate_in_form130c(self, data, person):
        return self._pb_in_cert(data, person, _("Salary and tax deducted — Form 130 Part C (figures)"),
                                'Form No. 130, Part C (Annexure-I)')

    # ---------------------------------------------- Form 24Q / Form 138
    def _pb_render_in_24q(self, data):
        self.ensure_one()
        return self._pb_in_quarter(data, 'Form 24Q', ANNEX1_OLD, ANNEX2_OLD, 'IN_FORM16B')

    def _pb_render_in_form138(self, data):
        self.ensure_one()
        return self._pb_in_quarter(data, 'Form 138', ANNEX1_NEW, ANNEX2_NEW, 'IN_FORM130C')

    def _pb_in_quarter(self, data, title, annex1, annex2, year_form):
        import xlsxwriter
        Reader = self.env['pb.gov.form.reader']
        rec = self.sudo()
        start = fields.Date.to_date(data['period_start'])
        end = fields.Date.to_date(data['period_end'])
        schemes = [s['id'] for s in data.get('schemes') or []]
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        # Annexure I: one row per person per month paid
        rows1 = []
        month = start
        while month <= end:
            m_end = month + relativedelta(months=1, days=-1)
            part = Reader._pb_read(rec.form_id, rec.company_id, month, m_end,
                                   scheme_ids=schemes, currency_id=data.get('currency_id'))
            for person in part.get('employees') or []:
                rows1.append((person, {'date': fields.Date.to_string(m_end),
                                       'lines': person.get('lines') or {}}))
            month = month + relativedelta(months=1)
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        book.set_properties({'title': title, 'author': '', 'company': ''})
        fmt = self._pb_in_formats(book, data)
        self._pb_in_sheet(book, 'Annexure I', '%s — %s — %s' % (title, 'Annexure I', data.get('period_label') or ''),
                          annex1, rows1, fmt)
        # Annexure II: only with the last quarter of the tax year
        ty_start, ty_end = TY.tax_year_bounds(TY.month_of(rec.form_id.year_start_month or 4), start)
        notes = []
        if end == ty_end:
            form = self.env['pb.gov.form'].sudo().search([('code', '=', year_form)], limit=1)
            year = None
            if form:
                year = Reader._pb_read(form, rec.company_id, ty_start, ty_end, scheme_ids=schemes,
                                       currency_id=data.get('currency_id'))
            blocks = [w for w in (year or {}).get('warnings') or [] if w.get('level') == 'block']
            if year is None or blocks:
                ws = book.add_worksheet('Annexure II')
                ws.write_string(0, 0, _("Annexure II reads the year's salary figures from “%s”. Put the year's pay items on its lines on Form lines, then prepare this quarter again.",
                                        form.name if form else year_form), fmt['note'])
                for i, w in enumerate(blocks, start=2):
                    ws.write_string(i, 0, w.get('message') or '')
                ws.set_column(0, 0, 120)
                notes.append(_("Annexure II is empty: the year-end certificate form is not set up yet."))
            else:
                rows2 = []
                for person in year.get('employees') or []:
                    emp = Emp.browse(person['employee_id'])
                    birthday = emp.birthday if 'birthday' in emp._fields else None
                    rows2.append((person, {'dtype': _age_type(birthday, ty_end),
                                           'lines': person.get('lines') or {}}))
                self._pb_in_sheet(book, 'Annexure II', '%s — %s — %s' % (
                    title, 'Annexure II', Reader._pb_form(form).name), annex2, rows2, fmt)
        # the points to check
        ws = book.add_worksheet(_("To check"))
        r = 0
        for text in notes + [w.get('message') or '' for w in data.get('warnings') or []]:
            ws.write_string(r, 0, text)
            r += 1
        for person in data.get('employees') or []:
            for check in person.get('checks') or []:
                ws.write_string(r, 0, '%s — %s' % (person.get('name') or '', check))
                r += 1
        ws.set_column(0, 0, 110)
        book.close()
        return [(self._pb_filename(data, title.replace(' ', '_'), 'xlsx'), buf.getvalue(), XLSX)]
