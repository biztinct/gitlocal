# -*- coding: utf-8 -*-
"""“This person needs a laptop.”

A request is the only way an item is meant to arrive on somebody's desk, and it
answers two questions in order: is this agreed, and is there already one in the
cupboard. Spares first — the cheapest laptop is the one already bought.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .asset_common import (
    FULFILMENTS, MANAGER_GROUPS, REQUEST_STATES,
)

_logger = logging.getLogger(__name__)


class PbAssetRequest(models.Model):
    _name = 'pb.asset.request'
    _description = 'Asset Request'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'needed_by, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Who it is for', required=True, index=True,
        tracking=True)
    manager_id = fields.Many2one(
        'hr.employee', string='Their manager', related='employee_id.parent_id',
        store=True, readonly=True)
    category_id = fields.Many2one(
        'pb.asset.category', string='What they need', required=True,
        tracking=True)
    country_id = fields.Many2one(
        'res.country', string='Country', index=True,
        help='Where the item is needed. It decides which spares can be used.')
    needed_by = fields.Date(string='Needed by', tracking=True)
    justification = fields.Text(string='Why')

    spare_asset_id = fields.Many2one(
        'pb.asset', string='Suggested spare', readonly=True,
        help='The oldest matching item sitting unused. Payobook looks for one '
             'every time the request is saved.')
    asset_id = fields.Many2one(
        'pb.asset', string='Item given', readonly=True, tracking=True)
    assignment_id = fields.Many2one(
        'pb.asset.assignment', string='Handover', readonly=True)
    journey_task_id = fields.Many2one(
        'pb.journey.task', string='Checklist step', readonly=True,
        ondelete='set null',
        help='The joining step this request answers, when it came from one.')

    state = fields.Selection(
        REQUEST_STATES, string='Status', default='draft', required=True,
        index=True, copy=False, tracking=True)
    fulfilment = fields.Selection(
        FULFILMENTS, string='Progress', default='todo', required=True,
        index=True, tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    approval_widget_json = fields.Char(
        compute='_compute_approval_widget', string='Approval trail')

    # Cosmetic button gates — the server's `_approval_can` is the real answer.
    can_submit = fields.Boolean(compute='_compute_can')
    can_manager_approve = fields.Boolean(compute='_compute_can')
    can_final_approve = fields.Boolean(compute='_compute_can')
    can_refuse = fields.Boolean(compute='_compute_can')
    can_fulfil = fields.Boolean(compute='_compute_can')

    # The ladder. Two tiers: the person's manager agrees they need it, the
    # asset team agrees to hand one over.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'manager_approved'): MANAGER_GROUPS[0],
        ('manager_approved', 'approved'): 'pb_assets.group_assets_manager',
    }
    _approval_dead_states = ('refused', 'cancelled')

    # ---------------------------------------------------------------- computes
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.name or _('Request'), rec.category_id.name or '')

    @api.depends('state')
    def _compute_approval_widget(self):
        steps = [
            {'state': 'draft', 'label': _('Asked for'),
             'group_label': _('Requester')},
            {'state': 'submitted', 'label': _('Sent'),
             'group_label': _('Requester')},
            {'state': 'manager_approved', 'label': _('Manager'),
             'group_label': _('Line manager')},
            {'state': 'approved', 'label': _('Approved'),
             'group_label': _('Asset team')},
        ]
        for rec in self:
            rec.approval_widget_json = (
                rec._approval_widget_payload(steps) if rec.id else False)

    @api.depends('state', 'fulfilment', 'employee_id', 'manager_id')
    def _compute_can(self):
        for rec in self:
            s = rec.state
            rec.can_submit = s == 'draft' and rec._approval_can(
                'draft', 'submitted')
            rec.can_manager_approve = s == 'submitted' and rec._approval_can(
                'submitted', 'manager_approved')
            rec.can_final_approve = s == 'manager_approved' \
                and rec._approval_can('manager_approved', 'approved')
            rec.can_refuse = s in ('submitted', 'manager_approved') \
                and rec._approval_can_refuse(s)
            rec.can_fulfil = (s == 'approved'
                              and rec.fulfilment not in ('delivered',
                                                         'confirmed'))

    # ----------------------------------------------------------- authorization
    def _user_in_any(self, xmlids):
        for x in xmlids:
            try:
                if self.env.user.has_group(x):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _approval_can(self, from_state, to_state):
        """The line manager passes tier two without holding any group.

        Otherwise a small company — where the manager is not in the HR group —
        has a request nobody can move, which is the dead end safety rail 4 was
        written about.
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        user = self.env.user
        rec = self.sudo()
        pair = (from_state, to_state)
        if pair == ('draft', 'submitted'):
            if rec.employee_id.user_id and rec.employee_id.user_id == user:
                return True
            if rec.create_uid == user:
                return True
            return self._user_in_any(MANAGER_GROUPS + (
                'pb_assets.group_assets_manager',))
        if pair == ('submitted', 'manager_approved'):
            if rec.manager_id and rec.manager_id.user_id == user:
                return True
            return self._user_in_any(MANAGER_GROUPS + (
                'pb_assets.group_assets_manager',))
        if pair == ('manager_approved', 'approved'):
            return self._user_in_any(('pb_assets.group_assets_manager',))
        return False

    # --------------------------------------------------------------- lifecycle
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'pb.asset.request') or _('New')
            if not vals.get('country_id'):
                vals['country_id'] = self._country_for(
                    vals.get('employee_id'))
        records = super().create(vals_list)
        records._suggest_spare()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'category_id', 'country_id'} & set(vals):
            self._suggest_spare()
        return res

    @api.model
    def _country_for(self, employee_id):
        employee = self.env['hr.employee'].browse(
            int(employee_id or 0)).exists()
        if not employee:
            return False
        company = employee.company_id or self.env.company
        return (company.country_id.id if company.country_id else False)

    @api.onchange('employee_id')
    def _onchange_employee(self):
        if self.employee_id and not self.country_id:
            self.country_id = self._country_for(self.employee_id.id)

    def _suggest_spare(self):
        for rec in self:
            if rec.state in ('refused', 'cancelled') or rec.asset_id:
                continue
            if not rec.category_id:
                continue
            spare = self.env['pb.asset'].find_spare(
                rec.category_id.id, rec.country_id.id or None)
            rec.spare_asset_id = spare.id or False
            if spare and rec.fulfilment == 'todo':
                rec.fulfilment = 'spare'
        return True

    # ---------------------------------------------------------------- actions
    def action_submit(self):
        self.ensure_one()
        self._advance_state('submitted')
        return True

    def action_manager_approve(self):
        self.ensure_one()
        return self._advance_state('manager_approved')

    def action_final_approve(self):
        self.ensure_one()
        return self._advance_state('approved')

    def action_cancel(self):
        for rec in self:
            if rec.state in ('cancelled', 'refused'):
                raise UserError(_("This request is already closed."))
            frm = rec.state
            rec._chain_state_write('cancelled')
            rec._log_transition(frm, 'cancelled', _('Cancelled'))
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('submitted', 'refused'):
                raise UserError(_(
                    "Only a request that is waiting or was turned down can go "
                    "back to draft."))
            frm = rec.state
            rec._chain_state_write('draft')
            rec._log_transition(frm, 'draft', _('Back to draft'))
        return True

    def action_fulfil(self, asset_id=None, condition_out=None):
        """Hand over the item this request was for."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_(
                "This request has not been approved yet, so nothing can be "
                "handed over."))
        Asset = self.env['pb.asset']
        asset = Asset.browse(int(asset_id)).exists() if asset_id \
            else (self.spare_asset_id or Asset.find_spare(
                self.category_id.id, self.country_id.id or None))
        if not asset:
            raise UserError(_(
                "There is nothing spare to give. Add the item to the register "
                "first, then hand it over from here."))
        assignment = asset.action_assign(
            self.employee_id.id, condition_out=condition_out,
            notes=_('From request %s', self.name))
        self.write({
            'asset_id': asset.id,
            'assignment_id': assignment.id,
            'fulfilment': 'delivered',
        })
        self.message_post(body=_(
            "%(what)s was handed to %(who)s.",
            what=asset.display_name, who=self.employee_id.name or ''))
        if self.journey_task_id and self.journey_task_id.state not in (
                'done', 'skipped'):
            try:
                self.journey_task_id.action_done()
            except Exception:       # noqa: BLE001 — never lose the handover
                _logger.exception('pb_assets: could not tick step %s',
                                  self.journey_task_id.id)
        return True

    def action_open_asset(self):
        self.ensure_one()
        if not self.asset_id:
            raise UserError(_("Nothing has been handed over yet."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }
