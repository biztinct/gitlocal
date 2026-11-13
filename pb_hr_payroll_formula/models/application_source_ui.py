"""Business-facing payroll sources and actionable readiness, without changing approvals."""
from collections import OrderedDict
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

OWNER_NAMES = {
    'hr.payslip': 'Payroll history', 'hr.employee': 'Employee profile', 'hr.contract': 'Employment contract',
    'hr.contract.advantage': 'Contract pay components', 'resource.calendar': 'Work calendar',
    'hr.leave': 'Time off', 'hr.leave.allocation': 'Leave balances',
    'hr.overtime.request': 'Overtime', 'pb.timesheet.packet': 'Timesheets & attendance',
    'hr.attendance': 'Attendance', 'hr.payroll.period.input': 'Monthly adjustments',
    'pb.resignation': 'Offboarding', 'pb.exit.clearance': 'Exit clearance',
    'hr.full.final.settlement': 'Final settlement', 'pb.asset.assignment': 'Asset assignments',
    'pb.probation.review': 'Probation reviews', 'pb.employee.document': 'Employee documents',
    'pb.incentive': 'Awards & incentives', 'res.partner.bank': 'Bank details',
    'pb.feedback.request': 'Employee feedback', 'hr.formula.config': 'Payroll settings',
}


class ApplicationSourceSettings(models.Model):
    _inherit = 'hr.formula.config'

    application_input_rule_ids = fields.One2many(
        'hr.formula.rule', 'config_id', domain=[('column_type', '=', 'input')],
        string='Application input mappings')

    def _application_source_display(self, key, spec=None):
        spec = spec if spec is not None else self._application_source_catalogue().get(key, {})
        model = spec.get('model', '')
        if not model:
            if key == 'application.mode': model = 'hr.formula.config'
            elif key in ('period.standard_days', 'period.public_holiday_days'): model = 'resource.calendar'
            elif '.ot.' in key or key.endswith('bonus_hours'): model = 'hr.overtime.request'
            elif 'regular_work' in key: model = 'pb.timesheet.packet'
            elif key.startswith('period.'): model = 'hr.leave'
        owner = OWNER_NAMES.get(model, 'Application records')
        if key in ('period.paid_day_equivalents', 'period.nonpayable_day_equivalents'):
            owner = 'Calendar, time off & attendance' if self.payroll_basis == 'timesheet' else 'Calendar & time off'
        label = (spec.get('label') or 'Choose a source').removeprefix('Approved period input: ')
        return {'owner': owner, 'model': model, 'label': label,
                'description': 'Approved amounts for this employee and pay period.' if key.startswith('period.input.') else
                'Calculated from the employee’s work calendar and approved records.' if key.startswith('period.') else
                'Read from the connected record. Payroll does not approve or change it.'}

    def application_source_options(self):
        self.ensure_one()
        self._application_require_access()
        return [dict(v, key=k, **self._application_source_display(k, v))
                for k, v in self._application_source_catalogue().items()
                if v.get('persist_in_payroll') is not False]

    def action_application_source_settings(self):
        self.ensure_one()
        self._application_require_access()
        return {'type': 'ir.actions.client', 'name': _('Payroll sources'),
                'tag': 'pb_application_sources', 'params': {'config_id': self.id}}

    def application_source_workspace(self):
        self.ensure_one()
        self._application_require_access()
        self = self.sudo(False)
        mappings = self.env['hr.payslip.import.mapping'].search([('salary_structure_id', '=', self.id)])
        catalogue = self._application_source_catalogue()
        rows = []
        for rule in self.rule_ids.filtered(lambda r: r.column_type == 'input' and r.application_source_key != 'application.mode'):
            key = rule.application_source_key or ''
            spec = catalogue.get(key, {})
            mapping = mappings.filtered(lambda m: m.component_id == rule)[:1]
            native_model = (mapping.target_model_id.model if mapping else '') or ('hr.contract.advantage' if rule.is_contract_component else '')
            native_label = (mapping.target_field_id.field_description if mapping else '') or ('Contract pay component' if rule.is_contract_component else 'No saved-record mapping')
            display = self._application_source_display(key, spec) if key else {
                'owner': OWNER_NAMES.get(native_model, 'Not connected'), 'model': native_model,
                'label': native_label, 'description': 'Uses the existing saved-record mapping.'}
            pending = bool(key and (not spec or spec.get('requires_domain_review') or not spec.get('available', True)))
            rows.append(dict(display, id=rule.id, name=rule.name, code=rule.code, key=key,
                kind=rule.value_kind, required=bool(rule.application_source_required),
                zero_allowed=bool(rule.application_zero_allowed), pending=pending,
                status='Needs review' if pending else 'Connected' if key or native_model else 'Choose a source',
                native_label=native_label, technical_note=rule.application_source_note or ''))
        can_edit = True
        try: self._application_require_access(certify=True)
        except AccessError: can_edit = False
        return {'id': self.id, 'name': self.name, 'company': self.company_id.name,
                'country': self.country_code, 'currency': self.currency_id.name,
                'stamp': self._application_settings_stamp(), 'can_edit': can_edit,
                'settings': {n: str(self[n]) if n == 'application_effective_from' and self[n] else self[n]
                    for n in ('application_data_enabled', 'application_effective_from', 'payroll_basis', 'standard_day_basis', 'fixed_standard_days')},
                'rows': rows, 'options': self.application_source_options()}

    def application_save_sources(self, stamp, settings, changes):
        self.ensure_one()
        self._application_require_access(certify=True)
        self = self.sudo(False)
        self.check_access('write')
        if stamp != self._application_settings_stamp():
            raise UserError(_('These settings changed in another session. Reload before saving.'))
        allowed = {'application_data_enabled', 'application_effective_from', 'payroll_basis', 'standard_day_basis', 'fixed_standard_days'}
        if not isinstance(settings, dict) or set(settings) - allowed:
            raise ValidationError(_('Use the payroll source settings controls.'))
        if settings.get('payroll_basis', self.payroll_basis) not in ('contractual', 'timesheet') or settings.get('standard_day_basis', self.standard_day_basis) not in ('calendar', 'fixed'):
            raise ValidationError(_('Choose a supported payroll and calendar basis.'))
        catalogue = self._application_source_catalogue()
        rules = {r.id: r for r in self.rule_ids if r.column_type == 'input'}
        if not isinstance(changes, list):
            raise ValidationError(_('Choose inputs using the source picker.'))
        seen = set()
        for change in changes:
            if not isinstance(change, dict) or set(change) != {'id', 'key'} or not isinstance(change['id'], int) or not isinstance(change['key'], str) or change['id'] not in rules or change['id'] in seen:
                raise ValidationError(_('Choose an input from this payroll configuration.'))
            seen.add(change['id'])
            rule, key = rules[change['id']], change['key']
            if rule.application_source_key == 'application.mode' or key == 'application.mode':
                raise ValidationError(_('The payroll calculation switch is managed automatically.'))
            if key:
                spec = catalogue.get(key)
                if not spec or spec.get('persist_in_payroll') is False or spec.get('requires_domain_review') or not spec.get('available', True):
                    raise ValidationError(_('This source needs review before it can be used.'))
                if key.startswith('period.input.') and key != 'period.input.' + rule.code:
                    raise ValidationError(_('Monthly adjustments must match the selected payroll item.'))
            rule.write({'application_source_key': key or False})
        self.write(settings)
        return self.application_source_workspace()

    def _application_workbook_suggestions(self, employee, start, end):
        """Read-only worksheet suggestions, never a signed payroll readiness result.

        Counts use approved records; pending/conflicting sources stay blank.
        Completeness remains a separate manager decision during payroll review.
        No certification, reservation, approval or source mutation is persisted.
        """
        contract, ambiguous = self._application_contract(employee, start, end)
        if not contract or ambiguous:
            return {}
        facts = self._application_time_values(employee, contract, start, end,
            {'channels': dict.fromkeys(('leave', 'overtime', 'timesheets', 'adjustments'), True)})
        facts.update(self._application_domain_values(employee, contract, start, end))
        return facts

    def _application_readiness_groups(self, answer, start, end):
        """Keep the execution gate intact; present repeated employee failures once."""
        catalogue = self._application_source_catalogue()
        rules = {r.code: r for r in self.rule_ids}
        if not self.application_data_enabled or not self.application_effective_from or start < self.application_effective_from:
            return [{'id': 'setup', 'kind': 'setup', 'title': 'Choose a supported pay period',
                     'message': 'Application payroll is turned off. Enable it in Payroll sources.' if not self.application_data_enabled else ('Application payroll starts on %s. This run starts on %s. Choose a period on or after the start date, or review the start date in Payroll sources.' % (self.application_effective_from, start)) if self.application_effective_from else 'Set an application payroll start date in Payroll sources.',
                     'count': answer['summary']['employees'], 'items': [], 'action_label': 'Review payroll setup', 'code': ''}]
        grouped = OrderedDict()
        for block in answer['blockers']:
            key, code, reason = block.get('key', ''), block.get('code', ''), block['reason']
            rule = rules.get(code)
            channel = key if key in ('leave', 'overtime', 'adjustments', 'timesheets') else None
            if not channel and block.get('status') != 'conflict' and ('certif' in reason.lower() or 'completeness' in reason.lower()):
                channel = 'overtime' if 'overtime' in reason.lower() else 'timesheets' if 'timesheet' in reason.lower() else 'leave' if 'leave' in reason.lower() else None
            if channel:
                kind, group_id = 'review', 'review:' + channel
                title = {'leave': 'Review time off for this period', 'overtime': 'Review overtime for this period', 'adjustments': 'Review monthly adjustments for this period', 'timesheets': 'Review timesheets and attendance'}[channel]
                message = 'Review the records, then confirm this section is complete above. This confirmation covers the selected employees once.'
            else:
                kind = 'adjustments' if key.startswith('period.input.') else 'overtime' if '.ot.' in key or 'overtime' in reason.lower() else 'timesheets' if ('timesheet' in reason.lower() or 'attendance' in reason.lower()) else 'leave' if ('leave' in key or 'unpaid' in key or 'leave' in reason.lower() or 'time off' in reason.lower()) else 'contract' if ('contract' in reason.lower() or 'calendar' in reason.lower()) else 'source'
                group_id = '%s:%s:%s' % (kind, code if kind in ('source', 'adjustments') else '', reason)
                title = (rule.name if rule else {'leave': 'Time off needs attention', 'overtime': 'Overtime needs attention', 'timesheets': 'Timesheets need attention', 'contract': 'Check employment and work calendars'}.get(kind, 'Check the source record'))
                message = ('No approved amount is available for this pay period. Enter and approve the amount, or confirm zero below only if nobody has this item.' if kind == 'adjustments' and 'Exactly one' in reason else reason)
            if group_id not in grouped:
                grouped[group_id] = {'id': group_id, 'kind': kind, 'channel': channel or '', 'code': code,
                    'title': title, 'message': message, 'owner': self._application_source_display(key, catalogue.get(key, {}))['owner'],
                    'items': [], 'action_label': {'review': 'Open records', 'leave': 'Review time off', 'overtime': 'Review overtime', 'timesheets': 'Review timesheets', 'contract': 'Open employment records', 'adjustments': 'Review adjustments', 'source': 'Open source records'}[kind]}
            group = grouped[group_id]
            if not any(i['employee_id'] == block['employee_id'] for i in group['items']):
                group['items'].append({'employee_id': block['employee_id'], 'employee': block['employee'], 'code': code})
        groups = list(grouped.values())
        for group in groups: group['count'] = len(group['items'])
        return sorted(groups, key=lambda g: (g['kind'] != 'review', -g['count'], g['title']))

    def application_issue_action(self, employee_ids, date_from, date_to, kind, code='', employee_id=False):
        self.ensure_one()
        self._application_require_access()
        start, end = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        if not start or not end or end < start: raise ValidationError(_('Choose a valid period.'))
        people = self.env['hr.employee'].sudo(False).browse(employee_ids).exists()
        if not people or len(people) != len(set(employee_ids)):
            raise AccessError(_('Choose employees from this payroll.'))
        people.check_access('read')
        if any(e.company_id != self.company_id for e in people): raise AccessError(_('Choose employees in this company.'))
        if employee_id:
            if employee_id not in people.ids: raise AccessError(_('Choose an employee from this payroll.'))
            people = people.filtered(lambda e: e.id == employee_id)
        rule = self.rule_ids.filtered(lambda r: r.code == code)[:1]
        key = rule.application_source_key or ''
        if kind == 'setup': return self.action_application_source_settings()
        models_by_kind = {'leave': 'hr.leave', 'overtime': 'hr.overtime.request', 'timesheets': 'pb.timesheet.packet', 'contract': 'hr.contract', 'adjustments': 'hr.payroll.period.input'}
        model = models_by_kind.get(kind)
        if kind == 'source':
            model = self._application_source_display(key)['model'] if key else ''
            if not model:
                mapping = self.env['hr.payslip.import.mapping'].search([('salary_structure_id', '=', self.id), ('component_id', '=', rule.id)], limit=1)
                model = mapping.target_model_id.model or ('hr.contract' if rule.is_contract_component else 'hr.employee')
        if model == 'resource.calendar': model = 'hr.contract'
        if not model or model not in self.env: return self.action_application_source_settings()
        allowed = set(OWNER_NAMES) - {'hr.formula.config', 'hr.contract.advantage', 'res.partner.bank'}
        if model not in allowed: return self.action_application_source_settings()
        obj = self.env[model].sudo(False)
        obj.check_access('read')
        domain = [('id', 'in', people.ids)] if model == 'hr.employee' else [('employee_id', 'in', people.ids)] if 'employee_id' in obj._fields else []
        if 'company_id' in obj._fields: domain.append(('company_id', '=', self.company_id.id))
        context = dict(self.env.context)
        if len(people) == 1 and 'employee_id' in obj._fields: context['default_employee_id'] = people.id
        if model == 'hr.payroll.period.input':
            domain += [('config_id', '=', self.id), ('date_from', '=', start), ('date_to', '=', end)]
            if rule: domain.append(('component_id', '=', rule.id))
            context.update(default_config_id=self.id, default_date_from=str(start), default_date_to=str(end), default_company_id=self.company_id.id)
            if rule: context['default_component_id'] = rule.id
        elif model == 'hr.leave': domain += [('request_date_from', '<=', end), ('request_date_to', '>=', start)]
        elif model == 'hr.overtime.request': domain += [('date', '>=', start), ('date', '<=', end)]
        elif model == 'pb.timesheet.packet': domain += [('week_start', '<=', end), ('week_end', '>=', start)]
        elif model == 'hr.attendance': domain += [('check_in', '<', str(fields.Date.add(end, days=1))), ('check_out', '>=', str(start))]
        elif model == 'hr.payslip': domain += [('date_from', '<=', end), ('date_to', '>=', start)]
        elif model == 'hr.contract': domain += [('date_start', '<=', end), '|', ('date_end', '=', False), ('date_end', '>=', start)]
        records = obj.search(domain, limit=2)
        return {'type': 'ir.actions.act_window', 'name': OWNER_NAMES.get(model, 'Source records'),
                'res_model': model, 'domain': domain, 'context': context,
                'views': [(False, 'form')] if len(records) == 1 else [(False, 'list'), (False, 'form')],
                'res_id': records.id if len(records) == 1 else False, 'target': 'current'}
