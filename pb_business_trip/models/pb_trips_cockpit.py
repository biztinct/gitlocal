# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models, _

# kanban lane ladder (Refused/Cancelled collapse into a footer filter)
_LANES = [
    ('draft', 'Draft'),
    ('submitted', 'Manager'),
    ('manager_approved', 'Finance'),
    ('finance_approved', 'HR'),
    ('approved', 'Authorized'),
]
_PENDING = ('submitted', 'manager_approved', 'finance_approved')


class PbTrips(models.AbstractModel):
    """RPC facade for the Business Trips cockpit (client action ``pb_trips``)."""
    _name = 'pb.trips'
    _description = 'Business Trips Cockpit API'

    @api.model
    def get_pipeline_data(self):
        Trip = self.env['pb.business.trip']
        co_ids = self.env.companies.ids or [self.env.company.id]
        trips = Trip.search([('company_id', 'in', co_ids)])
        today = date.today()
        month_start = date(today.year, today.month, 1)
        cur = self.env.company.currency_id

        lanes = {key: {'key': key, 'label': label, 'cards': [],
                       'count': 0, 'advance': 0.0} for key, label in _LANES}
        closed = []
        awaiting_me = 0
        days_mtd = 0
        advance_outstanding = 0.0

        for t in trips:
            can_act = t.state in _PENDING and t._can_current_user_act()
            if can_act:
                awaiting_me += 1
            # days travelled this month (approved only)
            if t.state == 'approved' and t.date_from and t.date_to:
                s = max(t.date_from, month_start)
                e = min(t.date_to, today)
                if e >= s:
                    days_mtd += (e - s).days + 1
            if t.state in _PENDING or t.state == 'approved':
                advance_outstanding += t.advance_amount or 0.0

            waiting = (today - (t.write_date.date() if t.write_date else today)).days
            card = {
                'id': t.id,
                'name': t.name,
                'destination': (t.destination_city or '').title() or _('Trip'),
                'country': t.destination_country_id.code or '',
                'employee': t.employee_id.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % t.employee_id.id,
                'date_from': fields.Date.to_string(t.date_from),
                'date_to': fields.Date.to_string(t.date_to),
                'days': t.duration_days,
                'per_diem_total': t.per_diem_total,
                'advance': t.advance_amount,
                'estimated_total': t.estimated_total,
                'state': t.state,
                'waiting_days': max(0, waiting),
                'can_act': can_act,
            }
            if t.state in lanes:
                lanes[t.state]['cards'].append(card)
                lanes[t.state]['count'] += 1
                lanes[t.state]['advance'] += t.advance_amount or 0.0
            else:
                closed.append(card)

        open_count = sum(lanes[k]['count'] for k in
                         ('draft', 'submitted', 'manager_approved', 'finance_approved'))
        return {
            'lanes': [lanes[k] for k, _l in _LANES],
            'closed': closed,
            'currency': cur.symbol or '',
            'currency_position': cur.position or 'after',
            'kpis': {
                'open': open_count,
                'awaiting_me': awaiting_me,
                'days_mtd': days_mtd,
                'advance_outstanding': round(advance_outstanding, 2),
            },
        }
