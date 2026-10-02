# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Vietnam Government XLS Reports",
    "summary": "Generates mandated Vietnamese government XLS reports (BHXH/BHYT/BHTN).",
    # 19.0.1.1.0 — the Odoo-19 field drift that made four of the five VN
    # filings unusable: address_home_id / bank_account_id / gender, all now
    # resolved through pb.govt.report.base.
    "version": "19.0.1.1.0",
    "license": "AGPL-3",
    "author": "Your Company",
    "website": "",
    "depends": [
        "base",
        "hr",
        "hr_contract",
        "om_hr_payroll",
        "report_xlsx",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/code_lookup_data.xml",
        "views/govt_report_wizard_views.xml",
        "report/govt_report_actions.xml",
    ],
    "installable": True,
}
