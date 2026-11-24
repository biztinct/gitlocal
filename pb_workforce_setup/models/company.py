# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Per-company setup state of the Workforce setup screen (WFSETUP P4, §2).

Four stored fields, written ONLY by the `pb.workforce.setup` facade with
sudo after its attendance-manager gate (`res.company` is not writable by an
attendance manager). Nothing else reads or writes them.
"""

from odoo import fields, models


class ResCompanyWorkforceSetup(models.Model):
    _inherit = 'res.company'

    pb_wfs_holidays_year = fields.Integer(
        string='Holidays confirmed up to year', readonly=True, copy=False,
        help='The latest year whose public holidays and company days off were confirmed in Workforce setup.')
    pb_wfs_clocks_ok = fields.Boolean(
        string='Time clocks confirmed', readonly=True, copy=False)
    pb_wfs_live_on = fields.Date(
        string='Roster first published from setup', readonly=True, copy=False)
    pb_wfs_live_to = fields.Date(
        string='Roster published up to', readonly=True, copy=False)
