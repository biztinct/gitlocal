# -*- coding: utf-8 -*-
"""UPDATES P4 — the Updates screens for leave opening balances (D18), and
the Attendance and timesheets tile (D17).

The same four steps as every other sheet (Start → Match columns → Review →
Apply), on a third kind of sheet: one row per person, one group of columns
per leave type that keeps a balance, one "balances as at" date for the whole
sheet. What this file adds is only what that sheet needs; finding people,
reading the file and the approval route are the Records Desk's own.

A cell's verdict lives in ONE place, `_leave_cell`; the review, an on-screen
fix, Apply and the write on approval (`_leave_row_check`) all ask it, so the
screen and the server never disagree:

  * new                 — a balance for a leave type the person can have;
  * same                — exactly the opening balance already set;
  * refused             — already set to something else, an allocation
                          already covers the date, waiting in another update,
                          not a number, negative, too large, a unit the leave
                          type does not take, a leave type not offered to the
                          person, or the absence policy cannot take it;
  * not used            — "carried" / "taken" for somebody who is not on an
                          absence policy (greyed and skipped).

Loaded last (models/__init__.py); constants come from `updates_leave` and
`updates_desk`, never the other way round (ledger G21).
"""
import base64
import difflib
import io
import json
import re
from datetime import date, timedelta

from odoo import _, api, fields, models

from odoo.addons.pb_records.models.pb_records_io import (
    _norm, XLSX_MIME, IDENTITY_COLS, ID_RE, META_SHEET, MAX_ROWS)
from odoo.addons.pb_records.models.records_approval import RECORDS_PROCESS_KEY
from odoo.addons.pb_updates.models.updates_desk import (
    GUESS_RATIO, IDENTITY_KEYS, product_label)
from odoo.addons.pb_updates.models.updates_batch import heading_fingerprint
from odoo.addons.pb_updates.models.updates_leave import (
    GROUP, HOURS_DEFAULT, LIVE, MANAGER, MAX_DAYS, PARTS, PREFIX, REACH_BACK_DAYS, SENDER,
    card_id, day_label, number_text, parse_card)

#: The hidden sheet's cell that says which date a sheet's balances are as at.
DATE_KEY = 'leave_date'
#: Words a typed number may carry ("12 days", "7.5 h", "12 ngày").
UNIT_WORDS = re.compile(r'(days?|hours?|hrs?|h|d|ngày|ngay|giờ|gio|hari|jam)\.?$', re.I)
#: The Attendance and timesheets tile: the existing attendance file screen,
#: by the doors it is reachable through today (first found wins).
ATTENDANCE_DOORS = (
    ('pb_mission.action_pb_workforce', {'pb_shell_lens': 'time', 'pb_lens': 'import'}),
    ('pb_time_hub.action_pb_time_hub', {'pb_lens': 'import'}),
)
ATTENDANCE_GROUP = 'hr_attendance.group_hr_attendance_officer'


