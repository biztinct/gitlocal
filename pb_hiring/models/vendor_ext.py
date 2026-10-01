# -*- coding: utf-8 -*-
"""What an agency actually delivered, counted on the agency's own card.

THE POINTER IS OURS AND SO ARE THE NUMBERS. `pb_vendor_access` keeps the
register and (RECRUIT P7) the agency's portal sign-ins; this module owns the
roles an agency is on (`agency_vendor_ids`) and, here, the figures a person
asks about an agency.

RECRUIT P7: THE FIGURES ARE THE AGENCY'S OWN SUBMISSIONS — who they put
forward through their portal, how many of those reached an interview, an
offer, and joined, and how many the 6-month rule turned away. Before P7 the
card summed the FILLED count of the agency's roles, which credited an agency
with every person on a role it merely shared with the team.

WHAT "HOW LONG IT TOOK" MEANS, said once: the days between the role being
opened and the role being filled, averaged over the roles this agency worked
on that actually filled. Roles still open are not in it, because a role that
has taken ninety days so far and may take a hundred and twenty is not an
average of anything yet — and counting it would make an agency look better
the longer it failed.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbVendorHiring(models.Model):
    _inherit = 'pb.vendor'

    hiring_requisition_ids = fields.Many2many(
        'pb.hiring.requisition', 'pb_hiring_requisition_agency_rel', 'vendor_id',
        'requisition_id', string='Roles they are working on')
    hiring_submission_ids = fields.One2many(
        'pb.hiring.agency.submission', 'vendor_id', string='People they put forward')
    hiring_open_count = fields.Integer(string='Roles open',
                                       compute='_compute_hiring')
    hiring_submitted = fields.Integer(string='Put forward', compute='_compute_hiring')
    hiring_refused = fields.Integer(string='Turned away by the 6-month rule',
                                    compute='_compute_hiring')
    hiring_interviewed = fields.Integer(string='Reached an interview',
                                        compute='_compute_hiring')
    hiring_offers = fields.Integer(string='Offers', compute='_compute_hiring')
    hiring_count = fields.Integer(string='Joined', compute='_compute_hiring')
    hiring_avg_days = fields.Integer(string='Average days to fill',
                                     compute='_compute_hiring')

    @api.depends('hiring_requisition_ids.state',
                 'hiring_requisition_ids.filled_count',
                 'hiring_requisition_ids.filled_on',
                 'hiring_requisition_ids.opened_on',
                 'hiring_submission_ids.state')
    def _compute_hiring(self):
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        for rec in self:
            roles = rec.sudo().hiring_requisition_ids
            rec.hiring_open_count = len(roles.filtered(lambda r: r.state == 'open'))
            figures = Sub._figures(Sub.search([('vendor_id', '=', rec.id)])) \
                if rec.id else {}
            rec.hiring_submitted = figures.get('submitted', 0)
            rec.hiring_refused = figures.get('refused', 0)
            rec.hiring_interviewed = figures.get('interviewed', 0)
            rec.hiring_offers = figures.get('offers', 0)
            rec.hiring_count = figures.get('joined', 0)
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
            'domain': [('agency_vendor_ids', 'in', self.ids)],
        }

    def action_open_submissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.hiring.agency.submission',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'name': _('People %s put forward', self.name or ''),
            'domain': [('vendor_id', '=', self.id)],
        }
