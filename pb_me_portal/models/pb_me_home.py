# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""MEHOME — the facts behind an employee's home page (`/my`).

ONE ENTRY POINT. ``get_home_data(emp)`` returns a dict of FACTS (numbers,
dates, keys and names that already exist as data) or ``None`` when there is no
employee. Every sentence on the page lives in the QWeb template (M-R5); nothing
here builds a phrase.

SOFT READS ONLY (M-R3). Every module this page reads from (workforce, pay
calendar, training, goals, pay explainer, pay delivery) DEPENDS ON
pb_me_portal, so none of them can be imported or declared. Every section is
built through ``optional()``: an absent model, an absent field, an access
error or any other failure makes THAT section ``None`` and the template does
not draw its card. A home page must never 500 because one of fifteen
neighbours is missing or broken.

OWN DATA ONLY (M-R4). The employee is resolved by the controller from the
session (``_ess_employee``); this model refuses an employee that is not the
caller's own, so a crafted RPC cannot read somebody else's home.

THE TILE REGISTRY (M-R2). The fifteen modules that put a tile on `/my` are not
edited. ``TILES`` says, per URL, which section a tile belongs to, which Lucide
icon and colour it wears, and (rarely) a shorter title/text. The
``portal.portal_docs_entry`` override reads it through ``tile_meta(url)``; the
frontend Interaction then moves each tile into its section.
"""

import logging
import time
from datetime import datetime, timedelta

# The common Vietnamese family names (with and without diacritics, casefolded):
# a name that opens with one of these is read given-name-last.
VN_FAMILY_NAMES = frozenset(n.casefold() for n in (
    'Nguyễn', 'Nguyen', 'Trần', 'Tran', 'Lê', 'Le', 'Phạm', 'Pham', 'Hoàng', 'Hoang',
    'Huỳnh', 'Huynh', 'Phan', 'Vũ', 'Vu', 'Võ', 'Vo', 'Đặng', 'Dang', 'Bùi', 'Bui',
    'Đỗ', 'Do', 'Hồ', 'Ho', 'Ngô', 'Ngo', 'Dương', 'Duong', 'Lý', 'Ly', 'Đinh', 'Dinh',
    'Trịnh', 'Trinh', 'Lâm', 'Lam', 'Mai', 'Đào', 'Dao', 'Trương', 'Truong', 'Lưu', 'Luu',
    'Tạ', 'Ta', 'Cao', 'Thái', 'Thai', 'Hà', 'Ha', 'Tô', 'To', 'Chu', 'Vương', 'Vuong',
))

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import format_date, formatLang
from odoo.tools.translate import LazyGettext, LazyTranslate

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)

#: The sections of the page, top to bottom. `me` is the strip inside the bento.
GROUPS = ('me', 'time', 'growth', 'people', 'more')

#: How far ahead a document counts as "needs renewing" (pb_employee_vault's own
#: `expiry_state` uses the same 90 days; that field is not stored — M4).
DOC_SOON_DAYS = 90
#: How many paid months the Pay card's trend shows.
TREND_MONTHS = 6
#: How long an approved profile change stays on "Needs you".
APPROVED_RECENT_DAYS = 7

#: The badge colours a "Needs you" row may wear (the kit's badge tones).
NEED_TONES = ('indigo', 'green', 'blue', 'amber', 'rose', 'teal', 'pink', 'slate')

#: My requests (TIERS T3a): a status tone → the filter bucket it counts in.
#: `act` = the person must do something (the one coloured pill), `wait` = with
#: somebody else (a quiet amber dot), `ok` / `no` / `off` = finished (grey).
REQUEST_BUCKETS = {'act': 'act', 'wait': 'wait', 'ok': 'done', 'no': 'done',
                   'off': 'done'}
REQUEST_TONES = tuple(REQUEST_BUCKETS)
#: How many rows My requests shows before "Show earlier".
MY_REQUESTS_PAGE = 50
#: The newest N records read per source (a person files far fewer).
MY_REQUESTS_PER_SOURCE = 500

#: "Needs you" order is fixed (M-R6).
NEEDS_ORDER = (
    'shifts_to_confirm', 'doc_expired', 'doc_expiring', 'timesheet_missing',
    'overtime_pending', 'training_overdue', 'training_due_soon',
    'goals_to_set', 'profile_waiting', 'profile_approved',
)

#: (url, group, icon, tone, extras) — order inside a group is the order here.
#: Icons are names `pb_me_portal.ess_icon` can draw (a source test checks it);
#: tones are the kit's badge colours. Title/text overrides live in
#: `_TILE_WORDS` below; a tile whose text is live (Public holidays) keeps its
#: own.
_TILE_ROWS = (
    # --- Me (the strip inside the bento) ---
    ('/my/profile', 'me', 'user', 'indigo', {}),
    ('/my/documents', 'me', 'file', 'amber', {}),
    ('/my/taxsheet', 'me', 'calculator', 'slate', {}),
    ('/my/assets', 'me', 'laptop', 'blue', {}),
    ('/my/compensation', 'me', 'gift', 'pink', {}),
    # TIERS T3a: every request the person made, in one list
    ('/my/requests', 'me', 'list-checks', 'teal', {}),
    # --- Time ---
    ('/my/work/schedule', 'time', 'calendar', 'indigo', {}),
    ('/my/work/timesheet', 'time', 'clock', 'blue', {}),
    ('/my/work/overtime', 'time', 'timer', 'amber', {}),
    ('/my/holidays', 'time', 'sun', 'teal', {}),
    # its door is the Leave card (M2); the tile is not drawn from M1 on
    ('/my/work/leave', 'time', 'umbrella', 'green', {'hidden': True}),
    # --- Growth ---
    ('/my/goals', 'growth', 'target', 'indigo', {}),
    ('/my/growth', 'growth', 'trending-up', 'green', {}),
    ('/my/training', 'growth', 'graduation-cap', 'blue', {}),
    ('/my/training/claims', 'growth', 'wallet', 'teal', {}),
    ('/my/recognition', 'growth', 'award', 'pink', {}),
    # --- People ---
    # TIERS T3a: pb_ask_hr's tile (soft — the row is inert without it)
    ('/my/ask-hr', 'people', 'message-circle-question', 'indigo', {}),
    ('/my/orgchart', 'people', 'users', 'indigo', {}),
    ('/my/buddy', 'people', 'user-check', 'green', {}),
    ('/my/journey', 'people', 'route', 'blue', {}),
    ('/my/refer', 'people', 'user-plus', 'teal', {}),
    ('/my/hiring', 'people', 'briefcase', 'amber', {}),
    ('/my/training/team', 'people', 'graduation-cap', 'pink', {}),
    # --- More (stock + anything unknown) ---
    ('/my/security', 'more', 'shield', 'slate', {}),
    ('/my/addresses', 'more', 'map-pin', 'slate', {}),
    ('/my/resignation', 'more', 'log-out', 'slate', {}),
    ('/my/invoices', 'more', 'file', 'slate', {}),
    ('/my/projects', 'more', 'briefcase', 'slate', {}),
    ('/my/tasks', 'more', 'file', 'slate', {}),
    ('/my/timesheets', 'more', 'clock', 'slate', {}),
    # --- doors that are cards, not tiles ---
    # the Pay card is the payslips' door (M6) and the explainer's
    ('/my/payslips', 'me', 'banknote', 'green', {'hidden': True}),
    ('/my/pay', 'me', 'wallet', 'indigo', {'hidden': True}),
)

#: Shorter words per tile (the mock-up's one-line texts). A dict of single
#: `_lt` calls on purpose: inside the tuple rows above, the term extractor
#: kept collecting the following rows' URLs as translatable strings.
_TILE_WORDS = {
    '/my/profile': {'text': _lt('Details and changes')},
    '/my/documents': {'text': _lt('Certificates, IDs and permits')},
    '/my/taxsheet': {'text': _lt('Your tax, period by period')},
    '/my/assets': {'text': _lt('Laptop, phone, accounts')},
    '/my/compensation': {'text': _lt('Pay, cover, awards')},
    '/my/work/schedule': {'text': _lt('This week and next, in full')},
    '/my/work/timesheet': {'text': _lt('Scheduled against worked, day by day')},
    '/my/work/overtime': {'text': _lt('Recorded, approved, and at which rate')},
    '/my/goals': {'text': _lt('What you are working towards')},
    '/my/growth': {'text': _lt('What you and your manager agreed')},
    '/my/training': {'text': _lt('Your courses and their tests')},
    '/my/training/claims': {'text': _lt('What you may spend on a course')},
    '/my/recognition': {'text': _lt('Say thank you to a colleague')},
    '/my/orgchart': {'text': _lt('Find anyone, see the teams')},
    '/my/buddy': {'text': _lt('Who shows you the ropes')},
    '/my/journey': {'text': _lt('Your first weeks, step by step')},
    '/my/refer': {'text': _lt('Put a name forward for a role')},
    '/my/hiring': {'text': _lt('Interviews and roles you asked for')},
    '/my/training/team': {'text': _lt('Who still has a course to finish')},
    '/my/security': {'title': _lt('Sign-in & security'),
                     'text': _lt('Password, devices, sessions')},
    '/my/resignation': {'text': _lt('Hand in your notice')},
    '/my/requests': {'title': _lt('My requests'),
                     'text': _lt('Everything you asked for, and where it is')},
    '/my/ask-hr': {'title': _lt('Ask HR'),
                   'text': _lt('Questions and answers')},
}


def _build_tiles():
    tiles, pos = {}, {}
    for url, group, icon, tone, extra in _TILE_ROWS:
        n = pos.get(group, 0)
        pos[group] = n + 1
        tiles[url] = dict(extra, **_TILE_WORDS.get(url, {}), group=group,
                          icon=icon, tone=tone,
                          seq=GROUPS.index(group) * 100 + n + 1)
    return tiles


#: url path (no query string) → {group, icon, tone, seq, title?, text?,
#: hidden?, always?}
TILES = _build_tiles()

#: An unknown tile: a stock or future one lands in "More" with a document icon.
TILE_DEFAULT = {'group': 'more', 'icon': 'file', 'tone': 'slate',
                'seq': GROUPS.index('more') * 100 + 99}


class PbMeHome(models.AbstractModel):
    _name = 'pb.me.home'
    _description = 'Employee home page facts'

    TILES = TILES

    # ================================================================ tiles
    @api.model
    def tile_meta(self, url):
        """The registry entry for a tile URL (matched on the path before `?`),
        or the "More" default. Lazy words are resolved in this env's language."""
        path = (url or '').split('?', 1)[0].split('#', 1)[0]
        if len(path) > 1:
            path = path.rstrip('/')
        meta = dict(TILES.get(path) or TILE_DEFAULT)
        for key in ('title', 'text'):
            if isinstance(meta.get(key), LazyGettext):
                meta[key] = self.env._(meta[key])
        meta['path'] = path
        return meta

    # ============================================================= optional
    @api.model
    def optional(self, model_name, fn, *, fields=()):
        """Run ``fn(Model)`` only when ``model_name`` is installed and has every
        field in ``fields``; ``None`` otherwise, and ``None`` on any failure.

        AccessError is expected (a reader without a right) and logged at debug;
        anything else is a bug in a neighbour and logged as a warning with its
        trace. The savepoint keeps a failed statement from poisoning the rest
        of the page's transaction.
        """
        if not model_name or model_name not in self.env:
            return None
        Model = self.env[model_name]
        if any(f not in Model._fields for f in fields):
            return None
        try:
            with self.env.cr.savepoint(flush=False):
                return fn(Model)
        except AccessError:
            _logger.debug('pb_me_portal: home section on %s not readable by '
                          'user %s', model_name, self.env.uid)
            return None
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_portal: home section on %s failed',
                            model_name, exc_info=True)
            return None

    @api.model
    def _pbme_timed(self, name, fn):
        t0 = time.monotonic()
        try:
            return fn()
        finally:
            _logger.debug('pb_me_portal: home section %s timing_ms=%.1f', name,
                          (time.monotonic() - t0) * 1000.0)

    # ========================================================== entry point
    @api.model
    def get_home_data(self, emp, now=None):
        """Everything the employee home draws, as facts. ``None`` when there is
        no employee (the stock page renders) or the employee is not the
        caller's own (M-R4)."""
        if not isinstance(emp, models.BaseModel) or emp._name != 'hr.employee':
            return None
        emp = emp.sudo()[:1]
        if not emp or emp.user_id.id != self.env.uid:
            return None
        now = now or fields.Datetime.now()
        local_now = self._pbme_local_now(emp, now)
        today = local_now.date()
        monday = today - timedelta(days=today.weekday())

        person = self._pbme_timed('person', lambda: self.optional(
            'hr.employee', lambda E: self._pbme_person(emp, local_now)))
        if not person:
            return None
        pay = self._pbme_timed('pay', lambda: self.optional(
            'hr.payslip', lambda S: self._pbme_pay(S, emp, today)))
        leave = self._pbme_timed('leave', lambda: self.optional(
            'pb.ess.workforce', self._pbme_leave))
        week = self._pbme_timed('week', lambda: self.optional(
            'pb.ess.workforce', lambda W: self._pbme_week(W, monday)))
        needs, docs = self._pbme_timed(
            'needs_you', lambda: self._pbme_needs(emp, today, monday, now))
        return {
            'person': person,
            'pay': pay,
            'leave': leave,
            'week': week,
            'needs_you': needs,
            'docs': docs,
            'tiles': [dict(self.tile_meta(url), url=url) for url in TILES],
        }

    # ============================================================== person
    @api.model
    def _pbme_tz_name(self, emp):
        """The user's timezone, then the company's, then UTC."""
        for name in (self.env.user.tz,
                     emp.company_id.partner_id.tz if emp else None):
            if name and name in pytz.all_timezones_set:
                return name
        return 'UTC'

    @api.model
    def _pbme_local_now(self, emp, now):
        """`now` (naive UTC, as the ORM stores it) on the person's wall clock."""
        if now.tzinfo is None:
            now = pytz.utc.localize(now)
        return now.astimezone(pytz.timezone(self._pbme_tz_name(emp)))

    @api.model
    def _pbme_daypart(self, local_dt):
        """morning before 12:00, afternoon before 18:00, evening after — the
        same cut-offs as the payroll Home greeting."""
        if local_dt.hour < 12:
            return 'morning'
        if local_dt.hour < 18:
            return 'afternoon'
        return 'evening'

    @api.model
    def _pbme_name_last_first(self, emp):
        """Vietnamese names put the given name LAST ("Nguyễn Văn An" is An).

        Decided by the person, never by the company alone: a Vietnamese-language
        user, or a name that opens with a Vietnamese family name (the demo
        world's people read English but are Vietnamese). The live walk greeted
        "Mitchell Admin" of a Vietnamese company as "Admin" when the company's
        country decided it.
        """
        if self.env.user.lang == 'vi_VN':
            return True
        first = ((emp.name or '').split() or [''])[0]
        return first.casefold() in VN_FAMILY_NAMES

    @api.model
    def _pbme_short_name(self, name, given_name_last):
        words = (name or '').split()
        if not words:
            return ''
        return words[-1] if given_name_last else words[0]

    @api.model
    def _pbme_person(self, emp, local_now):
        return {
            'name': emp.name or '',
            'short_name': self._pbme_short_name(
                emp.name, self._pbme_name_last_first(emp)),
            'daypart': self._pbme_daypart(local_now),
            'job': emp.job_title or emp.job_id.name or '',
            'company': emp.company_id.name or '',
            'avatar_url': self._photo_url(emp, 'avatar_128'),
            'date': local_now.date(),
        }

    @api.model
    def _photo_url(self, employee, size='avatar_128'):
        """Where the browser fetches the person's OWN photo (TIERS T2, ledger
        T14) — `/my/photo/<id>/<size>`, for every kind of login.

        `/web/image/hr.employee*` answers the placeholder to an employee login
        (a share account has no ACL on either employee model); the route reads
        the image under sudo after an own-employee guard. One code path, so an
        internal person's page and an employee login's page draw the same."""
        if not employee:
            return ''
        return '/my/photo/%s/%s' % (employee.id, size)

    # ================================================================= pay
    @api.model
    def _pbme_net(self, slip):
        """The slip's own net line (the one-pay-band rule), never a sum."""
        line = slip.line_ids.pb_net_line()
        return line.total if line else None

    @api.model
    def _pbme_slip_currency(self, slip):
        run = slip.payslip_run_id
        if run and 'pb_currency_id' in run._fields and run.pb_currency_id:
            return run.pb_currency_id
        return slip.company_id.currency_id

    @api.model
    def _pbme_next_pay_date(self, emp, today):
        """The pay calendar's next pay day for the employee's company, else a
        shared row's, else None (M9 — never guessed)."""
        def read(Cal):
            Cal = Cal.sudo()
            base = [('state', '=', 'upcoming'), ('pay_date', '>=', today)]
            row = Cal.search(base + [('company_id', '=', emp.company_id.id)],
                             order='pay_date asc, id asc', limit=1)
            if not row:
                row = Cal.search(base + [('company_id', '=', False)],
                                 order='pay_date asc, id asc', limit=1)
            return row.pay_date if row else None
        return self.optional('pb.payroll.calendar', read,
                             fields=('pay_date', 'state', 'company_id'))

    @api.model
    def _pbme_pay(self, Slip, emp, today):
        Slip = Slip.sudo()
        domain = [('employee_id', '=', emp.id), ('state', '=', 'done')]
        next_pay = self._pbme_next_pay_date(emp, today)
        common = {
            'next_pay_date': next_pay,
            'next_pay_days': (next_pay - today).days if next_pay else None,
            'explain_url': '/my/pay' if 'pb.pay.apply' in self.env else None,
            'list_url': '/my/payslips',
        }
        slips = Slip.search(domain, order='date_to desc, id desc',
                            limit=TREND_MONTHS)
        if not slips:
            return dict(common, count=0)
        last = slips[0]
        currency = self._pbme_slip_currency(last)
        # one currency per card: a slip paid in another currency is not a
        # point on this trend and not the "previous" figure (no total ever
        # adds two currencies)
        same = slips.filtered(lambda s: self._pbme_slip_currency(s) == currency)
        nets = [(s, self._pbme_net(s)) for s in same]
        paid_on = None
        if 'pb_paid_on' in Slip._fields and last.pb_paid_on:
            paid_on = fields.Datetime.context_timestamp(
                self, last.pb_paid_on).date()
        previous = nets[1][1] if len(nets) > 1 else None
        return dict(
            common,
            count=Slip.search_count(domain),
            last={
                'id': last.id,
                'period_date': last.date_to,
                'net': nets[0][1],
                'currency_id': currency.id,
                'currency': currency,
                'pdf_url': last.get_portal_url(report_type='pdf', download=True),
                'view_url': last.get_portal_url(),
                'paid_on': paid_on,
            },
            previous_net=previous,
            trend=[{'month_date': s.date_to, 'net': net}
                   for s, net in reversed(nets) if net is not None],
        )

    # =============================================================== leave
    @api.model
    def _pbme_leave(self, Ess):
        data = Ess.get_my_leave() or {}
        rows = data.get('balances') or []
        return {
            'left': round(sum(r.get('balance') or 0.0 for r in rows), 2),
            'allocated': round(sum(r.get('allocated') or 0.0 for r in rows), 2),
            'booked_pending': data.get('pending') or 0,
            'low': any(r.get('low') for r in rows),
            'types': len(rows),
            'url': '/my/work/leave',
        }

    # ================================================================ week
    @api.model
    def _pbme_hm_short(self, hhmm):
        """'09:00' → '9', '09:30' → '9:30' — a day cell is ~45 px wide, and
        '09:00–18:00' would be cut to '09:0…' on every desktop (M2)."""
        hh, _sep, mm = (hhmm or '').partition(':')
        if not hh.isdigit():
            return hhmm or ''
        return str(int(hh)) + ('' if mm in ('', '00') else ':' + mm)

    @api.model
    def _pbme_week(self, Ess, monday):
        """The FIRST week of the schedule facade, kept as it gives it (its own
        day labels and shift hours); hr.shift.planning is not re-queried."""
        data = Ess.get_my_schedule(monday.isoformat()) or {}
        weeks = data.get('weeks') or []
        if not weeks:
            return None
        wk = weeks[0]
        days = []
        for d in wk.get('days') or []:
            cards = d.get('shifts') or []
            shift, short, state = None, None, 'off'
            if cards:
                first = cards[0]
                if first.get('start') and first.get('end'):
                    shift = '%s–%s' % (first['start'], first['end'])
                    short = '%s–%s' % (self._pbme_hm_short(first['start']),
                                       self._pbme_hm_short(first['end']))
                else:
                    shift = short = first.get('hours_label') or None
                state = ('pending' if any(c.get('can_ack') for c in cards)
                         else 'acked')
            elif d.get('leave'):
                state = 'leave'
            days.append({
                'date': fields.Date.to_date(d.get('date')),
                'is_today': bool(d.get('is_today')),
                'label': d.get('label') or '',
                'day_num': d.get('day_num'),
                'shift': shift,
                'shift_short': short,
                'shifts': len(cards),
                'state': state,
            })
        # the facade's own sum (round(sum(hours), 1)), read from the cards it
        # returned rather than parsed back out of a translated label
        scheduled = round(sum(c.get('hours') or 0.0
                              for d in (wk.get('days') or [])
                              for c in (d.get('shifts') or [])), 1)
        return {
            'days': days,
            'pending': wk.get('pending') or 0,
            'hours_label': wk.get('hours_label') or '',
            'scheduled_h': scheduled,
            'worked_h': self._pbme_worked_h(Ess, monday),
            'url': '/my/work/schedule',
        }

    @api.model
    def _pbme_worked_h(self, Ess, monday):
        """Hours worked so far this week: the timesheet facade's week total
        `totals.actual` (pb.time.hub `_person_week`: `{sched, actual,
        entered, delta}`), one decimal. ``None`` when the facade gives
        nothing — and a failure here only loses this one number, never the
        week card (its own savepoint through `optional`)."""
        def read(W):
            totals = (W.get_my_week(monday.isoformat()) or {}).get('totals') or {}
            actual = totals.get('actual')
            return None if actual is None else round(float(actual), 1)
        return self.optional(Ess._name, read)

    # ============================================================== words
    @api.model
    def fmt_num(self, value):
        """A count of days or hours as the reader's language writes it: no
        decimals when whole ("12", "38"), one when not ("9.5", or "9,5" in
        Vietnamese). Formatting only — the template still owns every word."""
        if value is None or value is False:
            return ''
        value = round(float(value), 1)
        return formatLang(self.env, value, digits=0 if value == int(value) else 1)

    # ============================================================ needs you
    @api.model
    def _pbme_needs(self, emp, today, monday, now):
        """`[{key, n, days?, url}]` in the fixed M-R6 order, zeros dropped;
        plus the document counts the Documents tile shows."""
        found = {}

        def put(key, n, url, **extra):
            # `label`/`sub`/`icon`/`tone`/`sentence` are for rows the
            # templates do not know (T3a, `_pbme_needs_extra`); a tone outside
            # the kit's badge colours falls back to slate
            if 'tone' in extra and extra['tone'] not in NEED_TONES:
                extra['tone'] = 'slate'
            if n:
                found[key] = dict(extra, key=key, n=int(n), url=url)

        counters = self.optional(
            'pb.ess.workforce', lambda W: W.get_my_counters()) or {}
        put('shifts_to_confirm', counters.get('shift_pending'),
            '/my/work/schedule')
        put('overtime_pending', counters.get('overtime_pending'),
            '/my/work/overtime')

        def doc_counts(Doc):
            Doc = Doc.sudo()
            own = [('employee_id', '=', emp.id)]
            expired = Doc.search_count(own + [('expiry_date', '<', today)])
            soon_dom = own + [('expiry_date', '>=', today),
                              ('expiry_date', '<=',
                               today + timedelta(days=DOC_SOON_DAYS))]
            soon = Doc.search_count(soon_dom)
            first = Doc.search(soon_dom, order='expiry_date asc', limit=1)
            return {
                'expired': expired, 'expiring': soon,
                'soonest_days': ((first.expiry_date - today).days
                                 if first else None),
            }
        docs = self.optional('pb.employee.document', doc_counts,
                             fields=('expiry_date', 'employee_id'))
        if docs:
            put('doc_expired', docs['expired'], '/my/documents')
            put('doc_expiring', docs['expiring'], '/my/documents',
                days=docs['soonest_days'])

        def missing(W):
            week = W.get_my_week(monday.isoformat()) or {}
            return sum(1 for d in week.get('days') or []
                       if 'missing' in (d.get('flags') or []))
        put('timesheet_missing',
            self.optional('pb.ess.workforce', missing), '/my/work/timesheet')

        training = self.optional('pb.my.training', lambda T: T.home()) or {}
        put('training_overdue', training.get('overdue'), '/my/training')
        put('training_due_soon', training.get('due_soon'), '/my/training')

        put('goals_to_set',
            self.optional('pb.my.goals', lambda G: G.home_count()), '/my/goals')

        def profile(Req):
            Req = Req.sudo()
            own = [('employee_id', '=', emp.id)]
            since = now - timedelta(days=APPROVED_RECENT_DAYS)
            return (Req.search_count(own + [('state', '=', 'hr_review')]),
                    Req.search_count(own + [('state', '=', 'approved'),
                                            ('write_date', '>=', since)]))
        waiting, approved = self.optional(
            'pb.profile.change.request', profile) or (0, 0)
        put('profile_waiting', waiting, '/my/profile')
        put('profile_approved', approved, '/my/profile')

        # TIERS T3a: rows other modules add (pb_ask_hr's "HR answered your
        # question"). A broken extra loses its own rows, never the card.
        try:
            with self.env.cr.savepoint(flush=False):
                self._pbme_needs_extra(emp, put)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_portal: an extra needs-you row failed',
                            exc_info=True)

        # the fixed M-R6 order first, then any key the order does not know,
        # in the order it was put
        ordered = [found[k] for k in NEEDS_ORDER if k in found]
        ordered += [row for key, row in found.items() if key not in NEEDS_ORDER]
        return ordered, docs

    @api.model
    def _pbme_needs_extra(self, emp, put):
        """Hook (TIERS T3a): add "Needs you" rows the templates do not know.

        Call ``put(key, n, url, label=…, sub=…, icon=…, tone=…, sentence=…)``
        with ``label`` (the row's bold line), ``sub`` (its grey line), a Lucide
        ``icon`` name `ess_icon` draws, a badge ``tone`` (NEED_TONES) and an
        optional one-line ``sentence`` for the top line when it is the only
        thing waiting. The words are the caller's, already translated. Rows
        land after the fixed order, in insertion order; ``n == 0`` is dropped.
        Every override must call ``super()``."""
        return None

    # ========================================================== my requests
    @api.model
    def _my_requests_fmt_date(self, value):
        """A date for a request title, in the reader's language."""
        return format_date(self.env, value) if value else ''

    @api.model
    def _my_requests_sources(self):
        """Every kind of request an employee can make, as one list of dicts
        (TIERS T3a, D5). Other modules extend it with ``super()``; a model that
        is not installed is simply skipped by `get_my_requests` (soft reads —
        this list never adds a dependency).

        Each dict: ``key``, ``model``, ``label`` (the kind, shown small),
        ``icon`` (Lucide, drawn by `ess_icon`), ``employee_field``,
        ``date_field`` (the sort date; ``create_date`` when empty),
        ``state_field``, ``states`` ``{value: (label, tone)}`` with tone in
        REQUEST_TONES, ``url(rec)`` and ``title(rec)``."""
        _ = self.env._
        fmt = self._my_requests_fmt_date
        has_workforce = 'pb.ess.workforce' in self.env

        def leave_title(rec):
            start = rec.request_date_from or (rec.date_from and rec.date_from.date())
            end = rec.request_date_to or (rec.date_to and rec.date_to.date())
            when = fmt(start) if start == end else '%s – %s' % (fmt(start), fmt(end))
            return '%s · %s' % (rec.holiday_status_id.name or _('Leave'), when)

        def timesheet_url(rec):
            if not has_workforce:
                return None
            monday = rec.date - timedelta(days=rec.date.weekday())
            return '/my/work/timesheet?week=%s' % monday.isoformat()

        def resignation_title(rec):
            lwd = rec.approved_lwd or rec.requested_lwd
            if lwd:
                return _('Resignation · last day %s', fmt(lwd))
            return _('Resignation')

        return [
            {
                'key': 'leave', 'model': 'hr.leave', 'label': _('Leave'),
                'icon': 'umbrella', 'employee_field': 'employee_id',
                'date_field': 'date_from', 'state_field': 'state',
                'states': {
                    'confirm': (_('Waiting approval'), 'wait'),
                    'validate1': (_('Waiting approval'), 'wait'),
                    'validate': (_('Approved'), 'ok'),
                    'refuse': (_('Refused'), 'no'),
                    'cancel': (_('Cancelled'), 'off'),
                },
                'url': lambda rec: '/my/work/leave' if has_workforce else None,
                'title': leave_title,
            },
            {
                'key': 'timesheet_fix', 'model': 'hr.attendance.correction',
                'label': _('Timesheet'), 'icon': 'clock',
                'employee_field': 'employee_id', 'date_field': 'date',
                'state_field': 'state',
                'states': {
                    'draft': (_('Draft'), 'off'),
                    'submitted': (_('With your manager'), 'wait'),
                    'approved': (_('Applied'), 'ok'),
                    'refused': (_('Refused'), 'no'),
                },
                'url': timesheet_url,
                'title': lambda rec: _('Timesheet fix · %s', fmt(rec.date)),
            },
            {
                'key': 'profile', 'model': 'pb.profile.change.request',
                'label': _('Profile'), 'icon': 'user',
                'employee_field': 'employee_id', 'date_field': 'create_date',
                'state_field': 'state',
                'states': {
                    'draft': (_('Draft'), 'off'),
                    'hr_review': (_('With HR'), 'wait'),
                    'approved': (_('Applied'), 'ok'),
                    'refused': (_('Refused'), 'no'),
                },
                'url': lambda rec: '/my/profile/request/%s' % rec.id,
                'title': lambda rec: _('Profile change'),
            },
            {
                'key': 'asset', 'model': 'pb.asset.request',
                'label': _('Equipment'), 'icon': 'laptop',
                'employee_field': 'employee_id', 'date_field': 'needed_by',
                'state_field': 'state',
                'states': {
                    'draft': (_('Draft'), 'off'),
                    'submitted': (_('Waiting for the manager'), 'wait'),
                    'manager_approved': (_('With HR'), 'wait'),
                    'approved': (_('Approved'), 'ok'),
                    'refused': (_('Turned down'), 'no'),
                    'cancelled': (_('Cancelled'), 'off'),
                },
                'url': lambda rec: '/my/assets',
                'title': lambda rec: _('Asset · %s', rec.category_id.name or ''),
            },
            {
                'key': 'resignation', 'model': 'pb.resignation',
                'label': _('Resignation'), 'icon': 'log-out',
                'employee_field': 'employee_id', 'date_field': 'submit_date',
                'state_field': 'state',
                'states': {
                    'draft': (_('Draft'), 'off'),
                    'submitted': (_('With the manager'), 'wait'),
                    'manager_ok': (_('With HR'), 'wait'),
                    'approved': (_('Accepted'), 'ok'),
                    'refused': (_('Not accepted'), 'no'),
                    'withdrawn': (_('Withdrawn'), 'off'),
                },
                'url': lambda rec: '/my/resignation',
                'title': resignation_title,
            },
            {
                'key': 'overtime', 'model': 'hr.overtime.request',
                'label': _('Overtime'), 'icon': 'timer',
                'employee_field': 'employee_id', 'date_field': 'date',
                'state_field': 'state',
                'states': {
                    'draft': (_('Draft'), 'off'),
                    'submitted': (_('Waiting approval'), 'wait'),
                    'approved': (_('Approved'), 'ok'),
                    'refused': (_('Refused'), 'no'),
                },
                'url': lambda rec: '/my/work/overtime' if has_workforce else None,
                'title': lambda rec: _('Overtime · %s', fmt(rec.date)),
            },
        ]

    @api.model
    def _my_requests_rows(self, src, emp):
        """One source's rows for ``emp`` — read under sudo keyed on the
        employee (T-R11). Raises on any failure; the caller isolates it."""
        Model = self.env[src['model']].sudo()
        recs = Model.search([(src['employee_field'], '=', emp.id)],
                            order='id desc', limit=MY_REQUESTS_PER_SOURCE)
        rows = []
        for rec in recs:
            state = rec[src['state_field']]
            label, tone = src['states'].get(state) or (state or '', 'off')
            if tone not in REQUEST_TONES:
                tone = 'off'
            when = rec[src['date_field']] or rec.create_date
            if not isinstance(when, datetime):
                when = datetime.combine(when, datetime.min.time())
            rows.append({
                'key': src['key'],
                'model': src['model'],
                'id': rec.id,
                'kind': src['label'],
                'icon': src.get('icon') or 'file',
                'title': src['title'](rec),
                'state': state,
                'state_label': label,
                'tone': tone,
                'bucket': REQUEST_BUCKETS[tone],
                'url': src['url'](rec),
                'date': when,
                'created': rec.create_date,
            })
        return rows

    @api.model
    def get_my_requests(self, emp, bucket=None):
        """Every request ``emp`` made, newest first (TIERS T3a).

        ``{'rows': [...], 'counts': {'act', 'wait', 'done', 'all'}}`` — the
        counts are over every row, ``rows`` keeps only ``bucket`` when one of
        ``act`` / ``wait`` / ``done`` is given. ``None`` when ``emp`` is not
        the caller's own (M-R4). Each source runs in its own savepoint through
        `optional`: one broken source is logged and skipped, never a blank
        page."""
        if not isinstance(emp, models.BaseModel) or emp._name != 'hr.employee':
            return None
        emp = emp.sudo()[:1]
        if not emp or emp.user_id.id != self.env.uid:
            return None
        rows = []
        for src in self._my_requests_sources():
            got = self.optional(
                src['model'], lambda M, src=src: self._my_requests_rows(src, emp),
                fields=(src['employee_field'], src['date_field'],
                        src['state_field']))
            rows.extend(got or [])
        rows.sort(key=lambda r: (r['date'], r['created'] or r['date'], r['id']),
                  reverse=True)
        counts = {'act': 0, 'wait': 0, 'done': 0, 'all': len(rows)}
        for row in rows:
            counts[row['bucket']] += 1
        if bucket in ('act', 'wait', 'done'):
            rows = [r for r in rows if r['bucket'] == bucket]
        return {'rows': rows, 'counts': counts}