class PbUpdatesLeaveDesk(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # =================================================================
    # Gates, date, words
    # =================================================================
    @api.model
    def _leave_may_set(self):
        """Who may SEND leave balances (owner D23, 2026-11-13): an HR
        officer — the role that can check a sheet — or a Time Off
        administrator. The approval route still decides whether it goes in;
        an officer's approved balances are written as `updates_leave`
        describes."""
        try:
            user = self.env.user
            return bool(user._is_superuser() or user.has_group(SENDER)
                        or user.has_group(MANAGER))
        except Exception:   # noqa: BLE001 — a missing group is a "no"
            return False

    @api.model
    def _leave_may_undo(self):
        """Who may UNDO leave balances: a Time Off administrator only (P4,
        unchanged by D23) — the right that may refuse any allocation."""
        try:
            user = self.env.user
            return bool(user._is_superuser() or user.has_group(MANAGER))
        except Exception:   # noqa: BLE001 — a missing group is a "no"
            return False

    @api.model
    def _leave_own_people(self, sender):
        """The employee records of `sender` when that sender is not a Time
        Off administrator (D23 rail: only an administrator sets their own
        balance, the native Time Off rule). Empty for an administrator or no
        sender."""
        if not sender or sender._is_superuser() or sender.has_group(MANAGER):
            return frozenset()
        return frozenset(sender.sudo().with_context(active_test=False).employee_ids.ids)

    @api.model
    def _leave_today(self):
        return self.env['pb.records.apply']._today_for()

    @api.model
    def _leave_cutover(self, value):
        """`(date or None, refusal)` — the "balances as at" date: today or
        earlier, at most a year back."""
        try:
            day = fields.Date.to_date(value) if value else None
        except (TypeError, ValueError):
            day = None
        if not day:
            return None, _("Pick the date these balances are as at.")
        today = self._leave_today()
        if day > today:
            return None, _("Balances can be as at today or an earlier date, not a future one.")
        if day < today - timedelta(days=REACH_BACK_DAYS):
            return None, _("Pick a date within the last year. %s is too far back.") % \
                day_label(self.env, day)
        return day, ''

    @api.model
    def _unit_word(self, unit):
        return _("hours") if unit == 'hour' else _("days")

    @api.model
    def _part_label(self, type_name, part, unit='day'):
        if part == 'carry':
            return _("%s · carried from last year") % type_name
        if part == 'taken':
            return _("%s · already taken this year") % type_name
        return (_("%s · hours available") if unit == 'hour' else _("%s · days available")) % type_name

    # =================================================================
    # Leave types and people (read only)
    # =================================================================
    @api.model
    def _leave_types(self, company_ids=None):
        """Leave types that keep a balance and are offered in these
        companies (the ones the Time Off screen counts balances for)."""
        company_ids = list(company_ids or self.env.companies.ids)
        types = self.env['hr.leave.type'].sudo().search([
            ('requires_allocation', '=', True),
            '|', ('company_id', '=', False), ('company_id', 'in', company_ids)],
            order='sequence, name, id')
        policy_fields = 'pb_policy_category' in types._fields
        out = {}
        for t in types:
            policy_country = (t.pb_policy_country_id.code or '') if policy_fields else ''
            out[t.id] = {
                'id': t.id, 'name': t.name or '', 'unit': t.request_unit or 'day',
                'company_id': t.company_id.id or 0,
                'country': policy_country or (t.country_id.code or ''),
                'policy_country': policy_country,
                'category': (t.pb_policy_category or '') if policy_fields else '',
            }
        return out

    @api.model
    def _leave_edition_for(self, employee, on_date):
        """The published absence policy edition that covers `employee` on
        `on_date` (the person's assigned family, company and country), or an
        empty recordset. Read only; the same search the policy layer makes."""
        if 'pb.leave.policy.edition' not in self.env or not on_date:
            return None
        employee = employee.sudo()
        assigned = employee.pb_leave_policy_id if 'pb_leave_policy_id' in employee._fields else False
        if not assigned:
            return self.env['pb.leave.policy.edition'].browse()
        return self.env['pb.leave.policy.edition'].sudo().search([
            ('code', '=', assigned.code), ('company_id', '=', employee.company_id.id),
            ('country_id', '=', assigned.country_id.id), ('state', '=', 'published'),
            ('effective_from', '<=', on_date), '|', ('effective_to', '=', False),
            ('effective_to', '>=', on_date)], limit=1)

    @api.model
    def _leave_people(self, emp_ids, cutover):
        """`{emp_id: {...}}` — company, country (the Time Off screen's rule:
        absence policy, else payroll country, else the company's), and the
        absence policy that covers the date."""
        emps = self.env['hr.employee'].sudo().browse(sorted(set(emp_ids or []))).exists()
        has_policy = 'pb_leave_policy_id' in emps._fields
        editions = {}
        out = {}
        for emp in emps:
            assigned = emp.pb_leave_policy_id if has_policy else False
            if assigned and assigned.country_id:
                country = assigned.country_id.code or ''
            elif 'payroll_country' in emp._fields and emp.payroll_country:
                country = emp.payroll_country
            else:
                country = emp.company_id.country_id.code or ''
            edition = None
            if assigned:
                key = (assigned.code, emp.company_id.id, assigned.country_id.id)
                if key not in editions:
                    editions[key] = self._leave_edition_for(emp, cutover)
                edition = editions[key]
            out[emp.id] = {
                'id': emp.id, 'name': emp.name or '', 'company_id': emp.company_id.id,
                'company': emp.company_id.name or '', 'country': country,
                'policy': bool(assigned),
                'family_from': (assigned.effective_from if assigned else None),
                'edition': edition or None,
                'full_time': bool(emp.pb_policy_full_time_confirmed) if has_policy else False,
                '_record': emp,
            }
        return out

    @api.model
    def _leave_hours_per_day(self, person, cutover):
        if 'hours' not in person:
            try:
                person['hours'] = person['_record']._get_hours_per_day(cutover) or HOURS_DEFAULT
            except Exception:   # noqa: BLE001
                person['hours'] = HOURS_DEFAULT
        return person['hours']

    @api.model
    def _leave_existing(self, emp_ids, type_ids, cutover, skip_line_ids=()):
        """What already stands, per (person, leave type):

        `openings` — an opening balance (a policy posting of kind "opening",
        or a balance this sheet set that is still in place); `waiting` — a
        balance waiting for approval in another update; `covers` — other
        allocations still valid on or after the date (not refused)."""
        emp_ids, type_ids = list(emp_ids or []), list(type_ids or [])
        openings, waiting, covers = {}, {}, {}
        if not emp_ids or not type_ids:
            return {'openings': openings, 'waiting': waiting, 'covers': covers}
        own_allocs = set()
        if 'pb.leave.policy.posting' in self.env:
            for p in self.env['pb.leave.policy.posting'].sudo().search([
                    ('employee_id', 'in', emp_ids), ('leave_type_id', 'in', type_ids),
                    ('kind', '=', 'opening')], order='id'):
                openings[(p.employee_id.id, p.leave_type_id.id)] = {
                    'days': p.days, 'carried': p.opening_carried_days, 'taken': p.opening_taken_days,
                    'date': p.cutover_date, 'policy': True, 'batch': '', 'line': None}
                if p.allocation_id:
                    own_allocs.add(p.allocation_id.id)
        Line = self.env['pb.updates.leave.line'].sudo()
        for line in Line.search([('employee_id', 'in', emp_ids), ('leave_type_id', 'in', type_ids),
                                 ('state', 'in', LIVE), ('id', 'not in', list(skip_line_ids or []))],
                                order='id'):
            key = (line.employee_id.id, line.leave_type_id.id)
            if line.allocation_id:
                own_allocs.add(line.allocation_id.id)
            if line.state == 'waiting':
                waiting[key] = line
                continue
            alive = line.way == 'policy' or (line.allocation_id.exists()
                                             and line.allocation_id.state != 'refuse')
            if alive and key not in openings:
                openings[key] = {'days': line.available, 'carried': line.carried,
                                 'taken': line.taken, 'date': line.cutover_date,
                                 'policy': line.way == 'policy',
                                 'batch': line.batch_id.name or '', 'line': line}
        for alloc in self.env['hr.leave.allocation'].sudo().search([
                ('employee_id', 'in', emp_ids), ('holiday_status_id', 'in', type_ids),
                ('state', '!=', 'refuse'),
                '|', ('date_to', '=', False), ('date_to', '>=', cutover)], order='date_from, id'):
            if alloc.id in own_allocs:
                continue
            covers.setdefault((alloc.employee_id.id, alloc.holiday_status_id.id), []).append(
                (alloc.date_from, alloc.date_to))
        return {'openings': openings, 'waiting': waiting, 'covers': covers}

    @api.model
    def _leave_ctx(self, emp_ids, cutover, type_ids=None, skip_line_ids=(), sender=None):
        """`sender`: the person sending (review, recheck, apply: the user on
        the screen; on approval: the HR officer whose sheet is written), for
        the own-balance rail; None = no such rail."""
        people = self._leave_people(emp_ids, cutover)
        companies = sorted({p['company_id'] for p in people.values()} | set(self.env.companies.ids))
        types = self._leave_types(companies)
        if type_ids is not None:
            wanted = {int(t) for t in type_ids}
            types = {k: v for k, v in types.items() if k in wanted}
        existing = self._leave_existing(list(people), list(types), cutover, skip_line_ids)
        return dict(existing, people=people, types=types, cutover=cutover,
                    own=self._leave_own_people(sender))

    # =================================================================
    # One cell's verdict
    # =================================================================
    @api.model
    def _leave_number(self, raw):
        """A typed number of days or hours, or None."""
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw or '').strip().lower()
        text = UNIT_WORDS.sub('', text).strip()
        if not text:
            return None
        if re.fullmatch(r'\d{1,3}(,\d{3})+(\.\d+)?', text):
            text = text.replace(',', '')
        elif re.fullmatch(r'-?\d+,\d+', text):
            text = text.replace(',', '.')
        try:
            return float(text)
        except ValueError:
            return None

    @api.model
    def _leave_cell(self, ctx, emp_id, type_id, part, raw, clear_words=frozenset()):
        """The verdict of one cell — the only one there is."""
        cutover = ctx['cutover']
        t = ctx['types'].get(type_id)
        person = ctx['people'].get(emp_id)
        text = '' if raw is None else (number_text(raw) if isinstance(raw, (int, float))
                                       and not isinstance(raw, bool) else str(raw))
        out = {'status': 'ok', 'old': '', 'new': text, 'value': raw, 'why': '',
               'amount': 0.0, 'role': part, 'cleared': False, 'unit': (t or {}).get('unit', 'day')}

        def refuse(why):
            out.update(status='refused', why=why)
            return out

        def not_used(why):
            out.update(status='off_scheme', why=why)
            return out

        if not person:
            return refuse(_("This person could not be found any more."))
        who = person['name'] or _("This person")
        if not t:
            return refuse(_("This leave type does not keep a balance, or is not offered in "
                            "%s.") % (person['company'] or _("this company")))
        name, unit = t['name'], t['unit']
        if t['company_id'] and t['company_id'] != person['company_id']:
            return refuse(_("%(type)s is not offered in %(company)s, where %(who)s works.",
                            type=name, company=person['company'], who=who))
        if t['country'] and person['country'] and t['country'] != person['country']:
            return refuse(_("%(type)s is for employees in another country.", type=name))
        if emp_id in ctx.get('own', ()):
            return refuse(_("%(who)s cannot set their own leave balance. Ask a Time Off "
                            "administrator or another HR officer to send it.", who=who))
        if part != 'avail' and not person['policy']:
            return not_used(_("Carried and taken days are only kept for people on an absence "
                              "policy. %s is not on one, so this is left out.") % who)
        if person['policy']:
            edition = person['edition']
            if t['category'] != 'annual':
                why = _("%(who)s is on an absence policy: only its annual leave opening "
                        "balance can be set here.", who=who)
                return refuse(why) if part == 'avail' else not_used(why)
            if not edition:
                start = person.get('family_from')
                return refuse(_("%(who)s's absence policy does not cover %(date)s. Pick a "
                                "\"balances as at\" date from %(start)s.", who=who,
                                date=day_label(self.env, cutover),
                                start=day_label(self.env, start) if start else '?'))
            if edition.full_time_only and not person['full_time']:
                return refuse(_("%(who)s's full-time eligibility for the absence policy has not "
                                "been confirmed yet, so it cannot take an opening balance.",
                                who=who))
            if t['policy_country'] and t['policy_country'] != (edition.country_id.code or ''):
                return refuse(_("%(type)s is for employees in another country.", type=name))
            if unit == 'hour':
                return refuse(_("The absence policy keeps balances in days, and %(type)s is "
                                "counted in hours.", type=name))
        elif t['category']:
            return refuse(_("%(type)s belongs to an absence policy, and %(who)s is not on it. "
                            "Put %(who)s on the policy first.", type=name, who=who))
        key = (emp_id, type_id)
        line = ctx['waiting'].get(key)
        if line:
            return refuse(_("%(who)s's %(type)s balance is already waiting for approval in "
                            "“%(batch)s”.", who=who, type=name, batch=line.batch_id.name or ''))
        opening = ctx['openings'].get(key)
        if opening:
            have = {'avail': opening['days'], 'carry': opening['carried'],
                    'taken': opening['taken']}[part]
            out['old'] = self.env['pb.updates.leave.line']._qty_label(have, unit)
        if isinstance(raw, str) and raw.strip().lower() in clear_words:
            return refuse(_("A leave balance cannot be cleared from a sheet. To take one "
                            "back, undo the update that set it."))
        n = self._leave_number(raw)
        if n is None:
            return refuse(_("'%(text)s' is not a number of %(unit)s. Type a number, like 12.",
                            text=text, unit=self._unit_word(unit)))
        if n < 0:
            return refuse(_("A balance cannot be negative."))
        whole = abs(n * (2 if unit == 'half_day' else 1) - round(n * (2 if unit == 'half_day' else 1)))
        if unit == 'day' and whole > 1e-9:
            return refuse(_("%(type)s is taken in whole days, so this must be a whole number "
                            "of days, like 12.", type=name))
        if unit == 'half_day' and whole > 1e-9:
            return refuse(_("%(type)s is taken in half days, so this must be a whole or half "
                            "number, like 12.5.", type=name))
        if unit == 'hour' and abs(n * 100 - round(n * 100)) > 1e-6:
            return refuse(_("Use hours with at most two decimals, like 7.5."))
        cap = MAX_DAYS
        if unit == 'hour':
            cap = MAX_DAYS * self._leave_hours_per_day(person, cutover)
        if n > cap + 1e-9:
            return refuse(_("That is more than a year of leave (365 days). Check the number."))
        if part == 'avail' and n == 0:
            return refuse(_("A balance of 0 sets nothing. Leave the cell blank."))
        if part == 'carry' and person['policy'] and n > (person['edition'].carry_cap or 0) + 1e-9:
            return refuse(_("Under %(who)s's absence policy at most %(cap)s days can be "
                            "carried from last year.", who=who,
                            cap=number_text(person['edition'].carry_cap)))
        out['amount'] = n
        out['new'] = self.env['pb.updates.leave.line']._qty_label(n, unit)
        if opening:
            have = {'avail': opening['days'], 'carry': opening['carried'],
                    'taken': opening['taken']}[part]
            if round(have, 2) == round(n, 2):
                out.update(status='same', new=out['old'])
                return out
            if part != 'avail':
                return refuse(_("%(who)s's opening balance for %(type)s is already set, with "
                                "%(have)s here. It cannot be changed.", who=who, type=name,
                                have=out['old']))
            if opening['policy']:
                return refuse(_("%(who)s already has an opening balance of %(have)s for %(type)s, "
                                "set through the absence policy on %(date)s. It cannot be "
                                "replaced.", who=who, have=out['old'], type=name,
                                date=day_label(self.env, opening['date'])))
            return refuse(_("%(who)s already has an opening balance of %(have)s for %(type)s. "
                            "Undo that update first.", who=who, have=out['old'], type=name))
        covers = ctx['covers'].get(key) or []
        if person['policy']:
            year_end = date(cutover.year, 12, 31)
            covers = [c for c in covers if c[0] and c[0] <= year_end]
        if covers:
            start = covers[0][0]
            return refuse(_("%(who)s already has %(type)s days from %(date)s; an opening "
                            "balance cannot be added on top.", who=who, type=name,
                            date=day_label(self.env, start)))
        return out

    @api.model
    def _leave_row_check(self, row, sender=None):
        """At write time: the same verdict as the review, read fresh, for a
        waiting row. '' when it can still be written, else the sentence.
        `sender`: the HR officer whose sheet is being written (D23), or None."""
        row = row.sudo()
        ctx = self._leave_ctx([row.employee_id.id], row.cutover_date, [row.leave_type_id.id],
                              skip_line_ids=[row.id], sender=sender)
        person = ctx['people'].get(row.employee_id.id)
        if not person:
            return _("This person is no longer on record.")
        way = 'policy' if person['policy'] else 'allocation'
        if way != row.way:
            return _("%(who)s was put on an absence policy, or taken off one, after this was "
                     "sent. Send the balance again.", who=person['name'])
        parts = [('avail', row.available)]
        if row.way == 'policy':
            parts += [('carry', row.carried), ('taken', row.taken)]
        for part, value in parts:
            cell = self._leave_cell(ctx, row.employee_id.id, row.leave_type_id.id, part, value)
            if cell['status'] == 'same' and part == 'avail':
                return _("%(who)s already has this opening balance for %(type)s. Nothing was "
                         "added on top.", who=person['name'], type=row.type_name or '')
            if cell['status'] not in ('ok', 'same'):
                return cell['why'] or _("Something changed since this was sent.")
        return ''

    # =================================================================
    # The catalogue: cards per leave type
    # =================================================================
    @api.model
    def _leave_catalogue(self, type_ids=None, with_policy=None):
        """`{'cards': {card id: card}, 'types': {...}}` for the leave types
        offered in the companies in use. "Carried" and "taken" cards only for
        annual leave types of an absence policy (and only when somebody is on
        one, `with_policy`)."""
        types = self._leave_types()
        # Only the leave types somebody here can have (the Start screen's
        # list): a Belgian or Saudi stock leave type is not a place to send
        # a column for a Vietnamese team.
        countries = self._leave_home_countries()
        types = {k: t for k, t in types.items() if not t['country'] or t['country'] in countries}
        if type_ids is not None:
            wanted = {int(t) for t in type_ids}
            types = {k: v for k, v in types.items() if k in wanted}
        if with_policy is None:
            with_policy = self._leave_policy_people() > 0
        cards = {}
        for t in types.values():
            for part in PARTS:
                if part != 'avail' and not (with_policy and t['category'] == 'annual'):
                    continue
                fid = card_id(t['id'], part)
                cards[fid] = {'id': fid, 'label': self._part_label(t['name'], part, t['unit']),
                              'group': '%s_%s' % (GROUP, part), 'type_id': t['id'],
                              'part': part, 'unit': t['unit'], 'type_name': t['name'],
                              'ttype': 'float', 'editable': True, 'locked': False}
        return {'cards': cards, 'types': types}

    @api.model
    def _leave_topics(self, cat):
        labels = {'avail': _("Days available"), 'carry': _("Carried from last year"),
                  'taken': _("Already taken this year")}
        out = []
        for part in PARTS:
            fields_ = [dict(c) for c in cat['cards'].values() if c['part'] == part]
            if not fields_:
                continue
            out.append({'key': '%s_%s' % (GROUP, part), 'label': labels[part],
                        'icon': 'calendarRange', 'count': len(fields_),
                        'field_ids': [f['id'] for f in fields_], 'fields': fields_,
                        'examples': [f['label'] for f in fields_][:3], 'locked': False})
        return out

    @api.model
    def _leave_policy_people(self):
        """How many active people of the companies in use are on an absence
        policy (0 where the policy layer is not installed)."""
        Emp = self.env['hr.employee'].sudo()
        if 'pb_leave_policy_id' not in Emp._fields:
            return 0
        return Emp.search_count([('company_id', 'in', self.env.companies.ids),
                                 ('pb_leave_policy_id', '!=', False)])

    # =================================================================
    # Home: what the Start screen needs
    # =================================================================
    @api.model
    def _leave_home_countries(self):
        """Every country the people of the companies in use work in (the Time
        Off screen's rule, read in bulk): absence policy, payroll country,
        company. '' stands for "not known"."""
        Emp = self.env['hr.employee'].sudo()
        companies = self.env.companies
        found = set(c.country_id.code or '' for c in companies)
        domain = [('company_id', 'in', companies.ids)]
        if 'payroll_country' in Emp._fields:
            for value, _n in Emp._read_group(domain, ['payroll_country'], ['__count']):
                if value:
                    found.add(value)
        if 'pb_leave_policy_id' in Emp._fields:
            for edition, _n in Emp._read_group(domain + [('pb_leave_policy_id', '!=', False)],
                                               ['pb_leave_policy_id'], ['__count']):
                found.add(edition.sudo().country_id.code or '')
        return found

    @api.model
    def _leave_home(self):
        types = self._leave_types()
        countries = self._leave_home_countries()
        types = {k: t for k, t in types.items() if not t['country'] or t['country'] in countries}
        in_use = {}
        if types:
            groups = self.env['hr.leave.allocation'].sudo()._read_group(
                [('holiday_status_id', 'in', list(types)), ('state', '=', 'validate'),
                 ('employee_id.company_id', 'in', self.env.companies.ids)],
                ['holiday_status_id'], ['__count'])
            in_use = {t.id: n for t, n in groups}
        policy_people = self._leave_policy_people()
        today = self._leave_today()
        rows = []
        for t in types.values():
            rows.append({'id': t['id'], 'name': t['name'], 'unit': t['unit'],
                         'in_use': in_use.get(t['id'], 0),
                         'policy': t['category'] == 'annual' and policy_people > 0,
                         'managed': bool(t['category'])})
        rows.sort(key=lambda r: (-r['in_use'], r['name'].lower()))
        return {
            'available': bool(rows), 'may_set': self._leave_may_set(), 'types': rows,
            'policy_people': policy_people,
            'today': fields.Date.to_string(today),
            'min': fields.Date.to_string(today - timedelta(days=REACH_BACK_DAYS)),
        }

    @api.model
    def _attendance_installed(self):
        return 'pb.attendance.import.wizard' in self.env

    @api.model
    def _attendance_door(self):
        """D17: the tile that opens the existing attendance file screen —
        only where it is installed and the person may open it (the screen's
        own gate: the attendance officer tier). No new right."""
        if not self._attendance_installed():
            return {'available': False}
        try:
            allowed = self.env.user.has_group(ATTENDANCE_GROUP)
        except Exception:   # noqa: BLE001
            allowed = False
        if not allowed:
            return {'available': False}
        for xmlid, context in ATTENDANCE_DOORS:
            if self.env.ref(xmlid, raise_if_not_found=False):
                return {'available': True, 'action': xmlid, 'context': context}
        return {'available': False}

    @api.model
    def get_home(self):
        answer = super().get_home()
        try:
            answer['leave'] = self._leave_home()
        except Exception:   # noqa: BLE001 — a tile never blocks the home
            answer['leave'] = {'available': False, 'may_set': False, 'types': []}
        answer['attendance'] = self._attendance_door()
        return answer

    # =================================================================
    # Download the sheet
    # =================================================================
    @api.model
    def download_leave_sheet(self, cutover=None, type_ids=None, filters=None):
        """People × the leave types picked: "days available" for every type,
        "carried" and "taken" for an absence policy's annual leave; a balance
        already set is filled in and grey; a "Read me" sheet."""
        desk = self._gate()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading a sheet needs permission to export employee "
                "records. Ask an administrator, or upload a file of your own.")}
        cutover, refusal = self._leave_cutover(cutover)
        if refusal:
            return {'ok': False, 'msg': refusal}
        import openpyxl
        from openpyxl.comments import Comment
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        people = desk._matching(filters or {}, ctx={})
        total = len(people)
        people = people[:MAX_ROWS]
        ctx = self._leave_ctx(people.ids, cutover)
        offered = {}
        for p in ctx['people'].values():
            for t in ctx['types'].values():
                if t['company_id'] and t['company_id'] != p['company_id']:
                    continue
                if t['country'] and p['country'] and t['country'] != p['country']:
                    continue
                offered[t['id']] = True
        wanted = [int(t) for t in (type_ids or []) if str(t).isdigit() or isinstance(t, int)]
        types = [t for t in ctx['types'].values() if t['id'] in offered
                 and (not wanted or t['id'] in wanted)]
        if not types:
            return {'ok': False, 'msg': _(
                "None of the leave types you picked keeps a balance for these people. Pick "
                "another leave type.") if wanted else _(
                "No leave type keeps a balance here yet. Set one up on the Time Off screen "
                "first.")}
        any_policy = any(p['policy'] for p in ctx['people'].values())
        cards = []
        for t in types:
            for part in PARTS:
                if part != 'avail' and not (any_policy and t['category'] == 'annual'):
                    continue
                cards.append({'id': card_id(t['id'], part), 'type': t, 'part': part,
                              'label': self._part_label(t['name'], part, t['unit'])})
        Line = self.env['pb.updates.leave.line']
        when = day_label(self.env, cutover)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Records'
        bold = Font(bold=True, color='241F52')
        id_fill = PatternFill('solid', fgColor='EEF2F6')
        head_fill = PatternFill('solid', fgColor='EEEBFA')
        grey = PatternFill('solid', fgColor='EEEEF2')
        set_fill = PatternFill('solid', fgColor='E4E1F2')
        set_font = Font(color='6B6890')
        for idx, (_key, head) in enumerate(IDENTITY_COLS, start=1):
            cell = ws.cell(row=1, column=idx, value=_(head))
            cell.font, cell.fill = bold, id_fill
            cell.comment = Comment(_("Identity — used to match the row to a person. "
                                     "It is never imported."), product_label(self.env))
            ws.column_dimensions[get_column_letter(idx)].width = max(16, len(head) + 6)
        first = len(IDENTITY_COLS) + 1
        for offset, card in enumerate(cards):
            col = first + offset
            cell = ws.cell(row=1, column=col, value=card['label'])
            cell.font, cell.fill = bold, head_fill
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            cell.comment = Comment('id: %s\n%s' % (card['id'], _("Balances as at %s") % when),
                                   product_label(self.env))
            ws.column_dimensions[get_column_letter(col)].width = max(16, min(40, len(card['label']) + 4))
        for r, emp in enumerate(people, start=2):
            ws.cell(row=r, column=1, value=emp.barcode or emp.employee_id or '')
            ws.cell(row=r, column=2, value=emp.display_name or emp.name or '')
            ws.cell(row=r, column=3, value=emp.work_email or '')
            p = ctx['people'].get(emp.id)
            for offset, card in enumerate(cards):
                cell = ws.cell(row=r, column=first + offset)
                t = card['type']
                if not p or (t['company_id'] and t['company_id'] != p['company_id']) or (
                        t['country'] and p['country'] and t['country'] != p['country']) or (
                        card['part'] != 'avail' and not p['policy']) or (
                        p['policy'] and t['category'] != 'annual'):
                    cell.fill = grey
                    continue
                opening = ctx['openings'].get((emp.id, t['id']))
                if opening:
                    value = {'avail': opening['days'], 'carry': opening['carried'],
                             'taken': opening['taken']}[card['part']]
                    cell.value = value
                    cell.number_format = '0.##'
                    cell.fill, cell.font = set_fill, set_font
        ws.freeze_panes = 'D2'
        meta = wb.create_sheet(title=META_SHEET)
        meta['A1'], meta['B1'] = 'config_id', 0
        meta['D1'], meta['E1'] = DATE_KEY, fields.Date.to_string(cutover)
        meta['A2'], meta['B2'], meta['C2'] = 'column_index', 'field_id', 'label'
        for offset, card in enumerate(cards):
            meta.cell(row=3 + offset, column=1, value=first + offset)
            meta.cell(row=3 + offset, column=2, value=card['id'])
            meta.cell(row=3 + offset, column=3, value=card['label'])
        meta.sheet_state = 'hidden'
        guide = wb.create_sheet(title=_("Read me")[:31])
        guide.column_dimensions['A'].width = 110
        lines = [
            _("Leave opening balances as at %s") % when,
            _("Each number is how much of that leave the person still has available on %s. "
              "It becomes their balance from that day.") % when,
            _("A blank cell changes nothing. Type days (or hours, where the heading says "
              "hours). A leave type taken in whole days takes whole numbers; one taken in half "
              "days takes halves, like 12.5."),
            _("A balance can be set only once per person and leave type. Shaded cells with a "
              "number are already set: send them back as they are, or the change is refused. "
              "To correct one, undo the update that set it, then send it again."),
            _("Grey empty cells are leave types that person cannot have. Anything typed there "
              "is left out."),
        ]
        if any_policy:
            lines += [
                _("\"Carried from last year\" and \"already taken this year\" are kept on record "
                  "with the balance for people on an absence policy. They do not add to or take "
                  "from the days available."),
                _("For people on an absence policy a balance is permanent once it is set: it "
                  "cannot be undone from Updates."),
            ]
        for idx, line in enumerate(lines, start=1):
            cell = guide.cell(row=idx, column=1, value=line)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if idx == 1:
                cell.font = bold
        out = io.BytesIO()
        wb.save(out)
        return {'ok': True, 'file_b64': base64.b64encode(out.getvalue()).decode(),
                'filename': _("%(product)s leave opening balances %(date)s.xlsx") % {
                    'product': product_label(self.env), 'date': fields.Date.to_string(cutover)},
                'mimetype': XLSX_MIME, 'rows': len(people), 'total': total,
                'columns': len(cards), 'truncated': total > MAX_ROWS}

    # =================================================================
    # Match columns
    # =================================================================
    @api.model
    def _leave_sheet_date(self, file_b64, filename):
        """The date a downloaded sheet says its balances are as at, or ''."""
        if not (filename or '').lower().endswith(('.xlsx', '.xlsm')):
            return ''
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(file_b64 or '')),
                                        read_only=True, data_only=True)
            if META_SHEET not in wb.sheetnames:
                return ''
            ms = wb[META_SHEET]
            if str(ms['D1'].value or '') != DATE_KEY:
                return ''
            day = fields.Date.to_date(str(ms['E1'].value or '')[:10])
            return fields.Date.to_string(day) if day else ''
        except Exception:  # noqa: BLE001 — a hint, never a gate
            return ''

    @api.model
    def _leave_read_columns(self, file_b64='', filename='', cutover=None):
        desk = self._gate()
        refusal, header, rows, comments, meta, name = desk._io_open(file_b64, filename)
        if refusal:
            return refusal
        body = rows[1:]
        if not body:
            return {'ok': False, 'empty': True, 'filename': name,
                    'msg': _("This file has headings only — fill it in and drop it again.")}
        _used, identity_cols, _ignored, _how = desk._io_columns(
            header, comments, {'config_id': 0, 'by_index': {}}, {}, with_how=True)
        identity_at = {idx: key for key, idx in identity_cols.items()}
        cat = self._leave_catalogue()
        offered = cat['cards']
        by_label = {}
        for card in offered.values():
            by_label.setdefault(_norm(card['label']), card['id'])
            if card['part'] == 'avail':
                by_label.setdefault(_norm(card['type_name']), card['id'])
        heads = [str(h if h is not None else '').strip() for h in header]
        fingerprint = GROUP + ':' + heading_fingerprint(heads)
        Layout = self.env['pb.updates.layout']
        layouts = Layout.search([('company_id', '=', self.env.company.id), ('kind', '=', GROUP)],
                                order='last_used desc, id desc', limit=50)
        exact = layouts.filtered(lambda l: l.fingerprint == fingerprint)[:1]
        maps = ([exact.get_map()] if exact else []) + [l.get_map() for l in layouts if l != exact]
        columns, taken, taken_identity = [], set(), set(identity_at.values())
        for idx, head in enumerate(heads, start=1):
            if not head:
                continue
            samples = []
            for _offset, row in body:
                text = desk._io_text(desk._io_cell(row, idx))
                if text:
                    samples.append(text)
                    if len(samples) >= 3:
                        break
            col = {'idx': idx, 'head': head, 'samples': samples, 'field_id': '',
                   'identity': identity_at.get(idx, ''), 'how': '', 'target': ''}
            if col['identity']:
                col.update(how='identity', target='identity:%s' % col['identity'])
                columns.append(col)
                continue
            match = ID_RE.search(comments.get(idx) or '')
            fid = match.group(1).strip() if match else ''
            if not fid:
                fid = (meta.get('by_index') or {}).get(idx) or ''
            if fid in offered and fid not in taken:
                col.update(how='id', field_id=fid, target=fid)
            else:
                key = _norm(head)
                remembered = next((m[key] for m in maps if key in m), '')
                if remembered == 'ignore':
                    col.update(how='memory', target='ignore')
                elif remembered.startswith('identity:'):
                    ident = remembered.split(':', 1)[1]
                    if ident in IDENTITY_KEYS and ident not in taken_identity:
                        taken_identity.add(ident)
                        col.update(how='memory', identity=ident, target=remembered)
                elif remembered in offered and remembered not in taken:
                    col.update(how='memory', field_id=remembered, target=remembered)
                elif by_label.get(key) and by_label[key] not in taken:
                    col.update(how='label', field_id=by_label[key], target=by_label[key])
                else:
                    best, ratio = '', 0.0
                    for cid, card in offered.items():
                        if cid in taken:
                            continue
                        r = difflib.SequenceMatcher(None, key, _norm(card['label'])).ratio()
                        if r > ratio:
                            best, ratio = cid, r
                    if best and ratio >= GUESS_RATIO:
                        col.update(how='guess', field_id=best, target=best)
            if col['field_id']:
                taken.add(col['field_id'])
            columns.append(col)
        placed_by_id = [c for c in columns if c['how'] == 'id']
        return {
            'ok': True, 'kind': GROUP, 'filename': name, 'rows': len(body),
            'truncated': len(body) > MAX_ROWS, 'columns': columns,
            'fields': self._leave_topics(cat), 'layout_known': bool(exact),
            'sheet_date': self._leave_sheet_date(file_b64, filename),
            'from_sheet': bool(placed_by_id) and all(c['how'] in ('id', 'identity')
                                                    for c in columns),
            'schemes': [], 'no_scheme': 0,
        }

    @api.model
    def _remember_leave_layout(self, columns):
        cols = self._clean_columns(columns)
        heads = dict(cols['heads'])
        if not heads:
            return
        identity_at = {idx: key for key, idx in cols['identity'].items()}
        pairs = []
        for idx in sorted(heads):
            if not _norm(heads[idx]):
                continue
            if idx in identity_at:
                target = 'identity:%s' % identity_at[idx]
            elif idx in cols['used']:
                target = cols['used'][idx]
            else:
                target = 'ignore'
            pairs.append((heads[idx], target))
        self.env['pb.updates.layout'].remember(pairs, kind=GROUP)

    # =================================================================
    # Review
    # =================================================================
    @api.model
    def _leave_review(self, file_b64='', filename='', columns=None, cutover=None):
        desk = self._gate()
        cutover, refusal = self._leave_cutover(cutover)
        if refusal:
            return {'ok': False, 'msg': refusal}
        cols = self._clean_columns(columns)
        if not cols['identity']:
            return {'ok': False, 'msg': _(
                "Pick the column that finds the person: an employee code, a "
                "name or a work email.")}
        refusal, header, rows, _comments, _meta, name = desk._io_open(file_b64, filename)
        if refusal:
            return refusal
        cat = self._leave_catalogue()
        used = {idx: fid for idx, fid in cols['used'].items()
                if fid in cat['cards'] and idx not in cols['identity'].values()}
        if not used:
            return {'ok': False, 'msg': _(
                "Pick at least one column that goes to a leave balance.")}
        body = rows[1:]
        truncated = len(body) > MAX_ROWS
        body = body[:MAX_ROWS]
        index = desk._io_index(desk._matching({}, ctx={}))
        clear_words = desk._io_clear_words()
        matched, unmatched, methods = [], [], {}
        for offset, row in body:
            code = desk._io_text(desk._io_cell(row, cols['identity'].get('code')))
            person = desk._io_text(desk._io_cell(row, cols['identity'].get('name')))
            email = desk._io_text(desk._io_cell(row, cols['identity'].get('email')))
            values = {}
            for idx, fid in used.items():
                raw = desk._io_cell(row, idx)
                if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                    raw = desk._io_text(raw)
                if raw in (None, ''):
                    continue
                values[fid] = raw
            emp_id, method, why = desk._io_match(index, code, person, email)
            if not emp_id:
                unmatched.append({'row': offset, 'code': code, 'name': person, 'email': email,
                                  'why': why, 'values': {k: str(v) for k, v in values.items()}})
                continue
            methods[method] = methods.get(method, 0) + 1
            matched.append({'row': offset, 'emp_id': emp_id, 'method': method, 'values': values})
        emp_ids = sorted({m['emp_id'] for m in matched})
        info = self._people_info(desk, emp_ids)
        ctx = self._leave_ctx(emp_ids, cutover, sender=self.env.user)
        last_row, twice = {}, {}
        for pos, m in enumerate(matched):
            twice[m['emp_id']] = twice.get(m['emp_id'], 0) + 1
            for fid in m['values']:
                last_row[(m['emp_id'], fid)] = pos
        out_rows, changes = [], []
        for pos, m in enumerate(matched):
            p_info = info.get(m['emp_id']) or {}
            cells = {}
            for fid, raw in m['values'].items():
                type_id, part = parse_card(fid)
                cell = self._leave_cell(ctx, m['emp_id'], type_id, part, raw, clear_words)
                if last_row.get((m['emp_id'], fid)) != pos:
                    cell.update(status='dup', why=_(
                        "This person is in the file again further down, and that "
                        "row's value is the one used."))
                cells[fid] = cell
            # "Carried" and "taken" travel with a balance: alone, they wait for one.
            for fid, cell in cells.items():
                type_id, part = parse_card(fid)
                if part == 'avail' or cell['status'] != 'ok':
                    continue
                avail = cells.get(card_id(type_id))
                if not avail or avail['status'] not in ('ok',):
                    cell.update(status='refused', why=_(
                        "Fill in %s as well: carried and taken days are kept with a new "
                        "balance.") % cat['cards'][card_id(type_id)]['label']
                        if card_id(type_id) in cat['cards'] else _(
                        "Carried and taken days are kept with a new balance only."))
            for fid, cell in cells.items():
                if cell['status'] == 'ok':
                    changes.append({'emp_id': m['emp_id'], 'field_id': fid, 'value': cell['amount']})
            person = ctx['people'].get(m['emp_id']) or {}
            row = {'row': m['row'], 'emp_id': m['emp_id'], 'method': m['method'],
                   'name': p_info.get('name') or '', 'code': p_info.get('code') or '',
                   'department': p_info.get('department') or '',
                   'twice': twice.get(m['emp_id'], 0) > 1, 'cells': cells,
                   'policy': bool(person.get('policy'))}
            out_rows.append(row)
        out_columns = []
        for idx in sorted(used):
            card = cat['cards'][used[idx]]
            if any(c['field_id'] == card['id'] for c in out_columns):
                continue
            out_columns.append({'field_id': card['id'], 'label': card['label'],
                                'group': card['group'], 'idx': idx, 'role': card['part'],
                                'unit': card['unit'], 'head': cols['heads'].get(idx, '')})
        used_heads = {cols['heads'].get(i, '') for i in list(used) + list(cols['identity'].values())}
        ignored = [h for h in (str(x if x is not None else '').strip() for x in header)
                   if h and h not in used_heads]
        return {
            'ok': True, 'kind': GROUP, 'leave': True, 'filename': name,
            'cutover': fields.Date.to_string(cutover), 'cutover_label': day_label(self.env, cutover),
            'summary': {'rows': len(body), 'columns_ignored': ignored},
            'identity': max(methods, key=methods.get) if methods else '',
            'truncated': truncated, 'columns': out_columns, 'pay_items': False,
            'dated': False, 'today': fields.Date.to_string(self._leave_today()),
            'rows': out_rows, 'unmatched': unmatched, 'changes': changes,
            'policy_people': sum(1 for r in out_rows if r['policy']),
            'schemes': [], 'no_scheme': 0,
        }

    @api.model
    def _leave_recheck(self, changes=None, cutover=None):
        """An on-screen fix or a row bound by hand, judged like the file."""
        self._gate()
        cutover, refusal = self._leave_cutover(cutover)
        if refusal:
            return {'items': [], 'msg': refusal}
        changes = [c for c in (changes or []) if isinstance(c, dict)]
        emp_ids = sorted({int(c.get('emp_id') or 0) for c in changes} - {0})
        ctx = self._leave_ctx(emp_ids, cutover, sender=self.env.user)
        cat = self._leave_catalogue()
        clear_words = self._desk()._io_clear_words()
        items = []
        for change in changes:
            emp_id = int(change.get('emp_id') or 0)
            fid = str(change.get('field_id') or '')
            type_id, part = parse_card(fid)
            cell = self._leave_cell(ctx, emp_id, type_id, part, change.get('value'), clear_words) \
                if type_id else {'status': 'refused', 'why': _("This value could not be checked. Try again."),
                                 'old': '', 'new': str(change.get('value') or ''), 'amount': 0.0,
                                 'cleared': False, 'role': ''}
            items.append({'emp_id': emp_id, 'field_id': fid, 'status': cell['status'],
                          'old_label': cell['old'], 'new_label': cell['new'], 'why': cell['why'],
                          'cleared': False, 'amount': cell['amount'], 'role': cell['role'],
                          'field_label': (cat['cards'].get(fid) or {}).get('label') or ''})
        return {'items': items, 'people': {}}

    # =================================================================
    # Apply
    # =================================================================
    @api.model
    def leave_outlook(self, changes=None):
        """Before sending: who the balances go to for approval, in names —
        or "set now" under "No approval needed". Read only."""
        self._gate()
        rows = [c for c in (changes or []) if isinstance(c, dict)]
        probe = self._probe_apply('pay', rows)
        kind, names, sentence = self._first_step_people(probe, RECORDS_PROCESS_KEY)
        if kind == 'fast':
            return {'outcome': 'now', 'names': [], 'line': _("Set now: your company needs no "
                                                              "approval for these.")}
        if kind == 'route' and names:
            return {'outcome': 'approval', 'names': names,
                    'line': _("Go to %s for approval") % self._names_line(names)}
        return {'outcome': 'approval', 'names': [], 'line': sentence or _("Go for approval")}

    @api.model
    def _leave_apply(self, name='', file_b64='', filename='', columns=None,
                     changes=None, stats=None, cutover=None, draft_id=0):
        """Name it, keep the file, and send ONE approval for every balance in
        it. Every value is judged again here; the browser's list is trusted no
        more than the desk trusts it."""
        desk = self._gate()
        name = (name or '').strip()
        if not name:
            return {'ok': False, 'msg': _(
                "Give this update a name first, so you can find it later in "
                "Past updates.")}
        if not self._leave_may_set():
            return {'ok': False, 'msg': _(
                "Setting leave balances needs the HR officer role. You can still "
                "check a sheet and see what it would set.")}
        cutover, refusal = self._leave_cutover(cutover)
        if refusal:
            return {'ok': False, 'msg': refusal}
        clean, seen = [], set()
        for change in reversed([c for c in (changes or []) if isinstance(c, dict)]):
            try:
                emp_id = int(change.get('emp_id') or 0)
            except (TypeError, ValueError):
                continue
            fid = str(change.get('field_id') or '')
            type_id, part = parse_card(fid)
            if not emp_id or not type_id or (emp_id, fid) in seen:
                continue
            seen.add((emp_id, fid))
            clean.append({'emp_id': emp_id, 'field_id': fid, 'value': change.get('value'),
                          'type_id': type_id, 'part': part})
        clean.reverse()
        if not clean:
            return {'ok': False, 'msg': _(
                "There is nothing to send: no balance in this file would change anything.")}
        emp_ids = sorted({c['emp_id'] for c in clean})
        visible = set(desk._matching({'employee_ids': emp_ids}, ctx={}).ids)
        ctx = self._leave_ctx(emp_ids, cutover, sender=self.env.user)
        cat = self._leave_catalogue()
        names = {i: p['name'] for i, p in ctx['people'].items()}
        groups = {}
        for change in clean:
            if change['emp_id'] not in visible:
                continue
            groups.setdefault((change['emp_id'], change['type_id']), {})[change['part']] = change
        refused, lines, off = [], [], 0

        def label_of(fid):
            return (cat['cards'].get(fid) or {}).get('label') or fid

        for (emp_id, type_id), parts in groups.items():
            verdicts = {}
            for part, change in parts.items():
                raw = change['value']
                if raw is None or raw is False:
                    raw = ''
                verdicts[part] = self._leave_cell(ctx, emp_id, type_id, part, raw)
            avail = verdicts.get('avail')
            for part, cell in verdicts.items():
                if cell['status'] == 'off_scheme':
                    off += 1
                elif cell['status'] == 'refused':
                    refused.append({'emp_id': emp_id, 'emp_name': names.get(emp_id) or '',
                                    'field_id': card_id(type_id, part),
                                    'field_label': label_of(card_id(type_id, part)),
                                    'why': cell['why']})
            if not avail or avail['status'] != 'ok':
                for part in ('carry', 'taken'):
                    if verdicts.get(part, {}).get('status') == 'ok':
                        refused.append({'emp_id': emp_id, 'emp_name': names.get(emp_id) or '',
                                        'field_id': card_id(type_id, part),
                                        'field_label': label_of(card_id(type_id, part)),
                                        'why': _("Carried and taken days are kept with a new "
                                                 "balance only, and this row has none.")})
                continue
            person = ctx['people'][emp_id]
            t = ctx['types'][type_id]
            lines.append({
                'employee_id': emp_id, 'company_id': person['company_id'],
                'leave_type_id': type_id, 'type_name': t['name'], 'unit': t['unit'],
                'cutover_date': cutover, 'available': avail['amount'],
                'carried': verdicts['carry']['amount'] if verdicts.get('carry', {}).get('status') == 'ok' else 0.0,
                'taken': verdicts['taken']['amount'] if verdicts.get('taken', {}).get('status') == 'ok' else 0.0,
                'way': 'policy' if person['policy'] else 'allocation',
            })
        self._remember_leave_layout(columns)
        when = day_label(self.env, cutover)
        if not lines:
            return {'ok': True, 'kind': GROUP, 'nothing': True, 'batch_id': 0, 'apply_id': 0,
                    'written': 0, 'people': 0, 'refused': refused, 'pending': False,
                    'off_scheme': off, 'cutover_label': when,
                    'msg': _("Nothing was sent: every balance in this file is already set, or "
                             "could not be used.")}
        stats = stats if isinstance(stats, dict) else {}

        def count(key):
            try:
                return max(0, int(stats.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        batch = self._new_batch({
            'name': name[:200], 'kind': GROUP, 'leave_date': cutover,
            'filename': (filename or '').strip() or False,
            'rows_total': count('rows'), 'rows_unmatched': count('unmatched'),
            'values_refused': count('left_out') + len(refused),
            'values_off_scheme': count('off_scheme') + off,
        }, file_b64, filename, draft_id)
        Apply = self.env['pb.records.apply'].sudo()
        apply_rec = Apply.create({
            'name': '/', 'note': name, 'source': 'import', 'updates_leave': True,
            'count_people': 0, 'count_values': 0, 'plan_json': '[]',
            'changes_json': json.dumps([{k: c[k] for k in ('emp_id', 'field_id', 'value')}
                                        for c in clean], default=str),
            'people_count': len({l['employee_id'] for l in lines}), 'values_count': len(lines),
            'touches_bank': False, 'touches_salary': True,
            'company_id': self.env.company.id, 'updates_batch_id': batch.id,
        })
        apply_rec.name = 'RD%05d' % apply_rec.id
        Line = self.env['pb.updates.leave.line'].sudo()
        rows = Line.create([dict(l, batch_id=batch.id, apply_id=apply_rec.id) for l in lines])
        rows._log(_("Sent in “%s”.") % batch.name)
        apply_rec.plan_json = json.dumps([r._plan_row() for r in rows])
        payload = self.env['biz.approval.engine'].submit(apply_rec)
        apply_rec.invalidate_recordset()
        rows.invalidate_recordset()
        late = rows.filtered(lambda r: r.state == 'refused')
        for r in late:
            refused.append({'emp_id': r.employee_id.id, 'emp_name': r.employee_id.name or '',
                            'field_id': card_id(r.leave_type_id.id),
                            'field_label': label_of(card_id(r.leave_type_id.id)),
                            'why': r.reason or ''})
        live = rows.filtered(lambda r: r.state in LIVE)
        return dict(self._leave_totals(live or rows), **{
            'ok': True, 'kind': GROUP, 'batch_id': batch.id, 'batch_name': batch.name,
            'apply_id': apply_rec.id, 'reference': apply_rec.name,
            'pending': not apply_rec.applied, 'approved': bool(apply_rec.applied),
            'request_id': (payload or {}).get('id') or 0,
            'with_whom': apply_rec._waiting_for(), 'route': desk._route_labels(apply_rec),
            'written': len(rows.filtered(lambda r: r.state == 'set')),
            'values': len(rows), 'people': len(rows.mapped('employee_id')),
            'refused': refused, 'off_scheme': off, 'skipped_off_scheme': off,
            'not_set': len(late),
            'cutover': fields.Date.to_string(cutover), 'cutover_label': when,
            'undoable': len(rows.filtered(lambda r: r.way == 'allocation')),
            'permanent': len(rows.filtered(lambda r: r.way == 'policy')),
        })

    @api.model
    def _leave_totals(self, rows):
        days = sum(r.available for r in rows if r.unit != 'hour')
        hours = sum(r.available for r in rows if r.unit == 'hour')
        Line = self.env['pb.updates.leave.line']
        return {'days_total': days, 'hours_total': hours,
                'days_label': Line._qty_label(days, 'day') if days else '',
                'hours_label': Line._qty_label(hours, 'hour') if hours else ''}

    # =================================================================
    # Home: past updates, undo, cancel
    # =================================================================
    @api.model
    def _leave_state(self, batch):
        """`(state, label, note)` read off the rows and the proposal every
        time (never stored)."""
        rows = batch.leave_line_ids.sudo()
        apply_rec = rows.mapped('apply_id')[:1]
        if not rows:
            return 'cancelled', _("Cancelled"), ''
        reason = apply_rec._blocked_reason() if apply_rec else ''
        if reason:
            return 'blocked', _("Could not be made"), _("Approved, but it could not be made: %s") % reason
        states = set(rows.mapped('state'))
        if 'waiting' in states:
            return 'pending', _("Waiting for approval"), ''
        n_set = len(rows.filtered(lambda r: r.state == 'set'))
        n_ref = len(rows.filtered(lambda r: r.state == 'refused'))
        n_und = len(rows.filtered(lambda r: r.state == 'undone'))
        if n_set and n_und:
            return 'mixed', _("Partly undone"), ''
        if n_set and n_ref:
            return 'applied', _("Set, %s could not be set") % n_ref, ''
        if n_set:
            return 'applied', _("Set"), ''
        if n_und:
            return 'undone', _("Undone"), ''
        if states <= {'refused'}:
            return 'blocked', _("Could not be set"), ''
        if states <= {'rejected'}:
            return 'rejected', _("Turned down"), ''
        if states <= {'returned'}:
            return 'returned', _("Sent back"), ''
        return 'cancelled', _("Cancelled"), ''

    @api.model
    def _leave_batch_row(self, batch, may_write):
        rows = batch.leave_line_ids.sudo()
        state, label, note = self._leave_state(batch)
        apply_rec = rows.mapped('apply_id')[:1]
        may_undo = may_write and self._leave_may_undo()
        undoable = rows.filtered(lambda r: r.state == 'set' and r.way == 'allocation')
        permanent = rows.filtered(lambda r: r.state == 'set' and r.way == 'policy')
        live = rows.filtered(lambda r: r.state in LIVE) or rows
        totals = self._leave_totals(live)
        undone = rows.filtered(lambda r: r.state == 'undone').sorted('undone_at')
        return dict(totals, **{
            'id': batch.id, 'kind': GROUP, 'name': batch.name or '',
            'user': batch.user_id.display_name or '',
            'date': batch.date and batch.date.strftime('%Y-%m-%d %H:%M:%S') or '',
            'filename': batch.filename or '', 'file_id': batch.attachment_id.id or 0,
            'people': len(live.mapped('employee_id')), 'values': len(live),
            'rows_unmatched': batch.rows_unmatched, 'values_refused': batch.values_refused,
            'values_off_scheme': batch.values_off_scheme,
            'state': state, 'state_label': label, 'state_note': note,
            'state_reason': note if state == 'blocked' else '',
            'cutover': fields.Date.to_string(batch.leave_date) if batch.leave_date else '',
            'cutover_label': day_label(self.env, batch.leave_date) if batch.leave_date else '',
            'with_whom': apply_rec._waiting_for() if apply_rec and state == 'pending' else '',
            'can_undo': bool(may_undo and undoable),
            'can_cancel': bool(may_write and apply_rec and apply_rec.state == 'pending'
                               and not apply_rec.applied
                               and apply_rec.with_env(self.env)._may_cancel()),
            'has_open': False, 'scheduled': [], 'recorded': [],
            'set_values': len(rows.filtered(lambda r: r.state == 'set')),
            'not_set': len(rows.filtered(lambda r: r.state == 'refused')),
            'not_set_lines': [{'who': r.employee_id.name or '', 'type': r.type_name or '',
                               'why': r.reason or ''}
                              for r in rows.filtered(lambda r: r.state == 'refused')[:20]],
            'undoable': len(undoable), 'permanent': len(permanent),
            'undone_values': len(undone),
            'undone_by': undone[-1:].undone_by_id.display_name or '' if undone else '',
            'undone_date': undone[-1:].undone_at.strftime('%Y-%m-%d %H:%M:%S')
            if undone and undone[-1:].undone_at else '',
            'cancelled_values': len(rows.filtered(lambda r: r.state == 'cancelled')),
            'cancelled_by': '', 'cancelled_date': '',
        })

    @api.model
    def _batch_row(self, batch, may_write):
        if batch.kind == GROUP:
            return self._leave_batch_row(batch, may_write)
        return super()._batch_row(batch, may_write)

    @api.model
    def _leave_batch(self, batch_id):
        try:
            bid = int(batch_id or 0)
        except (TypeError, ValueError):
            bid = 0
        return self.env['pb.updates.batch'].search(
            [('id', '=', bid), ('company_id', 'in', self.env.companies.ids),
             ('state', '!=', 'draft'), ('kind', '=', GROUP)], limit=1)

    @api.model
    def _leave_undo_rows(self, rows, apply_rec=None):
        """Take back every balance of these rows that nothing has drawn on.
        A balance set through the absence policy stays (it is permanent)."""
        rows = rows.sudo().filtered(lambda r: r.state == 'set')
        plain = rows.filtered(lambda r: r.way == 'allocation')
        permanent = rows - plain
        removed, kept = 0, []
        for row in plain.sorted('id'):
            why = ''
            try:
                with self.env.cr.savepoint():
                    why = row._undo_one()
            except Exception as error:   # noqa: BLE001 — one row never stops the rest
                why = _("%(who)s's %(type)s balance could not be taken off: %(error)s",
                        who=row.employee_id.name or '', type=row.type_name or '',
                        error=(getattr(error, 'args', None) or [str(error)])[0])
            if why:
                row.invalidate_recordset()
                row._log(_("Undo refused: %s") % why)
                kept.append(why)
            else:
                removed += 1
        source = apply_rec or rows.mapped('apply_id')[:1]
        if source and source.applied and not source.undone and removed and not \
                source.leave_line_ids.filtered(lambda r: r.state == 'set'):
            source.sudo().write({'undone': True, 'undone_date': fields.Datetime.now(),
                                 'undone_by_id': self.env.uid})
        bits = []
        if removed:
            bits.append(_("1 balance was taken off.") if removed == 1 else
                        _("%s balances were taken off.") % removed)
        if len(kept) == 1:
            bits.append(_("1 stays: %s") % kept[0])
        elif kept:
            bits.append(_("%(n)s stay. %(first)s", n=len(kept), first=kept[0]))
        if permanent:
            bits.append(_("1 balance set through the absence policy is permanent and stays.")
                        if len(permanent) == 1 else
                        _("%s balances set through the absence policy are permanent and stay.")
                        % len(permanent))
        if not removed:
            return {'ok': False, 'msg': ' '.join(bits) or _(
                "Nothing in this update can be undone."), 'kept': kept}
        return {'ok': True, 'restored': removed, 'skipped_changed_since': len(kept),
                'skipped_missing': 0, 'kept': kept, 'permanent': len(permanent),
                'msg': ' '.join(bits)}

    @api.model
    def undo(self, batch_id=0, apply_id=0):
        if batch_id and not apply_id:
            batch = self._leave_batch(batch_id)
            if batch:
                self._gate()
                if not self._leave_may_undo():
                    return {'ok': False, 'msg': _(
                        "Undoing leave balances needs the Time Off administrator role.")}
                rows = batch.leave_line_ids
                if rows.filtered(lambda r: r.state == 'waiting'):
                    return {'ok': False, 'msg': _(
                        "This update is still waiting for approval, so there is nothing to "
                        "undo yet.")}
                answer = self._leave_undo_rows(rows)
                answer.update(batch_id=batch.id, name=batch.name)
                return answer
        return super().undo(batch_id=batch_id, apply_id=apply_id)

    @api.model
    def cancel(self, batch_id=0, apply_id=0):
        if batch_id and not apply_id:
            batch = self._leave_batch(batch_id)
            if batch:
                desk = self._gate()
                if not self._can_write(desk) and not self._leave_may_set():
                    return {'ok': False, 'msg': _(
                        "Cancelling an update needs permission to change employee records.")}
                apply_rec = batch.leave_line_ids.mapped('apply_id')[:1]
                if not apply_rec or apply_rec.applied or apply_rec.state != 'pending':
                    return {'ok': False, 'msg': _(
                        "Nothing in this update is waiting for approval, so there is nothing "
                        "to cancel.")}
                waiting = len(batch.leave_line_ids.filtered(lambda r: r.state == 'waiting'))
                res = desk.cancel_apply(apply_rec.id)
                if not res.get('ok'):
                    return res
                return {'ok': True, 'cancelled': 1, 'values': waiting, 'batch_id': batch.id,
                        'name': batch.name,
                        'msg': _("1 balance cancelled before it was set.") if waiting == 1 else
                        _("%s balances cancelled before they were set.") % waiting}
        return super().cancel(batch_id=batch_id, apply_id=apply_id)

    # =================================================================
    # The dispatchers: kind='leave'
    # =================================================================
    @api.model
    def read_columns(self, file_b64='', filename='', kind='lasting', month=None, cutover=None):
        if kind == GROUP:
            return self._leave_read_columns(file_b64, filename, cutover)
        return super().read_columns(file_b64, filename, kind, month)

    @api.model
    def review(self, file_b64='', filename='', columns=None, kind='lasting', month=None,
               cutover=None):
        if kind == GROUP:
            return self._leave_review(file_b64, filename, columns, cutover)
        return super().review(file_b64, filename, columns, kind, month)

    @api.model
    def recheck(self, changes=None, kind='lasting', month=None, cutover=None):
        if kind == GROUP:
            return self._leave_recheck(changes, cutover)
        return super().recheck(changes, kind, month)

    @api.model
    def apply(self, name='', file_b64='', filename='', columns=None, changes=None, stats=None,
              start_date=None, hold_scope='pay', kind='lasting', month=None, draft_id=0,
              joiners=None, cutover=None):
        if kind == GROUP:
            return self._leave_apply(name, file_b64, filename, columns, changes, stats,
                                     cutover, draft_id=draft_id)
        return super().apply(name=name, file_b64=file_b64, filename=filename, columns=columns,
                             changes=changes, stats=stats, start_date=start_date,
                             hold_scope=hold_scope, kind=kind, month=month,
                             draft_id=draft_id, joiners=joiners)

    # =================================================================
    # Drafts (UPDATES P3b) for the third kind
    # =================================================================
    @api.model
    def save_draft(self, draft_id=0, kind='lasting', month=None, filename='',
                   file_b64='', columns=None, choices=None, step=''):
        if kind != GROUP:
            return super().save_draft(draft_id=draft_id, kind=kind, month=month,
                                      filename=filename, file_b64=file_b64, columns=columns,
                                      choices=choices, step=step)
        answer = super().save_draft(draft_id=draft_id, kind='lasting', month=None,
                                    filename=filename, file_b64=file_b64, columns=columns,
                                    choices=choices, step=step)
        if answer.get('ok'):
            draft = self._own_draft(answer['draft_id'])
            day, _why = self._leave_cutover(month) if month else (None, '')
            if draft:
                draft.write({'kind': GROUP, 'leave_date': day or False})
        return answer

    @api.model
    def _draft_row(self, draft):
        row = super()._draft_row(draft)
        if draft.kind == GROUP:
            row.update(kind=GROUP,
                       cutover=fields.Date.to_string(draft.leave_date) if draft.leave_date else '',
                       cutover_label=day_label(self.env, draft.leave_date) if draft.leave_date else '')
        return row


class PbRecordsDeskLeave(models.AbstractModel):
    """The Records screen's History lists a leave update too (its approval
    proposal is a records change): it reads its own words there, and its
    Undo takes back only what nothing has drawn on."""
    _inherit = 'pb.records.desk'

    @api.model
    def get_history(self, limit=20):
        answer = super().get_history(limit)
        rows = answer.get('applies') or []
        if not rows:
            return answer
        Apply = self.env['pb.records.apply'].sudo()
        recs = {r.id: r for r in Apply.browse([h['id'] for h in rows]).exists()}
        for h in rows:
            rec = recs.get(h['id'])
            if not rec or not rec.updates_leave or not rec.updates_batch_id:
                continue
            state, label, note = self.env['pb.updates.desk']._leave_state(rec.updates_batch_id)
            h['leave'] = True
            if state != 'blocked' or not h.get('block_note'):
                h['block_note'] = ' · '.join(x for x in (rec._headline(), label, note) if x)
            if rec.applied and not rec.leave_line_ids.filtered(
                    lambda r: r.state == 'set' and r.way == 'allocation'):
                # Nothing left that an Undo could take back.
                h['undone'] = True
        return answer

    @api.model
    def undo_apply(self, apply_id):
        source = self.env['pb.records.apply'].sudo().browse(int(apply_id or 0)).exists()
        if source and source.updates_leave and source.applied:
            Updates = self.env['pb.updates.desk']
            if not Updates._leave_may_undo():
                return {'ok': False, 'msg': _(
                    "Undoing leave balances needs the Time Off administrator role.")}
            return Updates._leave_undo_rows(source.leave_line_ids, source)
        return super().undo_apply(apply_id)
