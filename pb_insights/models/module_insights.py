"""Read-only, module-specific measures for the shared Insights workspace.

Every measure names its source, cohort and date explicitly.  The caller's
company selection and the source model's record rules are applied to every
query where those rules grant the reporting audience access. Workforce,
Goals and Learning already have reporting facades broader than their source
ACL. Those facades authorize the caller before the source is read with sudo
and an explicit company domain, following the source board's contract.
Hiring retains its requisition record rules, including the line manager's
own-role scope.
"""

from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


# These are report destinations, never replacements for the actions themselves.
# PDF reports requiring a selected record remain on their original forms.
REPORTS = {
    'people': [
        ('Workforce insights', 'pb_workforce_insights.action_pb_workforce_insights', None),
        ('Employee records', 'pb_people_hub.action_pb_people_hub', 'employees'),
        ('Contracts', 'pb_people_hub.action_pb_people_contracts', None),
    ],
    'workforce': [
        ('Workforce insights', 'pb_workforce_insights.action_pb_workforce_insights', None),
        ('Time and attendance', 'pb_mission.action_pb_workforce', 'time'),
        ('Time off', 'pb_mission.action_pb_workforce', 'timeoff'),
    ],
    'expenses': [
        ('Expense claims', 'pb_me_expense.pb_expense_claim_action', None),
        ('Business trips', 'pb_business_trip.action_pb_business_trip', None),
    ],
    'hiring': [
        ('Hiring numbers', 'pb_hiring.action_pb_hiring_numbers', None),
    ],
    'talent': [
        ('Goal numbers', 'pb_goals.action_pb_goals_numbers', None),
        ('Goal reviews', 'pb_goals.action_pb_goal_review', None),
    ],
    'learning': [
        ('Training numbers', 'pb_training.action_pb_training_numbers', None),
        ('Required training', 'pb_training.action_pb_training_requirements', None),
        ('Training assignments', 'pb_training.action_pb_training_assignments', None),
    ],
    'payroll': [
        ('Payroll report', 'pb_hr_workforce.action_payroll_report_dashboard', None),
        ('Salary components pivot', 'pb_hr_flow.action_hr_payslip_line_analytics', None),
        ('Payroll Explorer', 'pb_explorer.action_pb_explorer', None),
    ],
}


