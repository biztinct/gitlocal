from odoo.addons.report_xlsx.report.report_abstract_xlsx import ReportXlsxAbstract

from ..models.report_base import _fmt


class Bhxh630ReportXlsx(ReportXlsxAbstract):
    _name = "report.pb_hr_govt.bhxh630_xlsx"
    _description = "BHXH630 XLS Report"
    start_row_phatsinh = 6  # data starts at row 7 (0-indexed)
    start_row_dieuchinh = 6
    _report_code = "BHXH630"

    def generate_xlsx_report(self, workbook, data, wizard):
        wizard = wizard.ensure_one()
        sheets = self.env["pb.govt.report.base"]._copy_template(
            workbook, "BHXH630.xls", ["M01B-HSB-PhatSinh", "M01B-HSB-DieuChinh"]
        )
        sheet = sheets["M01B-HSB-PhatSinh"]
        sheet2 = sheets["M01B-HSB-DieuChinh"]
        bold = workbook.add_format({"bold": True})

        # Re-write header row in bold so it is visible even when templates are plain values.
        headers = [
            "Số sổ BHXH",
            "Họ và tên",
            "Từ ngày",
            "Đến ngày",
            "Số serial của chứng từ",
            "Loại nhóm hưởng",
            "Số CMND",
            "Tổng số ngày nghỉ",
            "Đợt bổ sung",
            "Hình thức nhận",
            "Số tài khoản",
            "Tên chủ tài khoản",
            "Mã ngân hàng",
            "Mã nhân viên",
            "Từ ngày đơn vị đề nghị",
            "Nghỉ dưỡng thai",
            "Ngày sinh con",
            "Mã thẻ BHYT của con",
            "Ngày nghỉ trong tuần",
            "Số con",
            "Điều kiện làm việc",
            "Mã tuyến bệnh viện",
            "Mã bệnh dài ngày",
        ]
        for col, head in enumerate(headers):
            sheet.write(self.start_row_phatsinh - 1, col, head, bold)

        company = wizard.company_id
        date_from = wizard.date_from
        date_to = wizard.date_to

        base = self.env["pb.govt.report.base"]
        employees = base._select_employees(wizard)
        payslips = base._get_payslips_in_range(company, date_from, date_to)
        lines_map = base._payslip_lines_map(payslips)

        benefit_label = {
            "om_dau_thai_san": "Ốm đau/Thai sản",
            "duong_suc": "Dưỡng sức/Phục hồi sức khỏe",
            "khac": "Khác",
        }.get(wizard.bhxh630_benefit_group, "Ốm đau/Thai sản")
        payment_label = "Chuyển khoản" if wizard.bhxh630_payment_method == "transfer" else "Tiền mặt"

        row = self.start_row_phatsinh
        for emp in employees:
            emp_lines = lines_map.get(emp.id, {})
            total_days = emp_lines.get("SICK", 0.0) + emp_lines.get("MAT", 0.0)
            bank = emp.bank_account_id
            bank_number = wizard.bhxh630_bank_no or (bank.acc_number if bank and bank.acc_number else "")
            bank_holder = wizard.bhxh630_bank_holder or (bank.acc_holder_name if bank and bank.acc_holder_name else "")
            bank_bic = wizard.bhxh630_bank_code or (bank.bank_bic if bank and bank.bank_bic else "")

            # Keep template headers; only write data columns in the official order.
            sheet.write(row, 0, emp.identification_id or emp.barcode or "")
            sheet.write(row, 1, emp.name or "")
            sheet.write(row, 2, _fmt(date_from))
            sheet.write(row, 3, _fmt(date_to))
            sheet.write(row, 4, wizard.bhxh630_certificate_serial or "SERIAL-001")  # TODO replace with actual chứng từ serial
            sheet.write(row, 5, benefit_label)
            sheet.write(row, 6, emp.identification_id or "")
            sheet.write_number(row, 7, total_days)
            sheet.write(row, 8, wizard.bhxh630_supplement_batch or "")  # TODO Đợt bổ sung if applicable
            sheet.write(row, 9, payment_label)
            sheet.write(row, 10, bank_number or "0000000000")  # TODO replace with real bank account
            sheet.write(row, 11, bank_holder or company.name or "")
            sheet.write(row, 12, bank_bic or "BANKXXX")  # TODO replace with real bank code
            sheet.write(row, 13, emp.barcode or "EMP-CODE")  # TODO replace with actual employee code
            sheet.write(row, 14, _fmt(date_from))  # Từ ngày đơn vị đề nghị
            sheet.write(row, 15, "")  # Nghỉ dưỡng thai
            sheet.write(row, 16, "")  # Ngày sinh con
            sheet.write(row, 17, "")  # Mã thẻ BHYT của con
            sheet.write(row, 18, "")  # Ngày nghỉ trong tuần
            sheet.write(row, 19, "")  # Số con
            sheet.write(row, 20, "")  # Điều kiện làm việc
            sheet.write(row, 21, wizard.bhxh630_route_code or "")  # Mã tuyến bệnh viện
            sheet.write(row, 22, wizard.bhxh630_long_illness_code or "")  # Mã bệnh dài ngày
            row += 1

    def get_filename(self, wizard, record):
        base = self.env["pb.govt.report.base"]
        return base._default_filename(self._report_code, wizard.company_id, wizard.date_from)
