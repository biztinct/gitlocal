# -*- coding: utf-8 -*-
"""Indonesia — year-end income-tax slip for permanent employees (BPA1, form
1721-A1), WDGAP S2-B.

SOURCE (published by the tax office, Direktorat Jenderal Pajak), page
https://www.pajak.go.id/reformdjp/coretax/template-xml-dan-converter-excel-ke-xml
row "BPA1" (both files dated 7 November 2024, nothing newer listed on
18 November 2026):
  * "BPA1 Excel to XML.xlsx"
    (https://pajak.go.id/sites/default/files/2024-12/BPA1%20Excel%20to%20XML.xlsx):
    the XML map's schema — root `A1Bulk` (TIN, ListOfA1 / A1*), each A1 = 27
    elements in a fixed order — copied unchanged into
    `tests/data/bpa1_a1bulk.xsd`; its DATA sheet (A1 "NPWP Pemotong", C1 the
    employer's number, headings B3:AB3, people from row 4) and its BPA1 sheet
    (filling rules).
  * "bpa1.zip" (https://pajak.go.id/sites/default/files/2024-12/bpa1.zip):
    the official sample, which validates against the schema.
  * The tax office's Coretax guide "Pembuatan Bukti Pemotongan PPh Pasal 21
    Tahunan A1" (version 20251223) for the line words 1-23 and the filling
    rules (FullYear = months 1-12; NumberOfMonths 0 unless Annualized; tax on
    this slip filled 0 — the system adds up the monthly slips itself).

ORDER TRAP (ledger S2B1-1): the spreadsheet puts "Status Bukti Potong" after
"Posisi" and "Kode Objek Pajak", the XML puts StatusOfWithholding right after
TaxExemptOpt. Each writer keeps its own order.

Choices (INFERRED, said on the form and in the report): StatusOfWithholding
is FullYear for a person paid January to December, PartialYear otherwise
(Annualized — for a foreigner leaving mid-year — is never chosen); GrossUpOpt
"No"; WorkForSecondEmployer "No"; tax facility "N/A"; tax object code
21-100-01; the withholding date is the last day the person was paid for;
the place-of-business number defaults to the tax number + 000000 (the
official sample's pattern). Status K/I/n (pb_me_tax) has no place in the
schema's list: such a person is left out with the reason.
"""
import io

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import cert_pdf
from .render_id import XLSX, _dec, _digits, _ptkp

MONTH_KEYS = ('1', '2', '3', '4', '5', '6', '7')
DATA_HEADS = ['Pemberi Kerja Selanjutnya', 'Masa Pajak Awal', 'Masa Pajak Akhir',
              'Tahun Pajak', 'WNI/WNA', 'No. Paspor', 'NPWP', 'Status PTKP', 'Posisi',
              'Kode Objek Pajak', 'Status Bukti Potong', 'Jumlah Bulan Bekerja', 'Gaji',
              'Opsi Gross Up', 'Tunjangan PPh', 'Tunjangan Lainnya / Lembur', 'Honorarium',
              'Asuransi', 'Natura', 'Tantiem, Bonus, Gratifikasi, THR',
              'Iuran Pensiun atau Biaya THT/JHT', 'Zakat', 'Nomor Bukti Potong Sebelumnya',
              'Fasilitas Pajak', 'PPh Pasal 21*', 'ID TKU Pemotong', 'Tanggal Pemotongan']
#: form line → schema element (amounts)
AMOUNTS = (('1', 'SalaryPensionJhtTht'), ('2', 'IncomeTaxBenefit'), ('3', 'OtherBenefit'),
           ('4', 'Honorarium'), ('5', 'InsurancePaidByEmployer'), ('6', 'Natura'),
           ('7', 'TantiemBonusThr'), ('10', 'PensionContributionJhtThtFee'), ('11', 'Zakat'))


def _whole(value):
    """Rupiah without cents, as the official sample writes them."""
    return int(round(float(value or 0.0)))


