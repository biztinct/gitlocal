# -*- coding: utf-8 -*-
"""Leave that builds up — the earning job and its audit rows (WDGAP S5-A).

ENGINE A of the FACTS (a thin engine of our own, not core accrual plans):

* ONE native allocation per person, kind and LEAVE YEAR (the calendar year),
  marked with ``pb_ls_year``. Its ``number_of_days`` is never added to in
  place: it is SET to "everything posted for that year" (plus, when the kind
  lets people take days before they are earned, the rest of the year still to
  come). The posting rows are the authority; the allocation follows them.
* ONE audit row per person, kind and month (or year for "all at once each
  year"), keyed ``<employee>:<kind>:<YYYY-MM>`` / ``<employee>:<kind>:<YYYY>``
  with a unique index. A month already posted is never posted again, whoever
  runs the job and however often.
* Serialised per person and kind with the SAME advisory lock the Rize policy
  takes (``pb.leave.balance:<employee>:<kind>``), so the two can never write
  one person's balance at the same moment.
* Quiet: no email, no to-do, no chatter line (tracking off, the allocation is
  created the way an import creates one). Safe on an empty database: no kind
  that earns, no work.

Which months: a month is posted once it has ENDED ("earned so far"), from the
kind's "Build-up starts from" month, and never more than twelve months back.
"All at once each year" posts the year's days on the first run of the year,
or on the day the person becomes entitled (joiner, waiting period).

Service is measured from the employee's "Date of joining", or core's first
contract date where this version has that field. NEVER from the current
contract's start (ledger D27): somebody with no start date gets no extra days
for long service and no waiting-period kind, and is listed on the set-up
check instead.

Opening balances from People > Updates and Rize policy credits are separate
allocations (no ``pb_ls_year``): the job never reads or writes them as "this
year's", and never touches a kind bound to a leave policy.
"""
import logging
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CHUNK = 200
#: How far back the job looks for a month nobody posted (a server that was
#: down, a kind switched on with an earlier start month).
CATCH_UP_MONTHS = 12
#: The context every write of the job carries: no email, no to-do, no
#: chatter line. `import_file` is how core lets an allocation be created
#: without the "New allocation request" to-do (hr_leave_allocation.create).
QUIET = {
    'tracking_disable': True, 'mail_create_nolog': True, 'mail_notrack': True,
    'mail_create_nosubscribe': True, 'mail_activity_automation_skip': True,
    'import_file': True, 'pb_ls_engine': True,
}


def month_start(day):
    return day.replace(day=1)


def month_end(day):
    return month_start(day) + relativedelta(months=1, days=-1)


def completed_years(start, on):
    if not start or not on or on < start:
        return 0
    return relativedelta(on, start).years


