# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.attendance.flow — RPC facade for the Attendance Control cockpit (Phase G §3).

An AbstractModel (no table) exposing the exceptions queue, the corrections
pipeline (with the approval stepper), compliance KPIs and the import stepper to
the bespoke OWL screen. Reads are one-permission-world sudo (C18.17); correction
STATE actions run as the real user so the approval log is truthful and
``_approval_can`` decides authorization (never sudo'd).
"""

from datetime import date, datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_OFFICER_GROUPS = ('hr_attendance.group_hr_attendance_officer',
                   'hr_attendance.group_hr_attendance_manager',
                   'om_hr_payroll.group_hr_payroll_manager',
                   'hr.group_hr_manager')
_WINDOW_DAYS = 14          # exceptions feed look-back
_MAX_COHORT = 400          # bound the feed cohort (surfaced when truncated)


class PbAttendanceFlow(models.AbstractModel):
    _name = 'pb.attendance.flow'
    _description = 'Attendance Control Cockpit'

    # ------------------------------------------------------------- access
    @api.model
    def _require(self):
        if not self.env.user.has_group('base.group_user'):
            raise AccessError(_("Attendance Control is for internal users."))

    def _is_officer(self):
        u = self.env.user
        if u._is_admin():
            return True
        for g in _OFFICER_GROUPS:
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    # ------------------------------------------------------------- cohort
    def _cohort(self, df, dt, department_id=False):
        """Employees the feed covers: for an officer, everyone in-company with a
        published shift in the window or an open punch; for anyone else, just
        themselves. Bounded to _MAX_COHORT.

        `department_id` narrows the cohort to the Time hub's context department
        (W4). The Time hub's ribbon calls THIS method with THIS window so its
        count is the same number the Exceptions lens shows — the two must never
        disagree, so they share one cohort definition rather than two.
        """
        if not self._is_officer():
            return self.env.user.employee_id, 0
        co_ids = self.env.companies.ids or [self.env.company.id]
        Emp = self.env['hr.employee'].sudo()
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('company_id', 'in', co_ids),
            ('date', '>=', df), ('date', '<=', dt),
            ('state', '=', 'published'),
        ])
        emp_ids = set(shifts.mapped('employee_id').ids)
        opens = self.env['hr.attendance'].sudo().search([
            ('employee_id.company_id', 'in', co_ids),
            ('check_out', '=', False),
            ('check_in', '>=', datetime.combine(df - timedelta(days=2), time.min)),
        ])
        emp_ids |= set(opens.mapped('employee_id').ids)
        emps = Emp.browse(sorted(emp_ids)).exists()
        if department_id:
            emps = emps.filtered(
                lambda e: e.department_id.id == int(department_id))
        truncated = 0
        if len(emps) > _MAX_COHORT:
            truncated = len(emps) - _MAX_COHORT
            emps = emps[:_MAX_COHORT]
        return emps, truncated

    # ------------------------------------------------------------- KPIs
    def _late_pct_week(self, emps, df=False, dt=False):
        monday = df or (date.today() - timedelta(days=date.today().weekday()))
        sunday = dt or (monday + timedelta(days=6))
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('date', '>=', monday), ('date', '<=', sunday),
            ('state', '=', 'published'),
        ])
        total = len(shifts)
        if not total:
            return 0
        late = len(shifts.filtered(lambda s: s.compliance_status in ('late', 'early_leave')))
        return round(100.0 * late / total)

    def _imports_this_month(self):
        first = date.today().replace(day=1)
        return self.env['hr.attendance'].sudo().search_count([
            ('pb_entry_source', '=', 'import'),
            ('create_date', '>=', datetime.combine(first, time.min)),
        ])

    # ------------------------------------------------------------- load
    @api.model
    def get_control_data(self, date_from=False, date_to=False, department_id=False):
        """Board payload.

        Called with no arguments (the standalone Attendance Control action) the
        window is the historical rolling 14 days over every in-company employee
        — unchanged. The Time hub passes its shared context week + department
        instead (W4), which is also what makes the hub ribbon's count and this
        board's count the same number by construction.
        """
        self._require()
        dt = fields.Date.to_date(date_to) or date.today()
        df = fields.Date.to_date(date_from) or (dt - timedelta(days=_WINDOW_DAYS - 1))
        if df > dt:
            df, dt = dt, df
        emps, truncated = self._cohort(df, dt, department_id)

        exceptions = self.env['pb.attendance.exception.engine']._get_exceptions(
            emps, df, dt) if emps else []

        # group the queue by kind (queue tabs)
        groups = {}
        for x in exceptions:
            groups.setdefault(x['kind'], []).append(x)

        corrections = self._correction_cards()
        pending = [c for c in corrections if c['state'] == 'submitted']

        return {
            'is_officer': self._is_officer(),
            'window': {'from': df.isoformat(), 'to': dt.isoformat()},
            'kpis': {
                'open_exceptions': len(exceptions),
                'pending_corrections': len(pending),
                'late_pct': self._late_pct_week(emps, df, dt) if emps else 0,
                'imports_month': self._imports_this_month(),
            },
            'exceptions': exceptions,
            'exception_groups': [
                {'kind': k, 'rows': groups.get(k, [])}
                for k in ('missing_punch', 'missing_checkout', 'late', 'early_leave')
                if groups.get(k)],
            'corrections': corrections,
            'truncated': truncated,
        }

    # ------------------------------------------------------------- corrections
    def _correction_cards(self):
        Corr = self.env['hr.attendance.correction']
        # record rules already scope this: officer/manager see all/team, an
        # employee sees their own. Show the live pipeline + recent decisions.
        recs = Corr.search([], limit=80)
        return [self._card(c) for c in recs]

    def _card(self, c):
        return {
            'id': c.id,
            'name': c.name,
            'employee': c.employee_id.name,
            'employee_id': c.employee_id.id,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % c.employee_id.id,
            'date': c.date.isoformat() if c.date else '',
            'type': c.correction_type,
            'state': c.state,
            'reason': c.reason or '',
            'can_approve': c.can_approve,
            'can_refuse': c.can_refuse,
            'can_submit': c.can_submit,
            'apply_error': c.apply_error or '',
        }

    @api.model
    def get_correction(self, correction_id):
        self._require()
        c = self._corr(correction_id)
        return {
            **self._card(c),
            'new_check_in': self._fmt(c.new_check_in),
            'new_check_out': self._fmt(c.new_check_out),
            'attendance_id': c.attendance_id.id or False,
            'exception_kind': c.exception_kind or '',
            'day_punches': self.get_day_punches(c.employee_id.id, c.date.isoformat()) if c.date else [],
            'stepper': c.approval_widget_json or '{}',
        }

    @api.model
    def get_day_punches(self, employee_id, day_iso):
        """The day's punches (composer timeline). Device rows are flagged so the
        UI can lock them with a shield tooltip.

        Gated officer-or-self-or-line-manager and company-scoped (review G-H3:
        this used to hand ANY internal user any colleague's punch times), and
        the day window is the EMPLOYEE-LOCAL day converted to UTC (review G-M5
        — the import wizard already converts this way, the read side now
        agrees)."""
        self._require()
        emp = self.env['hr.employee'].sudo().browse(int(employee_id)).exists()
        if not emp:
            return []
        u = self.env.user
        if not self._is_officer():
            own = u.employee_id and u.employee_id.id == emp.id
            line_mgr = (emp.parent_id and emp.parent_id.user_id
                        and emp.parent_id.user_id.id == u.id)
            if not (own or line_mgr):
                raise AccessError(_(
                    "You can only view your own punches, or your reports' as "
                    "their manager."))
        if emp.company_id and emp.company_id.id not in self.env.companies.ids:
            raise AccessError(_("This employee belongs to another company."))
        d = date.fromisoformat(day_iso)
        try:
            tzinfo = pytz.timezone(emp.tz or 'UTC')
        except Exception:
            tzinfo = pytz.UTC
        start = tzinfo.localize(datetime.combine(d, time.min)) \
            .astimezone(pytz.UTC).replace(tzinfo=None)
        end = tzinfo.localize(datetime.combine(d, time.max)) \
            .astimezone(pytz.UTC).replace(tzinfo=None)
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', emp.id),
            ('check_in', '>=', start),
            ('check_in', '<=', end),
        ], order='check_in')
        return [{
            'id': a.id,
            'check_in': self._fmt(a.check_in),
            'check_out': self._fmt(a.check_out),
            'source': a.pb_entry_source or 'device',
            'is_device': not a.pb_entry_source,
        } for a in atts]

    @api.model
    def create_correction(self, payload):
        """File a (draft) correction, pre-filled from an exception row or blank.
        Employees file for themselves; officers/managers file for their team
        (record rules enforce the scope)."""
        self._require()
        payload = payload or {}
        emp_id = int(payload.get('employee_id') or 0) or (
            self.env.user.employee_id.id if self.env.user.employee_id else 0)
        if not emp_id:
            raise AccessError(_("No employee is linked to your user."))
        vals = {
            'employee_id': emp_id,
            'date': payload.get('date') or date.today().isoformat(),
            'correction_type': payload.get('correction_type') or 'create',
            'reason': payload.get('reason') or '',
            'exception_kind': payload.get('exception_kind') or False,
        }
        if payload.get('attendance_id'):
            vals['attendance_id'] = int(payload['attendance_id'])
        if payload.get('new_check_in'):
            vals['new_check_in'] = payload['new_check_in']
        if payload.get('new_check_out'):
            vals['new_check_out'] = payload['new_check_out']
        corr = self.env['hr.attendance.correction'].create(vals)
        return self.get_correction(corr.id)

    @api.model
    def save_correction(self, correction_id, vals):
        self._require()
        c = self._corr(correction_id)
        allowed = {'correction_type', 'attendance_id', 'new_check_in',
                   'new_check_out', 'reason', 'date'}
        clean = {}
        for k, v in (vals or {}).items():
            if k not in allowed:
                continue
            if k == 'attendance_id':
                clean[k] = int(v) if v else False
            else:
                clean[k] = v if v not in ('', None) else False
        c.write(clean)
        return self.get_correction(correction_id)

    @api.model
    def correction_action(self, correction_id, action, note=False):
        """Drive the chain as the REAL user (truthful log + _approval_can auth).
        A refused apply (young-worker etc.) comes back with apply_error set."""
        self._require()
        c = self._corr(correction_id)
        if action == 'submit':
            c.action_submit()
        elif action == 'approve':
            c.action_approve()
        elif action == 'refuse':
            c.action_refuse(note=note or False)
        elif action == 'reset':
            c.action_reset_to_draft()
        else:
            raise AccessError(_("Unknown action."))
        return self.get_correction(correction_id)

    # ------------------------------------------------------------- import
    @api.model
    def import_parse(self, file_b64, filename):
        self._require()
        return self.env['pb.attendance.import.wizard'].parse(file_b64, filename)

    @api.model
    def import_validate(self, file_b64, filename, mapping):
        self._require()
        return self.env['pb.attendance.import.wizard'].validate(file_b64, filename, mapping)

    @api.model
    def import_commit(self, file_b64, filename, mapping):
        self._require()
        return self.env['pb.attendance.import.wizard'].commit(file_b64, filename, mapping)

    # ------------------------------------------------------------- helpers
    def _corr(self, correction_id):
        c = self.env['hr.attendance.correction'].browse(int(correction_id)).exists()
        if not c:
            raise AccessError(_("This correction no longer exists."))
        return c

    def _fmt(self, dt_val):
        return dt_val.strftime('%Y-%m-%d %H:%M:%S') if dt_val else ''
