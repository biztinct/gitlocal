# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""A company created after install must not be silently ungated.

The post_init_hook seeds only the companies that exist at install time, and
`_rule_for_company` is deliberately company-only (no global fallback) — so
without this, a future company would have zero young-worker protection and
nothing would even hint at the gap. Seed the VN defaults on create; they are
ordinary config a payroll manager can edit or deactivate.
"""

from odoo import api, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        self.env['pb.young.worker.rule']._seed_vn_defaults(companies)
        return companies
