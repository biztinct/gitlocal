# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.report_xlsx.report.report_abstract_xlsx import ReportXlsxAbstract

from ..models.report_base import _fmt


class Bhxhdstk01ReportXlsx(ReportXlsxAbstract):
    _name = "report.pb_hr_govt.bhxhdstk01_xlsx"
    _description = "BHXHDSTK01-DV_595 XLS Report"
    start_row_danhsach = 6  # data row (1-indexed: row 7)
    start_row_hogd = 6
    _report_code = "BHXHDSTK01-DV_595"

    def generate_xlsx_report(self, workbook, data, wizard):
        wizard = wizard.ensure_one()
        sheets = self.env["pb.govt.report.base"]._copy_template(
            workbook, "BHXHDSTK01-DV_595.xls", ["Danhsach", "Hogiadinh"]
        )
        sheet = sheets["Danhsach"]
        sheet2 = sheets["Hogiadinh"]
        bold = workbook.add_format({"bold": True})

        company = wizard.company_id
        base = self.env["pb.govt.report.base"]
        employees = base._select_employees(wizard)

        # Header row in bold (matches template columns)
        headers = [
            "STT",
            "Họ và tên",
            "Mã sổ BHXH",
            "Ngày sinh",
            "Nữ (X)",
            "Quốc tịch",
            "Dân tộc",
            "Số CMND/CCCD",
            "Địa chỉ liên hệ",
            "Mã tỉnh",
            "Mã huyện",
            "Mã xã",
            "Tiền đóng",
            "Phương thức đóng",
            "Mã BV đăng ký KCB",
            "Nội dung thay đổi",
        ]
        for col, head in enumerate(headers):
            sheet.write(self.start_row_danhsach - 1, col, head, bold)

        contribution_label = {
            "monthly": "Hàng tháng",
            "quarterly": "Hàng quý",
            "halfyear": "6 tháng/lần",
            "yearly": "12 tháng/lần",
            "once": "Một lần",
        }.get(wizard.bhxhdstk_contribution_method, "Hàng tháng")
        change_content = wizard.bhxhdstk_change_content or "Thay đổi tham gia"

        for offset, emp in enumerate(employees):
            idx = self.start_row_danhsach + offset
            sheet.write(idx, 0, offset + 1)
            sheet.write(idx, 1, emp.name or "")
            sheet.write(idx, 2, emp.identification_id or "")
            sheet.write(idx, 3, _fmt(emp.birthday))
            sheet.write(idx, 4, "X" if emp.gender == "female" else "")
            sheet.write(idx, 5, emp.country_id.name or "")
            sheet.write(idx, 6, getattr(emp, "ethnicity_id", False) and emp.ethnicity_id.name or "")
            sheet.write(idx, 7, emp.identification_id or "")
            sheet.write(idx, 8, getattr(emp.address_home_id, "street", "") or "")
            province_code, district_code, commune_code = base._location_codes(emp.address_home_id)
            sheet.write(idx, 9, province_code)
            sheet.write(idx, 10, district_code)
            sheet.write(idx, 11, commune_code)
            sheet.write_number(idx, 12, emp.contract_id.wage if emp.contract_id else 0.0)
            sheet.write(idx, 13, contribution_label)
            sheet.write(idx, 14, wizard.bhxhdstk_hospital_code or base._hospital_code(emp.address_home_id))
            sheet.write(idx, 15, change_content)  # TODO replace with actual change content

        # Household headers bold
        hh_headers = [
            "STT",
            "Họ và tên",
            "Mã số BHXH",
            "Ngày sinh",
            "Nữ (X)",
            "Quan hệ với chủ hộ",
            "Ghi chú",
        ]
        for col, head in enumerate(hh_headers):
            sheet2.write(self.start_row_hogd - 1, col, head, bold)

    def get_filename(self, wizard, record):
        base = self.env["pb.govt.report.base"]
        return base._default_filename(self._report_code, wizard.company_id, wizard.date_from)
