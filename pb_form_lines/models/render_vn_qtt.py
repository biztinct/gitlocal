# -*- coding: utf-8 -*-
"""Vietnam — annual personal income tax finalisation of the payer, Mẫu số
05/QTT-TNCN, with appendices 05-1, 05-2 and 05-3/BK-QTT-TNCN, and a
tax-withheld statement for each person (WDGAP S2-B).

TWO LAYOUTS (`data/forms_year_end_vn.xml`), chosen by tax year:
  * VN_05QTT_TT89 — Thông tư 89/2026/TT-BTC (in force 1 July 2026), tax year
    2026 onwards: indicators [15]–[45]; 05-1 columns [06]–[25] (totals
    [26]–[39]), 05-2 [06]–[21] (totals [22]–[32]), 05-3 [06]–[16].
  * VN_05QTT_TT80 — Thông tư 80/2021/TT-BTC Phụ lục II, tax years up to 2025:
    indicators [16]–[41]; 05-1 [06]–[27] (totals [28]–[43]), 05-2 [06]–[16]
    (totals [17]–[22]), 05-3 the same.
Sources and what is INFERRED: on each form record and in the S2-B1 report.

DEPENDANTS (handover S2-B1 item 2, FACTS S2F-5). The number on 05-1 and the
rows of 05-3 come from the dependant records valid in the tax year
(`vietnam.employee.dependent`, status "eligible", effective dates overlapping
the year; months from/to within the year). Where the running contract
carries a "registered tax dependants" figure (the contract component whose
code is in the system parameter `pb_me_tax.vn_registered_dependants_codes`,
default VNREGISTER — the same parameter pb_me_tax reads, so a customer's own
label works for both) and it differs, the person gets a "to check" row: the
figure is never picked silently and never blocks.

The per-person statement is an information copy laid out like the sample
03/TNCN of Thông tư 91/2026 (fields [01]–[19]); it carries no official
series or number (those come from the company's own registered series).
"""
import io

from odoo import _, api, fields, models

from . import cert_pdf
from .render_vn import XLSX

REGISTER_PARAM = 'pb_me_tax.vn_registered_dependants_codes'
REGISTER_DEFAULT = 'VNREGISTER'
RELATION_VI = {'spouse': 'Vợ/Chồng', 'child': 'Con', 'parent': 'Bố/Mẹ',
               'sibling': 'Anh/Chị/Em', 'other': 'Khác'}

