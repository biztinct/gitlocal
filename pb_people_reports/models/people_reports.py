# -*- coding: utf-8 -*-
"""`pb.people.reports` — People › Insights › People reports.

Turnover, joiners against leavers, why people leave, age and gender, length
of service; by company, department and period.

OWNER RULING P6:
  * HR ONLY (`hr.group_hr_user`), for the companies they can already see (the
    company switcher, narrowed by "who sees what" — `pb.group.scoped`). The
    payroll analytics audience does NOT get gender, age or leaving reasons
    through this door.
  * ANY group under 5 people is hidden — on screen, in the totals and in the
    download — and so is any figure that would let somebody work a hidden one
    out by subtraction (`suppress.py`). Hidden values never leave the server.
  * No money anywhere, so nothing is ever added across currencies.

NO STORED SNAPSHOT, NO JOB (a deviation from the FACTS sketch, on purpose):
every figure is worked out when the screen asks, from the employee records
and their version history, so there is nothing to backfill, nothing pending,
and installing schedules nothing. Reads never write.

HOW A PERSON IS COUNTED. One person can hold employments in several companies
of a group (`pb_person_id`, when pb_workseg is installed). Their employments
inside the companies being looked at are joined into stretches of continuous
work: a move from one company of the group to another the next day is NO
joiner and NO leaver for the group, but a leaver and a joiner for each
company. The screen says so.

Start date: the joining date, else the first contract start. A person with
neither counts in every month and never as a joiner (said on screen). An
archived record with no leaving date is left out (said on screen).
"""

import base64
import calendar
import io
import logging
from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from .suppress import FLOOR, Suppressor

_logger = logging.getLogger(__name__)

HR_GROUP = 'hr.group_hr_user'
#: Groups from these modules do not count as "being HR" (they imply it).
PAYROLL_MODULES = ('om_hr_payroll', 'payroll_analytics_approval', 'pb_payroll_ai_insights')
VIEWS = ('headcount', 'movement', 'leaving', 'age_gender', 'service')
FAR_PAST = date(1900, 1, 1)
FAR_FUTURE = date(9999, 12, 31)

AGE_BANDS = [('u25', 0, 25), ('25_34', 25, 35), ('35_44', 35, 45),
             ('45_54', 45, 55), ('55p', 55, 200)]
SERVICE_BANDS = [('u1', 0, 12), ('1_2', 12, 24), ('2_5', 24, 60),
                 ('5_10', 60, 120), ('10p', 120, 100000)]
GENDERS = ('female', 'male', 'other', 'none')
REASON_KINDS = ('resigned', 'dismissed', 'retired', 'other', 'none')
REASON_XMLIDS = {'hr.departure_resigned': 'resigned', 'hr.departure_fired': 'dismissed',
                 'hr.departure_retired': 'retired'}


def month_end(d):
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def months_between(a, b):
    """Whole months from a to b (b later)."""
    m = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        m -= 1
    return max(m, 0)


