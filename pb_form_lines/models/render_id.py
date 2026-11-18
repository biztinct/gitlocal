# -*- coding: utf-8 -*-
"""Indonesia — monthly income-tax slips for permanent employees (BPMP).

SOURCE (published by the tax office, Direktorat Jenderal Pajak):
  * "BPMP Excel to XML v.3.xlsx" (converter, updated 17 April 2025) and
    "bpmp.zip" (XML template, 7 November 2024), both listed on
    https://www.pajak.go.id/reformdjp/coretax/template-xml-dan-converter-excel-ke-xml
    under "Bupot PPh Pasal 21/26". The converter's own XML map carries the
    schema `MONTHLYPAYROLL`: root `MmPayrollBulk` (TIN, ListOfMmPayroll /
    MmPayroll*), each MmPayroll = TaxPeriodMonth, TaxPeriodYear,
    CounterpartOpt (Resident|Foreign), CounterpartPassport (nillable),
    CounterpartTin (nillable), StatusTaxExemption (TK/0..TK/3, K/0..K/3,
    HB/0..HB/3), Position, TaxCertificate, TaxObjectCode, Gross (> 0),
    Rate (>= 0), IDPlaceOfBusinessActivity, WithholdingDate (YYYY-MM-DD).
  * Its DATA sheet: A1 "NPWP Pemotong", B1 the employer's number; row 4 the
    column heads B..N in the order above; people from row 5.

What this file is: the bulk import of the monthly withholding slips (form
1721-VIII) for every month except the last month of the tax year (that month
is reported on the year-end slip — Step 2 wave 2). The monthly return itself
is assembled by the tax office's system from these slips.

Choices made here (said in the report, changeable):
  * the Rate is the person's own tax withheld ÷ gross × 100 from their
    payslips, unless HR puts a pay item on the "Rate" line;
  * the withholding date is the last day of the period;
  * the tax object code defaults to 21-100-01 (permanent employees) and the
    tax facility to N/A;
  * the published schema lists the facility values N/A, DTP, ECT while the
    converter's own reference sheet and sample say ETC — INFERRED, only N/A is
    written.
"""
import io
import re

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PTKP = ('TK/0', 'TK/1', 'TK/2', 'TK/3', 'K/0', 'K/1', 'K/2', 'K/3',
        'HB/0', 'HB/1', 'HB/2', 'HB/3')
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
DATA_HEADS = ['Masa Pajak', 'Tahun Pajak', 'Status Pegawai', 'NPWP/NIK/TIN',
              'Nomor Passport', 'Status', 'Posisi', 'Sertifikat/Fasilitas',
              'Kode Objek Pajak', 'Penghasilan Kotor', 'Tarif', 'ID TKU',
              'Tgl Pemotongan']


def _digits(text):
    return ''.join(ch for ch in (text or '') if ch.isdigit())


def _ptkp(text):
    """'k/1', 'K1', 'K-1' -> 'K/1'; anything else -> ''."""
    m = re.fullmatch(r'\s*(TK|K|HB)\s*[/\-]?\s*([0-3])\s*', (text or '').upper())
    return '%s/%s' % m.groups() if m else ''


def _dec(value):
    """A decimal as the tax office's files print it: no thousands mark, a
    point, no trailing zeros ("6300001", "1.75")."""
    text = ('%.2f' % float(value or 0.0)).rstrip('0').rstrip('.')
    return text or '0'