#: (column, Vietnamese heading, source). Sources: a line code, or one of
#: name / tax_code / id_no / blank / deps / nonres.
COLS = {
    'TT89': {
        'line_taxable': '22', 'line_withheld': '33', 'line_payable': '40',
        'line_due': '44', 'line_over': '45', 'line_small': '41',
        '05-1': [
            ('06', 'STT', 'n'), ('07', 'Họ và tên', 'name'), ('08', 'Mã số thuế', 'tax_code'),
            ('09', 'Số ĐDCN/Hộ chiếu (trường hợp chưa có MST)', 'id_no'),
            ('10', 'Cá nhân uỷ quyền quyết toán thay', 'blank'),
            ('11', 'CN nước ngoài ủy quyền quyết toán dưới 12 tháng', 'blank'),
            ('12', 'Tổng số thu nhập chịu thuế phát sinh trong kỳ', '22'),
            ('13', 'Trong đó: TNCT được miễn theo Hiệp định', 'TREATY'),
            ('14', 'Trong đó: TNCT được miễn theo quy định của Hợp đồng dầu khí', '27'),
            ('15', 'Số lượng NPT tính giảm trừ', 'deps'),
            ('16', 'Tổng số tiền giảm trừ gia cảnh', 'FAMDED'),
            ('17', 'Từ thiện, nhân đạo, khuyến học', 'CHARITY'),
            ('18', 'Bảo hiểm được trừ', 'INS'),
            ('19', 'Quĩ hưu trí tự nguyện được trừ', 'PENSION'),
            ('20', 'Thu nhập tính thuế', 'ASSESS'),
            ('21', 'Tổng số thuế TNCN đã khấu trừ', '33'),
            ('22', 'Tổng số thuế phải nộp', '40'),
            ('23', 'Số thuế đã nộp thừa', '45'),
            ('24', 'Số thuế còn phải nộp', '44'),
            ('25', 'Cá nhân có số thuế được miễn do có số thuế còn phải nộp từ 50.000 đồng trở xuống', '41'),
        ],
        'total_from_1': 26,
        '05-2': [
            ('06', 'STT', 'n'), ('07', 'Họ và tên', 'name'), ('08', 'Mã số thuế', 'tax_code'),
            ('09', 'Số ĐDCN/Hộ chiếu', 'id_no'), ('10', 'Cá nhân không cư trú', 'nonres'),
            ('11', 'TNCT: Tổng số', '22'),
            ('12', 'Trong đó: TNCT từ phí mua BH nhân thọ, BH không bắt buộc khác của DN BH không thành lập tại Việt Nam cho người lao động', '25'),
            ('13', 'Số thuế TNCN được miễn: Cá nhân là nhân lực công nghiệp công nghệ số chất lượng cao', '42'),
            ('14', 'Số thuế TNCN được miễn: Cá nhân là nhân lực công nghệ cao', '43'),
            ('15', 'Các khoản bảo hiểm được trừ', 'INS'),
            ('16', 'Thu nhập miễn thuế: Theo Hiệp định', 'TREATY'),
            ('17', 'Thu nhập miễn thuế: Theo quy định của Hợp đồng dầu khí', '27'),
            ('18', 'Thu nhập miễn thuế: Từ thực hiện nhiệm vụ khoa học, công nghệ và đổi mới sáng tạo', '28'),
            ('19', 'Thu nhập của cá nhân là chuyên gia hỗ trợ khởi nghiệp sáng tạo theo quy định', '29'),
            ('20', 'Số thuế TNCN đã khấu trừ: Tổng số', '33'),
            ('21', 'Trong đó: Số thuế từ phí mua BH nhân thọ, BH không bắt buộc khác', '36'),
        ],
        'total_from_2': 22,
    },
    'TT80': {
        'line_taxable': '23', 'line_withheld': '31', 'line_payable': '38',
        'line_due': '40', 'line_over': '41', 'line_small': '39',
        '05-1': [
            ('06', 'STT', 'n'), ('07', 'Họ và tên', 'name'), ('08', 'Mã số thuế', 'tax_code'),
            ('09', 'Số CMND/CCCD/SĐDCN/Hộ chiếu (trường hợp chưa có MST)', 'id_no'),
            ('10', 'Cá nhân uỷ quyền quyết toán thay', 'blank'),
            ('11', 'CN nước ngoài ủy quyền quyết toán dưới 12 tháng', 'blank'),
            ('12', 'Tổng số TNCT', '23'),
            ('13', 'Trong đó: TNCT tại tổ chức trước khi điều chuyển', 'blank'),
            ('14', 'TNCT được miễn theo Hiệp định', 'TREATY'),
            ('15', 'TNCT được miễn theo quy định của Hợp đồng dầu khí', '27'),
            ('16', 'Số lượng NPT tính giảm trừ', 'deps'),
            ('17', 'Tổng số tiền giảm trừ gia cảnh', 'FAMDED'),
            ('18', 'Từ thiện, nhân đạo, khuyến học', 'CHARITY'),
            ('19', 'Bảo hiểm được trừ', 'INS'),
            ('20', 'Quĩ hưu trí tự nguyện được trừ', 'PENSION'),
            ('21', 'Thu nhập tính thuế', 'ASSESS'),
            ('22', 'Tổng số thuế TNCN đã khấu trừ', '31'),
            ('23', 'Trong đó: số thuế đã khấu trừ tại tổ chức trước khi điều chuyển', 'blank'),
            ('24', 'Tổng số thuế phải nộp', '38'),
            ('25', 'Số thuế đã nộp thừa', '41'),
            ('26', 'Số thuế còn phải nộp', '40'),
            ('27', 'Cá nhân có số thuế được miễn do có số thuế còn phải nộp từ 50.000 đồng trở xuống', '39'),
        ],
        'total_from_1': 28,
        '05-2': [
            ('06', 'STT', 'n'), ('07', 'Họ và tên', 'name'), ('08', 'Mã số thuế', 'tax_code'),
            ('09', 'Số CMND/CCCD/Hộ chiếu', 'id_no'), ('10', 'Cá nhân không cư trú', 'nonres'),
            ('11', 'TNCT: Tổng số', '23'),
            ('12', 'Trong đó: TNCT từ phí mua BH nhân thọ, BH không bắt buộc khác của DN BH không thành lập tại Việt Nam cho người lao động', '26'),
            ('13', 'TNCT được miễn theo Hiệp định', 'TREATY'),
            ('14', 'TNCT được miễn theo quy định của Hợp đồng dầu khí', '27'),
            ('15', 'Số thuế TNCN đã khấu trừ: Tổng số', '31'),
            ('16', 'Trong đó: Số thuế từ phí mua BH nhân thọ, BH không bắt buộc khác', '34'),
        ],
        'total_from_2': 17,
    },
}
DEP_COLS = [
    ('06', 'STT'), ('07', 'Họ và tên người nộp thuế là người lao động tại tổ chức trả thu nhập'),
    ('08', 'MST của người nộp thuế là người lao động tại tổ chức trả thu nhập'),
    ('09', 'Họ và tên người phụ thuộc'), ('10', 'Ngày sinh người phụ thuộc'),
    ('11', 'MST của người phụ thuộc'), ('12', 'Loại giấy tờ (Số ĐDCN/Hộ chiếu/GKS) người phụ thuộc'),
    ('13', 'Số giấy tờ'), ('14', 'Quan hệ với người nộp thuế'),
    ('15', 'Thời gian tính giảm trừ trong năm tính thuế: Từ tháng'),
    ('16', 'Thời gian tính giảm trừ trong năm tính thuế: Đến tháng'),
]


