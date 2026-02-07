# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Vietnam Government XLS Reports",
    "summary": "Generates mandated Vietnamese government XLS reports (BHXH/BHYT/BHTN).",
    "version": "19.0.1.0.0",
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
