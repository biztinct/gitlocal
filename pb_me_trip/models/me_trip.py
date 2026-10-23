# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.me.trip` — business trips as the employee pages see them (ETP E2).

THE GUARD IS HERE AS WELL AS IN THE ROUTE. Every public method takes the
session's employee (or a trip reached by id) and refuses anything whose
employee is not the CALLER's own (`employee.user_id == env.uid`, the M-R4
check `pb.me.home` uses). Reads and writes then run on `sudo()` records, which
keep `env.uid`, so `create_uid`, the chatter author and the approval engine's
submitter stay the employee (ledger E-R2).

SUDO SWITCHES THE STOCK GUARDS OFF, SO THEY ARE RE-STATED (E-R3, ledger E6):
  * a field WHITELIST — only the questions the page asks are read from the
    request; `employee_id`, `company_id`, `currency_id`, `policy_id` and
    `per_diem_rate` are set here; `state`, `manager_id` and `name` never;
  * edits (fields and lines) only while the trip is a draft;
  * send only from draft; take back only from the three "waiting" states
    (never an authorised trip: that is HR's, ledger E8); fix-and-resend only
    from refused (or a request withdrawn in the approvals inbox, which leaves
    the trip "submitted" — the one other state stock resets from).

THE MONEY IS THE RECORD'S. `preview()` mirrors `_compute_duration` /
`_compute_money` for the live card before anything is saved; after a save the
page shows the record's own stored computes (D6), and a test holds the two
equal. The rate is always the matched policy's (D2) — the person never types
it.
"""

import json
import logging
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang
from odoo.tools.translate import LazyTranslate, code_translations

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)

#: The three states a trip waits for a decision in (take back is legal here).
OPEN_STATES = ('submitted', 'manager_approved', 'finance_approved')
#: How far ahead an authorised trip counts as "your next trip" on the home.
NEXT_TRIP_DAYS = 14
#: At most this many cost lines on one trip (a sanity rail, not a policy).
MAX_LINES = 30
#: Lengths the page accepts (the inputs carry the same `maxlength`).
CITY_MAX = 80
NOTE_MAX = 120
PURPOSE_MAX = 2000
#: An amount above this is a typo, never a trip.
AMOUNT_MAX = 1e12

#: The pill words per state (D7). A dict of single `_lt` calls on purpose
#: (inside tuples the term extractor collects the neighbours too, ledger T3a).
STATE_LABELS = {
    'draft': _lt('Draft'),
    'submitted': _lt('Waiting approval'),
    'manager_approved': _lt('With finance'),
    'finance_approved': _lt('With HR'),
    'approved': _lt('Authorised'),
    'refused': _lt('Refused — your turn'),
    'cancelled': _lt('Taken back'),
    # not stock states: what the request says on top of the trip's state
    'returned': _lt('Sent back — your turn'),
    'blocked': _lt('Nobody to approve yet'),
    'withdrawn': _lt('Taken back from Approvals'),
}
STATE_TONES = {
    'draft': 'off', 'submitted': 'wait', 'manager_approved': 'wait',
    'finance_approved': 'wait', 'approved': 'ok', 'refused': 'act',
    'cancelled': 'off', 'returned': 'act', 'blocked': 'act',
    'withdrawn': 'off',
}
#: The list page's filter chip a status counts under. A draft has not been
#: sent yet, so it waits on the person (unlike My requests, where D7 keeps
#: drafts quiet).
STATE_BUCKETS = {
    'draft': 'act', 'returned': 'act', 'refused': 'act', 'blocked': 'act',
    'submitted': 'wait', 'manager_approved': 'wait', 'finance_approved': 'wait',
    'approved': 'done', 'cancelled': 'done', 'withdrawn': 'done',
}
BUCKETS = ('act', 'wait', 'done')

#: The fixed ladder's step names when no route is published. They are the
#: words the default route ships with (`pb_business_trip_approval.py`), so the
#: page reads the same either way; translated from the engine's own file.
_LADDER_WORDS = ('Their manager', 'Finance approver', 'HR lead')

#: An icon per stock cost category (`pb_trip_expense_category_data.xml`).
CATEGORY_ICONS = {
    'pb_business_trip.cat_lodging': 'bed',
    'pb_business_trip.cat_transport': 'car',
    'pb_business_trip.cat_meals': 'utensils',
    'pb_business_trip.cat_other': 'ellipsis',
}

_AMOUNT_RE = re.compile(r'^\s*-?[\d\s,]*\.?\d*\s*$')


def num_str(value):
    """A number as an input box shows it: ``2000000``, ``12.5``, '' for 0
    (never ``2e+06``)."""
    if not value:
        return ''
    return ('%.2f' % float(value)).rstrip('0').rstrip('.')


class PbMeTrip(models.AbstractModel):
    _name = 'pb.me.trip'
    _description = 'Business trips on the employee pages'

    # ================================================================ guards
    @api.model
    def _own_emp(self, emp):
        """``emp`` as a sudo record when it is the caller's own employee."""
        _ = self.env._
        if not isinstance(emp, models.BaseModel) or emp._name != 'hr.employee':
            raise AccessError(_("That is not your record."))
        emp = emp.sudo()[:1]
        if not emp or emp.user_id.id != self.env.uid:
            raise AccessError(_("That is not your record."))
        return emp

    @api.model
    def _own(self, trip):
        """``trip`` as a sudo record when its employee is the caller's own,
        else an empty recordset (never an error: a 404 is the caller's)."""
        Trip = self.env['pb.business.trip'].sudo()
        if not isinstance(trip, models.BaseModel) or trip._name != Trip._name:
            return Trip.browse()
        trip = Trip.browse(trip.ids[:1]).exists()
        if trip and trip.employee_id.user_id.id == self.env.uid:
            return trip
        return Trip.browse()

    @api.model
    def _require_own(self, trip):
        _ = self.env._
        trip = self._own(trip)
        if not trip:
            raise AccessError(_("That is not your trip."))
        return trip

    @api.model
    def get_trip(self, emp, trip_id):
        """The trip ``trip_id`` as a sudo record when it belongs to ``emp``
        (the caller's own), else an empty recordset."""
        Trip = self.env['pb.business.trip'].sudo()
        try:
            emp = self._own_emp(emp)
            trip = Trip.browse(int(trip_id)).exists()
        except (AccessError, TypeError, ValueError):
            return Trip.browse()
        if trip and trip.employee_id.user_id == emp.user_id:
            return trip
        return Trip.browse()

    # ================================================================ words
    @api.model
    def _today(self, emp):
        Home = self.env['pb.me.home']
        try:
            return Home._pbme_local_now(emp, fields.Datetime.now()).date()
        except Exception:               # noqa: BLE001 — a time zone typo
            return fields.Date.context_today(self)

    @api.model
    def fmt_money(self, amount, currency):
        """``amount`` in ``currency`` as the reader's language writes it
        (the same `formatLang` the live card's script mirrors)."""
        return formatLang(self.env, float(amount or 0.0), currency_obj=currency)

    @api.model
    def dates_label(self, date_from, date_to):
        """"12–14 Nov", "30 Nov – 2 Dec", "28 Dec 2026 – 3 Jan 2027"."""
        if not date_from:
            return ''
        date_to = date_to or date_from
        if date_to < date_from:
            date_from, date_to = date_to, date_from
        if date_from == date_to:
            return format_date(self.env, date_from, date_format='d MMM')
        if date_from.year != date_to.year:
            return '%s – %s' % (format_date(self.env, date_from, date_format='d MMM yyyy'),
                                format_date(self.env, date_to, date_format='d MMM yyyy'))
        if date_from.month == date_to.month:
            return '%s–%s' % (date_from.day,
                              format_date(self.env, date_to, date_format='d MMM'))
        return '%s – %s' % (format_date(self.env, date_from, date_format='d MMM'),
                            format_date(self.env, date_to, date_format='d MMM'))

    @api.model
    def where_label(self, city, country):
        """"Đà Nẵng, Vietnam" (either half alone when the other is empty)."""
        parts = [p for p in ((city or '').strip(), country.name if country else '') if p]
        return ', '.join(parts)

    @api.model
    def _engine_word(self, text):
        """A route step's stored title ("Their manager") in the reader's
        language, from the approval engine's own translation file — the words
        are the engine's, so they are not repeated in this module's file."""
        lang = self.env.lang or 'en_US'
        if not text or lang == 'en_US':
            return text or ''
        for module in ('biz_approval_workflow', 'pb_business_trip'):
            try:
                found = code_translations.get_python_translations(module, lang).get(text)
            except Exception:           # noqa: BLE001 — a word is never fatal
                found = None
            if found:
                return found
        return text

    # =============================================================== policy
    @api.model
    def _tier1_exists(self, country, company):
        if not country:
            return False
        return bool(self.env['pb.trip.policy'].sudo().search_count([
            ('active', '=', True), ('country_id', '=', country.id),
            ('city_tier', '=', 'tier1'),
            ('company_id', 'in', [company.id, False] if company else [False]),
        ]))

    @api.model
    def _policy_dict(self, policy, company):
        currency = policy.currency_id if policy and policy.currency_id else company.currency_id
        return {
            'policy': policy,
            'rate': float(policy.per_diem_rate or 0.0) if policy else 0.0,
            'currency': currency,
            'channel': (policy.per_diem_channel if policy and policy.per_diem_rate
                        else 'none'),
        }

    @api.model
    def policy_for(self, emp, country_id, tier=False):
        """The per-diem policy a trip of ``emp`` to ``country_id`` gets (D2):
        `pb.trip.policy._match(country, company, tier)` under sudo. ``tier``
        counts only when a tier-1 policy exists for that country (company or
        global, ledger E7). ``{'policy', 'rate', 'currency', 'channel'
        ('payroll' | 'expense' | 'none'), 'has_tier1', 'tier'}``."""
        emp = self._own_emp(emp)
        company = emp.company_id
        country = self.env['res.country'].sudo().browse(int(country_id or 0)).exists()
        has_tier1 = self._tier1_exists(country, company)
        use_tier = 'tier1' if (tier and has_tier1) else False
        policy = self.env['pb.trip.policy'].sudo()._match(country, company, use_tier)
        out = self._policy_dict(policy, company)
        out.update(has_tier1=has_tier1, tier=use_tier)
        return out

    @api.model
    def policy_map(self, emp):
        """Every answer `policy_for` can give ``emp``, for the live card's
        script (E-R8: server facts travel in a data attribute). ``{'countries':
        {id: {'base': p, 'tier1': p|None}}, 'fallback': p, 'currencies': {id:
        {'symbol', 'position', 'dp'}}}`` with ``p = {'rate', 'currency',
        'channel'}``."""
        emp = self._own_emp(emp)
        company = emp.company_id
        Policy = self.env['pb.trip.policy'].sudo()
        policies = Policy.search([('active', '=', True),
                                  ('company_id', 'in', [company.id, False])])
        currencies = {}

        def pack(policy):
            d = self._policy_dict(policy, company)
            cur = d['currency']
            currencies[cur.id] = {'symbol': cur.symbol or cur.name or '',
                                  'position': cur.position or 'after',
                                  'dp': cur.decimal_places}
            return {'rate': d['rate'], 'currency': cur.id, 'channel': d['channel']}

        countries = {}
        for country in policies.mapped('country_id'):
            countries[str(country.id)] = {
                'base': pack(Policy._match(country, company, False)),
                'tier1': (pack(Policy._match(country, company, 'tier1'))
                          if self._tier1_exists(country, company) else None),
            }
        return {
            'countries': countries,
            'fallback': pack(Policy._match(self.env['res.country'], company, False)),
            'currencies': currencies,
        }

    @api.model
    def policy_country_ids(self, emp):
        """Countries a policy names (company or global) — listed first in the
        country picker."""
        emp = self._own_emp(emp)
        return self.env['pb.trip.policy'].sudo().search([
            ('active', '=', True), ('country_id', '!=', False),
            ('company_id', 'in', [emp.company_id.id, False])]).mapped('country_id').ids

    # ============================================================== preview
    @api.model
    def preview(self, values):
        """The live card's arithmetic, pure (no write): the same sums as
        `_compute_duration` / `_compute_money`. ``values``: ``date_from``,
        ``date_to`` (dates or ISO strings), ``per_diem_rate``,
        ``line_amounts`` (list of numbers), ``advance_amount``. Returns
        ``{'days', 'rate', 'allowance', 'lines_total', 'estimated',
        'advance'}``."""
        def to_date(value):
            try:
                return fields.Date.to_date(value) if value else None
            except (TypeError, ValueError):
                return None
        date_from = to_date(values.get('date_from'))
        date_to = to_date(values.get('date_to'))
        days = ((date_to - date_from).days + 1
                if date_from and date_to and date_to >= date_from else 0)
        rate = float(values.get('per_diem_rate') or 0.0)
        allowance = rate * days
        lines_total = sum(float(a or 0.0) for a in values.get('line_amounts') or [])
        return {
            'days': days,
            'rate': rate,
            'allowance': allowance,
            'lines_total': lines_total,
            'estimated': allowance + lines_total,
            'advance': float(values.get('advance_amount') or 0.0),
        }

    # ========================================================= the whitelist
    @api.model
    def _amount(self, raw, blank_ok=True):
        """A typed amount as a float; ``None`` when blank (or not a number)."""
        _ = self.env._
        if raw in (None, False, ''):
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        if not text:
            return None
        if not _AMOUNT_RE.match(text):
            raise UserError(_("Amounts are numbers only, for example 250000."))
        try:
            return float(text.replace(',', '').replace(' ', ''))
        except ValueError:
            raise UserError(_("Amounts are numbers only, for example 250000.")) from None

    @api.model
    def _clean(self, emp, values):
        """The questions the page asks, checked. Only these keys are read
        from ``values`` (E-R3): ``destination_city``,
        ``destination_country_id``, ``date_from``, ``date_to``, ``purpose``,
        ``advance_amount``, ``notes`` and the "Major city" answer ``tier``.
        Returns ``(trip_vals, policy)``; raises a plain-words UserError on the
        first problem."""
        _ = self.env._
        Country = self.env['res.country'].sudo()
        try:
            country = Country.browse(int(values.get('destination_country_id') or 0)).exists()
        except (TypeError, ValueError):
            country = Country.browse()
        if not country:
            raise UserError(_("Choose the country you are going to."))
        city = (values.get('destination_city') or '').strip()[:CITY_MAX]
        if not city:
            raise UserError(_("Add the city you are going to."))
        try:
            date_from = fields.Date.to_date(values.get('date_from') or None)
            date_to = fields.Date.to_date(values.get('date_to') or None)
        except (TypeError, ValueError):
            date_from = date_to = None
        if not (date_from and date_to):
            raise UserError(_("Pick the first and the last day of the trip."))
        if date_to < date_from:
            raise UserError(_("The trip cannot end before it starts. Check the two dates."))
        purpose = (values.get('purpose') or '').strip()[:PURPOSE_MAX]
        if not purpose:
            raise UserError(_("Say why you are travelling, in a sentence or two."))
        advance = self._amount(values.get('advance_amount')) or 0.0
        if advance < 0:
            raise UserError(_("The cash advance cannot be below zero."))
        if advance > AMOUNT_MAX:
            raise UserError(_("That cash advance is too large. Check the number."))
        notes = (values.get('notes') or '').strip()[:PURPOSE_MAX] or False
        policy = self.policy_for(emp, country.id, values.get('tier'))
        vals = {
            'destination_city': city,
            'destination_country_id': country.id,
            'date_from': date_from,
            'date_to': date_to,
            'purpose': purpose,
            'advance_amount': advance,
            'notes': notes,
        }
        return vals, policy

    @api.model
    def _categories(self):
        return self.env['pb.trip.expense.category'].sudo().search([('active', '=', True)])

    @api.model
    def categories(self):
        """The cost category chips: ``[{'id', 'name', 'icon'}]``."""
        cats = self._categories()
        xmlids = cats.get_external_id()
        return [{'id': c.id, 'name': c.name,
                 'icon': CATEGORY_ICONS.get(xmlids.get(c.id) or '', 'tag')}
                for c in cats]

    @api.model
    def _clean_lines(self, lines):
        """Cost lines, checked: ``[{'category_id', 'description', 'amount'}]``
        (only these keys are read, D1). A row with nothing in it is dropped;
        a row with words or a category but no amount is refused."""
        _ = self.env._
        allowed = set(self._categories().ids)
        out = []
        for row in lines or []:
            if not isinstance(row, dict):
                continue
            desc = (row.get('description') or '').strip()[:NOTE_MAX]
            try:
                cat = int(row.get('category_id') or 0)
            except (TypeError, ValueError):
                cat = 0
            amount = self._amount(row.get('amount'))
            if not desc and not cat and not amount:
                continue
            if amount is None or amount == 0:
                raise UserError(_("Each cost line needs an amount. Add one, or remove the line."))
            if amount < 0:
                raise UserError(_("A cost cannot be below zero."))
            if amount > AMOUNT_MAX:
                raise UserError(_("One of the costs is too large. Check the number."))
            out.append({'category_id': cat if cat in allowed else False,
                        'description': desc or False, 'amount': amount})
        if len(out) > MAX_LINES:
            raise UserError(_("A trip can have up to %s cost lines.", MAX_LINES))
        return out

    @api.model
    def _money_vals(self, emp, policy):
        company = emp.company_id
        return {
            'company_id': company.id,
            'currency_id': (policy['currency'] or company.currency_id).id,
            'policy_id': policy['policy'].id or False,
            'per_diem_rate': policy['rate'],
        }

    # ================================================================ write
    @api.model
    def new_trip(self, emp, values, lines=None):
        """Create a DRAFT trip for ``emp`` (the caller's own) from the
        page's answers. ``state`` or any other key in ``values`` is ignored;
        the employee, company, currency, policy and rate are set here."""
        emp = self._own_emp(emp)
        vals, policy = self._clean(emp, values)
        line_vals = self._clean_lines(lines)
        vals.update(self._money_vals(emp, policy))
        vals['employee_id'] = emp.id
        vals['line_ids'] = [(0, 0, dict(line, date=vals['date_from'])) for line in line_vals]
        return self.env['pb.business.trip'].sudo().create(vals)

    @api.model
    def update_trip(self, trip, values, lines=None):
        """Change a DRAFT trip. ``lines=None`` leaves the cost lines alone; a
        list replaces them."""
        _ = self.env._
        trip = self._require_own(trip)
        if trip.state != 'draft':
            raise UserError(_(
                "This trip has been sent, so it cannot be changed here. "
                "Take it back first, then change it."))
        emp = trip.employee_id
        vals, policy = self._clean(emp, values)
        line_vals = self._clean_lines(lines) if lines is not None else None
        vals.update(self._money_vals(emp, policy))
        trip.write(vals)
        if line_vals is not None:
            trip.line_ids.unlink()
            if line_vals:
                self.env['pb.business.trip.line'].sudo().create([
                    dict(line, trip_id=trip.id, date=trip.date_from) for line in line_vals])
        return trip

    @api.model
    def add_line(self, trip, line):
        """Add one cost line to a DRAFT trip."""
        _ = self.env._
        trip = self._require_own(trip)
        if trip.state != 'draft':
            raise UserError(_(
                "This trip has been sent, so its costs cannot be changed here."))
        line_vals = self._clean_lines([line])
        if not line_vals:
            raise UserError(_("Each cost line needs an amount. Add one, or remove the line."))
        if len(trip.line_ids) >= MAX_LINES:
            raise UserError(_("A trip can have up to %s cost lines.", MAX_LINES))
        return self.env['pb.business.trip.line'].sudo().create(
            dict(line_vals[0], trip_id=trip.id, date=trip.date_from))

    @api.model
    def remove_line(self, trip, line_id):
        """Remove one cost line of a DRAFT trip (``False`` when it is not
        one of this trip's lines)."""
        _ = self.env._
        trip = self._require_own(trip)
        if trip.state != 'draft':
            raise UserError(_(
                "This trip has been sent, so its costs cannot be changed here."))
        line = trip.line_ids.filtered(lambda l: l.id == int(line_id or 0))
        if not line:
            return False
        line.unlink()
        return True

    @api.model
    def _overlap(self, trip):
        """Another trip of the same person on any of these days that is
        waiting or authorised (stock's `_guard_trip_overlap`, said in the
        person's words before stock's own guard runs)."""
        return self.env['pb.business.trip'].sudo().search([
            ('id', '!=', trip.id),
            ('employee_id', '=', trip.employee_id.id),
            ('state', 'in', OPEN_STATES + ('approved',)),
            ('date_from', '<=', trip.date_to),
            ('date_to', '>=', trip.date_from),
        ], order='date_from', limit=1)

    @api.model
    def send(self, trip):
        """Send a DRAFT trip for approval: the trip's own `action_submit`
        under sudo (D3) — the route takes over when the company has one, the
        fixed ladder runs otherwise."""
        _ = self.env._
        trip = self._require_own(trip)
        if trip.state != 'draft':
            raise UserError(_("This trip has already been sent."))
        clash = self._overlap(trip)
        if clash:
            where = self.where_label(clash.destination_city, clash.destination_country_id) \
                or clash.name
            when = self.dates_label(clash.date_from, clash.date_to)
            if clash.state == 'approved':
                raise UserError(_(
                    "You already have an authorised trip on some of these days: "
                    "%(where)s, %(when)s. Pick other dates, or ask HR to cancel that trip.",
                    where=where, when=when))
            raise UserError(_(
                "You already have a trip waiting for approval on some of these days: "
                "%(where)s, %(when)s. Pick other dates, or take that trip back first.",
                where=where, when=when))
        trip.action_submit()
        return trip

    @api.model
    def withdraw(self, trip):
        """Take a trip back before it is authorised (D4): the trip's own
        `action_cancel`, which also withdraws the open approval request."""
        _ = self.env._
        trip = self._require_own(trip)
        if trip.state == 'approved':
            raise UserError(_(
                "An authorised trip cannot be taken back here. Ask HR to cancel it."))
        if trip.state not in OPEN_STATES:
            raise UserError(_(
                "This trip is not waiting for approval, so there is nothing to take back."))
        trip.action_cancel()
        return trip

    @api.model
    def _withdrawn_in_inbox(self, trip):
        """The request was withdrawn in the approvals inbox but the trip
        still says it waits (ledger E8: the shim has no `_approval_withdraw`)."""
        req = self._request(trip)
        return bool(trip.state in OPEN_STATES and req and req.state == 'cancelled')

    @api.model
    def _can_reopen(self, trip):
        return trip.state == 'refused' or (
            trip.state == 'submitted' and self._withdrawn_in_inbox(trip))

    @api.model
    def reopen(self, trip):
        """Fix and resend, step one: a refused trip back to draft
        (`action_reset_to_draft`)."""
        _ = self.env._
        trip = self._require_own(trip)
        if not self._can_reopen(trip):
            raise UserError(_(
                "Only a refused trip can be fixed and sent again."))
        trip.action_reset_to_draft()
        return trip

    # =============================================================== status
    @api.model
    def _request(self, trip):
        """The latest approval request of ``trip`` (sudo), or empty. The
        field is computed on every read (no stored link), so it can never
        disagree with the engine."""
        trip.invalidate_recordset(['approval_request_id', 'approval_state'])
        return trip.approval_request_id.sudo()

    @api.model
    def _request_matches(self, trip, req):
        """Is the latest request the story of the trip's CURRENT state? (A
        trip resent on the fixed ladder after a route was switched off still
        has the old, finished request as its latest.)"""
        if not req:
            return False
        state, rstate = trip.state, req.state
        if state in OPEN_STATES:
            return rstate in ('pending', 'blocked', 'cancelled')
        return {
            'approved': rstate in ('approved', 'applied'),
            'refused': rstate == 'rejected',
            'draft': rstate == 'returned',
        }.get(state, False)

    @api.model
    def _key(self, trip, req):
        state = trip.state
        if req and self._request_matches(trip, req):
            if state == 'draft' and req.state == 'returned':
                return 'returned'
            if state in OPEN_STATES and req.state == 'blocked':
                return 'blocked'
            if state in OPEN_STATES and req.state == 'cancelled':
                return 'withdrawn'
        return state

    @api.model
    def _decision(self, req, action):
        return req.decision_ids.filtered(lambda d: d.action == action).sorted(
            lambda d: (d.stamp or fields.Datetime.now(), d.id))[-1:]

    @api.model
    def _route_steps(self, trip, req):
        """The route this trip was really given: Sent in → each included
        step with the live names of the people asked → Approved."""
        _ = self.env._
        rejected = self._decision(req, 'reject') if req.state == 'rejected' else None
        returned = self._decision(req, 'return') if req.state == 'returned' else None
        stopped_key = (rejected or returned).step_key if (rejected or returned) else None
        steps = [{'key': '_sent', 'name': _('Sent in'),
                  'who': req.submitter_uid.name or '', 'state': 'done',
                  'when': req.submitted_at}]
        status_map = {'done': 'done', 'active': 'current', 'pending': 'todo',
                      'blocked': 'blocked', 'returned': 'stopped'}
        for step in req.step_ids.sorted('sequence'):
            if not step.included or step.kind in ('notify', 'fast') \
                    or step.status == 'skipped':
                continue
            seats = step.seat_ids.filtered(lambda s: s.status != 'reassigned')
            names = sorted({s.acting_user_id.name for s in seats if s.acting_user_id})
            st = status_map.get(step.status, 'todo')
            if stopped_key and step.key == stopped_key:
                st = 'stopped'
            if req.state == 'cancelled' and st == 'current':
                st = 'todo'
            steps.append({'key': step.key, 'name': self._engine_word(step.title),
                          'who': ', '.join(names), 'state': st,
                          'when': step.decided_at if st in ('done', 'stopped') else False})
        done = req.state in ('approved', 'applied') or trip.state == 'approved'
        steps.append({'key': '_done', 'name': _('Approved'), 'who': '',
                      'state': 'done' if done else 'todo',
                      'when': req.closed_at if done else False})
        return steps

    @api.model
    def _ladder_steps(self, trip):
        """The fixed ladder (no route published): Sent in → Their manager →
        Finance approver → HR lead → Approved, read from the trip's state and
        its own trail."""
        _ = self.env._
        order = ('submitted', 'manager_approved', 'finance_approved', 'approved')
        state = trip.state
        stopped_from = None
        if state == 'refused':
            log = self.env['biz.approval.step.log'].sudo().search([
                ('res_model', '=', trip._name), ('res_id', '=', trip.id),
                ('to_state', '=', 'refused')], order='stamp desc, id desc', limit=1)
            stopped_from = log.from_state or 'submitted'
        reached = order.index(state) if state in order else (
            order.index(stopped_from) if stopped_from in order else -1)
        manager = trip.employee_id.parent_id
        words = [self._engine_word(w) for w in _LADDER_WORDS]
        steps = [{'key': '_sent', 'name': _('Sent in'), 'who': trip.create_uid.name or '',
                  'state': 'done' if reached >= 0 else 'todo', 'when': False}]
        for index, (name, who) in enumerate(zip(words, (manager.name or '', '', ''))):
            if index < reached:
                st = 'done'
            elif index == reached:
                st = 'stopped' if stopped_from else ('done' if state == 'approved' else 'current')
            else:
                st = 'todo'
            steps.append({'key': 'ladder%s' % index, 'name': name, 'who': who,
                          'state': st, 'when': False})
        steps.append({'key': '_done', 'name': _('Approved'), 'who': '',
                      'state': 'done' if state == 'approved' else 'todo', 'when': False})
        return steps

    @api.model
    def route_preview(self, emp):
        """Who will be asked, before anything is sent: the steps of the
        route the company publishes for trips (resolved for this person's
        part of the business), or the fixed ladder when there is none."""
        _ = self.env._
        emp = self._own_emp(emp)
        manager = emp.parent_id.name or ''
        steps = [{'key': '_sent', 'name': _('Sent in'), 'who': '', 'state': 'todo', 'when': False}]
        titles = None
        try:
            titles = self._route_titles(emp)
        except Exception:               # noqa: BLE001 — a preview is never fatal
            _logger.info('pb_me_trip: no route preview for %s', emp.id, exc_info=True)
        if titles is None:
            titles = [(w, 'manager' if i == 0 else 'role')
                      for i, w in enumerate(_LADDER_WORDS)]
        for index, (title, mode) in enumerate(titles):
            steps.append({'key': 'p%s' % index, 'name': self._engine_word(title),
                          'who': manager if mode == 'manager' else '',
                          'state': 'todo', 'when': False})
        steps.append({'key': '_done', 'name': _('Approved'), 'who': '', 'state': 'todo',
                      'when': False})
        return steps

    @api.model
    def _route_titles(self, emp):
        """``[(title, who-mode)]`` of the published trip route for ``emp``,
        or ``None`` when no route is bound (the fixed ladder runs)."""
        if 'biz.approval.engine' not in self.env:
            return None
        from odoo.addons.biz_approval_workflow.models import definition as D
        from odoo.addons.biz_approval_workflow.models.chain_shim import SCOPE_RESOLVERS
        spec_key = self.env['pb.business.trip']._approval_engine_process_key()
        process = self.env['biz.approval.process']._by_key(spec_key)
        if not process:
            return None
        today = self._today(emp)
        keys = []
        for resolver in SCOPE_RESOLVERS:
            try:
                keys += [r['key'] for r in (resolver(self.env, emp, today) or []) if r.get('key')]
            except Exception:           # noqa: BLE001 — same as the shim
                continue
        binding, version, _trace, error = self.env['biz.approval.engine'].sudo()._resolve_binding(
            emp.company_id, process, keys + [''], 'any')
        if error or not binding or not version:
            return None
        return [(step.get('title') or '', (step.get('who') or {}).get('mode') or 'role')
                for step in D.normalise(version.definition)['steps']
                if step.get('kind') not in ('notify', 'fast')]

    @api.model
    def _leave_overlap(self, trip):
        """The name of an approved leave over the trip's days, or ``None``
        (stock only posts a chatter note and sends anyway, ledger E8)."""
        _ = self.env._
        if 'hr.leave' not in self.env or not (trip.date_from and trip.date_to):
            return None
        end_dt = fields.Datetime.to_datetime(trip.date_to) + timedelta(days=1)
        leave = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', trip.employee_id.id),
            ('state', 'in', ('validate', 'validate1')),
            ('date_from', '<', end_dt),
            ('date_to', '>=', fields.Datetime.to_datetime(trip.date_from)),
        ], limit=1)
        if not leave:
            return None
        return leave.holiday_status_id.name or _('Leave')

    @api.model
    def status(self, trip):
        """Where the trip stands, for the trip page and the list:
        ``{state, key, label, tone, bucket, current (the step waiting now),
        steps: [{name, who, state, when}], reason, reason_by, block_reason, can: {edit, send, withdraw,
        reopen, ask_hr_cancel}, attendance_sentence, leave_overlap,
        request_state}``. ``None`` when the trip is not the caller's own."""
        _ = self.env._
        trip = self._own(trip)
        if not trip:
            return None
        req = self._request(trip)
        matches = self._request_matches(trip, req)
        key = self._key(trip, req)
        if trip.state == 'cancelled':
            steps = []
        elif trip.state == 'draft' and key != 'returned':
            steps = self.route_preview(trip.employee_id)
        elif matches:
            steps = self._route_steps(trip, req)
        else:
            steps = self._ladder_steps(trip)
        reason = reason_by = ''
        if key in ('refused', 'returned'):
            if matches and req.state in ('rejected', 'returned'):
                reason = req.return_note or ''
                decision = self._decision(req, 'reject' if req.state == 'rejected' else 'return')
                reason_by = decision.user_id.name or ''
            else:
                log = self.env['biz.approval.step.log'].sudo().search([
                    ('res_model', '=', trip._name), ('res_id', '=', trip.id),
                    ('to_state', '=', 'refused')], order='stamp desc, id desc', limit=1)
                reason = log.note or ''
                reason_by = log.user_id.name or ''
        state = trip.state
        current = next((s for s in steps if s['state'] in ('current', 'blocked')), None)
        return {
            'state': state,
            'key': key,
            'current': current if state in OPEN_STATES else None,
            'label': _(STATE_LABELS[key]) if key in STATE_LABELS else (state or ''),
            'tone': STATE_TONES.get(key, 'off'),
            'bucket': STATE_BUCKETS.get(key, 'done'),
            'steps': steps,
            'reason': reason,
            'reason_by': reason_by,
            'block_reason': (req.block_reason or '') if key == 'blocked' else '',
            'request_state': req.state if req else False,
            'can': {
                'edit': state == 'draft',
                'send': state == 'draft',
                'withdraw': state in OPEN_STATES,
                'reopen': self._can_reopen(trip),
                'ask_hr_cancel': state == 'approved',
            },
            'attendance_sentence': (
                _("Your attendance is marked automatically for every trip day.")
                if state == 'approved' else ''),
            'leave_overlap': (self._leave_overlap(trip)
                              if state not in ('cancelled', 'refused') else None),
        }

    # ================================================================= card
    @api.model
    def card(self, trip):
        """The trip card's facts, from the RECORD's own computes (D6)."""
        trip = self._own(trip)
        if not trip:
            return None
        currency = trip.currency_id or trip.company_id.currency_id
        policy = trip.policy_id
        channel = (policy.per_diem_channel if policy and trip.per_diem_rate else 'none')
        lines_total = sum(trip.line_ids.mapped('amount'))
        fmt = lambda v: self.fmt_money(v, currency)  # noqa: E731
        return {
            'id': trip.id,
            'ref': trip.name,
            'city': trip.destination_city or '',
            'country': trip.destination_country_id.name or '',
            'where': self.where_label(trip.destination_city, trip.destination_country_id)
                     or trip.name,
            'date_from': trip.date_from,
            'date_to': trip.date_to,
            'dates': self.dates_label(trip.date_from, trip.date_to),
            'days': trip.duration_days,
            'channel': channel,
            'currency': currency,
            'rate': trip.per_diem_rate,
            'allowance': trip.per_diem_total,
            'advance': trip.advance_amount,
            'lines_total': lines_total,
            'estimated': trip.estimated_total,
            'money': {
                'rate': fmt(trip.per_diem_rate),
                'allowance': fmt(trip.per_diem_total),
                'advance': fmt(trip.advance_amount),
                'lines': fmt(lines_total),
                'estimated': fmt(trip.estimated_total),
            },
            'purpose': trip.purpose or '',
        }

    @api.model
    def lines(self, trip):
        trip = self._own(trip)
        if not trip:
            return []
        currency = trip.currency_id or trip.company_id.currency_id
        xmlids = trip.line_ids.mapped('category_id').get_external_id()
        return [{
            'id': line.id,
            'category': line.category_id.name or '',
            'icon': CATEGORY_ICONS.get(xmlids.get(line.category_id.id) or '', 'tag'),
            'description': line.description or '',
            'amount': line.amount,
            'amount_label': self.fmt_money(line.amount, currency),
        } for line in trip.line_ids]

    # ================================================================= list
    @api.model
    def _trips(self, emp):
        return self.env['pb.business.trip'].sudo().search(
            [('employee_id', '=', emp.id)], order='date_from desc, id desc')

    @api.model
    def own_trips(self, emp, bucket=None):
        """The person's trips for `/my/trips`: ``{'rows': [...], 'counts':
        {'act', 'wait', 'done', 'all'}, 'next': next_trip(emp)}``; ``rows``
        keeps only ``bucket`` when one of ``act`` / ``wait`` / ``done`` is
        given (the counts stay whole)."""
        emp = self._own_emp(emp)
        rows = []
        for trip in self._trips(emp):
            st = self.status(trip)
            card = self.card(trip)
            rows.append({
                'id': trip.id,
                'url': '/my/trips/%s' % trip.id,
                'ref': trip.name,
                'where': card['where'],
                'dates': card['dates'],
                'days': card['days'],
                'estimated': card['money']['estimated'],
                'has_money': bool(trip.estimated_total),
                'label': st['label'],
                'tone': st['tone'],
                'key': st['key'],
                'bucket': st['bucket'],
            })
        counts = {b: 0 for b in BUCKETS}
        for row in rows:
            counts[row['bucket']] += 1
        counts['all'] = len(rows)
        if bucket in BUCKETS:
            rows = [r for r in rows if r['bucket'] == bucket]
        return {'rows': rows, 'counts': counts, 'next': self.next_trip(emp)}

    @api.model
    def next_trip(self, emp):
        """The nearest authorised trip that is under way or starts within
        NEXT_TRIP_DAYS days: ``{'id', 'url', 'where', 'dates', 'days',
        'in_days', 'ongoing', 'until'}`` or ``None`` (quiet at zero)."""
        emp = self._own_emp(emp)
        today = self._today(emp)
        trip = self.env['pb.business.trip'].sudo().search([
            ('employee_id', '=', emp.id), ('state', '=', 'approved'),
            ('date_to', '>=', today),
            ('date_from', '<=', today + timedelta(days=NEXT_TRIP_DAYS)),
        ], order='date_from asc, id asc', limit=1)
        if not trip:
            return None
        return {
            'id': trip.id,
            'url': '/my/trips/%s' % trip.id,
            'where': self.where_label(trip.destination_city, trip.destination_country_id)
                     or trip.name,
            'dates': self.dates_label(trip.date_from, trip.date_to),
            'days': trip.duration_days,
            'in_days': max(0, (trip.date_from - today).days),
            'ongoing': trip.date_from <= today,
            'until': trip.date_to,
        }

    @api.model
    def waiting_on_me(self, emp):
        """Trips that wait on the person (refused, or sent back to them)."""
        emp = self._own_emp(emp)
        out = {'refused': self.env['pb.business.trip'].sudo().browse(),
               'returned': self.env['pb.business.trip'].sudo().browse()}
        for trip in self._trips(emp).filtered(lambda t: t.state in ('refused', 'draft')):
            key = self._key(trip, self._request(trip))
            if key in out:
                out[key] |= trip
        return out

    @api.model
    def copy_values(self, trip):
        """A trip's answers as the new-trip form's starting values ("Ask
        again with these details" on a trip that was taken back)."""
        trip = self._own(trip)
        if not trip:
            return {}, []
        values = {
            'destination_country_id': trip.destination_country_id.id or '',
            'destination_city': trip.destination_city or '',
            'date_from': fields.Date.to_string(trip.date_from) if trip.date_from else '',
            'date_to': fields.Date.to_string(trip.date_to) if trip.date_to else '',
            'purpose': trip.purpose or '',
            'advance_amount': num_str(trip.advance_amount),
            'tier': bool(trip.policy_id.city_tier == 'tier1'),
        }
        lines = [{'category_id': line.category_id.id or '',
                  'amount': num_str(line.amount),
                  'description': line.description or ''} for line in trip.line_ids]
        return values, lines

    @api.model
    def form_facts(self, emp):
        """What the live card's script needs, as one JSON string."""
        emp = self._own_emp(emp)
        lang = self.env['res.lang']._lang_get(self.env.lang or 'en_US')
        data = self.policy_map(emp)
        data['sep'] = {'thousands': (lang.thousands_sep if lang else ',') or '',
                       'decimal': (lang.decimal_point if lang else '.') or '.'}
        return json.dumps(data)