def _version(code):
    return 'TT89' if (code or '').upper().endswith('TT89') else 'TT80'


class PbGovFormReaderVNQTT(models.AbstractModel):
    _inherit = 'pb.gov.form.reader'

    # ------------------------------------------------------- dependants
    @api.model
    def _pb_vn_dependants(self, employee, start, end):
        """Dependant rows valid in [start, end] (eligible only), or None when
        this database keeps no dependant records."""
        if 'vietnam.employee.dependent' not in self.env:
            return None
        Dep = self.env['vietnam.employee.dependent'].sudo().with_context(active_test=False)
        rows = []
        for dep in Dep.search([('employee_id', '=', employee.id)], order='effective_from, id'):
            if dep.status != 'eligible':
                continue
            first = dep.effective_from or start
            last = dep.effective_to or end
            if first > end or last < start:
                continue
            rows.append({
                'name': dep.name or '', 'birthday': dep.date_of_birth,
                'tax_code': (dep.tax_registration_number or '').strip(),
                'id_no': (dep.identification_number or '').strip(),
                'relation': RELATION_VI.get(dep.relationship, dep.relationship or ''),
                'from_month': max(first, start).month, 'to_month': min(last, end).month,
            })
        return rows

    @api.model
    def _pb_vn_registered(self, employee, start, end):
        """The "registered tax dependants" figure on the contract running in
        the year (the latest), or None when there is none."""
        Contract = self.env['hr.contract'].sudo().with_context(active_test=False)
        if 'advantages_ids' not in Contract._fields:
            return None
        raw = self.env['ir.config_parameter'].sudo().get_param(
            REGISTER_PARAM, REGISTER_DEFAULT) or ''
        codes = {c.strip().upper() for c in raw.split(',') if c.strip()}
        contract = Contract.search([
            ('employee_id', '=', employee.id), ('date_start', '<=', end),
            '|', ('date_end', '=', False), ('date_end', '>=', start)],
            order='date_start desc, id desc', limit=1)
        lines = contract.advantages_ids.filtered(
            lambda a: (a.advantage_template_id.code or '').upper() in codes)
        if not lines:
            return None
        return int(round(sum(lines.mapped('amount'))))

    def _pb_checks_vn_05qtt_tt89(self, form, company, out):
        return self._pb_vn_qtt_checks(form, company, out)

    def _pb_checks_vn_05qtt_tt80(self, form, company, out):
        return self._pb_vn_qtt_checks(form, company, out)

    @api.model
    def _pb_vn_qtt_checks(self, form, company, out):
        """Dependants per person + the "to check" rows (never a block)."""
        start = fields.Date.to_date(out['period_start'])
        end = fields.Date.to_date(out['period_end'])
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        differ = []
        for person in out['employees']:
            emp = Emp.browse(person['employee_id'])
            deps = self._pb_vn_dependants(emp, start, end)
            person['dependants'] = deps or []
            count = len(deps or [])
            person['dependant_count'] = count
            registered = self._pb_vn_registered(emp, start, end)
            if registered is not None and deps is not None and registered != count:
                person['checks'].append(_(
                    "To check: %(records)s dependants on record for the year, %(contract)s registered on the contract",
                    records=count, contract=registered))
                differ.append(emp.id)
        if differ:
            text = _("1 person has a different number of dependants on record and on the contract: to check.") \
                if len(differ) == 1 else _(
                    "%s people have a different number of dependants on record and on the contract: to check.", len(differ))
            self._pb_warn(out, 'dependants_to_check', text, employee_ids=differ)
        return out


