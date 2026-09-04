# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, time, timedelta

from pytz import timezone, utc, UnknownTimeZoneError

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

# OT types offered as chip measures, in the order the LEGEND prints them, and
# their palette.
#
# P5: these were the old Timecards colours (#e74c3c / #9b59b6 / #e67e22 /
# #2c3e50) — four invented hexes inherited from a Gen-1 screen that the redesign
# retires, i.e. a straight W1 violation that survived because the pills they
# painted were themselves the thing nobody wanted to look at. They are now the
# W1 CATEGORICAL ORDER, assigned by position in this tuple, which is also the
# order the legend renders in. Nothing else may pick a colour for a chip.
OT_TYPES = ('weekday', 'weekend', 'holiday', 'night')
OT_COLORS = {
    'weekday': '#5A4BB0',
    'weekend': '#D97706',
    'holiday': '#2563EB',
    'night': '#DC2668',
}
_DAY_FIELDS = ('apply_monday', 'apply_tuesday', 'apply_wednesday',
               'apply_thursday', 'apply_friday', 'apply_saturday', 'apply_sunday')
_MAX_ROWS = 200  # perf budget: grid targets ≤200 employees (§5.6 / §6.15)


class AttendanceWeekEntry(models.TransientModel):
    """Backend API for the WOW Weekly-Entry grid.

    Rows = employees, columns = Mon–Sun. Each cell carries a REG measure
    (regular worked hours → hr.attendance) plus one chip measure per applicable
    OT type (→ hr.overtime.request). All reads are batched (no per-cell queries);
    every client-side rule is re-validated server-side (safety rail 1).
    """
    _name = 'hr.attendance.weekentry'
    _description = 'Weekly Entry Grid API'

    # ------------------------------------------------------------- access
    @api.model
    def _require_officer(self):
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_officer')
                or u.has_group('base.group_system')):
            raise AccessError(_("Weekly Entry is restricted to attendance officers."))

    @api.model
    def _require_manager(self):
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_manager')
                or u.has_group('base.group_system')):
            raise AccessError(_("Approving overtime is restricted to attendance managers."))

    # ------------------------------------------------------------- helpers
    @api.model
    def _monday(self, week_start_str):
        if week_start_str:
            d = fields.Date.from_string(week_start_str)
        else:
            d = date.today()
        return d - timedelta(days=d.weekday())

    @api.model
    def _emp_tz(self, emp):
        # working-schedule tz first (§5.3), then the company schedule, then the
        # employee resource tz, then the requesting user's tz, finally UTC.
        cal = emp.resource_calendar_id or emp.company_id.resource_calendar_id
        name = ((cal.tz if cal else False) or emp.tz
                or self.env.user.tz or 'UTC')
        try:
            timezone(name)
        except UnknownTimeZoneError:
            name = 'UTC'
        return name

    @api.model
    def _att_token(self, recs):
        """Concurrency token for a cell = MICROSECOND-precise max write_date of
        its attendances (empty when none). Second precision (C14 trap) would let
        a fetch+edit in the same wall-clock second slip past stale detection, so
        we keep the raw datetime string (write_date carries microseconds)."""
        wds = [a.write_date for a in recs if a.write_date]
        return str(max(wds)) if wds else ''

    @api.model
    def _att_hours(self, a):
        """Grid REG hours = the wall-clock span check_out−check_in, NOT
        ``worked_hours`` (which subtracts the calendar lunch in Odoo 19). This
        keeps the round-trip lossless: entering 8 h writes an 8 h span and reads
        8 h back, matching the '=check_in+hours, no lunch arithmetic' write rule.
        """
        if a.check_in and a.check_out:
            return (a.check_out - a.check_in).total_seconds() / 3600.0
        return a.worked_hours or 0.0

    @api.model
    def _holidays(self, week_start, week_end):
        try:
            lines = self.env['hr.holidays.public.line'].search([
                ('date', '>=', week_start), ('date', '<=', week_end)])
            return {l.date for l in lines}
        except Exception:
            return set()

    @api.model
    def _config_applies(self, config, d, holidays):
        """Is this OT config applicable on day `d`?

        Honour the admin's per-day flags when ANY are set; otherwise fall back to
        the natural default for the type (the seed configs ship the flags unset,
        so a pure-flag test would render an empty grid).
        """
        t = config.overtime_type
        if t == 'holiday':
            return d in holidays
        day_flags = [bool(getattr(config, f, False)) for f in _DAY_FIELDS]
        if any(day_flags):
            return day_flags[d.weekday()]
        wd = d.weekday()
        if t == 'weekday':
            return wd < 5 and d not in holidays
        if t == 'weekend':
            return wd >= 5
        if t == 'night':
            return True
        return False

    @api.model
    def _employees(self, department_id, search):
        co_ids = self.env.companies.ids or [self.env.company.id]
        domain = [('active', '=', True), ('company_id', 'in', co_ids)]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        if search:
            domain.append(('name', 'ilike', search))
        return self.env['hr.employee'].search(domain, order='name', limit=_MAX_ROWS + 1)

    # --------------------------------------------------------- read payload
    @api.model
    def get_week_entries(self, week_start_str=False, department_id=False, search=False):
        self._require_officer()
        week_start = self._monday(week_start_str)
        week_end = week_start + timedelta(days=6)
        today = date.today()

        days = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            days.append({
                'iso': d.isoformat(),
                'label': d.strftime('%a'),
                'sublabel': d.strftime('%b %d'),
                'is_today': d == today,
                'is_weekend': d.weekday() >= 5,
            })

        emps = self._employees(department_id, search)
        truncated = 0
        if len(emps) > _MAX_ROWS:
            truncated = len(emps) - _MAX_ROWS
            emps = emps[:_MAX_ROWS]

        # --- batch read: active OT configs (1 query) ---
        configs = self.env['hr.overtime.config'].search([('active', '=', True)])
        cfg_by_type = {}
        for c in configs:
            cfg_by_type.setdefault(c.overtime_type, c)  # first (lowest sequence) wins
        holidays = self._holidays(week_start, week_end)

        # Week-level measure list: REG first, then each OT type with a config.
        #
        # `label` used to BE the rate ("150%"), because the rate was what the
        # per-cell pills printed. P5 splits the two: `name` is the config's own
        # name and `rate` is the rate, and the grid writes them in its legend
        # and its cell editor — never in a cell. `label` is kept as the short
        # fallback for a consumer that reads neither.
        measures = [{'key': 'reg', 'label': _('Reg'), 'name': _('Regular hours'),
                     'min': 0, 'max': 24, 'step': 0.5}]
        for t in OT_TYPES:
            c = cfg_by_type.get(t)
            if not c:
                continue
            measures.append({
                'key': t,
                'label': '%s' % (c.rate_display or t.title()),
                'name': c.name or t.title(),
                'rate': c.rate_display or '',
                'color': OT_COLORS[t],
                'min': 0, 'max': 24, 'step': 0.5,
            })

        # --- batch read: attendances for the week (1 query) ---
        ws_dt = datetime.combine(week_start, time.min)
        we_dt = datetime.combine(week_end, time.max)
        # sudo: reads must live in the same permission world as the sudo write
        # path — the officer record rules are own-only, so a plain officer
        # would otherwise see blank/locked cells and zeroed ceilings for every
        # other employee (review F2). Access is gated by _require_officer and
        # employees are company-scoped in _employees().
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('check_in', '>=', ws_dt), ('check_in', '<=', we_dt),
        ])
        att_by_cell = {}  # (emp_id, iso) -> list of atts
        for a in atts:
            key = (a.employee_id.id, a.check_in.date().isoformat())
            att_by_cell.setdefault(key, self.env['hr.attendance'])
            att_by_cell[key] |= a

        # --- batch read: existing OT requests for the week (1 query) ---
        reqs = self.env['hr.overtime.request'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('date', '>=', week_start), ('date', '<=', week_end),
        ])
        req_by_cell = {}  # (emp_id, iso, type) -> request (latest)
        draft_ids, pending_ids = [], []
        draft_hours = 0.0
        for r in reqs:
            req_by_cell[(r.employee_id.id, r.date.isoformat(), r.overtime_type)] = r
            if r.state == 'draft':
                draft_ids.append(r.id)
                draft_hours += r.actual_hours or 0.0
            elif r.state == 'submitted':
                pending_ids.append(r.id)

        # --- batch read: ceilings for these employees (1-2 queries) ---
        ceilings = self.get_ot_ceilings(emps.ids, today.isoformat())

        rows = []
        for emp in emps:
            cells = {}
            for day in days:
                iso = day['iso']
                d = fields.Date.from_string(iso)
                cell_atts = att_by_cell.get((emp.id, iso), self.env['hr.attendance'])
                n = len(cell_atts)
                reg_hours = round(sum(self._att_hours(a) for a in cell_atts), 2)

                # REG editability + lock reason (safety rail 2)
                reg_editable = True
                lock_reason = ''
                meta = None
                if n >= 2:
                    reg_editable = False
                    lock_reason = _('Multiple attendance records — edit on the attendance form.')
                    meta = [{
                        'id': a.id,
                        'check_in': fields.Datetime.to_string(a.check_in),
                        'check_out': fields.Datetime.to_string(a.check_out) if a.check_out else '',
                        'hours': round(self._att_hours(a), 2),
                        'source': a.pb_entry_source or 'device',
                    } for a in cell_atts]
                elif n == 1 and cell_atts.pb_entry_source != 'grid':
                    reg_editable = False
                    lock_reason = _('Device/kiosk punch — edit on the attendance form.')

                token = self._att_token(cell_atts)

                cell_measures = {'reg': {
                    'value': reg_hours,
                    'editable': reg_editable,
                    'lock_reason': lock_reason,
                    'token': token,
                }}
                if meta:
                    cell_measures['reg']['note'] = _('%d records') % n

                # OT chip measures for applicable (day, type)
                for t in OT_TYPES:
                    c = cfg_by_type.get(t)
                    if not c or not self._config_applies(c, d, holidays):
                        continue
                    req = req_by_cell.get((emp.id, iso, t))
                    if req:
                        val = req.actual_hours or req.approved_hours or 0.0
                        bonus = round(req.bonus_hours or 0.0, 2)
                        # refused is locked too — _save_ot refuses it, so the
                        # grid must not invite an edit that will fail (review F6);
                        # re-entry after refusal goes through the OT request form.
                        locked = req.state in ('submitted', 'approved', 'refused')
                        # `state` is the RAW workflow state now. It used to be
                        # overloaded — "+2b" when there was a bonus split,
                        # otherwise the state — because the old chip had exactly
                        # one text slot for both. The P5 cell renders the state
                        # as a micro-dot and reads `bonus` separately (dashed
                        # chip + the amount spelled out in the editor), so the
                        # two facts no longer have to fight over one string.
                        cell_measures[t] = {
                            'value': round(val, 2),
                            'editable': not locked,
                            'state': req.state,
                            'bonus': bonus,
                            'approved': round(req.approved_hours or 0.0, 2),
                            'request_id': req.id,
                            'lock_reason': (_('%s OT already %s.') % (t.title(), req.state))
                                           if locked else '',
                        }
                    else:
                        cell_measures[t] = {
                            'value': 0.0, 'editable': True, 'state': '', 'request_id': False,
                        }

                cell = {'measures': cell_measures}
                if meta:
                    cell['multi_records'] = meta
                cells[iso] = cell

            rows.append({
                'id': emp.id,
                'label': emp.name,
                'sublabel': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
                'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                'flags': {},  # Phase-E minor-worker hook lands here
                'meta': {'department': emp.department_id.name if emp.department_id else ''},
                'cells': cells,
            })

        ot_legend = [{
            'type': t, 'color': OT_COLORS[t],
            'name': cfg_by_type[t].name, 'rate': cfg_by_type[t].rate_display,
        } for t in OT_TYPES if t in cfg_by_type]

        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'days': days,
            'measures': measures,
            'rows': rows,
            'ceilings': ceilings,
            'ot_legend': ot_legend,
            'summary': {
                'draft_count': len(draft_ids),
                'draft_hours': round(draft_hours, 2),
                'draft_ids': draft_ids,
                'pending_count': len(pending_ids),
                'pending_ids': pending_ids,
            },
            'truncated': truncated,
        }

    @api.model
    def get_departments(self):
        self._require_officer()
        deps = self.env['hr.department'].search([], order='name')
        return [{'id': d.id, 'name': d.name} for d in deps]

    # ------------------------------------------------------------ ceilings
    @api.model
    def get_ot_ceilings(self, employee_ids, ref_date=False):
        """Per-employee OT budget: {emp_id: {mtd, ytd, cap_month, cap_year}}.

        The OFFICER-GATED, RPC-reachable door. The body lives in
        ``_ot_ceilings`` below so a server-side caller that has already crossed
        its OWN gate can reuse it without either duplicating the arithmetic or
        being forced through a second, narrower persona test — see that
        method's docstring for why that mattered (P4 WP-6).
        """
        self._require_officer()
        return self._ot_ceilings(employee_ids, ref_date)

    @api.model
    def _ot_ceilings(self, employee_ids, ref_date=False):
        """The same figures, UNGATED — underscore-private, so not reachable over
        ``call_kw`` (C18.32), and every caller gates itself first.

        Extracted in P4 WP-6 for the dock's clean-overtime batch. The dock is
        read by HR and payroll MANAGERS as well as attendance officers, and
        ``_require_officer`` admits only the attendance tier: routing the
        headroom test through the public door would have made the batch
        silently invisible to half the personas it was built for, with a
        swallowed AccessError and no console message — W40's exact failure
        shape, which cost this program a search box for three phases.

        MTD/YTD sum submitted+approved OT hours (actual_hours, fallback
        approved_hours). Caps come from pb.ot.ceiling config; special-sector
        employees get the higher annual cap.
        """
        employee_ids = [int(e) for e in (employee_ids or [])]
        if not employee_ids:
            return {}
        ref = fields.Date.from_string(ref_date) if ref_date else date.today()
        year_start = date(ref.year, 1, 1)
        year_end = date(ref.year, 12, 31)
        month_start = date(ref.year, ref.month, 1)
        # month end = last day of the month
        if ref.month == 12:
            month_end = date(ref.year, 12, 31)
        else:
            month_end = date(ref.year, ref.month + 1, 1) - timedelta(days=1)

        emps = self.env['hr.employee'].browse(employee_ids)
        # caps are resolved PER EMPLOYEE COMPANY (review F8) — a mixed-company
        # grid must not inherit the first employee's caps for everyone
        Ceil = self.env['pb.ot.ceiling']
        ceil_by_co = {}
        emp_by_id = {e.id: e for e in emps}
        for e in emps:
            co = e.company_id or self.env.company
            if co.id not in ceil_by_co:
                ceil_by_co[co.id] = Ceil._for_company(co)

        # one search_read over the year's submitted/approved requests; fold in
        # py (sudo — same permission world as the write path, review F2)
        rows = self.env['hr.overtime.request'].sudo().search_read(
            [('employee_id', 'in', employee_ids),
             ('date', '>=', year_start), ('date', '<=', year_end),
             ('state', 'in', ('submitted', 'approved'))],
            ['employee_id', 'date', 'actual_hours', 'approved_hours'])

        agg = {e: {'mtd': 0.0, 'ytd': 0.0} for e in employee_ids}
        for r in rows:
            eid = r['employee_id'][0] if r['employee_id'] else False
            if eid not in agg:
                continue
            hrs = r['actual_hours'] or r['approved_hours'] or 0.0
            agg[eid]['ytd'] += hrs
            if month_start <= r['date'] <= month_end:
                agg[eid]['mtd'] += hrs

        # sudo: same rail as _allowance — the flag is groups='hr.group_hr_user'
        # and the ceiling rail must render for any gated grid user (K-F8)
        special = {e.id: e.pb_ot_special_sector for e in emps.sudo()}
        out = {}
        for eid in employee_ids:
            e = emp_by_id.get(eid)
            co = (e.company_id if e else False) or self.env.company
            ceil = ceil_by_co.get(co.id) or Ceil._for_company(co)
            cap_year = ceil.annual_cap_special if special.get(eid) else ceil.annual_cap
            out[eid] = {
                'mtd': round(agg[eid]['mtd'], 2),
                'ytd': round(agg[eid]['ytd'], 2),
                'cap_month': ceil.monthly_cap,
                'cap_year': cap_year,
            }
        return out

    # -------------------------------------------------------------- writes
    @api.model
    def save_week_entries(self, payload):
        """Persist dirty cells. Returns {results:[{rowId,dayISO,measure,ok,error}]}.

        Everything the client 'already checked' is re-validated here (rail 1):
        editability, 0–24 h bounds, locked OT states, grid-only mutation, and a
        write_date snapshot token for stale detection (rail 7).
        """
        self._require_officer()
        cells = (payload or {}).get('cells') or []
        results = []
        if not cells:
            return {'results': results}

        req_ids = sorted({int(c['rowId']) for c in cells})
        # company-scope guard (respects record rules): only employees the officer
        # may see are writable; unknown/foreign rowIds are rejected per-cell.
        co_ids = self.env.companies.ids or [self.env.company.id]
        allowed = self.env['hr.employee'].search([
            ('id', 'in', req_ids), ('company_id', 'in', co_ids)])
        emps = {e.id: e for e in allowed}
        emp_ids = list(emps)
        dates = sorted({fields.Date.from_string(c['dayISO']) for c in cells})
        d_min, d_max = dates[0], dates[-1]

        # batch reads (sudo — access already gated + scoped above; su gives an
        # accurate multi-record / stale view regardless of row-level rules)
        Att = self.env['hr.attendance'].sudo()
        atts = Att.search([
            ('employee_id', 'in', emp_ids),
            ('check_in', '>=', datetime.combine(d_min, time.min)),
            ('check_in', '<=', datetime.combine(d_max, time.max)),
        ])
        att_map = {}
        for a in atts:
            att_map.setdefault((a.employee_id.id, a.check_in.date()), Att.browse())
            att_map[(a.employee_id.id, a.check_in.date())] |= a

        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('date', '>=', d_min), ('date', '<=', d_max),
            ('state', '=', 'published'),
        ])
        shift_map = {}
        for s in shifts:
            shift_map.setdefault((s.employee_id.id, s.date), s)

        cfgs = {c.overtime_type: c for c in
                self.env['hr.overtime.config'].search([('active', '=', True)])}
        holidays = self._holidays(d_min, d_max)

        for c in cells:
            emp_id = int(c['rowId'])
            d = fields.Date.from_string(c['dayISO'])
            measure = c['measure']
            try:
                value = float(c.get('value') or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            emp = emps.get(emp_id)
            res = {'rowId': emp_id, 'dayISO': c['dayISO'], 'measure': measure}
            if not emp:
                results.append({**res, 'ok': False, 'error': 'noemp'})
                continue
            # isolate each cell in a savepoint: a genuine DB error on one cell
            # rolls back only that cell and never poisons the batch cursor.
            try:
                extra = None
                with self.env.cr.savepoint():
                    if measure == 'reg':
                        ok, err = self._save_reg(emp, d, value, c.get('token'),
                                                 att_map, shift_map)
                    elif measure in OT_TYPES:
                        ok, err, extra = self._save_ot(emp, d, measure, value,
                                                       cfgs, holidays)
                    else:
                        ok, err = False, 'badmeasure'
                row = {**res, 'ok': ok, 'error': err}
                if extra:  # OT split preview — grid renders the live bonus chip
                    row.update(extra)
                results.append(row)
            except Exception:  # never let one bad cell abort the batch
                results.append({**res, 'ok': False, 'error': 'exc'})
        return {'results': results}

    def _save_reg(self, emp, d, hours, token, att_map, shift_map):
        if hours < 0 or hours > 24:
            return False, 'bounds'
        Att = self.env['hr.attendance'].sudo()
        recs = att_map.get((emp.id, d), Att.browse())
        # stale detection: the fetched token must match the cell's CURRENT
        # token EXACTLY — including the empty case (no attendance at fetch
        # time: if a record has appeared meanwhile, refuse rather than
        # silently mutate it). An omitted token never bypasses the check
        # (review F5).
        if (token or '') != self._att_token(recs):
            return False, 'stale'
        n = len(recs)
        if n >= 2:
            return False, 'multi'
        if n == 1:
            rec = recs[0]
            if rec.pb_entry_source != 'grid':
                return False, 'notgrid'
            if hours == 0:
                rec.unlink()
                att_map[(emp.id, d)] = Att.browse()
                return True, None
            rec.write({'check_out': rec.check_in + timedelta(hours=hours)})
            return True, None
        # n == 0
        if hours == 0:
            return True, None  # nothing to create
        ci = False
        shift = shift_map.get((emp.id, d))
        if shift and shift.start_datetime:
            ci = shift.start_datetime
        else:
            tz = timezone(self._emp_tz(emp))
            ci = tz.localize(datetime.combine(d, time(8, 0))).astimezone(utc).replace(tzinfo=None)
        new = Att.create({
            'employee_id': emp.id,
            'check_in': ci,
            'check_out': ci + timedelta(hours=hours),
            'pb_entry_source': 'grid',
        })
        att_map[(emp.id, d)] = new
        return True, None

    def _save_ot(self, emp, d, ot_type, hours, cfgs, holidays):
        """Persist one OT cell as a draft request, computing the Bonus-Hours
        split (Phase K, first of the two writers). Returns
        ``(ok, err, extra)`` where ``extra`` = {value, approved, bonus} so the
        grid can render the live split chip (``4 + 2b``). For a minor the write
        trips the Phase-E @api.constrains and raises — caught by the per-cell
        savepoint, so no split and no bonus row are ever persisted (rail 3)."""
        if hours < 0 or hours > 24:
            return False, 'bounds', None
        # rail 1: the type must have an active config and be applicable on this
        # day — the grid greys these cells, but a crafted RPC must not file
        # weekend OT on a Tuesday (review F7)
        cfg = cfgs.get(ot_type)
        if not cfg or not self._config_applies(cfg, d, holidays):
            return False, 'notapplicable', None
        Req = self.env['hr.overtime.request'].sudo()
        Ceil = self.env['pb.ot.ceiling']
        req = Req.search([
            ('employee_id', '=', emp.id), ('date', '=', d),
            ('overtime_type', '=', ot_type),
        ], limit=1)
        if req:
            if req.state in ('submitted', 'approved', 'refused'):
                return False, 'locked', None
            # draft
            if hours == 0:
                req.unlink()
                return True, None, {'value': 0.0, 'approved': 0.0, 'bonus': 0.0}
            # a draft is not counted by _allowance (submitted+approved only), so
            # excluding its own id is belt-and-braces; reducing hours re-splits
            # and always commits (C18.38 posture carries over).
            approved, bonus = Ceil._split(emp, d, hours, exclude_ids=[req.id])
            req.write({'actual_hours': hours, 'planned_hours': hours,
                       'approved_hours': approved, 'bonus_hours': bonus})
            return True, None, {'value': hours, 'approved': approved, 'bonus': bonus}
        if hours == 0:
            return True, None, None
        approved, bonus = Ceil._split(emp, d, hours)
        Req.create({
            'employee_id': emp.id,
            'date': d,
            'overtime_type': ot_type,
            'planned_hours': hours,
            'actual_hours': hours,
            'approved_hours': approved,
            'bonus_hours': bonus,
            'reason': _('Entered via Weekly Entry grid'),
            # explicit: the model default is env.company, which can mismatch
            # the employee's company in a multi-company grid (review F8)
            'company_id': emp.company_id.id or self.env.company.id,
        })
        return True, None, {'value': hours, 'approved': approved, 'bonus': bonus}

    # ------------------------------------------------------- bulk workflow
    @api.model
    def submit_week(self, week_start_str=False, department_id=False, search=False):
        """Submit every DRAFT OT request in the visible week (loops action_submit)."""
        self._require_officer()
        week_start = self._monday(week_start_str)
        week_end = week_start + timedelta(days=6)
        emps = self._employees(department_id, search)[:_MAX_ROWS]
        # sudo: same permission world as the sudo create path — an officer must
        # be able to submit the drafts the grid just created (review F2)
        drafts = self.env['hr.overtime.request'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('date', '>=', week_start), ('date', '<=', week_end),
            ('state', '=', 'draft'),
        ])
        drafts.action_submit()
        return {'submitted': len(drafts)}

    @api.model
    def approve_requests(self, request_ids):
        """Approve submitted OT requests (loops the model's action_approve)."""
        self._require_manager()
        reqs = self.env['hr.overtime.request'].browse(
            [int(r) for r in (request_ids or [])]).exists()
        reqs = reqs.filtered(lambda r: r.state == 'submitted')
        reqs.action_approve()
        return {'approved': len(reqs)}
