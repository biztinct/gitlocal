"""Explicit application-data payroll, with signed coverage and frozen inputs.

This is opt-in. Merely installing it never changes a scheme or a completed run.
Operational records are read, never approved, repaired or created by payroll.
"""
import hashlib
import json
import math
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from . import value_kind_classifier


_SEAL = object()
_SEAL_KEY = 'pb_application_payroll_seal'
_CHANNELS = frozenset(('leave', 'overtime', 'timesheets', 'adjustments'))
_READY = ('resolved', 'zero_confirmed')


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _stamp(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _fact(value=None, status='resolved', reason='', sources=None, **evidence):
    return {'value': value, 'status': status, 'reason': reason,
            'source_ids': sources or [], 'evidence': evidence}


def _date(value):
    return fields.Date.to_date(value)


def _application_branch(formula, mode_references):
    """Select only an explicit outer IF(application-mode=1, app, legacy).

    Other conditions stay conservative. Strings and nested function commas
    are respected; this is selection, never evaluation of user code.
    """
    text = (formula or '').strip().lstrip('=').strip()
    match = re.fullmatch(r'IF\s*\((.*)\)', text, flags=re.I | re.S)
    if not match:
        return None
    parts, start, depth, quoted, index = [], 0, 0, False, 0
    body = match.group(1)
    while index < len(body):
        char = body[index]
        if char == '"':
            if quoted and index + 1 < len(body) and body[index + 1] == '"':
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(body[start:index]); start = index + 1
        index += 1
    parts.append(body[start:])
    if len(parts) != 3 or quoted or depth != 0:
        return None
    condition = re.sub(r'\s|\$', '', parts[0]).upper()
    if any(re.fullmatch(re.escape(ref) + r'(?:\d+)?=1', condition)
           for ref in mode_references if ref):
        return parts[1]
    return None


class ApplicationFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    application_data_enabled = fields.Boolean(
        string='Allow payroll from application records', default=False, tracking=True)
    application_effective_from = fields.Date(string='Application payroll effective from', tracking=True)
    payroll_basis = fields.Selection([
        ('contractual', 'Contractual paid days'),
        ('timesheet', 'Approved timesheets reconciled to attendance')],
        default='contractual', required=True, tracking=True)
    standard_day_basis = fields.Selection([
        ('calendar', 'Work calendar'), ('fixed', 'Fixed standard days')],
        default='calendar', required=True, tracking=True)
    fixed_standard_days = fields.Float(string='Fixed standard days', digits=(16, 4), tracking=True)

    @api.constrains('standard_day_basis', 'fixed_standard_days', 'application_data_enabled',
                    'application_effective_from')
    def _check_application_basis(self):
        for config in self:
            if config.application_data_enabled and not config.application_effective_from:
                raise ValidationError(_('Set the effective date before enabling application payroll.'))
            if config.standard_day_basis == 'fixed' and config.fixed_standard_days <= 0:
                raise ValidationError(_('Fixed standard days must be greater than zero.'))

    def _application_source_catalogue(self):
        """Extension seam: domain modules add typed sources, not arbitrary eval."""
        labels = {
            'application.mode': ('Use application payroll inputs', 'boolean'),
            'period.standard_days': ('Standard days', 'days'),
            'period.paid_day_equivalents': ('Paid day equivalents', 'days'),
            'period.unpaid_day_equivalents': ('Unpaid day equivalents', 'days'),
            'period.nonpayable_day_equivalents': ('Standard days not payable', 'days'),
            'period.paid_leave_days': ('Fully paid leave taken', 'days'),
            'period.partially_paid_leave_days': ('Partially paid leave taken', 'days'),
            'period.regular_work_hours': ('Approved regular hours', 'hours'),
            'period.regular_work_days': ('Approved regular day equivalents', 'days'),
            'period.public_holiday_days': ('Paid public holiday days', 'days'),
            'period.approved_bonus_hours': ('Approved overtime bonus hours', 'hours'),
        }
        for kind in ('weekday', 'weekend', 'holiday', 'night', 'extended'):
            labels['period.ot.%s.approved_hours' % kind] = ('Approved %s overtime' % kind, 'hours')
        return {key: {'label': label, 'unit': unit} for key, (label, unit) in labels.items()}

    def _application_domain_values(self, employee, contract, date_from, date_to):
        return {}

    def _application_require_access(self, certify=False):
        # The wizard deliberately reads scheme metadata with sudo. That must
        # never turn an officer into a person who may certify completeness.
        real = self.sudo(False)
        user = real.env.user
        groups = ('hr.group_hr_manager', 'om_hr_payroll.group_hr_payroll_manager',
                  'pb_hr_payroll_formula.group_formula_manager',
                  'pb_hr_payroll_base.group_payroll_base_manager')
        if not certify:
            groups += ('om_hr_payroll.group_hr_payroll_user', 'pb_hr_payroll_base.group_payroll_base_officer')
        if not (user._is_admin() or any(user.has_group(g) for g in groups)):
            raise AccessError(_('Only an HR or payroll manager can review and certify application payroll.'))
        if self and any(c.company_id and c.company_id not in real.env.companies for c in self):
            raise AccessError(_('The payroll scheme belongs to another company.'))

    def _application_settings_stamp(self):
        self.ensure_one()
        return _stamp({
            'scheme': self.id, 'company': self.company_id.id,
            'enabled': self.application_data_enabled,
            'effective': self.application_effective_from,
            'basis': self.payroll_basis, 'standard': self.standard_day_basis,
            'fixed': self.fixed_standard_days,
            'content': self._content_hash(),
            'bindings': [(r.id, r.application_source_key, r.application_source_required,
                          r.is_required, r.column_type, r.write_date) for r in self.rule_ids],
        })

    def _application_contract(self, employee, start, end):
        contracts = self.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id), ('company_id', '=', employee.company_id.id),
            ('date_start', '<=', end), '|', ('date_end', '=', False), ('date_end', '>=', start),
            ('state', 'not in', ['draft', 'cancel'])], order='date_start,id')
        # Multi-contract/salary slices need a reviewed earnings split, never arbitrary first.
        return contracts[:1], len(contracts) != 1

    def _application_time_values(self, employee, contract, start, end, certification):
        self.ensure_one()
        result = {}
        calendar = contract.resource_calendar_id or employee.resource_calendar_id
        if not calendar:
            return {k: _fact(status='missing', reason='No employee work calendar.')
                    for k in self._application_source_catalogue() if k.startswith('period.')}
        tz = pytz.timezone(calendar.tz or 'UTC')
        bounds = lambda d: (tz.localize(datetime.combine(d, time.min)),
                            tz.localize(datetime.combine(d + timedelta(days=1), time.min)))
        first, last = bounds(start)[0], bounds(end)[1]
        utc_start = first.astimezone(pytz.utc).replace(tzinfo=None)
        utc_end = last.astimezone(pytz.utc).replace(tzinfo=None)
        days, cursor = {}, start
        while cursor <= end:
            low, high = bounds(cursor)
            hours = calendar.get_work_hours_count(low, high, compute_leaves=False)
            nonholiday = calendar.get_work_hours_count(low, high, compute_leaves=True)
            eligible = contract.date_start <= cursor and (not contract.date_end or cursor <= contract.date_end)
            days[cursor] = {'hours': hours, 'holiday': max(0., hours - nonholiday),
                            'eligible': eligible, 'paid': 0., 'partial': 0., 'loss': 0.,
                            'leave_hours': 0., 'regular': 0.}
            cursor += timedelta(days=1)
        schedule_days = sum(1. for d in days.values() if d['hours'] > 0)
        standard = self.fixed_standard_days if self.standard_day_basis == 'fixed' else schedule_days
        factor = standard / schedule_days if schedule_days else 0.
        calendar_sources = [['resource.calendar', calendar.id, str(calendar.write_date)]]
        # Calendar event content is reflected in daily hours/holiday values below.
        result['period.standard_days'] = _fact(standard, sources=calendar_sources,
            basis=self.standard_day_basis, calendar_days=schedule_days)
        if standard <= 0 or schedule_days <= 0:
            result['period.standard_days'] = _fact(status='missing', reason='The period has no positive calendar/divisor days.')

        channels = (certification or {}).get('channels') or {}
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id), ('date_from', '<', utc_end),
            ('date_to', '>', utc_start), ('state', 'in', ['confirm', 'validate1', 'validate'])])
        leave_sources, leave_errors = [], []
        for leave in leaves:
            leave_sources.append(['hr.leave', leave.id, str(leave.write_date), leave.state])
            if leave.state != 'validate':
                leave_errors.append('Time off %s is awaiting approval.' % leave.id)
                continue
            classification = (leave._pb_payroll_classification()
                              if hasattr(leave, '_pb_payroll_classification')
                              else {'error': 'Leave pay treatment is not configured.'})
            if classification.get('error'):
                leave_errors.append(str(classification['error']))
                continue
            fraction = classification.get('employer_fraction', classification.get('fraction'))
            if fraction is None or not 0 <= fraction <= 1:
                leave_errors.append('Time off %s has no explicit employer-paid fraction.' % leave.id)
                continue
            leave_sources[-1].append(classification)
            for day, data in days.items():
                if not data['eligible'] or data['hours'] <= 0:
                    continue
                low, high = bounds(day)
                left = max(low.astimezone(pytz.utc), pytz.utc.localize(leave.date_from))
                right = min(high.astimezone(pytz.utc), pytz.utc.localize(leave.date_to))
                if left >= right:
                    continue
                # Public holidays already have their own paid credit; never debit leave twice.
                hours = calendar.get_work_hours_count(left, right, compute_leaves=True)
                data['leave_hours'] += hours
                data['loss'] += hours / data['hours'] * (1. - fraction)
                if fraction == 1:
                    data['paid'] += hours / data['hours']
                elif fraction > 0:
                    data['partial'] += hours / data['hours']
                if data['leave_hours'] + data['holiday'] > data['hours'] + .01:
                    leave_errors.append('Overlapping time-off hours on %s.' % day)
        leave_status = ('conflict' if leave_errors else 'resolved' if channels.get('leave') else 'missing')
        leave_reason = '; '.join(leave_errors) or ('' if channels.get('leave') else 'HR has not certified this period\'s leave completeness.')
        facts_stamp = {'days': {str(k): v for k, v in days.items()}, 'records': leave_sources}
        for key, prop in [('period.paid_leave_days', 'paid'), ('period.partially_paid_leave_days', 'partial'),
                          ('period.unpaid_day_equivalents', 'loss')]:
            result[key] = _fact(round(sum(d[prop] for d in days.values()) * factor, 6),
                                leave_status, leave_reason, leave_sources, facts=facts_stamp)
        holiday = sum(d['holiday'] / d['hours'] for d in days.values() if d['eligible'] and d['hours'])
        result['period.public_holiday_days'] = _fact(round(holiday * factor, 6), sources=calendar_sources,
                                                     daily_holidays={str(k): v['holiday'] for k, v in days.items()})

        packet_sources, time_errors, used_dates, ot_seen = [], [], set(), set()
        Request = self.env.get('hr.overtime.request')
        supported = dict(Request._fields['overtime_type']._description_selection(self.env)) if Request is not None else {}
        overtime = dict.fromkeys((kind for kind in ('weekday', 'weekend', 'holiday', 'night', 'extended') if kind in supported), 0.)
        bonus = 0.
        Packet = self.env.get('pb.timesheet.packet')
        packets = Packet.sudo().search([('employee_id', '=', employee.id), ('state', '=', 'approved'),
                    ('week_start', '<=', end), ('week_end', '>=', start)]) if Packet is not None else []
        for packet in packets:
            packet_sources.append(['pb.timesheet.packet', packet.id, str(packet.write_date), packet.approved_hash])
            if not packet.approved_hash or packet._live_stamp() != packet.approved_hash:
                time_errors.append('Approved week %s changed after sign-off.' % packet.week_start)
                continue
            for cell in packet.days():
                day = _date(cell.get('date'))
                if not day or day not in days or not days[day]['eligible']:
                    continue
                if day in used_dates:
                    time_errors.append('Duplicate approved day %s.' % day)
                    continue
                used_dates.add(day)
                data = days[day]
                # The approved daily snapshot, not weekly total: exact period clipping.
                regular = float(cell.get('reg') or 0.)
                attendance_ids = cell.get('attendance_ids') or []
                attendance = self.env['hr.attendance'].sudo().browse(attendance_ids).exists()
                if any(a.employee_id != employee or not a.check_out for a in attendance):
                    time_errors.append('Unreconciled attendance on %s.' % day)
                live = sum((a.check_out - a.check_in).total_seconds() / 3600.
                           for a in attendance if a.check_out and a.check_in)
                if abs(live - regular) > .02:
                    time_errors.append('Timesheet and attendance differ on %s.' % day)
                if any(pytz.utc.localize(a.check_in).astimezone(tz).date() != day
                       or (a.check_out and pytz.utc.localize(a.check_out - timedelta(microseconds=1)).astimezone(tz).date() != day)
                       for a in attendance if a.check_in):
                    time_errors.append('Attendance crossing local work dates needs an approved daily split on %s.' % day)
                exclusive_ot = 0.
                for kind, item in (cell.get('ot') or {}).items():
                    rid = item.get('id')
                    if not rid:
                        time_errors.append('Overtime entry has no approved source on %s.' % day)
                        continue
                    if rid in ot_seen:
                        time_errors.append('Duplicate overtime request %s in approved daily entries.' % rid)
                        continue
                    ot_seen.add(rid)
                    # The packet is captured before its approval applies the
                    # OT decisions. Verify the approved request against that
                    # frozen entry, rather than trusting its old state label.
                    request = self.env['hr.overtime.request'].sudo().browse(rid).exists()
                    if (not request or request.employee_id != employee or request.date != day
                            or request.overtime_type != kind or request.state != 'approved'
                            or abs(request.approved_hours + request.bonus_hours - float(item.get('hours') or 0.)) > .02):
                        time_errors.append('Overtime %s no longer matches its approved daily entry.' % rid)
                        continue
                    packet_sources.append(['hr.overtime.request', request.id, str(request.write_date)])
                    if kind not in overtime:
                        time_errors.append('Unsupported overtime classification %s.' % kind)
                        continue
                    overtime[kind] += request.approved_hours
                    bonus += request.bonus_hours
                    # Night is a premium over hours already worked, not an
                    # additional block to deduct from the ordinary duration.
                    if kind != 'night':
                        exclusive_ot += request.approved_hours + request.bonus_hours
                sources = {getattr(a, 'pb_entry_source', False) or 'device' for a in attendance}
                if len(sources) > 1:
                    time_errors.append('Mixed grid/device attendance needs a reviewed daily split on %s.' % day)
                elif sources == {'device'}:
                    # Packet reg is the signed raw punch span. Actual paid
                    # attendance excludes configured lunch; approved OT is
                    # separate from ordinary time on device punches.
                    regular = sum(a.worked_hours for a in attendance) - exclusive_ot
                if regular < -.02 or regular + data['leave_hours'] + data['holiday'] > data['hours'] + .02:
                    time_errors.append('Regular work, leave or holiday overlap/exceed scheduled hours on %s.' % day)
                data['regular'] = max(0., regular)
        # Even a certified zero cannot conceal attendance omitted from approved packets.
        Attendance = self.env.get('hr.attendance')
        unmatched = Attendance.sudo().search([('employee_id', '=', employee.id),
            ('check_in', '<', utc_end), '|', ('check_out', '=', False), ('check_out', '>', utc_start)]) if Attendance is not None else []
        att_ids = {aid for packet in packets for cell in packet.days()
                   if _date(cell.get('date')) in days for aid in (cell.get('attendance_ids') or [])}
        if any(a.id not in att_ids for a in unmatched):
            time_errors.append('Attendance exists outside approved daily timesheets.')
        if self.payroll_basis == 'timesheet' and Request is not None:
            current_ot = Request.sudo().search([('employee_id', '=', employee.id), ('date', '>=', start),
                ('date', '<=', end), ('state', 'in', ['draft', 'submitted', 'approved'])])
            for request in current_ot:
                if hasattr(request, '_application_policy_errors'):
                    time_errors.extend(request._application_policy_errors())
                if request.state != 'approved' or request.id not in ot_seen:
                    time_errors.append('Overtime %s is pending or missing from approved daily timesheets.' % request.id)
        time_status = ('conflict' if time_errors else 'resolved' if Packet is not None and channels.get('timesheets') else 'missing')
        time_reason = '; '.join(time_errors) or ('' if time_status == 'resolved' else 'Approved timesheet completeness is not certified or unavailable.')
        regular_hours = sum(d['regular'] for d in days.values())
        regular_days = sum(d['regular'] / d['hours'] for d in days.values() if d['hours'])
        for key, value in [('period.regular_work_hours', regular_hours), ('period.regular_work_days', regular_days * factor)]:
            result[key] = _fact(round(value, 6), time_status, time_reason, packet_sources,
                                attendance_ids=sorted(a.id for a in unmatched))

        # Contractual payroll may use approved OT requests without requiring regular timesheets.
        if self.payroll_basis == 'contractual':
            Request = self.env.get('hr.overtime.request')
            requests = Request.sudo().search([('employee_id', '=', employee.id), ('date', '>=', start),
                ('date', '<=', end), ('state', 'in', ['draft', 'submitted', 'approved'])]) if Request is not None else []
            ot_errors, ot_sources = [], []
            overtime = dict.fromkeys(overtime, 0.); bonus = 0.
            for request in requests:
                ot_sources.append(['hr.overtime.request', request.id, str(request.write_date), request.state])
                if hasattr(request, '_application_policy_errors'):
                    ot_errors.extend(request._application_policy_errors())
                if not days[request.date]['eligible']:
                    ot_errors.append('Overtime %s falls outside the effective contract.' % request.id)
                elif request.state != 'approved':
                    ot_errors.append('Overtime %s is awaiting approval.' % request.id)
                elif request.overtime_type not in overtime:
                    ot_errors.append('Unsupported overtime classification %s.' % request.overtime_type)
                else:
                    overtime[request.overtime_type] += request.approved_hours
                    bonus += request.bonus_hours
            ot_status = 'conflict' if ot_errors else 'resolved' if Request is not None and channels.get('overtime') else 'missing'
            ot_reason = '; '.join(ot_errors) or ('' if ot_status == 'resolved' else 'Overtime completeness is not certified or unavailable.')
        else:
            ot_sources, ot_status, ot_reason = packet_sources, time_status, time_reason
            if not channels.get('overtime') and ot_status != 'conflict':
                ot_status, ot_reason = 'missing', 'Overtime completeness is not certified.'
        for kind, value in overtime.items():
            result['period.ot.%s.approved_hours' % kind] = _fact(round(value, 6), ot_status, ot_reason, ot_sources)
        result['period.approved_bonus_hours'] = _fact(round(bonus, 6), ot_status, ot_reason, ot_sources)
        for kind in ('weekday', 'weekend', 'holiday', 'night', 'extended'):
            if kind not in overtime:
                result['period.ot.%s.approved_hours' % kind] = _fact(status='missing', reason='This overtime classification is not installed; it is not inferred from other hours.')
        eligible = sum(1. for d in days.values() if d['eligible'] and d['hours'])
        loss = sum(d['loss'] for d in days.values())
        if self.payroll_basis == 'contractual':
            paid, status, reason = (eligible - loss) * factor, leave_status, leave_reason
        else:
            # Partial leave contribution is leave-duration minus its lost fraction.
            paid = (regular_days + sum(d['leave_hours'] / d['hours'] - d['loss']
                    for d in days.values() if d['hours']) + holiday) * factor
            status = 'conflict' if 'conflict' in (time_status, leave_status) else 'resolved' if time_status == leave_status == 'resolved' else 'missing'
            reason = '; '.join(v for v in (time_reason, leave_reason) if v)
        if paid < -.001 or paid > standard + .001:
            status, reason = 'conflict', 'Paid day equivalents are outside the standard-day range.'
        result['period.paid_day_equivalents'] = _fact(round(paid, 6), status, reason,
            leave_sources + (packet_sources if self.payroll_basis == 'timesheet' else []),
            basis=self.payroll_basis, eligible_days=eligible, normalization=factor,
            daily_facts={str(k): v for k, v in days.items()})
        result['period.nonpayable_day_equivalents'] = _fact(round(standard - paid, 6), status, reason,
            result['period.paid_day_equivalents']['source_ids'],
            standard_days=standard, paid_day_equivalents=paid,
            meaning='Includes employment-slice gaps and approved unpaid/partial-pay losses; not an unpaid-leave report.')
        return result

    def _application_employee_inputs(self, employee, start, end, certification):
        self.ensure_one()
        contract, ambiguous = self._application_contract(employee, start, end)
        blockers = []
        for channel in ('leave', 'overtime', 'adjustments'):
            if not (certification or {}).get('channels', {}).get(channel):
                blockers.append({'code': '', 'key': channel,
                    'reason': 'A payroll manager must certify this period\'s %s records are complete.' % channel})
        if self.use_proration:
            blockers.append({'code': '', 'key': '', 'reason': 'Salary-history proration requires a reviewed allocation-aware application provider.'})
        if ambiguous:
            blockers.append({'code': '', 'key': '', 'reason': 'Exactly one effective contract is required; split overlapping or changed contracts explicitly.'})
        if 'pb.work.segment' in self.env:
            home, host = self.env['pb.work.segment']._segments_for(employee, start, end)
            if home or host:
                blockers.append({'code': '', 'key': '', 'reason': 'Confirmed work assignments need an explicit allocation-aware payroll provider before application payroll can run.'})
        if not self.application_data_enabled or not self.application_effective_from or start < self.application_effective_from:
            blockers.append({'code': '', 'key': '', 'reason': 'Application payroll is not enabled for this period.'})
        slip = self.env['hr.payslip'].new({'employee_id': employee.id, 'contract_id': contract.id,
                    'date_from': start, 'date_to': end, 'formula_config_id': self.id})
        provenance = {}
        values = slip.with_context(pb_application_data_mode=True)._get_formula_input_values(self, provenance=provenance) if contract else {}
        facts = self._application_time_values(employee, contract, start, end, certification) if contract else {}
        facts['application.mode'] = _fact(1, sources=[['hr.formula.config', self.id]])
        run_id = (certification or {}).get('run_id') or False
        slip_id = self.env.context.get('pb_application_payslip_id') or False
        facts.update(self.with_context(pb_application_run_id=run_id, application_run_id=run_id,
                    pb_application_payslip_id=slip_id, application_payslip_id=slip_id)
                    ._application_domain_values(employee, contract, start, end))
        catalogue = self._application_source_catalogue()
        zero_keys = set((certification or {}).get('zero_keys') or [])
        inputs = []
        # Walk only the dependency closure of pay-affecting formulas. A
        # profile/display formula must not make its HR metadata a pay blocker.
        by_reference = {}
        for rule in self.rule_ids:
            by_reference[rule.code.upper()] = rule
            by_reference[(rule.column_letter or '').upper()] = rule
        pending = list(self.rule_ids.filtered(lambda r: r.column_type == 'formula'
                       and r.column_role == 'payroll' and r.net_role != 'info'))
        modes = self.rule_ids.filtered(lambda r: r.application_source_key == 'application.mode')
        mode_refs = [v for r in modes for v in (r.code.upper(), (r.column_letter or '').upper())]
        visited, dependencies, inactive_candidates = set(), set(), set()
        while pending:
            formula = pending.pop()
            if formula.id in visited:
                continue
            visited.add(formula.id)
            branch = _application_branch(formula.excel_formula, mode_refs)
            if branch is not None:
                probe = self.env['hr.formula.rule'].new({'config_id': self.id, 'name': formula.name,
                    'code': formula.code, 'column_type': 'formula', 'excel_formula': '=' + branch})
                refs = probe.formula_dependencies or ''
                dependencies.update(r.code.upper() for r in modes)
                inactive_candidates.update(set((formula.formula_dependencies or '').split(',')) - set(refs.split(',')))
            else:
                refs = formula.formula_dependencies or ''
            for token in refs.split(','):
                target = by_reference.get(token)
                if target:
                    dependencies.add(target.code.upper())
                    if target.column_type == 'formula':
                        pending.append(target)
        # Preserve spreadsheet-required fields, while ignoring those reached
        # exclusively through the explicitly unselected legacy branch.
        inactive, inactive_pending = set(), list(inactive_candidates)
        while inactive_pending:
            target = by_reference.get(inactive_pending.pop())
            if not target or target.code.upper() in inactive:
                continue
            inactive.add(target.code.upper())
            if target.column_type == 'formula':
                inactive_pending.extend((target.formula_dependencies or '').split(','))
        inactive -= dependencies
        # Overtime is a payable event even if the scheme has never had a column
        # for its category. An informational mapping does not constitute pay.
        paid_source_keys = set(self.rule_ids.filtered(
            lambda r: r.code.upper() in dependencies or
            (r.column_type == 'input' and r.column_role == 'payroll' and r.net_role != 'info')
        ).mapped('application_source_key'))
        for key, fact in facts.items():
            if not (key.startswith('period.ot.') or key == 'period.approved_bonus_hours'):
                continue
            if fact.get('status') == 'conflict':
                blockers.append({'code': '', 'key': key, 'reason': fact.get('reason') or 'Overtime needs review.'})
            elif (fact.get('value') or 0) > 0 and key not in paid_source_keys:
                blockers.append({'code': '', 'key': key, 'reason': 'Approved overtime has no pay-affecting mapping. Configure its payment component before running payroll.'})
        for rule in self.rule_ids.filtered(lambda r: r.column_type == 'input'):
            key = (rule.application_source_key or '').strip()
            required = bool(rule.application_source_required or
                            (rule.code.upper() not in inactive and
                             (rule.is_required or rule.code.upper() in dependencies or
                              (rule.column_role == 'payroll' and rule.net_role != 'info'))))
            if key:
                # An explicit provider is authoritative even when it cannot
                # answer. Never retain a value read through an old contract
                # mapping behind a missing/ambiguous domain result.
                values.pop(rule.code, None)
                provenance.pop(rule.code, None)
                fact = dict(facts.get(key) or _fact(status='missing', reason='The mapped application provider is unavailable.'))
                if fact.get('status') == 'available': fact['status'] = 'resolved'
                if fact.get('status') == 'ambiguous': fact['status'] = 'conflict'
                if fact.get('status') == 'unsupported': fact['status'] = 'missing'
                if (fact.get('status') == 'missing' and key in zero_keys
                        and catalogue.get(key, {}).get('certification_zero_allowed')
                        and (certification or {}).get('channels', {}).get('adjustments')):
                    fact = _fact(0., 'zero_confirmed', sources=[], certification='Explicit period no-activity attestation')
            else:
                source = provenance.get(rule.code) or {}
                sourced = source.get('src') in ('employee_field', 'contract_component', 'period') and source.get('via') != 'contract_default'
                fact = _fact(values.get(rule.code) if sourced else None, 'resolved' if sourced else 'missing',
                    '' if sourced else 'No mapped application value; defaults and old spreadsheets are not coverage.',
                    sources=[['legacy_record', source]], provenance=source)
            fact.setdefault('reason', '')
            fact.setdefault('source_ids', [])
            fact.setdefault('evidence', {})
            if fact.get('status') in _READY and rule.value_kind in ('money', 'quantity', 'rate', 'integer'):
                value = fact.get('value')
                try:
                    number = float(value) if value is not None and value != '' else float('nan')
                except (TypeError, ValueError):
                    number = float('nan')
                if isinstance(value, bool) or not math.isfinite(number) or (rule.value_kind == 'integer' and not number.is_integer()):
                    fact.update(status='conflict', reason='The application value does not match the component numeric type.')
                else:
                    fact['value'] = int(number) if rule.value_kind == 'integer' else number
            if fact.get('evidence', {}).get('consumption_required'):
                fact.update(status='missing', reason='This event needs a paid-once reservation before payroll can consume it.')
            row = dict(fact, code=rule.code, label=rule.name, key=key,
                       unit=catalogue.get(key, {}).get('unit', ''), required=required,
                       source_owner=self._application_source_display(key, catalogue.get(key, {}))['owner'] if key else 'Employee or contract record')
            if fact.get('status') in _READY and fact.get('value') is not None:
                values[rule.code] = fact['value']
                if key:
                    provenance[rule.code] = {'src': 'employee_field', 'via': 'application_snapshot',
                                            'key': key, 'status': fact['status'], 'evidence': fact['evidence']}
            elif required:
                blockers.append({'code': rule.code, 'key': key, 'status': fact['status'], 'reason': fact['reason'] or 'Mapped value is missing or conflicting.'})
            inputs.append(row)
        return {'employee_id': employee.id, 'name': employee.name, 'ok': not blockers,
                'contract_id': contract.id, 'inputs': inputs, 'blockers': blockers,
                'values': values, 'provenance': provenance, 'settings_stamp': self._application_settings_stamp(),
                'period': [str(start), str(end)], 'certification': certification or {}}

    def application_preflight(self, employee_ids, date_from, date_to, certifications=None):
        self.ensure_one()
        self._application_require_access()
        self = self.sudo(False)
        if certifications:
            if not isinstance(certifications, dict):
                raise ValidationError(_('Use an explicit coverage object.'))
            channels = certifications.get('channels') or {}
            if not isinstance(channels, dict) or set(channels) - _CHANNELS or any(type(v) is not bool for v in channels.values()):
                raise ValidationError(_('Use explicit true/false coverage for supported channels.'))
            if any(channels.values()) or certifications.get('zero_keys'):
                self._application_require_access(certify=True)
        start, end = _date(date_from), _date(date_to)
        if not start or not end or end < start or (end - start).days > 366:
            raise ValidationError(_('Choose a valid payroll period of at most one year.'))
        employees = self.env['hr.employee'].browse(list(set(int(v) for v in employee_ids))).exists()
        if not employees or any(e.company_id != self.company_id for e in employees):
            raise AccessError(_('Choose employees from this payroll company.'))
        rows = [self._application_employee_inputs(e, start, end, certifications or {}) for e in employees]
        blockers = [dict(b, employee_id=r['employee_id'], employee=r['name']) for r in rows for b in r['blockers']]
        all_inputs = [v for r in rows for v in r['inputs']]
        answer = {'ok': not blockers, 'employees': rows, 'blockers': blockers,
                'certifications': certifications or {},
                'summary': {'employees': len(rows), 'inputs': len(all_inputs),
                    'resolved': sum(v['status'] in _READY for v in all_inputs),
                    'missing': sum(v['status'] == 'missing' for v in all_inputs),
                    'conflicts': sum(v['status'] == 'conflict' for v in all_inputs)}}
        answer['issue_groups'] = self._application_readiness_groups(answer, start, end)
        answer['summary']['issue_groups'] = len(answer['issue_groups'])
        return answer


