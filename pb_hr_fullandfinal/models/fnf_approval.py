# -*- coding: utf-8 -*-
"""A final settlement is the last money somebody is ever paid here.

WHAT WAS TRUE BEFORE. Selecting some leavers and pressing Generate produced a
settlement each, with a net figure on it, and the report could be downloaded
straight away. There was no state on the record at all — nothing distinguished
a figure somebody had checked from a figure a wizard had just worked out.

WHAT IS TRUE NOW. Each settlement is created in `draft` and travels a route
(`fnf`: HR lead, then the finance approver). The settlement REPORT can only be
downloaded once it has been approved — or where the business has published
"No approval needed", in which case the settlement is approved as it is made
and the press behaves exactly as it did.

WHY THE SETTLEMENT AND NOT A PROPOSAL. Creating the settlement is the only way
to know what it comes to, and the figure is what everybody in the route is
agreeing to. So the record is made, and it is the record that is held — the
same shape as a bank file in Phase 5.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

FNF_PROCESS_KEY = 'fnf'


class HrFullFinalSettlementApproval(models.Model):
    _name = 'hr.full.final.settlement'
    _inherit = ['hr.full.final.settlement', 'biz.approval.adapter.mixin']

    _approval_process_key = FNF_PROCESS_KEY

    state = fields.Selection(
        [('draft', 'Being prepared'),
         ('pending', 'Waiting for approval'),
         ('approved', 'Approved'),
         ('returned', 'Sent back'),
         ('rejected', 'Turned down')],
        default='draft', required=True, index=True, readonly=True, copy=False,
        string='Status')
    approved_at = fields.Datetime(string='Approved on', readonly=True,
                                  copy=False)
    approved_by = fields.Many2one('res.users', string='Approved by',
                                  readonly=True, copy=False)

    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'hr_full_final_settlement_seat_rel', 'settlement_id',
        'user_id', string='Asked to decide', copy=False)

    # ==================================================================
    # The adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state == 'approved':
            raise UserError(_("This settlement has already been approved."))
        if self.state == 'pending':
            raise UserError(_("This settlement has already been sent in."))
        return True

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        employee = self.employee_id.sudo()
        return {
            'company_id': company.id,
            'title': _("Final settlement · %s", employee.name or ''),
            'scope_keys': [''],
            'scope_label': company.name,
            'kind_key': self.source or 'manual',
            'facts': {
                'net_amount': {'value': float(self.net_payable or 0.0),
                               'unit': (self.currency_id.name
                                        or company.currency_id.name or '')},
                'employees': {'value': 1, 'unit': ''},
            },
            'amount': float(self.net_payable or 0.0),
            'currency_id': (self.currency_id
                            or company.currency_id).id,
            'maker_uids': [self.create_uid.id] if self.create_uid else [],
            'submitter_uid': self.env.uid,
            'subject_uids': employee.user_id.ids,
            # The MONEY is what is signed for (ledger AM32).
            'source_revision': self._approval_revision_of({
                'net': round(float(self.net_payable or 0.0), 2),
                'earnings': round(float(self.total_earnings or 0.0), 2),
                'deductions': round(float(self.total_deductions or 0.0), 2),
            }),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'net_amount': {'type': 'decimal',
                               'label': _('What they are owed')},
                'employees': {'type': 'int', 'label': _('People')},
            },
            'kinds': [{'key': 'manual', 'label': _('Worked out here')},
                      {'key': 'import', 'label': _('From a file')}],
            'evidence': [],
            'scope_levels': [_('Whole company')],
            'manager_mode': True,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'manual', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        return self.employee_id.name or ''

    def _approval_detail(self, request):
        self.ensure_one()
        summary = self.get_component_summary() or {}
        rows = []
        for key, value in sorted(summary.items()):
            if isinstance(value, (int, float)):
                rows.append({'head': str(key)[:40], 'sub': '',
                             'cells': ['', '{:,.0f}'.format(value)],
                             'tone': 'on'})
            if len(rows) >= 20:
                break
        return {
            'title': _('What it comes to'),
            'columns': ['', _('Amount')],
            'rows': rows,
            'chips': [{'label': _('Net payable'),
                       'value': '{:,.0f}'.format(self.net_payable or 0.0)},
                      {'label': _('Last day'),
                       'value': str(self.settlement_date or '')}],
            'note': '',
        }

    def _approval_freeze(self, request):
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.sudo().write({'state': 'rejected'})
        return True

    def _approval_apply(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'approved',
                           'approved_at': fields.Datetime.now(),
                           'approved_by': self.env.uid})
        return True

    # ------------------------------------------------- the door it protects
    def action_download_full_and_final(self):
        """A settlement nobody has agreed to is not a document."""
        self.ensure_one()
        if self.state != 'approved':
            if self.state == 'pending':
                raise UserError(_(
                    "This settlement is still with %s for approval, so it "
                    "cannot be printed yet.",
                    self._fnf_waiting_for() or _('its approver')))
            if self.state == 'returned':
                raise UserError(_(
                    "This settlement was sent back to be worked out again, "
                    "so what is on it now is nobody's decision. Send it in "
                    "again once it is right."))
            if self.state == 'rejected':
                raise UserError(_(
                    "This settlement was turned down, so there is nothing to "
                    "print."))
            raise UserError(_(
                "This settlement has not been sent for approval yet."))
        return super().action_download_full_and_final()

    def _fnf_waiting_for(self):
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        return ', '.join(sorted({seat.acting_user_id.name or ''
                                 for seat in step.seat_ids
                                 if seat.status == 'open'}))

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', ('hr.group_hr_manager',))
        Seed.fill_role_from_group(
            company, 'finance', ('om_hr_payroll.group_hr_payroll_manager',))
        return Seed.lay(
            company, FNF_PROCESS_KEY, 'Final settlements',
            route(role_step(_('HR lead'), 'hr_lead'),
                  role_step(_('Finance approver'), 'finance')),
            binding_note='The route the last money somebody is paid follows.',
            model_name='hr.full.final.settlement',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when settlement approvals were switched on')


class BizApprovalRequestSeatFnf(models.Model):
    """A seat on a settlement is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'hr.full.final.settlement' \
                    or not request.res_id:
                continue
            record = self.env['hr.full.final.settlement'].sudo().browse(
                request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyFnfSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['hr.full.final.settlement']._approval_seed_default(
                    company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('fnf: %s has no route yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['hr.full.final.settlement']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('fnf: %s has no route yet', company.name)
    return done


def post_init_hook(env):
    seed_all(env)
