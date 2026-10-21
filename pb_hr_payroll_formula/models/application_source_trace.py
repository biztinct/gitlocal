"""Explain a payroll input and navigate to its owners without changing any records."""
import re
from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .application_source_ui import OWNER_NAMES


class ApplicationSourceTrace(models.Model):
    _inherit = 'hr.formula.config'

    def _source_trace_rule(self, component_id):
        self.ensure_one()
        self._application_require_access()
        self.check_access('read')
        rule = self.rule_ids.filtered(lambda r: r.id == component_id and r.column_type == 'input' and r.application_source_key != 'application.mode')
        if not rule:
            raise ValidationError(_('Choose an input from this payroll configuration.'))
        rule.check_access('read')
        return rule

    def _source_trace_models(self, rule):
        key = rule.application_source_key or ''
        row = next(r for r in self.application_source_workspace()['rows'] if r['id'] == rule.id)
        model = row['model']
        if key in ('period.paid_day_equivalents', 'period.nonpayable_day_equivalents'):
            result = ['hr.contract', 'resource.calendar', 'hr.leave']
            if self.payroll_basis == 'timesheet': result += ['pb.timesheet.packet', 'hr.attendance']
        elif key == 'period.standard_days': result = ['hr.contract', 'resource.calendar']
        elif model == 'hr.contract.advantage': result = ['hr.contract']
        else: result = [model] if model in OWNER_NAMES else []
        return [m for m in result if m in self.env and m != 'hr.formula.config']

    def application_source_detail(self, component_id):
        rule = self._source_trace_rule(component_id)
        row = next(r for r in self.application_source_workspace()['rows'] if r['id'] == rule.id)
        key = rule.application_source_key or ''
        explanation = row['description']
        if key == 'period.paid_day_equivalents':
            explanation = ('Scheduled working days within employment dates − unpaid portions of approved leave. Fully paid leave stays included once.'
                if self.payroll_basis == 'contractual' else
                'Approved regular working hours converted to days + paid portions of approved leave + public holiday credit. Timesheets must reconcile with attendance; overlapping time is rejected.')
        elif key == 'period.nonpayable_day_equivalents':
            explanation = 'Standard days − paid day equivalents. This includes dates outside employment and unpaid portions of leave; it is not just an unpaid-leave total.'
        elif key == 'period.standard_days':
            explanation = ('Scheduled working days in the selected month, using the contract work calendar or the employee calendar when no contract calendar is set.' if self.standard_day_basis == 'calendar' else 'Fixed monthly divisor: %s days. The payable share still follows the employee’s work calendar.' % self.fixed_standard_days)
        elif key == 'period.unpaid_day_equivalents':
            explanation = 'Approved leave on scheduled days × its unpaid fraction. A half-paid day contributes 0.5 unpaid days; overlapping leave needs review.'
        elif key.startswith('period.input.'):
            explanation = 'The approved monthly adjustment for this employee, payroll item and exact pay period. Missing, pending or conflicting amounts need review; missing does not automatically mean zero.'
        elif '.ot.' in key:
            explanation = 'Approved overtime hours of this category in the selected period. In timesheet mode they must also appear in approved daily timesheets. Payroll applies the rate in the consuming formula.'
        actions = []
        for model in self._source_trace_models(rule):
            try: self.env[model].sudo(False).check_access('read')
            except AccessError: continue
            actions.append({'model': model, 'label': OWNER_NAMES[model]})
        # Dependencies use the current scheme's column letters, not old workbook positions.
        formulas = self.rule_ids.filtered(lambda r: r.column_type == 'formula')
        seen, frontier, consumers = {rule.id}, {rule.column_letter, rule.code}, []
        depth = 0
        while frontier:
            following = set()
            for target in formulas:
                refs = {re.sub(r'\d+$', '', s.strip().replace('$', '')) for s in (target.formula_dependencies or '').split(',')}
                if target.id in seen or not (refs & frontier): continue
                seen.add(target.id)
                consumers.append({'id': target.id, 'name': target.name, 'direct': depth == 0,
                                  'formula': target.excel_formula or ''})
                following.update((target.column_letter, target.code))
            frontier = following - {False, ''}
            depth += 1
        people = self.env['hr.employee'].sudo(False).search([('company_id', '=', self.company_id.id)], order='name')
        return dict(row, explanation=explanation, actions=actions, consumers=consumers,
            normalization=('Fixed divisor %s scales the payable share of scheduled days.' % self.fixed_standard_days
                if key.startswith('period.') and self.standard_day_basis == 'fixed' else ''),
            employees=[{'id': e.id, 'name': e.name} for e in people], company=self.company_id.name,
            direction='Application records → Payroll input',
            spreadsheet='A mapped monthly spreadsheet can supply this input instead. Moving a column between worksheets does not change its application source.')

    def application_source_record_action(self, component_id, model, employee_id=False, date_from=False, date_to=False):
        rule = self._source_trace_rule(component_id)
        if model not in self._source_trace_models(rule):
            raise AccessError(_('This record type does not supply the selected payroll item.'))
        obj = self.env[model].sudo(False)
        obj.check_access('read')
        people = self.env['hr.employee'].sudo(False).search([('company_id', '=', self.company_id.id)] + ([('id', '=', employee_id)] if employee_id else []))
        if employee_id and len(people) != 1: raise AccessError(_('Choose an employee in this company.'))
        start, end = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        if bool(start) != bool(end) or (start and end < start): raise ValidationError(_('Choose a valid start and end date.'))
        domain = [('id', 'in', people.ids)] if model == 'hr.employee' else [('employee_id', 'in', people.ids)] if 'employee_id' in obj._fields else []
        if 'company_id' in obj._fields: domain += [('company_id', 'in', [False, self.company_id.id])] if model == 'resource.calendar' else [('company_id', '=', self.company_id.id)]
        if model == 'resource.calendar':
            contracts = self.env['hr.contract'].sudo(False).search([('employee_id', 'in', people.ids), ('company_id', '=', self.company_id.id)] + ([('date_start', '<=', end), '|', ('date_end', '=', False), ('date_end', '>=', start)] if start else []))
            domain += [('id', 'in', (contracts.resource_calendar_id | people.resource_calendar_id).ids)]
        elif model == 'res.partner.bank': domain += [('id', 'in', people.bank_account_id.ids)]
        if model == 'hr.payroll.period.input':
            domain += [('config_id', '=', self.id), ('component_id', '=', rule.id)]
            if start: domain += [('date_from', '=', start), ('date_to', '=', end)]
        elif start:
            if model in ('hr.contract', 'hr.payslip'):
                a, b = ('date_start', 'date_end') if model == 'hr.contract' else ('date_from', 'date_to')
                domain += [(a, '<=', end), '|', (b, '=', False), (b, '>=', start)]
            elif model == 'hr.leave': domain += [('request_date_from', '<=', end), ('request_date_to', '>=', start)]
            elif model == 'hr.overtime.request': domain += [('date', '>=', start), ('date', '<=', end)]
            elif model == 'pb.timesheet.packet': domain += [('week_start', '<=', end), ('week_end', '>=', start)]
            elif model == 'hr.attendance': domain += [('check_in', '<', str(fields.Date.add(end, days=1))), '|', ('check_out', '=', False), ('check_out', '>=', str(start))]
        if not domain: raise AccessError(_('Open this source through its own application.'))
        records = obj.search(domain, limit=2)
        return {'type': 'ir.actions.act_window', 'name': OWNER_NAMES[model], 'res_model': model,
            'domain': domain, 'views': [(False, 'form')] if len(records) == 1 else [(False, 'list'), (False, 'form')],
            'res_id': records.id if len(records) == 1 else False, 'target': 'new',
            'context': {'allowed_company_ids': [self.company_id.id], 'create': False}}
