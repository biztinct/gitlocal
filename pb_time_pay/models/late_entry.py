# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Decided late and early minutes (owner ruling L5) and dismissed suggestions.

A ROW IS A DECISION, NOT A MEASUREMENT
--------------------------------------
Nothing is stored while minutes are only worked out: the Close reads them live
from the punches. A row is written when a manager CONFIRMS (the minutes count
for pay) or EXCUSES (they do not), and it records the minutes as they stood on
screen at that moment. If the punches change afterwards the Close shows the row
as changed and asks again; pay keeps reading what was decided.

PAID ONCE
---------
`payslip_id` is the reservation. A confirmed row is free until a payslip of the
person's regular run for that period takes it; it is then held by that payslip,
and paid once the payslip is done. A deleted payslip lets go of it (set null);
a cancelled one is read as letting go. A row held by a finished payslip can no
longer be changed or removed.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

#: Payslip states that mean "paid".
DONE_STATES = ('done', 'paid')


class PbTimeLate(models.Model):
    _name = 'pb.time.late'
    _description = 'Late or early minutes, decided'
    _order = 'date desc, employee_id, kind'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, index=True,
                                  ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True)
    date = fields.Date(string='Day', required=True, index=True)
    kind = fields.Selection([('late', 'Late arrival'),
                             ('early', 'Early leave')],
                            string='Kind', required=True)
    minutes = fields.Integer(string='Minutes', required=True)
    state = fields.Selection([('confirmed', 'Confirmed'),
                              ('excused', 'Excused')],
                             string='Decision', required=True)
    basis = fields.Selection([('shift', 'Compared with the shift'),
                              ('hours', 'Compared with working hours')],
                             string='Compared with')
    expected_at = fields.Datetime(string='Expected')
    actual_at = fields.Datetime(string='Punched')
    note = fields.Char(string='Note')
    decided_by_id = fields.Many2one('res.users', string='Decided by',
                                    readonly=True)
    decided_on = fields.Datetime(string='Decided on', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Taken by payslip',
                                 index=True, ondelete='set null',
                                 readonly=True, copy=False)
    pay_state = fields.Selection([('free', 'Not in a payslip yet'),
                                  ('held', 'In a payslip'),
                                  ('paid', 'Paid')],
                                 string='Pay', compute='_compute_pay_state')

    _one_per_day_kind = models.Constraint(
        'UNIQUE(employee_id, date, kind)',
        'There is already a decision for these minutes.')
    _minutes_positive = models.Constraint(
        'CHECK(minutes >= 0)', 'Minutes cannot be negative.')

    @api.depends('payslip_id', 'payslip_id.state')
    def _compute_pay_state(self):
        for row in self:
            slip = row.payslip_id
            if not slip or slip.state == 'cancel':
                row.pay_state = 'free'
            elif slip.state in DONE_STATES:
                row.pay_state = 'paid'
            else:
                row.pay_state = 'held'

    def _key(self):
        self.ensure_one()
        return '%s:%s:%s' % (self.employee_id.id, self.date.isoformat(),
                             self.kind)

    # ------------------------------------------------------------- guards
    def _check_changeable(self):
        for row in self:
            if row.pay_state == 'paid':
                raise UserError(_(
                    "These minutes of %(name)s on %(day)s are already paid "
                    "in payslip %(slip)s, so the decision stays.",
                    name=row.employee_id.name, day=row.date,
                    slip=row.payslip_id.name or row.payslip_id.id))

    def write(self, vals):
        if set(vals) - {'payslip_id'}:
            self._check_changeable()
        return super().write(vals)

    def unlink(self):
        self._check_changeable()
        return super().unlink()

    # ------------------------------------------------------------ decide
    @api.model
    def _decide(self, row, decision, note=False):
        """Record one decision for one live row (a dict of the Close read).

        Refused: your own attendance, a locked day, minutes already paid.
        A row whose minutes are now zero (the punches were corrected) is
        cleared rather than confirmed at zero.
        """
        if row.get('own'):
            raise AccessError(_(
                "You cannot confirm or excuse your own late minutes."))
        employee = self.env['hr.employee'].sudo().browse(row['employee_id'])
        day = fields.Date.to_date(row['date'])
        company = employee.company_id or self.env.company
        self.env['pb.wf.lock']._check_days_open(
            [(company.id, day)], _("Deciding late minutes"))
        found = self.sudo().search([('employee_id', '=', employee.id),
                                    ('date', '=', day),
                                    ('kind', '=', row['kind'])], limit=1)
        if not row.get('minutes'):
            if found:
                found.unlink()
            return False
        vals = {
            'minutes': int(row['minutes']),
            'state': decision,
            'basis': row.get('basis') if row.get('basis') in ('shift', 'hours')
            else False,
            'note': note or False,
            'expected_at': row.get('expected_at') or False,
            'actual_at': row.get('actual_at') or False,
            'decided_by_id': self.env.uid,
            'decided_on': fields.Datetime.now(),
        }
        if found:
            found._check_changeable()
            # a different decision for a held row lets the payslip go: the
            # next recalculation reads the new decision
            if found.pay_state == 'held':
                vals['payslip_id'] = False
            found.write(vals)
            return found
        vals.update({'employee_id': employee.id, 'company_id': company.id,
                     'date': day, 'kind': row['kind']})
        return self.sudo().create(vals)


class PbTimeOtDismiss(models.Model):
    _name = 'pb.time.ot.dismiss'
    _description = 'Overtime suggestion marked as not overtime'
    _order = 'date desc, id desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, index=True,
                                  ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True)
    date = fields.Date(string='Day', required=True, index=True)
    kind = fields.Char(string='Kind of overtime', required=True)
    hours = fields.Float(string='Suggested hours')
    note = fields.Char(string='Note')
    user_id = fields.Many2one('res.users', string='Marked by', readonly=True)

    _one_per_day_kind = models.Constraint(
        'UNIQUE(employee_id, date, kind)',
        'This suggestion is already marked as not overtime.')
