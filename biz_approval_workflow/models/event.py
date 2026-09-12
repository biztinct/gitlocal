# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The append-only trail the Audit console reads.

One row per thing that happened, with a summary written in plain words — "Nithya
approved HR lead review on Pay run · September 2026" — because the audit console
shows the summary and nothing else. Who and when are forced server-side (the
biz.approval.step.log pattern); write and unlink always raise, for everyone.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

KINDS = [
    ('submitted', 'Sent in'),
    ('step_activated', 'Step opened'),
    ('decided', 'Decided'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('cancelled', 'Withdrawn'),
    ('applied', 'Carried out'),
    ('blocked', 'Stuck'),
    ('reassigned', 'Moved to someone else'),
    ('escalated', 'Escalated'),
    ('reminded', 'Reminder sent'),
    ('published', 'Workflow published'),
    ('binding_changed', 'Where it applies changed'),
    ('responsibility_changed', 'Responsibility changed'),
    ('delegation_changed', 'Hand-over changed'),
    ('grant_changed', 'Exception changed'),
    ('exception_used', 'Exception used'),
]
KIND_LABELS = dict(KINDS)


class BizApprovalEvent(models.Model):
    _name = 'biz.approval.event'
    _description = 'Approval Event'
    _order = 'stamp desc, id desc'
    _rec_name = 'summary'

    company_id = fields.Many2one('res.company', index=True)
    kind = fields.Selection(KINDS, required=True, index=True)
    summary = fields.Char(required=True)
    payload = fields.Json(default=dict)
    user_id = fields.Many2one('res.users', string='By', required=True,
                              readonly=True, index=True,
                              default=lambda self: self.env.user)
    stamp = fields.Datetime(string='When', required=True, readonly=True,
                            default=fields.Datetime.now)
    request_id = fields.Many2one('biz.approval.request', index=True,
                                 ondelete='set null')
    workflow_id = fields.Many2one('biz.approval.workflow', index=True,
                                  ondelete='set null')
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['user_id'] = self.env.uid
            vals.pop('stamp', None)
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_(
            "The record of what happened cannot be changed."))

    def unlink(self):
        raise UserError(_(
            "The record of what happened cannot be deleted."))

    @api.model
    def _log(self, kind, summary, company=None, payload=None, request=None,
             workflow=None, res_model=None, res_id=None):
        # No sudo: every internal user may CREATE an event (create() forces
        # who and when), so the trail is truthful — the biz.approval.step.log
        # contract, kept.
        return self.create({
            'kind': kind,
            'summary': summary,
            'company_id': company.id if company else False,
            'payload': payload or {},
            'request_id': request.id if request else False,
            'workflow_id': workflow.id if workflow else False,
            'res_model': res_model or (request.res_model if request else False),
            'res_id': res_id or (request.res_id if request else False),
        })
