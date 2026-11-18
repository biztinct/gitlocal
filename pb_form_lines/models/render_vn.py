# -*- coding: utf-8 -*-
"""Vietnam — personal income tax declaration of the payer, Mẫu số 05/KK-TNCN.

TWO LAYOUTS, both shipped as data (`data/forms_vn.xml`):

  * VN_05KK_TT89 — Thông tư 89/2026/TT-BTC, periods from 1 July 2026,
    QUARTERLY only, indicators [15]–[45]. Source: the comparison published by
    FAST (fast.com.vn, "So sánh Mẫu 05/KK-TNCN theo Thông tư 89/2026/TT-BTC và
    Thông tư 80", citing Công văn 5746/CT-CS). The official appendix of
    Thông tư 89/2026 itself could not be read from here, so the form is
    marked INFERRED.
  * VN_05KK_TT80 — Thông tư 80/2021/TT-BTC Phụ lục II, periods up to 30 June
    2026 (Article 100 of Thông tư 89 lets it be used until the tax office says
    otherwise), monthly or quarterly, indicators [16]–[32]. Source: the
    indicator guide published by ECN (ecn.net.vn, "Tờ khai thuế TNCN
    05/KK-TNCN hướng dẫn chi tiết"). Also a secondary source → INFERRED.

The official XML of the tax office's declaration software is NOT produced: its
schema could not be confirmed from a published source (handover §S2-A.5). The
workbook gives the declaration in the form's own line order, ready to type
into the tax office's software, and a second sheet with every person.
"""
import io

from odoo import _, api, fields, models

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class PbGovFilingVN(models.Model):
    _inherit = 'pb.gov.filing'

    def _pb_render_vn_05kk_tt89(self, data):
        self.ensure_one()
        return self._pb_vn_05kk(data, 'TT89')

    def _pb_render_vn_05kk_tt80(self, data):
        self.ensure_one()
        return self._pb_vn_05kk(data, 'TT80')

    def _pb_vn_05kk(self, data, version):
        return [(self._pb_filename(data, '05KK-TNCN', 'xlsx'),
                 self._pb_vn_workbook(data, version), XLSX)]

    @api.model
    def _pb_vn_period_words(self, data):
        start = fields.Date.to_date(data['period_start'])
        end = fields.Date.to_date(data['period_end'])
        if start.month == end.month and start.year == end.year:
            return 'Tháng %02d năm %d' % (start.month, start.year)
        quarter = (start.month - 1) // 3 + 1
        return 'Quý %d năm %d' % (quarter, start.year)

    def _pb_vn_workbook(self, data, version):
        import xlsxwriter
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        book.set_properties({'title': 'Mẫu số 05/KK-TNCN', 'author': '', 'company': ''})
        bold = book.add_format({'bold': True})
        h1 = book.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        center = book.add_format({'align': 'center'})
        note = book.add_format({'italic': True, 'bold': True, 'font_color': '#B45309'})
        money = book.add_format({'num_format': '#,##0'})
        head = book.add_format({'bold': True, 'bg_color': '#EEF0F8', 'border': 1, 'text_wrap': True})
        cell = book.add_format({'border': 1, 'text_wrap': True})
        cell_money = book.add_format({'border': 1, 'num_format': '#,##0'})

        form = self.form_id.sudo()
        settings = data.get('settings') or {}
        company = self.company_id.sudo()
        ws = book.add_worksheet('05-KK-TNCN')
        r = 0
        if data.get('adviser_mark'):
            ws.write_string(r, 0, data.get('adviser_text') or '', note)
            r += 1
        ws.merge_range(r, 0, r, 4, 'TỜ KHAI THUẾ THU NHẬP CÁ NHÂN', h1)
        r += 1
        ws.merge_range(r, 0, r, 4, '(Áp dụng cho tổ chức, cá nhân trả thu nhập chịu thuế từ tiền lương, tiền công) — Mẫu số 05/KK-TNCN', center)
        r += 1
        basis = 'Thông tư 89/2026/TT-BTC' if version == 'TT89' else 'Thông tư 80/2021/TT-BTC'
        ws.merge_range(r, 0, r, 4, '(Ban hành kèm theo %s)' % basis, center)
        r += 2
        header = [
            ('[01]', 'Kỳ tính thuế', self._pb_vn_period_words(data)),
            ('[02]', 'Lần đầu', 'X'),
            ('[04]', 'Tên người nộp thuế', company.name or ''),
            ('[05]', 'Mã số thuế', settings.get('employer_tax_id') or company.vat or ''),
            ('[06]', 'Địa chỉ', ', '.join(p for p in (company.street, company.street2) if p)),
            ('[07]', 'Xã/phường' if version == 'TT89' else 'Quận/huyện', company.city or ''),
            ('[08]', 'Tỉnh/thành phố', company.state_id.name or ''),
        ]
        for code, label, value in header:
            ws.write_string(r, 0, code, bold)
            ws.write_string(r, 1, label)
            ws.write_string(r, 2, value or '')
            r += 1
        r += 1
        ws.write_string(r, 0, 'STT', head)
        ws.write_string(r, 1, 'Chỉ tiêu', head)
        ws.write_string(r, 2, 'Mã chỉ tiêu', head)
        ws.write_string(r, 3, 'Đơn vị tính', head)
        ws.write_string(r, 4, 'Số người / Số tiền', head)
        r += 1
        totals = data.get('lines') or {}
        for n, line in enumerate(form._pb_ordered_lines(), start=1):
            if line.kind == 'text':
                continue
            ws.write_number(r, 0, n, cell)
            ws.write_string(r, 1, line.official_label or line.label, cell)
            ws.write_string(r, 2, '[%s]' % line.code, cell)
            ws.write_string(r, 3, 'Người' if line.kind == 'count' else 'VNĐ', cell)
            ws.write_number(r, 4, float(totals.get(line.code) or 0), cell_money)
            r += 1
        ws.set_column(0, 0, 8)
        ws.set_column(1, 1, 70)
        ws.set_column(2, 3, 14)
        ws.set_column(4, 4, 22)

        # the people behind the figures (a working sheet, not part of the form)
        ws2 = book.add_worksheet(_("People"))
        money_lines = [l for l in form._pb_ordered_lines()
                       if l.kind in ('money', 'computed') and l.scope == 'employee'
                       and not l.base_line_id]
        heads = [_("Name"), _("Personal tax code"), _("Tax resident")] + \
            ['[%s] %s' % (l.code, l.label) for l in money_lines] + [_("Check")]
        for col, text in enumerate(heads):
            ws2.write_string(0, col, text, bold)
        for i, emp in enumerate(data.get('employees') or [], start=1):
            ident = emp.get('identity') or {}
            ws2.write_string(i, 0, emp.get('name') or '')
            ws2.write_string(i, 1, ident.get('tax_code') or '')
            ws2.write_string(i, 2, _("Yes") if emp.get('resident') else _("No"))
            for j, line in enumerate(money_lines, start=3):
                ws2.write_number(i, j, float((emp.get('lines') or {}).get(line.code) or 0), money)
            ws2.write_string(i, 3 + len(money_lines), '; '.join(emp.get('checks') or []))
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, 2 + len(money_lines), 18)
        ws2.set_column(3 + len(money_lines), 3 + len(money_lines), 40)
        if data.get('warnings'):
            ws3 = book.add_worksheet(_("To check"))
            for i, warn in enumerate(data['warnings']):
                ws3.write_string(i, 0, warn.get('message') or '')
            ws3.set_column(0, 0, 100)
        book.close()
        return buf.getvalue()
