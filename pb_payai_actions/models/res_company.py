# -*- coding: utf-8 -*-
"""The four company switches: what PayAI may DO for people in this company.

Company fields (precedent: pb_timesheet_approval `pb_timesheet_block_run`),
not database parameters — a group with several companies may want PayAI's
hands on in one and off in another.

Defaults follow the owner decision of 2026-10-12: on for the master database
(`payobook`), off on every other database until somebody asks. The default is
read per new company; existing companies are set by the module's
`post_init_hook`.
"""
from odoo import fields, models


def _master_db(self):
    return self.env.cr.dbname == 'payobook'


class ResCompany(models.Model):
    _inherit = 'res.company'

    payai_tier_look = fields.Boolean(
        string='PayAI may look (open screens, show figures)',
        default=_master_db,
        help="PayAI may open any screen the person can already reach, show "
             "where a pay run is and download an approved run's Excel. It "
             "never changes anything.")
    payai_tier_prepare = fields.Boolean(
        string='PayAI may prepare (draft runs, send for approval, change values)',
        default=_master_db,
        help="PayAI may prepare work for a person after they tap Do it: a "
             "draft pay run, a request for approval, a changed value that "
             "still goes through the normal approval route.")
    payai_tier_decide = fields.Boolean(
        string='PayAI may decide (approve, send back, reject)',
        default=_master_db,
        help="PayAI may record an approver's own decision after they type "
             "the word to confirm it. A spoken yes never counts here.")
    payai_voice_go_ahead = fields.Boolean(
        string="A spoken 'go ahead' counts for Amber",
        default=False,
        help="When on, a person who asked by voice may confirm a prepare "
             "request by saying go ahead. Decisions always need typing.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    payai_tier_look = fields.Boolean(
        related='company_id.payai_tier_look', readonly=False)
    payai_tier_prepare = fields.Boolean(
        related='company_id.payai_tier_prepare', readonly=False)
    payai_tier_decide = fields.Boolean(
        related='company_id.payai_tier_decide', readonly=False)
    payai_voice_go_ahead = fields.Boolean(
        related='company_id.payai_voice_go_ahead', readonly=False)
