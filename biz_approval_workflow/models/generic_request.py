# Part of Payobook. See LICENSE file for full copyright and licensing details.
""""Other request" — ask anyone for a sign-off on anything.

Two jobs at once (ledger AM3). It is a real, useful feature: a title, a
description, an optional amount, and whatever route the business published for
it. And it is the reference adapter — the worked example every later adapter
copies, and the fixture every engine test runs against, so the contract is
proved by something that ships rather than by a test-only stub.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

STATES = [
    ('draft', 'Draft'),
    ('pending', 'Waiting for approval'),
    ('done', 'Approved and done'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('cancelled', 'Withdrawn'),
]


class BizApprovalGenericRequest(models.Model):
    _name = 'biz.approval.generic.request'
    _description = 'Other Request'
    _inherit = ['biz.approval.adapter.mixin', 'mail.thread']
    _order = 'create_date desc, id desc'

    _approval_process_key = 'generic'

    name = fields.Char(string='What are you asking for?', required=True,
                       tracking=True)
    description = fields.Text(string='Why')
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    requester_user_id = fields.Many2one(
        'res.users', string='Asked for by', required=True,
        default=lambda self: self.env.user)
    amount = fields.Monetary(currency_field='currency_id',
                             string='Amount, if any')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id)
    area_key = fields.Char(
        string='Part of the business',
        help='Optional. Lets a workflow apply only to one part of the '
             'business.')
    area_label = fields.Char(string='Part of the business, in words')
    kind_key = fields.Char(string='Kind of request', default='any')
    urgent = fields.Boolean()
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, tracking=True, readonly=True)
    decided_on = fields.Datetime(readonly=True)

    # ================================================== the adapter contract
    def _approval_context(self):
        self.ensure_one()
        scope_keys = []
        if self.area_key:
            scope_keys.append('area:%s' % self.area_key)
        scope_keys.append('')
        return {
            'company_id': self.company_id.id,
            'title': self.name,
            'scope_keys': scope_keys,
            'scope_label': self.area_label or self.area_key or '',
            'kind_key': self.kind_key or 'any',
            'facts': {
                'amount': {'value': self.amount,
                           'unit': self.currency_id.name or ''},
                'urgent': {'value': bool(self.urgent), 'unit': 'bool'},
                'kind': {'value': self.kind_key or 'any', 'unit': ''},
            },
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'maker_uids': [self.create_uid.id] if self.create_uid else [],
            'submitter_uid': self.env.uid,
            'subject_uids': [self.requester_user_id.id]
            if self.requester_user_id else [],
            'source_revision': self._approval_revision_of({
                'name': self.name,
                'description': self.description or '',
                'amount': self.amount,
                'currency': self.currency_id.id,
            }),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'amount': {'type': 'decimal', 'label': _('Amount'),
                           'unit': 'currency'},
                'urgent': {'type': 'bool', 'label': _('Marked urgent'),
                           'unit': 'bool'},
                'kind': {'type': 'selection', 'label': _('Kind of request'),
                         'unit': ''},
            },
            'kinds': [{'key': 'any', 'label': _('Any kind')}],
            'evidence': [],
            'scope_levels': [_('Part of the business'), _('Whole company')],
            'manager_mode': True,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        rows = [{'scope_keys': [''], 'scope_key': '',
                 'label': company.name, 'kind_key': 'any',
                 'headcount': 0}]
        counts = {}
        for rec in self.sudo().search([('company_id', '=', company.id),
                                       ('area_key', '!=', False)]):
            counts[rec.area_key] = counts.get(rec.area_key, 0) + 1
        for key, count in sorted(counts.items()):
            rows.append({
                'scope_keys': ['area:%s' % key, ''],
                'scope_key': 'area:%s' % key,
                'label': key,
                'kind_key': 'any',
                'headcount': count,
            })
        return rows

    def _approval_validate(self):
        self.ensure_one()
        if self.state not in ('draft', 'returned'):
            raise UserError(_(
                "This has already been sent in. Only a draft or something "
                "sent back can be sent again."))
        if not self.name:
            raise UserError(_("Say what you are asking for."))
        return True

    def _approval_freeze(self, request):
        self.ensure_one()
        # sudo: the person sending it in may not own this record, and the
        # engine has already checked they may write to it.
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_apply(self, request):
        self.ensure_one()
        if self.state == 'done':
            return True  # idempotent: the engine may retry
        self.sudo().write({'state': 'done',
                           'decided_on': fields.Datetime.now()})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned'})
        return True

    # ------------------------------------------------------------ the guard
    def write(self, vals):
        """The state belongs to the approval, not to whoever can edit — and
        once something is sent in, what was approved must stop moving."""
        if self.env.su or self.env.user._is_admin():
            return super().write(vals)
        if 'state' in vals:
            raise UserError(_(
                "Whether this is approved is decided by the people on its "
                "approval route, not by editing it here."))
        frozen = self.filtered(lambda r: r.state not in ('draft', 'returned'))
        if frozen and set(vals) - {'message_follower_ids', 'message_ids',
                                   'activity_ids'}:
            raise UserError(_(
                "This has been sent in for approval, so it cannot be changed. "
                "Ask for it to be sent back first."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not (self.env.su or self.env.user._is_admin()):
                vals.pop('state', None)
        return super().create(vals_list)
