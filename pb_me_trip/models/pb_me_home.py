# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Business trips on the employee home (ETP E2, D7): a "Needs you" row when a
trip was refused or sent back, a source for "My requests", and a "Your next
trip" card — drawn ONLY when an authorised trip is under way or starts within
14 days (quiet at zero). pb_me_portal's three hooks; every read is sudo keyed
on the employee (T-R11) through the `pb.me.trip` facade."""

from odoo import api, models

from .me_trip import STATE_LABELS, STATE_TONES


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        Trips = self.env['pb.me.trip']
        waiting = Trips.waiting_on_me(emp)
        refused, returned = waiting['refused'], waiting['returned']
        if refused:
            n = len(refused)
            first = refused[:1]
            card = Trips.card(first)
            if n == 1:
                label = _('1 trip request refused — fix and resend')
                sentence = _('Your trip request was refused. Fix it and send it again.')
                url = '/my/trips/%s' % first.id
            else:
                label = _('%s trip requests refused — fix and resend', n)
                sentence = _('%s trip requests were refused. Fix them and send them again.', n)
                url = '/my/trips?filter=act'
            put('trip_refused', n, url, label=label,
                sub='%s · %s' % (card['where'], card['dates']),
                icon='plane', tone='rose', sentence=sentence)
        if returned:
            n = len(returned)
            first = returned[:1]
            card = Trips.card(first)
            if n == 1:
                label = _('1 trip request sent back — fix and resend')
                sentence = _('Your trip request was sent back to you. Fix it and send it again.')
                url = '/my/trips/%s' % first.id
            else:
                label = _('%s trip requests sent back — fix and resend', n)
                sentence = _('%s trip requests were sent back to you. Fix them and send them again.', n)
                url = '/my/trips?filter=act'
            put('trip_returned', n, url, label=label,
                sub='%s · %s' % (card['where'], card['dates']),
                icon='plane', tone='amber', sentence=sentence)

    @api.model
    def _my_requests_sources(self):
        sources = super()._my_requests_sources()
        _ = self.env._
        Trips = self.env['pb.me.trip']
        states = {state: (_(STATE_LABELS[state]), STATE_TONES[state])
                  for state in ('draft', 'submitted', 'manager_approved',
                                'finance_approved', 'approved', 'refused',
                                'cancelled')}

        def title(rec):
            where = (rec.destination_city or rec.destination_country_id.name
                     or rec.name or '')
            return _('Trip · %(where)s · %(when)s', where=where,
                     when=Trips.dates_label(rec.date_from, rec.date_to))

        sources.append({
            'key': 'trip', 'model': 'pb.business.trip', 'label': _('Business trip'),
            'icon': 'plane', 'employee_field': 'employee_id',
            'date_field': 'date_from', 'state_field': 'state',
            'states': states,
            'url': lambda rec: '/my/trips/%s' % rec.id,
            'title': title,
        })
        return sources

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        nxt = self.env['pb.me.trip'].next_trip(emp)
        if nxt:
            cards.append({
                'key': 'next_trip',
                'template': 'pb_me_trip.pbme_card_next_trip',
                'data': nxt,
            })
        return cards
