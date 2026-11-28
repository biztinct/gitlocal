"""Presentation facade. All record edits use the original form/model and ACLs.

Installation changes no attendance, rule, assignment, payroll or company opt-in.
Optional attendance calculation is discovered, never installed by this module.
"""
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression
from odoo.tools.misc import formatLang


CATALOGS = {
    'shifts': ('hr.shift.template', 'Shifts', ['name', 'code', 'start_hour', 'end_hour', 'break_duration', 'duration', 'shift_type', 'is_overnight']),
    'policies': ('pb.attendance.policy', 'Attendance policies', ['name', 'state', 'tz', 'pairing', 'capture_before', 'capture_after']),
    'people': ('hr.employee', 'People & assignments', ['name', 'barcode', 'department_id', 'work_location_id', 'resource_calendar_id', 'pb_attendance_category', 'pb_attendance_policy_id']),
    'calendars': ('resource.calendar', 'Working calendars', ['name', 'tz', 'hours_per_day']),
    'rates': ('hr.overtime.config', 'Overtime definitions', ['name', 'overtime_type', 'rate_multiplier', 'threshold_hours', 'requires_approval', 'country_id']),
    'ceilings': ('pb.ot.ceiling', 'Overtime ceilings', ['name', 'country_id', 'daily_cap', 'weekly_cap', 'monthly_cap', 'annual_cap']),
    'connectors': ('pb.clock.connector', 'Data connectors', ['name', 'source_group', 'state', 'last_contact', 'last_read', 'pending_rows', 'last_error']),
    'rosters': ('hr.shift.planning', 'Roster review', ['name', 'employee_id', 'date', 'shift_template_id', 'state', 'planned_hours', 'pb_inferred', 'pb_calculation_status']),
}


def _catalog_label(key):
    """The section names, translated when they are read (WFSETUP P5c): the
    labels in CATALOGS stay English identifiers."""
    return {
        'shifts': _('Shifts'),
        'policies': _('Attendance policies'),
        'people': _('People & assignments'),
        'calendars': _('Working calendars'),
        'rates': _('Overtime definitions'),
        'ceilings': _('Overtime ceilings'),
        'connectors': _('Data connectors'),
        'rosters': _('Roster review'),
    }.get(key, key)


class Company(models.Model):
    _inherit = 'res.company'
    pb_workforce_workspace_enabled = fields.Boolean(string='Use unified Workforce workspace', default=False,
        help='Use grouped navigation and guided setup. Existing attendance and payroll rules are unchanged.')

    def write(self, vals):
        if 'pb_workforce_workspace_enabled' in vals and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an administrator can change the company workspace.'))
        return super().write(vals)


