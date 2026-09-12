# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Where a workflow applies.

One binding = one company, one process, one opaque scope key, one kind. The
engine walks the adapter's scope keys most-specific-first and takes the first
effective binding; within a rank an exact kind beats "any kind" (ledger AM2).

Two effective bindings for the same company + process + scope + kind is the one
structural error this model refuses outright: a request must never see two
routes.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ANY_KIND = 'any'


class BizApprovalBinding(models.Model):
    _name = 'biz.approval.binding'
    _description = 'Approval Binding'
    _order = 'process_id, scope_key, kind_key, id'

    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    process_id = fields.Many2one('biz.approval.process', required=True,
                                 index=True, ondelete='cascade')
    scope_key = fields.Char(default='', index=True,
                            help='Empty means the company default.')
    scope_label = fields.Char()
    kind_key = fields.Char(default=ANY_KIND, index=True,
                           help='"any" matches every kind of request.')
    workflow_id = fields.Many2one('biz.approval.workflow', required=True,
                                  index=True, ondelete='restrict')
    mode = fields.Selection([
        ('follow', 'Always the current version'),
        ('pin', 'Stay on one version'),
        ('paused', 'Paused — nothing new accepted'),
    ], default='follow', required=True)
    pinned_version_id = fields.Many2one('biz.approval.workflow.version')
    date_from = fields.Datetime()
    date_to = fields.Datetime()
    revision = fields.Integer(default=1, readonly=True)
    note = fields.Char()
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------ integrity
    @api.constrains('company_id', 'process_id', 'scope_key', 'kind_key',
                    'date_from', 'date_to', 'active')
    def _check_no_tie(self):
        for rec in self:
            if not rec.active:
                continue
            others = self.sudo().search([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('process_id', '=', rec.process_id.id),
                ('scope_key', '=', rec.scope_key or ''),
                ('kind_key', '=', rec.kind_key or ANY_KIND),
                ('active', '=', True),
            ])
            for other in others:
                if rec._overlaps(other):
                    raise ValidationError(_(
                        "\"%(name)s\" already covers exactly this place and "
                        "kind of request over the same dates. A request can "
                        "only follow one route, so end or narrow one of "
                        "them.", name=other.workflow_id.name))

    @api.constrains('mode', 'pinned_version_id')
    def _check_pin(self):
        for rec in self:
            if rec.mode == 'pin' and not rec.pinned_version_id:
                raise ValidationError(_(
                    "Choose which version this should stay on."))
            if rec.pinned_version_id \
                    and rec.pinned_version_id.workflow_id != rec.workflow_id:
                raise ValidationError(_(
                    "That version belongs to a different workflow."))

    @api.constrains('company_id', 'workflow_id')
    def _check_company(self):
        for rec in self:
            if rec.workflow_id.company_id != rec.company_id:
                raise ValidationError(_(
                    "This workflow belongs to another company."))

    def _overlaps(self, other):
        self.ensure_one()
        if self.date_to and other.date_from and self.date_to < other.date_from:
            return False
        if other.date_to and self.date_from and other.date_to < self.date_from:
            return False
        return True

    def _effective_at(self, at):
        self.ensure_one()
        if self.date_from and at < self.date_from:
            return False
        if self.date_to and at > self.date_to:
            return False
        return True

    def write(self, vals):
        if set(vals) - {'revision'}:
            vals = dict(vals)
            for rec in self:
                super(BizApprovalBinding, rec).write(
                    dict(vals, revision=rec.revision + 1))
            return True
        return super().write(vals)