class PbGovFilingID(models.Model):
    _inherit = 'pb.gov.filing'

    @api.model
    def _pb_id_rows(self, data):
        """(rows, excluded) — every person as the import file needs them, and
        the people left out of the XML with the plain reason."""
        start = fields.Date.to_date(data['period_start'])
        end = fields.Date.to_date(data['period_end'])
        settings = data.get('settings') or {}
        tin = _digits(settings.get('employer_tax_id'))
        place = _digits(settings.get('place_of_business')) or (tin + '000000' if len(tin) == 16 else '')
        rows, excluded = [], []
        for emp in data['employees']:
            ident = emp.get('identity') or {}
            lines = emp.get('lines') or {}
            status = _ptkp(lines.get('PTKP') or ident.get('ptkp'))
            gross = float(lines.get('GROSS') or 0.0)
            rate = float(lines.get('RATE') or 0.0)
            person_tin = ident.get('tin') or ''
            passport = ident.get('passport') or ''
            resident = bool(person_tin) or not passport
            reasons = []
            if resident and not person_tin:
                reasons.append(_("no NIK or tax number"))
            if not status:
                reasons.append(_("no tax status (TK/K/HB)"))
            if gross <= 0:
                reasons.append(_("no gross income"))
            if rate < 0:
                reasons.append(_("rate below zero"))
            row = {
                'employee_id': emp['employee_id'], 'name': emp.get('name') or '',
                'month': start.month, 'year': start.year,
                'opt': 'Resident' if resident else 'Foreign',
                'tin': person_tin, 'passport': '' if resident else passport,
                'status': status, 'position': ident.get('position') or '',
                'certificate': 'N/A', 'object_code': '21-100-01',
                'gross': gross, 'rate': rate, 'tax': float(lines.get('PPH21') or 0.0),
                'place': place, 'date': end, 'reasons': reasons,
                'checks': list(emp.get('checks') or []),
            }
            if not row['position']:
                row['checks'].append(_("No position on the employee record"))
            rows.append(row)
            if reasons:
                excluded.append(row)
        return tin, rows, excluded

    def _pb_render_id_bpmp(self, data):
        self.ensure_one()
        tin, rows, excluded = self._pb_id_rows(data)
        if len(tin) not in (15, 16):
            raise UserError(_("Fill in the employer's tax number (NPWP, 15 or 16 digits) for this form on Form lines first."))
        good = [r for r in rows if not r['reasons']]
        if not good:
            raise UserError(_("Nobody in this filing can go into the import file: %s.",
                              '; '.join(sorted({x for r in rows for x in r['reasons']}))))
        return [
            (self._pb_filename(data, 'BPMP', 'xml'), self._pb_id_xml(data, tin, good),
             'application/xml'),
            (self._pb_filename(data, 'BPMP_converter_data', 'xlsx'),
             self._pb_id_data_xlsx(data, tin, good), XLSX),
            (self._pb_filename(data, 'BPMP_summary', 'xlsx'),
             self._pb_id_summary_xlsx(data, rows, excluded), XLSX),
        ]

    # ------------------------------------------------------------------ XML
    @api.model
    def _pb_id_xml(self, data, tin, rows):
        xsi = 'http://www.w3.org/2001/XMLSchema-instance'
        root = etree.Element('MmPayrollBulk', nsmap={'xsi': xsi})
        if data.get('adviser_mark'):
            root.append(etree.Comment(' %s ' % data.get('adviser_text')))
        etree.SubElement(root, 'TIN').text = tin
        listing = etree.SubElement(root, 'ListOfMmPayroll')

        def nil(parent, tag, value):
            el = etree.SubElement(parent, tag)
            if value:
                el.text = value
            else:
                el.set('{%s}nil' % xsi, 'true')
            return el

        for r in rows:
            item = etree.SubElement(listing, 'MmPayroll')
            etree.SubElement(item, 'TaxPeriodMonth').text = str(r['month'])
            etree.SubElement(item, 'TaxPeriodYear').text = str(r['year'])
            etree.SubElement(item, 'CounterpartOpt').text = r['opt']
            nil(item, 'CounterpartPassport', r['passport'])
            nil(item, 'CounterpartTin', r['tin'])
            etree.SubElement(item, 'StatusTaxExemption').text = r['status']
            etree.SubElement(item, 'Position').text = r['position']
            etree.SubElement(item, 'TaxCertificate').text = r['certificate']
            etree.SubElement(item, 'TaxObjectCode').text = r['object_code']
            etree.SubElement(item, 'Gross').text = _dec(r['gross'])
            etree.SubElement(item, 'Rate').text = _dec(r['rate'])
            etree.SubElement(item, 'IDPlaceOfBusinessActivity').text = r['place']
            etree.SubElement(item, 'WithholdingDate').text = fields.Date.to_string(r['date'])
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8',
                              standalone=True, pretty_print=True)

    # ------------------------------------------------------------------ XLSX
    @api.model
    def _pb_workbook(self, title):
        import xlsxwriter
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        book.set_properties({'title': title, 'author': '', 'company': ''})
        return buf, book

    @api.model
    def _pb_id_data_xlsx(self, data, tin, rows):
        """The DATA sheet of the tax office's converter, same cells: paste
        rows 5 onwards into the converter, or read it as it is."""
        buf, book = self._pb_workbook('BPMP')
        ws = book.add_worksheet('DATA')
        bold = book.add_format({'bold': True})
        note = book.add_format({'italic': True, 'font_color': '#B45309'})
        date_fmt = book.add_format({'num_format': 'yyyy-mm-dd'})
        ws.write_string(0, 0, 'NPWP Pemotong', bold)
        ws.write_string(0, 1, tin)
        if data.get('adviser_mark'):
            ws.write_string(1, 0, data.get('adviser_text') or '', note)
        for col, head in enumerate(DATA_HEADS, start=1):
            ws.write_string(3, col, head, bold)
        for i, r in enumerate(rows):
            row = 4 + i
            ws.write_number(row, 1, r['month'])
            ws.write_number(row, 2, r['year'])
            ws.write_string(row, 3, r['opt'])
            ws.write_string(row, 4, r['tin'])
            ws.write_string(row, 5, r['passport'])
            ws.write_string(row, 6, r['status'])
            ws.write_string(row, 7, r['position'])
            ws.write_string(row, 8, r['certificate'])
            ws.write_string(row, 9, r['object_code'])
            ws.write_number(row, 10, r['gross'])
            ws.write_number(row, 11, r['rate'])
            ws.write_string(row, 12, r['place'])
            ws.write_datetime(row, 13, fields.Datetime.to_datetime(r['date']), date_fmt)
        ws.set_column(1, 13, 16)
        book.close()
        return buf.getvalue()

    @api.model
    def _pb_id_summary_xlsx(self, data, rows, excluded):
        buf, book = self._pb_workbook(_("Monthly tax slips summary"))
        bold = book.add_format({'bold': True})
        h1 = book.add_format({'bold': True, 'font_size': 14})
        note = book.add_format({'italic': True, 'font_color': '#B45309', 'bold': True})
        money = book.add_format({'num_format': '#,##0.00'})
        ws = book.add_worksheet(_("Summary"))
        r = 0
        if data.get('adviser_mark'):
            ws.write_string(r, 0, data.get('adviser_text') or '', note)
            r += 1
        ws.write_string(r, 0, _("Monthly income tax slips — permanent employees (BPMP)"), h1)
        r += 1
        ws.write_string(r, 0, _("Company"), bold)
        ws.write_string(r, 1, data.get('company_name') or '')
        r += 1
        ws.write_string(r, 0, _("Period"), bold)
        ws.write_string(r, 1, data.get('period_label') or '')
        r += 1
        ws.write_string(r, 0, _("Currency"), bold)
        ws.write_string(r, 1, data.get('currency') or '')
        r += 2
        ws.write_string(r, 0, _("Line"), bold)
        ws.write_string(r, 1, _("Total"), bold)
        r += 1
        form = self.form_id.sudo()
        for line in form._pb_ordered_lines():
            if line.code not in (data.get('lines') or {}):
                continue
            ws.write_string(r, 0, '%s — %s' % (line.code, line.label))
            ws.write_number(r, 1, float(data['lines'][line.code] or 0.0), money)
            r += 1
        r += 1
        ws.write_string(r, 0, _("People in the import file"), bold)
        ws.write_number(r, 1, len(rows) - len(excluded))
        r += 1
        ws.write_string(r, 0, _("People left out of the import file"), bold)
        ws.write_number(r, 1, len(excluded))
        r += 2
        for warn in data.get('warnings') or []:
            ws.write_string(r, 0, warn.get('message') or '')
            r += 1
        ws.set_column(0, 0, 60)
        ws.set_column(1, 1, 22)

        ws2 = book.add_worksheet(_("People"))
        heads = [_("Name"), _("Tax number"), _("Passport"), _("Tax status"), _("Position"),
                 _("Gross income"), _("Tax withheld"), _("Rate (%)"),
                 _("In the import file"), _("Check")]
        for col, head in enumerate(heads):
            ws2.write_string(0, col, head, bold)
        for i, row in enumerate(rows, start=1):
            ws2.write_string(i, 0, row['name'])
            ws2.write_string(i, 1, row['tin'])
            ws2.write_string(i, 2, row['passport'])
            ws2.write_string(i, 3, row['status'])
            ws2.write_string(i, 4, row['position'])
            ws2.write_number(i, 5, row['gross'], money)
            ws2.write_number(i, 6, row['tax'], money)
            ws2.write_number(i, 7, row['rate'])
            ws2.write_string(i, 8, _("No") if row['reasons'] else _("Yes"))
            ws2.write_string(i, 9, '; '.join(row['reasons'] + row['checks']))
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, 8, 16)
        ws2.set_column(9, 9, 50)
        book.close()
        return buf.getvalue()