class Workspace(models.AbstractModel):
    _name = 'pb.workforce.workspace'
    _description = 'Workforce workspace'

    def _gate(self):
        if not (self.env.user.has_group('hr_attendance.group_hr_attendance_officer') or
                self.env.user.has_group('base.group_system')):
            raise AccessError(_('Attendance access is required.'))

    @api.model
    def preferences(self):
        # Safe for every internal user of Mission, including an approvals-only user.
        if not self.env.user.has_group('base.group_user'):
            raise AccessError(_('Sign in to continue.'))
        return {'enabled': self.env.company.pb_workforce_workspace_enabled,
                'company': self.env.company.name, 'company_id': self.env.company.id,
                'can_configure': self.env.user.has_group('base.group_system'),
                'review_rows': self._review_rows()}

    @api.model
    def _review_rows(self):
        """Roster rows still waiting for review (drafts from today on, this
        company) — the trimmed menu lists "Review roster" only when there are
        some (WFSETUP P5a). Zero for anyone who cannot read the roster; sudo
        only for the count, behind the attendance-officer check."""
        user = self.env.user
        if not (user.has_group('hr_attendance.group_hr_attendance_officer') or user.has_group('base.group_system')):
            return 0
        if 'hr.shift.planning' not in self.env:
            return 0
        return self.env['hr.shift.planning'].sudo().search_count([
            ('company_id', '=', self.env.company.id), ('state', '=', 'draft'),
            ('date', '>=', fields.Date.context_today(self))])

    def _catalog(self, key):
        self._gate()
        if key not in CATALOGS:
            raise ValidationError(_('Unknown workforce section.'))
        name, _label, wanted = CATALOGS[key]
        label = _catalog_label(key)
        if name not in self.env:
            raise ValidationError(_('This optional feature is not installed for this database.'))
        model = self.env[name]
        model.check_access('read')
        meta = model.fields_get([f for f in wanted if f in model._fields], ['string', 'type', 'selection'])
        domain = [('company_id', 'in', [False, self.env.company.id])] if 'company_id' in model._fields else []
        # Shared reference calendars/rates are visible, but every model's record rules still apply.
        return model, label, meta, domain

    @api.model
    def catalog(self, key, search='', offset=0, location_id=None, week_start=None, drafts=False):
        model, label, meta, domain = self._catalog(key)
        if search:
            domain = expression.AND([domain, [('name', 'ilike', str(search)[:150])]])
        if location_id is not None and key in ('people', 'rosters'):
            field = 'work_location_id' if key == 'people' else 'employee_id.work_location_id'
            domain.append((field, '=', int(location_id) or False))
        if key == 'rosters':
            if week_start:
                low = fields.Date.to_date(week_start)
                domain += [('date', '>=', low), ('date', '<', low + timedelta(days=7))]
            if drafts:
                domain.append(('state', '=', 'draft'))
        offset = max(0, int(offset))
        order = 'date desc, id desc' if key == 'rosters' else 'name, id'
        rows = model.search_read(domain, list(meta), limit=40, offset=offset, order=order)
        return {'model': model._name, 'label': label, 'fields': meta, 'rows': rows,
                'total': model.search_count(domain), 'can_create': key not in ('people', 'rosters') and model.has_access('create'),
                'can_write': model.has_access('write'), 'domain': domain}

    @api.model
    def overview(self, week_start=None):
        self._gate()
        low = fields.Date.to_date(week_start) if week_start else fields.Date.today()
        high = low + timedelta(days=7)
        result = {'catalogs': [], 'steps': [], 'locations': [], 'week_start': str(low), 'week_end': str(high-timedelta(days=1))}
        counts = {}
        for key in CATALOGS:
            try:
                model, label, meta, domain = self._catalog(key)
            except (AccessError, ValidationError):
                continue
            count = model.search_count(domain)
            counts[key] = count
            result['catalogs'].append({'key': key, 'label': label, 'count': count})
        def count(name, extra):
            if name not in self.env or not self.env[name].has_access('read'):
                return None
            model = self.env[name]
            domain = [('company_id', '=', self.env.company.id)] if 'company_id' in model._fields else []
            return model.search_count(domain + extra)
        active = count('pb.attendance.policy', [('state', '=', 'active')])
        drafts = count('hr.shift.planning', [('state', '=', 'draft')])
        contacts = count('pb.clock.connector', [('last_contact', '!=', False)])
        missing = count('hr.employee', [('pb_attendance_policy_id', '=', False)]) if 'pb.attendance.policy' in self.env else None
        result.update(active_policies=active, draft_rosters=drafts, contacted_connectors=contacts, unassigned_people=missing)
        num = lambda n: formatLang(self.env, int(n or 0), digits=0)
        result['steps'] = [
            {'key': 'shifts', 'title': _('Define the shifts'), 'text': _('Set start and end times, unpaid breaks and overnight work.'),
             'status': _('%s shifts available', num(counts.get('shifts', 0)))},
            {'key': 'policies', 'title': _('Review rules & calendars'), 'text': _('Confirm normal hours, overtime boundaries and lateness deductions. Activate only after review.'),
             'status': _('%s active policies', num(active)) if active is not None else _('Calculation policy module not installed')},
            {'key': 'people', 'title': _('Assign people'), 'text': _('Check each person’s workplace, calendar and attendance group. Assign recurring patterns in the next step.'),
             'status': _('%s people without a policy', num(missing)) if missing is not None else _('%s employees', num(counts.get('people', 0)))},
            {'key': 'patterns', 'title': _('Build and review the roster'), 'text': _('Assign people to recurring patterns, preview dates and create drafts. Publish only the reviewed roster.'),
             'status': _('%s roster drafts awaiting review', num(drafts))},
            {'key': 'connectors', 'title': _('Connect attendance'), 'text': _('Invite IT, pair the PC and verify received records. A successful upload does not prove that all terminals were downloaded.'),
             'status': _('%s connectors have reported', num(contacts))},
            {'key': 'time', 'title': _('Check hours before payroll'), 'text': _('Review actual attendance, normal hours and overtime. Resolve exceptions and approve hours before closing the period.'),
             'status': _('Review required before each payroll')},
        ]
        Employee = self.env['hr.employee']
        if Employee.has_access('read'):
            edomain = [('company_id', '=', self.env.company.id)]
            locations = Employee._read_group(edomain, ['work_location_id'], ['__count'])
            Roster = self.env['hr.shift.planning']
            grouped = Roster._read_group([('company_id', '=', self.env.company.id), ('date', '>=', low), ('date', '<', high)], ['employee_id', 'state'], ['__count']) if Roster.has_access('read') else []
            roster_counts = {}
            for employee, state, n in grouped:
                location = employee.work_location_id.id or 0
                tally = roster_counts.setdefault(location, {'draft': 0, 'other': 0})
                tally['draft' if state == 'draft' else 'other'] += n
            for location, n in locations:
                lid = location.id or 0
                result['locations'].append({'id': lid, 'name': location.name or _('Workplace not assigned'), 'people': n,
                    **roster_counts.get(lid, {'draft': 0, 'other': 0})})
        return result


class Patterns(models.AbstractModel):
    _inherit = 'pb.shift.patterns'

    @api.model
    def _row(self, rec, tmap):
        result = super()._row(rec, tmap)
        result['cycle_start'] = str(rec.start_date) if rec.start_date else False
        return result
