"""Reviewed in-application period inputs, with paid-once reservations.

These records are an explicit period input, not a replacement for compensation,
expense or leave records. An empty ledger has no implied value. Every approval
is immutable; a correction supersedes the old row before it is reserved.
"""

from decimal import Decimal, InvalidOperation
import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_TOKEN = object()
_TOKEN_KEY = 'pb_period_input_internal_token'
_NUMERIC = {'money', 'quantity', 'rate', 'integer'}
_SEALED = {'state', 'approved_by', 'approved_at', 'reserved_run_id',
           'reserved_payslip_id', 'consumed_payslip_id', 'consumed_at',
           'policy_assessment_json', 'policy_assessment_hash', 'approved_currency_id'}


def decimal_value(value):
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(_('Enter a decimal number without commas or currency symbols.'))
    if not result.is_finite() or abs(result) > Decimal('1e20'):
        raise ValidationError(_('The period input must be a finite number within the supported range.'))
    return result


class PayrollPeriodInput(models.Model):
    _name = 'hr.payroll.period.input'
    _description = 'Approved Payroll Period Input'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                  default=lambda self: self.env.company)
    config_id = fields.Many2one('hr.formula.config', required=True, index=True, ondelete='restrict')
    employee_id = fields.Many2one('hr.employee', required=True, index=True, ondelete='restrict')
    component_id = fields.Many2one('hr.formula.rule', required=True, index=True, ondelete='restrict',
                                    domain="[('config_id', '=', config_id), ('column_type', '=', 'input')]")
    date_from = fields.Date(required=True, index=True)
    date_to = fields.Date(required=True, index=True)
    value_kind = fields.Selection(related='component_id.value_kind', readonly=True)
    value_decimal = fields.Char(string='Decimal value',
                                 help='An exact decimal. Zero must be deliberately entered and approved.')
    value_text = fields.Char(string='Text value', help='For a reviewed textual payroll control only.')
    unit = fields.Selection([('money', 'Scheme currency'), ('days', 'Days'),
                              ('hours', 'Hours'), ('number', 'Number'), ('text', 'Text')], required=True)
    reason = fields.Text(required=True, tracking=True)
    evidence_reference = fields.Char(required=True, string='Evidence or approval reference', tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'),
                               ('superseded', 'Superseded')], default='draft', required=True, index=True,
                              readonly=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    approved_currency_id = fields.Many2one('res.currency', readonly=True, copy=False,
        string='Approved currency', help='Currency sealed when a monetary input was approved.')
    reserved_run_id = fields.Many2one('hr.payslip.run', readonly=True, copy=False, ondelete='restrict')
    reserved_payslip_id = fields.Many2one('hr.payslip', readonly=True, copy=False, ondelete='restrict')
    consumed_payslip_id = fields.Many2one('hr.payslip', readonly=True, copy=False, ondelete='restrict')
    consumed_at = fields.Datetime(readonly=True, copy=False)
    settlement_kind = fields.Selection([
        ('none', 'Ordinary period input'), ('cashout_days', 'Policy leave cash-out days'),
        ('cashout_amount', 'Policy leave cash-out amount'), ('recovery_amount', 'Policy excess-leave recovery'),
    ], default='none', required=True)
    settlement_basis = fields.Selection([
        ('policy', 'Calculate from exit policy'),
        ('historical', 'Already-approved historical amount'),
    ], default='policy', required=True,
        help='Historical cash-out amounts require an explicit approval reference and a completed payroll period. They do not calculate or change leave balances.')
    exit_reference = fields.Reference(selection=[('pb.resignation', 'Approved resignation')],
                                        string='Approved exit')
    leave_type_reference = fields.Reference(selection=[('hr.leave.type', 'Annual leave type')],
                                             string='Annual leave type')
    settlement_gross_salary = fields.Char(string='Verified gross monthly salary')
    settlement_employment_start = fields.Date(string='Verified service start')
    settlement_review_months = fields.Boolean(string='Use reviewed service-month quantity')
    settlement_months = fields.Float(string='Reviewed service months')
    settlement_tax_review_reference = fields.Char(string='Country tax treatment review',
        help='Evidence of approved scheme-level tax treatment. Required for Singapore cash-out and all excess-leave recoveries; it does not create a net-pay formula or change tax classification.')
    policy_assessment_json = fields.Text(readonly=True, copy=False)
    policy_assessment_hash = fields.Char(readonly=True, copy=False)

    @api.onchange('component_id')
    def _onchange_component(self):
        for row in self:
            row.unit = ('money' if row.value_kind == 'money' else
                        'number' if row.value_kind in _NUMERIC else 'text')
            row.settlement_kind = row.component_id.application_settlement_kind or 'none'
            if row.settlement_kind == 'cashout_days':
                row.unit = 'days'

    @api.depends('employee_id', 'component_id', 'date_from', 'date_to')
    def _compute_name(self):
        for row in self:
            row.name = '%s · %s · %s' % (row.employee_id.name or '', row.component_id.name or '', row.date_from or '')

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS payroll_period_input_one_approved
            ON hr_payroll_period_input (company_id, config_id, employee_id, component_id, date_from, date_to)
            WHERE state = 'approved'
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS payroll_period_input_one_exit_settlement
            ON hr_payroll_period_input (exit_reference, leave_type_reference,
                (CASE WHEN settlement_kind = 'recovery_amount' THEN 'recovery' ELSE 'cashout' END))
            WHERE state = 'approved' AND settlement_kind != 'none'
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS payroll_period_input_one_historical_reference
            ON hr_payroll_period_input (company_id, employee_id, lower(btrim(evidence_reference)))
            WHERE state = 'approved' AND settlement_basis = 'historical'
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS payroll_period_input_one_historical_period
            ON hr_payroll_period_input (company_id, employee_id, date_from, date_to)
            WHERE state = 'approved' AND settlement_basis = 'historical'
        """)

    def _manager(self):
        if not (self.env.su or self.env.user.has_group('pb_hr_payroll_formula.group_formula_manager')):
            raise AccessError(_('A payroll manager must approve or supersede period inputs.'))
        self.check_access('write')

    @api.constrains('company_id', 'config_id', 'employee_id', 'component_id', 'date_from', 'date_to',
                    'value_decimal', 'value_text', 'unit', 'reason', 'evidence_reference')
    def _check_input(self):
        for row in self:
            if (row.config_id.company_id != row.company_id or row.employee_id.company_id != row.company_id
                    or row.component_id.config_id != row.config_id or row.component_id.column_type != 'input'):
                raise ValidationError(_('Employee, component and scheme must belong to the same company and scheme.'))
            if row.date_from > row.date_to or (row.date_to - row.date_from).days > 366:
                raise ValidationError(_('Choose a valid period of at most one year.'))
            if not (row.reason or '').strip() or not (row.evidence_reference or '').strip():
                raise ValidationError(_('Record the reason and evidence reference.'))
            if row.value_kind in _NUMERIC:
                value = decimal_value(row.value_decimal)
                if row.unit == 'text' or row.value_text:
                    raise ValidationError(_('Numeric components require a decimal value and a numeric unit.'))
                if row.value_kind == 'money' and row.unit != 'money':
                    raise ValidationError(_('Money inputs use the scheme currency.'))
                if row.value_kind == 'integer' and value != value.to_integral_value():
                    raise ValidationError(_('This component requires a whole number.'))
            elif not (row.value_text or '').strip() or row.unit != 'text' or row.value_decimal:
                raise ValidationError(_('This component requires text and the Text unit.'))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if any(k in values for k in _SEALED - {'state'}) or values.get('state', 'draft') != 'draft':
                raise AccessError(_('Create a draft period input and approve it through its action.'))
        return super().create(vals_list)

    def write(self, vals):
        internal = self.env.context.get(_TOKEN_KEY) is _TOKEN
        if not internal:
            if _SEALED.intersection(vals):
                raise AccessError(_('Approval and payment links are controlled by their workflow.'))
            content = set(vals) - {'message_follower_ids', 'message_partner_ids', 'message_main_attachment_id'}
            if content and any(r.state != 'draft' for r in self):
                raise UserError(_('Approved inputs are immutable. Supersede an unused input and create its correction.'))
        return super().write(vals)

    def unlink(self):
        if any(r.state != 'draft' or r.reserved_payslip_id or r.consumed_payslip_id for r in self):
            raise UserError(_('Approved or reserved payroll evidence cannot be deleted.'))
        return super().unlink()

    def _lock(self):
        if self:
            self.env.cr.execute('SELECT id FROM hr_payroll_period_input WHERE id IN %s ORDER BY id FOR UPDATE',
                                [tuple(self.ids)])
            self.invalidate_recordset()

    def _assessment(self):
        self.ensure_one()
        if (self.state == 'approved' and self.unit == 'money'
                and self.approved_currency_id != self.config_id.currency_id):
            raise ValidationError(_('The scheme currency differs from the approved input currency. Review a replacement input.'))
        expected_kind = self.component_id.application_settlement_kind or 'none'
        if expected_kind != self.settlement_kind:
            raise ValidationError(_('Use the settlement treatment configured for this component.'))
        if self.settlement_basis == 'historical':
            if self.settlement_kind != 'cashout_amount' or self.unit != 'money' or self.value_kind != 'money':
                raise ValidationError(_('Historical settlement entry is only available for a monetary leave cash-out.'))
            if self.date_to >= fields.Date.context_today(self):
                raise ValidationError(_('Historical amounts require a completed payroll period.'))
            if self.exit_reference or self.leave_type_reference:
                raise ValidationError(_('Use policy calculation when linking an exit or leave type. Historical amounts retain their external approval reference.'))
            if decimal_value(self.value_decimal) <= 0:
                raise ValidationError(_('Enter the positive historical cash-out amount that was approved.'))
            result = {
                'basis': 'historical', 'cashout_amount': str(decimal_value(self.value_decimal)),
                'company_id': self.company_id.id, 'employee_id': self.employee_id.id,
                'config_id': self.config_id.id, 'component_id': self.component_id.id,
                'date_from': str(self.date_from), 'date_to': str(self.date_to),
                'currency_id': self.config_id.currency_id.id,
                'approval_reference': self.evidence_reference, 'reason': self.reason,
            }
            payload = json.dumps(result, sort_keys=True, default=str)
            if self.state == 'approved' and (not self.policy_assessment_hash or
                    hashlib.sha256(payload.encode()).hexdigest() != self.policy_assessment_hash):
                raise ValidationError(_('The approved historical evidence has changed. Review a replacement input.'))
            return result
        if self.settlement_kind == 'none':
            return None
        if (self.settlement_kind == 'recovery_amount' or self.config_id.country_code == 'SG') and not (self.settlement_tax_review_reference or '').strip():
            raise ValidationError(_('Country payroll tax treatment is awaiting review. Record the approved treatment reference before this settlement can be approved.'))
        exit_case, leave_type = self.exit_reference, self.leave_type_reference
        if not exit_case or exit_case._name != 'pb.resignation' or exit_case.state != 'approved':
            raise ValidationError(_('Leave settlement requires an approved exit record.'))
        if exit_case.employee_id != self.employee_id or exit_case.company_id != self.company_id:
            raise ValidationError(_('The approved exit must belong to this employee and company.'))
        if not exit_case.approved_lwd or not self.date_from <= exit_case.approved_lwd <= self.date_to:
            raise ValidationError(_('The agreed last working day must fall inside this settlement period.'))
        if not leave_type or leave_type._name != 'hr.leave.type':
            raise ValidationError(_('Select the policy annual leave type.'))
        policy = (self.employee_id._pb_policy_for_date(exit_case.approved_lwd)
                  if hasattr(self.employee_id, '_pb_policy_for_date') else False)
        if not policy or not hasattr(policy, 'assess_exit'):
            raise ValidationError(_('Assign a published leave policy before approving leave settlement.'))
        if not self.settlement_employment_start:
            raise ValidationError(_('Verify the service start date for the exit calculation.'))
        posting = policy._settlement_posting(self) if hasattr(policy, '_settlement_posting') else False
        if posting:
            result = json.loads(posting.assessment_json)
        else:
            result = policy.assess_exit(self.employee_id.id, leave_type.id, exit_case.approved_lwd,
                self.settlement_employment_start, float(decimal_value(self.settlement_gross_salary)),
                self.settlement_months if self.settlement_review_months else None, self.evidence_reference)
        payload = json.dumps(result, sort_keys=True, default=str)
        if self.state == 'approved' and (not self.policy_assessment_hash or
                hashlib.sha256(payload.encode()).hexdigest() != self.policy_assessment_hash):
            raise ValidationError(_('The approved leave assessment has changed. Review and approve a replacement before payroll.'))
        expected = decimal_value(result[self.settlement_kind])
        actual = decimal_value(self.value_decimal)
        precision = Decimal('0.000001') if self.settlement_kind == 'cashout_days' else Decimal(str(self.config_id.currency_id.rounding or .01))
        if abs(expected - actual) > precision / 2:
            raise ValidationError(_('The input differs from the policy exit calculation. Reassess it before approval.'))
        if self.settlement_kind == 'cashout_days' and self.unit != 'days':
            raise ValidationError(_('Leave cash-out quantities use days.'))
        if self.settlement_kind != 'cashout_days' and self.unit != 'money':
            raise ValidationError(_('Leave settlement amounts use the scheme currency.'))
        return result

    def action_approve(self):
        self._manager()
        self._lock()
        for row in self:
            if row.state == 'approved':
                continue
            if row.state != 'draft':
                raise UserError(_('Only a draft period input can be approved.'))
            row._check_input()
            existing = self.search([
                ('company_id', '=', row.company_id.id), ('config_id', '=', row.config_id.id),
                ('employee_id', '=', row.employee_id.id), ('component_id', '=', row.component_id.id),
                ('date_from', '=', row.date_from), ('date_to', '=', row.date_to), ('state', '=', 'approved'),
            ])
            if existing:
                raise UserError(_('An approved value already exists. Supersede it explicitly before approving a correction.'))
            assessment = row._assessment()
            if row.settlement_kind != 'none':
                # Serialize cross-scheme approvals for the same employee. A
                # historical receipt cannot silently duplicate a policy payout.
                self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                    ['payroll-settlement:%s:%s' % (row.company_id.id, row.employee_id.id)])
                kinds = ['recovery_amount'] if row.settlement_kind == 'recovery_amount' else ['cashout_days', 'cashout_amount']
                overlap = self.search([
                    ('state', '=', 'approved'), ('company_id', '=', row.company_id.id),
                    ('employee_id', '=', row.employee_id.id), ('settlement_kind', 'in', kinds),
                    ('date_from', '<=', row.date_to), ('date_to', '>=', row.date_from),
                ])
                if overlap and (row.settlement_basis == 'historical' or
                                any(r.settlement_basis == 'historical' for r in overlap)):
                    raise UserError(_('An approved historical or policy cash-out already covers this employee and period.'))
            if row.settlement_basis == 'historical':
                self.env.cr.execute("""SELECT id FROM hr_payroll_period_input
                    WHERE state='approved' AND settlement_basis='historical'
                      AND company_id=%s AND employee_id=%s
                      AND lower(btrim(evidence_reference))=lower(btrim(%s))""",
                    [row.company_id.id, row.employee_id.id, row.evidence_reference])
                if self.env.cr.fetchone():
                    raise UserError(_('This historical approval reference has already been used for this employee.'))
            elif row.settlement_kind != 'none':
                previous = self.search([('state', '=', 'approved'),
                    ('exit_reference', '=', '%s,%s' % (row.exit_reference._name, row.exit_reference.id)),
                    ('leave_type_reference', '=', '%s,%s' % (row.leave_type_reference._name, row.leave_type_reference.id)),
                    ('settlement_kind', 'in', kinds)], limit=1)
                if previous:
                    raise UserError(_('This exit and leave type already have an approved settlement, including other schemes and periods.'))
            payload = json.dumps(assessment, sort_keys=True, default=str) if assessment else False
            row.with_context(**{_TOKEN_KEY: _TOKEN}).write({
                'state': 'approved', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now(),
                'approved_currency_id': row.config_id.currency_id.id if row.unit == 'money' else False,
                'policy_assessment_json': payload,
                'policy_assessment_hash': hashlib.sha256(payload.encode()).hexdigest() if payload else False})
            row.message_post(body=_('Period input approved with its evidence reference.'))
        return True

    def action_supersede(self):
        self._manager()
        self._lock()
        if any(r.state != 'approved' or r.reserved_payslip_id or r.consumed_payslip_id for r in self):
            raise UserError(_('Only an approved, unreserved and unconsumed input can be superseded.'))
        self.with_context(**{_TOKEN_KEY: _TOKEN}).write({'state': 'superseded'})
        for row in self:
            row.message_post(body=_('Unused period input superseded. Its approved value remains in the audit record.'))
        return True

    def _application_reserve(self, run, slip):
        self._lock()
        for row in self:
            if (row.state != 'approved' or row.employee_id != slip.employee_id
                    or row.company_id != slip.company_id or row.config_id != slip.formula_config_id
                    or row.date_from != slip.date_from or row.date_to != slip.date_to
                    or slip.payslip_run_id != run or not run.application_data_mode):
                raise UserError(_('The approved period input does not belong to this application payroll.'))
            if row.consumed_payslip_id and row.consumed_payslip_id != slip:
                raise UserError(_('This period input has already been paid by another payslip.'))
            if row.reserved_payslip_id and row.reserved_payslip_id != slip:
                raise UserError(_('This period input is reserved by another payslip. Cancel that draft before using it here.'))
            row._assessment()
        self.with_context(**{_TOKEN_KEY: _TOKEN}).write({'reserved_run_id': run.id, 'reserved_payslip_id': slip.id})

    def _application_consume(self, slip):
        self._lock()
        if any(r.reserved_payslip_id != slip or r.state != 'approved' for r in self):
            raise UserError(_('Reserve the approved period input for this payslip before completing payroll.'))
        if any(r.consumed_payslip_id and r.consumed_payslip_id != slip for r in self):
            raise UserError(_('This approved input has already been consumed.'))
        for row in self.filtered(lambda r: not r.consumed_payslip_id):
            assessment = row._assessment()
            if row.settlement_kind != 'none' and row.settlement_basis == 'policy':
                policy = row.employee_id._pb_policy_for_date(row.exit_reference.approved_lwd)
                if not hasattr(policy, '_consume_exit_settlement'):
                    raise UserError(_('The native leave settlement posting is unavailable. Payroll cannot consume this settlement.'))
                policy._consume_exit_settlement(row.employee_id, row.leave_type_reference,
                    row.exit_reference, assessment['cashout_days'], row)
            row.with_context(**{_TOKEN_KEY: _TOKEN}).write({
                'consumed_payslip_id': slip.id, 'consumed_at': fields.Datetime.now()})

    def _application_release(self, slip):
        self._lock()
        if any(r.consumed_payslip_id for r in self):
            raise UserError(_('A paid period input cannot be released. Use a reviewed reversal or adjustment.'))
        if any(r.reserved_payslip_id != slip for r in self):
            raise UserError(_('The reservation belongs to another payslip.'))
        self.with_context(**{_TOKEN_KEY: _TOKEN}).write({'reserved_run_id': False, 'reserved_payslip_id': False})


class PayrollPeriodInputRule(models.Model):
    _inherit = 'hr.formula.rule'

    application_zero_allowed = fields.Boolean(
        string='Allow signed no-activity zero', default=False,
        help='Only reviewed variable period inputs may allow an explicit no-activity attestation. Never enable for salary, identity, balances or unknown statutory data.')
    application_settlement_kind = fields.Selection([
        ('none', 'Ordinary input'), ('cashout_days', 'Policy cash-out days'),
        ('cashout_amount', 'Policy cash-out amount'), ('recovery_amount', 'Policy excess-leave recovery'),
    ], default='none', required=True)

    @api.constrains('application_zero_allowed', 'application_settlement_kind', 'value_kind')
    def _check_period_input_treatment(self):
        for rule in self:
            if rule.application_zero_allowed and (rule.value_kind not in _NUMERIC
                                                   or rule.is_contract_component):
                raise ValidationError(_('Only numeric period events can allow a signed no-activity zero.'))
            if rule.application_settlement_kind != 'none' and rule.value_kind not in _NUMERIC:
                raise ValidationError(_('Policy settlement components must be numeric.'))


class PayrollPeriodInputConfig(models.Model):
    _inherit = 'hr.formula.config'

    def action_application_period_inputs(self):
        self.ensure_one()
        self._application_require_access()
        action = self.env.ref('pb_hr_payroll_formula.action_payroll_period_inputs').read()[0]
        action.update(domain=[('config_id', '=', self.id), ('company_id', '=', self.company_id.id)],
                      context=dict(self.env.context, default_config_id=self.id,
                                   default_company_id=self.company_id.id))
        return action

    def _application_source_catalogue(self):
        result = dict(super()._application_source_catalogue())
        for config in self:
            for rule in config.rule_ids.filtered(lambda r: r.column_type == 'input'):
                result['period.input.' + rule.code] = {
                    'label': rule.name,
                    'unit': rule.value_kind, 'model': 'hr.payroll.period.input',
                    'component_code': rule.code, 'writable': False,
                    'certification_zero_allowed': bool(rule.application_zero_allowed),
                }
        return result

    def _application_domain_values(self, employee, contract, date_from, date_to):
        result = dict(super()._application_domain_values(employee, contract, date_from, date_to))
        self = self.sudo(False)
        employee, contract = employee.sudo(False), contract.sudo(False)
        self.ensure_one()
        run_id = self.env.context.get('pb_application_run_id') or self.env.context.get('application_run_id')
        slip_id = self.env.context.get('pb_application_payslip_id') or self.env.context.get('application_payslip_id')
        for rule in self.rule_ids.filtered(lambda r: (r.application_source_key or '').startswith('period.input.')):
            key = rule.application_source_key
            fact = {'value': None, 'status': 'missing', 'source_ids': [], 'evidence': {}}
            result[key] = fact
            if key != 'period.input.' + rule.code:
                fact.update(status='conflict', reason='Period input source must name this exact component.')
                continue
            rows = self.env['hr.payroll.period.input'].search([
                ('company_id', '=', self.company_id.id), ('config_id', '=', self.id),
                ('employee_id', '=', employee.id), ('component_id', '=', rule.id),
                ('date_from', '=', date_from), ('date_to', '=', date_to), ('state', 'in', ['draft', 'approved']),
            ])
            if rows.filtered(lambda row: row.state == 'draft'):
                fact.update(status='conflict', reason='A monthly adjustment is awaiting approval; it cannot be certified as no activity.')
                continue
            if len(rows) != 1:
                fact.update(status='conflict' if rows else 'missing',
                            reason='Exactly one approved monthly adjustment is required.')
                continue
            row = rows[0]
            if ((row.consumed_payslip_id and row.consumed_payslip_id.id != slip_id)
                    or (row.reserved_run_id and row.reserved_run_id.id != run_id)
                    or (slip_id and row.reserved_payslip_id and row.reserved_payslip_id.id != slip_id)):
                fact.update(status='conflict', reason='Input reserved or consumed by another payroll.')
                continue
            try:
                assessment = row._assessment()
            except (UserError, ValidationError, AccessError) as exc:
                fact.update(status='conflict', reason=str(exc))
                continue
            value = float(decimal_value(row.value_decimal)) if row.value_kind in _NUMERIC else row.value_text
            fact.update(value=value, status='resolved', source_ids=[[row._name, row.id]], evidence={
                'period_input_ids': row.ids, 'approved_by': row.approved_by.id,
                'approved_at': str(row.approved_at), 'evidence_reference': row.evidence_reference,
                'unit': row.unit, 'policy_assessment': assessment,
            })
        return result


class PayrollPeriodInputPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _period_input_records(self):
        self.ensure_one()
        snapshot = self.application_snapshot_id
        if not snapshot:
            return self.env['hr.payroll.period.input']
        payload = json.loads(snapshot.payload_json)
        ids = []
        for row in payload.get('inputs', []):
            if row.get('status') in ('resolved', 'zero_confirmed'):
                ids.extend((row.get('evidence') or {}).get('period_input_ids') or [])
        if len(ids) != len(set(ids)):
            raise UserError(_('One approved period input cannot feed multiple payroll components.'))
        records = self.env['hr.payroll.period.input'].browse(ids).exists()
        if len(records) != len(set(ids)):
            raise UserError(_('An approved source referenced by the payroll snapshot is missing.'))
        return records

    def _application_resolve_inputs(self, config):
        self.ensure_one()
        context = dict(pb_application_run_id=self.payslip_run_id.id,
                       pb_application_payslip_id=self.id)
        values = super(PayrollPeriodInputPayslip, self.with_context(**context))._application_resolve_inputs(
            config.with_context(**context))
        wanted = self._period_input_records()
        prior = self.env['hr.payroll.period.input'].search([('reserved_payslip_id', '=', self.id)])
        (prior - wanted)._application_release(self)
        wanted._application_reserve(self.payslip_run_id, self)
        return values

    def _application_assert_current(self):
        for slip in self:
            scoped = slip.with_context(pb_application_run_id=slip.payslip_run_id.id,
                                       pb_application_payslip_id=slip.id)
            super(PayrollPeriodInputPayslip, scoped)._application_assert_current()
        return True

    def write(self, vals):
        if vals.get('state') == 'cancel':
            for slip in self:
                reserved = self.env['hr.payroll.period.input'].search([('reserved_payslip_id', '=', slip.id)])
                reserved._application_release(slip)
        result = super().write(vals)
        if vals.get('state') in ('done', 'paid'):
            for slip in self.filtered(lambda s: s._application_mode()):
                slip._period_input_records()._application_consume(slip)
        return result

    def unlink(self):
        for slip in self:
            reserved = self.env['hr.payroll.period.input'].search([('reserved_payslip_id', '=', slip.id)])
            reserved._application_release(slip)
        return super().unlink()
