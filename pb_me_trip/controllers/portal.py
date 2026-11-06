# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/trips` — ask for a business trip and follow it (ETP E2).

THE ROUTE IS THE GATE (ledger E-R2). The employee is re-resolved from the
SESSION on every request (`_ess_employee`, pb_me_portal); no route accepts an
employee id. A trip reached by id is browsed under sudo and served only when
its employee is one of the session's own (`_ess_own_employees`); anything else
is a styled 404, for a GET and a POST alike, and nothing is written. Every
write then goes through the `pb.me.trip` facade, which checks ownership again
and re-states the guards sudo switches off (E-R3).

EVERY POST: guard → savepoint → redirect with `?done=` on success, or the same
page again with the reason on failure (a UserError / ValidationError is shown
as it is: those words are already plain). Never a traceback, never a bare 500.

NO JAVASCRIPT NEEDED (E-R8). The form posts `action=send|save`; "Add a line",
a row's remove button and Enter in a field post `action=add_line`,
`remove_line:<n>` and `refresh`, which re-render the form (and its card) and
write nothing. The script only does the same things in place.
"""

import logging
import re

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

from ..models.me_trip import BUCKETS, MAX_LINES

_logger = logging.getLogger(__name__)

#: `?done=` keys the pages say a toast for (the template owns the words).
_DONE = ('sent', 'saved', 'withdrawn', 'reopened', 'line_added', 'line_removed')
#: The form's row fields: `line-<n>-category`, `line-<n>-amount`, `line-<n>-note`.
_LINE_KEY = re.compile(r'^line-(\d{1,3})-(category|amount|note)$')
#: The answers the form posts (anything else in the request is ignored).
_FORM_KEYS = ('destination_country_id', 'destination_city', 'date_from', 'date_to',
              'purpose', 'advance_amount')
_REFUSED = (AccessError, UserError, ValidationError)


def _reason(exc):
    """The plain words of a refusal (stock and the facade both raise them)."""
    return str(exc.args[0] if exc.args else exc)


class PbMeTripPortal(PbMePortal):

    # ------------------------------------------------------------ helpers
    def _trip_own(self, trip_id):
        """The trip as a SUDO record when one of the session's own employees
        asked for it, else an empty recordset (the ownership guard)."""
        Trip = request.env['pb.business.trip'].sudo()
        try:
            trip = Trip.browse(int(trip_id)).exists()
        except (TypeError, ValueError):
            return Trip.browse()
        if trip and trip.employee_id in self._ess_own_employees():
            return trip
        return Trip.browse()

    def _trip_not_found(self):
        return request.render('pb_me_trip.portal_trip_missing',
                              {'page_name': 'trip_missing'}, status=404)

    def _trip_ask_hr_url(self, category='other'):
        if 'pb.ask.hr.ticket' in request.env:
            return '/my/ask-hr/new?category=%s' % category
        return None

    # ------------------------------------------------------ home counter
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'trip_count' in counters:
            emp = self._ess_employee()
            n = 0
            if emp:
                waiting = request.env['pb.me.trip'].waiting_on_me(emp)
                n = len(waiting['refused']) + len(waiting['returned'])
            values['trip_count'] = n
        return values

    # =============================================================== list
    @http.route(['/my/trips'], type='http', auth='user', website=True)
    def portal_my_trips(self, filter=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        bucket = filter if filter in BUCKETS else 'all'
        data = request.env['pb.me.trip'].own_trips(emp, bucket if bucket != 'all' else None)
        values = {
            'page_name': 'trips',
            'bucket': bucket,
            'rows': data['rows'],
            'counts': data['counts'],
            'next_trip': data['next'],
            'done': kw.get('done') if kw.get('done') in _DONE else None,
        }
        return request.render('pb_me_trip.portal_my_trips', values)

    # =========================================================== the form
    def _trip_form_post(self, post):
        """``(values, lines, action)`` from a posted form: only the known
        answers (``_FORM_KEYS`` + the "Major city" box) and the indexed cost
        rows, in row order."""
        values = {key: (post.get(key) or '').strip() for key in _FORM_KEYS}
        values['tier'] = bool(post.get('tier'))
        rows = {}
        for key, value in post.items():
            match = _LINE_KEY.match(key)
            if match:
                rows.setdefault(int(match.group(1)), {})[match.group(2)] = (value or '').strip()
        lines = [{'n': n,
                  'category_id': rows[n].get('category') or '',
                  'amount': rows[n].get('amount') or '',
                  'description': rows[n].get('note') or ''}
                 for n in sorted(rows)][:MAX_LINES + 1]
        return values, lines, (post.get('action') or 'send').strip()

    def _trip_preview_card(self, emp, values, lines):
        """The live card as the server draws it for the values typed so far
        (the same arithmetic as the record's computes, `preview`)."""
        Trips = request.env['pb.me.trip']
        Country = request.env['res.country'].sudo()
        try:
            country = Country.browse(int(values.get('destination_country_id') or 0)).exists()
        except (TypeError, ValueError):
            country = Country.browse()
        policy = Trips.policy_for(emp, country.id, values.get('tier'))
        amounts = []
        for line in lines:
            try:
                amounts.append(max(0.0, Trips._amount(line.get('amount')) or 0.0))
            except UserError:
                continue
        try:
            advance = max(0.0, Trips._amount(values.get('advance_amount')) or 0.0)
        except UserError:
            advance = 0.0
        pre = Trips.preview({'date_from': values.get('date_from'),
                             'date_to': values.get('date_to'),
                             'per_diem_rate': policy['rate'],
                             'line_amounts': amounts, 'advance_amount': advance})
        currency = policy['currency']
        fmt = lambda v: Trips.fmt_money(v, currency)  # noqa: E731
        try:
            d1 = fields.Date.to_date(values.get('date_from') or None)
            d2 = fields.Date.to_date(values.get('date_to') or None)
        except (TypeError, ValueError):
            d1 = d2 = None
        return {
            'id': False, 'ref': '',
            'city': values.get('destination_city') or '',
            'country': country.name or '',
            'where': Trips.where_label(values.get('destination_city'), country),
            'dates': Trips.dates_label(d1, d2) if d1 and d2 and d2 >= d1 else '',
            'days': pre['days'],
            'channel': policy['channel'],
            'currency': currency,
            'rate': pre['rate'], 'allowance': pre['allowance'], 'advance': pre['advance'],
            'lines_total': pre['lines_total'], 'estimated': pre['estimated'],
            'money': {'rate': fmt(pre['rate']), 'allowance': fmt(pre['allowance']),
                      'advance': fmt(pre['advance']), 'lines': fmt(pre['lines_total']),
                      'estimated': fmt(pre['estimated'])},
            'has_tier1': policy['has_tier1'],
            'purpose': values.get('purpose') or '',
        }

    def _trip_countries(self, emp):
        """The country picker: the countries a policy names and the
        company's own first, then every country."""
        Country = request.env['res.country'].sudo()
        common_ids = list(request.env['pb.me.trip'].policy_country_ids(emp))
        home = emp.company_id.country_id
        if home and home.id not in common_ids:
            common_ids.insert(0, home.id)
        common = Country.browse(common_ids).sorted('name')
        rest = Country.search([('id', 'not in', common.ids)], order='name')
        return common, rest

    def _trip_render_form(self, emp, values, lines, trip=None, error=None, done=None):
        Trips = request.env['pb.me.trip']
        values = dict(values or {})
        if not values.get('destination_country_id') and emp.company_id.country_id:
            values['destination_country_id'] = emp.company_id.country_id.id
        rows = [line for line in (lines or [])] or [{'category_id': '', 'amount': '', 'description': ''}]
        for n, row in enumerate(rows):
            row['n'] = n
        common, rest = self._trip_countries(emp)
        try:
            country_id = int(values.get('destination_country_id') or 0)
        except (TypeError, ValueError):
            country_id = 0
        render = {
            'page_name': 'trip_edit' if trip else 'trips_new',
            'trip': trip,
            'ref': trip.name if trip else '',
            'action_url': '/my/trips/%s/edit' % trip.id if trip else '/my/trips/new',
            'values': values,
            'country_id': country_id,
            'rows': rows,
            'next_row': len(rows),
            'categories': Trips.categories(),
            'countries_common': common,
            'countries_rest': rest,
            'card': self._trip_preview_card(emp, values, rows),
            'facts': Trips.form_facts(emp),
            'company_currency_id': emp.company_id.currency_id.id,
            'steps': Trips.route_preview(emp),
            'error': error,
            'done': done if done in _DONE else None,
            'max_lines': MAX_LINES,
        }
        return request.render('pb_me_trip.portal_trip_form', render)

    def _trip_form_rerender(self, action, values, lines):
        """`add_line` / `remove_line:<n>` / `refresh`: the no-script path.
        Returns the rows to draw, or ``None`` when ``action`` writes."""
        if action == 'add_line':
            if len(lines) < MAX_LINES:
                lines = lines + [{'category_id': '', 'amount': '', 'description': ''}]
            return lines
        if action.startswith('remove_line:'):
            try:
                n = int(action.split(':', 1)[1])
            except ValueError:
                return lines
            return [line for line in lines if line.get('n') != n]
        if action in ('send', 'save'):
            return None
        # `refresh` (Enter in a field without the script) or anything unknown:
        # draw the form again, write nothing
        return lines

    @http.route(['/my/trips/new'], type='http', auth='user', website=True,
                methods=['GET'])
    def portal_trip_new(self, copy=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        values, lines = {}, []
        if copy:
            source = self._trip_own(copy)
            if source:
                values, lines = request.env['pb.me.trip'].copy_values(source)
        return self._trip_render_form(emp, values, lines)

    @http.route(['/my/trips/new'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_trip_create(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        values, lines, action = self._trip_form_post(post)
        rows = self._trip_form_rerender(action, values, lines)
        if rows is not None:
            return self._trip_render_form(emp, values, rows)
        Trips = request.env['pb.me.trip']
        try:
            # E-R2: the facade forces the session's employee and checks every
            # answer; create + send are one savepoint, so a refused send
            # leaves nothing behind
            with request.env.cr.savepoint():
                trip = Trips.new_trip(emp, values, lines)
                if action == 'send':
                    Trips.send(trip)
        except _REFUSED as exc:
            _logger.info('pb_me_trip: a new trip was refused: %s', exc)
            return self._trip_render_form(emp, values, lines, error=_reason(exc))
        done = 'sent' if action == 'send' else 'saved'
        return request.redirect('/my/trips/%s?done=%s' % (trip.id, done))

    @http.route(['/my/trips/<int:trip_id>/edit'], type='http', auth='user',
                website=True, methods=['GET'])
    def portal_trip_edit(self, trip_id, **kw):
        trip = self._trip_own(trip_id)
        if not trip:
            return self._trip_not_found()
        if trip.state != 'draft':
            return request.redirect('/my/trips/%s' % trip.id)
        values, lines = request.env['pb.me.trip'].copy_values(trip)
        return self._trip_render_form(trip.employee_id, values, lines, trip=trip,
                                      done=kw.get('done'))

    @http.route(['/my/trips/<int:trip_id>/edit'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_trip_update(self, trip_id, **post):
        trip = self._trip_own(trip_id)
        if not trip:
            return self._trip_not_found()
        emp = trip.employee_id
        values, lines, action = self._trip_form_post(post)
        rows = self._trip_form_rerender(action, values, lines)
        if rows is not None:
            return self._trip_render_form(emp, values, rows, trip=trip)
        Trips = request.env['pb.me.trip']
        try:
            with request.env.cr.savepoint():
                Trips.update_trip(trip, values, lines)
                if action == 'send':
                    Trips.send(trip)
        except _REFUSED as exc:
            _logger.info('pb_me_trip: a trip change was refused: %s', exc)
            return self._trip_render_form(emp, values, lines, trip=trip, error=_reason(exc))
        done = 'sent' if action == 'send' else 'saved'
        return request.redirect('/my/trips/%s?done=%s' % (trip.id, done))

    # =========================================================== the trip
    def _trip_render_page(self, trip, done=None, error=None, status=200):
        Trips = request.env['pb.me.trip']
        st = Trips.status(trip)
        card = Trips.card(trip)
        claim_url = None
        if 'pb.expense.claim' in request.env and trip.state == 'approved':
            claim_url = '/my/expenses/new?trip=%s' % trip.id
        values = {
            'page_name': 'trip',
            'trip': trip,
            'ref': trip.name,
            'card': card,
            'status': st,
            'lines': Trips.lines(trip),
            'categories': Trips.categories() if st['can']['edit'] else [],
            'done': done if done in _DONE else None,
            'error': error,
            'ask_hr_url': self._trip_ask_hr_url(),
            'claim_url': claim_url,
            'copy_url': '/my/trips/new?copy=%s' % trip.id
            if trip.state in ('cancelled', 'refused') or st['key'] == 'withdrawn' else None,
        }
        return request.render('pb_me_trip.portal_trip_page', values, status=status)

    @http.route(['/my/trips/<int:trip_id>'], type='http', auth='user',
                website=True, methods=['GET'])
    def portal_trip_page(self, trip_id, **kw):
        trip = self._trip_own(trip_id)
        if not trip:
            return self._trip_not_found()
        return self._trip_render_page(trip, done=kw.get('done'))

    def _trip_post(self, trip_id, fn, done, then=None):
        """One guarded action on a trip: 404 when not the person's own, the
        trip page with the reason when refused, a redirect on success."""
        trip = self._trip_own(trip_id)
        if not trip:
            return self._trip_not_found()
        try:
            with request.env.cr.savepoint():
                fn(trip)
        except _REFUSED as exc:
            _logger.info('pb_me_trip: %s on trip %s was refused: %s', done, trip.id, exc)
            trip.invalidate_recordset()
            return self._trip_render_page(trip, error=_reason(exc))
        return request.redirect((then or '/my/trips/%s') % trip.id + '?done=%s' % done)

    @http.route(['/my/trips/<int:trip_id>/send'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_trip_send(self, trip_id, **post):
        return self._trip_post(trip_id, request.env['pb.me.trip'].send, 'sent')

    @http.route(['/my/trips/<int:trip_id>/withdraw'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_trip_withdraw(self, trip_id, **post):
        return self._trip_post(trip_id, request.env['pb.me.trip'].withdraw, 'withdrawn')

    @http.route(['/my/trips/<int:trip_id>/reopen'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_trip_reopen(self, trip_id, **post):
        return self._trip_post(trip_id, request.env['pb.me.trip'].reopen, 'reopened',
                               then='/my/trips/%s/edit')

    @http.route(['/my/trips/<int:trip_id>/line/add'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_trip_line_add(self, trip_id, **post):
        line = {'category_id': post.get('category_id') or '',
                'amount': (post.get('amount') or '').strip(),
                'description': (post.get('description') or '').strip()}
        return self._trip_post(
            trip_id, lambda trip: request.env['pb.me.trip'].add_line(trip, line),
            'line_added')

    @http.route(['/my/trips/<int:trip_id>/line/<int:line_id>/remove'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_trip_line_remove(self, trip_id, line_id, **post):
        return self._trip_post(
            trip_id, lambda trip: request.env['pb.me.trip'].remove_line(trip, line_id),
            'line_removed')

