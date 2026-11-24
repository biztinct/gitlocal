# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.workforce.setup.undo` — one row per bulk action of step 3 (WFSETUP P2).

The payload records exactly what the action changed (rows ended and their
previous end date, rows removed with their values, rows and teams created), so
`pb.workforce.setup.undo()` can put it back or refuse whole. Only its creator
may use a row (record rule + a check in the facade). Transient: vacuumed after
the usual transient age (one hour by default), far longer than the toast.
"""

from odoo import fields, models


class WorkforceSetupUndo(models.TransientModel):
    _name = 'pb.workforce.setup.undo'
    _description = 'Workforce setup: undo of one bulk change'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda self: self.env.company, ondelete='cascade')
    kind = fields.Selection([('assign', 'Working week'), ('oneoff', 'One-off shift'),
                             ('late', 'Late rule')], required=True)
    payload = fields.Json()
    summary = fields.Char()
