# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Pay it, or give time off (owner rulings L3 and L4).

THE CHOICE
----------
`pb_comp_choice` — empty or "pay" means the overtime is paid exactly as before;
"time_off" means that, when the overtime is approved, the person receives the
same number of hours (hour for hour, L3) as time off in lieu, and those hours
are NOT also paid (`hr_payslip.py` takes them back out above both overtime
producers). The hours never run out (L4: no expiry, no payout).

WHO CHOOSES, AND WHEN
---------------------
The person who may decide the overtime (the overtime model's own rule,
`_ot_can_decide`), while it is still being decided — draft or sent in. Once it
is approved the choice is money, and it is sealed with this module's own token,
the pattern the overtime model uses for its own sealed fields. Locked days and
frozen weeks refuse a change exactly as they refuse any other.

EMPTY, NOT "pay", ON EXISTING ROWS
----------------------------------
The field has no column default, so installing this module rewrites no stored
overtime: every request that existed before reads "pay" because it is empty.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_TP_KEY = 'pb_time_pay_write'
_TP_TOKEN = object()
_TP_SEALED = {'pb_comp_choice', 'pb_toil_allocation_id', 'pb_from_punches'}


class HrOvertimeRequestTimePay(models.Model):
    _inherit = 'hr.overtime.request'

    pb_comp_choice = fields.Selection(
        [('pay', 'Pay it'), ('time_off', 'Give time off')],
        string='When approved', copy=False, tracking=True,
        help='Pay it: the hours are paid as overtime. Give time off: the '
             'same number of hours become time off in lieu and are not '
             'also paid.')
    pb_toil_allocation_id = fields.Many2one(
        'hr.leave.allocation', string='Time off given', readonly=True,
        copy=False, ondelete='restrict')
    pb_from_punches = fields.Boolean(
        string='Suggested from clock punches', readonly=True, copy=False)
    pb_comp_label = fields.Char(compute='_compute_pb_comp_label',
                                string='Paid or time off')

    @api.depends('pb_comp_choice', 'state')
    def _compute_pb_comp_label(self):
        for rec in self:
            if rec.pb_comp_choice == 'time_off':
                rec.pb_comp_label = (_("Given as time off")
                                     if rec.state == 'approved'
                                     else _("Time off when approved"))
            else:
                rec.pb_comp_label = _("Paid")

    # ------------------------------------------------------------ the seal
    def _pb_tp_ok(self):
        return self.env.context.get(_TP_KEY) is _TP_TOKEN

    def _pb_tp(self):
        return self.with_context(**{_TP_KEY: _TP_TOKEN})

    @api.model_create_multi
    def create(self, vals_list):
        choice = self.env.context.get('pb_time_pay_choice')
        for vals in vals_list:
            forged = _TP_SEALED.intersection(vals)
            if forged and not (self._pb_tp_ok() or self.env.su):
                for name in forged:
                    vals.pop(name)
            if choice == 'time_off' and (self.env.su or self._pb_tp_ok()):
                vals.setdefault('pb_comp_choice', 'time_off')
        return super().create(vals_list)

    def write(self, vals):
        forged = _TP_SEALED.intersection(vals)
        if forged and not self._pb_tp_ok():
            if not self.env.su:
                raise AccessError(_(
                    "Whether overtime is paid or given as time off changes "
                    "only through the overtime screens."))
            # even the superuser may not turn approved money into time off
            if 'pb_comp_choice' in vals and any(
                    r.state == 'approved'
                    and (r.pb_comp_choice or 'pay') != (vals['pb_comp_choice']
                                                        or 'pay')
                    for r in self):
                raise UserError(_(
                    "This overtime is already approved, so whether it is "
                    "paid or given as time off can no longer change."))
        return super().write(vals)

    # ---------------------------------------------------------- the choice
    def _pb_set_choice(self, choice):
        """The one door that changes the choice. Refused once approved or
        refused, refused for somebody who may not decide this overtime, and
        refused on a locked day (the week is closed)."""
        for rec in self:
            if rec.state not in ('draft', 'submitted'):
                raise UserError(_(
                    "%(name)s is already %(state)s, so whether it is paid or "
                    "given as time off can no longer change.",
                    name=rec.name, state=dict(rec._fields['state']
                                              ._description_selection(
                                                  self.env)).get(rec.state)))
            if not rec._ot_can_decide():
                raise AccessError(_(
                    "Only somebody who may decide %s can choose between pay "
                    "and time off.", rec.name))
            if 'pb.wf.lock' in self.env and hasattr(rec, '_pb_check_open'):
                rec._pb_check_open(_("Changing pay or time off"))
            if (rec.pb_comp_choice or 'pay') == choice:
                continue
            rec.sudo()._pb_tp().write({'pb_comp_choice': choice})
        return True

    def action_pb_give_time_off(self):
        self._pb_set_choice('time_off')
        return True

    def action_pb_pay_it(self):
        self._pb_set_choice('pay')
        return True

    # ------------------------------------------------------ on approval
    def action_approve(self):
        todo = self.filtered(lambda r: r.state == 'submitted')
        result = super().action_approve()
        for rec in todo:
            if rec.state == 'approved' and rec.pb_comp_choice == 'time_off' \
                    and not rec.pb_toil_allocation_id:
                rec._pb_give_time_off()
        return result

    def _pb_toil_hours(self):
        """Hour for hour (L3): everything the approval split decided — the
        hours within the ceiling and the bonus hours beyond it."""
        self.ensure_one()
        return round((self.approved_hours or 0.0) + (self.bonus_hours or 0.0),
                     2)

    def _pb_give_time_off(self):
        """One allocation of the company's time off in lieu, for exactly the
        approved hours, from the overtime's day, never expiring (L4). Raised
        failures roll the approval back with it: overtime that is neither
        paid nor given as time off must never exist."""
        self.ensure_one()
        hours = self._pb_toil_hours()
        if hours <= 0:
            return False
        employee = self.employee_id.sudo()
        company = self.company_id or employee.company_id or self.env.company
        kind = self.env['pb.time.pay']._toil_kind(company)
        per_day = employee._get_hours_per_day(self.date) or 8.0
        Alloc = self.env['hr.leave.allocation'].sudo().with_context(
            mail_create_nolog=True, mail_notrack=True)
        day = self.date.strftime('%d %b %Y') if self.date else ''
        alloc = Alloc.create({
            'name': _("Time off in lieu for overtime on %s", day),
            'employee_id': employee.id,
            'holiday_status_id': kind.id,
            'allocation_type': 'regular',
            'number_of_days': hours / per_day,
            'date_from': self.date,
            'date_to': False,
            'notes': _("%(hours)s h of overtime on %(day)s, given as time off "
                       "instead of pay.", hours='{:g}'.format(hours), day=day),
        })
        if alloc.state != 'validate':
            alloc.action_approve()
        if alloc.state != 'validate':
            raise UserError(_(
                "The time off for %s could not be given (it needs another "
                "approval in Time Off), so this overtime was not approved. "
                "Pay it instead, or ask HR.", self.name))
        self.sudo()._pb_tp().write({'pb_toil_allocation_id': alloc.id})
        self.sudo().message_post(body=_(
            "%(hours)s h given as time off in lieu instead of pay.",
            hours='{:g}'.format(hours)))
        return alloc

    # ------------------------------------------------- the approvals inbox
    def _approval_detail(self, request):
        detail = super()._approval_detail(request)
        try:
            if isinstance(detail, dict):
                chips = list(detail.get('chips') or [])
                chips.append({
                    'label': _('When approved'),
                    'value': (_('Give time off') if self.pb_comp_choice ==
                              'time_off' else _('Pay it'))})
                if self.pb_from_punches:
                    chips.append({'label': _('From'),
                                  'value': _('Clock punches')})
                detail['chips'] = chips
        except Exception:                                   # noqa: BLE001
            _logger.debug('pb_time_pay: approval detail', exc_info=True)
        return detail
