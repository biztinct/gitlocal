# -*- coding: utf-8 -*-
"""Letting a support engineer in is the customer's decision, not ours.

WHAT WAS TRUE BEFORE. Support asked for a link, the link was issued, and the
first person to click it was inside. The customer could switch support access
off entirely, and that was the whole of their say: on, or off.

WHAT IS TRUE NOW. Issuing a link also raises a request on the customer's own
approvals screen — who asked, why, and for how long — and the link cannot be
spent until that request has been approved. The customer sees every attempt,
whether or not anybody clicks.

THE CUSTOMER MAY STILL SAY "JUST LET THEM IN". The owner's ruling is that
every process may be set to "No approval needed", and this one ships that way
nowhere: it ships with one approval step, because an unannounced session in
somebody's payroll is the thing this exists to stop. A customer who wants the
old behaviour publishes the fast lane, and every session is still recorded as
a request with a name and a reason on it.
"""

import logging

from odoo import _, api, fields, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

SUPPORT_PROCESS_KEY = 'support'


class PbSupportAccessApproval(models.Model):
    _name = 'pb.support.access'
    _inherit = ['pb.support.access', 'biz.approval.adapter.mixin']

    _approval_process_key = SUPPORT_PROCESS_KEY

    approved_at = fields.Datetime(
        readonly=True, copy=False,
        help='When the customer agreed to this session. A link cannot be '
             'used before it.')
    company_id = fields.Many2one(
        'res.company', index=True, readonly=True,
        default=lambda s: s.env.company)

    # ------------------------------------------------------------- managed?
    @api.model
    def _support_route_live(self, company=None):
        if 'biz.approval.binding' not in self.env:
            return False
        process = self.env['biz.approval.process']._by_key(
            SUPPORT_PROCESS_KEY)
        if not process:
            return False
        company = company or self.env.company
        return bool(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id), ('active', '=', True)]))

    # ==================================================================
    # The adapter
    # ==================================================================
    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        return {
            'company_id': company.id,
            'title': _("Support access · %s", self.support_name or ''),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': 'any',
            'facts': {
                'minutes': {'value': self.duration_minutes or 0,
                            'unit': _('minutes')},
                'support_name': {'value': self.support_name or '', 'unit': ''},
                'reason': {'value': (self.reason or '')[:120], 'unit': ''},
            },
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': [],
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._approval_revision_of({
                'token': self.token_hash or '',
                'minutes': self.duration_minutes or 0,
                'reason': self.reason or ''}),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'minutes': {'type': 'int', 'label': _('How long, in minutes')},
                'support_name': {'type': 'char', 'label': _('Who is asking')},
                'reason': {'type': 'char', 'label': _('Why')},
            },
            'kinds': [],
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
        return _("%s minutes", self.duration_minutes or 0)

    def _approval_detail(self, request):
        self.ensure_one()
        return {
            'title': _('The session asked for'),
            'columns': [], 'rows': [],
            'chips': [
                {'label': _('Who'), 'value': self.support_name or ''},
                {'label': _('How long'),
                 'value': _("%s minutes", self.duration_minutes or 0)},
            ],
            'note': (self.reason or '')[:240],
        }

    def _approval_apply(self, request):
        self.ensure_one()
        if not self.approved_at:
            self.sudo().write({'approved_at': fields.Datetime.now()})
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        if self.state in ('issued',):
            self.sudo().write({
                'state': 'refused',
                'refused_reason': (reason or _("The customer said no."))[:200],
            })
        return True

    def _approval_return(self, request, reason):
        """There is nothing to change and ask again about: a support link is
        one link, for one session. Sending it back ends it, and says why."""
        return self._approval_reject(request, reason)

    # ==================================================================
    # The two doors
    # ==================================================================
    @api.model
    def issue(self, token_hash, reason, support_name, minutes):
        row = super().issue(token_hash, reason, support_name, minutes)
        if not self._support_route_live(row.sudo().company_id):
            return row
        try:
            self.env['biz.approval.engine'].submit(row.sudo())
        except Exception as exc:    # noqa: BLE001
            # The row still exists and the link still cannot be spent — the
            # claim below refuses anything that is not approved. A support
            # session that fails CLOSED is the right failure.
            _logger.warning('pb_tenancy: the support session could not be '
                            'sent for approval: %s', exc)
        return row

    @api.model
    def claim(self, token, source_ip=''):
        row, verdict = super().claim(token, source_ip)
        if verdict != 'ok' or not row:
            return row, verdict
        if not self._support_route_live(row.sudo().company_id):
            return row, verdict
        if row.sudo().approved_at:
            return row, verdict
        # Not approved (yet, or ever). Put the session back and say so — the
        # session must not open on a decision nobody has made.
        row.sudo().write({
            'used_at': False, 'session_expires_at': False, 'state': 'issued'})
        _logger.info('pb_tenancy: a support link was used before it was '
                     'approved (%s)', row.id)
        return row, 'not_approved'

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        return self.env['biz.approval.seed'].lay(
            company, SUPPORT_PROCESS_KEY, 'Support access',
            route(role_step(_('Approver'), 'approver'), independent=False),
            binding_note='Nobody from support gets into this account until '
                         'somebody here says so.',
            model_name='pb.support.access',
            role_keys=('approver',),
            reason='Set up when support-access approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.support.access']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_tenancy: %s has no support-access route',
                              company.name)
    return done
