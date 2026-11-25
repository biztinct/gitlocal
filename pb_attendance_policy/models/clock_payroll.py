"""WFSETUP P10b — the clock facts a pay scheme reads from its clock date.

Design of record: `docs/handovers/wfsetup/WFSETUP_P10A_PROPOSAL.md` §4.1 / §6,
owner rulings R10–R15 (`WFSETUP_OWNER_RULINGS.md`):

* paid days (R13) = worked-day equivalents of the person's published shifts
  (paid normal hours ÷ the shift rule's planned normal hours — lateness is
  already taken off inside the paid normal hours, R10) + approved PAID time off
  + public holidays the person was due to work and did not work;
* overtime (R14) = approved hours within the legal limit only; the hours above
  it are shown, never paid here; premium hours = hours × (rate − 1);
* every overtime entry must be decided (R15); no weekly sign-off.

WHICH DAYS COUNT for time off and holidays (handover "Live data changes" 2):
the work calendar is NOT used. Sudima's people sit on a Monday–Friday calendar
while they work six days, so calendar-based counting would drop every
Saturday. A day counts when the person was due to work it: a published shift
on that day, or a working day of their working week (pattern slot). This
needs no calendar re-assignment.

Nothing here writes. `facts_many` reads in bulk for the readiness list; the
payslip overlay (`hr.formula.config._pb_clock_apply`) asks for one person
with `live=True`, which also re-runs every shift's calculation against the
punches (`hr.attendance._pb_policy_valid`).
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

#: Overtime kinds a pay input reads (night / extended have no pay column).
_PAID_OT = ('weekday', 'weekend', 'holiday')
#: Holiday kinds that are paid days off (a collective leave is taken from
#: annual leave elsewhere and is not a paid holiday here).
_PAID_HOLIDAY_KINDS = ('public', 'company')
_ROUND_PAY = 6
_ROUND_INFO = 2


def _fact(value=None, status='resolved', reason=''):
    return {'value': value, 'status': status, 'reason': reason}


class ClockPayroll(models.AbstractModel):
    _name = 'pb.clock.payroll'
    _description = 'Clock hours for payroll (read-only)'

    # ================================================================ labels
    def _blocker_labels(self):
        return {
            'no_rules': _("Shift not under confirmed late rules"),
            'not_finished': _("Shift not over yet"),
            'not_calculated': _("Shift not worked out yet"),
            'stale': _("Shift changed since it was worked out"),
            'one_punch': _("Only one clock-in on a shift"),
            'no_code': _("No clock number"),
            'ambiguous_code': _("Clock number shared with someone else"),
            'no_shift_punch': _("Punches on a day with no shift"),
            'loose_attendance': _("Clock hours outside a shift"),
            'ot_pending': _("Overtime waiting for a decision"),
            'ot_unpaid_kind': _("Night overtime has no pay column"),
            'ot_rate': _("Overtime without a rate"),
            'leave_pending': _("Time off waiting for approval"),
            'leave_type': _("Time off type not set as paid or unpaid"),
            'leave_worked': _("Time off on a day with clock-ins"),
            'no_shifts': _("No shifts this month"),
        }

    @api.model
    def _fmt_days(self, days):
        days = sorted(set(days))
        shown = ', '.join(d.strftime('%d/%m') for d in days[:6])
        if len(days) > 6:
            shown += ' +%s' % (len(days) - 6)
        return shown

    # ================================================================ helpers
    @api.model
    def _tz(self, employee, policy=None):
        name = (policy.tz if policy else False) or employee.sudo().pb_attendance_policy_id.tz
        if not name:
            name = self.env['hr.shift.planning.grid']._pb_shift_tzname(employee)
        try:
            return pytz.timezone(name or 'UTC')
        except pytz.UnknownTimeZoneError:
            return pytz.utc

    @api.model
    def _due_by_pattern(self, employees, first, last):
        """{employee_id: {date}} — the days their working week has a shift."""
        out = defaultdict(set)
        Member = self.env.get('pb.shift.pattern.member')
        if Member is None:
            return out
        members = Member.sudo().search([
            ('employee_id', 'in', employees.ids), ('pattern_id.active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', last),
            '|', ('date_to', '=', False), ('date_to', '>=', first)])
        slot_maps = {}
        for m in members:
            pattern = m.pattern_id
            if pattern.id not in slot_maps:
                slot_maps[pattern.id] = pattern._pb_slot_map()
            slots = slot_maps[pattern.id]
            day = max(first, m.date_from or first)
            stop = min(last, m.date_to or last)
            while day <= stop:
                if slots.get(pattern._pb_cycle_index(day, m.team_id.offset_days)):
                    out[m.employee_id.id].add(day)
                day += timedelta(days=1)
        return out

    @api.model
    def _holidays(self, employees, first, last):
        """{employee_id: {date: name}} — paid company holidays (public / company)."""
        out = defaultdict(dict)
        if not employees:
            return out
        lo = datetime.combine(first - timedelta(days=1), time.min)
        hi = datetime.combine(last + timedelta(days=1), time.max)
        Leaves = self.env['resource.calendar.leaves'].sudo()
        domain = [('resource_id', '=', False), ('company_id', 'in', employees.company_id.ids),
                  ('time_type', '=', 'leave'), ('date_from', '<=', hi), ('date_to', '>=', lo)]
        if 'pb_holiday_kind' in Leaves._fields:
            domain.append(('pb_holiday_kind', 'in', list(_PAID_HOLIDAY_KINDS)))
        rows = Leaves.search(domain)
        Holidays = self.env.get('pb.holidays')
        for emp in employees:
            cals = {emp.resource_calendar_id.id, emp.company_id.resource_calendar_id.id}
            for row in rows:
                if row.company_id != emp.company_id or (row.calendar_id and row.calendar_id.id not in cals):
                    continue
                # The day as the holiday board wrote it: in its calendar's own
                # time zone (`pb.holidays._bounds`), whatever the person's.
                calendar = row.calendar_id or emp.company_id.resource_calendar_id
                tz = (Holidays._tz(calendar, emp.company_id) if Holidays is not None
                      else self._tz(emp))
                d_from = pytz.utc.localize(row.date_from).astimezone(tz).date()
                end_local = pytz.utc.localize(row.date_to).astimezone(tz)
                d_to = end_local.date()
                if end_local.time() == time.min and d_to > d_from:
                    d_to -= timedelta(days=1)
                day = max(d_from, first)
                while day <= min(d_to, last):
                    out[emp.id].setdefault(day, row.name or '')
                    day += timedelta(days=1)
        return out

    @api.model
    def _punch_times(self, shifts_by_emp, employees, first, last):
        """{employee_id: [aware local datetimes]} of every retained punch, and
        {employee_id: blocker code} for people whose number cannot be read."""
        times, bad = defaultdict(set), {}
        Event = self.env['pb.clock.connector.event'].sudo()
        Punch = self.env['pb.clock.punch'].sudo()
        Roster = self.env['hr.shift.planning'].sudo()
        for emp in employees:
            emp_s = emp.sudo()
            code = (emp_s.pb_clock_code or emp_s.barcode or '').strip()
            if not code:
                bad[emp.id] = 'no_code'
                continue
            # the rules' own reading of a clock number (R8), asked through a
            # throwaway in-memory shift of this person
            probe = Roster.new({'employee_id': emp.id, 'company_id': emp.company_id.id})
            codes = probe._pb_clock_codes(code)
            if codes is None:
                bad[emp.id] = 'ambiguous_code'
                continue
            tz = self._tz(emp)
            lo = datetime.combine(first - timedelta(days=1), time.min)
            hi = datetime.combine(last + timedelta(days=2), time.min)
            policy_tz = emp_s.pb_attendance_policy_id.tz or tz.zone
            for e in Event.search([('company_id', '=', emp.company_id.id), ('user_code', 'in', list(codes)),
                                   ('state', 'in', ['ready', 'posted', 'duplicate']),
                                   ('punch_local', '>=', lo), ('punch_local', '<', hi),
                                   ('connector_id.tz', '=', policy_tz)]):
                try:
                    times[emp.id].add(tz.localize(e.punch_local, is_dst=None))
                except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
                    continue
            ulo = tz.localize(lo).astimezone(pytz.utc).replace(tzinfo=None)
            uhi = tz.localize(hi).astimezone(pytz.utc).replace(tzinfo=None)
            for p in Punch.search([('employee_id', '=', emp.id), ('punch_utc', '>=', ulo), ('punch_utc', '<', uhi),
                                   ('state', 'in', ['matched', 'paired', 'middle', 'held', 'ignored_duplicate_tap'])]):
                times[emp.id].add(pytz.utc.localize(p.punch_utc).astimezone(tz))
        return times, bad

    @api.model
    def _window(self, shift, tz):
        policy = shift.pb_policy_id
        before = policy.capture_before if policy else 2.0
        after = policy.capture_after if policy else 2.0
        start = pytz.utc.localize(shift.start_datetime).astimezone(tz)
        end = pytz.utc.localize(shift.end_datetime).astimezone(tz)
        return start - timedelta(hours=before), end + timedelta(hours=after), end

    # ================================================================ facts
    @api.model
    def facts_many(self, employees, date_from, date_to, live=False):
        """{employee_id: {'facts': {key: fact}, 'blockers': [..], 'absent': [dates]}}.

        `live=True` re-checks every calculated shift against its punches
        (slow, used per payslip); `live=False` trusts the stored calculation
        (fast, used for the readiness list of a whole run).
        """
        first = fields.Date.to_date(date_from)
        last = fields.Date.to_date(date_to) or first
        employees = employees.sudo()
        labels = self._blocker_labels()
        Roster = self.env['hr.shift.planning'].sudo()
        all_shifts = Roster.search([
            ('employee_id', 'in', employees.ids), ('state', '!=', 'cancelled'),
            ('date', '>=', first - timedelta(days=1)), ('date', '<=', last + timedelta(days=1))],
            order='date, start_datetime, id')
        shifts_by_emp = defaultdict(lambda: Roster.browse())
        for s in all_shifts:
            shifts_by_emp[s.employee_id.id] |= s
        due_pattern = self._due_by_pattern(employees, first, last)
        holidays = self._holidays(employees, first, last)
        times, bad_code = self._punch_times(shifts_by_emp, employees, first, last)

        Req = self.env['hr.overtime.request'].sudo()
        has_comp = 'pb_comp_choice' in Req._fields
        reqs = Req.search([('employee_id', 'in', employees.ids), ('date', '>=', first), ('date', '<=', last)])
        reqs_by_emp = defaultdict(lambda: Req.browse())
        for r in reqs:
            reqs_by_emp[r.employee_id.id] |= r

        Leave = self.env['hr.leave'].sudo()
        leaves = Leave.search([('employee_id', 'in', employees.ids),
                               ('state', 'in', ['confirm', 'validate1', 'validate']),
                               ('request_date_from', '<=', last), ('request_date_to', '>=', first)])
        leaves_by_emp = defaultdict(lambda: Leave.browse())
        for lv in leaves:
            leaves_by_emp[lv.employee_id.id] |= lv

        Att = self.env['hr.attendance'].sudo()
        out = {}
        for emp in employees:
            tz = self._tz(emp)
            blockers = defaultdict(set)
            notes = defaultdict(set)
            absent = set()
            mine = shifts_by_emp.get(emp.id) or Roster.browse()
            published = mine.filtered(lambda s: s.state == 'published')
            in_period = published.filtered(lambda s: first <= s.date <= last)
            worked_days = paid_normal = actual = late = deduction = 0.0
            worked_dates = set()
            punches = sorted(times.get(emp.id) or ())
            if emp.id in bad_code:
                blockers[bad_code[emp.id]].update(s.date for s in in_period)
                if not in_period:
                    blockers[bad_code[emp.id]].add(first)
            for s in in_period:
                if s.pb_policy_id.state not in ('active', 'retired'):
                    blockers['no_rules'].add(s.date)
                    continue
                low, high, end = self._window(s, tz)
                inside = [p for p in punches if low <= p <= high]
                att = s.pb_attendance_id
                if att:
                    valid = (att._pb_policy_valid(s.date) if live else
                             bool(att.pb_policy_proof) and att.pb_policy_proof == s.pb_calculation_json)
                    if not valid:
                        blockers['stale'].add(s.date)
                        continue
                    proof = att._pb_policy_values() or {}
                    rule = self.env['pb.attendance.policy.shift'].sudo().browse(proof.get('shift_rule_id') or 0).exists()
                    planned = rule.normal_hours if rule else 0.0
                    normal = float(proof.get('normal_hours') or 0.0)
                    if (proof.get('day_kind') or 'weekday') == 'weekday':
                        if planned <= 0:
                            blockers['not_calculated'].add(s.date)
                            continue
                        worked_days += normal / planned
                    paid_normal += normal
                    actual += float(proof.get('worked_hours') or 0.0)
                    late += float(proof.get('late_minutes') or 0.0)
                    deduction += float(proof.get('penalty_hours') or 0.0)
                    worked_dates.add(s.date)
                    continue
                if emp.id in bad_code:
                    continue
                if high.astimezone(pytz.utc).replace(tzinfo=None) > fields.Datetime.now():
                    blockers['not_finished'].add(s.date)
                elif not inside:
                    absent.add(s.date)
                elif len(set(inside)) == 1:
                    blockers['one_punch'].add(s.date)
                    worked_dates.add(s.date)
                else:
                    blockers['not_calculated'].add(s.date)
                    worked_dates.add(s.date)
            # punches no published shift covers
            windows = [self._window(s, tz)[:2] for s in published]
            for p in punches:
                if not (first <= p.date() <= last):
                    continue
                if not any(lo <= p <= hi for lo, hi in windows):
                    blockers['no_shift_punch'].add(p.date())
            # clock hours outside a shift
            ulo = tz.localize(datetime.combine(first, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            uhi = tz.localize(datetime.combine(last + timedelta(days=1), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            for a in Att.search([('employee_id', '=', emp.id), ('pb_policy_roster_id', '=', False),
                                 ('check_in', '>=', ulo), ('check_in', '<', uhi)]):
                blockers['loose_attendance'].add(pytz.utc.localize(a.check_in).astimezone(tz).date())
            # overtime
            ot = premium = over = 0.0
            for r in reqs_by_emp.get(emp.id) or Req.browse():
                if r.state in ('draft', 'submitted'):
                    blockers['ot_pending'].add(r.date)
                    continue
                if r.state != 'approved':
                    continue
                if has_comp and r.pb_comp_choice == 'time_off':
                    continue
                if r.overtime_type not in _PAID_OT:
                    if (r.approved_hours or 0) or (r.bonus_hours or 0):
                        blockers['ot_unpaid_kind'].add(r.date)
                    continue
                rate = r.rate_multiplier or 0.0
                if rate < 1.0:
                    blockers['ot_rate'].add(r.date)
                    continue
                hours = r.approved_hours or 0.0
                ot += hours
                premium += hours * (rate - 1.0)
                over += r.bonus_hours or 0.0
            # paid time off and holidays (R13)
            due = set(due_pattern.get(emp.id) or ()) | {s.date for s in in_period}
            emp_holidays = holidays.get(emp.id) or {}
            holiday_days = 0.0
            for day in emp_holidays:
                if day in due and day not in worked_dates:
                    holiday_days += 1.0
            leave_days = 0.0
            for lv in leaves_by_emp.get(emp.id) or Leave.browse():
                lo_d, hi_d = max(lv.request_date_from, first), min(lv.request_date_to, last)
                if lv.state != 'validate':
                    blockers['leave_pending'].add(lo_d)
                    continue
                info = (lv._pb_payroll_classification() if hasattr(lv, '_pb_payroll_classification')
                        else {'error': True})
                fraction = info.get('employer_fraction', info.get('fraction')) if not info.get('error') else None
                if fraction is None or not 0 <= fraction <= 1:
                    blockers['leave_type'].add(lo_d)
                    notes['leave_type'].add(lv.holiday_status_id.display_name or '')
                    continue
                day = lo_d
                while day <= hi_d:
                    if day in due and day not in emp_holidays:
                        if day in worked_dates:
                            blockers['leave_worked'].add(day)
                        elif lv.request_unit_hours:
                            planned = 8.0
                            proofs = in_period.filtered(lambda s, d=day: s.date == d)[:1]
                            rule = proofs.pb_policy_id.shift_ids.filtered(
                                lambda r, s=proofs: r.template_id == s.shift_template_id)[:1] if proofs else False
                            if rule and rule.normal_hours:
                                planned = rule.normal_hours
                            leave_days += (lv.number_of_hours or 0.0) / planned * fraction
                        elif lv.request_unit_half:
                            leave_days += 0.5 * fraction
                        else:
                            leave_days += fraction
                    day += timedelta(days=1)
            if not in_period and not leave_days and not holiday_days:
                blockers['no_shifts'].add(first)

            blocks = []
            for code, days in blockers.items():
                text = labels[code]
                shown = self._fmt_days(days) if code != 'no_shifts' else ''
                extra = ', '.join(sorted(n for n in notes.get(code, ()) if n))
                parts = [p for p in (shown, extra) if p]
                blocks.append({'code': code, 'label': text, 'dates': sorted(str(d) for d in days),
                               'text': '%s (%s)' % (text, ' · '.join(parts)) if parts else text})
            blocks.sort(key=lambda b: list(labels).index(b['code']))
            worked = round(worked_days, _ROUND_PAY)
            leave = round(leave_days, _ROUND_PAY)
            hol = round(holiday_days, _ROUND_PAY)
            facts = {
                'clock.paid_days': _fact(round(worked + leave + hol, _ROUND_PAY)),
                'clock.worked_days': _fact(worked),
                'clock.paid_leave_days': _fact(leave),
                'clock.holiday_days': _fact(hol),
                'clock.paid_normal_hours': _fact(round(paid_normal, _ROUND_INFO)),
                'clock.ot_hours': _fact(round(ot, _ROUND_PAY)),
                'clock.ot_premium_hours': _fact(round(premium, _ROUND_PAY)),
                'clock.over_limit_hours': _fact(round(over, _ROUND_INFO)),
                'clock.actual_hours': _fact(round(actual, _ROUND_INFO)),
                'clock.late_minutes': _fact(round(late, _ROUND_INFO)),
                'clock.deduction_hours': _fact(round(deduction, _ROUND_INFO)),
            }
            if blocks:
                reason = '; '.join(b['text'] for b in blocks)
                facts = {k: _fact(None, 'conflict', reason) for k in facts}
            out[emp.id] = {'facts': facts, 'blockers': blocks,
                           'absent': sorted(str(d) for d in absent)}
        return out

    # ================================================================ stamp
    @api.model
    def signature(self, employee, date_from, date_to):
        """A content fingerprint of every record the facts read (§3.6).

        Content, not write dates: the 15-minute calculation job rewrites a
        shift with the same values every run, which must not look like a
        change."""
        first = fields.Date.to_date(date_from)
        last = fields.Date.to_date(date_to) or first
        employee = employee.sudo()
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', '=', employee.id), ('date', '>=', first - timedelta(days=1)),
            ('date', '<=', last + timedelta(days=1))], order='id')
        reqs = self.env['hr.overtime.request'].sudo().search([
            ('employee_id', '=', employee.id), ('date', '>=', first), ('date', '<=', last)], order='id')
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id), ('request_date_from', '<=', last),
            ('request_date_to', '>=', first)], order='id')
        holidays = self._holidays(employee, first, last).get(employee.id) or {}
        tz = self._tz(employee)
        ulo = tz.localize(datetime.combine(first, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        uhi = tz.localize(datetime.combine(last + timedelta(days=1), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        loose = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id), ('pb_policy_roster_id', '=', False),
            ('check_in', '>=', ulo), ('check_in', '<', uhi)], order='id')
        comp = 'pb_comp_choice' in reqs._fields
        data = {
            'shifts': [(s.id, s.state, str(s.date), s.pb_policy_id.id, s.pb_policy_id.state,
                        s.pb_attendance_id.id, s.pb_attendance_id.pb_policy_proof or '',
                        s.pb_calculation_json or '', s.pb_day_kind) for s in shifts],
            'ot': [(r.id, r.state, r.overtime_type, r.approved_hours, r.bonus_hours, r.rate_multiplier,
                    r.pb_comp_choice if comp else '') for r in reqs],
            'leave': [(lv.id, lv.state, str(lv.request_date_from), str(lv.request_date_to),
                       lv.holiday_status_id.id, lv.number_of_days, lv.number_of_hours,
                       bool(lv.request_unit_half), bool(lv.request_unit_hours)) for lv in leaves],
            'holidays': sorted((str(d), n) for d, n in holidays.items()),
            'loose': [(a.id, str(a.check_in), str(a.check_out)) for a in loose],
        }
        raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    # ================================================================ readiness
    @api.model
    def readiness(self, config, employees, date_from, date_to):
        """The run's "Hours from the clocks" panel, as data (proposal §6)."""
        config = config.sudo()
        mode = config._pb_clock_mode(date_from, date_to)
        base = {'enabled': bool(config.pb_clock_from), 'mode': mode,
                'clock_from': fields.Date.to_string(config.pb_clock_from) if config.pb_clock_from else '',
                'scheme': config.display_name or config.name or ''}
        if mode != 'clock' or not config._pb_clock_rules():
            return dict(base, active=False)
        labels = self._blocker_labels()
        facts = self.facts_many(employees, date_from, date_to, live=False)
        groups = defaultdict(list)
        ready = 0
        for emp in employees.sudo():
            result = facts.get(emp.id) or {}
            if not result.get('blockers'):
                ready += 1
                continue
            for b in result['blockers']:
                groups[b['code']].append({'id': emp.id, 'name': emp.name or '',
                                          'dates': b['dates'][:6], 'text': b['text']})
        scheme_issues = config._pb_clock_refusals()
        order = list(labels)
        group_rows = [{'code': code, 'label': labels[code], 'count': len(rows),
                       'people': sorted(rows, key=lambda r: r['name'])[:50]}
                      for code, rows in sorted(groups.items(), key=lambda kv: order.index(kv[0]))]
        attention = len({p['id'] for rows in groups.values() for p in rows})
        return dict(base, active=True, total=len(employees), ready=ready, attention=attention,
                    groups=group_rows, scheme_issues=scheme_issues)

    @api.model
    def refusal_text(self, panel):
        """One grouped sentence for a run that cannot be worked out yet."""
        if not panel.get('active'):
            return ''
        if not panel.get('attention') and not panel.get('scheme_issues'):
            return ''
        parts = ['%s (%s)' % (g['label'], g['count']) for g in panel.get('groups') or []]
        lines = []
        for g in panel.get('groups') or []:
            for p in g['people'][:5]:
                lines.append('%s — %s' % (p['name'], p['text']))
        head = _("This pay run can't be worked out yet — %(n)s people need attention: %(what)s.",
                 n=panel.get('attention') or 0, what=' · '.join(parts)) if panel.get('attention') else ''
        body = '\n'.join(panel.get('scheme_issues') or [])
        return '\n\n'.join(p for p in (head, body, '\n'.join(lines)) if p)


class ClockFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    def _pb_clock_facts(self, employee, date_from, date_to, live=True):
        return self.env['pb.clock.payroll'].facts_many(employee, date_from, date_to, live=live).get(employee.id) or {}

    def _pb_clock_signature(self, employee, date_from, date_to):
        return self.env['pb.clock.payroll'].signature(employee, date_from, date_to)
