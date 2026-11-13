# -*- coding: utf-8 -*-
"""ORG CHART P3 §1.4 — "Fill this role › A new starter" lowers the role's
"to hire" count when the new person is actually saved.

The org chart opens the new-employee form with `fill_job_id` in its
pre-fill (only from "Fill this role"); the form sends it back with the
other values. When the employee is really created — at once, or later when
a new-hire approval is carried out (the same method runs again with the
stored values) — and they took that job, the job has one fewer to fill
(never below 0). A form whose job was changed by hand lowers nothing.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbOnboardWizardFill(models.AbstractModel):
    _inherit = 'pb.people.onboard.wizard'

    @api.model
    def create_employee(self, vals):
        res = super().create_employee(vals)
        try:
            fill = (vals or {}).get('fill_job_id')
            if fill and res and res.get('employee_id') and not res.get('pending') \
                    and str(vals.get('job_id') or '') == str(fill):
                job = self.env['hr.job'].sudo().browse(int(fill)).exists()
                if job and job.no_of_recruitment > 0:
                    # officers may only read jobs once recruitment is installed (G17)
                    job.write({'no_of_recruitment': job.no_of_recruitment - 1})
        except Exception:   # noqa: BLE001 — the person is saved whatever happens here
            _logger.exception("pb_orgchart: the role's to-hire count was not lowered")
        return res
