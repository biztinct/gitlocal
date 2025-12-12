# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.report_xlsx.report.report_abstract_xlsx import ReportXlsxAbstract

from ..models.report_base import _fmt


class TangLdReportXlsx(ReportXlsxAbstract):
    _name = "report.pb_hr_govt.tang_ld_xlsx"
    _description = "TangLaoDong XLS Report"
    start_row = 6
    _report_code = "TangLaoDong"

    def generate_xlsx_report(self, workbook, data, wizard):
        wizard = wizard.ensure_one()
        sheets = self.env["pb.govt.report.base"]._copy_template(
            workbook, "TangLaoDong.xls", ["TangLaoDong"]
        )
        sheet = sheets["TangLaoDong"]
        bold = workbook.add_format({"bold": True})

        company = wizard.company_id
        base = self.env["pb.govt.report.base"]
        employees = base._select_employees(wizard)
        payslips = base._get_payslips_in_range(company, wizard.date_from, wizard.date_to)
        lines_map = base._payslip_lines_map(payslips)

        # Header bold to match template columns
        headers = [
            "Họ và tên",
            "Mã sổ BHXH",
            "Ngày sinh",
            "Nữ (X)",
            "CMND/CCCD",
            "Chức vụ",
            "Tiền lương",
            "Hệ số",
            "Phụ cấp",
            "Các khoản bổ sung",
            "Ngày bắt đầu HĐLĐ",
            "HĐLĐ xác định thời hạn",
            "HĐLĐ thử việc",
            "Ngày bắt đầu đóng BHXH",
            "Hiệu lực từ tháng",
            "Ghi chú / Mã vùng",
        ]
        for col, head in enumerate(headers):
            sheet.write(self.start_row - 1, col, head, bold)

        row = self.start_row
        for emp in employees:
            emp_lines = lines_map.get(emp.id, {})
            wage = emp.contract_id.wage if emp.contract_id else 0.0
            coef = emp.contract_id.struct_id.name if emp.contract_id else ""
            allowance = emp_lines.get("ALLOW", 0.0)
            extra = emp_lines.get("EXTRA", 0.0)
            province_code, district_code, commune_code = base._location_codes(emp.address_home_id)
            reason_note = dict(wizard._fields["tang_reason"].selection).get(wizard.tang_reason, "") or ""
            region_note = wizard.tang_region_code or ""
            note = (
                f"{reason_note} - {region_note}".strip(" -")
                if reason_note or region_note
                else f"Mã vùng:{province_code}; QH:{district_code}; XP:{commune_code} (TODO replace with actual codes)"
            )
            sheet.write(row, 0, emp.name or "")
            sheet.write(row, 1, emp.identification_id or "")
            sheet.write(row, 2, _fmt(emp.birthday))
            sheet.write(row, 3, "X" if emp.gender == "female" else "")
            sheet.write(row, 4, emp.identification_id or "")
            sheet.write(row, 5, emp.job_id.name or "")
            sheet.write_number(row, 6, wage)
            sheet.write(row, 7, coef)
            sheet.write_number(row, 8, allowance)
            sheet.write_number(row, 9, extra)
            sheet.write(row, 10, _fmt(emp.contract_id.date_start) if emp.contract_id else "")
            sheet.write(row, 11, _fmt(emp.contract_id.date_end) if emp.contract_id else "")
            sheet.write(row, 12, "")
            sheet.write(row, 13, _fmt(emp.contract_id.date_start) if emp.contract_id else "")
            sheet.write(row, 14, _fmt(wizard.tang_effective_date or wizard.date_from))
            sheet.write(row, 15, note)
            row += 1

    def get_filename(self, wizard, record):
        base = self.env["pb.govt.report.base"]
        return base._default_filename(self._report_code, wizard.company_id, wizard.date_from)