class PbPeopleReports(models.AbstractModel):
    _name = 'pb.people.reports'
    _inherit = ['pb.group.scoped']
    _description = 'People reports'

    # ============================================================ gates
    @api.model
    def _can_read(self):
        """HR staff. NOT the payroll team as such (owner ruling P6).

        On this build every payroll officer also holds the HR officer group,
        because the payroll groups IMPLY it. So "has the HR group" would hand
        gender, age and leaving reasons to the whole payroll team. Here the HR
        group must come from a group that is not a payroll group: somebody who
        is both HR and payroll still passes through their HR group."""
        if self.env.su:
            return True
        user = self.env.user
        if not user.has_group(HR_GROUP):
            return False
        hr = self.env.ref(HR_GROUP)
        own = user.sudo().group_ids
        data = self.env['ir.model.data'].sudo().search_read(
            [('model', '=', 'res.groups'), ('res_id', 'in', own.ids)], ['module', 'res_id'])
        payroll_ids = {d['res_id'] for d in data
                       if d['module'] in PAYROLL_MODULES or d['module'].startswith('pb_hr_payroll')}
        others = own.filtered(lambda g: g.id not in payroll_ids)
        return hr in others.sudo().all_implied_ids

    @api.model
    def can_open(self):
        return self._can_read()

    @api.model
    def _require(self):
        if not self._can_read():
            raise AccessError(_("People reports are for HR. Ask your administrator if you "
                                "believe you should see them."))

    @api.model
    def _companies(self):
        chosen = self.env.companies.ids or [self.env.company.id]
        return self._visible_companies(chosen)

    # ============================================================ options
    @api.model
    def get_options(self):
        if not self._can_read():
            return {'allowed': False, 'why': _("People reports are for HR. Ask your "
                                               "administrator if you believe you should see them.")}
        cids = self._companies()
        Company = self.env['res.company'].sudo()
        depts = self.env['hr.department'].sudo().search(
            [('company_id', 'in', cids or [0])], order='name')
        allowed_depts = set(self._visible_departments() or [])
        if allowed_depts:
            depts = depts.filtered(lambda d: d.id in allowed_depts)
        years = self._years()
        return {
            'allowed': True, 'why': '',
            'floor': FLOOR,
            'companies': [{'id': c.id, 'name': c.name or ''} for c in Company.browse(cids)],
            'departments': [{'id': d.id, 'name': d.complete_name or d.name or '',
                             'company_id': d.company_id.id} for d in depts],
            'years': [{'year': y, 'label': lbl} for y, lbl in years],
            'year': years[0][0],
            'views': [{'key': k, 'label': v} for k, v in self._view_labels().items()],
            'note': self._visibility_note() or '',
        }

    @api.model
    def _view_labels(self):
        return {
            'headcount': _('Headcount and turnover'),
            'movement': _('Joiners and leavers'),
            'leaving': _('Why people leave'),
            'age_gender': _('Age and gender'),
            'service': _('Length of service'),
        }

    # ============================================================ params
    @api.model
    def _params(self, params):
        params = params or {}
        visible = self._companies()
        if not visible:
            raise UserError(_("You do not see any company here."))
        try:
            cid = int(params.get('company_id') or 0)
        except (TypeError, ValueError):
            cid = 0
        companies = [cid] if cid in visible else list(visible)
        try:
            dept = int(params.get('department_id') or 0)
        except (TypeError, ValueError):
            dept = 0
        allowed_depts = set(self._visible_departments() or [])
        if dept:
            d = self.env['hr.department'].sudo().browse(dept).exists()
            if not d or d.company_id.id not in companies or (allowed_depts and dept not in allowed_depts):
                dept = 0
            else:
                # a department is looked at inside its own company, the screen
                # its parent table is on
                companies = [d.company_id.id]
        # FIXED CALENDAR YEARS, month-end figures only. A sliding window
        # ("the last 12 months", any end month) would let two windows be
        # subtracted to give one month's hidden figure; a year is a fixed block.
        years = [y for y, _l in self._years()]
        try:
            year = int(params.get('year') or years[0])
        except (TypeError, ValueError):
            year = years[0]
        year = year if year in years else years[0]
        last = self._last_month_end()
        ends = [month_end(date(year, mo, 1)) for mo in range(1, 13)]
        ends = [d for d in ends if d <= last]
        months = len(ends)
        return {'visible': list(visible), 'companies': companies, 'department_id': dept,
                'allowed_depts': allowed_depts, 'months': months, 'ends': ends,
                'year': year, 'start': ends[0].replace(day=1), 'end': ends[-1],
                '_cache': {}}

    @api.model
    def _last_month_end(self):
        """The last COMPLETE month: today's figures change every day, and two
        days' figures subtracted would name a single joiner or leaver."""
        today = fields.Date.context_today(self)
        return today.replace(day=1) - timedelta(days=1)

    @api.model
    def _years(self):
        """This year (once a month of it is complete) and the four before."""
        last = self._last_month_end()
        out = []
        for y in range(last.year, last.year - 5, -1):
            if y == last.year and last.year == fields.Date.context_today(self).year:
                out.append((y, _('%s so far', y)))
            else:
                out.append((y, str(y)))
        return out

    # ============================================================ the people
    @api.model
    def _people_records(self, company_ids):
        """Every employment of these companies (archived ones too), read once."""
        Emp = self.env['hr.employee']
        cr = self.env.cr
        has_person = 'pb_person_id' in Emp._fields and Emp._fields['pb_person_id'].store
        has_join = 'date_of_joining' in Emp._fields and Emp._fields['date_of_joining'].store
        self.env.flush_all()
        cr.execute("""
            SELECT e.id, e.company_id, e.active, e.birthday,
                   v.departure_date, v.departure_reason_id, v.sex,
                   {person}, {joining}
              FROM hr_employee e
              JOIN hr_version v ON v.id = e.current_version_id
             WHERE e.company_id IN %s
        """.format(person='e.pb_person_id' if has_person else 'NULL',
                   joining='e.date_of_joining' if has_join else 'NULL'),
                   (tuple(company_ids) or (0,),))
        rows = cr.fetchall()
        ids = [r[0] for r in rows]
        versions = defaultdict(list)
        first_contract = {}
        if ids:
            cr.execute("""
                SELECT employee_id, date_version, department_id, contract_date_start
                  FROM hr_version
                 WHERE employee_id IN %s AND active
                 ORDER BY employee_id, date_version, id
            """, (tuple(ids),))
            for emp_id, dv, dept, cstart in cr.fetchall():
                versions[emp_id].append((dv, dept))
                if cstart and (emp_id not in first_contract or cstart < first_contract[emp_id]):
                    first_contract[emp_id] = cstart
        reason_kind = {}
        for xmlid, kind in REASON_XMLIDS.items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                reason_kind[rec.id] = kind
        out, no_start, no_end = [], 0, 0
        for (eid, cid, active, birthday, dep_date, dep_reason, sex, person, joining) in rows:
            start = joining or first_contract.get(eid)
            if not active and not dep_date:
                no_end += 1
                continue
            if not start:
                no_start += 1
            out.append({
                'id': eid, 'company_id': cid, 'person': ('p', person) if person else ('e', eid),
                'start': start, 'end': dep_date, 'birthday': birthday,
                'sex': sex if sex in ('female', 'male', 'other') else 'none',
                'reason': (reason_kind.get(dep_reason, 'other') if dep_reason else 'none'),
                'versions': versions.get(eid) or [],
            })
        return out, {'no_start': no_start, 'no_end': no_end}

    @staticmethod
    def _dept_at(rec, day):
        dept = None
        for dv, d in rec['versions']:
            if dv and dv <= day:
                dept = d
            elif dept is None:
                dept = d
                break
        return dept

    @api.model
    def _stretches(self, records):
        """Per person: their continuous stretches of work in these records."""
        by_person = defaultdict(list)
        for rec in records:
            by_person[rec['person']].append(rec)
        out = []
        for person, recs in by_person.items():
            spans = sorted(((r['start'] or FAR_PAST, r['end'] or FAR_FUTURE, r) for r in recs),
                           key=lambda x: (x[0], x[1]))
            cur = None
            for s, e, r in spans:
                if cur and s <= cur['end'] + timedelta(days=1):
                    if e >= cur['end']:
                        cur['end'], cur['end_rec'] = e, r
                    cur['recs'].append(r)
                else:
                    cur = {'person': person, 'start': s, 'end': e, 'start_rec': r,
                           'end_rec': r, 'recs': [r]}
                    out.append(cur)
        return out

    @staticmethod
    def _rec_at(stretch, day):
        best = None
        for r in stretch['recs']:
            s, e = r['start'] or FAR_PAST, r['end'] or FAR_FUTURE
            if s <= day <= e and (best is None or (best['start'] or FAR_PAST) <= s):
                best = r
        return best or stretch['end_rec']

    @api.model
    def _measure(self, records, ends, dept=None, allowed_depts=None):
        """Headcount per month-end, joiners/leavers per month, and the
        people at the period end / leavers of the period with their facts."""
        stretches = self._stretches(records)
        start = ends[0].replace(day=1)

        def in_scope(rec, day):
            d = self._dept_at(rec, day)
            if allowed_depts and d not in allowed_depts:
                return False
            return not dept or d == dept

        def head_on(day):
            n = 0
            for st in stretches:
                if st["start"] <= day < st["end"]:
                    if in_scope(self._rec_at(st, day), day):
                        n += 1
            return n
        heads = [head_on(day) for day in ends]
        # the headcount the day before the period starts
        h0 = head_on(start - timedelta(days=1))
        month_of = {(d.year, d.month): i for i, d in enumerate(ends)}
        joins = [0] * len(ends)
        leaves = [0] * len(ends)
        leavers, joiners = [], []
        for st in stretches:
            s, e = st['start'], st['end']
            if s != FAR_PAST and start <= s <= ends[-1] and in_scope(st['start_rec'], s):
                i = month_of.get((s.year, s.month))
                if i is not None:
                    joins[i] += 1
                    joiners.append(st)
            if e != FAR_FUTURE and start <= e <= ends[-1] and in_scope(st['end_rec'], e):
                i = month_of.get((e.year, e.month))
                if i is not None:
                    leaves[i] += 1
                    leavers.append(st)
        last = ends[-1]
        at_end = []
        for st in stretches:
            if st["start"] <= last < st["end"]:
                rec = self._rec_at(st, last)
                if in_scope(rec, last):
                    at_end.append((st, rec))
        return {'ends': ends, 'heads': heads, 'h0': h0, 'joins': joins, 'leaves': leaves, 'at_end': at_end,
                'leavers': leavers, 'joiners': joiners, 'stretches': stretches,
                # without a department filter, this month = last month + joiners - leavers
                'exact': not dept and not allowed_depts}

    # ============================================================ figures
    @api.model
    def _breakdown(self, P, records, by, companies=None):
        """Rows of the company / department table: headcount at the end,
        average headcount, joiners, leavers — per company or department."""
        ends = P['ends']
        rows = {}
        if by == 'company':
            for cid in companies:
                m = self._measure([r for r in records if r['company_id'] == cid], ends,
                                  allowed_depts=P['allowed_depts'])
                rows[cid] = {'h': m['heads'][-1], 'j': sum(m['joins']), 'l': sum(m['leaves']),
                             'avg': sum(m['heads']) / len(ends)}
            return rows
        m = self._measure(records, ends, allowed_depts=P['allowed_depts'])
        allowed = P['allowed_depts']
        acc = defaultdict(lambda: {'h': 0, 'j': 0, 'l': 0, 'avg': 0.0, 'heads': [0] * len(ends)})
        for i, day in enumerate(ends):
            for st in m['stretches']:
                if st["start"] <= day < st["end"]:
                    d = self._dept_at(self._rec_at(st, day), day)
                    if allowed and d not in allowed:
                        continue
                    acc[d or 0]['heads'][i] += 1
        for st in m['joiners']:
            acc[self._dept_at(st['start_rec'], st['start']) or 0]['j'] += 1
        for st in m['leavers']:
            acc[self._dept_at(st['end_rec'], st['end']) or 0]['l'] += 1
        for row in acc.values():
            row['h'] = row['heads'][-1]
            row['avg'] = sum(row['heads']) / len(ends)
            row.pop('heads')
        return dict(acc)

    @staticmethod
    def _quarters(m):
        """(joiners, leavers) per calendar quarter of the period."""
        out = {}
        for i, day in enumerate(m['ends']):
            q = (day.month - 1) // 3
            j, l = out.get(q, (0, 0))
            out[q] = (j + m['joins'][i], l + m['leaves'][i])
        return [out[q] for q in sorted(out)]

    @api.model
    def _series_suppressor(self, m, force=(), hide_all=False):
        """The month-by-month figures of one scope and their totals."""
        # WHY QUARTERS. The headcount is shown for every month, so the change
        # from one month to the next is public: joiners minus leavers. With
        # joiners and leavers ALSO shown month by month, a reader can piece
        # almost every small month together (the audit proves it, and then
        # hides nearly everything for a small company). So joiners and
        # leavers are shown by QUARTER and for the year; the headcount stays
        # monthly. Each quarter's difference is still public (quarter-end
        # headcounts), which the pairs below say.
        S = Suppressor()
        n = len(m['heads'])
        S.cell('H0', m['h0'])
        for i in range(n):
            S.cell(('H', i), m['heads'][i])
        quarters = self._quarters(m)
        for q, (j, l) in enumerate(quarters):
            S.cell(('J', q), j)
            S.cell(('L', q), l)
            S.add_pair(('J', q), ('L', q))
        S.cell('S:h_end', m['heads'][-1])
        S.cell('S:j', sum(m['joins']))
        S.cell('S:l', sum(m['leaves']))
        S.add_set('S:j', [('J', q) for q in range(len(quarters))])
        S.add_set('S:l', [('L', q) for q in range(len(quarters))])
        S.add_pair('S:j', 'S:l')
        # average headcount = (start + end) / 2, and turnover = leavers / it
        S.add_derived('S:avg', ['H0', 'S:h_end'])
        S.add_derived('S:rate', ['S:l', 'H0', 'S:h_end'])
        # widening hides a month's headcount before one of these
        S.protect = {'S:h_end', 'H0', 'S:j', 'S:l'}
        for key in force:
            S.force(key)
        if hide_all:
            for key in list(S.values):
                S.force(key)
        S.solve()
        # the headcount at the end IS the last month's headcount
        if S.is_hidden('S:h_end') or S.is_hidden(('H', n - 1)):
            S.hidden.update({'S:h_end', ('H', n - 1)})
        return S

    @api.model
    def _breakdown_table(self, P, records, by, companies, m, S_series):
        """The company / department table of a scope, suppressed — the ONE
        way it is computed, used by the table on screen and by every child
        screen's parent check.

        Both directions: the table takes the hiding of the scope's own tiles
        (its totals), AND each row takes the hiding its own screen needs on
        its own (e.g. a company hides its leavers to protect its quarters),
        so the table never shows a figure a child screen had to hide."""
        scope_recs = [r for r in records if r['company_id'] in companies]
        if by == 'company':
            rows = self._breakdown(P, scope_recs, 'company', companies=companies)
        else:
            rows = self._breakdown(P, scope_recs, 'department')
        own = {}
        for key in rows:
            ck = ('own', by, key)
            if ck not in P['_cache']:
                if by == 'company':
                    rm = self._measure([r for r in scope_recs if r['company_id'] == key],
                                       P['ends'], allowed_depts=P['allowed_depts'])
                else:
                    rm = self._measure(scope_recs, P['ends'], dept=key or None,
                                       allowed_depts=P['allowed_depts'])
                P['_cache'][ck] = self._series_suppressor(rm)
            RS = P['_cache'][ck]
            own[key] = {col for col, cell in (('h', 'S:h_end'), ('j', 'S:j'), ('l', 'S:l'))
                        if RS.is_hidden(cell)}
        return self._table_suppressor(rows, m, S_series, own=own), rows

    @api.model
    def _table_suppressor(self, rows, m, S_series, own=None):
        """The company / department table. Its totals are the scope's tiles,
        so whatever the tiles hide, the table's total hides too."""
        S = Suppressor()
        S.cell('T:h', m['heads'][-1])
        S.cell('T:j', sum(m['joins']))
        S.cell('T:l', sum(m['leaves']))
        for key, r in rows.items():
            S.cell(('R', key, 'h'), r['h'])
            S.cell(('R', key, 'j'), r['j'])
            S.cell(('R', key, 'l'), r['l'])
            # a row's headcount change is its joiners less its leavers
            S.add_pair(('R', key, 'j'), ('R', key, 'l'))
        for col in ('h', 'j', 'l'):
            S.add_set('T:%s' % col, [('R', k, col) for k in rows])
        S.add_pair('T:j', 'T:l')
        for col, cell in (('h', 'S:h_end'), ('j', 'S:j'), ('l', 'S:l')):
            if S_series.is_hidden(cell):
                S.force('T:%s' % col)
        for key, cols in (own or {}).items():
            for col in cols:
                S.force(('R', key, col))
        # the totals are the scope's tiles, shown on screen already
        S.public = {'T:h', 'T:j', 'T:l'} - S.forced
        return S.solve()

    @api.model
    def _scope_figures(self, P, records, companies, dept):
        """(measure, suppressor, too_small) for one scope, with the hiding of
        its PARENT table applied: a company or department looked at on its
        own never shows what its row in the parent table hides. The parent is
        computed exactly as the parent screen computes it (same calls), so
        the two always agree."""
        ckey = (tuple(sorted(companies)), dept or 0)
        if ckey in P['_cache']:
            return P['_cache'][ckey]
        scope_recs = [r for r in records if r['company_id'] in companies]
        force, too_small, parent = set(), False, None
        if dept:
            pm, PSs, _small = self._scope_figures(P, records, companies, None)
            PS, rows = self._breakdown_table(P, records, 'department', companies, pm, PSs)
            parent = (PS, rows, dept)
        elif len(companies) == 1 and len(P['visible']) > 1:
            gm, GSs, _small = self._scope_figures(P, records, P['visible'], None)
            PS, rows = self._breakdown_table(P, records, 'company', P['visible'], gm, GSs)
            parent = (PS, rows, companies[0])
        if parent:
            PS, rows, key = parent
            if key not in rows or PS.is_hidden(('R', key, 'h')):
                too_small = True
            for col, cell in (('h', 'S:h_end'), ('j', 'S:j'), ('l', 'S:l')):
                if key in rows and PS.is_hidden(('R', key, col)):
                    force.add(cell)
        m = self._measure(scope_recs, P['ends'], dept=dept or None,
                          allowed_depts=P['allowed_depts'])
        S = self._series_suppressor(m, force=force, hide_all=too_small)
        P['_cache'][ckey] = (m, S, too_small)
        return m, S, too_small

    @api.model
    def _shared(self, P):
        """Everything every view shares, suppressed ONCE, so a figure that is
        on two screens is hidden on both."""
        records, notes = self._people_records(P['visible'])
        m, S, too_small = self._scope_figures(P, records, P['companies'], P['department_id'])
        return {'m': m, 'S': S, 'notes': notes, 'too_small': too_small,
                'all_records': records,
                'records': [r for r in records if r['company_id'] in P['companies']]}

    # ============================================================ the views
    @api.model
    def get_report(self, view, params=None):
        self._require()
        if view not in VIEWS:
            view = 'headcount'
        P = self._params(params)
        B = self._shared(P)
        S, m = B['S'], B['m']
        n = len(P['ends'])
        avg = (m['h0'] + m['heads'][-1]) / 2.0
        out = {
            'view': view,
            'title': self._view_labels()[view],
            'period': _('%(start)s to %(end)s', start=format_date(self.env, P['start']),
                        end=format_date(self.env, P['end'])),
            'floor': FLOOR,
            'too_small': B['too_small'],
            'scope_note': self._scope_sentence(P),
            'notes': self._data_notes(B['notes']),
            'tiles': self._tiles(S, m, avg),
        }
        months = [format_date(self.env, d, date_format='MMM y') for d in P['ends']]
        if view in ('headcount', 'movement'):
            out['series'] = [{'month': months[i], 'h': S.out(('H', i))} for i in range(n)]
            quarters = self._quarters(m)
            last_i = {}
            for i, day in enumerate(P['ends']):
                last_i[(day.month - 1) // 3] = i
            qkeys = sorted(last_i)
            out['quarters'] = [{
                'label': _('Q%(q)s %(year)s', q=qk + 1, year=P['year']),
                'j': S.out(('J', q)), 'l': S.out(('L', q)),
                'net': self._net(S, quarters, q, last_i[qk],
                                 last_i[qkeys[q - 1]] if q else None, exact=m['exact']),
            } for q, qk in enumerate(qkeys)]
            if view == 'headcount':
                out['table'] = self._group_table(P, B)
                out['crosscheck'] = self._crosscheck(P)
        elif view == 'leaving':
            out.update(self._leaving(P, B))
        elif view == 'age_gender':
            out.update(self._age_gender(P, B))
        elif view == 'service':
            out.update(self._service(P, B))
        return out

    @api.model
    def _net(self, S, quarters, q, end_i, prev_i, exact=True):
        """A quarter's joiners less its leavers: shown when both are shown,
        or when the two headcounts around the quarter are (it is then simply
        their difference, already on the screen)."""
        prev = 'H0' if prev_i is None else ('H', prev_i)
        j, l = quarters[q]
        both_h = exact and not S.is_hidden(prev) and not S.is_hidden(('H', end_i))
        if both_h or not (S.is_hidden(('J', q)) or S.is_hidden(('L', q))):
            return {'v': j - l, 'h': False}
        return {'v': None, 'h': True}

    @api.model
    def _tiles(self, S, m, avg):
        rate_hidden = S.is_hidden('S:l') or S.is_hidden('S:avg')
        rate = round(sum(m['leaves']) * 100.0 / avg, 1) if avg and not rate_hidden else None
        return {
            'h_end': S.out('S:h_end'),
            'avg': {'v': None if S.is_hidden('S:avg') else round(avg, 1),
                    'h': S.is_hidden('S:avg')},
            'j': S.out('S:j'), 'l': S.out('S:l'),
            'rate': {'v': rate, 'h': rate is None and bool(avg)},
        }

    @api.model
    def _group_table(self, P, B):
        by = 'company' if len(P['companies']) > 1 else 'department'
        if P['department_id']:
            return {'by': by, 'rows': [], 'skipped': True}
        # exactly the call a child screen's parent check makes
        TS, rows = self._breakdown_table(P, B['all_records'], by, P['companies'], B['m'], B['S'])
        if by == 'company':
            names = {c.id: c.name for c in self.env['res.company'].sudo().browse(list(rows))}
        else:
            names = {d.id: d.name for d in self.env['hr.department'].sudo().browse(
                [k for k in rows if k])}
        out_rows = []
        # No turnover % per row: it would need the row's start headcount,
        # which this table does not show (and must not give away).
        for key, r in rows.items():
            out_rows.append({
                'name': names.get(key) or _('No department'),
                'h': TS.out(('R', key, 'h')), 'j': TS.out(('R', key, 'j')),
                'l': TS.out(('R', key, 'l')),
            })
        out_rows.sort(key=lambda x: x['name'] or '')
        # the total row IS the tiles (same figures, same hiding as the tiles)
        S = B['S']
        return {'by': by, 'rows': out_rows,
                'total': {'h': S.out('S:h_end'), 'j': S.out('S:j'), 'l': S.out('S:l')}}

    @api.model
    def _cat_keys(self, which):
        return {
            'reason': list(REASON_KINDS),
            'leave_service': [b[0] for b in SERVICE_BANDS] + ['none'],
            'age': [b[0] for b in AGE_BANDS] + ['none'],
            'gender': list(GENDERS),
            'service': [b[0] for b in SERVICE_BANDS] + ['none'],
        }[which]

    @api.model
    def _cat_counts(self, m, which, last):
        """How many people of one scope fall in each group."""
        acc = defaultdict(int)
        if which in ('reason', 'leave_service'):
            for st in m['leavers']:
                if which == 'reason':
                    acc[st['end_rec']['reason']] += 1
                elif st['start'] == FAR_PAST:
                    acc['none'] += 1
                else:
                    acc[self._band(months_between(st['start'], st['end']), SERVICE_BANDS)] += 1
            return acc
        for st, rec in m['at_end']:
            if which == 'gender':
                acc[rec['sex']] += 1
            elif which == 'age':
                b = rec['birthday']
                acc[self._band(months_between(b, last) // 12, AGE_BANDS) if b else 'none'] += 1
            elif st['start'] == FAR_PAST:
                acc['none'] += 1
            else:
                acc[self._band(months_between(st['start'], last), SERVICE_BANDS)] += 1
        return acc

    @api.model
    def _cats(self, P, B, which):
        """One breakdown (why they left, age bands, ...) of the scope.

        With several companies visible it is worked out as ONE table —
        companies down, groups across, company totals and group totals — and
        suppressed as a table, so the group's figure and one company's figure
        can never be subtracted to give another company's hidden one. The
        screen then shows the column totals (whole group) or one row (one
        company). Each total takes the hiding of the same figure on the
        Headcount screen (headcount at the end, or leavers)."""
        keys = self._cat_keys(which)
        leavers = which in ('reason', 'leave_service')
        tot_cell = 'S:l' if leavers else 'S:h_end'
        last = P['ends'][-1]
        records = B['all_records']
        S = Suppressor()

        def total_of(m):
            return len(m['leavers']) if leavers else len(m['at_end'])

        if len(P['visible']) == 1:
            m, Ss = B['m'], B['S']
            counts = self._cat_counts(m, which, last)
            S.cell('T', total_of(m))
            if Ss.is_hidden(tot_cell):
                S.force('T')
            for k in keys:
                S.cell(('G', k), counts.get(k, 0))
            S.add_set('T', [('G', k) for k in keys])
            S.public = {"T"} - S.forced      # the tile, already on screen
            S.solve()
            return S, 'T', lambda k: ('G', k)
        gm, GS, _small = self._scope_figures(P, records, P['visible'], None)
        gcounts = self._cat_counts(gm, which, last)
        S.cell('T', total_of(gm))
        if GS.is_hidden(tot_cell):
            S.force('T')
        for k in keys:
            S.cell(('G', k), gcounts.get(k, 0))
        S.add_set('T', [('G', k) for k in keys])
        for cid in P['visible']:
            cm, CS, _small = self._scope_figures(P, records, [cid], None)
            ccounts = self._cat_counts(cm, which, last)
            S.cell(('C', cid), total_of(cm))
            if CS.is_hidden(tot_cell):
                S.force(('C', cid))
            for k in keys:
                S.cell(('X', cid, k), ccounts.get(k, 0))
            S.add_set(('C', cid), [('X', cid, k) for k in keys])
        for k in keys:
            S.add_set(('G', k), [('X', c, k) for c in P['visible']])
        S.add_set('T', [('C', c) for c in P['visible']])
        # the group and company totals are tiles, already on screen
        S.public = ({"T"} | {("C", c) for c in P["visible"]}) - S.forced
        S.solve()
        if len(P['companies']) == 1:
            cid = P['companies'][0]
            return S, ('C', cid), lambda k: ('X', cid, k)
        return S, 'T', lambda k: ('G', k)

    @api.model
    def _cat_rows(self, P, B, which, labels):
        if P['department_id']:
            return None, []
        S, total, cell = self._cats(P, B, which)
        rows = []
        for k in self._cat_keys(which):
            rows.append({'key': k, 'label': labels[k], 'n': S.out(cell(k)),
                         'pct': self._pct(S, cell(k), total)})
        return S.out(total), rows

    @api.model
    def _leaving(self, P, B):
        total, reasons = self._cat_rows(P, B, 'reason', self._reason_labels())
        _t2, service = self._cat_rows(P, B, 'leave_service', self._service_labels())
        return {
            'dept_not_offered': bool(P['department_id']),
            'total': total, 'reasons': reasons, 'service_rows': service,
            'voluntary_note': _('Resigned counts as leaving by choice. Dismissed and retired do not.'),
        }

    @api.model
    def _age_gender(self, P, B):
        total, genders = self._cat_rows(P, B, 'gender', self._gender_labels())
        _t2, ages = self._cat_rows(P, B, 'age', self._age_labels())
        return {'dept_not_offered': bool(P['department_id']),
                'total': total, 'genders': genders, 'ages': ages}

    @api.model
    def _service(self, P, B):
        total, rows = self._cat_rows(P, B, 'service', self._service_labels())
        return {'dept_not_offered': bool(P['department_id']),
                'total': total, 'service_rows': rows}

    # ============================================================ helpers
    @staticmethod
    def _band(value, bands, unit=None):
        for key, lo, hi in bands:
            if lo <= value < hi:
                return key
        return bands[-1][0]

    @staticmethod
    def _pct(S, cell, total):
        if S.is_hidden(cell) or S.is_hidden(total) or not S.values.get(total):
            return {'v': None, 'h': S.is_hidden(cell) or S.is_hidden(total)}
        return {'v': round(S.values[cell] * 100.0 / S.values[total], 1), 'h': False}

    @api.model
    def _reason_labels(self):
        return {'resigned': _('Resigned'), 'dismissed': _('Dismissed'),
                'retired': _('Retired'), 'other': _('Another reason'),
                'none': _('Reason not recorded')}

    @api.model
    def _service_labels(self):
        return {'u1': _('Under 1 year'), '1_2': _('1 to 2 years'), '2_5': _('2 to 5 years'),
                '5_10': _('5 to 10 years'), '10p': _('10 years or more'),
                'none': _('Start date not recorded')}

    @api.model
    def _age_labels(self):
        return {'u25': _('Under 25'), '25_34': _('25 to 34'), '35_44': _('35 to 44'),
                '45_54': _('45 to 54'), '55p': _('55 and over'), 'none': _('Birthday not recorded')}

    @api.model
    def _gender_labels(self):
        return {'female': _('Women'), 'male': _('Men'), 'other': _('Other'),
                'none': _('Not recorded')}

    @api.model
    def _few(self, n):
        if n <= 0:
            return ''
        if n < FLOOR:
            return _('fewer than 5')
        return str(n)

    @api.model
    def _data_notes(self, notes):
        out = []
        if notes.get('no_start'):
            out.append(_('%s people have no joining date or contract start: they count in every '
                         'month and never as joiners.', self._few(notes['no_start'])))
        if notes.get('no_end'):
            out.append(_('%s archived records have no leaving date and are left out.',
                         self._few(notes['no_end'])))
        return out

    @api.model
    def _scope_sentence(self, P):
        if len(P['companies']) > 1:
            return _('Across %s companies. A person who moves between two of them counts once: '
                     'not as a leaver or a joiner.', len(P['companies']))
        if len(P['visible']) > 1:
            return _('One company. A person who moves to another company of the group counts '
                     'as a leaver here, and as a joiner there.')
        return ''

    @api.model
    def _crosscheck(self, P):
        """"Paid last month, not this month, and no leaving date" — a count."""
        if 'hr.payslip' not in self.env or P['department_id']:
            return ''
        Slip = self.env['hr.payslip'].sudo()
        dom = [('company_id', 'in', P['companies']), ('state', 'in', ('done', 'paid'))]
        last = Slip.search(dom, order='date_to desc', limit=1)
        if not last or not last.date_to:
            return ''
        this_start = last.date_to.replace(day=1)
        prev_start = this_start - relativedelta(months=1)
        cur = set(Slip.search(dom + [('date_to', '>=', this_start)]).mapped('employee_id').ids)
        prev = Slip.search(dom + [('date_to', '>=', prev_start), ('date_to', '<', this_start)])
        gone = prev.mapped('employee_id').filtered(
            lambda e: e.id not in cur and not e.sudo().departure_date)
        if not gone:
            return ''
        return _('Check: %(n)s people were paid in %(prev)s but not in %(this)s, and have no '
                 'leaving date. If they left, add the leaving date so turnover counts them.',
                 n=self._few(len(gone)), prev=format_date(self.env, prev_start, date_format='MMMM y'),
                 this=format_date(self.env, this_start, date_format='MMMM y'))

    # ============================================================ download
    @api.model
    def export_xlsx(self, view, params=None):
        """The SAME suppressed payload, as a spreadsheet: hidden is hidden."""
        data = self.get_report(view, params)
        import xlsxwriter
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = book.add_worksheet(data['title'][:31])
        bold = book.add_format({'bold': True})
        hid = _('Hidden (small group)')

        def val(c):
            return hid if (c is None or c.get('h')) else (c.get('v') if c.get('v') is not None else '')
        r = 0
        for line in (data['title'], data['period'], data.get('scope_note') or '',
                     _('Groups of fewer than 5 people are hidden, and so is any figure that '
                       'would let someone work one out.')):
            if line:
                sheet.write(r, 0, line, bold if r == 0 else None)
                r += 1
        r += 1
        t = data['tiles']
        for label, c in ((_('Headcount at the end'), t['h_end']), (_('Average headcount'), t['avg']),
                         (_('Joiners'), t['j']), (_('Leavers'), t['l']), (_('Turnover %'), t['rate'])):
            sheet.write(r, 0, label)
            sheet.write(r, 1, val(c))
            r += 1
        r += 1

        def table(head, rows):
            nonlocal r
            for i, h in enumerate(head):
                sheet.write(r, i, h, bold)
            r += 1
            for row in rows:
                for i, v in enumerate(row):
                    sheet.write(r, i, v)
                r += 1
            r += 1
        if data.get('series') and data['view'] == 'headcount':
            table([_('Month'), _('Headcount')],
                  [[s['month'], val(s['h'])] for s in data['series']])
        if data.get('quarters'):
            table([_('Quarter'), _('Joiners'), _('Leavers'), _('Change')],
                  [[s['label'], val(s['j']), val(s['l']), val(s['net'])] for s in data['quarters']])
        if data.get('table') and data['table'].get('rows'):
            tb = data['table']
            table([_('Company') if tb['by'] == 'company' else _('Department'), _('Headcount'),
                   _('Joiners'), _('Leavers')],
                  [[x['name'], val(x['h']), val(x['j']), val(x['l'])] for x in tb['rows']] +
                  [[_('Total'), val(tb['total']['h']), val(tb['total']['j']), val(tb['total']['l'])]])
        if data.get('reasons'):
            table([_('Why they left'), _('People'), '%'],
                  [[x['label'], val(x['n']), val(x['pct'])] for x in data['reasons']])
        if data.get('genders'):
            table([_('Gender'), _('People'), '%'],
                  [[x['label'], val(x['n']), val(x['pct'])] for x in data['genders']])
        if data.get('ages'):
            table([_('Age'), _('People'), '%'],
                  [[x['label'], val(x['n']), val(x['pct'])] for x in data['ages']])
        if data.get('service_rows'):
            table([_('Length of service'), _('People'), '%'],
                  [[x['label'], val(x['n']), val(x['pct'])] for x in data['service_rows']])
        sheet.set_column(0, 0, 34)
        sheet.set_column(1, 6, 14)
        book.close()
        name = '%s.xlsx' % data['title']
        return {'name': name, 'data': base64.b64encode(buf.getvalue()).decode()}