# kind: count, sum, avg, or rate.  Rate numerators and denominators are
# separate filtered aggregates over exactly the same cohort and date range.
# A snapshot never invents a historical series from today's status.
MEASURES = {
    'people': {
        'employees': dict(label='Active employee records', model='hr.employee',
                          domain=[('active', '=', True)], company='company_id',
                          date=None, dimensions=('department', 'company'),
                          note='Active employee records today, including people without a running contract.'),
        'working': dict(label='Employees with a running contract', model='hr.employee',
                        domain=[('active', '=', True), ('contract_id.state', '=', 'open')],
                        company='company_id', date=None,
                        dimensions=('department', 'company'),
                        note='Active employees whose current contract is open today. This is not payroll people paid.'),
        'joined': dict(label='First contracts started', model='hr.employee',
                       domain=[('active', '=', True), ('first_contract_date', '!=', False)],
                       company='company_id', date='first_contract_date',
                       dimensions=('department', 'company'),
                       note='Active employee records by first contract start date; former employees are excluded.'),
    },
    'workforce': {
        'checkins': dict(label='Attendance check-ins', model='hr.attendance',
                         company='employee_id.company_id', employee='employee_id',
                         date='check_in', dimensions=('department', 'company'),
                         note='Attendance events, not distinct employees or paid days.'),
        'open_checkouts': dict(label='Open check-outs', model='hr.attendance',
                               company='employee_id.company_id', employee='employee_id',
                               date='check_in', domain=[('check_out', '=', False)],
                               dimensions=('department', 'company'),
                               note='Check-ins in the selected period without a check-out.'),
        'approved_leave': dict(label='Approved leave requests', model='hr.leave',
                               company='employee_id.company_id', employee='employee_id',
                               date='request_date_from', domain=[('state', '=', 'validate')],
                               dimensions=('department', 'company'),
                               note='Approved leave requests by requested start date, not leave days.'),
    },
    'expenses': {
        'submitted': dict(label='Claims submitted', model='pb.expense.claim',
                          company='company_id', employee='employee_id',
                          date='submitted_on', domain=[('state', 'in', ['submitted', 'approved', 'paid'])],
                          dimensions=('department', 'company', 'status'),
                          note='Claims sent for review in the selected period.'),
        'pending': dict(label='Claims awaiting approval', model='pb.expense.claim',
                        company='company_id', employee='employee_id',
                        date='submitted_on', domain=[('state', '=', 'submitted')],
                        dimensions=('department', 'company'),
                        note='Still awaiting approval, among claims submitted in the selected period.'),
        'approved_value': dict(label='Approved claim value', model='pb.expense.claim',
                               company='company_id', employee='employee_id',
                               date='submitted_on', domain=[('state', 'in', ['approved', 'paid'])],
                               kind='sum', value='total', currency='currency_id',
                               dimensions=('department', 'company'),
                               note='Approved or paid claims by submission date; shown only for one currency.'),
        'trips': dict(label='Trips started', model='pb.business.trip',
                      company='company_id', date='date_from',
                      domain=[('state', 'not in', ['refused', 'cancelled'])],
                      dimensions=('department', 'company', 'status'),
                      note='Trips whose start date is in the selected period.'),
    },
    'hiring': {
        'agreed': dict(label='Roles opened', model='pb.hiring.requisition',
                       company='company_id', date='opened_on',
                       domain=[('opened_on', '!=', False)],
                       dimensions=('department', 'company', 'status'),
                       note='Hiring roles by the date they opened to candidates.'),
        'filled': dict(label='Opened roles now filled', model='pb.hiring.requisition',
                       company='company_id', date='opened_on',
                       domain=[('opened_on', '!=', False), ('state', '=', 'filled')],
                       dimensions=('department', 'company'),
                       note='Of roles opened in the period, those currently marked filled.'),
        'open': dict(label='Opened roles still open', model='pb.hiring.requisition',
                     company='company_id', date='opened_on',
                     domain=[('opened_on', '!=', False), ('state', '=', 'open')],
                     dimensions=('department', 'company'),
                     note='Of roles opened in the period, those currently open.'),
    },
    'talent': {
        'sheets': dict(label='Goal sheets', model='pb.goal.set',
                       company='company_id', date='create_date',
                       dimensions=('department', 'company', 'status', 'cycle'),
                       note='Goal sheets by creation date; one sheet per person per goal year.'),
        'agreed': dict(label='Agreed goal sheets', model='pb.goal.set',
                       company='company_id', date='create_date',
                       domain=[('state', 'in', ['locked', 'closed'])],
                       dimensions=('department', 'company', 'cycle'),
                       note='Sheets created in the period and now agreed or closed.'),
        'progress': dict(label='Average goal progress', model='pb.goal.set',
                         company='company_id', date=None, kind='avg', value='progress',
                         dimensions=('department', 'company', 'cycle'),
                         note='Average of each visible sheet’s weighted progress today, in percent.'),
    },
    'learning': {
        'assigned': dict(label='Training assignments', model='pb.training.assignment',
                         company='company_id', employee='employee_id',
                         date='assigned_on', dimensions=('department', 'company', 'course', 'status'),
                         note='Course assignments made in the selected period.'),
        'completed': dict(label='Assignments now finished', model='pb.training.assignment',
                          company='company_id', employee='employee_id',
                          date='assigned_on', domain=[('state', '=', 'done')],
                          dimensions=('department', 'company', 'course'),
                          note='Assignments made in the period that are finished today.'),
        'completion': dict(label='Assignment completion rate', model='pb.training.assignment',
                           company='company_id', employee='employee_id',
                           date='assigned_on', kind='rate',
                           numerator=[('state', '=', 'done')],
                           denominator=[('state', '!=', 'excused')],
                           dimensions=('department', 'company', 'course'),
                           note='Finished divided by assignments made in the period, excluding approved extensions.'),
        'overdue': dict(label='Assignments now overdue', model='pb.training.assignment',
                        company='company_id', employee='employee_id',
                        date='assigned_on', domain=[('state', '=', 'overdue')],
                        dimensions=('department', 'company', 'course'),
                        note='Assignments made in the period that are overdue today.'),
    },
}


