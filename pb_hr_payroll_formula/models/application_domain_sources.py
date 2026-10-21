"""Read-only, typed sources owned by HR domains, not contract pay components.

The formula engine owns the source contract.  These optional adapters do not
install domain apps, create business records, infer approvals, or select an
arbitrary row from a one-to-many relation.  Missing is deliberately not zero.
"""

from datetime import date, datetime, timedelta
import json
import math

from odoo import fields, models
from odoo.exceptions import AccessError, MissingError


EMPLOYEE_FIELDS = (
    'barcode', 'birthday', 'country_id', 'date_of_joining', 'department_id',
    'emergency_contact', 'emergency_phone', 'employee_id', 'identification_id',
    'job_id', 'job_title', 'job_title_text', 'marital', 'name', 'passport_id',
    'payroll_country', 'permit_no', 'place_of_birth', 'private_email',
    'private_phone', 'private_street', 'study_field', 'study_school', 'sex',
    'certificate', 'employee_type', 'work_email', 'work_phone',
    'vietnam_emergency_contact_name', 'vietnam_emergency_contact_phone',
    'vietnam_emergency_contact_relationship', 'vietnam_passport_number',
    'vietnam_social_insurance_number', 'vietnam_tax_code',
    'vietnam_temporary_address', 'vietnam_work_permit_number',
    'vn_dependent_record_count', 'pb_legal_first_name', 'pb_legal_last_name',
    'pb_blood_type', 'pb_religion', 'pb_emergency_relationship',
    'pb_permanent_address', 'pb_position_reference', 'pb_job_level',
    'pb_visa_status', 'pb_npwp_number', 'pb_family_card_number',
    'pb_bpjs_employment_number', 'pb_bpjs_health_number',
)
# Payroll readers are a broader audience than restricted HR-profile readers.
# Even a manager's compute must not copy these facts into shared payslip JSON.
PAYROLL_EXCLUDED_FIELDS = {'pb_blood_type', 'pb_religion'}
CONTRACT_FIELDS = (
    'date_end', 'date_start', 'location', 'tax_identification_number',
    'trial_date_end', 'pb_trial_date_start', 'wage', 'currency_id', 'costcenter', 'contract_type_id',
    'pb_signed_date', 'pb_salary_basis',
    'pb_payroll_contract_type', 'pb_payroll_nationality_status',
)
RELATED_FIELDS = {
    'employee.manager_name': ('parent_id', 'name'),
    'employee.manager_email': ('parent_id', 'work_email'),
    'employee.work_location': ('work_location_id', 'name'),
    'employee.work_country': ('work_location_id', 'address_id', 'country_id'),
    'employee.work_city': ('work_location_id', 'address_id', 'city'),
}
DOMAIN_SOURCES = {
    'assets.physical_types': ('Assigned physical asset types', 'text', 'pb.asset.assignment'),
    'assets.physical_codes': ('Assigned physical asset codes', 'text', 'pb.asset.assignment'),
    'assets.physical_serials': ('Assigned physical asset serial numbers', 'text', 'pb.asset.assignment'),
    'assets.digital_names': ('Assigned software and digital access', 'text', 'pb.asset.assignment'),
    'exit.reason': ('Approved exit reason', 'text', 'pb.resignation'),
    'exit.submitted_on': ('Notice submitted on', 'date', 'pb.resignation'),
    'exit.notice_days': ('Approved notice days', 'days', 'pb.resignation'),
    'exit.contractual_lwd': ('Last working day under notice', 'date', 'pb.resignation'),
    'exit.approved_lwd': ('Approved last working day', 'date', 'pb.resignation'),
    'exit.unserved_notice_days': ('Unserved notice days', 'days', 'pb.resignation'),
    'exit.interview_status': ('Exit interview status', 'text', 'pb.resignation'),
    'exit.feedback_status': ('Exit questionnaire status', 'text', 'pb.feedback.request'),
    'exit.clearance_status': ('Exit clearance status', 'text', 'pb.exit.clearance'),
    'exit.settlement_status': ('Final settlement status', 'text', 'hr.full.final.settlement'),
    'probation.verdict': ('Approved probation outcome', 'text', 'pb.probation.review'),
    'documents.offer_verified': ('Signed offer verified', 'text', 'pb.employee.document'),
    'documents.agreement_verified': ('Employment agreement verified', 'text', 'pb.employee.document'),
    'awards.bonus': ('Approved unpaid bonus awards', 'money', 'pb.incentive'),
    'awards.incentive': ('Approved unpaid incentive awards', 'money', 'pb.incentive'),
    'awards.spot': ('Approved unpaid spot awards', 'money', 'pb.incentive'),
    'leave.annual.entitlement': ('Annual leave yearly policy entitlement', 'days', 'hr.leave.allocation'),
    'leave.sick.entitlement': ('Sick leave yearly policy entitlement', 'days', 'hr.leave.allocation'),
    'leave.annual.balance': ('Annual leave balance as of period end', 'days', 'hr.leave.allocation'),
    'leave.sick.balance': ('Sick leave balance as of period end', 'days', 'hr.leave.allocation'),
}


