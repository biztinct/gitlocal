# -*- coding: utf-8 -*-
"""Keeping the group's pattern and the stretches of days in step.

`pb.work.segment.effective_policy` is stored, because the payroll hook reads
it on every payslip and a compute that walks up to the group per payslip is
four thousand extra queries a run. Storing it means somebody changing the
group's pattern has to be the moment those rows are rewritten — otherwise a
switch on the Group screen would be a switch that changes nothing until each
stretch of days is next touched, which is the worst possible shape for a
setting about money.

`pb.group` itself knows nothing about this: the dependency runs one way, and
`pb_group` stays installable with no work segments anywhere.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PbGroupWorkSegments(models.Model):
    _inherit = 'pb.group'

    def write(self, vals):
        res = super().write(vals)
        if 'split_pay_policy' not in vals:
            return res
        segments = self.env['pb.work.segment'].sudo().search([
            ('pay_policy', '=', 'inherit'),
            ('home_company_id', 'in', self.mapped('company_ids').ids),
            ('state', '!=', 'cancelled'),
        ])
        if segments:
            # A stored compute is refreshed by asking for it again, not by
            # writing the value: the compute is the one place that knows what
            # "whatever the group says" means.
            segments.invalidate_recordset(['effective_policy'])
            segments._compute_effective_policy()
            segments.flush_recordset(['effective_policy'])
            _logger.info(
                'pb_workseg: %s stretch(es) of days now follow the group\'s '
                'new pattern', len(segments))
        return res
