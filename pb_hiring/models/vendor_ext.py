# -*- coding: utf-8 -*-
"""What an agency actually delivered, counted on the agency's own card.

THE POINTER IS OURS AND SO ARE THE NUMBERS. `pb_vendor_access` is not edited:
the vendor register knows nothing about hiring and should not have to. This
module owns `agency_vendor_id` on the request and, here, the two figures a
person asks about an agency — how many people they found, and how long it
took — plus the button that opens the roles behind them.

WHAT "HOW LONG IT TOOK" MEANS, said once: the days between the role being
agreed and the role being filled, averaged over the roles this agency worked
on that actually filled. Roles still open are not in it, because a role that
has taken ninety days so far and may take a hundred and twenty is not an
average of anything yet — and counting it would make an agency look better the
longer it failed.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbVendorHiring(models.Model):
    _inherit = 'pb.vendor'

    hiring_requisition_ids = fields.One2many(
        'pb.hiring.requisition', 'agency_vendor_id',
        string='Roles they are working on')
    hiring_open_count = fields.Integer(string='Roles open',
                                       compute='_compute_hiring')
    hiring_count = fields.Integer(string='People they found',
                                  compute='_compute_hiring')
    hiring_avg_days = fields.Integer(string='Average days to fill',
                                     compute='_compute_hiring')

    @api.depends('hiring_requisition_ids.state',
                 'hiring_requisition_ids.filled_count',
                 'hiring_requisition_ids.filled_on',
                 'hiring_requisition_ids.opened_on')
    def _compute_hiring(self):
        for rec in self:
            roles = rec.hiring_requisition_ids
            rec.hiring_open_count = len(
                roles.filtered(lambda r: r.state == 'open'))
            rec.hiring_count = sum(roles.mapped('filled_count'))
            # The SAME arithmetic the Hiring numbers use, floored at zero:
            # `opened_on` and `filled_on` are written on the acting person's
            # clock, so a role agreed and filled either side of midnight in
            # one timezone can otherwise read as a negative and vanish.
            spans = [max(0, (r.filled_on - r.opened_on).days) for r in roles
                     if r.filled_on and r.opened_on]
            rec.hiring_avg_days = int(round(sum(spans) / len(spans))) \
                if spans else 0

    def action_open_hiring(self):
        """Every hand-built window action carries `views` (R125)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.hiring.requisition',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'name': _('Roles %s is working on', self.name or ''),
            'domain': [('agency_vendor_id', '=', self.id)],
        }
