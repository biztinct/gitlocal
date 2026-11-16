"""Read-only Vietnam profile: saved payroll settings, not legacy defaults.

No tax is calculated or record synchronised by opening a profile. Contract
settings describe the current setup; an uploaded pay-run input may override
them. Dependent documents and the payroll's registered count stay separate.
"""
import math

from odoo import _, fields, models
from odoo.exceptions import AccessError


def valid_number(value, integer=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
        return None
    return int(number) if integer else number


class PbPeople(models.AbstractModel):
    _inherit = 'pb.people'

    def _e360_vn_scheme(self, emp, today):
        Config = self.env.get('hr.formula.config')
        if Config is None:
            return None
        # Resolve today's map rather than trusting a stale stored Paid by.
        if 'pb.scheme.map' in self.env:
            cycle = emp._pb_main_cycle(emp.company_id.id) if hasattr(emp, '_pb_main_cycle') else 'any'
            answer = self.env['pb.scheme.map'].resolve(emp, cycle, on_date=today)
            config = Config.browse(answer.get('config_id') or []).exists()
        else:
            config = emp.pb_paid_by_id if 'pb_paid_by_id' in emp._fields else Config.browse()
        if config and config.state == 'active' and config.country_code == 'VN' \
                and (not config.company_id or config.company_id == emp.company_id):
            config.check_access('read')
            return config
        return None

    def _e360_vn_settings(self, emp, today):
        """Only one current running contract; never a future/expired fallback."""
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', emp.id), ('company_id', '=', emp.company_id.id),
            ('active', '=', True), ('state', '=', 'open'), ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today)], limit=2)
        if len(contracts) != 1:
            return None, {}, (_('More than one current contract; review required.')
                              if contracts else _('No current running contract.'))
        contract = contracts[0]
        values, duplicates = {}, set()
        for line in contract.advantages_ids:
            code = line.advantage_template_code
            if code in values:
                duplicates.add(code)
            pending = ('pb_fill' in line._fields and line.pb_fill == 'auto'
                       and not line.pb_checked_at)
            values[code] = None if pending else (
                line.text_value if line.value_type == 'text' else line.amount)
        for code in duplicates:
            values[code] = None
        return contract, values, _('Saved current-contract settings. A pay run may supply different inputs.')

    def _e360_vietnam(self, emp, unmask):
        if 'payroll_country' not in emp._fields or emp.payroll_country != 'VN':
            return None
        today = fields.Date.context_today(self)
        missing = _('Not recorded — review required')
        masked = _('Visible to payroll managers only')
        rows, dep_rows = [], []

        def row(key, label, value):
            rows.append({'key': key, 'label': label, 'value': value, 'empty': False})

        def money(value):
            if value is None:
                return missing
            return _('%s VND / month', '{:,.0f}'.format(value)) if unmask else masked

        def employee_value(name):
            if name not in emp._fields or name not in emp.fields_get([name]):
                return None
            return emp[name] or None

        tax_number = employee_value('vietnam_tax_code')
        si_number = employee_value('vietnam_social_insurance_number')
        row('vietnam_tax_code', _('PIT number'), tax_number or missing)
        row('vietnam_social_insurance_number', _('SI number'), si_number or missing)
        config, contract, values, rates = None, None, {}, {}
        note = _('Payroll settings are not available to your account.')
        try:
            config = self._e360_vn_scheme(emp, today)
            contract, values, note = self._e360_vn_settings(emp, today)
            if config:
                for code in ('VNPERSONAL', 'VNDEPAMT'):
                    rules = config.rule_ids.filtered(lambda r: r.code == code and r.column_type == 'constant')
                    rates[code] = valid_number(rules.constant_value) if len(rules) == 1 else None
        except AccessError:
            config, contract, values, rates = None, None, {}, {}

        row('vn_payroll_scheme', _('Payroll scheme'), config.name if config else missing)
        row('vn_settings_date', _('Settings as of'), str(today))
        yes_no = {'Yes': _('Yes'), 'No': _('No')}
        for code, label in [('VNSIJOIN', _('Social insurance (SI)')),
                            ('VNHIJOIN', _('Health insurance (HI)')),
                            ('VNUIJOIN', _('Unemployment insurance (UI)'))]:
            row(code, label, yes_no.get(values.get(code), missing))
        mode = values.get('VNINSMODE')
        modes = {'Contract salary': _('Contract salary'),
                 'Salary + private insurance': _('Contract salary plus private insurance allowance'),
                 'Fixed base': _('Fixed contribution salary')}
        row('VNINSMODE', _('Insurance salary basis'), modes.get(mode, missing))
        # This is the saved salary basis, before statutory caps, not an SI
        # deduction or a claimed calculation for a particular payslip.
        base = None
        if contract and unmask:
            if mode == 'Contract salary':
                base = valid_number(contract.wage)
            elif mode == 'Salary + private insurance':
                private = valid_number(values.get('VNPRIVATE'))
                base = contract.wage + private if private is not None else None
            elif mode == 'Fixed base':
                base = valid_number(values.get('VNINSBASE'))
        row('vn_insurance_salary', _('Salary before insurance caps'), money(base) if unmask else masked)
        tax_mode = {'Workbook': _('Client payroll rules'), 'Resident': _('Resident calculation'),
                    'Manual': _('Reviewed manual PIT')}.get(values.get('VNTAXMODE'), missing)
        row('VNTAXMODE', _('PIT calculation method'), tax_mode)
        row('VNPTYPE', _('Saved payroll treatment'),
            {'Permanent': _('Permanent'), 'Probation': _('Probation')}.get(values.get('VNPTYPE'), missing))
        row('VNPERSONAL', _('Personal deduction — scheme rate'), money(rates.get('VNPERSONAL')))
        count = valid_number(values.get('VNREGISTER'), integer=True)
        row('VNREGISTER', _('Registered dependents — payroll count'), str(count) if count is not None else missing)
        rate = rates.get('VNDEPAMT')
        row('VNDEPAMT', _('Deduction per registered dependent'), money(rate))
        row('vn_dependent_total', _('Dependent deduction from saved payroll count'),
            money(count * rate if count is not None and rate is not None else None))

        # Never replace a registered payroll count with a headcount of family
        # records, and never turn missing verification dates into eligibility.
        pending = None
        if 'vietnam.employee.dependent' in self.env:
            try:
                dependents = self.env['vietnam.employee.dependent'].search([('employee_id', '=', emp.id)])
                pending = len(dependents.filtered(lambda d: d.status == 'pending' or (d.status == 'eligible' and not d.effective_from)))
                row('vn_saved_dependents', _('Dependent records saved'), str(len(dependents)))
                row('vn_pending_dependents', _('Dependent records needing verification'), str(pending))
                relationships = dict(dependents.fields_get(['relationship'])['relationship']['selection'])
                for dep in dependents:
                    if dep.status == 'pending' or (dep.status == 'eligible' and not dep.effective_from):
                        status = _('Pending verification')
                    elif dep.status == 'ineligible':
                        status = _('Not eligible')
                    elif dep.effective_from > today:
                        status = _('Starts in the future')
                    elif dep.effective_to and dep.effective_to < today:
                        status = _('Eligibility ended')
                    else:
                        status = _('Eligible for the recorded dates')
                    dates = _('%(start)s to %(end)s', start=str(dep.effective_from) if dep.effective_from else _('Start date missing'),
                              end=str(dep.effective_to) if dep.effective_to else _('No end date recorded'))
                    dep_rows.append({'key': 'dependent_%s' % dep.id, 'label': dep.name,
                                     'value': ' · '.join([relationships.get(dep.relationship, ''), status, dates]), 'empty': False})
            except AccessError:
                row('vn_saved_dependents', _('Dependent records'), _('Not available to your account'))
        row('vn_deduction_note', _('How relief is applied'),
            _('Scheme rates are shown above. Actual relief follows the payroll period and tax treatment.'))
        groups = [{'key': 'vn', 'title': _('Vietnam tax and insurance'), 'icon': 'shield',
                   'rows': rows, 'filled': len(rows), 'note': note}]
        if dep_rows:
            groups.append({'key': 'vn_dependents', 'title': _('Dependent records'), 'icon': 'users',
                           'rows': dep_rows, 'filled': len(dep_rows),
                           'note': _('These records do not automatically change the registered payroll count. Confirm registration and dates for pending records.')})
        return {'groups': groups, 'tax': bool(tax_number),
                'tax_label': _('PIT number on file') if tax_number else _('PIT number missing'),
                'insurance': values.get('VNSIJOIN') == 'Yes',
                'insurance_label': _('SI: %s', yes_no.get(values.get('VNSIJOIN'), _('Review required')))}
