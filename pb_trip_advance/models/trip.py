# -*- coding: utf-8 -*-
"""The trip's buttons (record the advance as given, settle it, record a cash
repayment), the small form they open, and the trips board's real
"advance outstanding"."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

from odoo.addons.pb_expense_payroll.models.common import TOKEN_KEY, WRITE_TOKEN

from .advance import can_manage

_PENDING_OR_APPROVED = ('submitted', 'manager_approved', 'finance_approved', 'approved')


class PbBusinessTripAdvance(models.Model):
    _inherit = 'pb.business.trip'

    pb_advance_ids = fields.One2many('pb.trip.advance', 'trip_id', string='Cash advance',
                                     readonly=True)
    pb_advance_state = fields.Selection(related='pb_advance_ids.state',
                                        string='Cash advance status')
    pb_advance_left = fields.Monetary(related='pb_advance_ids.left',
                                      string='Still to take back')
    pb_advance_return_reason = fields.Text(related='pb_advance_ids.return_reason',
                                           string='Why the settlement was sent back')

    def _pb_wizard(self, mode):
        self.ensure_one()
        if not can_manage(self.env):
            raise AccessError(_("Only finance or the pay team can do this."))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'pb.trip.advance.wizard',
            'view_mode': 'form', 'target': 'new',
            'name': {'given': _("Cash advance given"), 'settle': _("Settle the cash advance"),
                     'cash': _("Paid back directly"),
                     'sendback': _("Send the settlement back")}[mode],
            'context': {'default_trip_id': self.id, 'default_mode': mode},
        }

    def action_pb_advance_given(self):
        self.ensure_one()
        if self.state != 'approved' or not self.advance_amount:
            raise UserError(_("Only an authorized trip with a cash advance can have it "
                              "recorded as given."))
        if self.sudo().pb_advance_ids:
            raise UserError(_("This trip's cash advance is already recorded."))
        return self._pb_wizard('given')

    def action_pb_advance_settle(self):
        self.ensure_one()
        adv = self.sudo().pb_advance_ids[:1]
        if not adv or adv.state != 'given':
            raise UserError(_("Record the cash advance as given first."))
        return self._pb_wizard('settle')

    def _pb_waiting_advance(self):
        self.ensure_one()
        adv = self.sudo().pb_advance_ids[:1]
        if not adv or adv.state != 'waiting':
            raise UserError(_("No settlement of this trip is waiting for approval."))
        return self.env['pb.trip.advance'].browse(adv.id)

    def action_pb_advance_approve(self):
        """The Head of pay approves the settlement from the trip (the same
        decision as in Approvals; the engine checks the seat and who may
        not decide)."""
        self._pb_waiting_advance()._advance_state('settled')
        return True

    def action_pb_advance_sendback(self):
        self._pb_waiting_advance()
        return self._pb_wizard('sendback')

    def action_pb_advance_cash(self):
        self.ensure_one()
        adv = self.sudo().pb_advance_ids[:1]
        if not adv or adv.state != 'settled':
            raise UserError(_("Nothing is waiting to be paid back on this trip."))
        return self._pb_wizard('cash')


class PbTripAdvanceWizard(models.TransientModel):
    _name = 'pb.trip.advance.wizard'
    _description = 'Trip cash advance: given, settled, paid back'

    trip_id = fields.Many2one('pb.business.trip', required=True, readonly=True)
    mode = fields.Selection([('given', 'Given'), ('settle', 'Settle'), ('cash', 'Cash'),
                             ('sendback', 'Send back')],
                            required=True, readonly=True)
    currency_id = fields.Many2one(related='trip_id.currency_id')
    day = fields.Date(string='On', default=fields.Date.context_today)
    reference = fields.Char(string='Reference')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    recover_how = fields.Selection([('pay', 'Take it back from the next pay'),
                                    ('cash', 'The person pays it back directly')],
                                   string='The part not spent', default='pay')
    reason = fields.Text(string='Why')
    preview = fields.Text(compute='_compute_preview')

    @api.depends('trip_id', 'mode')
    def _compute_preview(self):
        for wiz in self:
            text = ''
            adv = wiz.trip_id.sudo().pb_advance_ids[:1]
            if wiz.mode == 'settle' and adv:
                p = adv._settle_preview()
                lines = [_("Advance given: %s", adv._money(adv.amount)),
                         _("Claimed against it (approved, not paid yet): %s",
                           adv._money(p['claimed']))]
                if p['unspent']:
                    lines.append(_("Not spent: %s", adv._money(p['unspent'])))
                if p['extra_due']:
                    lines.append(_("Spent above the advance: %s — paid with the claims as "
                                   "usual", adv._money(p['extra_due'])))
                if p['waiting']:
                    lines.append(_("Still waiting approval (decide these first): %s",
                                   ', '.join(p['waiting'].mapped('name'))))
                if p['drafts']:
                    lines.append(_("Not counted (not sent, or refused): %s",
                                   ', '.join(p['drafts'].mapped('name'))))
                text = '\n'.join(lines)
            elif wiz.mode == 'cash' and adv:
                text = _("Still to be paid back: %s", adv._money(adv.left))
            elif wiz.mode == 'given':
                text = _("Advance on this trip: %s", formatLang(
                    self.env, wiz.trip_id.advance_amount or 0.0,
                    currency_obj=wiz.trip_id.currency_id))
            wiz.preview = text

    def action_confirm(self):
        self.ensure_one()
        if self.mode == 'sendback':
            reason = (self.reason or '').strip()
            if len(reason) < 4:
                raise UserError(_("Say why it is sent back. Finance sees it on the trip."))
            self.trip_id._pb_waiting_advance()._advance_state('given', note=reason)
            return {'type': 'ir.actions.act_window_close'}
        if not can_manage(self.env):
            raise AccessError(_("Only finance or the pay team can do this."))
        trip = self.trip_id.sudo()
        if self.mode == 'given':
            if trip.state != 'approved' or not trip.advance_amount or trip.pb_advance_ids:
                raise UserError(_("This trip's cash advance cannot be recorded now."))
            if self.day and self.day > fields.Date.context_today(self):
                raise UserError(_("The day it was given cannot be in the future."))
            adv = self.env['pb.trip.advance'].with_context(
                **{TOKEN_KEY: WRITE_TOKEN}).sudo().create({
                    'trip_id': trip.id, 'employee_id': trip.employee_id.id,
                    'company_id': trip.company_id.id, 'currency_id': trip.currency_id.id,
                    'amount': trip.advance_amount, 'state': 'given',
                    'given_on': self.day or fields.Date.context_today(self),
                    'given_ref': (self.reference or '').strip()[:120] or False,
                    'given_by': self.env.uid})
            body = _("Cash advance of %(amount)s given on %(day)s.",
                     amount=adv._money(adv.amount), day=format_date(self.env, adv.given_on))
            adv.message_post(body=body)
            trip.message_post(body=body)
        elif self.mode == 'settle':
            # as the person who settles (the request's submitter), not sudo
            self.env['pb.trip.advance'].browse(trip.pb_advance_ids[:1].id) \
                ._settle_request(self.recover_how or 'pay')
        elif self.mode == 'cash':
            trip.pb_advance_ids[:1]._record_cash(self.amount, self.day,
                                                 (self.reference or '').strip()[:120])
        return {'type': 'ir.actions.act_window_close'}


class PbTripsAdvance(models.AbstractModel):
    _inherit = 'pb.trips'

    @api.model
    def _pb_real_outstanding(self, old):
        """The board's "advance outstanding" with tracked advances counted
        by what is really out: given and not settled → the whole advance;
        settled → what is still to take back; closed → nothing. A trip whose
        advance nobody recorded counts as it always did, so a company that
        never records advances sees exactly the figure it saw before."""
        co = self.env.companies.ids or [self.env.company.id]
        currency = self.env.company.currency_id
        Adv = self.env['pb.trip.advance'].sudo()
        advs = Adv.search([('company_id', 'in', co),
                           ('trip_id.state', 'in', list(_PENDING_OR_APPROVED))])
        if not advs:
            return old
        was = sum(advs.mapped('trip_id.advance_amount'))
        real = 0.0
        for adv in advs.filtered(lambda a: a.currency_id == currency):
            if adv.state in ('given', 'waiting'):
                real += adv.amount
            elif adv.state == 'settled':
                real += adv.left
        return round((old or 0.0) - was + real, 2)

    @api.model
    def get_trips_head(self):
        out = super().get_trips_head()
        try:
            kpis = out.get('kpis') or {}
            kpis['advance_outstanding'] = self._pb_real_outstanding(
                kpis.get('advance_outstanding'))
        except Exception:       # noqa: BLE001 — a figure never breaks the board
            pass
        return out

    @api.model
    def get_pipeline_data(self):
        out = super().get_pipeline_data()
        try:
            kpis = out.get('kpis') or {}
            kpis['advance_outstanding'] = self._pb_real_outstanding(
                kpis.get('advance_outstanding'))
        except Exception:       # noqa: BLE001
            pass
        return out
