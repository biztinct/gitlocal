# -*- coding: utf-8 -*-
"""B3 — Release bundles + sign-off.

A release groups the F7 version rows created since the last milestone into a
reviewable, signed-off bundle. It is a QUERY over F7 versions plus two milestone
boundaries — never a second history (D-B3). Approving a release writes an
immutable milestone; the change set is always re-derivable from the two
milestone timestamps via the F7 version snapshots.
"""
from odoo import api, fields, models


class HrFormulaRelease(models.Model):
    _name = 'hr.formula.release'
    _description = 'Formula Release'
    _order = 'approved_date desc, id desc'

    name = fields.Char(required=True)
    config_id = fields.Many2one('hr.formula.config', required=True,
                                ondelete='cascade', index=True)
    # boundaries: the change window is (from_milestone .. to_milestone].
    from_milestone_id = fields.Many2one('hr.formula.config.milestone',
                                        string='Since', ondelete='set null')
    to_milestone_id = fields.Many2one('hr.formula.config.milestone',
                                      string='Sealed at', ondelete='set null')
    approved_by_id = fields.Many2one('res.users', string='Signed off by',
                                     default=lambda s: s.env.user, readonly=True)
    approved_date = fields.Datetime(default=fields.Datetime.now, readonly=True, index=True)
    narrative = fields.Text(string='Changelog')
    change_count = fields.Integer(string='Components changed')
    # provenance: the exact F7 version rows in this release's window (audit only —
    # the diffs are re-derived from the two milestone timestamps, not from here).
    version_ids = fields.Many2many('hr.formula.rule.version', string='Version rows')

    # ------------------------------------------------------ Approval Matrix P4
    # A release used to be born approved, because sealing one WAS the approval:
    # whoever pressed the button had decided. It is now the OUTCOME of a
    # decision somebody else may have taken, so the row says which state it is
    # in and which proposal produced it.
    #
    # `approved` is the default, and the migration writes it onto every
    # existing row: those releases were signed off by the person who sealed
    # them, under the rules of the day, and re-labelling history as "pending"
    # would be a lie about what happened.
    state = fields.Selection([
        ('pending', 'Waiting for approval'),
        ('approved', 'Approved'),
    ], default='approved', required=True, index=True)
    proposal_id = fields.Many2one(
        'pb.scheme.proposal', string='Proposed by', ondelete='set null',
        help="The proposal whose approval produced this release, where there "
             "was one.")