class ApplicationFormulaRule(models.Model):
    _inherit = 'hr.formula.rule'

    application_source_key = fields.Char(string='Application source key', index=True)
    application_source_required = fields.Boolean(string='Require application source', default=False)
    application_source_note = fields.Text(string='Application mapping review note')

    @api.constrains('application_source_key', 'column_type')
    def _check_application_source(self):
        for rule in self:
            if rule.application_source_key and rule.column_type != 'input':
                raise ValidationError(_('Only input components can read an application source.'))

    def application_source_options(self):
        self.ensure_one()
        return [dict(v, key=k) for k, v in self.config_id._application_source_catalogue().items()]


class ApplicationPayrollSnapshot(models.Model):
    _name = 'hr.payroll.application.snapshot'
    _description = 'Frozen Application Payroll Inputs'
    _order = 'id desc'

    # Draft cleanup may remove the slip; immutable payload retains employee,
    # contract, period, sources and values after this reference is detached.
    payslip_id = fields.Many2one('hr.payslip', ondelete='set null', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    config_id = fields.Many2one('hr.formula.config', required=True, ondelete='restrict')
    fingerprint = fields.Char(required=True, index=True)
    payload_json = fields.Text(required=True)
    certification_stamp = fields.Char(required=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(_SEAL_KEY) is not _SEAL:
            raise AccessError(_('Payroll snapshots are created only by validated computation.'))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_('Payroll input snapshots are immutable. Recompute a draft to create a new snapshot.'))

    def unlink(self):
        raise UserError(_('Payroll input evidence cannot be deleted.'))


class ApplicationPayrollRun(models.Model):
    _inherit = 'hr.payslip.run'

    application_data_mode = fields.Boolean(string='Use application records', copy=False)
    application_certification_json = fields.Text(readonly=True, copy=False)
    application_certified_by = fields.Many2one('res.users', readonly=True, copy=False)
    application_certified_at = fields.Datetime(readonly=True, copy=False)

    def _application_config(self):
        self.ensure_one()
        config = self.pb_formula_config_id if 'pb_formula_config_id' in self._fields else self.env['hr.formula.config']
        if not config:
            config = self.slip_ids.formula_config_id
        if len(config) != 1:
            raise UserError(_('Choose exactly one payroll scheme for application data.'))
        return config

    def action_certify_application_data(self, certifications, reason):
        self.ensure_one()
        config = self._application_config()
        config._application_require_access(certify=True)
        if self.state != 'draft' or not self.application_data_mode:
            raise UserError(_('Certify an application-data run while it is a draft.'))
        if not isinstance(certifications, dict) or not (reason or '').strip():
            raise ValidationError(_('Record a reason and explicit period coverage.'))
        channels = certifications.get('channels') or {}
        if set(channels) - _CHANNELS or any(type(v) is not bool for v in channels.values()):
            raise ValidationError(_('Use explicit true/false coverage for leave, overtime, timesheets and adjustments.'))
        employee_ids = sorted(set(certifications.get('employee_ids') or self.slip_ids.employee_id.ids))
        employees = self.env['hr.employee'].browse(employee_ids).exists()
        if not employee_ids or len(employees) != len(employee_ids) or any(e.company_id != config.company_id for e in employees):
            raise ValidationError(_('Certification must name the employees in this payroll company.'))
        catalogue = config._application_source_catalogue()
        zeros = sorted(set(certifications.get('zero_keys') or []))
        if any(not catalogue.get(k, {}).get('certification_zero_allowed') for k in zeros):
            raise ValidationError(_('Only supported period-event sources allow a no-activity certification.'))
        cert = {'channels': channels, 'zero_keys': zeros, 'employee_ids': employee_ids,
                'run_id': self.id, 'config_id': config.id, 'company_id': config.company_id.id,
                'period': [str(self.date_start), str(self.date_end)],
                'reason': reason.strip(), 'certified_by': self.env.uid,
                'certified_at': str(fields.Datetime.now())}
        self.with_context(**{_SEAL_KEY: _SEAL}).write({
            'application_certification_json': _json(cert),
            'application_certified_by': self.env.uid, 'application_certified_at': fields.Datetime.now()})
        return {'ok': True, 'certification': cert}

    def _application_certification(self, employee_id=None):
        self.ensure_one()
        try:
            cert = json.loads(self.application_certification_json or '{}')
        except (TypeError, ValueError):
            cert = {}
        config = self._application_config()
        if (cert.get('run_id') != self.id or cert.get('config_id') != config.id
                or cert.get('company_id') != config.company_id.id
                or cert.get('period') != [str(self.date_start), str(self.date_end)]
                or employee_id and employee_id not in cert.get('employee_ids', [])):
            raise UserError(_('Certify application-data completeness for this exact run, period and employee scope first.'))
        return cert

    def _application_assert_current(self):
        for run in self.filtered('application_data_mode'):
            cert = run._application_certification()
            if not run.slip_ids:
                raise UserError(_('Compute the application-data payslips before approval.'))
            active_slips = run.slip_ids.filtered(lambda s: s.state != 'cancel')
            if (set(active_slips.employee_id.ids) != set(cert.get('employee_ids') or [])
                    or len(active_slips) != len(active_slips.employee_id)):
                raise UserError(_('Compute exactly one payslip for every employee in the certified scope before approval.'))
            for slip in active_slips:
                slip._application_assert_current()
        return True

    def _approval_validate(self):
        self._application_assert_current()
        parent = getattr(super(), '_approval_validate', None)
        return parent() if parent else True

    def _approval_apply(self, request):
        if any(r.state not in ('done', 'paid') for r in self):
            self._application_assert_current()
        parent = getattr(super(), '_approval_apply', None)
        return parent(request) if parent else True

    def write(self, vals):
        sealed = {'application_certification_json', 'application_certified_by', 'application_certified_at'}
        if sealed.intersection(vals) and self.env.context.get(_SEAL_KEY) is not _SEAL:
            raise AccessError(_('Use the coverage certification action to sign payroll completeness.'))
        if vals.get('state') in ('level1', 'level2', 'approval_pending', 'done', 'close'):
            # Finalization can consume a leave settlement and close its live
            # balance. Retrying the same already-final state must preserve
            # that historical snapshot, not compare it with the post-close
            # balance and accidentally demand another payment.
            self.filtered(lambda r: not (vals.get('state') == r.state == 'done'))._application_assert_current()
        if vals.get('application_data_mode') is False and any(r.application_data_mode and r.slip_ids for r in self):
            raise UserError(_('A run with application snapshots cannot be switched to spreadsheet mode.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v) & {'application_certification_json', 'application_certified_by', 'application_certified_at'} for v in vals_list):
            raise AccessError(_('Create the run first, then certify its coverage.'))
        return super().create(vals_list)


class ApplicationPayrollPayslip(models.Model):
    _inherit = 'hr.payslip'

    application_snapshot_id = fields.Many2one('hr.payroll.application.snapshot', readonly=True,
                                               copy=False, ondelete='restrict')

    def _application_mode(self):
        self.ensure_one()
        return bool(self.payslip_run_id.application_data_mode)

    def _application_check_scope(self, config):
        self.ensure_one()
        run = self.payslip_run_id
        if (config != run._application_config() or self.formula_config_id != config
                or self.date_from != run.date_start or self.date_to != run.date_end
                or self.company_id != config.company_id):
            raise UserError(_('The payslip must match its certified run scheme, company and period.'))

    def _application_resolve_inputs(self, config):
        self.ensure_one()
        if self.state not in ('draft',) or self.payslip_run_id.state != 'draft':
            raise UserError(_('Only draft application payroll can be computed; return pending payroll for review or use a reviewed adjustment.'))
        self._application_check_scope(config)
        cert = self.payslip_run_id._application_certification(self.employee_id.id)
        row = config.with_context(pb_application_payslip_id=self.id)._application_employee_inputs(
            self.employee_id, self.date_from, self.date_to, cert)
        if not row['ok']:
            raise UserError(_('Application payroll needs attention:\n%s') % '\n'.join(
                '%s: %s' % (b.get('code') or self.employee_id.name, b['reason']) for b in row['blockers']))
        if self.contract_id.id != row['contract_id']:
            raise UserError(_('The payslip contract does not match the single effective application contract.'))
        snap = self.env['hr.payroll.application.snapshot'].sudo().with_context(**{_SEAL_KEY: _SEAL}).create({
            'payslip_id': self.id, 'company_id': self.company_id.id, 'config_id': config.id,
            'fingerprint': _stamp(row), 'payload_json': _json(row), 'certification_stamp': _stamp(cert)})
        self.with_context(**{_SEAL_KEY: _SEAL}).write({'application_snapshot_id': snap.id})
        sources = row['provenance']
        for source in sources.values():
            source['application_snapshot_id'] = snap.id
        return row['values'], sources

    def _application_assert_current(self):
        for slip in self.filtered(lambda s: s._application_mode()):
            slip._application_check_scope(slip.formula_config_id)
            snapshot = slip.application_snapshot_id
            if not snapshot:
                raise UserError(_('Compute a validated application snapshot before approval.'))
            cert = slip.payslip_run_id._application_certification(slip.employee_id.id)
            row = slip.formula_config_id.with_context(pb_application_payslip_id=slip.id)._application_employee_inputs(
                slip.employee_id, slip.date_from, slip.date_to, cert)
            if not row['ok'] or snapshot.fingerprint != _stamp(row) or snapshot.certification_stamp != _stamp(cert):
                raise UserError(_('Application records, policy, mappings or coverage changed. Review and recompute the draft before approval.'))
            try:
                stored_inputs = json.loads(slip.formula_input_values or '{}')
                stored_results = json.loads(slip.formula_computed_values or '{}')
                stored_sources = json.loads(slip.formula_input_sources or '{}')
            except (TypeError, ValueError):
                raise UserError(_('The application payroll calculation is incomplete. Recompute it before approval.'))
            if stored_inputs != row['values']:
                raise UserError(_('Payslip inputs no longer match their frozen application evidence. Recompute before approval.'))
            expected_sources = {code: dict(source, application_snapshot_id=snapshot.id)
                                for code, source in row['provenance'].items()}
            if stored_sources != expected_sources:
                raise UserError(_('Payslip provenance no longer matches its frozen evidence. Recompute before approval.'))
            rules = slip.formula_config_id.rule_ids.sorted(key=lambda r: r.sequence)
            expected, log = slip._evaluate_rules_with_dependencies(rules, row['values'])
            if expected != stored_results or any(entry.startswith('[ERROR]') for entry in log):
                raise UserError(_('Payslip results no longer match the certified inputs and formulas. Recompute before approval.'))
            expected_lines = {r.code: r for r in rules if r.appears_on_payslip and
                              value_kind_classifier.wants_number(r.value_kind)}
            if len(slip.line_ids) != len(expected_lines) or set(slip.line_ids.mapped('code')) != set(expected_lines):
                raise UserError(_('Payslip lines no longer match the certified calculation. Recompute before approval.'))
            for line in slip.line_ids:
                rule = expected_lines[line.code]
                amount = float(expected.get(rule.code, 0.))
                # Formula results retain intermediate precision; persisted
                # payslip lines use the amount field's two-decimal rounding.
                # Compare against that same representation, not raw results.
                if (not math.isfinite(amount) or not math.isclose(line.amount, line._smart_round(amount), rel_tol=0., abs_tol=.000001)
                        or line.quantity != 1. or line.rate != 100.
                        or line.pay_role != (rule.net_role or False)
                        or line.component_detail != bool(rule.net_role_detail)
                        or line.employee_id != slip.employee_id or line.contract_id != slip.contract_id):
                    raise UserError(_('Payslip line amounts or pay roles changed after computation. Recompute before approval.'))
        return True

    def write(self, vals):
        if 'application_snapshot_id' in vals and self.env.context.get(_SEAL_KEY) is not _SEAL:
            raise AccessError(_('The payroll computation owns its frozen input snapshot.'))
        if vals.get('state') in ('level1', 'level2', 'verify', 'done'):
            self.filtered(lambda s: not (vals.get('state') == s.state == 'done'))._application_assert_current()
        if any(s.application_snapshot_id and s.state in ('done', 'paid') for s in self) and set(vals) & {
                'formula_input_values', 'formula_input_sources', 'formula_computed_values',
                'date_from', 'date_to', 'formula_config_id', 'employee_id', 'contract_id'}:
            raise UserError(_('Completed application payroll inputs cannot be changed.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any('application_snapshot_id' in v for v in vals_list):
            raise AccessError(_('Payroll snapshots cannot be supplied by an import.'))
        return super().create(vals_list)
