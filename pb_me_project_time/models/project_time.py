# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.me.project.time`` — the facade behind `/my/project-time` (ETP E3).

THE ONE RULE (ledger E-R2 / E-R3, E9)
-------------------------------------
Every public method takes the caller's OWN employee record, as the controller
resolved it from the session (``PbMePortal._ess_employee``), and re-checks it
in ``_own``: an ``hr.employee`` RECORD whose ``user_id`` is the caller. A JSON
id sent over RPC is not a record, so it is refused; another person's record is
refused. No route reads an employee from the request.

Reads and writes of ``account.analytic.line`` run under sudo AFTER that guard
(an employee login holds no right on timesheet lines, and the stock portal rows
ship inactive — E9). Under sudo the stock guards are off, so this module
re-states the ones it relies on:

* ownership — every search is keyed on ``employee_id = <own employee>``;
* who may log where — ``_projects`` / ``_key_ok``, the stock internal-user rule
  in Python (D2, ledger E10), re-checked on EVERY write;
* leave lines — lines made by time off (``holiday_id``) or a public holiday
  (``global_leave_id``, both from project_timesheet_holidays, read softly) are
  never written or unlinked; they are shown read-only;
* the time-off task is never pickable (stock refuses it only when not sudo);
* a whitelist — only ``project_id, task_id, date, unit_amount, name,
  employee_id`` ever reach ``create``; stock derives company and accounts;
* 24 hours per cell and per day.

There is no new table. A row with no hours is not stored anywhere: the page
passes it back in its ``rows`` parameter (D1/Scope).
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

#: Per-company switch (D3): '1' on, '0' off, UNSET = ON. A parameter, never a
#: column on res.company.
PARAM = 'pb_me_project_time.enabled.%s'
#: A cell, and a whole day, hold 24 hours at most.
MAX_DAY_HOURS = 24.0
#: "Has used project time lately" for the home card and the needs-you row.
ACTIVE_WEEKS = 8
#: "Fill the week with 8 h".
FILL_HOURS = 8.0
#: Empty rows a page may carry in its `rows` parameter.
MAX_EXTRA_ROWS = 40
#: Characters kept of a cell's one-line note.
NOTE_MAX = 300
#: Tasks the picker lists per project (a write is checked one key at a time,
#: so a longer project is still writable — the picker just stays usable).
PICKER_TASKS_PER_PROJECT = 200
EPS = 0.005

_RE_NUM = re.compile(r'^\d{1,3}(?:[.,]\d{1,4})?$')
_RE_HM = re.compile(r'^(\d{1,2})(?::|h)(\d{1,2})(?:m|min)?$')
_RE_H = re.compile(r'^(\d{1,3}(?:[.,]\d{1,4})?)h$')
_RE_M = re.compile(r'^(\d{1,4})(?:m|min)$')
_RE_KEY = re.compile(r'^(\d{1,9})-(\d{1,9})$')


def fmt_h(value):
    """Hours as the grid writes them: '8', '7.5', '1.25' — never '8.00'.
    The browser formats the same way (project_time.js `fmtHours`)."""
    value = round(float(value or 0.0), 2)
    if abs(value) < EPS:
        return '0'
    return ('%.2f' % value).rstrip('0').rstrip('.')


def key_str(key):
    return '%s-%s' % (key[0], key[1] or 0)


def parse_key(text):
    """'12-0' → (12, 0); anything else → None."""
    match = _RE_KEY.match((text or '').strip())
    if not match:
        return None
    pid, tid = int(match.group(1)), int(match.group(2))
    return (pid, tid) if pid else None


def parse_rows(text):
    """The page's `rows` parameter ('12-0,12-7') → [(12, 0), (12, 7)], each
    key once, at most MAX_EXTRA_ROWS. None stays None (= "propose last week's
    rows"); an empty string is an explicit empty list."""
    if text is None:
        return None
    keys = []
    for part in str(text).split(','):
        key = parse_key(part)
        if key and key not in keys:
            keys.append(key)
        if len(keys) >= MAX_EXTRA_ROWS:
            break
    return keys


