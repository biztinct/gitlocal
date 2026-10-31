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
_CORR_PAGE = 30            # correction cards per page (FILTER W7)


class PbAttendanceFlow(models.AbstractModel):
    _name = 'pb.attendance.flow'
    _inherit = ['pb.filter.mixin']
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
    def _cohort(self, df, dt, department_id=False, employee_id=False):
        """Employees the feed covers: for an officer, everyone in-company with a
        published shift in the window or an open punch; for anyone else, just
        themselves. Bounded to _MAX_COHORT.

        `department_id` narrows the cohort to the Time hub's context department
        (W4). The Time hub's ribbon calls THIS method with THIS window so its
        count is the same number the Exceptions lens shows — the two must never
        disagree, so they share one cohort definition rather than two.

        `employee_id` (P1b §2.4) narrows it to ONE person — the shared context's
        pinned person, which is how the Today board's "File correction" door
        lands the officer on that person's exceptions instead of on a queue of
        four hundred they then have to search. It is a FILTER over the cohort
        this method already computed, never a way to reach someone the caller
        could not otherwise see: a non-officer still gets themselves, and a
        pinned id outside the window simply yields an empty queue.
        """
        if not self._is_officer():
            emp = self.env.user.employee_id
            if employee_id and emp.id != int(employee_id):
                # A pinned colleague must not become a way past the own-only
                # rail; the pin is ignored, not honoured.
                return emp, 0
            return emp, 0
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
        if employee_id:
            emps = emps.filtered(lambda e: e.id == int(employee_id))
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
    def get_control_data(self, date_from=False, date_to=False,
                         department_id=False, employee_id=False):
        """Board payload.

        Called with no arguments (the standalone Attendance Control action) the
        window is the historical rolling 14 days over every in-company employee
        — unchanged. The Time hub passes its shared context week + department
        instead (W4), which is also what makes the hub ribbon's count and this
        board's count the same number by construction.

        `employee_id` (P1b §2.4) is the shared context's pinned person. It
        narrows the queue and comes back in `person`, so the board can show a
        clearable chip: a filtered queue that does not SAY it is filtered reads
        as "this person has no exceptions", which is the opposite of the truth.

        Deliberately NOT applied to the corrections pipeline: an officer who
        pins a person is triaging that person's exceptions, and hiding the rest
        of the approval queue underneath would lose work in progress. Record
        rules already scope that list.
        """
        self._require()
        dt = fields.Date.to_date(date_to) or date.today()
        df = fields.Date.to_date(date_from) or (dt - timedelta(days=_WINDOW_DAYS - 1))
        if df > dt:
            df, dt = dt, df
        emps, truncated = self._cohort(df, dt, department_id, employee_id)

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
            'person': self._person_chip(employee_id, emps),
        }

    def _person_chip(self, employee_id, emps):
        """{id, name} for the filter chip, or False.

        The chip must render even when the pin matches nobody in the window —
        "no exceptions for X" and "the queue is empty" are different sentences,
        and only the chip tells them apart — so the name is resolved
        independently of the cohort. That resolution is a directory lookup, so
        it is gated and company-scoped: a NON-officer (who is pinned to their
        own row anyway) gets an id and no name, never a colleague's identity out
        of a context value any session can edit.
        """
        if not employee_id:
            return False
        try:
            emp_id = int(employee_id)
        except (TypeError, ValueError):
            return False
        name = ''
        if emp_id in emps.ids:
            name = emps.browse(emp_id).name or ''
        elif self._is_officer():
            co_ids = self.env.companies.ids or [self.env.company.id]
            emp = self.env['hr.employee'].sudo().browse(emp_id).exists()
            if emp and (not emp.company_id or emp.company_id.id in co_ids):
                name = emp.name or ''
        return {'id': emp_id, 'name': name}

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

    # ------------------------------------------------------------- the filter panel
    # FILTER wave 7 (2026-10-31). The corrections column used to be the 80
    # most recent corrections, unfiltered. It now sits on the shared filter
    # panel, paged. The exceptions queue beside it is NOT records (the
    # exception engine computes its rows), so it stays as it is (ruling R5).
    #
    # Who sees what is the record rules' answer, as before: an officer every
    # correction, a manager their team's, an employee their own. Nothing here
    # is read under sudo, and there is no company domain beyond what the
    # rules already apply.

    def _pbf_model(self):
        return 'hr.attendance.correction'

    def _pbf_screen(self):
        return 'corrections'

    def _pbf_base_domain(self):
        return []

    def _pbf_search_fields(self):
        return ['name', 'employee_id.name', 'reason', 'department_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Newest first'),
             'order': 'create_date desc, id desc'},
            {'key': 'oldest', 'label': _('Waiting longest first'),
             'order': 'create_date asc, id asc'},
            {'key': 'day', 'label': _('Latest day first'),
             'order': 'date desc, id desc'},
            {'key': 'name', 'label': _('Name A–Z'),
             'order': 'employee_id, date desc, id desc'},
        ]

    @api.model
    def _week_bounds(self):
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())
        return monday, monday + timedelta(days=7)

    # ---- Python facts, each one read once per request (ledger F18/F25)
    @api.model
    def _mine_to_review_ids(self):
        """Submitted corrections the reader may approve now — the card's own
        Approve rule (`can_approve`: the specific line manager, the officer
        tier or the route's open seat, never the person who filed it), over
        the submitted corrections the reader can see."""
        key = ('pb_attendance_flow.mine', self.env.uid, tuple(self.env.companies.ids))
        cache = self.env.cr.cache
        if key not in cache:
            subs = self.env['hr.attendance.correction'].search([('state', '=', 'submitted')])
            cache[key] = [c.id for c in subs if c.can_approve]
        return cache[key]

    @api.model
    def _applied_this_week_ids(self):
        """Corrections whose punch was applied this week: the approval log's
        own stamp (the record has no "applied on" field)."""
        key = ('pb_attendance_flow.applied_week', self.env.uid)
        cache = self.env.cr.cache
        if key not in cache:
            monday, next_monday = self._week_bounds()
            logs = self.env['biz.approval.step.log'].sudo().search_read([
                ('res_model', '=', 'hr.attendance.correction'),
                ('to_state', '=', 'approved'),
                ('stamp', '>=', fields.Datetime.to_string(
                    datetime.combine(monday, time.min))),
                ('stamp', '<', fields.Datetime.to_string(
                    datetime.combine(next_monday, time.min))),
            ], ['res_id'])
            cache[key] = sorted({r['res_id'] for r in logs if r.get('res_id')})
        return cache[key]

    @api.model
    def _pbf_mine(self):
        return [('id', 'in', self._mine_to_review_ids())]

    @api.model
    def _pbf_not_mine(self):
        return [('state', '=', 'submitted'), ('id', 'not in', self._mine_to_review_ids())]

    @api.model
    def _pbf_applied_week(self):
        return [('state', '=', 'approved'), ('id', 'in', self._applied_this_week_ids())]

    @api.model
    def _pbf_applied_before(self):
        return [('state', '=', 'approved'), ('id', 'not in', self._applied_this_week_ids())]

    def _pbf_spec(self):
        return [
            # ---- pinned: where it is, who, which team
            {'key': 'status', 'label': _('Status'), 'icon': 'listChecks',
             'group': 'other', 'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'draft', 'label': _('Draft'), 'tone': 'slate',
                  'domain': [('state', '=', 'draft')]},
                 {'value': 'submitted', 'label': _('Waiting for approval'), 'tone': 'amber',
                  'domain': [('state', '=', 'submitted')]},
                 {'value': 'approved', 'label': _('Applied'), 'tone': 'green',
                  'domain': [('state', '=', 'approved')]},
                 {'value': 'refused', 'label': _('Refused'), 'tone': 'rose',
                  'domain': [('state', '=', 'refused')]},
             ]},
            {'key': 'employee', 'label': _('Who it is for'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id',
             'pinned': True, 'label_sudo': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id',
             'pinned': True, 'label_sudo': True, 'none_label': _('No department')},
            # ---- more filters
            {'key': 'review', 'label': _('Who it waits on'), 'icon': 'userCheck',
             'group': 'people', 'type': 'choice',
             'help': _('Corrections you can approve now.'),
             'options': [
                 {'value': 'yes', 'label': _('Me'), 'tone': 'amber',
                  'domain_method': '_pbf_mine'},
                 {'value': 'no', 'label': _('Somebody else'), 'tone': 'slate',
                  'domain_method': '_pbf_not_mine'},
             ]},
            {'key': 'day', 'label': _('Day corrected'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'date',
             'presets': ['today', 'this_week', 'this_month', 'last_month',
                         'last_90', 'this_year']},
            {'key': 'applied', 'label': _('When it was applied'), 'icon': 'checkCircle',
             'group': 'dates', 'type': 'choice',
             'options': [
                 {'value': 'this_week', 'label': _('This week'), 'tone': 'green',
                  'domain_method': '_pbf_applied_week'},
                 {'value': 'before', 'label': _('Before this week'), 'tone': 'slate',
                  'domain_method': '_pbf_applied_before'},
             ]},
            {'key': 'type', 'label': _('What it changes'), 'icon': 'pencil',
             'group': 'other', 'type': 'selection', 'path': 'correction_type'},
            {'key': 'from_exc', 'label': _('Filed from'), 'icon': 'alert',
             'group': 'other', 'type': 'char', 'path': 'exception_kind',
             'none_label': _('Filed by hand')},
            {'key': 'failed', 'label': _('Problem applying it'), 'icon': 'xCircle',
             'group': 'other', 'type': 'choice',
             'help': _('Approved, but the punch could not be changed, for example '
                       'because of a working-hours limit. The reason is on the card.'),
             'options': [
                 {'value': 'yes', 'label': _('Could not be applied'), 'tone': 'rose',
                  'domain': [('apply_error', '!=', False)]},
                 {'value': 'no', 'label': _('No problem'), 'tone': 'slate',
                  'domain': [('apply_error', '=', False)]},
             ]},
            {'key': 'manager', 'label': _('Their manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'manager_id',
             'label_sudo': True, 'none_label': _('No manager')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'waiting', 'label': _('Waiting for approval'), 'icon': 'inbox',
             'filters': {'status': ['submitted']}},
            {'key': 'applied', 'label': _('Applied this week'), 'icon': 'checkCircle',
             'filters': {'applied': ['this_week']}},
            {'key': 'failed', 'label': _('Failed to apply'), 'icon': 'xCircle',
             'filters': {'failed': ['yes']}},
            {'key': 'mine', 'label': _('Mine to review'), 'icon': 'userCheck',
             'filters': {'review': ['yes']}},
            {'key': 'all', 'label': _('All'), 'icon': 'layoutList', 'filters': {}},
        ]

    @api.model
    def _pbf_label_values(self, s, values):
        # the exception kinds read the way the queue's tabs read them
        out = super()._pbf_label_values(s, values)
        if s.get('key') == 'from_exc':
            words = self._exception_words()
            for row in out:
                row['label'] = words.get(row['v'], row['label'])
        return out

    @api.model
    def _pbf_list_values(self, s, domain, selected=None):
        rows, more = super()._pbf_list_values(s, domain, selected)
        if s.get('key') == 'from_exc':
            words = self._exception_words()
            for row in rows:
                if row['v']:
                    row['label'] = words.get(row['v'], row['label'])
        return rows, more

    @api.model
    def _exception_words(self):
        return {
            'missing_punch': _('Missing punch'),
            'missing_checkout': _('Missing check-out'),
            'late': _('Late arrival'),
            'early_leave': _('Early departure'),
        }

    @api.model
    def pbf_layout(self):
        try:
            self._require()
        except AccessError as e:
            return {'refused': str(e.args[0] if e.args else e)}
        return super().pbf_layout()

    @api.model
    def get_correction_page(self, filters=None, search=None, sort=None, offset=0,
                            limit=_CORR_PAGE):
        """One page of correction cards for the panel's state, read as the
        reader (record rules scope it, as they always did)."""
        self._require()
        Corr = self.env['hr.attendance.correction']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or _CORR_PAGE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, _CORR_PAGE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        recs = Corr.search(domain, order=self.pbf_order(sort) or 'create_date desc, id desc',
                           offset=offset, limit=limit)
        return {
            'cards': [self._card(c) for c in recs],
            'total': Corr.search_count(domain),
            'offset': offset,
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

        # `reuse_draft`: hand back the OPEN draft for this person+day+type
        # instead of minting another one. The Time hub's drawer hand-off is an
        # idempotent "open the correction for this day" gesture, not "file a new
        # one every time" — and a mount that runs twice for any reason must not
        # leave a trail of duplicate drafts in the pipeline. Only ever reuses a
        # DRAFT: anything submitted/approved/refused is history and is left be.
        if payload.get('reuse_draft'):
            existing = self.env['hr.attendance.correction'].search([
                ('employee_id', '=', emp_id),
                ('date', '=', vals['date']),
                ('correction_type', '=', vals['correction_type']),
                ('state', '=', 'draft'),
            ], limit=1, order='id desc')
            if existing:
                return self.get_correction(existing.id)

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