class PbGovFilingVNQTT(models.Model):
    _inherit = 'pb.gov.filing'

    def _pb_render_vn_05qtt_tt89(self, data):
        self.ensure_one()
        return [(self._pb_filename(data, '05QTT-TNCN', 'xlsx'),
                 self._pb_vn_qtt_workbook(data, 'TT89'), XLSX)]

    def _pb_render_vn_05qtt_tt80(self, data):
        self.ensure_one()
        return [(self._pb_filename(data, '05QTT-TNCN', 'xlsx'),
                 self._pb_vn_qtt_workbook(data, 'TT80'), XLSX)]

    @api.model
    def _pb_vn_cell(self, person, source, n):
        ident = person.get('identity') or {}
        lines = person.get('lines') or {}
        if source == 'n':
            return n
        if source == 'name':
            return person.get('name') or ''
        if source == 'tax_code':
            return ident.get('tax_code') or ''
        if source == 'id_no':
            return '' if ident.get('tax_code') else (ident.get('national_id') or ident.get('passport') or '')
        if source == 'nonres':
            return 'X' if not person.get('resident') else ''
        if source == 'blank':
            return ''
        if source == 'deps':
            return int(person.get('dependant_count') or 0)
        return float(lines.get(source) or 0.0)

    def _pb_vn_qtt_workbook(self, data, version):
        import xlsxwriter
        spec = COLS[version]
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        book.set_properties({'title': 'Mẫu số 05/QTT-TNCN', 'author': '', 'company': ''})
        bold = book.add_format({'bold': True})
        h1 = book.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        center = book.add_format({'align': 'center'})
        note = book.add_format({'italic': True, 'bold': True, 'font_color': '#B45309'})
        head = book.add_format({'bold': True, 'bg_color': '#EEF0F8', 'border': 1, 'text_wrap': True,
                                'valign': 'top'})
        cell = book.add_format({'border': 1, 'text_wrap': True})
        cell_money = book.add_format({'border': 1, 'num_format': '#,##0'})
        total_money = book.add_format({'border': 1, 'num_format': '#,##0', 'bold': True,
                                       'bg_color': '#F4F3FB'})
        form = self.form_id.sudo()
        settings = data.get('settings') or {}
        company = self.company_id.sudo()
        year = fields.Date.to_date(data['period_start']).year
        basis = 'Thông tư 89/2026/TT-BTC' if version == 'TT89' else 'Thông tư 80/2021/TT-BTC'

        def top(ws, title, width, main=False):
            """Title and the header indicators: the declaration names the
            payer in [05]/[06], each appendix in [04]/[05]."""
            r = 0
            if data.get('adviser_mark'):
                ws.write_string(r, 0, data.get('adviser_text') or '', note)
                r += 1
            ws.merge_range(r, 0, r, width, title, h1)
            r += 1
            ws.merge_range(r, 0, r, width, '(Ban hành kèm theo %s)' % basis, center)
            r += 2
            name_code, tax_code = ('[05]', '[06]') if main else ('[04]', '[05]')
            for code, label, value in (('[01]', 'Kỳ tính thuế', 'Năm %d' % year),
                                       ('[02]', 'Lần đầu', 'X'),
                                       (name_code, 'Tên người nộp thuế', company.name or ''),
                                       (tax_code, 'Mã số thuế', settings.get('employer_tax_id') or company.vat or '')):
                ws.write_string(r, 0, code, bold)
                ws.write_string(r, 1, label)
                ws.write_string(r, 2, value or '')
                r += 1
            return r + 1

        # ------------------------------------------------ the declaration
        ws = book.add_worksheet('05-QTT-TNCN')
        r = top(ws, 'TỜ KHAI QUYẾT TOÁN THUẾ THU NHẬP CÁ NHÂN', 4, main=True)
        for text in ('(Dành cho tổ chức, cá nhân trả thu nhập từ tiền lương, tiền công) — Mẫu số 05/QTT-TNCN',):
            ws.merge_range(r, 0, r, 4, text, center)
            r += 2
        for i, label in enumerate(('STT', 'Chỉ tiêu', 'Mã chỉ tiêu', 'Đơn vị tính', 'Số người / Số tiền')):
            ws.write_string(r, i, label, head)
        r += 1
        totals = data.get('lines') or {}
        n = 0
        for line in form._pb_ordered_lines():
            if line.kind == 'text' or not line.code.isdigit():
                continue
            n += 1
            ws.write_number(r, 0, n, cell)
            ws.write_string(r, 1, line.official_label or line.label, cell)
            ws.write_string(r, 2, '[%s]' % line.code, cell)
            ws.write_string(r, 3, 'Người' if line.kind == 'count' else 'VNĐ', cell)
            ws.write_number(r, 4, float(totals.get(line.code) or 0), cell_money)
            r += 1
        ws.set_column(0, 0, 8)
        ws.set_column(1, 1, 80)
        ws.set_column(2, 3, 14)
        ws.set_column(4, 4, 22)

        people = data.get('employees') or []
        residents = [p for p in people if p.get('resident')]
        others = [p for p in people if not p.get('resident')]

        def appendix(name, title, cols, rows, total_from, first_total):
            """`first_total`: the first column whose total is printed — the
            totals row numbers [total_from] onwards for it and every column
            after it, in order (the form's own totals codes)."""
            sheet = book.add_worksheet(name)
            rr = top(sheet, title, len(cols) - 1)
            for c, (code, heading, _src) in enumerate(cols):
                sheet.write_string(rr, c, '%s\n[%s]' % (heading, code), head)
            sheet.set_row(rr, 90)
            rr += 1
            sums = [0.0] * len(cols)
            for i, person in enumerate(rows, start=1):
                for c, (_code, _h, src) in enumerate(cols):
                    value = self._pb_vn_cell(person, src, i)
                    if isinstance(value, (int, float)) and src != 'n':
                        sheet.write_number(rr, c, value, cell_money)
                        sums[c] += value
                    elif isinstance(value, (int, float)):
                        sheet.write_number(rr, c, value, cell)
                    else:
                        sheet.write_string(rr, c, value, cell)
                rr += 1
            # the totals row: [total_from]... for every number column
            sheet.write_string(rr, 1, 'Tổng cộng', head)
            code = total_from
            for c, (col_code, _h, _src) in enumerate(cols):
                if int(col_code) < int(first_total):
                    continue
                sheet.write_number(rr, c, sums[c], total_money)
                sheet.write_comment(rr, c, '[%02d]' % code)
                code += 1
            sheet.set_column(0, 0, 6)
            sheet.set_column(1, 1, 28)
            sheet.set_column(2, len(cols), 16)
            return sheet

        appendix('05-1', 'PHỤ LỤC BẢNG KÊ CHI TIẾT CÁ NHÂN THUỘC DIỆN TÍNH THUẾ THEO BIỂU LUỸ TIẾN TỪNG PHẦN — Mẫu số 05-1/BK-QTT-TNCN',
                 spec['05-1'], residents, spec['total_from_1'], '12')
        appendix('05-2', 'PHỤ LỤC BẢNG KÊ CHI TIẾT CÁ NHÂN THUỘC DIỆN TÍNH THUẾ THEO THUẾ SUẤT TOÀN PHẦN — Mẫu số 05-2/BK-QTT-TNCN',
                 spec['05-2'], others, spec['total_from_2'], '11')

        # ------------------------------------------------ 05-3 dependants
        ws3 = book.add_worksheet('05-3')
        r = top(ws3, 'PHỤ LỤC BẢNG KÊ CHI TIẾT NGƯỜI PHỤ THUỘC GIẢM TRỪ GIA CẢNH — Mẫu số 05-3/BK-QTT-TNCN',
                len(DEP_COLS) - 1)
        for c, (code, heading) in enumerate(DEP_COLS):
            ws3.write_string(r, c, '%s\n[%s]' % (heading, code), head)
        ws3.set_row(r, 75)
        r += 1
        n = 0
        date_fmt = book.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        for person in residents:
            ident = person.get('identity') or {}
            for dep in person.get('dependants') or []:
                n += 1
                values = [n, person.get('name') or '', ident.get('tax_code') or '', dep['name'],
                          dep['birthday'], dep['tax_code'],
                          '' if dep['tax_code'] else ('Số ĐDCN' if dep['id_no'] else ''),
                          '' if dep['tax_code'] else dep['id_no'], dep['relation'],
                          dep['from_month'], dep['to_month']]
                for c, value in enumerate(values):
                    if c == 4:
                        if value:
                            ws3.write_datetime(r, c, fields.Datetime.to_datetime(value), date_fmt)
                        else:
                            ws3.write_string(r, c, '', cell)
                    elif isinstance(value, int):
                        ws3.write_number(r, c, value, cell)
                    else:
                        ws3.write_string(r, c, value or '', cell)
                r += 1
        ws3.set_column(0, 0, 6)
        ws3.set_column(1, 10, 20)

        # ------------------------------------------------ to check
        ws4 = book.add_worksheet(_("To check"))
        r = 0
        for warn in data.get('warnings') or []:
            ws4.write_string(r, 0, warn.get('message') or '')
            r += 1
        for person in people:
            for check in person.get('checks') or []:
                ws4.write_string(r, 0, '%s — %s' % (person.get('name') or '', check))
                r += 1
        ws4.set_column(0, 0, 110)
        book.close()
        return buf.getvalue()

    # ------------------------------------------------------------- the PDF
    def _pb_vn_certificate(self, data, person, version):
        self.ensure_one()
        spec = COLS[version]
        rec = self.sudo()
        company = rec.company_id
        ident = person.get('identity') or {}
        lines = person.get('lines') or {}
        currency = rec.currency_id or company.currency_id
        out = self._pb_cert_base(
            data, person, _("Tax withheld in the year"),
            'Chứng từ khấu trừ thuế thu nhập cá nhân (theo mẫu tham khảo 03/TNCN)')
        out['file_stem'] = 'TNCN'
        employer = out['blocks'][0]['rows']
        address = ', '.join(p for p in (company.street, company.street2, company.city) if p)
        employer[1:1] = [(_("Address"), address)] if address else []
        if company.phone:
            employer.append((_("Phone"), company.phone))
        months = person.get('months') or []
        span = '%s – %s' % (months[0][5:7] + '/' + months[0][:4], months[-1][5:7] + '/' + months[-1][:4]) \
            if months else ''
        out['blocks'].append({'title': _("Employee"), 'rows': [
            (_("Name"), person.get('name') or ''),
            (_("Personal tax code"), ident.get('tax_code') or ''),
            (_("Nationality"), ident.get('nationality') or ''),
            (_("Tax resident"), _("Yes") if person.get('resident') else _("No")),
            (_("Address"), ident.get('address') or ''),
            (_("ID or passport number"), '' if ident.get('tax_code') else (ident.get('national_id') or ident.get('passport') or '')),
        ]})

        def money(code):
            return self._pb_cert_amount(float(lines.get(code) or 0.0), currency)

        withheld = spec['line_withheld']
        taxable = spec['line_taxable']
        subject = float(lines.get(taxable) or 0.0) if float(lines.get(withheld) or 0.0) else 0.0
        rows = [
            ('[13]', cert_pdf.row_label(_("Kind of income"), 'Khoản thu nhập'), _("Salary and wages"), ''),
            ('[14]', cert_pdf.row_label(_("Compulsory insurance deducted"), 'Khoản đóng bảo hiểm bắt buộc'), money('INS'), ''),
            ('[15]', cert_pdf.row_label(_("Gifts to charity, humanitarian and study funds"), 'Khoản đóng từ thiện, nhân đạo, khuyến học'), money('CHARITY'), ''),
            ('[16]', cert_pdf.row_label(_("Months paid"), 'Thời điểm trả thu nhập'), span, ''),
            ('[17]', cert_pdf.row_label(_("Taxable income subject to withholding"), 'Tổng thu nhập chịu thuế phải khấu trừ'),
             self._pb_cert_amount(subject, currency), ''),
            ('[18]', cert_pdf.row_label(_("Income tax is worked out on"), 'Tổng thu nhập tính thuế'), money('ASSESS'), ''),
            ('[19]', cert_pdf.row_label(_("Personal income tax withheld"), 'Số thuế thu nhập cá nhân đã khấu trừ'), money(withheld), 'total'),
        ]
        out['tables'].append({'title': _("Income and tax for the year"),
                              'head': [_("Field"), _("What it is"), data.get('currency') or ''],
                              'rows': rows})
        deps = person.get('dependants') or []
        if deps:
            out['notes'].insert(0, _("Dependants counted for the family deduction: %s.", len(deps)))
        out['notes'].append(_("An information copy laid out like the sample 03/TNCN. The official withholding certificate carries the company's own series and number."))
        return out

    def _pb_certificate_vn_05qtt_tt89(self, data, person):
        return self._pb_vn_certificate(data, person, 'TT89')

    def _pb_certificate_vn_05qtt_tt80(self, data, person):
        return self._pb_vn_certificate(data, person, 'TT80')