class PbMeProjectTime(models.AbstractModel):
    _name = 'pb.me.project.time'
    _description = 'Project time on the self-service pages'

    # ================================================================ guards
    @api.model
    def _own(self, emp):
        """The caller's own employee, or AccessError. ``emp`` must be an
        ``hr.employee`` RECORD (an id sent over RPC is refused) linked to the
        calling user."""
        if (not isinstance(emp, models.BaseModel) or emp._name != 'hr.employee'
                or len(emp) != 1):
            raise AccessError(self.env._("That is not your employee record."))
        emp = emp.sudo()
        if not emp.active or emp.user_id.id != self.env.uid:
            raise AccessError(self.env._("That is not your employee record."))
        return emp

    @api.model
    def enabled(self, company):
        """Is project time on for ``company``? ON when the parameter is unset
        (D3). Exception-safe: templates call it."""
        try:
            company = company[:1]
            if not company:
                return False
            raw = self.env['ir.config_parameter'].sudo().get_param(PARAM % company.id)
            return (raw or '1').strip().lower() not in ('0', 'false', 'off')
        except Exception:               # noqa: BLE001 — a switch never 500s a page
            _logger.warning('pb_me_project_time: could not read the switch',
                            exc_info=True)
            return False

    @api.model
    def _days_unit(self, company):
        """A company that encodes timesheets in DAYS (non-goal: this page
        works in hours only)."""
        company = company[:1].sudo()
        if not company or 'timesheet_encode_uom_id' not in company._fields:
            return False
        day = self.env.ref('uom.product_uom_day', raise_if_not_found=False)
        return bool(day and company.timesheet_encode_uom_id == day)

    @api.model
    def page_state(self, company):
        """'ok', 'off' (the switch) or 'days' (encoded in days)."""
        if not self.enabled(company):
            return 'off'
        if self._days_unit(company):
            return 'days'
        return 'ok'

    @api.model
    def session_state(self):
        """The page state for the SESSION user's own employee (current company
        first, as `_ess_employee` resolves it): 'ok' / 'off' / 'days', or
        'none' without an employee. For templates — never raises."""
        try:
            Emp = self.env['hr.employee'].sudo()
            emp = Emp.search([('user_id', '=', self.env.uid),
                              ('company_id', '=', self.env.company.id)], limit=1) \
                or Emp.search([('user_id', '=', self.env.uid)], limit=1)
            if not emp:
                return 'none'
            return self.page_state(emp.company_id)
        except Exception:               # noqa: BLE001
            _logger.warning('pb_me_project_time: session state failed', exc_info=True)
            return 'none'

    @api.model
    def _require_open(self, emp):
        state = self.page_state(emp.company_id)
        if state == 'off':
            raise UserError(self.env._(
                "Project time is switched off for your company."))
        if state == 'days':
            raise UserError(self.env._(
                "Your company counts project time in days, which this page "
                "does not do yet."))

    # ============================================================== helpers
    @api.model
    def fmt_h(self, value):
        return fmt_h(value)

    @api.model
    def _tz(self, emp):
        for name in (emp.tz, self.env.user.tz,
                     emp.company_id.partner_id.tz if emp.company_id else None):
            if name:
                try:
                    return pytz.timezone(name)
                except Exception:       # noqa: BLE001
                    continue
        return pytz.UTC

    @api.model
    def _today(self, emp):
        """Today on the employee's wall clock (tests patch this)."""
        now = pytz.UTC.localize(fields.Datetime.now())
        return now.astimezone(self._tz(emp)).date()

    @api.model
    def _monday(self, day=False):
        try:
            d = fields.Date.to_date(day) if day else None
        except (TypeError, ValueError):
            d = None
        d = d or fields.Date.context_today(self)
        return d - timedelta(days=d.weekday())

    @api.model
    def _day(self, value):
        try:
            d = fields.Date.to_date(value)
        except (TypeError, ValueError):
            d = None
        if not d:
            raise UserError(self.env._("That day is not a real date."))
        return d

    @api.model
    def _key_ids(self, project_id, task_id):
        try:
            pid = int(project_id or 0)
            tid = int(task_id or 0)
        except (TypeError, ValueError):
            pid = 0
            tid = 0
        if pid <= 0 or tid < 0:
            raise UserError(self.env._("Pick a project from the list."))
        return pid, tid

    @api.model
    def _clean_note(self, note):
        text = ' '.join(str(note or '').split())[:NOTE_MAX]
        return '' if text == '/' else text

    @api.model
    def _note_of(self, line):
        name = (line[:1].name or '').strip() if line else ''
        return '' if name == '/' else name

    @api.model
    def _leave_fields(self):
        Line = self.env['account.analytic.line']
        return [f for f in ('holiday_id', 'global_leave_id') if f in Line._fields]

    @api.model
    def _is_leave(self, line):
        return any(line[f] for f in self._leave_fields())

    @api.model
    def _leave_name(self, line):
        if 'holiday_id' in line._fields and line.holiday_id:
            return line.holiday_id.holiday_status_id.name or line.name or ''
        if 'global_leave_id' in line._fields and line.global_leave_id:
            return line.global_leave_id.name or line.name or ''
        return line.name or ''

    @api.model
    def _not_leave_domain(self):
        return [(f, '=', False) for f in self._leave_fields()]

    @api.model
    def _line_model(self, emp):
        """`account.analytic.line` under sudo in a CLEAN context: the employee's
        company as the only allowed company (stock create looks the employee up
        among `env.companies`), the reader's language — and nothing a request
        could have added (no `default_*` key ever reaches create)."""
        ctx = {
            'lang': self.env.context.get('lang') or self.env.lang,
            'tz': emp.tz or self.env.context.get('tz'),
            'allowed_company_ids': [emp.company_id.id],
        }
        return self.env(context=ctx, su=True)['account.analytic.line']

    @api.model
    def _lines(self, emp, first, last, extra=None):
        """The person's OWN project lines between two dates (leave included)."""
        return self._line_model(emp).search([
            ('employee_id', '=', emp.id), ('project_id', '!=', False),
            ('date', '>=', first), ('date', '<=', last),
        ] + (extra or []), order='date, id')

    @api.model
    def _key_lines(self, emp, pid, tid, day):
        """The non-leave own lines of one cell (usually 0 or 1; more only when
        the backend made several — see `set_cell`)."""
        return self._line_model(emp).search([
            ('employee_id', '=', emp.id), ('project_id', '=', pid),
            ('task_id', '=', tid or False), ('date', '=', day),
        ] + self._not_leave_domain(), order='id')

    # ========================================================= who may log
    @api.model
    def _projects(self, emp):
        """The projects ``emp`` may log time on (D2, ledger E10): the stock
        internal-user rule re-stated — active, timesheets allowed, not a
        template, of the employee's company or of none, and visible to all
        employees or followed by the employee's partner. Ordered: the
        company's Internal project first, then by name."""
        Project = self.env['project.project'].sudo()
        domain = [('active', '=', True), ('allow_timesheets', '=', True),
                  ('company_id', 'in', [False, emp.company_id.id])]
        if 'is_template' in Project._fields:
            domain.append(('is_template', '=', False))
        projects = Project.search(domain)
        partner = emp.user_id.partner_id
        followed = set()
        if partner and projects:
            followed = set(self.env['mail.followers'].sudo().search([
                ('res_model', '=', 'project.project'),
                ('partner_id', '=', partner.id),
                ('res_id', 'in', projects.ids)]).mapped('res_id'))
        projects = projects.filtered(
            lambda p: p.privacy_visibility in ('employees', 'portal')
            or p.id in followed)
        internal = self._internal_project(emp)
        return projects.sorted(
            lambda p: (p != internal, (p.name or '').casefold(), p.id))

    @api.model
    def _internal_project(self, emp):
        company = emp.company_id.sudo()
        if 'internal_project_id' in company._fields:
            return company.internal_project_id
        return self.env['project.project'].sudo().browse()

    @api.model
    def _leave_task_ids(self, companies):
        """The time-off task of each company (project_timesheet_holidays) —
        never pickable: stock refuses a line there only when not sudo."""
        ids = set()
        for company in companies.sudo():
            if 'leave_timesheet_task_id' in company._fields \
                    and company.leave_timesheet_task_id:
                ids.add(company.leave_timesheet_task_id.id)
        return ids

    @api.model
    def _timeoff_task_ids(self, emp, tasks):
        """The time-off tasks among the companies in play: the employee's
        company and the companies of ``tasks`` and their projects (D2: "minus
        project.company_id.leave_timesheet_task_id"). A task that merely
        CARRIES a leave line is not excluded: its other lines are ordinary
        work, and the leave lines themselves are never written (E9)."""
        return self._leave_task_ids(
            emp.company_id | tasks.mapped('company_id')
            | tasks.mapped('project_id.company_id'))

    @api.model
    def _task_domain(self, project_ids):
        Task = self.env['project.task']
        domain = [('project_id', 'in', list(project_ids)), ('active', '=', True)]
        if 'is_template' in Task._fields:
            domain.append(('is_template', '=', False))
        return domain

    @api.model
    def _key_ok(self, emp, pid, tid, projects=None):
        """May ``emp`` write a line on (project, task)? Re-checked on every
        write: a pickable project, and (when a task is given) an active task
        of that project that is not a template and not a time-off task."""
        projects = self._projects(emp) if projects is None else projects
        if pid not in projects.ids:
            return False
        if not tid:
            return True
        task = self.env['project.task'].sudo().search(
            self._task_domain([pid]) + [('id', '=', tid)], limit=1)
        if not task:
            return False
        return tid not in self._timeoff_task_ids(emp, task)

    @api.model
    def pickable_projects(self, emp, query=None):
        """The picker: ``[{company, projects: [{id, key, name, internal,
        tasks: [{id, key, name}]}]}]`` — the employee's company first (its
        Internal project first, Training / Meeting at the top of it), then the
        projects that belong to no company. Closed tasks and the time-off task
        are left out. ``query`` filters on project or task name."""
        emp = self._own(emp)
        projects = self._projects(emp)
        internal = self._internal_project(emp)
        Task = self.env['project.task'].sudo()
        tasks = Task.search(self._task_domain(projects.ids), order='sequence, id')
        if 'state' in Task._fields:
            try:
                from odoo.addons.project.models.project_task import CLOSED_STATES
                tasks = tasks.filtered(lambda t: t.state not in CLOSED_STATES)
            except ImportError:         # pragma: no cover
                pass
        timeoff = self._timeoff_task_ids(emp, tasks)
        by_project = defaultdict(list)
        for task in tasks:
            if task.id not in timeoff \
                    and len(by_project[task.project_id.id]) < PICKER_TASKS_PER_PROJECT:
                by_project[task.project_id.id].append(task)
        q = ' '.join((query or '').split()).casefold()
        groups = []
        index = {}
        for project in projects:
            name = project.name or ''
            task_rows = [{'id': t.id, 'key': key_str((project.id, t.id)),
                          'name': t.name or ''} for t in by_project[project.id]]
            if q and q not in name.casefold():
                task_rows = [t for t in task_rows if q in t['name'].casefold()]
                if not task_rows:
                    continue
            company = project.company_id
            gkey = company.id or 0
            if gkey not in index:
                index[gkey] = len(groups)
                groups.append({
                    'company': company.name if company
                    else self.env._("Projects shared by every company"),
                    'company_id': gkey,
                    'projects': [],
                })
            groups[index[gkey]]['projects'].append({
                'id': project.id, 'key': key_str((project.id, 0)), 'name': name,
                'internal': project == internal, 'tasks': task_rows,
            })
        own = emp.company_id.id
        groups.sort(key=lambda g: (g['company_id'] != own, g['company_id'] == 0))
        return groups

    # ============================================================== hours
    @api.model
    def parse_hours(self, text):
        """'8' → 8.0, '7.5' / '7,5' → 7.5, '1:30' / '1h30' → 1.5, '0:45' →
        0.75, '45m' → 0.75, '' → 0. Negative, over 24 or unreadable → a plain
        UserError. Rounded to 2 decimals."""
        _ = self.env._
        if text is None or text is False:
            return 0.0
        if isinstance(text, bool):
            raise UserError(_("Type hours like 8, 7.5 or 1:30."))
        if isinstance(text, (int, float)):
            value = float(text)
            if value != value:          # NaN
                raise UserError(_("Type hours like 8, 7.5 or 1:30."))
        else:
            s = ''.join(str(text).split()).lower()
            if not s:
                return 0.0
            if s.startswith('-'):
                raise UserError(_("Hours cannot be below zero."))
            if _RE_NUM.match(s):
                value = float(s.replace(',', '.'))
            elif _RE_HM.match(s):
                h, m = _RE_HM.match(s).groups()
                if int(m) >= 60:
                    raise UserError(_("Minutes go up to 59, like 1:45."))
                value = int(h) + int(m) / 60.0
            elif _RE_H.match(s):
                value = float(_RE_H.match(s).group(1).replace(',', '.'))
            elif _RE_M.match(s):
                value = int(_RE_M.match(s).group(1)) / 60.0
            else:
                raise UserError(_("Type hours like 8, 7.5 or 1:30."))
        if value < 0:
            raise UserError(_("Hours cannot be below zero."))
        if value > MAX_DAY_HOURS + EPS:
            raise UserError(_("One cell holds 24 hours at most."))
        return round(value, 2)

    # ============================================================ targets
    @api.model
    def _targets(self, emp, monday):
        """Expected hours per day from the employee's working schedule (D4),
        on the employee's wall clock: the schedule's work intervals minus its
        leaves — a public holiday (the calendar's global leaves) or approved
        time off makes the day 0. No schedule (fully flexible) → 0 every day.
        Never raises: a broken schedule gives zeros and a warning."""
        days = [monday + timedelta(days=i) for i in range(7)]
        out = {d: 0.0 for d in days}
        cal = emp.resource_calendar_id.sudo()
        if not cal or not emp.resource_id:
            return out
        try:
            tz = self._tz(emp)
            start = tz.localize(datetime.combine(days[0], time.min))
            end = tz.localize(datetime.combine(days[-1], time.max))
            if cal.flexible_hours:
                per_day = cal.hours_per_day or 0.0
                leaves = cal._leave_intervals_batch(
                    start, end, resources=emp.resource_id, tz=tz)[emp.resource_id.id]
                off = {s.astimezone(tz).date() for s, _e, _m in leaves}
                for d in days:
                    if d.weekday() < 5 and d not in off:
                        out[d] = per_day
                return out
            intervals = cal._work_intervals_batch(
                start, end, resources=emp.resource_id, tz=tz)[emp.resource_id.id]
            for s, e, _meta in intervals:
                d = s.astimezone(tz).date()
                if d in out:
                    out[d] += (e - s).total_seconds() / 3600.0
        except Exception:               # noqa: BLE001 — a target never 500s a page
            _logger.warning('pb_me_project_time: could not read the working '
                            'schedule of employee %s', emp.id, exc_info=True)
            return {d: 0.0 for d in days}
        return {d: round(h, 2) for d, h in out.items()}

    # =============================================================== week
    @api.model
    def _state(self, logged, target, leave_hours=0.0):
        if leave_hours > EPS and logged <= EPS:
            return 'leave'
        if target <= EPS:
            # No target (a weekend, a day off the schedule): hours logged
            # there are simply hours, never "over" — amber would read as a
            # warning to somebody who chose to work a Saturday (Fable, E3
            # review).
            return 'at' if logged > EPS else 'none'
        if logged < target - EPS:
            return 'under'
        if logged <= target + EPS:
            return 'at'
        return 'over'

    @api.model
    def _pct(self, logged, target):
        if target <= EPS:
            return 100.0 if logged > EPS else 0.0
        return round(min(100.0, logged * 100.0 / target), 1)

    @api.model
    def get_week(self, emp, monday=False, rows=None, today=None):
        """The week grid's facts (Scope): ``{week: {monday, sunday, days: [...],
        total, logged, target, leave_hours, pct, state, prev, next,
        is_current}, rows: [{key, kind, project_id, task_id, label, sub,
        company, cells: [{iso, hours, note, line_ids, locked}], total,
        pickable, has_lines}], can_copy_last_week, empty_ever, rows_param}``.

        ``rows`` (a list of (project, task) keys, or None): the empty rows the
        page carries. None = propose last week's rows ("rows persist for the
        week they have hours in and are proposed again next week").

        Day ``total`` counts every line, leave included; ``logged`` counts
        the person's own project hours (what the ring and the bars compare
        with the day's ``target``)."""
        emp = self._own(emp)
        _ = self.env._
        monday = self._monday(monday)
        sunday = monday + timedelta(days=6)
        today = today or self._today(emp)
        dates = [monday + timedelta(days=i) for i in range(7)]
        targets = self._targets(emp, monday)
        lines = self._lines(emp, monday - timedelta(days=7), sunday)

        cells = {}
        keys = []
        prev_keys = []
        prev_cells = set()
        leave_by_day = defaultdict(list)
        leave_hours = defaultdict(float)
        for line in lines:
            leave = self._is_leave(line)
            key = (line.project_id.id, line.task_id.id or 0)
            if line.date < monday:
                if not leave:
                    if key not in prev_keys:
                        prev_keys.append(key)
                    prev_cells.add((key, line.date + timedelta(days=7)))
                continue
            if leave:
                leave_by_day[line.date].append({
                    'name': self._leave_name(line), 'hours': line.unit_amount,
                    'line_id': line.id})
                leave_hours[line.date] += line.unit_amount
                continue
            if key not in keys:
                keys.append(key)
            cell = cells.setdefault((key, line.date),
                                    {'hours': 0.0, 'note': '', 'line_ids': []})
            # several stock lines on one key (made in the backend): the grid
            # shows their SUM; a write keeps the first and removes the rest
            cell['hours'] += line.unit_amount
            cell['line_ids'].append(line.id)
            if not cell['note']:
                cell['note'] = self._note_of(line)

        projects = self._projects(emp)
        with_lines = list(keys)
        extra = prev_keys if rows is None else list(rows or [])
        empty_keys = []
        for key in extra[:MAX_EXTRA_ROWS]:
            if key and key not in keys and self._key_ok(emp, key[0], key[1], projects):
                keys.append(key)
                empty_keys.append(key)

        Project = self.env['project.project'].sudo()
        Task = self.env['project.task'].sudo()
        internal = self._internal_project(emp)
        timeoff = self._timeoff_task_ids(
            emp, Task.browse([k[1] for k in keys if k[1]]).exists())
        row_list = []
        for key in keys:
            project = Project.browse(key[0]).exists()
            task = Task.browse(key[1]).exists() if key[1] else Task
            if not project:
                continue
            pickable = (project.id in projects.ids
                        and (not key[1] or (task and task.active
                                            and task.project_id == project
                                            and key[1] not in timeoff)))
            row_cells = []
            for d in dates:
                c = cells.get((key, d)) or {}
                row_cells.append({
                    'iso': d.isoformat(),
                    'hours': round(c.get('hours', 0.0), 2),
                    'note': c.get('note', ''),
                    'line_ids': c.get('line_ids', []),
                    'locked': not pickable,
                })
            row_list.append({
                'key': key_str(key), 'kind': 'project',
                'project_id': project.id, 'task_id': key[1] or False,
                'label': project.name or '',
                'sub': task.name if task else '',
                'company': project.company_id.name or '',
                'internal': project == internal,
                'cells': row_cells,
                'total': round(sum(c['hours'] for c in row_cells), 2),
                'pickable': bool(pickable),
                'has_lines': key in with_lines,
                '_sort': (project != internal, (project.name or '').casefold(),
                          project.id, task.sequence if task else -1,
                          (task.name or '').casefold() if task else ''),
            })
        row_list.sort(key=lambda r: r['_sort'])
        for row in row_list:
            row.pop('_sort')

        if leave_by_day:
            leave_cells = []
            for d in dates:
                items = leave_by_day.get(d, [])
                leave_cells.append({
                    'iso': d.isoformat(),
                    'hours': round(sum(i['hours'] for i in items), 2),
                    'note': ', '.join(dict.fromkeys(i['name'] for i in items if i['name'])),
                    'line_ids': [i['line_id'] for i in items],
                    'locked': True,
                })
            row_list.append({
                'key': 'leave', 'kind': 'leave', 'project_id': False,
                'task_id': False, 'label': _("Time off and public holidays"),
                'sub': '', 'company': '', 'internal': False,
                'cells': leave_cells,
                'total': round(sum(c['hours'] for c in leave_cells), 2),
                'pickable': False, 'has_lines': True,
            })

        days = []
        for i, d in enumerate(dates):
            logged = round(sum(r['cells'][i]['hours'] for r in row_list
                               if r['kind'] == 'project'), 2)
            lh = round(leave_hours.get(d, 0.0), 2)
            target = targets.get(d, 0.0)
            days.append({
                'index': i,
                'iso': d.isoformat(),
                'date': d,
                'label': format_date(self.env, d, date_format='EEE'),
                'long': format_date(self.env, d, date_format='EEEE d MMMM'),
                'dnum': d.day,
                'is_today': d == today,
                'is_past': d < today,
                'is_weekend': d.weekday() >= 5,
                'target': target,
                'total': round(logged + lh, 2),
                'logged': logged,
                'leave_hours': lh,
                'leave': [{'name': x['name'], 'hours': x['hours']}
                          for x in leave_by_day.get(d, [])],
                'state': self._state(logged, target, lh),
                'pct': self._pct(logged, target),
            })
        logged = round(sum(d['logged'] for d in days), 2)
        target = round(sum(d['target'] for d in days), 2)
        week_leave = round(sum(d['leave_hours'] for d in days), 2)
        current_monday = self._monday(today)

        leave_days = {d for d, items in leave_by_day.items() if items}
        can_copy = any(
            (key, d) not in cells and d not in leave_days
            and self._key_ok(emp, key[0], key[1], projects)
            for (key, d) in prev_cells)
        empty_ever = not with_lines and not prev_keys and not self._line_model(emp) \
            .search_count([('employee_id', '=', emp.id), ('project_id', '!=', False)]
                          + self._not_leave_domain(), limit=1)
        return {
            'week': {
                'monday': monday.isoformat(), 'sunday': sunday.isoformat(),
                'monday_date': monday, 'sunday_date': sunday,
                'days': days,
                'total': round(logged + week_leave, 2),
                'logged': logged, 'target': target, 'leave_hours': week_leave,
                'pct': self._pct(logged, target),
                'state': self._state(logged, target),
                'prev': (monday - timedelta(days=7)).isoformat(),
                'next': (monday + timedelta(days=7)).isoformat(),
                'this': current_monday.isoformat(),
                'is_current': monday == current_monday,
            },
            'rows': row_list,
            'can_copy_last_week': bool(can_copy),
            'empty_ever': bool(empty_ever),
            'rows_param': ','.join(key_str(k) for k in empty_keys),
            'today': today.isoformat(),
        }

    @api.model
    def _numbers(self, emp, pid, tid, day):
        """What a cell save answers with: the row, the day and the week."""
        data = self.get_week(emp, day, rows=[])
        week = data['week']
        idx = (day - fields.Date.to_date(week['monday'])).days
        dayinfo = week['days'][idx]
        key = key_str((pid, tid))
        row = next((r for r in data['rows'] if r['key'] == key), None)
        cell = row['cells'][idx] if row else {'hours': 0.0, 'note': ''}
        return {
            'ok': True, 'error': False,
            'key': key, 'date': day.isoformat(),
            'hours': cell['hours'], 'hours_text': fmt_h(cell['hours']) if cell['hours'] else '',
            'note': cell['note'],
            'row_total': row['total'] if row else 0.0,
            'day_total': dayinfo['total'], 'day_logged': dayinfo['logged'],
            'day_target': dayinfo['target'], 'day_state': dayinfo['state'],
            'day_pct': dayinfo['pct'],
            'week_total': week['total'], 'week_logged': week['logged'],
            'week_target': week['target'], 'week_state': week['state'],
            'week_pct': week['pct'],
        }

    # ============================================================== writes
    @api.model
    def set_cell(self, emp, project_id, task_id, date, hours, note=None):
        """Write ONE cell for the caller: find the line by (employee, project,
        task, date) among the NON-leave lines, update its hours / note, create
        it when absent, unlink it when the value is 0 and there is no note.
        ``note=None`` keeps the cell's note; '' clears it.

        More than one stock line for the same key (made in the backend): the
        grid shows their sum; this write keeps the FIRST line with the new
        value and unlinks the others. Leave lines are never touched — a cell
        on a key that also has a leave line writes its own separate line."""
        emp = self._own(emp)
        _ = self.env._
        self._require_open(emp)
        pid, tid = self._key_ids(project_id, task_id)
        day = self._day(date)
        if not self._key_ok(emp, pid, tid):
            raise UserError(_("You cannot log time on that project. Pick one "
                              "from the list."))
        value = self.parse_hours(hours)
        Line = self._line_model(emp)
        mine = self._key_lines(emp, pid, tid, day)
        new_note = self._note_of(mine[:1]) if note is None else self._clean_note(note)
        if value > EPS:
            day_lines = Line.search([('employee_id', '=', emp.id),
                                     ('project_id', '!=', False),
                                     ('date', '=', day)])
            others = sum((day_lines - mine).mapped('unit_amount'))
            if others + value > MAX_DAY_HOURS + EPS:
                raise UserError(_(
                    "That would make %(total)s h on %(day)s. A day has 24 hours.",
                    total=fmt_h(others + value),
                    day=format_date(self.env, day, date_format='EEEE d MMMM')))
        if value <= EPS and not new_note:
            mine.unlink()
        elif mine:
            mine[0].write({'unit_amount': value, 'name': new_note or '/'})
            (mine - mine[0]).unlink()
        else:
            Line.create({
                'project_id': pid,
                'task_id': tid or False,
                'date': day,
                'unit_amount': value,
                'name': new_note or '/',
                'employee_id': emp.id,
            })
        return self._numbers(emp, pid, tid, day)

    @api.model
    def save_week(self, emp, monday, cells):
        """The no-JS "Save week": ``cells`` = ``[{project_id, task_id, date,
        hours, note}]`` (``note`` None = not sent). Only cells that changed are
        written, through `set_cell`, each in its own savepoint; decreases go
        first so moving hours between rows never trips the day limit.
        Returns ``{saved, errors: [{key, date, value, error}]}``."""
        emp = self._own(emp)
        self._require_open(emp)
        monday = self._monday(monday)
        dates = {monday + timedelta(days=i) for i in range(7)}
        data = self.get_week(emp, monday, rows=[])
        current = {}
        for row in data['rows']:
            if row['kind'] != 'project':
                continue
            for c in row['cells']:
                current[(row['key'], c['iso'])] = (c['hours'], c['note'])
        todo, errors = [], []
        for cell in cells or []:
            try:
                pid, tid = self._key_ids(cell.get('project_id'), cell.get('task_id'))
                day = self._day(cell.get('date'))
            except UserError:
                continue
            if day not in dates:
                continue
            key = key_str((pid, tid))
            raw = cell.get('hours')
            cur_h, cur_n = current.get((key, day.isoformat()), (0.0, ''))
            try:
                # an hours field that was not sent keeps the cell's hours
                value = cur_h if raw is None else self.parse_hours(raw)
            except UserError as e:
                errors.append({'key': key, 'date': day.isoformat(),
                               'value': raw or '', 'error': e.args[0]})
                continue
            note = cell.get('note')
            same_note = note is None or self._clean_note(note) == cur_n
            if abs(value - cur_h) < EPS and same_note:
                continue
            todo.append((value - cur_h, pid, tid, day, value, note, raw))
        todo.sort(key=lambda t: t[0])
        saved = 0
        for _delta, pid, tid, day, value, note, raw in todo:
            try:
                with self.env.cr.savepoint():
                    self.set_cell(emp, pid, tid, day, value, note)
                saved += 1
            except (UserError, ValidationError, AccessError) as e:
                errors.append({'key': key_str((pid, tid)), 'date': day.isoformat(),
                               'value': raw or '', 'error': e.args[0]})
        return {'saved': saved, 'errors': errors}

    @api.model
    def add_row(self, emp, project_id, task_id, monday):
        """A row for (project, task) in the week of ``monday``: validated as
        pickable and returned with its (empty or filled) cells. Nothing is
        stored — the page carries the row in its ``rows`` parameter."""
        emp = self._own(emp)
        self._require_open(emp)
        pid, tid = self._key_ids(project_id, task_id)
        if not self._key_ok(emp, pid, tid):
            raise UserError(self.env._(
                "You cannot log time on that project. Pick one from the list."))
        data = self.get_week(emp, monday, rows=[(pid, tid)])
        key = key_str((pid, tid))
        return next(r for r in data['rows'] if r['key'] == key)

    @api.model
    def copy_last_week(self, emp, monday):
        """"Copy last week": every hour logged last week lands on the same
        weekday of this week — only in EMPTY cells (a cell with a value or a
        note keeps it), never on a day with time off, never on a project the
        person may no longer log on; notes are not copied. Returns
        ``{copied, skipped, fresh: ['<key>|<iso>']}``."""
        emp = self._own(emp)
        self._require_open(emp)
        monday = self._monday(monday)
        lines = self._lines(emp, monday - timedelta(days=7), monday + timedelta(days=6))
        projects = self._projects(emp)
        have, leave_days = set(), set()
        src = {}
        for line in lines:
            key = (line.project_id.id, line.task_id.id or 0)
            if line.date >= monday:
                if self._is_leave(line):
                    leave_days.add(line.date)
                else:
                    have.add((key, line.date))
                continue
            if self._is_leave(line):
                continue
            src[(key, line.date)] = src.get((key, line.date), 0.0) + line.unit_amount
        copied, skipped, fresh = 0, 0, []
        for (key, d), hours in src.items():
            target = d + timedelta(days=7)
            if hours <= EPS or (key, target) in have or target in leave_days:
                continue
            if not self._key_ok(emp, key[0], key[1], projects):
                skipped += 1
                continue
            try:
                with self.env.cr.savepoint():
                    self.set_cell(emp, key[0], key[1], target, round(hours, 2), None)
                copied += 1
                fresh.append('%s|%s' % (key_str(key), target.isoformat()))
            except (UserError, ValidationError):
                skipped += 1
        return {'copied': copied, 'skipped': skipped, 'fresh': fresh}

    @api.model
    def fill_row(self, emp, project_id, task_id, monday, hours=FILL_HOURS):
        """"Fill the week with 8 h" on one row: only EMPTY cells, only working
        days (a target above 0). Returns ``{filled, skipped, fresh}``."""
        emp = self._own(emp)
        self._require_open(emp)
        pid, tid = self._key_ids(project_id, task_id)
        if not self._key_ok(emp, pid, tid):
            raise UserError(self.env._(
                "You cannot log time on that project. Pick one from the list."))
        value = self.parse_hours(hours)
        if value <= EPS:
            raise UserError(self.env._("Type hours like 8, 7.5 or 1:30."))
        monday = self._monday(monday)
        data = self.get_week(emp, monday, rows=[(pid, tid)])
        key = key_str((pid, tid))
        row = next(r for r in data['rows'] if r['key'] == key)
        filled, skipped, fresh = 0, 0, []
        for day, cell in zip(data['week']['days'], row['cells']):
            if day['target'] <= EPS or cell['line_ids']:
                continue
            try:
                with self.env.cr.savepoint():
                    self.set_cell(emp, pid, tid, day['date'], value, None)
                filled += 1
                fresh.append('%s|%s' % (key, day['iso']))
            except (UserError, ValidationError):
                skipped += 1
        return {'filled': filled, 'skipped': skipped, 'fresh': fresh}

    # ================================================================ home
    @api.model
    def week_summary(self, emp, today=None):
        """The home's "Project time this week" facts, or None — quiet at zero:
        None when the page is off for the company, or when the person has not
        logged any project time in the last eight weeks. ``missing`` counts the
        PAST working days of this week (target > 0) with nothing logged."""
        emp = self._own(emp)
        if self.page_state(emp.company_id) != 'ok':
            return None
        today = today or self._today(emp)
        since = today - timedelta(weeks=ACTIVE_WEEKS)
        if not self._line_model(emp).search_count(
                [('employee_id', '=', emp.id), ('project_id', '!=', False),
                 ('date', '>=', since)] + self._not_leave_domain(), limit=1):
            return None
        week = self.get_week(emp, today, rows=[], today=today)['week']
        missing = [d for d in week['days']
                   if d['is_past'] and d['target'] > EPS and d['logged'] <= EPS]
        return {
            'week': week,
            'logged': week['logged'], 'target': week['target'],
            'missing': len(missing),
            'url': '/my/project-time',
        }
