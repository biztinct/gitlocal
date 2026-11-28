# -*- coding: utf-8 -*-
"""WDGAP S2-B2 item 6 — the pay items the Vietnamese social-insurance reports
read, on Form lines.

`VN_SI_ITEMS` is a catalogue form with four lines — sick-leave days,
maternity-leave days, allowances, other additions — that the five
Vietnamese social-insurance reports (`pb_hr_govt`, BHXH630, Tăng / Giảm lao
động) used to look up by the fixed codes SICK, MAT, ALLOW, EXTRA. It is NOT a
filing of its own (`filing_section = 'reports'`): its tile is not offered on
Compliance › Filings and it has no file. The reports read it through the
reader (`pb.govt.report.base._pb_si_items`, pb_hr_govt) once the company has
put a pay item on a line; until then they behave exactly as before.
"""
from odoo import _, models
from odoo.exceptions import UserError


class PbGovFilingVnSiItems(models.Model):
    _inherit = 'pb.gov.filing'

    def _pb_render_vn_si_items(self, data):
        raise UserError(_("These pay items are read by the Vietnamese social-insurance reports on Compliance › Filings. There is no file of its own to prepare."))
