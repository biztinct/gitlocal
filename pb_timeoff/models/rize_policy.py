# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Versioned absence policy over native allocations and requests.

Policy postings are an audit trail, not another leave balance. There is no
scheduled or automatic data migration: Rize editions are seeded explicitly,
then employees and leave types are assigned after reviewed cutover.
"""
import calendar
import json
import math
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MANAGER = 'hr_holidays.group_hr_holidays_manager'
CATEGORIES = [
    ('annual', 'Annual / privilege'), ('wellness', 'Sick / wellness'),
    ('hospitalization', 'Hospitalization'), ('maternity', 'Maternity'),
    ('paternity', 'Paternity'), ('miscarriage', 'Miscarriage'),
    ('adoption', 'Adoption'), ('childcare', 'Childcare'),
    ('bereavement', 'Bereavement'), ('marriage', 'Marriage'),
    ('menstrual', 'Menstrual'), ('child_marriage', "Child's marriage"),
    ('family_death', 'Family death'), ('household_death', 'Household death'),
    ('baptism', 'Child baptism / khitan'), ('surrogacy', 'Surrogacy'),
    ('unpaid', 'Unpaid absence'),
]
TREATMENTS = [('unconfigured', 'Needs pay review'), ('paid', 'Paid'),
              ('unpaid', 'Unpaid'), ('partial', 'Partially paid')]
FUNDING = [('unconfigured', 'Needs funding review'), ('employer', 'Employer'),
           ('external', 'External benefit'), ('mixed', 'Employer and external'),
           ('none', 'No pay')]


def _manager(env):
    if not env.is_superuser() and not env.user.has_group(MANAGER):
        raise AccessError(_('Only a Time Off administrator can change policy or post entitlements.'))


def _classification(treatment, fraction, funding, employer_fraction, policy_id=False, rule_id=False):
    result = {'treatment': treatment, 'fraction': 0.0, 'employer_fraction': 0.0,
              'funding': funding, 'policy_id': policy_id, 'rule_id': rule_id, 'error': False}
    if treatment == 'unconfigured' or funding == 'unconfigured':
        result['error'] = _('Leave payment or funding is not configured.')
        return result
    if treatment == 'unpaid':
        fraction = 0.0
    elif treatment == 'paid':
        fraction = 1.0
    if not math.isfinite(fraction) or not 0 <= fraction <= 1:
        result['error'] = _('Leave paid fraction must be between zero and one.')
        return result
    if funding == 'employer':
        employer_fraction = fraction
    elif funding in ('external', 'none'):
        employer_fraction = 0.0
    if not math.isfinite(employer_fraction) or not 0 <= employer_fraction <= fraction:
        result['error'] = _('Employer continuation cannot exceed the leave paid fraction.')
        return result
    if (treatment == 'unpaid') != (funding == 'none'):
        result['error'] = _('Unpaid leave must use No pay funding; paid leave needs a funding source.')
        return result
    result.update(fraction=employer_fraction, employer_fraction=employer_fraction,
                  entitlement_fraction=fraction)
    return result


class LeavePolicyEdition(models.Model):
    _name = 'pb.leave.policy.edition'
    _description = 'Effective absence policy edition'
    _order = 'effective_from desc, id desc'

    name = fields.Char(required=True)
    code = fields.Char(required=True, default='ABSENCE', index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    country_id = fields.Many2one('res.country', required=True)
    effective_from = fields.Date(required=True)
    effective_to = fields.Date()
    source_effective_date = fields.Date(help='Date stated by the source policy, separate from system activation.')
    source_reference = fields.Char(required=True)
    state = fields.Selection([('draft', 'Draft'), ('published', 'Published')], default='draft', required=True)
    rule_ids = fields.One2many('pb.leave.policy.rule', 'edition_id', copy=True)
    full_time_only = fields.Boolean(default=True)
    annual_days = fields.Float(default=20)
    carry_cap = fields.Float(default=8)
    exit_divisor = fields.Float(default=30)
    exit_cashout_cap = fields.Float(default=60)
    joiner_proration = fields.Selection([
        ('review', 'HR review required'), ('daily', 'Calendar-day proportion'),
        ('monthly', 'Whole calendar months only')], default='review', required=True)
    workflow_mode = fields.Selection([
        ('email_form', 'Manager email and completed leave form'),
        ('portal', 'Policy-owner-approved portal equivalent')], default='email_form', required=True)
    workflow_authority_ref = fields.Char()
    interpretation_notes = fields.Text()
    overtime_policy_enabled = fields.Boolean(string='Enforce policy overtime controls')
    overtime_monthly_limit = fields.Float(default=40)
    overtime_annual_limit = fields.Float(default=200)
    overtime_extended_limit_authority = fields.Char(string='Annual-limit exception authority',
        help='Required evidence of eligible industry treatment before using the 300-hour annual limit.')

    @api.constrains('overtime_policy_enabled', 'overtime_monthly_limit', 'overtime_annual_limit',
                    'overtime_extended_limit_authority')
    def _check_overtime_policy(self):
        for row in self.filtered('overtime_policy_enabled'):
            if (not math.isfinite(row.overtime_monthly_limit) or not 0 < row.overtime_monthly_limit <= 40
                    or row.overtime_annual_limit not in (200, 300)):
                raise ValidationError(_('Policy overtime requires a monthly limit up to 40 and an annual limit of 200 or 300 hours.'))
            if row.overtime_annual_limit == 300 and not row.overtime_extended_limit_authority:
                raise ValidationError(_('Record verified industry authority before enabling the 300-hour annual limit.'))
    published_by = fields.Many2one('res.users', readonly=True, copy=False)
    published_at = fields.Datetime(readonly=True, copy=False)

    _version_unique = models.Constraint('unique(code, company_id, country_id, effective_from)',
                                       'A policy edition already starts on this date.')

    @api.constrains('effective_from', 'effective_to', 'annual_days', 'carry_cap', 'exit_divisor', 'exit_cashout_cap', 'state')
    def _check_policy(self):
        for row in self:
            if row.effective_to and row.effective_to < row.effective_from:
                raise ValidationError(_('Policy end must not precede its start.'))
            if any(not math.isfinite(v) or v < 0 for v in
                   (row.annual_days, row.carry_cap, row.exit_cashout_cap)) or not math.isfinite(row.exit_divisor) or row.exit_divisor <= 0:
                raise ValidationError(_('Entitlements and caps must be non-negative; the exit divisor must be positive.'))
            if row.state == 'published':
                others = self.search([
                    ('id', '!=', row.id), ('code', '=', row.code), ('company_id', '=', row.company_id.id),
                    ('country_id', '=', row.country_id.id), ('state', '=', 'published'),
                    ('effective_from', '<=', row.effective_to or date.max),
                    '|', ('effective_to', '=', False), ('effective_to', '>=', row.effective_from)])
                if others:
                    raise ValidationError(_('Published policy editions must not overlap.'))

    def write(self, vals):
        _manager(self.env)
        if self.filtered(lambda p: p.state == 'published'):
            # Closing an edition prospectively permits its successor without rewriting rules.
            if set(vals) != {'effective_to'} or not vals['effective_to']:
                raise UserError(_('Published policy rules are frozen. Create a new edition.'))
            if fields.Date.to_date(vals['effective_to']) < fields.Date.today():
                raise UserError(_('A published edition cannot be closed retrospectively.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        _manager(self.env)
        if any(v.get('state', 'draft') != 'draft' for v in vals_list):
            raise UserError(_('Create a draft edition, then publish it.'))
        return super().create(vals_list)

    def unlink(self):
        _manager(self.env)
        if self.filtered(lambda p: p.state == 'published'):
            raise UserError(_('Published policy editions cannot be deleted.'))
        return super().unlink()

    def copy(self, default=None):
        self.ensure_one()
        values = {'state': 'draft', 'effective_from': max(fields.Date.today(), self.effective_from) + timedelta(days=1),
                  'effective_to': False, 'name': self.name + _(' (revision)')}
        values.update(default or {})
        return super().copy(values)

    def action_publish(self):
        _manager(self.env)
        for row in self:
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                ['pb.leave.edition:%s:%s:%s' % (row.company_id.id, row.country_id.id, row.code)])
            if row.state == 'published':
                continue
            if not row.rule_ids:
                raise UserError(_('Add policy rules before publishing.'))
            if row.workflow_mode == 'portal' and not row.workflow_authority_ref:
                raise UserError(_('Record the policy owner approval for replacing email and form steps.'))
            row.write({'state': 'published', 'published_by': self.env.uid,
                       'published_at': fields.Datetime.now()})
        return True

    def _rule_for(self, category):
        self.ensure_one()
        return self.rule_ids.filtered(lambda r: r.category == category)[:1]

    @api.model
    def _seed_rize_policy(self, company_id, country_code, effective_from, leave_type_ids_by_category=None):
        """Explicit Rize migration hook, never loaded through global XML data.

        Existing leave types can be bound explicitly. No historical requests,
        employee assignments, balances or allocations are changed by this hook.
        """
        _manager(self.env)
        if self.env.cr.dbname != 'rize':
            raise UserError(_('Rize policy seeding is restricted to the rize database.'))
        country_code = str(country_code).upper()
        if country_code not in ('VN', 'IN', 'SG', 'ID'):
            raise ValidationError(_('Unsupported Rize country.'))
        start = fields.Date.to_date(effective_from)
        if not start or start < fields.Date.today():
            raise UserError(_('Rize activation must be today or a future date. Historical balances require separate reconciliation.'))
        company = self.env['res.company'].browse(company_id).exists()
        company.check_access('write')
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        existing = self.search([('code', '=', 'RIZE_TIMEOFF'), ('company_id', '=', company.id),
                                ('country_id', '=', country.id), ('effective_from', '=', start)], limit=1)
        if existing:
            existing._bind_policy_types(leave_type_ids_by_category or {})
            return existing
        edition = self.create({
            'name': 'Rize %s · Policy 1.0 · activation %s' % (country_code, start),
            'code': 'RIZE_TIMEOFF', 'company_id': company.id, 'country_id': country.id,
            'effective_from': start, 'source_effective_date': '2025-01-01',
            'source_reference': 'RIZE/Rize _ Time Off Policy.pdf · v1.0 · detailed clauses prevail',
            'carry_cap': 6 if country_code == 'ID' else 8,
            'overtime_policy_enabled': country_code == 'VN',
            'interpretation_notes': 'Literal supplied policy. No automatic statutory substitution. '
                'HR review: maternity/PL interaction, Indonesian bereavement overlap, new-joiner proration scope, '
                'partial-month exit proration, and benefit payment/funding. Indonesia Act reference includes Law4/2024.'})
        definitions = [
            ('annual', 20, 'working', 'year', 'paid', 'employer', '', 10),
            ('wellness', {'VN': 10, 'IN': 12, 'SG': 14, 'ID': 0}[country_code], 'working', 'year', 'paid', 'employer', '', 0),
            ('maternity', {'VN': 6, 'IN': 182, 'SG': 112, 'ID': 3}[country_code],
             'months' if country_code in ('VN', 'ID') else 'calendar', 'event', 'unconfigured', 'unconfigured', '', 0),
            ('paternity', 14, 'calendar', 'event', 'unconfigured', 'unconfigured', '', 0),
            ('miscarriage', 42 if country_code == 'IN' else 45, 'calendar', 'event',
             'paid' if country_code in ('IN', 'ID') else 'unconfigured',
             'employer' if country_code in ('IN', 'ID') else 'unconfigured',
             '', 0),
            ('bereavement', 3, 'working', 'event', 'unconfigured', 'unconfigured',
             'Indonesia general and specific bereavement clauses conflict.' if country_code == 'ID' else '', 0),
            ('marriage', 3, 'working', 'year', 'unconfigured', 'unconfigured', '', 0),
            ('unpaid', 0, 'working', 'event', 'unpaid', 'none', '', 0),
        ]
        if country_code == 'SG':
            definitions += [('hospitalization', 60, 'working', 'year', 'paid', 'employer',
                             'HR must settle the outpatient/hospitalization shared cap.', 0),
                            ('childcare', 6, 'working', 'year', 'unconfigured', 'unconfigured', '', 0)]
        if country_code in ('SG', 'IN'):
            definitions += [('adoption', 84, 'calendar', 'event', 'unconfigured', 'unconfigured', '', 0)]
        if country_code == 'IN':
            definitions += [('surrogacy', 84, 'calendar', 'event', 'unconfigured', 'unconfigured', '', 0)]
        if country_code == 'ID':
            definitions += [(c, n, 'working', 'event', 'unconfigured', 'unconfigured', note, 0) for c, n, note in [
                ('menstrual', 2, 'The policy does not state the recurrence period.'),
                ('child_marriage', 2, ''), ('family_death', 2, 'General bereavement overlaps this event.'),
                ('household_death', 1, 'General bereavement overlaps this event.'), ('baptism', 2, '')]]
        labels = dict(CATEGORIES)
        for category, quantity, counting, period, pay, funding, review, maximum in definitions:
            self.env['pb.leave.policy.rule'].create({
                'edition_id': edition.id, 'name': labels[category], 'category': category,
                'quantity': quantity, 'counting': counting, 'limit_period': period,
                'pay_treatment': pay, 'paid_fraction': 0 if pay == 'unpaid' else 1,
                'pay_funding': funding, 'review_reason': review, 'max_request_days': maximum,
                'medical_after_days': 3 if category in ('wellness', 'hospitalization') else 0,
                'event_evidence_required': category not in ('annual', 'wellness', 'unpaid', 'hospitalization'),
                'source_pages': '5–8' if category == 'annual' else '8–12',
            })
        edition._bind_policy_types(leave_type_ids_by_category or {})
        edition.action_publish()
        return edition

    def _bind_policy_types(self, mappings):
        _manager(self.env)
        self.ensure_one()
        for category, leave_type_id in mappings.items():
            rule = self._rule_for(category)
            if not rule:
                raise ValidationError(_('No Rize rule exists for category %s.', category))
            leave_type = self.env['hr.leave.type'].browse(leave_type_id).exists()
            if len(leave_type) != 1 or (leave_type.company_id and leave_type.company_id != self.company_id):
                raise ValidationError(_('The mapped leave type belongs to another company.'))
            if leave_type.pb_policy_country_id and leave_type.pb_policy_country_id != self.country_id:
                raise ValidationError(_('The mapped leave type belongs to another employment country.'))
            leave_type.write({'pb_policy_category': category, 'pb_pay_treatment': rule.pay_treatment,
                              'pb_paid_fraction': rule.paid_fraction, 'pb_pay_funding': rule.pay_funding,
                              'pb_policy_country_id': self.country_id.id})

    def post_annual_credit(self, employee_id, leave_type_id, year, employment_start,
                           reviewed_days=None, review_reference=None):
        """Grant native annual allocation once, never backfill an incomplete year."""
        _manager(self.env)
        self.ensure_one()
        employee, leave_type = self._posting_subject(employee_id, leave_type_id)
        year = int(year)
        start, end = date(year, 1, 1), date(year, 12, 31)
        employment_start = fields.Date.to_date(employment_start)
        if not employment_start or employment_start > end:
            raise UserError(_('A verified employment episode start within or before the year is required.'))
        credit_start = max(start, employment_start)
        if credit_start < self.effective_from:
            raise UserError(_('This year predates policy activation. Import reviewed opening balances instead.'))
        if self.effective_to and credit_start > self.effective_to:
            raise UserError(_('Select the policy edition effective on the annual credit date.'))
        days = self.annual_days
        if employment_start > start:
            if self.joiner_proration == 'daily':
                days *= ((end - employment_start).days + 1) / ((end - start).days + 1)
            elif self.joiner_proration == 'monthly' and employment_start.day == 1:
                days *= (13 - employment_start.month) / 12
            elif reviewed_days is None or not review_reference:
                raise UserError(_('New-joiner proration needs HR-reviewed days and an evidence reference.'))
            else:
                days = float(reviewed_days)
        if not math.isfinite(days) or not 0 < days <= self.annual_days:
            raise ValidationError(_('Reviewed annual credit must be positive and within the annual entitlement.'))
        # An existing native allocation must be reconciled, never credited twice.
        key = '%s:%s:%s:annual' % (employee.id, leave_type.id, year)
        existing = self._lock_posting(key)
        if existing:
            return existing
        overlapping = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', '!=', 'refuse'), ('date_from', '<=', end),
            '|', ('date_to', '=', False), ('date_to', '>=', credit_start)])
        if overlapping.filtered(lambda a: not a.pb_policy_posting_id or a.pb_policy_posting_id.kind != 'carry'):
            raise UserError(_('Existing annual allocations overlap this year. Reconcile them before granting another credit.'))
        return self._create_posting(employee, leave_type, year, 'annual', key, days, credit_start, end,
                                    review_reference=review_reference or 'Policy annual entitlement')

    def _posting_subject(self, employee_id, leave_type_id):
        if self.state != 'published':
            raise UserError(_('Publish the edition first.'))
        employee = self.env['hr.employee'].browse(employee_id).exists()
        leave_type = self.env['hr.leave.type'].browse(leave_type_id).exists()
        employee.check_access('write')
        leave_type.check_access('write')
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                            ['pb.leave.balance:%s:%s' % (employee.id, leave_type.id)])
        self.env.cr.execute('SELECT id FROM hr_leave_allocation WHERE employee_id=%s AND holiday_status_id=%s ORDER BY id FOR UPDATE',
                            [employee.id, leave_type.id])
        if employee.company_id != self.company_id or (leave_type.company_id and leave_type.company_id != self.company_id):
            raise ValidationError(_('Policy, employee and leave type must belong to the same company.'))
        if leave_type.pb_policy_country_id and leave_type.pb_policy_country_id != self.country_id:
            raise ValidationError(_('The native leave type belongs to another employment country.'))
        assigned = employee.sudo().pb_leave_policy_id
        if not assigned or assigned.code != self.code or assigned.country_id != self.country_id:
            raise ValidationError(_('Assign the employee to this policy family and employment country first.'))
        if self.full_time_only and not employee.sudo().pb_policy_full_time_confirmed:
            raise UserError(_('Verify full-time eligibility before posting an entitlement.'))
        if leave_type.pb_policy_category != 'annual' or not leave_type.requires_allocation or leave_type.request_unit == 'hour':
            raise ValidationError(_('Use an annual leave type with native allocations counted in days.'))
        return employee, leave_type

    def _lock_posting(self, key):
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ['pb.leave.policy:' + key])
        return self.env['pb.leave.policy.posting'].search([('posting_key', '=', key)], limit=1)

    def _create_posting(self, employee, leave_type, year, kind, key, days, start, end,
                        source_days=0, lapsed_days=0, review_reference=None, source_allocations=None):
        posting = self.env['pb.leave.policy.posting'].create({
            'edition_id': self.id, 'employee_id': employee.id, 'leave_type_id': leave_type.id,
            'year': year, 'kind': kind, 'posting_key': key, 'days': days,
            'source_days': source_days, 'lapsed_days': lapsed_days,
            'review_reference': review_reference,
            'source_allocation_ids': [(6, 0, (source_allocations or self.env['hr.leave.allocation']).ids)]})
        if days > 0:
            allocation = self.env['hr.leave.allocation'].create({
                'name': '%s · %s · %s' % (self.name, kind, year),
                'employee_id': employee.id, 'holiday_status_id': leave_type.id,
                'allocation_type': 'regular', 'number_of_days': days,
                'date_from': start, 'date_to': end, 'pb_policy_posting_id': posting.id})
            if allocation.state != 'validate':
                allocation.action_approve()
            posting.allocation_id = allocation
        return posting

    def post_opening_balance(self, employee_id, leave_type_id, cutover_date, available_days,
                             carried_days, taken_year_to_date, review_reference):
        """Explicit reviewed cutover; native allocations remain the only balance."""
        _manager(self.env)
        self.ensure_one()
        employee, leave_type = self._posting_subject(employee_id, leave_type_id)
        cutover = fields.Date.to_date(cutover_date)
        values = [float(v) for v in (available_days, carried_days, taken_year_to_date)]
        if (not review_reference or not cutover or cutover < self.effective_from
                or (self.effective_to and cutover > self.effective_to)):
            raise UserError(_('Opening balances require a reviewed reference and an active cutover date.'))
        if any(not math.isfinite(v) or v < 0 for v in values) or values[1] > self.carry_cap:
            raise ValidationError(_('Opening quantities must be non-negative and carried leave within the policy cap.'))
        key = '%s:%s:%s:opening' % (employee.id, leave_type.id, cutover.year)
        existing = self._lock_posting(key)
        if existing:
            return existing
        if self.env['hr.leave.allocation'].search_count([
                ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
                ('state', '!=', 'refuse'), ('date_from', '<=', date(cutover.year, 12, 31)),
                '|', ('date_to', '=', False), ('date_to', '>=', cutover)]):
            raise UserError(_('Existing allocations overlap cutover. Reconcile their validity before importing an opening balance.'))
        posting = self._create_posting(employee, leave_type, cutover.year, 'opening', key, values[0],
                                       cutover, date(cutover.year, 12, 31), review_reference=review_reference)
        # Internal initialization only, never a mutable second balance.
        super(LeavePolicyPosting, posting).write({'opening_carried_days': values[1],
                                                  'opening_taken_days': values[2], 'cutover_date': cutover})
        return posting

    def post_rollover(self, employee_id, leave_type_id, year, review_reference):
        """Expire the managed prior cycle and replace its unused balance once.

        No arbitrary legacy allocations are changed. The audit posting records
        forfeiture; native dated allocations remain the sole balance engine.
        """
        _manager(self.env)
        self.ensure_one()
        employee, leave_type = self._posting_subject(employee_id, leave_type_id)
        start, prior = date(int(year), 1, 1), date(int(year) - 1, 12, 31)
        if (not review_reference or start < self.effective_from
                or (self.effective_to and start > self.effective_to)):
            raise UserError(_('Rollover requires a reviewed reference and an active policy date.'))
        key = '%s:%s:%s:carry' % (employee.id, leave_type.id, year)
        existing = self._lock_posting(key)
        if existing:
            return existing
        pending = self.env['hr.leave'].search_count([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', 'in', ('confirm', 'validate1')), ('request_date_from', '<=', prior)])
        if pending:
            raise UserError(_('Resolve prior-year pending leave before rollover.'))
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', '=', 'validate'), ('date_from', '<=', prior),
            '|', ('date_to', '=', False), ('date_to', '>=', prior)])
        if not allocations or any(not a.pb_policy_posting_id or a.date_to != prior or a.allocation_type != 'regular' for a in allocations):
            raise UserError(_('Rollover requires reconciled policy-managed allocations ending on 31 December. Import opening balances for legacy records.'))
        if self.env['hr.leave'].search_count([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', 'in', ('confirm', 'validate1', 'validate')),
            ('request_date_from', '<=', prior), ('request_date_to', '>=', start)]):
            raise UserError(_('Split and reconcile cross-year requests before rollover.'))
        consumed = employee._get_consumed_leaves(leave_type, target_date=prior, ignore_future=True)[0]
        values = consumed.get(employee, {}).get(leave_type, {})
        remaining = sum(max(0, values.get(a, {}).get('remaining_leaves', 0)) for a in allocations)
        carried = min(self.carry_cap, remaining)
        return self._create_posting(employee, leave_type, int(year), 'carry', key, carried, start,
                                    date(int(year), 12, 31), source_days=remaining,
                                    lapsed_days=remaining - carried, review_reference=review_reference,
                                    source_allocations=allocations)

    def assess_exit(self, employee_id, leave_type_id, exit_date, employment_start, gross_salary,
                    reviewed_months=None, review_reference=None):
        """Read-only earned/bookable settlement assessment; no payment or debit."""
        _manager(self.env)
        self.ensure_one()
        employee, leave_type = self._posting_subject(employee_id, leave_type_id)
        end = fields.Date.to_date(exit_date)
        employment_start = fields.Date.to_date(employment_start)
        if not end or not employment_start:
            raise UserError(_('Verified employment start and exit dates are required.'))
        start = max(employment_start, date(end.year, 1, 1))
        if end < self.effective_from or (self.effective_to and end > self.effective_to) or end < start:
            raise UserError(_('Exit assessment dates are outside this policy or employment episode.'))
        if self.env['pb.leave.policy.settlement'].search_count([
                ('employee_id', '=', employee.id), ('leave_type_id', '=', leave_type.id),
                ('closed_on', '>=', start), ('closed_on', '<=', end)]):
            raise UserError(_('This employment episode already has a terminal leave settlement. Use its immutable assessment or a reviewed reversal.'))
        salary = float(gross_salary)
        if not math.isfinite(salary) or salary < 0:
            raise ValidationError(_('Gross monthly salary must be finite and non-negative.'))
        complete_months = start.day == 1 and end.day == calendar.monthrange(end.year, end.month)[1]
        if complete_months:
            months = end.month - start.month + 1
        elif reviewed_months is not None and review_reference:
            months = float(reviewed_months)
        else:
            raise UserError(_('Partial-month exit proration needs HR-reviewed months and a reference.'))
        if not math.isfinite(months) or not 0 <= months <= 12:
            raise ValidationError(_('Reviewed service months must be between zero and twelve.'))
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', '=', 'validate'), ('date_from', '<=', end),
            '|', ('date_to', '=', False), ('date_to', '>=', date(end.year, 1, 1))])
        if not allocations or any(not a.pb_policy_posting_id for a in allocations):
            raise UserError(_('Legacy balances must be reconciled before exit assessment.'))
        opening = self.env['pb.leave.policy.posting'].search([
            ('employee_id', '=', employee.id), ('leave_type_id', '=', leave_type.id),
            ('year', '=', end.year), ('kind', '=', 'opening')], limit=1)
        carry = (opening.opening_carried_days if opening else 0) + sum(a.number_of_days for a in allocations
                    if a.pb_policy_posting_id.kind == 'carry' and a.pb_policy_posting_id.year == end.year)
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', 'in', ('confirm', 'validate1', 'validate')), ('request_date_from', '<=', end),
            ('request_date_to', '>=', date(end.year, 1, 1))])
        if any(l.state != 'validate' or l.request_date_from < date(end.year, 1, 1) or l.request_date_to > end for l in leaves):
            raise UserError(_('Resolve pending or boundary-spanning leave before settlement.'))
        if opening:
            if leaves.filtered(lambda l: l.request_date_from < opening.cutover_date <= l.request_date_to):
                raise UserError(_('Reconcile leave spanning the opening-balance cutover before settlement.'))
            leaves = leaves.filtered(lambda l: l.request_date_from >= opening.cutover_date)
        taken = sum(leaves.mapped('number_of_days')) + (opening.opening_taken_days if opening else 0)
        earned = months / 12 * self.annual_days
        unused, excess = max(0, earned + carry - taken), max(0, taken - earned - carry)
        cashout = min(self.exit_cashout_cap, unused)
        balance_data = employee._get_consumed_leaves(leave_type, target_date=end, ignore_future=True)[0]
        native = balance_data.get(employee, {}).get(leave_type, {})
        bookable = sum(v.get('remaining_leaves', 0) for a, v in native.items()
                       if a and a.date_from <= end and (not a.date_to or a.date_to >= end))
        if cashout > max(0, bookable) + 0.00001:
            raise UserError(_('Earned cash-out exceeds the native available balance. Reconcile opening balances and prior settlements first.'))
        return {'policy_id': self.id, 'employee_id': employee.id, 'as_of': str(end),
                'bookable_days': bookable, 'earned_days': earned, 'carried_days': carry,
                'taken_days': taken, 'cashout_days': cashout,
                'cashout_amount': salary / self.exit_divisor * cashout,
                'excess_days': excess, 'recovery_amount': salary / self.exit_divisor * excess,
                'gross_salary': salary, 'divisor': self.exit_divisor,
                'review_reference': review_reference or False,
                'assessment_only': True, 'requires_settlement_approval_and_native_balance_debit': True}

    def _settlement_posting(self, period_input):
        return self.env['pb.leave.policy.settlement'].search([
            ('period_input_reference', '=', '%s,%s' % (period_input._name, period_input.id))], limit=1)

    def _consume_exit_settlement(self, employee, leave_type, exit_case, days, period_input):
        return self.post_exit_settlement(employee.id, leave_type.id, exit_case, days, period_input)

    def post_exit_settlement(self, employee_id, leave_type_id, exit_case, days, period_input):
        """Close the settled employment episode atomically with payroll completion.

        Grant quantities remain intact. The audit preserves their original end
        dates; closing them prevents bookings after exit. Native balance reads
        account for terminal cash-out and forfeiture from the closing date.
        """
        _manager(self.env)
        self.ensure_one()
        employee, leave_type = self._posting_subject(employee_id, leave_type_id)
        if (exit_case._name != 'pb.resignation' or exit_case.state != 'approved'
                or exit_case.employee_id != employee or exit_case.company_id != self.company_id
                or not exit_case.approved_lwd):
            raise UserError(_('An approved exit for this employee and company is required.'))
        if (period_input._name != 'hr.payroll.period.input' or period_input.state != 'approved'
                or period_input.employee_id != employee or period_input.company_id != self.company_id
                or not period_input.reserved_payslip_id
                or period_input.settlement_kind not in ('cashout_days', 'cashout_amount', 'recovery_amount')):
            raise UserError(_('Reserve an approved policy settlement input for payroll before closing leave.'))
        if period_input.exit_reference != exit_case or period_input.leave_type_reference != leave_type:
            raise UserError(_('The settlement input must reference this approved exit and annual leave type.'))
        reference = '%s,%s' % (exit_case._name, exit_case.id)
        previous = self.env['pb.leave.policy.settlement'].search([
            ('employee_id', '=', employee.id), ('leave_type_id', '=', leave_type.id),
            ('exit_reference', '=', reference)], limit=1)
        if previous:
            if previous.period_input_reference == '%s,%s' % (period_input._name, period_input.id):
                return previous
            raise UserError(_('The annual leave balance for this exit was already settled by another input.'))
        end = exit_case.approved_lwd
        assessment = self.assess_exit(employee.id, leave_type.id, end,
            period_input.settlement_employment_start, float(period_input.settlement_gross_salary),
            period_input.settlement_months if period_input.settlement_review_months else None,
            period_input.evidence_reference)
        expected_days = assessment['cashout_days']
        if not math.isfinite(float(days)) or abs(float(days) - expected_days) > 0.000001:
            raise UserError(_('The cash-out days changed; review and approve the settlement again.'))
        if period_input.policy_assessment_json != json.dumps(assessment, sort_keys=True, default=str):
            raise UserError(_('The approved policy assessment changed before settlement posting.'))
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
            ('state', '!=', 'refuse'), '|', ('date_to', '=', False), ('date_to', '>=', end)])
        if any(a.state != 'validate' or not a.pb_policy_posting_id or a.date_from > end for a in allocations):
            raise UserError(_('Reconcile pending, future or unmanaged allocations before terminal leave settlement.'))
        if self.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id), ('holiday_status_id', '=', leave_type.id),
                ('state', 'in', ('confirm', 'validate1', 'validate')), ('request_date_to', '>', end)]):
            raise UserError(_('Cancel or reconcile leave after the approved exit before settling the balance.'))
        balances = employee._get_consumed_leaves(leave_type, target_date=end, ignore_future=True)[0]
        native = balances.get(employee, {}).get(leave_type, {})
        audit = [{'allocation_id': a.id, 'original_days': a.number_of_days,
                  'original_date_from': str(a.date_from), 'original_date_to': str(a.date_to) if a.date_to else False,
                  'available_days': native.get(a, {}).get('remaining_leaves', 0)} for a in allocations]
        for allocation in allocations:
            if allocation.date_to != end:
                # This private, audited operation is the sole permitted validity
                # closure of a managed grant. Original quantities are unchanged.
                super(LeavePolicyAllocation, allocation).write({'date_to': end})
        posting = self.env['pb.leave.policy.settlement']._create_from_payroll({
            'edition_id': self.id, 'employee_id': employee.id, 'leave_type_id': leave_type.id,
            'exit_reference': reference, 'period_input_reference': '%s,%s' % (period_input._name, period_input.id),
            'closed_on': end, 'cashout_days': expected_days,
            'lapsed_days': max(0, assessment['bookable_days'] - expected_days),
            'allocation_ids': [(6, 0, allocations.ids)], 'allocation_audit_json': json.dumps(audit, sort_keys=True),
            'assessment_json': period_input.policy_assessment_json,
            'posted_by': self.env.uid, 'posted_at': fields.Datetime.now()})
        allocations.invalidate_recordset()
        return posting


class LeavePolicyRule(models.Model):
    _name = 'pb.leave.policy.rule'
    _description = 'Absence policy rule'
    _order = 'edition_id, id'

    name = fields.Char(required=True)
    edition_id = fields.Many2one('pb.leave.policy.edition', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='edition_id.company_id', store=True)
    category = fields.Selection(CATEGORIES, required=True)
    quantity = fields.Float(help='Zero means no numerical cap, not zero entitlement.')
    counting = fields.Selection([('working', 'Scheduled working days'), ('calendar', 'Calendar days'),
                                 ('months', 'Calendar months')], default='working', required=True)
    limit_period = fields.Selection([('year', 'Per calendar year'), ('event', 'Per event')], default='event', required=True)
    max_request_days = fields.Float()
    medical_after_days = fields.Float()
    event_evidence_required = fields.Boolean()
    review_reason = fields.Text(help='An unresolved interpretation blocks approval until an authorized exception is recorded.')
    source_pages = fields.Char()
    pay_treatment = fields.Selection(TREATMENTS, default='unconfigured', required=True)
    paid_fraction = fields.Float(default=1)
    pay_funding = fields.Selection(FUNDING, default='unconfigured', required=True)
    employer_paid_fraction = fields.Float(default=0, help='Explicit employer continuation for mixed funding, from 0 to 1.')

    _one_category = models.Constraint('unique(edition_id, category)', 'Only one rule per category and edition is allowed.')

    @api.constrains('quantity', 'paid_fraction', 'employer_paid_fraction', 'max_request_days', 'medical_after_days', 'pay_treatment', 'pay_funding')
    def _check_rule(self):
        for row in self:
            numbers = (row.quantity, row.max_request_days, row.medical_after_days, row.paid_fraction, row.employer_paid_fraction)
            if any(not math.isfinite(v) or v < 0 for v in numbers) or row.paid_fraction > 1 or row.employer_paid_fraction > 1:
                raise ValidationError(_('Rule quantities must be non-negative and pay fractions between zero and one.'))
            if row.pay_treatment != 'unconfigured' and row.pay_funding != 'unconfigured':
                result = row._pay_classification()
                if result['error']:
                    raise ValidationError(result['error'])

    def _pay_classification(self):
        self.ensure_one()
        return _classification(self.pay_treatment, self.paid_fraction, self.pay_funding,
                               self.employer_paid_fraction, self.edition_id.id, self.id)

    @api.model_create_multi
    def create(self, vals_list):
        _manager(self.env)
        editions = self.env['pb.leave.policy.edition'].browse([v['edition_id'] for v in vals_list])
        if editions.filtered(lambda p: p.state == 'published'):
            raise UserError(_('Published policy rules are frozen.'))
        return super().create(vals_list)

    def write(self, vals):
        _manager(self.env)
        if self.edition_id.filtered(lambda p: p.state == 'published'):
            raise UserError(_('Published policy rules are frozen. Create a new edition.'))
        if vals.get('edition_id') and self.env['pb.leave.policy.edition'].browse(vals['edition_id']).state == 'published':
            raise UserError(_('Cannot move a rule into a published edition.'))
        return super().write(vals)

    def unlink(self):
        _manager(self.env)
        if self.edition_id.filtered(lambda p: p.state == 'published'):
            raise UserError(_('Published policy rules cannot be deleted.'))
        return super().unlink()


class LeavePolicyPosting(models.Model):
    _name = 'pb.leave.policy.posting'
    _description = 'Native leave allocation policy audit'
    _order = 'year desc, id desc'

    edition_id = fields.Many2one('pb.leave.policy.edition', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='edition_id.company_id', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='restrict', index=True)
    leave_type_id = fields.Many2one('hr.leave.type', required=True, ondelete='restrict')
    year = fields.Integer(required=True)
    kind = fields.Selection([('annual', 'Annual credit'), ('carry', 'Carry and excess lapse'), ('opening', 'Reviewed opening balance')], required=True)
    posting_key = fields.Char(required=True, index=True)
    days = fields.Float(readonly=True)
    cutover_date = fields.Date(readonly=True)
    opening_carried_days = fields.Float(readonly=True)
    opening_taken_days = fields.Float(readonly=True)
    source_days = fields.Float(readonly=True)
    lapsed_days = fields.Float(readonly=True)
    allocation_id = fields.Many2one('hr.leave.allocation', readonly=True, ondelete='restrict')
    allocation_state = fields.Selection(related='allocation_id.state')
    source_allocation_ids = fields.Many2many('hr.leave.allocation', readonly=True)
    review_reference = fields.Char(readonly=True)
    _once_only = models.Constraint('unique(posting_key)', 'This policy allocation has already been posted.')

    @api.constrains('edition_id', 'employee_id', 'leave_type_id', 'days', 'source_days', 'lapsed_days')
    def _check_posting(self):
        for posting in self:
            if posting.employee_id.company_id != posting.company_id or (posting.leave_type_id.company_id and posting.leave_type_id.company_id != posting.company_id):
                raise ValidationError(_('Entitlement audit records cannot cross companies.'))
            if any(not math.isfinite(v) or v < 0 for v in (posting.days, posting.source_days, posting.lapsed_days)):
                raise ValidationError(_('Entitlement audit quantities must be finite and non-negative.'))

    @api.model_create_multi
    def create(self, vals_list):
        _manager(self.env)
        return super().create(vals_list)

    def unlink(self):
        raise UserError(_('Policy postings are permanent allocation audit records.'))

    def write(self, vals):
        _manager(self.env)
        if set(vals) != {'allocation_id'} or any(r.allocation_id for r in self):
            raise UserError(_('Policy postings are immutable.'))
        return super().write(vals)


class LeavePolicyAllocation(models.Model):
    _inherit = 'hr.leave.allocation'
    pb_policy_posting_id = fields.Many2one('pb.leave.policy.posting', readonly=True, copy=False, ondelete='restrict')
    _policy_posting_once = models.Constraint('unique(pb_policy_posting_id)', 'A policy posting can produce only one native allocation.')

    @api.constrains('pb_policy_posting_id', 'employee_id', 'holiday_status_id', 'number_of_days')
    def _check_policy_posting(self):
        for allocation in self.filtered('pb_policy_posting_id'):
            posting = allocation.pb_policy_posting_id
            if allocation.employee_id != posting.employee_id or allocation.holiday_status_id != posting.leave_type_id or abs(allocation.number_of_days - posting.days) > 0.00001:
                raise ValidationError(_('The native allocation must match its reviewed policy posting.'))

    def write(self, vals):
        frozen = {'employee_id', 'holiday_status_id', 'date_from', 'date_to', 'number_of_days',
                  'number_of_days_display', 'number_of_hours_display', 'allocation_type', 'pb_policy_posting_id'}
        for employee_id, type_id in sorted({(a.employee_id.id, a.holiday_status_id.id)
                                           for a in self if a.pb_policy_posting_id}):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                ['pb.leave.balance:%s:%s' % (employee_id, type_id)])
        if vals.get('state') and self.env['pb.leave.policy.settlement'].sudo().search_count([
                ('allocation_ids', 'in', self.ids)]):
            raise UserError(_('Settled grant history is immutable; use a reviewed reversal process.'))
        if frozen.intersection(vals) and self.filtered('pb_policy_posting_id'):
            raise UserError(_('Policy-managed allocation quantities and validity are frozen; use a reviewed correction.'))
        return super().write(vals)


class LeavePolicySettlement(models.Model):
    _name = 'pb.leave.policy.settlement'
    _description = 'Terminal annual leave settlement audit'
    _order = 'closed_on desc, id desc'

    edition_id = fields.Many2one('pb.leave.policy.edition', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='edition_id.company_id', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='restrict', index=True)
    leave_type_id = fields.Many2one('hr.leave.type', required=True, ondelete='restrict')
    exit_reference = fields.Char(required=True, readonly=True)
    period_input_reference = fields.Char(required=True, readonly=True)
    closed_on = fields.Date(required=True, index=True)
    cashout_days = fields.Float(required=True)
    lapsed_days = fields.Float(required=True)
    allocation_ids = fields.Many2many('hr.leave.allocation', string='Closed native allocations')
    allocation_audit_json = fields.Text(required=True)
    assessment_json = fields.Text(required=True)
    posted_by = fields.Many2one('res.users', required=True)
    posted_at = fields.Datetime(required=True)

    _exit_once = models.Constraint('unique(employee_id, leave_type_id, exit_reference)',
                                   'This exit and annual leave type has already been settled.')
    _input_once = models.Constraint('unique(period_input_reference)',
                                    'This payroll input already closed a leave settlement.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Terminal leave postings are created only by the payroll settlement operation.'))

    @api.model
    def _create_from_payroll(self, vals):
        _manager(self.env)
        return super().create(vals)

    def write(self, vals):
        raise AccessError(_('Terminal leave settlement evidence is immutable.'))

    def unlink(self):
        raise AccessError(_('Terminal leave settlement evidence cannot be deleted.'))


class LeavePolicyEmployee(models.Model):
    _inherit = 'hr.employee'
    pb_leave_policy_id = fields.Many2one('pb.leave.policy.edition', string='Absence policy family',
                                        domain="[('state', '=', 'published'), ('company_id', '=', company_id)]",
                                        groups='hr.group_hr_user')
    pb_policy_full_time_confirmed = fields.Boolean(string='Full-time policy eligibility verified',
                                                   groups='hr.group_hr_user')
    pb_policy_eligibility_review_ref = fields.Char(string='Full-time eligibility review evidence',
                                                   groups='hr.group_hr_user')

    @api.constrains('pb_leave_policy_id', 'company_id')
    def _check_leave_policy_company(self):
        for employee in self:
            if employee.pb_leave_policy_id and employee.pb_leave_policy_id.company_id != employee.company_id:
                raise ValidationError(_('Employee absence policy belongs to another company.'))

    def write(self, vals):
        if {'pb_leave_policy_id', 'pb_policy_full_time_confirmed', 'pb_policy_eligibility_review_ref'}.intersection(vals):
            _manager(self.env)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any({'pb_leave_policy_id', 'pb_policy_full_time_confirmed', 'pb_policy_eligibility_review_ref'}.intersection(vals) for vals in vals_list):
            _manager(self.env)
        return super().create(vals_list)

    def _pb_policy_for_date(self, on_date):
        self.ensure_one()
        assigned = self.sudo().pb_leave_policy_id
        if not assigned or not on_date:
            return self.env['pb.leave.policy.edition']
        return self.env['pb.leave.policy.edition'].search([
            ('code', '=', assigned.code), ('company_id', '=', self.company_id.id),
            ('country_id', '=', assigned.country_id.id), ('state', '=', 'published'),
            ('effective_from', '<=', on_date), '|', ('effective_to', '=', False),
            ('effective_to', '>=', on_date)], limit=1)

    def _get_consumed_leaves(self, leave_types, target_date=False, ignore_future=False):
        result = super()._get_consumed_leaves(leave_types, target_date=target_date, ignore_future=ignore_future)
        employees = self or self._get_contextual_employee()
        on_date = fields.Date.to_date(target_date) if target_date else fields.Date.today()
        # Narrow elevation provides numeric own-balance effects without exposing
        # the salary or exit evidence stored on the HR-only settlement record.
        postings = self.env['pb.leave.policy.settlement'].sudo().search([
            ('employee_id', 'in', employees.ids), ('leave_type_id', 'in', leave_types.ids),
            ('closed_on', '<=', on_date)])
        for posting in postings:
            employee = self.env['hr.employee'].browse(posting.employee_id.id)
            leave_type = self.env['hr.leave.type'].browse(posting.leave_type_id.id)
            native = result[0].get(employee, {}).get(leave_type, {})
            for allocation in self.env['hr.leave.allocation'].browse(posting.allocation_ids.ids):
                if allocation in native:
                    native[allocation]['remaining_leaves'] = 0.0
                    native[allocation]['virtual_remaining_leaves'] = 0.0
                    native[allocation]['policy_terminal_settlement_id'] = posting.id
        return result

    def _pb_policy_payroll_metrics(self, date_to):
        """Policy limits and native balance facts, preserving missing as missing.

        Entitlement is the annual policy limit, not a joiner credit or exit-earned
        amount. An uncapped category has no numerical entitlement. Balances are
        available only from an unambiguous native allocated leave type.
        """
        self.ensure_one()
        on_date = fields.Date.to_date(date_to)
        keys = ('annual_entitlement', 'sick_entitlement', 'annual_balance', 'sick_balance')
        result = dict.fromkeys(keys)
        result.update(policy_id=False, as_of=str(on_date) if on_date else False,
                      allocation_ids=[], errors={})
        policy = self._pb_policy_for_date(on_date)
        if not policy or (policy.full_time_only and not self.sudo().pb_policy_full_time_confirmed):
            reason = _('No applicable published policy with verified employee eligibility.')
            result['errors'] = dict.fromkeys(keys, reason)
            return result
        result['policy_id'] = policy.id
        for category, prefix in (('annual', 'annual'), ('wellness', 'sick')):
            rule = policy._rule_for(category)
            entitlement_key, balance_key = prefix + '_entitlement', prefix + '_balance'
            if not rule or rule.review_reason:
                reason = rule.review_reason if rule else _('No published rule for this category.')
                result['errors'].update({entitlement_key: reason, balance_key: reason})
                continue
            quantity = policy.annual_days if category == 'annual' else rule.quantity
            if quantity > 0:
                result[entitlement_key] = quantity
            else:
                result['errors'][entitlement_key] = _('This policy has no numerical annual cap for this category.')
            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', self.id), ('holiday_status_id.pb_policy_category', '=', category),
                ('state', '=', 'validate'), ('date_from', '<=', on_date),
                '|', ('date_to', '=', False), ('date_to', '>=', on_date)])
            leave_types = allocations.holiday_status_id
            if not allocations:
                settled = self.env['pb.leave.policy.settlement'].sudo().search_count([
                    ('employee_id', '=', self.id), ('leave_type_id.pb_policy_category', '=', category),
                    ('closed_on', '<=', on_date)])
                if settled:
                    result[balance_key] = 0.0
                    continue
            if len(leave_types) != 1 or leave_types.request_unit == 'hour':
                result['errors'][balance_key] = _('A single reconciled native day-based allocated leave type is required.')
                continue
            consumed = self._get_consumed_leaves(leave_types, target_date=on_date, ignore_future=True)[0]
            native = consumed.get(self, {}).get(leave_types, {})
            if any(allocation not in native for allocation in allocations):
                result['errors'][balance_key] = _('Native allocation balance is unavailable; review the allocation state.')
                continue
            result[balance_key] = sum(native[a].get('remaining_leaves', 0) for a in allocations)
            result['allocation_ids'].extend(allocations.ids)
        return result


class LeavePolicyType(models.Model):
    _inherit = 'hr.leave.type'
    pb_policy_category = fields.Selection(CATEGORIES, string='Policy category')
    pb_policy_country_id = fields.Many2one('res.country', string='Policy employment country',
        help='Absence policy country, independent of nationality and the legal company address.')
    pb_policy_code = fields.Char(string='Policy type reference', index=True, copy=False)
    _policy_code_unique = models.Constraint('unique(pb_policy_code)', 'A policy type reference already exists.')
    pb_pay_treatment = fields.Selection(TREATMENTS, default='unconfigured', required=True, string='Payroll treatment')
    pb_paid_fraction = fields.Float(default=1, string='Paid entitlement fraction')
    pb_pay_funding = fields.Selection(FUNDING, default='unconfigured', required=True, string='Pay funding')
    pb_employer_paid_fraction = fields.Float(default=0, string='Employer fraction (mixed funding)')

    @api.constrains('pb_pay_treatment', 'pb_paid_fraction', 'pb_pay_funding', 'pb_employer_paid_fraction')
    def _check_explicit_pay(self):
        for row in self:
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in (row.pb_paid_fraction, row.pb_employer_paid_fraction)):
                raise ValidationError(_('Leave paid fractions must be between zero and one.'))
            if row.pb_pay_treatment != 'unconfigured' and row.pb_pay_funding != 'unconfigured':
                info = _classification(row.pb_pay_treatment, row.pb_paid_fraction, row.pb_pay_funding, row.pb_employer_paid_fraction)
                if info['error']:
                    raise ValidationError(info['error'])


class LeavePolicyRequest(models.Model):
    _inherit = 'hr.leave'

    pb_policy_rule_id = fields.Many2one('pb.leave.policy.rule', readonly=True, copy=False, ondelete='restrict')
    pb_policy_event_date = fields.Date(string='Birth / adoption / event date')
    pb_policy_event_key = fields.Char(string='Event reference', help='Stable HR event identifier shared by all blocks of the same event.')
    pb_policy_expected_delivery = fields.Date(string='Expected delivery date')
    pb_policy_child_birth_date = fields.Date(string='Child date of birth')
    pb_policy_child_country_id = fields.Many2one('res.country', string='Child citizenship')
    pb_policy_surviving_children = fields.Integer(string='Surviving children before this birth',
        help='HR verifies the count before this birth: zero or one gives 26 weeks in India; two or more gives 12 weeks.')
    pb_policy_children_in_birth = fields.Integer(default=1, string='Children in this birth')
    pb_policy_employment_start = fields.Date(string='Verified employment episode start')
    pb_policy_eligibility_verified = fields.Boolean(groups=MANAGER, string='Event eligibility verified by HR')
    pb_policy_evidence_ref = fields.Char(string='Manager email and leave form evidence')
    pb_policy_medical_ref = fields.Char(string='Restricted medical evidence reference', groups=MANAGER)
    pb_policy_exception_ref = fields.Char(string='HR Head / CEO exception reference', groups=MANAGER)
    pb_policy_exception_authority = fields.Selection([('hr_head', 'HR Head'), ('ceo', 'CEO')], groups=MANAGER)
    pb_policy_exception_by = fields.Many2one('res.users', readonly=True, copy=False, groups=MANAGER)
    pb_policy_exception_at = fields.Datetime(readonly=True, copy=False, groups=MANAGER)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('pb_policy_rule_id'):
                raise UserError(_('Policy rules are selected from the employee assignment, not entered manually.'))
            if vals.get('pb_policy_exception_by') or vals.get('pb_policy_exception_at'):
                raise AccessError(_('Use the policy exception action to record approval evidence.'))
            employee = self.env['hr.employee'].browse(vals.get('employee_id') or self.env.user.employee_id.id)
            leave_type = self.env['hr.leave.type'].browse(vals.get('holiday_status_id'))
            start = fields.Date.to_date(vals.get('request_date_from') or vals.get('date_from'))
            if employee and leave_type and start:
                edition = employee._pb_policy_for_date(start)
                rule = edition._rule_for(leave_type.pb_policy_category) if edition else False
                if rule:
                    vals['pb_policy_rule_id'] = rule.id
        leaves = super().create(vals_list)
        leaves.filtered(lambda leave: leave.state in ('validate1', 'validate'))._pb_validate_policy()
        return leaves

    def write(self, vals):
        if 'pb_policy_rule_id' in vals or 'pb_policy_exception_by' in vals or 'pb_policy_exception_at' in vals:
            raise AccessError(_('Policy references and exception audit fields cannot be changed directly.'))
        if 'state' in vals:
            for employee_id, type_id in sorted({(l.employee_id.id, l.holiday_status_id.id) for l in self if l.pb_policy_rule_id}):
                self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                    ['pb.leave.balance:%s:%s' % (employee_id, type_id)])
            for leave in self.filtered('pb_policy_rule_id'):
                if self.env['pb.leave.policy.settlement'].sudo().search_count([
                        ('employee_id', '=', leave.employee_id.id), ('leave_type_id', '=', leave.holiday_status_id.id),
                        ('closed_on', '>=', leave.request_date_from)]):
                    raise UserError(_('Leave used by a completed terminal settlement cannot be changed without a reviewed reversal.'))
        substantive = {'request_date_from', 'request_date_to', 'date_from', 'date_to', 'holiday_status_id', 'employee_id',
                       'pb_policy_event_date', 'pb_policy_event_key', 'pb_policy_child_birth_date',
                       'pb_policy_surviving_children', 'pb_policy_children_in_birth', 'pb_policy_expected_delivery',
                       'pb_policy_child_country_id', 'pb_policy_employment_start', 'pb_policy_eligibility_verified',
                       'pb_policy_medical_ref', 'pb_policy_evidence_ref', 'pb_policy_exception_ref',
                       'pb_policy_exception_authority'}
        if set(vals) & substantive and self.filtered(lambda l: l.state == 'validate' and l.pb_policy_rule_id):
            raise UserError(_('Return the approved policy leave to approval before changing its facts. Payroll will require review.'))
        if vals.get('state') in ('validate1', 'validate'):
            if set(vals) & substantive:
                raise UserError(_('Save the request facts before submitting the approval transition.'))
            self._pb_validate_policy()
        result = super().write(vals)
        if set(vals) & substantive:
            for leave in self:
                edition = leave.employee_id._pb_policy_for_date(leave.request_date_from)
                rule = edition._rule_for(leave.holiday_status_id.pb_policy_category) if edition else False
                super(LeavePolicyRequest, leave).write({'pb_policy_rule_id': rule.id if rule else False,
                                                       'pb_policy_exception_by': False, 'pb_policy_exception_at': False})
        return result

    def action_record_policy_exception(self):
        _manager(self.env)
        for leave in self:
            if not leave.pb_policy_exception_ref or not leave.pb_policy_exception_authority:
                raise UserError(_('Record the HR Head / CEO authority and evidence reference first.'))
            super(LeavePolicyRequest, leave).write({'pb_policy_exception_by': self.env.uid,
                                                   'pb_policy_exception_at': fields.Datetime.now()})
        return True

    def _pb_payroll_classification(self):
        self.ensure_one()
        rule = self.pb_policy_rule_id
        if rule:
            result = rule._pay_classification()
            if rule.review_reason and not self.sudo().pb_policy_exception_by:
                result['error'] = rule.review_reason
            return result
        leave_type = self.holiday_status_id
        return _classification(leave_type.pb_pay_treatment, leave_type.pb_paid_fraction,
                               leave_type.pb_pay_funding, leave_type.pb_employer_paid_fraction)

    def _pb_validate_policy(self):
        for leave in self:
            rule = leave.pb_policy_rule_id
            if not rule:
                edition = leave.employee_id._pb_policy_for_date(leave.request_date_from)
                if edition:
                    raise UserError(_('This leave type has no applicable policy rule. Ask HR to map its category.'))
                continue
            edition, facts = rule.edition_id, leave.sudo()
            if (leave.holiday_status_id.pb_policy_country_id
                    and leave.holiday_status_id.pb_policy_country_id != edition.country_id):
                raise UserError(_('Choose the leave type for the employee employment country.'))
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                ['pb.leave.balance:%s:%s' % (leave.employee_id.id, leave.holiday_status_id.id)])
            if self.env['pb.leave.policy.settlement'].sudo().search_count([
                    ('employee_id', '=', leave.employee_id.id), ('leave_type_id', '=', leave.holiday_status_id.id),
                    ('closed_on', '>=', date(leave.request_date_from.year, 1, 1))]):
                raise UserError(_('This annual leave employment episode is closed by payroll settlement. HR must review a new employment episode before approving leave.'))
            # Serialize category caps and event/block limits across concurrent approvals.
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                ['pb.leave.approval:%s:%s' % (leave.employee_id.id, rule.category)])
            exception = bool(facts.pb_policy_exception_by and facts.pb_policy_exception_ref)
            if edition.full_time_only and not leave.employee_id.sudo().pb_policy_full_time_confirmed:
                raise UserError(_('HR must verify full-time policy eligibility.'))
            if edition.workflow_mode == 'email_form' and not leave.pb_policy_evidence_ref:
                raise UserError(_('Record the manager email and completed leave form evidence before approval.'))
            if rule.review_reason and not exception:
                raise UserError(_('HR interpretation is required: %s', rule.review_reason))
            calendar_days = (leave.request_date_to - leave.request_date_from).days + 1
            units = calendar_days if rule.counting == 'calendar' else leave.number_of_days
            if rule.max_request_days and units > rule.max_request_days and not exception:
                raise UserError(_('The annual leave maximum is ten working days; record an authorized emergency exception.'))
            if rule.medical_after_days and calendar_days > rule.medical_after_days and not facts.pb_policy_medical_ref:
                raise UserError(_('A medical certificate reference is required for this consecutive absence.'))
            if rule.category == 'wellness' and edition.country_id.code == 'ID' and not facts.pb_policy_medical_ref:
                raise UserError(_('Indonesia wellness absence requires a medical certificate.'))
            if rule.category == 'miscarriage' and not facts.pb_policy_medical_ref:
                raise UserError(_('Miscarriage leave requires supporting medical evidence.'))
            event_date = leave.pb_policy_event_date or (leave.pb_policy_expected_delivery if rule.category == 'maternity' else False)
            if rule.event_evidence_required and (not facts.pb_policy_eligibility_verified or not leave.pb_policy_event_key or not event_date):
                raise UserError(_('HR must verify event eligibility and record its reference and date.'))
            related = self.search([
                ('id', '!=', leave.id), ('employee_id', '=', leave.employee_id.id),
                ('pb_policy_rule_id.category', '=', rule.category), ('state', 'in', ('validate1', 'validate'))])
            if rule.limit_period == 'year':
                if leave.request_date_from.year != leave.request_date_to.year:
                    raise UserError(_('Split annual-limit leave at the year boundary so each year is assessed correctly.'))
                related = related.filtered(lambda l: l.request_date_from.year == leave.request_date_from.year)
            else:
                related = related.filtered(lambda l: l.pb_policy_event_key == leave.pb_policy_event_key)
            total = units + sum((l.request_date_to - l.request_date_from).days + 1
                                if rule.counting == 'calendar' else l.number_of_days for l in related)
            if rule.category not in ('annual', 'maternity') and rule.quantity and total > rule.quantity and not exception:
                raise UserError(_('The request exceeds the policy entitlement for this year or event.'))
            if rule.category == 'annual' and leave.number_of_days >= 10 and not leave.pb_policy_evidence_ref:
                raise UserError(_('Advance manager notice is required for ten days of annual leave.'))
            if rule.category == 'paternity':
                if leave.employee_id.sudo().sex != 'male' and not exception:
                    raise UserError(_('The supplied paternity policy specifies eligible male employees. HR must review an exception.'))
                if leave.request_date_from < leave.pb_policy_event_date or leave.request_date_to >= leave.pb_policy_event_date + relativedelta(years=1):
                    raise UserError(_('Paternity leave must be taken within one year after birth or adoption.'))
                if len(related) >= 2 and not exception:
                    raise UserError(_('Paternity leave permits at most two blocks per event.'))
                all_events = self.search([('employee_id', '=', leave.employee_id.id),
                                         ('pb_policy_rule_id.category', '=', 'paternity'),
                                         ('state', 'in', ('validate1', 'validate'))]).mapped('pb_policy_event_key')
                if len(set(filter(None, all_events + [leave.pb_policy_event_key]))) > 2 and not exception:
                    raise UserError(_('The supplied policy limits paternity to two births/adoptions.'))
            if rule.category == 'adoption':
                birth = leave.pb_policy_child_birth_date
                if (leave.employee_id.sudo().sex != 'female' or not birth or not birth <= leave.pb_policy_event_date < birth + relativedelta(years=1)) and not exception:
                    raise UserError(_('Adoption policy requires an eligible woman employee adopting a child below one year.'))
            if rule.category == 'childcare':
                birth, joined = leave.pb_policy_child_birth_date, leave.pb_policy_employment_start
                if (not birth or not birth <= leave.request_date_from < birth + relativedelta(years=7)
                        or leave.pb_policy_child_country_id.code != 'SG' or not joined
                        or leave.request_date_from < joined + relativedelta(months=3)):
                    raise UserError(_('Childcare requires a Singapore-citizen child under seven and three continuous months of service.'))
            if rule.category == 'marriage' and related and not exception:
                raise UserError(_('Marriage leave may be taken once per calendar year.'))
            if rule.category == 'maternity':
                self._pb_validate_maternity(leave, related, exception)

    def _pb_validate_maternity(self, leave, related, exception):
        rule = leave.pb_policy_rule_id
        code = rule.edition_id.country_id.code
        if not leave.sudo().pb_policy_medical_ref or not leave.pb_policy_expected_delivery:
            raise UserError(_('Maternity requires medical evidence and expected delivery date.'))
        max_days = rule.quantity
        if code == 'IN':
            if leave.pb_policy_surviving_children < 0:
                raise UserError(_('Record the verified surviving-child count for the India entitlement.'))
            max_days = 182 if leave.pb_policy_surviving_children < 2 else 84
        if code == 'VN':
            if leave.pb_policy_children_in_birth < 1:
                raise UserError(_('Record the number of children in this birth.'))
            max_days = ((leave.request_date_from + relativedelta(months=6 + leave.pb_policy_children_in_birth - 1)) - leave.request_date_from).days
        elif code == 'ID':
            max_days = ((leave.request_date_from + relativedelta(months=3)) - leave.request_date_from).days
        total = (leave.request_date_to - leave.request_date_from).days + 1
        total += sum((l.request_date_to - l.request_date_from).days + 1 for l in related)
        if total > max_days and not exception:
            raise UserError(_('Additional maternity / PL use needs HR interpretation of the conflicting detailed clauses.'))
        lead_days = {'IN': 56, 'SG': 28}.get(code)
        earliest = leave.pb_policy_expected_delivery - (timedelta(days=lead_days) if lead_days else relativedelta(months=2 if code == 'VN' else 1))
        if code == 'ID':
            # 1.5 calendar months is not a universal 45-day conversion.
            if not exception:
                raise UserError(_('Indonesia 1.5-month pre/post-birth split requires a documented HR date interpretation.'))
        elif leave.request_date_from < earliest and not exception:
            raise UserError(_('The maternity request begins earlier than the country policy permits.'))


class LeavePolicyOperation(models.TransientModel):
    _name = 'pb.leave.policy.operation'
    _description = 'Post policy entitlement or assess exit'

    edition_id = fields.Many2one('pb.leave.policy.edition', required=True,
                                 domain="[('state', '=', 'published')]")
    employee_id = fields.Many2one('hr.employee', required=True)
    leave_type_id = fields.Many2one('hr.leave.type', required=True,
                                    domain="[('pb_policy_category', '=', 'annual')]")
    operation = fields.Selection([('annual', 'Annual credit'), ('carry', 'Year-end rollover'),
                                   ('opening', 'Reviewed opening balance'), ('exit', 'Exit assessment')],
                                  default='annual', required=True)
    on_date = fields.Date(required=True, default=fields.Date.context_today)
    employment_start = fields.Date()
    review_reference = fields.Char()
    reviewed_quantity = fields.Boolean(string='Use HR-reviewed proration')
    reviewed_days = fields.Float()
    reviewed_months = fields.Float()
    available_days = fields.Float(string='Reviewed available balance at cutover')
    carried_days = fields.Float(string='Reviewed carried portion')
    taken_year_to_date = fields.Float(string='Approved leave used before cutover')
    gross_salary = fields.Float(string='Verified gross monthly salary')
    result = fields.Text(readonly=True)

    def action_execute(self):
        _manager(self.env)
        self.ensure_one()
        policy = self.edition_id
        if self.operation == 'annual':
            posting = policy.post_annual_credit(self.employee_id.id, self.leave_type_id.id,
                self.on_date.year, self.employment_start,
                self.reviewed_days if self.reviewed_quantity else None, self.review_reference)
        elif self.operation == 'carry':
            if (self.on_date.month, self.on_date.day) != (1, 1):
                raise UserError(_('Rollover date must be 1 January.'))
            posting = policy.post_rollover(self.employee_id.id, self.leave_type_id.id,
                                           self.on_date.year, self.review_reference)
        elif self.operation == 'opening':
            posting = policy.post_opening_balance(self.employee_id.id, self.leave_type_id.id, self.on_date,
                self.available_days, self.carried_days, self.taken_year_to_date, self.review_reference)
        else:
            import json
            result = policy.assess_exit(self.employee_id.id, self.leave_type_id.id, self.on_date,
                self.employment_start, self.gross_salary,
                self.reviewed_months if self.reviewed_quantity else None, self.review_reference)
            self.result = json.dumps(result, indent=2)
            return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                    'view_mode': 'form', 'target': 'new'}
        return {'type': 'ir.actions.act_window', 'res_model': posting._name, 'res_id': posting.id,
                'view_mode': 'form', 'target': 'current'}