class PbLeaveEarning(models.Model):
    _name = 'pb.leave.earning'
    _description = 'Leave earned (audit)'
    _order = 'period_start desc, id desc'

    employee_id = fields.Many2one('hr.employee', required=True, ondelete='restrict',
                                  index=True, readonly=True)
    leave_type_id = fields.Many2one('hr.leave.type', required=True, ondelete='restrict',
                                    index=True, readonly=True)
    company_id = fields.Many2one('res.company', readonly=True, index=True)
    period = fields.Selection([('month', 'Month'), ('year', 'Year')], required=True,
                              readonly=True)
    period_start = fields.Date(required=True, readonly=True, index=True)
    posting_key = fields.Char(required=True, readonly=True)
    days = fields.Float(readonly=True, digits=(8, 4))
    base_days = fields.Float(string='Days a year', readonly=True, digits=(6, 2))
    extra_days = fields.Float(string='Extra days a year', readonly=True, digits=(6, 2))
    service_years = fields.Integer(readonly=True)
    worked_share = fields.Float(readonly=True, digits=(6, 4))
    capped = fields.Boolean(readonly=True)
    allocation_id = fields.Many2one('hr.leave.allocation', readonly=True, ondelete='set null')

    _posting_once = models.Constraint(
        'unique(posting_key)', 'These days have already been added.')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('pb_ls_engine'):
            raise UserError(_('Earned days are added by the build-up job only.'))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_('Earned days are a permanent record and cannot be changed.'))

    def unlink(self):
        raise UserError(_('Earned days are a permanent record and cannot be deleted.'))

    # ================================================================ people
    @api.model
    def _service_start(self, emp):
        """The verified start of service, or None. Never the contract start."""
        for fname in ('date_of_joining', 'first_contract_date'):
            if fname in emp._fields:
                value = emp.sudo()[fname]
                if value:
                    return fields.Date.to_date(value)
        return None

    @api.model
    def _departure(self, emp):
        if 'departure_date' in emp._fields:
            value = emp.sudo().departure_date
            if value:
                return fields.Date.to_date(value)
        return None

    @api.model
    def _eligible_employees(self, kind, since):
        """Everybody the kind is for: its company (or every company for a
        shared kind), the kind's country, still here or left on/after
        `since` (a leaver still earns their last part-month)."""
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        domain = [('company_id', '=', kind.company_id.id)] if kind.company_id else []
        emps = Emp.search(domain + [('active', '=', True)], order='id')
        gone = Emp.search(domain + [('active', '=', False), ('departure_date', '>=', since)],
                          order='id')
        emps |= gone
        TO = self.env['pb.timeoff'].sudo()
        country = TO._type_country(kind)
        if country:
            emps = emps.filtered(lambda e: TO._emp_country(e) == country)
        return emps

    # ================================================================ maths
    @api.model
    def _month_share(self, kind, emp, first):
        """What `emp` earns of `kind` for the month starting `first`.

        None when nothing is due (not working that month, still waiting);
        ``{'no_start': True}`` when a waiting period cannot be measured;
        else ``{'days', 'base', 'extra', 'years', 'share', 'no_start'}``.
        """
        last = month_end(first)
        start = self._service_start(emp)
        gone = self._departure(emp)
        lo, hi = first, last
        if start and start > lo:
            lo = start
        if gone and gone < hi:
            hi = gone
        if kind.pb_ls_waiting_months:
            if not start:
                return {'no_start': True}
            lo = max(lo, start + relativedelta(months=kind.pb_ls_waiting_months))
        if lo > hi:
            return None
        share = ((hi - lo).days + 1) / float((last - first).days + 1)
        # A service step counts from the month the person reaches it.
        years = completed_years(start, last) if start else 0
        extra = kind._pb_ls_step_extra(years) if start else 0.0
        per_year = (kind.pb_ls_days_per_year or 0.0) + extra
        return {'days': round(per_year / 12.0 * share, 4),
                'base': kind.pb_ls_days_per_year or 0.0, 'extra': extra,
                'years': years, 'share': round(share, 4), 'no_start': not start}

    @api.model
    def _year_share(self, kind, emp, year):
        """The year's days for "all at once each year", from the day the
        person is entitled (joiner, waiting period) to the end of the year or
        their known leaving date. ``(due_on, values)``; values as above."""
        first, last = date(year, 1, 1), date(year, 12, 31)
        start = self._service_start(emp)
        gone = self._departure(emp)
        lo, hi = first, last
        if start and start > lo:
            lo = start
        if kind.pb_ls_waiting_months:
            if not start:
                return None, {'no_start': True}
            lo = max(lo, start + relativedelta(months=kind.pb_ls_waiting_months))
        if gone and gone < hi:
            hi = gone
        if lo > hi:
            return None, None
        share = ((hi - lo).days + 1) / float((last - first).days + 1)
        years = completed_years(start, lo) if start else 0
        extra = kind._pb_ls_step_extra(years) if start else 0.0
        per_year = (kind.pb_ls_days_per_year or 0.0) + extra
        return lo, {'days': round(per_year * share, 4),
                    'base': kind.pb_ls_days_per_year or 0.0, 'extra': extra,
                    'years': years, 'share': round(share, 4), 'no_start': not start}

    @api.model
    def _earn_from(self, kind, today):
        first = kind.pb_ls_earn_from and month_start(kind.pb_ls_earn_from)
        if not first:
            # Switched on without a start month (not through the screen):
            # start now and remember it, so nothing before today is added.
            first = month_start(today)
            kind.sudo().with_context(**QUIET).write({'pb_ls_earn_from': first})
        return first

    @api.model
    def _due_months(self, kind, today):
        first = self._earn_from(kind, today)
        floor = month_start(today) - relativedelta(months=CATCH_UP_MONTHS)
        m = max(first, floor)
        out = []
        while m < month_start(today):          # only months that have ended
            out.append(m)
            m += relativedelta(months=1)
        return out

    @api.model
    def _next_credit(self, kind, emp, today):
        """(date, days) of the next credit the job will add, or (None, 0)."""
        if not kind._pb_ls_earns():
            return None, 0.0
        if kind.pb_ls_earning == 'monthly':
            first = max(month_start(today), self._earn_from(kind, today))
            for _i in range(14):
                res = self._month_share(kind, emp, first)
                if res and 'days' in res and res['days'] > 0:
                    return first + relativedelta(months=1), res['days']
                if res is None and self._departure(emp) and self._departure(emp) < first:
                    return None, 0.0
                first += relativedelta(months=1)
            return None, 0.0
        year = today.year
        key = '%s:%s:%s' % (emp.id, kind.id, year)
        if self.sudo().search_count([('posting_key', '=', key)]):
            year += 1
        due, res = self._year_share(kind, emp, year)
        if res and 'days' in res and res['days'] > 0:
            return max(due, today), res['days']
        return None, 0.0

    # ============================================================ allocation
    @api.model
    def _year_allocation(self, kind, emp, year):
        return self.env['hr.leave.allocation'].sudo().with_context(active_test=False).search([
            ('employee_id', '=', emp.id), ('holiday_status_id', '=', kind.id),
            ('pb_ls_year', '=', year)], limit=1)

    @api.model
    def _posted(self, kind, emp, year):
        return self.sudo().search([
            ('employee_id', '=', emp.id), ('leave_type_id', '=', kind.id),
            ('period_start', '>=', date(year, 1, 1)),
            ('period_start', '<=', date(year, 12, 31))])

    @api.model
    def _ahead(self, kind, emp, year, done, today):
        """Days of the year still to come (months not posted yet), for a
        monthly kind that lets people take days before they are earned."""
        if not (kind.pb_ls_take_ahead and kind.pb_ls_earning == 'monthly'):
            return 0.0
        m = max(self._earn_from(kind, today), date(year, 1, 1))
        total = 0.0
        while m.year == year:
            if m not in done:
                res = self._month_share(kind, emp, m)
                if res and 'days' in res:
                    total += res['days']
            m += relativedelta(months=1)
        return round(total, 4)

    @api.model
    def _set_allocation(self, kind, emp, year, target):
        """Make the year's allocation hold `target` days. Created the first
        time there is something to hold; approved at once (the job is the
        authority, there is nobody to ask)."""
        # AS the system user, not merely sudo: hr_holidays_attendance refuses a
        # change to an approved allocation's days unless env.USER is a Time
        # Off officer, sudo or not — and "Add the finished months now" is
        # pressed by an HR manager who need not be one (found in the walk).
        Alloc = self.env['hr.leave.allocation'].with_user(SUPERUSER_ID).with_context(
            allowed_company_ids=[emp.company_id.id], **QUIET).sudo()
        alloc = self._year_allocation(kind, emp, year)
        if alloc:
            if target > 0 and abs((alloc.number_of_days or 0.0) - target) > 0.00001:
                Alloc.browse(alloc.id).write({'number_of_days': target})
            return alloc
        if target <= 0:
            return alloc
        date_to = False
        if kind.pb_ls_expire_months:
            date_to = date(year, 12, 31) + relativedelta(months=kind.pb_ls_expire_months)
        alloc = Alloc.create({
            'name': _('Earned leave %(year)s', year=year),
            'employee_id': emp.id, 'holiday_status_id': kind.id,
            'allocation_type': 'regular', 'number_of_days': target,
            'date_from': date(year, 1, 1), 'date_to': date_to,
            'pb_ls_year': year,
        })
        if alloc.state != 'validate':
            alloc.action_approve()
        if alloc.state != 'validate':
            raise UserError(_('The allocation needs a second approval in Time Off, so the '
                              'earned days were not added.'))
        return alloc

    # ================================================================ posting
    @api.model
    def _lock(self, kind, emp):
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                            ['pb.leave.balance:%s:%s' % (emp.id, kind.id)])

    @api.model
    def _balance_now(self, kind, emp, today):
        nums = self.env['pb.timeoff'].sudo()._pb_balance_numbers(
            [emp.id], [kind.id], today=today)
        return nums.get((emp.id, kind.id), {}).get('balance', 0.0)

    @api.model
    def _post_one(self, kind, emp, period, first, today):
        """Post one person's month (or year). Returns 'posted', 'exists',
        'none' (nothing due) or 'no_start'."""
        if period == 'month':
            key = '%s:%s:%s' % (emp.id, kind.id, first.strftime('%Y-%m'))
        else:
            key = '%s:%s:%s' % (emp.id, kind.id, first.year)
        self._lock(kind, emp)
        if self.sudo().search_count([('posting_key', '=', key)]):
            return 'exists'
        if period == 'month':
            res = self._month_share(kind, emp, first)
        else:
            due, res = self._year_share(kind, emp, first.year)
            if res and 'days' in res and due and due > today:
                return 'none'
        if not res:
            return 'none'
        if 'days' not in res:
            return 'no_start'
        year = first.year
        posted = self._posted(kind, emp, year)
        days, capped = res['days'], False
        if kind.pb_ls_max_balance:
            # the room left under the limit, counted on EARNED days only (the
            # part of the year held ahead is not the person's yet)
            alloc = self._year_allocation(kind, emp, year)
            held_ahead = 0.0
            if alloc:
                held_ahead = max(0.0, (alloc.number_of_days or 0.0) - sum(posted.mapped('days')))
            room = kind.pb_ls_max_balance - (self._balance_now(kind, emp, today) - held_ahead)
            if days > room:
                days, capped = round(max(0.0, room), 4), True
        done = {r.period_start for r in posted}
        if period == 'month':
            done.add(first)
        target = round(sum(posted.mapped('days')) + days
                       + self._ahead(kind, emp, year, done, today), 4)
        alloc = self._set_allocation(kind, emp, year, target)
        self.sudo().with_context(**QUIET).create({
            'employee_id': emp.id, 'leave_type_id': kind.id,
            'company_id': emp.company_id.id, 'period': period,
            'period_start': first, 'posting_key': key, 'days': days,
            'base_days': res['base'], 'extra_days': res['extra'],
            'service_years': res['years'], 'worked_share': res['share'],
            'capped': capped, 'allocation_id': alloc.id or False,
        })
        return 'posted'

    @api.model
    def _refresh_year(self, kind, emp, today):
        """Bring the current year's allocation in line with what was posted
        (and, for a take-ahead kind, the rest of the year). This is what puts
        the whole year's days there on 1 January, before any month ended, and
        what takes them back to "earned so far" when HR switches it off."""
        year = today.year
        self._lock(kind, emp)
        posted = self._posted(kind, emp, year)
        done = {r.period_start for r in posted}
        target = round(sum(posted.mapped('days'))
                       + self._ahead(kind, emp, year, done, today), 4)
        self._set_allocation(kind, emp, year, target)

    @api.model
    def _run_kind(self, kind, today, commit=False, employees=None):
        out = defaultdict(int)
        if not kind._pb_ls_earns():
            return out
        if kind.pb_ls_earning == 'monthly':
            jobs = [('month', m) for m in self._due_months(kind, today)]
        else:
            first = self._earn_from(kind, today)
            jobs = [('year', date(today.year, 1, 1))] if first.year <= today.year else []
        refresh = kind.pb_ls_earning == 'monthly'
        since = min([j[1] for j in jobs] + [month_start(today)])
        emps = employees if employees is not None else self._eligible_employees(kind, since)
        for i in range(0, len(emps), CHUNK):
            for emp in emps[i:i + CHUNK]:
                for period, first in jobs:
                    try:
                        with self.env.cr.savepoint():
                            out[self._post_one(kind, emp, period, first, today)] += 1
                    except Exception as e:      # noqa: BLE001 — one person never stops the run
                        out['failed'] += 1
                        _logger.warning('pb_leave_setup: %s / %s / %s not posted: %s',
                                        emp.id, kind.id, first, e)
                if refresh and (kind.pb_ls_take_ahead or self._year_allocation(kind, emp, today.year)):
                    try:
                        with self.env.cr.savepoint():
                            self._refresh_year(kind, emp, today)
                    except Exception as e:      # noqa: BLE001
                        out['failed'] += 1
                        _logger.warning('pb_leave_setup: year total %s / %s not set: %s',
                                        emp.id, kind.id, e)
            if commit:
                self.env.cr.commit()
        return out

    @api.model
    def _run(self, kinds=None, today=None, commit=False):
        today = fields.Date.to_date(today) if today else fields.Date.context_today(self)
        Kind = self.env['hr.leave.type'].sudo()
        if kinds is None:
            kinds = Kind.search([('pb_ls_earning', 'in', ('monthly', 'yearly'))])
        total = defaultdict(int)
        for kind in kinds.sudo():
            for k, v in self._run_kind(kind, today, commit=commit).items():
                total[k] += v
        return dict(total)

    @api.model
    def _cron_post(self):
        """The daily job. Quiet and safe on an empty database."""
        from odoo.modules.module import current_test
        res = self.sudo()._run(commit=not current_test)
        if res:
            _logger.info('pb_leave_setup: earned leave job %s', res)
        return res