class PbGovFilingIDBPA1(models.Model):
    _inherit = 'pb.gov.filing'

    @api.model
    def _pb_bpa1_rows(self, data):
        start = fields.Date.to_date(data['period_start'])
        end = fields.Date.to_date(data['period_end'])
        settings = data.get('settings') or {}
        tin = _digits(settings.get('employer_tax_id'))
        place = _digits(settings.get('place_of_business')) or (
            tin + '000000' if len(tin) == 16 else '')
        rows, excluded = [], []
        for emp in data['employees']:
            ident = emp.get('identity') or {}
            lines = emp.get('lines') or {}
            raw_status = (lines.get('PTKP') or ident.get('ptkp') or '').strip().upper()
            status = _ptkp(raw_status)
            months = sorted(int(m[5:7]) for m in emp.get('months') or []
                            if m[:4] == str(start.year)) or [start.month, end.month]
            m_start, m_end = months[0], months[-1]
            last = fields.Date.to_date(emp.get('date_to')) or end
            person_tin = ident.get('tin') or ''
            passport = ident.get('passport') or ''
            resident = bool(person_tin) or not passport
            gross = sum(float(lines.get(k) or 0.0) for k in MONTH_KEYS)
            reasons = []
            if resident and not person_tin:
                reasons.append(_("no NIK or tax number"))
            if not status:
                if raw_status.startswith('K/I'):
                    reasons.append(_("tax status %s cannot go in the import file", raw_status))
                else:
                    reasons.append(_("no tax status (TK/K/HB)"))
            if gross <= 0:
                reasons.append(_("no gross income"))
            if any(float(lines.get(k) or 0.0) < 0 for k, _el in AMOUNTS):
                reasons.append(_("an amount below zero"))
            row = {
                'employee_id': emp['employee_id'], 'name': emp.get('name') or '',
                'second': 'No', 'm_start': m_start, 'm_end': m_end, 'year': start.year,
                'opt': 'Resident' if resident else 'Foreign',
                'passport': '' if resident else passport, 'tin': person_tin,
                'status': status, 'withholding': 'FullYear' if (m_start, m_end) == (1, 12) else 'PartialYear',
                'position': ident.get('position') or '', 'object_code': '21-100-01',
                'n_months': 0, 'gross_up': 'No', 'amounts': {k: _whole(lines.get(k)) for k, _el in AMOUNTS},
                'gross': gross, 'tax': float(lines.get('22') or 0.0),
                'certificate': 'N/A', 'place': place, 'date': min(last, end),
                'reasons': reasons, 'checks': list(emp.get('checks') or []),
            }
            if not row['position']:
                row['checks'].append(_("No position on the employee record"))
            if row['withholding'] == 'PartialYear':
                row['checks'].append(_("Paid for months %(a)s to %(b)s only", a=m_start, b=m_end))
            rows.append(row)
            if reasons:
                excluded.append(row)
        return tin, place, rows, excluded

    def _pb_render_id_bpa1(self, data):
        self.ensure_one()
        tin, place, rows, excluded = self._pb_bpa1_rows(data)
        if len(tin) not in (15, 16):
            raise UserError(_("Fill in the employer's tax number (NPWP, 15 or 16 digits) for this form on Form lines first."))
        good = [r for r in rows if not r['reasons']]
        if not good:
            raise UserError(_("Nobody in this filing can go into the import file: %s.",
                              '; '.join(sorted({x for r in rows for x in r['reasons']}))))
        return [
            (self._pb_filename(data, 'BPA1', 'xml'), self._pb_bpa1_xml(data, tin, good),
             'application/xml'),
            (self._pb_filename(data, 'BPA1_converter_data', 'xlsx'),
             self._pb_bpa1_data_xlsx(data, tin, good), XLSX),
            (self._pb_filename(data, 'BPA1_summary', 'xlsx'),
             self._pb_bpa1_summary_xlsx(data, rows, excluded), XLSX),
        ]

    # ------------------------------------------------------------------ XML
    @api.model
    def _pb_bpa1_xml(self, data, tin, rows):
        xsi = 'http://www.w3.org/2001/XMLSchema-instance'
        root = etree.Element('A1Bulk', nsmap={'xsi': xsi})
        if data.get('adviser_mark'):
            root.append(etree.Comment(' %s ' % data.get('adviser_text')))
        etree.SubElement(root, 'TIN').text = tin
        listing = etree.SubElement(root, 'ListOfA1')

        def put(parent, tag, value, nillable=False):
            el = etree.SubElement(parent, tag)
            if value in (None, '') and nillable:
                el.set('{%s}nil' % xsi, 'true')
            else:
                el.text = str(value)
            return el

        for r in rows:
            item = etree.SubElement(listing, 'A1')
            put(item, 'WorkForSecondEmployer', r['second'])
            put(item, 'TaxPeriodMonthStart', r['m_start'])
            put(item, 'TaxPeriodMonthEnd', r['m_end'])
            put(item, 'TaxPeriodYear', r['year'])
            put(item, 'CounterpartOpt', r['opt'])
            put(item, 'CounterpartPassport', r['passport'], nillable=True)
            put(item, 'CounterpartTin', r['tin'])
            put(item, 'TaxExemptOpt', r['status'])
            put(item, 'StatusOfWithholding', r['withholding'])
            put(item, 'CounterpartPosition', r['position'])
            put(item, 'TaxObjectCode', r['object_code'])
            put(item, 'NumberOfMonths', r['n_months'])
            put(item, 'SalaryPensionJhtTht', r['amounts']['1'])
            put(item, 'GrossUpOpt', r['gross_up'])
            for key, tag in AMOUNTS[1:]:
                put(item, tag, r['amounts'][key])
            put(item, 'PrevWhTaxSlip', '', nillable=True)
            put(item, 'TaxCertificate', r['certificate'])
            # the tax office's guide: filled 0, its system adds up the
            # monthly slips (BPMP) itself
            put(item, 'Article21IncomeTax', 0)
            put(item, 'IDPlaceOfBusinessActivity', r['place'])
            put(item, 'WithholdingDate', fields.Date.to_string(r['date']))
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8',
                              standalone=True, pretty_print=True)

    # ------------------------------------------------------------------ XLSX
    @api.model
    def _pb_bpa1_data_xlsx(self, data, tin, rows):
        buf, book = self._pb_workbook('BPA1')
        ws = book.add_worksheet('DATA')
        bold = book.add_format({'bold': True})
        note = book.add_format({'italic': True, 'font_color': '#B45309'})
        date_fmt = book.add_format({'num_format': 'yyyy-mm-dd'})
        ws.write_string(0, 0, 'NPWP Pemotong', bold)
        ws.write_string(0, 2, tin)
        if data.get('adviser_mark'):
            ws.write_string(1, 0, data.get('adviser_text') or '', note)
        for col, head in enumerate(DATA_HEADS, start=1):
            ws.write_string(2, col, head, bold)
        for i, r in enumerate(rows):
            row = 3 + i
            values = [r['second'], r['m_start'], r['m_end'], r['year'], r['opt'],
                      r['passport'], r['tin'], r['status'], r['position'], r['object_code'],
                      r['withholding'], r['n_months'], r['amounts']['1'], r['gross_up'],
                      r['amounts']['2'], r['amounts']['3'], r['amounts']['4'],
                      r['amounts']['5'], r['amounts']['6'], r['amounts']['7'],
                      r['amounts']['10'], r['amounts']['11'], '', r['certificate'], 0,
                      r['place']]
            for col, value in enumerate(values, start=1):
                if isinstance(value, (int, float)):
                    ws.write_number(row, col, value)
                else:
                    ws.write_string(row, col, value or '')
            ws.write_datetime(row, 27, fields.Datetime.to_datetime(r['date']), date_fmt)
        ws.set_column(1, 27, 16)
        book.close()
        return buf.getvalue()

    @api.model
    def _pb_bpa1_summary_xlsx(self, data, rows, excluded):
        buf, book = self._pb_workbook(_("Year-end tax slips summary"))
        bold = book.add_format({'bold': True})
        h1 = book.add_format({'bold': True, 'font_size': 14})
        note = book.add_format({'italic': True, 'font_color': '#B45309', 'bold': True})
        money = book.add_format({'num_format': '#,##0'})
        ws = book.add_worksheet(_("Summary"))
        r = 0
        if data.get('adviser_mark'):
            ws.write_string(r, 0, data.get('adviser_text') or '', note)
            r += 1
        ws.write_string(r, 0, _("Year-end income tax slips — permanent employees (BPA1)"), h1)
        r += 1
        for label, value in ((_("Company"), data.get('company_name') or ''),
                             (_("Tax year"), data.get('period_label') or ''),
                             (_("Currency"), data.get('currency') or '')):
            ws.write_string(r, 0, label, bold)
            ws.write_string(r, 1, value)
            r += 1
        r += 1
        ws.write_string(r, 0, _("Line"), bold)
        ws.write_string(r, 1, _("Total"), bold)
        r += 1
        for line in self.form_id.sudo()._pb_ordered_lines():
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
                 _("Months"), _("Gross income"), _("Tax withheld in the year"),
                 _("In the import file"), _("Check")]
        for col, head in enumerate(heads):
            ws2.write_string(0, col, head, bold)
        for i, row in enumerate(rows, start=1):
            ws2.write_string(i, 0, row['name'])
            ws2.write_string(i, 1, row['tin'])
            ws2.write_string(i, 2, row['passport'])
            ws2.write_string(i, 3, row['status'])
            ws2.write_string(i, 4, row['position'])
            ws2.write_string(i, 5, '%s–%s' % (row['m_start'], row['m_end']))
            ws2.write_number(i, 6, row['gross'], money)
            ws2.write_number(i, 7, row['tax'], money)
            ws2.write_string(i, 8, _("No") if row['reasons'] else _("Yes"))
            ws2.write_string(i, 9, '; '.join(row['reasons'] + row['checks']))
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, 8, 16)
        ws2.set_column(9, 9, 50)
        book.close()
        return buf.getvalue()

    # ------------------------------------------------------------- the PDF
    def _pb_certificate_id_bpa1(self, data, person):
        self.ensure_one()
        _tin, _place, rows, _excluded = self._pb_bpa1_rows(dict(data, employees=[person]))
        row = rows[0]
        spec = self._pb_cert_base(
            data, person, _("Year-end income tax slip (BPA1)"),
            'Bukti Pemotongan PPh Pasal 21 bagi Pegawai Tetap atau Pensiunan (BPA1) — 1721-A1')
        spec['file_stem'] = 'BPA1'
        ident = person.get('identity') or {}
        spec['blocks'].append({'title': _("Employee"), 'rows': [
            (_("Name"), person.get('name') or ''),
            (_("NIK or tax number"), ident.get('tin') or ''),
            (_("Passport"), row['passport']),
            (_("Tax status"), row['status'] or (ident.get('ptkp') or '')),
            (_("Position"), row['position']),
            (_("Months paid"), _("%(a)s to %(b)s", a=row['m_start'], b=row['m_end'])),
        ]})
        spec['tables'].append({
            'title': _("Income and deductions"),
            'head': [_("Line"), _("What it is"), data.get('currency') or ''],
            'rows': self._pb_cert_lines(person, codes={'1', '2', '3', '4', '5', '6', '7', '8', '10', '11', '22'},
                                        totals={'8', '22'}),
        })
        spec['notes'].insert(0, _("Lines 9 and 12 to 21 and 23 are worked out by the tax office's system from these figures and the monthly slips."))
        if row['reasons']:
            spec['notes'].insert(0, _("Not in the import file yet: %s.", '; '.join(row['reasons'])))
        return spec
