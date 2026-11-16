# -*- coding: utf-8 -*-
"""`pb.people.reports` — People › Insights › People reports.

Turnover, joiners against leavers, why people leave, age and gender, length
of service; by company, department and period, month by month.

OWNER RULINGS:
  * P6 — HR ONLY (`hr.group_hr_user`, from a group that is not a payroll
    group), for the companies they can already see (the company switcher,
    narrowed by "who sees what" — `pb.group.scoped`). The payroll team does
    NOT get gender, age or leaving reasons through this door.
  * PR1 (2026-11-17, REVERSES P6's small-group hiding for this screen): HR
    sees every figure — no group is hidden, on screen, in the totals or in
    the download. (Surveys keep their own 5+ rule; that is `pb_voice`.)
  * PR2 — a month-by-month line: headcount at each month end, joiners and
    leavers per month, grouped by quarter.
  * No money anywhere, so nothing is ever added across currencies.

NO STORED SNAPSHOT, NO JOB: every figure is worked out when the screen asks,
from the employee records and their version history, so there is nothing to
backfill, nothing pending, and installing schedules nothing. Reads never
write.

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

_logger = logging.getLogger(__name__)

HR_GROUP = 'hr.group_hr_user'
#: Groups from these modules do not count as "being HR" (they imply it).
PAYROLL_MODULES = ('om_hr_payroll', 'payroll_analytics_approval', 'pb_payroll_ai_insights')
VIEWS = ('headcount', 'movement', 'leaving', 'age_gender', 'service')
#: The sliding period beside the calendar years (PR1: it was dropped only
#: because two sliding windows could be subtracted under the hiding rule).
LAST12 = 'last12'
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


def rate(leavers, h0, h_end):
    """Turnover %: leavers ÷ the average of the start and end headcount."""
    avg = (h0 + h_end) / 2.0
    return round(leavers * 100.0 / avg, 1) if avg else None


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
        periods = self._periods()
        return {
            'allowed': True, 'why': '',
            'companies': [{'id': c.id, 'name': c.name or ''} for c in Company.browse(cids)],
            'departments': [{'id': d.id, 'name': d.complete_name or d.name or '',
                             'company_id': d.company_id.id} for d in depts],
            'periods': [{'key': str(k), 'label': lbl} for k, lbl in periods],
            'period': str(periods[0][0]),
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
                # a department is looked at inside its own company
                companies = [d.company_id.id]
        keys = [str(k) for k, _l in self._periods()]
        period = str(params.get('period') or params.get('year') or keys[0])
        period = period if period in keys else keys[0]
        last = self._last_month_end()
        if period == LAST12:
            first = last.replace(day=1) - relativedelta(months=11)
            ends = [month_end(first + relativedelta(months=i)) for i in range(12)]
        else:
            year = int(period)
            ends = [month_end(date(year, mo, 1)) for mo in range(1, 13)]
            ends = [d for d in ends if d <= last]
        return {'visible': list(visible), 'companies': companies, 'department_id': dept,
                'allowed_depts': allowed_depts, 'ends': ends, 'period': period,
                'start': ends[0].replace(day=1), 'end': ends[-1]}

    @api.model
    def _last_month_end(self):
        """The last COMPLETE month: a month still running would show a
        headcount that changes every day."""
        today = fields.Date.context_today(self)
        return today.replace(day=1) - timedelta(days=1)

    @api.model
    def _periods(self):
        """This year (once a month of it is complete), the last 12 months,
        and the four calendar years before."""
        last = self._last_month_end()
        out = []
        for y in range(last.year, last.year - 5, -1):
            if y == last.year and last.year == fields.Date.context_today(self).year:
                out.append((y, _('%s so far', y)))
            else:
                out.append((y, str(y)))
            if y == last.year:
                out.append((LAST12, _('Last 12 months')))
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
        return {'ends': ends, 'heads': heads, 'h0': h0, 'joins': joins, 'leaves': leaves,
                'at_end': at_end, 'leavers': leavers, 'joiners': joiners,
                'stretches': stretches}

    # ============================================================ figures
    @api.model
    def _breakdown(self, P, records, by, companies=None):
        """Rows of the company / department table: headcount at the start and
        the end, joiners, leavers — per company or department."""
        ends = P['ends']
        if by == 'company':
            rows = {}
            for cid in companies:
                m = self._measure([r for r in records if r['company_id'] == cid], ends,
                                  allowed_depts=P['allowed_depts'])
                rows[cid] = {'h0': m['h0'], 'h': m['heads'][-1],
                             'j': sum(m['joins']), 'l': sum(m['leaves'])}
            return rows
        m = self._measure(records, ends, allowed_depts=P['allowed_depts'])
        allowed = P['allowed_depts']
        acc = defaultdict(lambda: {'h0': 0, 'h': 0, 'j': 0, 'l': 0})
        day0 = P['start'] - timedelta(days=1)
        for key, day in (('h0', day0), ('h', ends[-1])):
            for st in m['stretches']:
                if st["start"] <= day < st["end"]:
                    d = self._dept_at(self._rec_at(st, day), day)
                    if allowed and d not in allowed:
                        continue
                    acc[d or 0][key] += 1
        for st in m['joiners']:
            acc[self._dept_at(st['start_rec'], st['start']) or 0]['j'] += 1
        for st in m['leavers']:
            acc[self._dept_at(st['end_rec'], st['end']) or 0]['l'] += 1
        return dict(acc)

    @api.model
    def _shared(self, P):
        """What every view shares: the people and the scope's measure."""
        records, notes = self._people_records(P['visible'])
        scope = [r for r in records if r['company_id'] in P['companies']]
        m = self._measure(scope, P['ends'], dept=P['department_id'] or None,
                          allowed_depts=P['allowed_depts'])
        return {'m': m, 'notes': notes, 'records': scope}

    # ============================================================ the views
    @api.model
    def get_report(self, view, params=None):
        self._require()
        if view not in VIEWS:
            view = 'headcount'
        P = self._params(params)
        B = self._shared(P)
        m = B['m']
        out = {
            'view': view,
            'title': self._view_labels()[view],
            'period': _('%(start)s to %(end)s', start=format_date(self.env, P['start']),
                        end=format_date(self.env, P['end'])),
            'scope_note': self._scope_sentence(P),
            'notes': self._data_notes(B['notes']),
            'tiles': self._tiles(m),
        }
        if view in ('headcount', 'movement'):
            out['months'], out['quarters'] = self._months(m)
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
    def _tiles(self, m):
        h0, h_end = m['h0'], m['heads'][-1]
        leavers = sum(m['leaves'])
        return {
            'h0': h0, 'h_end': h_end,
            'avg': round((h0 + h_end) / 2.0, 1),
            'j': sum(m['joins']), 'l': leavers,
            'rate': rate(leavers, h0, h_end),
        }

    @api.model
    def _months(self, m):
        """PR2 — the month-by-month line, and the quarters it groups into.

        Month: headcount at its last day, joiners and leavers in it, and the
        change. Quarter: its months' joiners and leavers, and the headcount
        at its last month in the period (a "last 12 months" period can start
        or end part-way through a quarter)."""
        months, quarters = [], []
        prev = m['h0']
        for i, day in enumerate(m['ends']):
            j, l, h = m['joins'][i], m['leaves'][i], m['heads'][i]
            qkey = (day.year, (day.month - 1) // 3)
            if not quarters or quarters[-1]['key'] != '%s-Q%s' % (qkey[0], qkey[1] + 1):
                quarters.append({'key': '%s-Q%s' % (qkey[0], qkey[1] + 1),
                                 'label': _('Q%(q)s %(year)s', q=qkey[1] + 1, year=qkey[0]),
                                 'h0': prev, 'j': 0, 'l': 0, 'h': h, 'months': []})
            q = quarters[-1]
            months.append({
                'key': day.strftime('%Y-%m'),
                'label': format_date(self.env, day, date_format='MMM y'),
                'short': format_date(self.env, day, date_format='MMM'),
                'h': h, 'j': j, 'l': l, 'net': h - prev, 'quarter': q['key'],
            })
            q['j'] += j
            q['l'] += l
            q['h'] = h
            q['months'].append(len(months) - 1)
            prev = h
        for q in quarters:
            q['net'] = q['h'] - q['h0']
        return months, quarters

    @api.model
    def _group_table(self, P, B):
        by = 'company' if len(P['companies']) > 1 else 'department'
        if P['department_id']:
            return {'by': by, 'rows': [], 'skipped': True}
        rows = self._breakdown(P, B['records'], by, companies=P['companies'])
        if by == 'company':
            names = {c.id: c.name for c in self.env['res.company'].sudo().browse(list(rows))}
        else:
            names = {d.id: d.name for d in self.env['hr.department'].sudo().browse(
                [k for k in rows if k])}
        out_rows = [{
            'name': names.get(key) or _('No department'),
            'h0': r['h0'], 'h': r['h'], 'j': r['j'], 'l': r['l'],
            'rate': rate(r['l'], r['h0'], r['h']),
        } for key, r in rows.items()]
        out_rows.sort(key=lambda x: x['name'] or '')
        # the total row IS the tiles (same figures)
        t = self._tiles(B['m'])
        return {'by': by, 'rows': out_rows,
                'total': {'h0': t['h0'], 'h': t['h_end'], 'j': t['j'], 'l': t['l'],
                          'rate': t['rate']}}

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
    def _cat_rows(self, P, B, which, labels):
        """One breakdown (why they left, age bands, ...) of the scope — a
        company, the group, or one department (PR1: per department again)."""
        m = B['m']
        counts = self._cat_counts(m, which, P['ends'][-1])
        total = len(m['leavers']) if which in ('reason', 'leave_service') else len(m['at_end'])
        rows = [{'key': k, 'label': labels[k], 'n': counts.get(k, 0),
                 'pct': round(counts.get(k, 0) * 100.0 / total, 1) if total else None}
                for k in self._cat_keys(which)]
        return total, rows

    @api.model
    def _leaving(self, P, B):
        total, reasons = self._cat_rows(P, B, 'reason', self._reason_labels())
        _t2, service = self._cat_rows(P, B, 'leave_service', self._service_labels())
        return {
            'total': total, 'reasons': reasons, 'service_rows': service,
            'voluntary_note': _('Resigned counts as leaving by choice. Dismissed and retired do not.'),
        }

    @api.model
    def _age_gender(self, P, B):
        total, genders = self._cat_rows(P, B, 'gender', self._gender_labels())
        _t2, ages = self._cat_rows(P, B, 'age', self._age_labels())
        return {'total': total, 'genders': genders, 'ages': ages}

    @api.model
    def _service(self, P, B):
        total, rows = self._cat_rows(P, B, 'service', self._service_labels())
        return {'total': total, 'service_rows': rows}

    # ============================================================ helpers
    @staticmethod
    def _band(value, bands):
        for key, lo, hi in bands:
            if lo <= value < hi:
                return key
        return bands[-1][0]

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
    def _data_notes(self, notes):
        out = []
        if notes.get('no_start'):
            out.append(_('%s people have no joining date or contract start: they count in every '
                         'month and never as joiners.', notes['no_start']))
        if notes.get('no_end'):
            out.append(_('%s archived records have no leaving date and are left out.',
                         notes['no_end']))
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
                 n=len(gone), prev=format_date(self.env, prev_start, date_format='MMMM y'),
                 this=format_date(self.env, this_start, date_format='MMMM y'))

    # ============================================================ download
    @api.model
    def export_xlsx(self, view, params=None):
        """The SAME payload as the screen, as a spreadsheet."""
        data = self.get_report(view, params)
        import xlsxwriter
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = book.add_worksheet(data['title'][:31])
        bold = book.add_format({'bold': True})

        def val(v):
            return '' if v is None else v
        r = 0
        for line in (data['title'], data['period'], data.get('scope_note') or ''):
            if line:
                sheet.write(r, 0, line, bold if r == 0 else None)
                r += 1
        r += 1
        t = data['tiles']
        for label, v in ((_('Headcount at the start'), t['h0']),
                         (_('Headcount at the end'), t['h_end']),
                         (_('Average headcount'), t['avg']),
                         (_('Joiners'), t['j']), (_('Leavers'), t['l']),
                         (_('Turnover %'), t['rate'])):
            sheet.write(r, 0, label)
            sheet.write(r, 1, val(v))
            r += 1
        r += 1

        def table(head, rows, bold_rows=()):
            """`rows`: lists of cells; the indexes in `bold_rows` are totals."""
            nonlocal r
            for i, h in enumerate(head):
                sheet.write(r, i, h, bold)
            r += 1
            for n, row in enumerate(rows):
                for i, v in enumerate(row):
                    sheet.write(r, i, v, bold if n in bold_rows else None)
                r += 1
            r += 1
        if data.get('months'):
            lines, totals = [], set()
            for q in data['quarters']:
                for i in q['months']:
                    mo = data['months'][i]
                    lines.append([mo['label'], mo['h'], mo['j'], mo['l'], mo['net']])
                totals.add(len(lines))
                lines.append([q['label'], q['h'], q['j'], q['l'], q['net']])
            table([_('Month'), _('Headcount at the month end'), _('Joiners'), _('Leavers'),
                   _('Change')], lines, bold_rows=totals)
        if data.get('table') and data['table'].get('rows'):
            tb = data['table']
            table([_('Company') if tb['by'] == 'company' else _('Department'),
                   _('Headcount at the start'), _('Headcount at the end'),
                   _('Joiners'), _('Leavers'), _('Turnover %')],
                  [[x['name'], x['h0'], x['h'], x['j'], x['l'], val(x['rate'])]
                   for x in tb['rows']] +
                  [[_('Total'), tb['total']['h0'], tb['total']['h'], tb['total']['j'],
                    tb['total']['l'], val(tb['total']['rate'])]],
                  bold_rows={len(tb['rows'])})
        heads = {
            'reasons': _('Why they left'),
            'genders': _('Gender'),
            'ages': _('Age'),
            'service_rows': _('Length of service'),
        }
        for key in ('reasons', 'genders', 'ages', 'service_rows'):
            if data.get(key):
                table([heads[key], _('People'), '%'],
                      [[x['label'], x['n'], val(x['pct'])] for x in data[key]])
        sheet.set_column(0, 0, 34)
        sheet.set_column(1, 6, 16)
        book.close()
        name = '%s.xlsx' % data['title']
        return {'name': name, 'data': base64.b64encode(buf.getvalue()).decode()}
