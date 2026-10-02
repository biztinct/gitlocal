# -*- coding: utf-8 -*-
"""The Vietnamese statutory payslip, as a document the payroll can fill in.

WHAT THIS IS. `hr.formula.config.payslip_layout_html` holds a complete page:
when it has a value the printed payslip IS that page, with two kinds of marker
resolved against the run — `{{pb_component:<rule id>:value}}` for a figure the
scheme computed, and `{{pb_meta:<key>}}` for a fact about the person or the
period. Everything else is ordinary HTML. So a payslip that has to look like a
particular piece of paper is built by writing that paper out once, which is what
this module does.

WHY IT IS A BUILDER AND NOT A DATA FILE. The markers carry rule IDs, and rule
IDs differ in every database. The document therefore has to be assembled where
it is applied. Codes are matched case-insensitively and a row whose component is
missing prints its label with an empty cell rather than failing — a scheme
without, say, a phone allowance still gets a payslip.

WHAT IT IS NOT. It is not a lock. The result is an ordinary document that the
Payslip Studio opens and edits; applying it again overwrites the document, which
is why `pb_apply_vn_payslip_layout` never runs on its own.

THE LETTERHEAD is a caller's argument, defaulting to the company record. A
legal entity's registered name is often not the name the database calls it, and
guessing produces a payslip that names the wrong company.
"""

from markupsafe import escape

from odoo import _, api, models

#: The look of the paper: a pale band per section, thin grey rules, black text.
_BAND_BG = '#d8e4bc'
_BAND_FG = '#254117'
_LINE = '#a6b98a'
_CELL_BORDER = '1px solid %s' % _LINE

#: THE DOCUMENT, section by section. Each section is a heading and its rows;
#: each row is up to two label/component pairs, side by side, the way the paper
#: reads.
#:
#: A pair is `(Vietnamese label, English label, component code)`. A code of
#: None means the row is printed with an EMPTY value cell on purpose — the paper
#: has a line for it and this scheme has nothing that fills it. A pair of None
#: leaves that half of the row blank.
#:
#: `meta:<key>` in place of a code prints a fact about the person rather than a
#: figure: the payslip states who it is for before it states what they are paid.
VN_PAYSLIP_SECTIONS = [
    ('THÔNG TIN NHÂN VIÊN', 'EMPLOYEE INFORMATION', [
        (('Họ tên nhân viên', "Employee's name", 'meta:employee_name'),
         ('Mã nhân viên', 'Employee ID', 'meta:employee_id')),
        (('Vị trí', 'Position', 'meta:position'),
         ('Loại HĐ', 'Contract Type', 'meta:contract_type')),
        (('Ngày vào công ty', 'Starting date', 'meta:date_joined'),
         ('Ngày nghỉ việc', 'Resignation date', 'meta:date_left')),
    ]),
    ('THÔNG TIN NGÀY CÔNG', 'WORKING DAYS', [
        (('Ngày công chuẩn trong tháng', 'Standard working days', 'STDDAYS'),
         ('Ngày công thực tế', 'Actual working days', 'PAIDDAYS')),
    ]),
    ('CÁC KHOẢN THU NHẬP THỰC TẾ TRONG THÁNG', 'ACTUAL MONTHLY GROSS INCOME', [
        (('Lương gộp', 'Gross salary', 'BASIC'),
         ('Phụ cấp xăng xe', 'Transportation allowance', 'TRANSPORT')),
        (('Lương thực tế trong tháng', 'Actual monthly salary', 'SALARYPAID'),
         ('Phụ cấp điện thoại', 'Phone allowance', 'PHONEALLOW')),
        # The owner's ruling, 2026-09-11: the paper has a line for a technical
        # advisory allowance and the scheme has no such payment, so the line is
        # printed and left empty rather than quietly dropped.
        (('Trợ cấp tư vấn kỹ thuật', 'Technical advisory allowance', None),
         ('Tiền lương tháng trước', 'Payback salary', 'ADJADD')),
        (('Thưởng/trợ cấp khác', 'Other allowance/bonus', 'OTHERTAX'),
         None),
    ]),
    ('KHẤU TRỪ BẢO HIỂM BẮT BUỘC, CÔNG ĐOÀN PHÍ',
     'SOCIAL INSURANCE & UNION FEE DEDUCTION', [
         (('BHXH 8% NLĐ đóng', 'Compulsory Social Insurance 8% by Employee', 'SIDED'),
          ('BHTN 1% NLĐ đóng',
           'Compulsory Un-employment Insurance 1% by Employee', 'UIDED')),
         (('BHYT 1.5% NLĐ đóng',
           'Compulsory Health Insurance 1.5% by Employee', 'HIDED'),
          ('ĐOÀN PHÍ 0.5% NLĐ đóng', 'Trade Union Fee 0.5% by Employee',
           'UNIONDUES')),
     ]),
    ('THUẾ THU NHẬP CÁ NHÂN', 'PERSONAL INCOME TAX', [
        (('Số người phụ thuộc', 'Number of dependent', 'DEPS'),
         ('Thuế TNCN khấu trừ NLĐ', 'Personal Income Tax', 'PIT')),
    ]),
]

