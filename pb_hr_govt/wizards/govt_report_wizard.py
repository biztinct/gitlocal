# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class PbGovtReportWizard(models.TransientModel):
    _name = "pb.govt.report.wizard"
    _description = "Vietnam Government XLS Report Wizard"

    REPORT_SELECTION = [
        ("bhxh630", "BHXH630 - Ốm đau/Thai sản"),
        ("bhxhdstk01", "BHXHDSTK01-DV_595 - Danh sách tham gia"),
        ("bangke_d01", "BangKeHS D01 - Hồ sơ D01-TS"),
        ("giam_ld", "GiamLaoDong - Báo giảm lao động"),
        ("tang_ld", "TangLaoDong - Báo tăng lao động"),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date", required=True)
    employee_ids = fields.Many2many("hr.employee", string="Employees")
    department_id = fields.Many2one("hr.department", string="Department")
    contract_type_id = fields.Many2one("hr.contract.type", string="Contract Type")

    # BHXH630 parameters
    bhxh630_benefit_group = fields.Selection(
        [
            ("om_dau_thai_san", "Ốm đau/Thai sản"),
            ("duong_suc", "Dưỡng sức/Phục hồi sức khỏe"),
            ("khac", "Khác"),
        ],
        string="Loại nhóm hưởng",
        default="om_dau_thai_san",
    )
    bhxh630_certificate_serial = fields.Char(string="Số serial chứng từ")
    bhxh630_supplement_batch = fields.Char(string="Đợt bổ sung (yyyymm+đợt)")
    bhxh630_payment_method = fields.Selection(
        [("transfer", "Chuyển khoản"), ("cash", "Tiền mặt")],
        string="Hình thức nhận",
        default="transfer",
    )
    bhxh630_bank_no = fields.Char(string="Số tài khoản (mặc định)")
    bhxh630_bank_holder = fields.Char(string="Tên chủ tài khoản (mặc định)")
    bhxh630_bank_code = fields.Char(string="Mã ngân hàng (mặc định)")
    bhxh630_route_code = fields.Char(string="Mã tuyến bệnh viện")
    bhxh630_long_illness_code = fields.Char(string="Mã bệnh dài ngày")

    # BHXHDSTK01 parameters
    bhxhdstk_contribution_method = fields.Selection(
        [
            ("monthly", "Hàng tháng"),
            ("quarterly", "Hàng quý"),
            ("halfyear", "6 tháng/lần"),
            ("yearly", "12 tháng/lần"),
            ("once", "Một lần"),
        ],
        string="Phương thức đóng",
        default="monthly",
    )
    bhxhdstk_change_content = fields.Char(string="Nội dung thay đổi")
    bhxhdstk_hospital_code = fields.Char(string="Mã BV đăng ký KCB")

    # BangKe D01 parameters
    d01_doc_name = fields.Char(string="Tên/Loại văn bản")
    d01_doc_number = fields.Char(string="Số hiệu văn bản")
    d01_issue_date = fields.Date(string="Ngày ban hành")
    d01_effective_date = fields.Date(string="Ngày hiệu lực")
    d01_agency = fields.Char(string="Cơ quan ban hành")
    d01_summary = fields.Char(string="Trích yếu văn bản")
    d01_appraisal = fields.Char(string="Nội dung thẩm định")

    # Giảm lao động parameters
    giam_reason = fields.Selection(
        [
            ("resign", "Nghỉ việc/Chấm dứt HĐLĐ"),
            ("maternity", "Nghỉ thai sản dài hạn"),
            ("unpaid", "Nghỉ không lương"),
            ("other", "Khác"),
        ],
        string="Lý do giảm",
    )
    giam_effective_date = fields.Date(string="Ngày kết thúc đóng")
    giam_region_code = fields.Char(string="Mã vùng (ghi chú)")

    # Tăng lao động parameters
    tang_reason = fields.Selection(
        [
            ("new", "Tuyển mới"),
            ("return", "Quay lại làm việc"),
            ("salary_change", "Điều chỉnh lương/thay đổi HĐ"),
            ("other", "Khác"),
        ],
        string="Lý do tăng",
    )
    tang_effective_date = fields.Date(string="Hiệu lực từ tháng")
    tang_region_code = fields.Char(string="Mã vùng (ghi chú)")
    report_type = fields.Selection(
        REPORT_SELECTION,
        string="Report",
        required=True,
    )

    def action_export(self):
        """Trigger the selected XLS report."""
        self.ensure_one()
        report_map = {
            "bhxh630": "pb_hr_govt.report_bhxh630_xlsx",
            "bhxhdstk01": "pb_hr_govt.report_bhxhdstk01_xlsx",
            "bangke_d01": "pb_hr_govt.report_bangke_d01_xlsx",
            "giam_ld": "pb_hr_govt.report_giam_ld_xlsx",
            "tang_ld": "pb_hr_govt.report_tang_ld_xlsx",
        }
        action_xmlid = report_map.get(self.report_type)
        if not action_xmlid:
            return False
        return self.env.ref(action_xmlid).report_action(self)

    @api.model
    def action_export_monthly(self, report_type):
        report_map = {
            "bhxh630": "pb_hr_govt.report_bhxh630_xlsx",
            "bhxhdstk01": "pb_hr_govt.report_bhxhdstk01_xlsx",
            "bangke_d01": "pb_hr_govt.report_bangke_d01_xlsx",
            "giam_ld": "pb_hr_govt.report_giam_ld_xlsx",
            "tang_ld": "pb_hr_govt.report_tang_ld_xlsx",
        }
        action_xmlid = report_map.get(report_type)
        if not action_xmlid:
            return False
        date_from = fields.Date.today().replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        wizard = self.create({
            "company_id": self.env.company.id,
            "report_type": report_type,
            "date_from": date_from,
            "date_to": date_to,
        })
        return self.env.ref(action_xmlid).report_action(wizard)

    def action_mail_report(self):
        """Show notification about mail report feature."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Mail Report',
                'message': 'Mail report feature - configure email template to enable sending reports via email.',
                'type': 'info',
                'sticky': False,
            }
        }