class PbModuleInsights(models.AbstractModel):
    _name = 'pb.module.insights'
    _description = 'Module Insights measures and report catalogue'

    def _company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    def _allowed(self, area):
        user = self.env.user
        if area == 'payroll':
            if 'pb.explorer' not in self.env.registry.models:
                return False
            try:
                self.env['pb.explorer']._require()
                return True
            except AccessError:
                return False
        if area == 'workforce':
            if 'pb.workforce.insights' not in self.env.registry.models:
                return False
            try:
                self.env['pb.workforce.insights']._require()
                return True
            except AccessError:
                return False
        if area == 'people':
            return (user.has_group('base.group_system') or
                    user.has_group('hr.group_hr_user') or
                    user.has_group('pb_records.group_records_viewer') or
                    user.has_group('pb_demo.group_payobook_demo'))
        if area == 'expenses':
            return user.has_group('hr_expense.group_hr_expense_team_approver') or user._is_admin()
        if area == 'hiring':
            if 'pb.hiring' not in self.env.registry.models:
                return False
            return bool(self.env['pb.hiring'].can_open())
        if area == 'talent':
            if 'pb.goals.analytics' not in self.env.registry.models:
                return False
            return bool(self.env['pb.goals.analytics']._can_read())
        if area == 'learning':
            if 'pb.training.analytics' not in self.env.registry.models:
                return False
            return bool(self.env['pb.training.analytics']._can_read())
        return False

    def _require_area(self, area):
        if area not in REPORTS:
            raise UserError(_('Unknown Insights area.'))
        if not self._allowed(area):
            raise AccessError(_('You do not have access to these insights.'))

    @api.model
    def catalogue(self, area='all'):
        if area != 'all':
            self._require_area(area)
        result = []
        for key, entries in REPORTS.items():
            if area not in ('all', key) or not self._allowed(key):
                continue
            for label, xmlid, lens in entries:
                if not self.env.ref(xmlid, raise_if_not_found=False):
                    continue
                if xmlid.startswith('pb_workforce_insights.') and not self._allowed('workforce'):
                    continue
                if xmlid == 'pb_hr_workforce.action_payroll_report_dashboard':
                    if not any(self.env.user.has_group(group) for group in (
                        'om_hr_payroll.group_hr_payroll_manager',
                        'pb_hr_payroll_base.group_payroll_base_officer',
                        'pb_demo.group_payobook_demo')):
                        continue
                result.append({'area': key, 'label': label,
                               'xmlid': xmlid, 'lens': lens or ''})
        return result

    @api.model
    def measures(self, area):
        self._require_area(area)
        if area == 'payroll':
            return {'measures': [], 'payroll': True}
        return {'measures': [
            {'key': key, 'label': spec['label'], 'note': spec['note'],
             'dimensions': list(spec['dimensions']), 'has_time': bool(spec['date']),
             'kind': spec.get('kind', 'count')}
            for key, spec in MEASURES[area].items()], 'payroll': False}

    def _source(self, area, spec):
        model = self.env[spec['model']]
        if area in ('workforce', 'talent', 'learning'):
            return model.sudo()
        model.check_access('read')
        return model

    def _domain(self, spec, months):
        domain = [(spec['company'], 'in', self._company_ids())]
        domain += list(spec.get('domain', []))
        if spec['date']:
            today = fields.Date.today()
            start = today.replace(day=1) - relativedelta(months=months - 1)
            domain.append((spec['date'], '>=', fields.Date.to_string(start)))
            if self.env[spec['model']]._fields[spec['date']].type == 'datetime':
                domain.append((spec['date'], '<', fields.Date.to_string(today + timedelta(days=1))))
            else:
                domain.append((spec['date'], '<=', fields.Date.to_string(today)))
        return domain

    def _dimension_field(self, model, spec, dimension):
        if dimension == 'department':
            if 'department_id' in model._fields and model._fields['department_id'].store:
                return 'department_id', False
            if spec.get('employee'):
                return spec['employee'], True
        return {'company': 'company_id', 'status': 'state',
                'course': 'channel_id', 'cycle': 'cycle_id'}.get(dimension), False

    def _group_rows(self, model, spec, domain, dimension, over):
        if dimension == 'department' and model._name == 'hr.employee':
            if model.search_count(domain) > 50000:
                raise UserError(_('This employee breakdown is too large; narrow the company selection.'))
            fields_to_read = ['id', 'department_id']
            if over == 'month' and spec['date']:
                fields_to_read.append(spec['date'])
            people = model.search_read(domain, fields_to_read)
            counts = defaultdict(int)
            for person in people:
                dept = person['department_id'] or (0, _('Unassigned'))
                month = str(person.get(spec['date']) or '')[:7] if over == 'month' and spec['date'] else ''
                counts[(tuple(dept), month)] += 1
            rows = []
            for (dept, month), count in counts.items():
                row = {'department_id': dept, '__count': count}
                if month:
                    row['%s:month' % spec['date']] = month
                    row['__range'] = {'%s:month' % spec['date']: {'from': month + '-01'}}
                rows.append(row)
            return rows, 'department_id', False
        dim_field, employee_rollup = self._dimension_field(model, spec, dimension)
        if dim_field not in model._fields:
            if dimension == 'company' and spec.get('employee'):
                dim_field, employee_rollup = spec['employee'], True
            else:
                raise UserError(_('This breakdown is unavailable for this measure.'))
        groupby = [dim_field]
        time_field = spec['date']
        if over == 'month' and time_field:
            groupby.append('%s:month' % time_field)
        value = spec.get('value')
        kind = spec.get('kind', 'count')
        aggregates = [dim_field]
        if value and kind in ('sum', 'avg'):
            aggregates.append('%s:%s' % (value, kind))
        rows = model.read_group(domain, aggregates, groupby, lazy=False)
        return rows, dim_field, employee_rollup

    def _rollup(self, rows, dim_field, employee_rollup, dimension, spec, over):
        employee_info = {}
        if employee_rollup:
            employee_ids = [r[dim_field][0] for r in rows if r.get(dim_field)]
            if employee_ids:
                emps = self.env['hr.employee'].sudo().browse(employee_ids).exists()
                # The source rows were already limited by company and their
                # model's reporting gate.  This reads only matching labels.
                for emp in emps:
                    target = emp.company_id if dimension == 'company' else emp.department_id
                    employee_info[emp.id] = (target.id, target.name) if target else (0, _('Unassigned'))
        buckets = defaultdict(lambda: {'count': 0, 'sum': 0.0, 'weighted': 0.0})
        for row in rows:
            raw = row.get(dim_field)
            if employee_rollup:
                key, label = employee_info.get(raw[0], (0, _('Unassigned'))) if raw else (0, _('Unassigned'))
            elif isinstance(raw, (tuple, list)):
                key, label = raw[0], raw[1]
            else:
                key, label = raw or '', str(raw or _('Unassigned'))
            month = ''
            month_sort = ''
            if over == 'month' and spec['date']:
                part = row.get('%s:month' % spec['date'])
                month = str(part or '')
                month_sort = ((row.get('__range') or {}).get('%s:month' % spec['date']) or {}).get('from', '')
            bucket = buckets[(str(key), str(label), month)]
            bucket['sort'] = month_sort
            count = row.get('__count', 0)
            bucket['count'] += count
            value = spec.get('value')
            if value:
                amount = float(row.get(value) or 0.0)
                bucket['sum'] += amount
                bucket['weighted'] += amount * count
        return buckets

    @api.model
    def explore(self, area, measure, dimension='department', over='month', months=6):
        self._require_area(area)
        if area == 'payroll':
            raise UserError(_('Open Payroll Explorer for payroll measures.'))
        spec = MEASURES[area].get(measure)
        if not spec:
            raise UserError(_('Unknown measure.'))
        if dimension not in spec['dimensions'] or over not in ('month', 'total'):
            raise UserError(_('Unknown Insights breakdown.'))
        try:
            months = int(months)
        except (TypeError, ValueError):
            raise UserError(_('Choose 3, 6 or 12 months.'))
        if months not in (3, 6, 12):
            raise UserError(_('Choose 3, 6 or 12 months.'))
        if not spec['date']:
            over = 'total'
        model = self._source(area, spec)
        domain = self._domain(spec, months)
        if area == 'learning' and measure in ('completed', 'completion', 'overdue'):
            # The native Learning numbers board refreshes assignment status
            # before counting it.  Use the same operation on this cohort so
            # the two screens agree about finished and overdue work.
            model.search(domain)._refresh()
        kind = spec.get('kind', 'count')
        currency = ''
        if kind == 'sum' and spec.get('currency'):
            currencies = model.read_group(domain, [spec['currency']], [spec['currency']], lazy=False)
            ids = [r[spec['currency']][0] for r in currencies if r.get(spec['currency']) and r.get('__count')]
            if len(ids) > 1:
                raise UserError(_('Select companies with one currency before adding claim amounts.'))
            if ids:
                currency = self.env['res.currency'].browse(ids[0]).symbol or ''
        if kind == 'rate':
            denominator = domain + spec['denominator']
            numerator = domain + spec['numerator']
            den_rows, dim_field, rollup = self._group_rows(model, spec, denominator, dimension, over)
            num_rows = self._group_rows(model, spec, numerator, dimension, over)[0]
            den = self._rollup(den_rows, dim_field, rollup, dimension, spec, over)
            num = self._rollup(num_rows, dim_field, rollup, dimension, spec, over)
            values = [(key, (100.0 * num.get(key, {}).get('count', 0) / val['count'])
                       if val['count'] else 0.0, val['count']) for key, val in den.items()]
            total_den = model.search_count(denominator)
            total_num = model.search_count(numerator)
            total = (100.0 * total_num / total_den) if total_den else 0.0
        else:
            rows, dim_field, rollup = self._group_rows(model, spec, domain, dimension, over)
            buckets = self._rollup(rows, dim_field, rollup, dimension, spec, over)
            if kind == 'sum':
                values = [(key, val['sum'], val['count']) for key, val in buckets.items()]
                total = sum(item[1] for item in values)
            elif kind == 'avg':
                values = [(key, val['weighted'] / val['count'] if val['count'] else 0.0,
                           val['count']) for key, val in buckets.items()]
                count = sum(count for _, _, count in values)
                total = sum(item[1] * item[2] for item in values) / count if count else 0.0
            else:
                values = [(key, val['count'], val['count']) for key, val in buckets.items()]
                total = sum(item[1] for item in values)
        result = [{'key': key[0], 'label': key[1], 'period': key[2],
                   'period_key': val.get('sort', ''),
                   'value': round(value, 2), 'records': count}
                  for key, value, count in values
                  for val in [buckets.get(key, {}) if kind != 'rate' else den.get(key, {})]]
        result.sort(key=lambda row: (row['period_key'], -row['value'], row['label']))
        return {'area': area, 'measure': measure, 'label': spec['label'],
                'note': spec['note'], 'kind': kind, 'dimension': dimension,
                'over': over, 'months': months, 'currency': currency,
                'total': round(total, 2), 'rows': result,
                'record_count': sum(row['records'] for row in result)}

    @api.model
    def overview(self, area):
        self._require_area(area)
        if area == 'payroll':
            return {'tiles': []}
        tiles = []
        for key, spec in list(MEASURES[area].items())[:3]:
            try:
                data = self.explore(area, key, spec['dimensions'][0], 'total', 6)
                tiles.append({'key': key, 'label': data['label'], 'value': data['total'],
                              'kind': data['kind'], 'currency': data['currency'],
                              'note': data['note']})
            except UserError as error:
                tiles.append({'key': key, 'label': spec['label'], 'value': None,
                              'kind': spec.get('kind', 'count'), 'currency': '',
                              'note': str(error)})
        return {'tiles': tiles}
