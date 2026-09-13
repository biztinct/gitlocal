# -*- coding: utf-8 -*-
"""Giving somebody a role is a decision, so it can be asked for.

WHAT WAS TRUE BEFORE. Anybody who could manage access could give anybody any
role, take it away again, or hand their own over, in one press. The trail was
perfect and it answered the wrong question: it said who did it, never who
agreed to it.

WHAT IS TRUE NOW. Where a company has published a route for role changes, the
press makes a REQUEST instead. The board says so, the person waiting is named,
and the change happens when the route says yes — carried out by the last
approver, as themselves, through exactly the same code the press used to run.

WHERE THERE IS NO ROUTE, NOTHING CHANGES. This module is generic: it can be
installed in a product that has never heard of the approval catalogue, and in
that case every press writes at once, exactly as before.

THE DEFAULT ROUTE IS ONE STEP, AND THAT IS TWO PEOPLE. Asking already requires
the right to manage access, so a route of one approval step means an access
manager asks and somebody else agrees. The handover called the two halves
"Access team" and "Tenant administrator"; those are Payobook words for
Payobook's own catalogue, and this module may not depend on it — so the step
names the ENGINE's own **Approver** responsibility, which every company has
from the moment approvals are switched on. A business that wants a different
person changes the step; a business that wants none publishes "No approval
needed".
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

ROLES_PROCESS_KEY = 'roles'

#: Set while the engine is carrying out an approved change, so the doors below
#: know this press is the route's own and not somebody skipping it.
ENGINE_APPLY = 'biz_access_engine_apply'

MANAGE_GROUP = 'biz_access.group_access_manager'

KINDS = [
    ('grant', 'Give a role'),
    ('remove', 'Take a role away'),
    ('delegate', 'Hand a role over for a while'),
]

STATES = [
    ('draft', 'Not sent yet'),
    ('pending', 'Waiting for a decision'),
    ('applied', 'Done'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('cancelled', 'Withdrawn'),
]


class PbAccessRequest(models.Model):
    _name = 'pb.access.request'
    _description = 'Access Request'
    _inherit = ['biz.approval.adapter.mixin']
    _order = 'create_date desc, id desc'

    _approval_process_key = ROLES_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    kind = fields.Selection(KINDS, required=True, index=True)
    profile_ids = fields.Many2many('pb.role.profile', string='Roles')
    target_user_id = fields.Many2one('res.users', string='For', index=True)
    delegate_user_id = fields.Many2one('res.users', string='Handed to')
    date_start = fields.Date()
    date_end = fields.Date()
    reason = fields.Text()
    payload = fields.Text(
        string='What was asked for (JSON)', readonly=True,
        help='The exact instruction, kept word for word so that what is '
             'carried out is what was agreed.')
    requested_by = fields.Many2one('res.users', string='Asked by',
                                   default=lambda s: s.env.user, index=True)
    company_id = fields.Many2one('res.company', index=True,
                                 default=lambda s: s.env.company)
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)
    block_note = fields.Text(readonly=True, copy=False)
    #: What the board itself said when the change was finally made. Kept so
    #: that a press on a "No approval needed" route answers with the same
    #: sentence it always did ("X now has Y") rather than a flat "done".
    done_note = fields.Char(readonly=True, copy=False)
    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_access_request_seat_rel', 'request_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('kind', 'profile_ids', 'target_user_id', 'delegate_user_id')
    def _compute_name(self):
        labels = dict(KINDS)
        for rec in self:
            roles = ', '.join(rec.profile_ids.mapped('name'))
            who = (rec.delegate_user_id if rec.kind == 'delegate'
                   else rec.target_user_id)
            rec.name = _("%(what)s · %(roles)s · %(who)s",
                         what=labels.get(rec.kind, ''), roles=roles or '',
                         who=who.name or '')

    def instruction(self):
        self.ensure_one()
        try:
            data = json.loads(self.payload or '{}')
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    # ==================================================================
    # The adapter
    # ==================================================================
    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        makers = {self.requested_by.id, self.create_uid.id}
        makers.discard(False)
        subjects = {self.target_user_id.id, self.delegate_user_id.id}
        subjects.discard(False)
        return {
            'company_id': company.id,
            'title': self.name or _('Access request'),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': self.kind or 'any',
            'facts': {
                'kind': {'value': self.kind or '', 'unit': ''},
                'roles': {'value': len(self.profile_ids), 'unit': ''},
                'temporary': {'value': bool(self.date_end), 'unit': ''},
                'role_names': {'value': ', '.join(
                    self.profile_ids.mapped('name'))[:120], 'unit': ''},
            },
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': sorted(subjects),
            # THE INSTRUCTION IS THE THING BEING AGREED. Stamping it means a
            # request edited after it was sent in cannot be carried out under
            # the approval it already has.
            'source_revision': self._approval_revision_of(self.instruction()),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'kind': {'type': 'selection', 'label': _('What is being asked')},
                'roles': {'type': 'int', 'label': _('How many roles')},
                'temporary': {'type': 'bool', 'label': _('Ends on a date')},
                'role_names': {'type': 'char', 'label': _('Which roles')},
            },
            'kinds': [{'key': key, 'label': label} for key, label in KINDS],
            'evidence': [],
            'scope_levels': [_('Whole company')],
            'manager_mode': False,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        count = len(self.profile_ids)
        return _("1 role") if count == 1 else _("%s roles", count)

    def _approval_detail(self, request):
        self.ensure_one()
        rows = [{'head': profile.name or '', 'sub': '',
                 'cells': [self.target_user_id.name
                           or self.delegate_user_id.name or ''],
                 'tone': 'on'} for profile in self.profile_ids[:20]]
        chips = []
        if self.delegate_user_id:
            chips.append({'label': _('Handed to'),
                          'value': self.delegate_user_id.name or ''})
        if self.date_end:
            chips.append({'label': _('Until'), 'value': str(self.date_end)})
        return {'title': _('What would change'), 'columns': [_('Who')],
                'rows': rows, 'chips': chips, 'note': (self.reason or '')[:240]}

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending', 'block_note': False})
        return True

    def _approval_return(self, request, reason):
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.sudo().write({'state': 'rejected'})
        return True

    def _approval_apply(self, request):
        """Carry out the change, as the last approver, through the same door.

        NOT `sudo()` (safety rail 7): the person who said yes is the person who
        does it, so somebody who cannot manage access is refused BY NAME and
        the seat can be moved to somebody who can.
        """
        self.ensure_one()
        if self.state == 'applied':
            return True
        if not (self.env.su or self.env.user._is_admin()
                or self.env.user.has_group(MANAGE_GROUP)):
            raise UserError(_(
                "This is approved, but %s is not allowed to change who holds "
                "a role. Ask somebody who looks after approvals to move this "
                "step to a person who is, or give them that permission first.",
                self.env.user.name))
        data = self.instruction()
        Access = self.env['pb.access'].with_context(**{ENGINE_APPLY: True})
        if self.kind == 'grant':
            answer = Access.grant(data.get('profile_id'), data.get('user_id'),
                                  data.get('reason'))
        elif self.kind == 'remove':
            answer = Access.remove(data.get('profile_id'),
                                   data.get('user_id'), data.get('reason'))
        else:
            answer = Access.delegate(data.get('vals') or {})
        self.sudo().write({
            'state': 'applied', 'block_note': False,
            'done_note': (answer or {}).get('message') or False})
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'approver', MANAGE_GROUP)
        return Seed.lay(
            company, ROLES_PROCESS_KEY, 'Role changes',
            route(role_step(_('Approver'), 'approver')),
            binding_note='Asking already needs the right to manage access, so '
                         'one approval step means two people: one asks, '
                         'another agrees.',
            model_name='pb.access.request',
            role_keys=('approver',),
            reason='Set up when role approvals were switched on')


class BizApprovalRequestSeatAccess(models.Model):
    """A seat on an access request is also a permission to read it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.access.request' or not request.res_id:
                continue
            record = self.env['pb.access.request'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.access.request']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('biz_access: %s has no role-change route',
                              company.name)
    return done
