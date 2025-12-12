# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.report_xlsx.report.report_abstract_xlsx import ReportXlsxAbstract

from ..models.report_base import _fmt


class BangKeD01ReportXlsx(ReportXlsxAbstract):
    _name = "report.pb_hr_govt.bangke_d01_xlsx"
    _description = "BangKeHS D01 XLS Report"
    start_row = 6
    _report_code = "BangKeHS_D01"

    def generate_xlsx_report(self, workbook, data, wizard):
        wizard = wizard.ensure_one()
        sheets = self.env["pb.govt.report.base"]._copy_template(workbook, "BangKeHS D01.xls", ["D01-TS"])
        sheet = sheets["D01-TS"]
        bold = workbook.add_format({"bold": True})
        company = wizard.company_id
        base = self.env["pb.govt.report.base"]
        employees = base._select_employees(wizard)

        # Header row bold (matches template)
        headers = [
            "Họ và tên",
            "Mã sổ BHXH",
            "Tên, loại văn bản",
            "Số hiệu văn bản",
            "Ngày ban hành",
            "Ngày hiệu lực",
            "Cơ quan ban hành",
            "Trích yếu văn bản",
            "Trích lược nội dung cần thẩm định",
        ]
        for col, head in enumerate(headers):
            sheet.write(self.start_row - 1, col, head, bold)

        doc_name = wizard.d01_doc_name or "Văn bản mẫu"  # TODO replace with document name/type
        doc_number = wizard.d01_doc_number or "Số VB-001"  # TODO replace with document number
        issue_date = wizard.d01_issue_date or wizard.date_from
        effective_date = wizard.d01_effective_date or wizard.date_to
        agency = wizard.d01_agency or company.name
        summary = wizard.d01_summary or "Trích yếu nội dung"  # TODO replace with actual summary
        appraisal = wizard.d01_appraisal or "Nội dung thẩm định"  # TODO replace with actual review content

        for offset, emp in enumerate(employees):
            row = self.start_row + offset
            sheet.write(row, 0, emp.name or "")
            sheet.write(row, 1, emp.identification_id or "")
            sheet.write(row, 2, doc_name)
            sheet.write(row, 3, doc_number)
            sheet.write(row, 4, _fmt(issue_date))
            sheet.write(row, 5, _fmt(effective_date))
            sheet.write(row, 6, agency)
            sheet.write(row, 7, summary)
            sheet.write(row, 8, appraisal)

    def get_filename(self, wizard, record):
        base = self.env["pb.govt.report.base"]
        return base._default_filename(self._report_code, wizard.company_id, wizard.date_from)
