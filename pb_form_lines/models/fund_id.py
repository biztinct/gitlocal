# -*- coding: utf-8 -*-
"""Indonesia — the two BPJS monthly sheets (WDGAP S2-B2 item 1).

ID_BPJS_TK  BPJS Ketenagakerjaan, the wage report uploaded on SIPP ("Upload
            Upah": NIK, KPJ number, name, date of birth, wage, month). The
            template is downloaded inside SIPP after login; it is not
            published, so the columns follow published guides and are marked
            INFERRED (source on the form record).
ID_BPJS_KES BPJS Kesehatan, the member / contribution sheet for e-Dabu (NIK,
            card number, name, date of birth, wage, employee and employer
            contribution). The e-Dabu template is not published either:
            INFERRED.

Member numbers come from the employee record (`pb_bpjs_employment_number`,
`pb_bpjs_health_number`, pb_employee_vault, read by probe) and the NIK from
the national ID. No number → the person is left out with the reason.
Contributions are the customer's own pay items (G2): nothing is worked out
here.
"""
from odoo import _, api, fields, models

from .fund_common import XLSX, digits, whole


#: THE ONE PLACE the BPJS member numbers are looked for (pb_employee_vault).
BPJS_TK_FIELDS = ('pb_bpjs_employment_number',)
BPJS_KES_FIELDS = ('pb_bpjs_health_number',)


def _ddmmyyyy(text):
    day = fields.Date.to_date(text) if text else None
    return day.strftime('%d-%m-%Y') if day else ''


class PbGovFormReaderFundID(models.AbstractModel):
    _inherit = 'pb.gov.form.reader'

    @api.model
    def _pb_id_nik(self, employee):
        nik = digits(employee.sudo().identification_id)
        return nik if len(nik) == 16 else ''

    @api.model
    def _pb_fund_identity_id_bpjs_tk(self, form, employee):
        nik = self._pb_id_nik(employee)
        kpj = digits(self._pb_probe(employee, BPJS_TK_FIELDS))
        missing = []
        if not kpj:
            missing.append(_("BPJS Ketenagakerjaan number"))
        if not nik:
            missing.append(_("NIK (16 digits)"))
        return self._pb_fund_answer(employee, {'nik': nik, 'member': kpj}, missing)

    @api.model
    def _pb_fund_identity_id_bpjs_kes(self, form, employee):
        nik = self._pb_id_nik(employee)
        card = digits(self._pb_probe(employee, BPJS_KES_FIELDS))
        missing = []
        if not card:
            missing.append(_("BPJS Kesehatan card number"))
        if not nik:
            missing.append(_("NIK (16 digits)"))
        return self._pb_fund_answer(employee, {'nik': nik, 'member': card}, missing)


class PbGovFilingFundID(models.Model):
    _inherit = 'pb.gov.filing'

    @api.model
    def _pb_fund_reasons_id_bpjs_tk(self, emp, data):
        reasons = []
        if float((emp.get('lines') or {}).get('WAGE') or 0.0) <= 0:
            reasons.append(_("No wage for BPJS"))
        return reasons

    @api.model
    def _pb_fund_reasons_id_bpjs_kes(self, emp, data):
        return self._pb_fund_reasons_id_bpjs_tk(emp, data)

    # -------------------------------------------------------- Ketenagakerjaan
    def _pb_render_id_bpjs_tk(self, data):
        self.ensure_one()
        form = self.form_id.sudo()
        kept, left = self._pb_fund_split(form, data)
        if not kept:
            raise self._pb_fund_nobody(left)
        start = fields.Date.to_date(data['period_start'])
        buf, book = self._pb_fund_book('SIPP')
        text = book.add_format({'num_format': '@'})
        bold = book.add_format({'bold': True})
        ws = book.add_worksheet('Upload Upah')
        heads = ['NIK', 'NO KPJ', 'NAMA LENGKAP', 'TGL LAHIR', 'UPAH', 'BLN/THN']
        for col, head in enumerate(heads):
            ws.write_string(0, col, head, bold)
        for i, row in enumerate(kept, start=1):
            ident = row.get('identity') or {}
            ws.write_string(i, 0, ident.get('nik') or '', text)
            ws.write_string(i, 1, ident.get('member') or '', text)
            ws.write_string(i, 2, (row.get('name') or '').upper())
            ws.write_string(i, 3, _ddmmyyyy(ident.get('birthday')), text)
            ws.write_number(i, 4, whole((row.get('lines') or {}).get('WAGE')))
            ws.write_string(i, 5, start.strftime('%m-%Y'), text)
        ws.set_column(0, 1, 20)
        ws.set_column(2, 2, 34)
        ws.set_column(3, 5, 14)
        self._pb_fund_check_sheet(book, data)
        book.close()
        upload = buf.getvalue()
        summary = self._pb_fund_summary(data, kept, left, [
            (_("NIK"), 'nik'), (_("BPJS Ketenagakerjaan number"), 'member')])
        return [
            (self._pb_filename(data, 'BPJS_TK_upah', 'xlsx'), upload, XLSX),
            (self._pb_filename(data, 'BPJS_TK_summary', 'xlsx'), summary, XLSX),
        ]

    # -------------------------------------------------------------- Kesehatan
    def _pb_render_id_bpjs_kes(self, data):
        self.ensure_one()
        form = self.form_id.sudo()
        kept, left = self._pb_fund_split(form, data)
        if not kept:
            raise self._pb_fund_nobody(left)
        buf, book = self._pb_fund_book('e-Dabu')
        text = book.add_format({'num_format': '@'})
        bold = book.add_format({'bold': True})
        ws = book.add_worksheet('Data Peserta')
        heads = ['NIK', 'NO KARTU', 'NAMA', 'TGL LAHIR', 'GAJI', 'IURAN PEKERJA',
                 'IURAN PEMBERI KERJA', 'TOTAL IURAN']
        for col, head in enumerate(heads):
            ws.write_string(0, col, head, bold)
        for i, row in enumerate(kept, start=1):
            ident = row.get('identity') or {}
            lines = row.get('lines') or {}
            ws.write_string(i, 0, ident.get('nik') or '', text)
            ws.write_string(i, 1, ident.get('member') or '', text)
            ws.write_string(i, 2, (row.get('name') or '').upper())
            ws.write_string(i, 3, _ddmmyyyy(ident.get('birthday')), text)
            ws.write_number(i, 4, whole(lines.get('WAGE')))
            ws.write_number(i, 5, whole(lines.get('KES_EE')))
            ws.write_number(i, 6, whole(lines.get('KES_ER')))
            ws.write_number(i, 7, whole(lines.get('KES_EE')) + whole(lines.get('KES_ER')))
        ws.set_column(0, 1, 20)
        ws.set_column(2, 2, 34)
        ws.set_column(3, 7, 16)
        self._pb_fund_check_sheet(book, data)
        book.close()
        summary = self._pb_fund_summary(data, kept, left, [
            (_("NIK"), 'nik'), (_("BPJS Kesehatan card number"), 'member')])
        return [
            (self._pb_filename(data, 'BPJS_Kesehatan', 'xlsx'), buf.getvalue(), XLSX),
            (self._pb_filename(data, 'BPJS_Kesehatan_summary', 'xlsx'), summary, XLSX),
        ]