#: The two totals, which the paper gives a full-width band each.
#: `(Vietnamese, English, component code or None)`.
#:
#: The dollar figure has NO component: the owner's ruling of 2026-09-11 is that
#: the line prints empty until somebody decides where a dong-to-dollar rate
#: comes from. Nothing on this system converts a payslip today, and a figure
#: made up from a stale rate on an employee's payslip is worse than a blank.
VN_PAYSLIP_TOTALS = [
    ('THỰC LĨNH', 'Final Net pay (VND)', 'NET'),
    ('THỰC LĨNH', 'Final Net pay (USD)', None),
]

#: What the paper says at the bottom, under the table.
VN_PAYSLIP_NOTES = [
    ('Vui lòng bảo mật tất cả thông tin trong phiếu lương này',
     'It is important to keep all information in this payslip confidential.'),
    ('Mọi thắc mắc liên hệ phòng nhân sự.',
     'Any questions can be directed to the Human Resources Department.'),
]


class HrFormulaConfigVnPayslip(models.Model):
    _inherit = 'hr.formula.config'

    # ------------------------------------------------------------------ bits
    @api.model
    def _vn_payslip_cell(self, style):
        return 'border:%s;padding:4px 6px;vertical-align:top;%s' % (
            _CELL_BORDER, style)

    def _vn_payslip_label(self, vietnamese, english):
        """A label cell: Vietnamese over its English translation, as on paper."""
        return (
            '<td style="%s">%s<br/><em style="color:#333">%s</em></td>'
        ) % (self._vn_payslip_cell('width:28%;font-size:10.5px;line-height:1.25'),
             escape(vietnamese), escape(english))

    def _vn_payslip_value(self, token):
        """A value cell: a marker the payroll fills in, or an empty box."""
        return '<td style="%s">%s</td>' % (
            self._vn_payslip_cell(
                'width:22%;text-align:right;font-weight:700;white-space:nowrap'),
            token or '')

    def _vn_payslip_band(self, vietnamese, english):
        return (
            '<tr><td colspan="4" style="%s">%s / <em>%s</em></td></tr>'
        ) % (self._vn_payslip_cell(
            'background-color:%s;color:%s;font-weight:700;font-size:10.5px'
            % (_BAND_BG, _BAND_FG)), escape(vietnamese), escape(english))

    def _vn_payslip_token(self, code, rules_by_code):
        """The marker that fills a value cell, or '' when nothing fills it.

        `meta:<key>` is a fact about the person; anything else is a component
        code resolved against THIS configuration's own rules.
        """
        if not code:
            return ''
        if code.startswith('meta:'):
            return '{{pb_meta:%s}}' % code[5:]
        rule = rules_by_code.get(code.upper())
        # A scheme without this component prints the line empty rather than
        # printing a marker nothing will ever replace.
        return '{{pb_component:%s:value}}' % rule.id if rule else ''

    def _vn_payslip_note(self, entry):
        """One line under the table.

        A `(vietnamese, english)` pair reads as the rest of the paper does:
        the Vietnamese line with its English translation in italics beneath.
        A plain string is a single centred line — which is what an address is,
        and translating an address produces the same address twice.
        """
        if isinstance(entry, (tuple, list)):
            vietnamese, english = (list(entry) + ['', ''])[:2]
            return ('<div style="font-size:10px;line-height:1.35">%s<br/>'
                    '<em>%s</em></div>') % (escape(vietnamese), escape(english))
        return ('<div style="font-size:10px;line-height:1.4;text-align:center;'
                'margin-top:6px">%s</div>') % escape(str(entry))

    # ------------------------------------------------------------- the paper
    def _vn_payslip_letterhead(self, letterhead=None):
        """The company block at the top right: name, then its identifiers."""
        self.ensure_one()
        if letterhead is None:
            company = self.env.company
            partner = company.partner_id
            letterhead = [company.name or '']
            if partner.company_registry:
                letterhead.append(_('Enterprise code: %s', partner.company_registry))
            if partner.vat:
                letterhead.append(_('Tax code: %s', partner.vat))
        lines = [str(line) for line in letterhead if line]
        if not lines:
            return ''
        head = ('<div style="font-size:13px;font-weight:700">%s</div>'
                % escape(lines[0]))
        rest = ''.join('<div style="font-size:10.5px">%s</div>' % escape(line)
                       for line in lines[1:])
        return ('<td style="width:60%%;text-align:right;vertical-align:top;'
                'border:0;padding:0">%s%s</td>') % (head, rest)

    def pb_build_vn_payslip_layout(self, letterhead=None, footer=None,
                                   title_vi=None, title_en=None):
        """Return the payslip document for THIS configuration, as HTML.

        Pure: it reads the configuration's rules and writes a string. Nothing is
        saved, so a caller can look at the result before committing to it.

        :param letterhead: lines for the company block, first one in bold.
            Defaults to the company record.
        :param footer: `(vietnamese, english)` pairs printed under the table,
            after the standard confidentiality note. The registered address
            belongs here.
        """
        self.ensure_one()
        rules_by_code = {}
        for rule in self.rule_ids:
            if rule.code:
                rules_by_code.setdefault(rule.code.upper(), rule)

        rows = []
        for vietnamese, english, pairs in VN_PAYSLIP_SECTIONS:
            rows.append(self._vn_payslip_band(vietnamese, english))
            for left, right in pairs:
                cells = []
                for pair in (left, right):
                    if pair is None:
                        # The paper leaves this half of the line blank.
                        cells.append('<td style="%s"></td><td style="%s"></td>'
                                     % (self._vn_payslip_cell('width:28%'),
                                        self._vn_payslip_cell('width:22%')))
                        continue
                    label_vi, label_en, code = pair
                    cells.append(self._vn_payslip_label(label_vi, label_en))
                    cells.append(self._vn_payslip_value(
                        self._vn_payslip_token(code, rules_by_code)))
                rows.append('<tr>%s</tr>' % ''.join(cells))

        for vietnamese, english, code in VN_PAYSLIP_TOTALS:
            rows.append(
                '<tr><td colspan="3" style="%s">%s / <em>%s</em></td>'
                '<td style="%s">%s</td></tr>'
                % (self._vn_payslip_cell(
                    'background-color:%s;color:%s;font-weight:700;font-size:11px'
                    % (_BAND_BG, _BAND_FG)),
                   escape(vietnamese), escape(english),
                   self._vn_payslip_cell(
                       'background-color:%s;text-align:right;font-weight:700;'
                       'white-space:nowrap' % _BAND_BG),
                   self._vn_payslip_token(code, rules_by_code)))

        notes = ''.join(self._vn_payslip_note(entry)
                        for entry in list(VN_PAYSLIP_NOTES) + list(footer or []))

        title_vi = title_vi or 'PHIẾU LƯƠNG THÁNG {{pb_meta:month}} NĂM {{pb_meta:year}}'
        title_en = title_en or 'PAYSLIP IN {{pb_meta:month_name}} {{pb_meta:year}}'
        head = self._vn_payslip_letterhead(letterhead)
        return (
            '<table style="width:100%%;border-collapse:collapse;border:0;'
            'margin-bottom:10px"><tr>'
            '<td style="width:40%%;border:0;padding:0"></td>%s</tr></table>'
            '<h2 style="text-align:center;font-size:15px;margin:6px 0 14px">'
            '%s / <em>%s</em></h2>'
            '<table style="width:100%%;border-collapse:collapse;'
            'table-layout:fixed;font-size:10.5px">%s</table>'
            '<div style="margin-top:12px">%s</div>'
        ) % (head, title_vi, title_en, ''.join(rows), notes)

    def pb_apply_vn_payslip_layout(self, letterhead=None, footer=None):
        """Write the document onto these configurations, and say what happened.

        OVERWRITES `payslip_layout_html`. The caller has asked for the paper
        back as it ships, so an edit made in the Payslip Studio is replaced —
        which is the point, and the reason nothing calls this automatically.
        """
        applied = []
        for config in self:
            config.payslip_layout_html = config.pb_build_vn_payslip_layout(
                letterhead=letterhead, footer=footer)
            missing = [
                code for _vi, _en, code in
                [pair for _v, _e, pairs in VN_PAYSLIP_SECTIONS
                 for row in pairs for pair in row if pair]
                + list(VN_PAYSLIP_TOTALS)
                if code and not code.startswith('meta:')
                and code.upper() not in {r.code.upper() for r in config.rule_ids
                                         if r.code}]
            applied.append({'config': config.display_name, 'missing': missing})
        return applied