def source_result(value=None, status='missing', records=None, **evidence):
    """Keep the wire shape serializable and source IDs explicit."""
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    return {
        'value': value, 'status': status,
        'source_ids': [[r._name, r.id] for r in (records or [])],
        'evidence': evidence, 'reason': evidence.get('reason', ''),
    }


def scalar_value(record, field_name):
    """Typed display values matching the established native mapping resolver."""
    record = record.sudo(False)
    record.check_access('read')
    # Attribute reads alone are not a field-level permission check. The field
    # catalogue filters group-protected fields for the real payroll actor.
    if field_name not in record.fields_get([field_name]):
        raise AccessError('This source field is restricted.')
    field = record._fields[field_name]
    value = record[field_name]
    if field.type in ('integer', 'float', 'monetary'):
        return float(value)
    if field.type == 'boolean':
        return bool(value)
    if not value:
        return None
    if field.type == 'many2one':
        value.sudo(False).check_access('read')
        return value.display_name
    if field.type == 'selection':
        return dict(field._description_selection(record.env)).get(value, value)
    if field.type in ('date', 'datetime'):
        return value.isoformat()
    if field.type in ('char', 'text'):
        return value
    return None


class HrFormulaConfigApplicationDomains(models.Model):
    _inherit = 'hr.formula.config'

    def _application_mapping_descriptors(self):
        """Mapping definitions, not employee-data coverage or run readiness."""
        self.ensure_one()
        catalogue = self._application_source_catalogue()
        result = {}
        record_prefixes = ('employee.', 'contract.', 'bank.', 'assets.', 'exit.',
                           'probation.', 'documents.', 'pending.domain.')
        for rule in self.rule_ids.filtered(lambda r: r.column_type == 'input' and r.application_source_key):
            key = rule.application_source_key
            spec = catalogue.get(key, {})
            pending = not spec or spec.get('requires_domain_review', False)
            result[rule.id] = {
                'key': key, 'label': spec.get('label') or key,
                'model': spec.get('model') or rule.application_source_owner_model or '',
                'record': key.startswith(record_prefixes),
                'pending': pending,
                'available': not pending and spec.get('available', True),
                'payroll_excluded': spec.get('persist_in_payroll') is False,
                'note': rule.application_source_note or '',
            }
        return result

    def _application_source_catalogue(self):
        parent = getattr(super(), '_application_source_catalogue', None)
        result = dict(parent() if parent else {})
        for prefix, model_name, names in (
                ('employee', 'hr.employee', EMPLOYEE_FIELDS),
                ('contract', 'hr.contract', CONTRACT_FIELDS)):
            model = self.env[model_name]
            for name in names:
                field = model._fields.get(name)
                if field:
                    result[prefix + '.' + name] = {
                        'label': field.string or name, 'unit': field.type,
                        'model': model_name, 'field': name,
                        'effective_date': 'current_record_snapshot',
                        'writable': False,
                        'persist_in_payroll': name not in PAYROLL_EXCLUDED_FIELDS,
                    }
        for key, path in RELATED_FIELDS.items():
            result[key] = {'label': key.split('.', 1)[1].replace('_', ' ').title(),
                           'unit': 'text', 'model': 'hr.employee',
                           'path': '.'.join(path), 'writable': False}
        for role in ('acc_number', 'acc_holder_name', 'bank_name', 'bank_bic'):
            result['bank.' + role] = {
                'label': role.replace('_', ' ').title(), 'unit': 'text',
                'model': 'res.partner.bank', 'writable': False,
            }
        for key, (label, unit, model_name) in DOMAIN_SOURCES.items():
            result[key] = {'label': label, 'unit': unit, 'model': model_name,
                           'available': model_name in self.env, 'writable': False,
                           'cardinality': 'many' if key.startswith('assets.') else 'one'}
        # Explicit component selection makes history unambiguous; it does not
        # infer which total the local tax authority considers taxable.
        for config in self:
            for rule in config.rule_ids.filtered(lambda r: (r.application_source_key or '').startswith('pending.domain.')):
                result[rule.application_source_key] = {
                    'label': 'Domain review required: ' + rule.name, 'unit': rule.value_kind,
                    'model': rule.application_source_owner_model or 'unconfirmed domain model',
                    'canonical_owner': rule.application_source_owner,
                    'review_reason': rule.application_source_note,
                    'available': False, 'writable': False, 'requires_domain_review': True,
                    'certification_zero_allowed': False,
                }
            for rule in config.rule_ids.filtered(lambda r: r.value_kind in ('money', 'quantity')):
                result['history.ytd.' + rule.code] = {
                    'label': 'Posted year-to-date: ' + rule.name,
                    'unit': rule.value_kind, 'model': 'hr.payslip',
                    'component_code': rule.code, 'writable': False,
                    'requires_complete_history': True,
                }
        return result

    def _application_domain_values(self, employee, contract, date_from, date_to):
        return self._application_record_context_values(employee, contract, date_from, date_to)

    def _application_record_context_values(self, employee, contract, date_from, date_to, source_keys=None):
        self.ensure_one()
        parent = getattr(super(), '_application_domain_values', None)
        result = dict(parent(employee, contract, date_from, date_to) if parent else {})
        self = self.sudo(False)
        employee, contract = employee.sudo(False), contract.sudo(False)
        if not employee or employee.company_id != self.company_id:
            return result
        wanted = {r.application_source_key for r in self.rule_ids
                  if r.column_type == 'input' and r.application_source_key}
        if source_keys is not None:
            wanted.intersection_update(source_keys)
        start, end = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        if not start or not end or start > end:
            return result
        # Reading the record and its individual fields retains normal ACLs,
        # record rules and restricted-field permissions.  No sudo fallback.
        for key in sorted(wanted):
            if key.startswith('pending.domain.'):
                rules = self.rule_ids.filtered(lambda r: r.application_source_key == key)
                result[key] = source_result(reason='canonical_domain_source_requires_review',
                    canonical_owner=rules[:1].application_source_owner,
                    canonical_model=rules[:1].application_source_owner_model,
                    review_note=rules[:1].application_source_note)
                continue
            if not (key in DOMAIN_SOURCES or key in RELATED_FIELDS
                    or key.startswith(('employee.', 'contract.', 'bank.', 'history.ytd.'))):
                continue
            try:
                result[key] = self._application_domain_value(
                    key, employee, contract, start, end)
            except (AccessError, MissingError):
                result[key] = source_result(reason='source_not_accessible', key=key)
        return result

    def _application_domain_value(self, key, employee, contract, start, end):
        if key in RELATED_FIELDS:
            record = employee
            path = RELATED_FIELDS[key]
            for name in path[:-1]:
                if not record or name not in record._fields:
                    return source_result(reason='related_record_missing', path='.'.join(path))
                record.check_access('read')
                if name not in record.fields_get([name]):
                    raise AccessError('This related source field is restricted.')
                record = record[name]
            if not record or path[-1] not in record._fields:
                return source_result(reason='related_field_missing', path='.'.join(path))
            value = scalar_value(record, path[-1])
            return source_result(value, 'resolved' if value is not None else 'missing',
                                 record, as_of=str(end), path='.'.join(path))
        if key.startswith(('employee.', 'contract.')):
            prefix, name = key.split('.', 1)
            allowed = EMPLOYEE_FIELDS if prefix == 'employee' else CONTRACT_FIELDS
            record = employee if prefix == 'employee' else contract
            if prefix == 'employee' and name in PAYROLL_EXCLUDED_FIELDS:
                return source_result(reason='restricted_profile_excluded_from_payroll_snapshot',
                    canonical_model='hr.employee', field=name, persist_in_payroll=False)
            if name not in allowed or not record or name not in record._fields:
                return source_result(reason='field_not_available')
            if prefix == 'contract' and (record.employee_id != employee
                                       or record.company_id != self.company_id):
                return source_result(status='conflict', reason='contract_scope_mismatch')
            value = scalar_value(record, name)
            return source_result(value, 'resolved' if value is not None else 'missing', record,
                                 field=name, as_of=str(end), snapshot='current_master_record')
        if key.startswith('bank.'):
            return self._application_bank_value(key, employee, end)
        if key.startswith('assets.'):
            return self._application_asset_value(key, employee, end)
        if key.startswith('exit.'):
            return self._application_exit_value(key, employee, contract, start, end)
        if key == 'probation.verdict':
            model = 'pb.probation.review'
            if model not in self.env:
                return source_result(reason='optional_model_not_installed', model=model)
            rows = self.env[model].search([
                ('employee_id', '=', employee.id), ('company_id', '=', self.company_id.id),
                ('kind', '=', 'probation'), ('verdict_at', '!=', False),
                ('verdict_at', '<', str(end + timedelta(days=1))),
            ], order='verdict_at desc, id desc', limit=2)
            if not rows:
                return source_result(reason='approved_probation_outcome_missing')
            if len(rows) > 1 and rows[0].verdict_at == rows[1].verdict_at:
                return source_result(status='conflict', records=rows,
                                     reason='multiple_outcomes_at_same_effective_time')
            return source_result(scalar_value(rows[0], 'verdict'), 'resolved', rows[:1], as_of=str(end))
        if key.startswith('documents.'):
            return self._application_document_value(key, employee, end)
        if key.startswith('awards.'):
            return self._application_award_value(key, employee, start, end)
        if key.startswith('history.ytd.'):
            return self._application_history_value(key, employee, contract, start)
        if key.startswith('leave.'):
            if not hasattr(employee, '_pb_policy_payroll_metrics'):
                return source_result(reason='policy_balance_provider_not_installed')
            metric = key[len('leave.'):].replace('.', '_')
            metrics = employee._pb_policy_payroll_metrics(end)
            value = metrics.get(metric)
            records = self.env['hr.leave.allocation'].browse(metrics.get('allocation_ids') or [])
            return source_result(value, 'resolved' if value is not None else 'missing', records,
                                 policy_id=metrics.get('policy_id'), as_of=str(end),
                                 reason=(metrics.get('errors') or {}).get(metric, ''))
        return source_result(reason='unsupported_source', key=key)

    def _application_bank_value(self, key, employee, end):
        # A one-to-many list's first row is not a payment instruction.
        field_name = 'bank_account_ids' if 'bank_account_ids' in employee._fields else 'bank_account_id'
        employee.check_access('read')
        if field_name not in employee.fields_get([field_name]):
            raise AccessError('Payment account source is restricted.')
        accounts = employee[field_name]
        accounts.check_access('read')
        if 'company_id' in accounts._fields:
            accounts = accounts.filtered(lambda a: not a.company_id or a.company_id == self.company_id)
        if len(accounts) != 1:
            return source_result(status='conflict' if accounts else 'missing', records=accounts,
                                 reason='explicit_single_payment_account_required')
        account = accounts[0]
        role = key.split('.', 1)[1]
        if role in ('acc_number', 'acc_holder_name'):
            value = scalar_value(account, role)
        elif role in ('bank_name', 'bank_bic') and account.bank_id:
            value = scalar_value(account.bank_id, 'name' if role == 'bank_name' else 'bic')
        else:
            value = None
        return source_result(value or None, 'resolved' if value else 'missing', accounts,
                             as_of=str(end), role=role, snapshot='current_payment_account')

    def _application_asset_value(self, key, employee, end):
        model = 'pb.asset.assignment'
        if model not in self.env:
            return source_result(reason='optional_model_not_installed', model=model)
        kind = 'digital' if key == 'assets.digital_names' else 'tangible'
        rows = self.env[model].search([
            ('employee_id', '=', employee.id), ('company_id', '=', self.company_id.id),
            ('assigned_date', '<=', end), ('kind', '=', kind),
            '|', ('returned_date', '=', False), ('returned_date', '>', end),
        ], order='asset_id, id')
        if not rows:
            return source_result(reason='no_dated_assignment', as_of=str(end))
        if len(rows.asset_id) != len(rows):
            return source_result(status='conflict', records=rows,
                                 reason='overlapping_assignments_for_same_asset')
        values = []
        for row in rows:
            asset = row.asset_id
            if key == 'assets.physical_types':
                value = asset.category_id.name
            elif key == 'assets.physical_codes':
                value = asset.code
            elif key == 'assets.physical_serials':
                value = asset.serial
            else:
                value = asset.name
            if not value:
                return source_result(records=rows, reason='assigned_asset_field_missing', key=key)
            # Preserve one value per assignment, including repeated categories.
            values.append(str(value))
        return source_result('; '.join(values), 'resolved', rows, as_of=str(end),
                             aggregation='all_assignments_in_asset_id_order', values=values)

    def _application_exit_value(self, key, employee, contract, start, end):
        model = 'pb.resignation'
        if model not in self.env:
            return source_result(reason='optional_model_not_installed', model=model)
        domain = [('employee_id', '=', employee.id), ('company_id', '=', self.company_id.id),
                  ('state', '=', 'approved'), ('submit_date', '<=', end)]
        if contract and contract.date_start:
            domain.append(('approved_lwd', '>=', contract.date_start))
        rows = self.env[model].search(domain, order='approved_lwd desc, id desc', limit=2)
        if len(rows) != 1:
            return source_result(status='conflict' if rows else 'missing', records=rows,
                                 reason='unique_approved_exit_required')
        row = rows[0]
        simple = {'exit.reason': 'reason_text', 'exit.submitted_on': 'submit_date',
                  'exit.notice_days': 'notice_days', 'exit.approved_lwd': 'approved_lwd',
                  'exit.contractual_lwd': 'pb_contractual_lwd',
                  'exit.unserved_notice_days': 'pb_unserved_notice_days',
                  'exit.interview_status': 'pb_interview_status'}
        if key in simple:
            name = simple[key]
            if name not in row._fields:
                return source_result(records=rows, reason='domain_field_not_installed', field=name)
            if name == 'pb_unserved_notice_days' and not row.pb_contractual_lwd:
                return source_result(records=rows, reason='contractual_last_day_not_reviewed')
            value = scalar_value(row, name)
            return source_result(value, 'resolved' if value is not None else 'missing', rows, as_of=str(end))
        case = row.case_id
        if not case:
            return source_result(records=rows, reason='exit_case_missing')
        if key == 'exit.feedback_status':
            model = 'pb.feedback.request'
            if model not in self.env:
                return source_result(reason='optional_model_not_installed', model=model)
            feedback = self.env[model].search([('case_id', '=', case.id), ('kind', '=', 'exit')], limit=2)
            if len(feedback) != 1:
                return source_result(status='conflict' if feedback else 'missing', records=feedback,
                                     reason='unique_exit_questionnaire_required')
            return source_result(scalar_value(feedback, 'state'), 'resolved', feedback,
                                 semantics='questionnaire_not_interview', snapshot='current_case')
        if key == 'exit.clearance_status':
            model = 'pb.exit.clearance'
            if model not in self.env:
                return source_result(reason='optional_model_not_installed', model=model)
            clearance = self.env[model].search([('case_id', '=', case.id),
                                                ('company_id', '=', self.company_id.id)])
            desks = set(clearance.mapped('dept'))
            if not {'it', 'hr', 'finance', 'admin'}.issubset(desks):
                return source_result(records=clearance, reason='required_clearance_desks_missing')
            complete = all(c.state in ('cleared', 'na') for c in clearance)
            return source_result('Cleared' if complete else 'Pending', 'resolved', clearance,
                                 snapshot='current_case', semantics='clearance_not_form_submission')
        if key == 'exit.settlement_status':
            model = 'hr.full.final.settlement'
            if model not in self.env or 'pb_case_id' not in self.env[model]._fields:
                return source_result(reason='optional_model_not_installed', model=model)
            settlements = self.env[model].search([
                ('pb_case_id', '=', case.id), ('employee_id', '=', employee.id),
                ('company_id', '=', self.company_id.id), ('settlement_date', '<=', end),
            ], limit=2)
            if len(settlements) != 1:
                return source_result(status='conflict' if settlements else 'missing', records=settlements,
                                     reason='unique_final_settlement_required')
            return source_result(scalar_value(settlements, 'state'), 'resolved', settlements,
                                 closed=settlements.pb_closed, semantics='settlement_status_not_bank_payment')
        return source_result(reason='unsupported_exit_source')

    def _application_document_value(self, key, employee, end):
        model = 'pb.employee.document'
        if model not in self.env:
            return source_result(reason='optional_model_not_installed', model=model)
        category = 'OFFER' if key == 'documents.offer_verified' else 'LABOR'
        rows = self.env[model].search([
            ('employee_id', '=', employee.id), ('company_id', '=', self.company_id.id),
            ('category_id.code', '=', category), ('verified', '=', True),
            ('verified_at', '<', str(end + timedelta(days=1))),
            '|', ('issue_date', '=', False), ('issue_date', '<=', end),
            '|', ('expiry_date', '=', False), ('expiry_date', '>=', end),
        ])
        if not rows:
            return source_result(reason='verified_document_missing', category=category)
        return source_result('Verified', 'resolved', rows, category=category, as_of=str(end))

    def _application_award_value(self, key, employee, start, end):
        model = 'pb.incentive'
        if model not in self.env:
            return source_result(reason='optional_model_not_installed', model=model)
        # An award specifies a MONTH, not a day. A partial payroll window needs
        # an explicit allocation decision and must not pay the same award twice.
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        if start.day != 1 or end != next_month - timedelta(days=1):
            return source_result(reason='awards_require_full_calendar_month')
        kind = key.split('.', 1)[1]
        if kind not in ('bonus', 'incentive', 'spot'):
            return source_result(reason='unsupported_award_kind')
        records = self.env[model].search([
            ('employee_id', '=', employee.id), ('company_id', '=', self.company_id.id),
            ('period_month', '>=', start), ('period_month', '<=', end),
            ('kind', '=', kind), ('state', '=', 'approved'),
        ])
        if not records:
            return source_result(reason='no_approved_awards_or_period_certification')
        if any(r.fulfilment in ('queued', 'paid') or r.run_id or r.feed_batch_ref for r in records):
            return source_result(status='conflict', records=records,
                                 reason='award_already_exported_or_paid_use_existing_pay_run')
        if any(r.currency_id != self.currency_id for r in records):
            return source_result(status='conflict', records=records, reason='award_currency_mismatch')
        amounts = records.mapped('amount')
        if any(not math.isfinite(a) or a < 0 for a in amounts):
            return source_result(status='conflict', records=records, reason='invalid_approved_award_amount')
        # Settlement remains the award's existing pay-run workflow. Evidence
        # identifies every award so the engine can lock and consume it once.
        return source_result(sum(amounts), 'resolved', records,
                             period_from=str(start), period_to=str(end),
                             consumption_required=True, currency=self.currency_id.name)

    def _application_history_value(self, key, employee, contract, start):
        code = key[len('history.ytd.'):]
        if code not in set(self.rule_ids.mapped('code')):
            return source_result(reason='history_component_not_in_scheme')
        year_start = start.replace(month=1, day=1)
        joined = employee.date_of_joining or (contract.date_start if contract else False)
        if not joined:
            return source_result(reason='employment_start_required_for_history_coverage')
        lower = max(year_start, joined)
        if lower >= start:
            return source_result(0.0, 'zero_confirmed', reason='no_prior_service_days_this_year')
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id), ('company_id', '=', self.company_id.id),
            ('formula_config_id', '=', self.id), ('state', '=', 'done'),
            ('date_from', '<', start), ('date_to', '>=', lower),
        ], order='date_from, date_to, id')
        if not slips:
            return source_result(reason='posted_history_or_opening_balances_missing')
        cursor, total = lower, 0.0
        for slip in slips:
            if slip.date_to >= start or slip.date_from < lower:
                return source_result(status='conflict', records=slips,
                                     reason='posted_period_straddles_history_boundary')
            if slip.date_from != cursor:
                return source_result(status='conflict' if slip.date_from < cursor else 'missing',
                                     records=slips, reason='history_overlap_or_gap',
                                     expected_from=str(cursor), actual_from=str(slip.date_from))
            try:
                payload = json.loads(slip.formula_computed_values or '{}')
                value = payload[code]
            except (ValueError, KeyError, TypeError):
                return source_result(records=slips, reason='posted_component_not_available', component=code)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return source_result(status='conflict', records=slips,
                                     reason='posted_component_not_numeric', component=code)
            total += value
            cursor = slip.date_to + timedelta(days=1)
        if cursor != start:
            return source_result(records=slips, reason='posted_history_incomplete',
                                 covered_until=str(cursor - timedelta(days=1)))
        return source_result(total, 'resolved', slips, component=code,
                             period_from=str(lower), period_to=str(start - timedelta(days=1)),
                             coverage='complete_contiguous_posted_periods')


class HrFormulaRuleApplicationOwner(models.Model):
    _inherit = 'hr.formula.rule'

    application_source_owner = fields.Char(string='Canonical business owner',
        help='Owning record and meaning, including fields awaiting domain review. It never authorizes data import or an approval.')
    application_source_owner_model = fields.Char(string='Canonical owner model',
        help='Informational model identifier for source review; it does not grant access or dynamically read arbitrary records.')
