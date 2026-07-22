# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class BizApprovalStepLog(models.Model):
    """Append-only audit row for one approval transition on any record.

    Created by the mixin as the CLICKING user (never sudo — safety rail 5), so
    the log is the truthful record of who advanced/refused each stage. Rows are
    read-scoped by company via a record rule the consumer can extend; nobody but
    a system admin may write or unlink (append-only).
    """
    _name = 'biz.approval.step.log'
    _description = 'Approval Step Log'
    _order = 'stamp, id'
    _rec_name = 'to_state'

    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    from_state = fields.Char(string='From')
    to_state = fields.Char(string='To')
    user_id = fields.Many2one(
        'res.users', string='By', required=True, readonly=True, index=True,
        default=lambda self: self.env.user)
    stamp = fields.Datetime(
        string='When', required=True, readonly=True,
        default=fields.Datetime.now)
    note = fields.Text(string='Note')
    company_id = fields.Many2one('res.company', string='Company', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Authenticity: every internal user may CREATE (the mixin logs as the
        # clicking user, no sudo), so who/when must always be the server's
        # idea — a crafted call_kw create must not be able to forge a trail
        # row in another user's name or back-date one.
        for vals in vals_list:
            vals['user_id'] = self.env.uid
            vals.pop('stamp', None)
        return super().create(vals_list)

    @api.model
    def _for_record(self, record):
        """Ordered trail for a single record (helper for the stepper JSON)."""
        return self.search([
            ('res_model', '=', record._name), ('res_id', '=', record.id),
        ], order='stamp, id')
