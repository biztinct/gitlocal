# -*- coding: utf-8 -*-
"""Time off asks the same way everything else does.

WHAT WAS TRUE BEFORE. Who approves a leave was a setting on the leave TYPE —
"by the manager", "by an officer", "by both", "nobody" — and nothing else
could be said. No amount, no condition, no deadline, no reminder, no
hand-over, no backup, and no way to see a leave request in the same place as
every other thing waiting for you.

WHAT IS TRUE NOW. The default route says exactly what the type setting said:
**Their manager, when the type asks for a manager; then the HR lead, when the
type asks for an officer.** A type set to "no validation" is approved by
hr_holidays itself at the moment it is created, exactly as before, and never
reaches a route at all. From there a business can add a step for long
absences, a deadline, a backup — or set the whole process to "No approval
needed".

THE LEAVE IS APPROVED BY THE LAST APPROVER, AS THEMSELVES. `_approval_apply`
calls hr_holidays' own `action_approve`, which re-checks the holidays groups.
Somebody without them is told so by name and the seat can be moved — never
approved on their behalf by a background account (safety rail 5).
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, role_step, route,
)

_logger = logging.getLogger(__name__)

LEAVE_PROCESS_KEY = 'leave'

#: Set while the engine is carrying out an approval, so the override below
#: knows this press is the route's own and not a person skipping it.
ENGINE_APPLY = 'pb_leave_engine_apply'

OFFICER_GROUP = 'hr_holidays.group_hr_holidays_user'

#: A leave type whose name or code says the days are not paid. A heuristic and
#: deliberately a wide one: it is only ever used as a FACT a route may
#: condition on, never as a gate, and a business that wants it exact says so
#: with its own condition on the leave type instead.
UNPAID_WORDS = ('unpaid', 'no pay', 'nopay', 'không lương', 'khong luong')
UNPAID_CODES = ('UNPAID', 'NOPAY', 'UP', 'LUNPAID')


class HrLeaveApproval(models.Model):
    _name = 'hr.leave'
    _inherit = ['hr.leave', 'biz.approval.adapter.mixin']

    _approval_process_key = LEAVE_PROCESS_KEY

    # NO "a seat is also a read" column here, and that is deliberate:
    # hr_holidays already gives the person who approves somebody's leave the
    # Time off responsible role the moment they are named as their leave
    # manager, and that role carries its own read of their requests. Adding a
    # second door to the same room is how a security model stops being
    # readable.

    # ==================================================================
    # Is this company running leave through the engine?
    # ==================================================================
    def _leave_engine_managed(self):
        self.ensure_one()
        if 'biz.approval.binding' not in self.env:
            return False
        process = self.env['biz.approval.process']._by_key(LEAVE_PROCESS_KEY)
        if not process:
            return False
        company = self.company_id or self.env.company
        return bool(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id), ('active', '=', True)]))

    def _leave_open_request(self):
        self.ensure_one()
        request = self.approval_request_id
        return request if request and request.state in ('pending', 'blocked') \
            else self.env['biz.approval.request']

    # ==================================================================
    # The adapter
    # ==================================================================
    def _leave_days(self):
        self.ensure_one()
        return float(self.number_of_days or 0.0)

    def _leave_unpaid(self):
        self.ensure_one()
        leave_type = self.holiday_status_id
        code = (getattr(leave_type, 'code', '') or '').upper()
        name = (leave_type.name or '').lower()
        return bool(code in UNPAID_CODES
                    or any(word in name for word in UNPAID_WORDS))

    def _leave_over_cutoff(self):
        """Does this fall in a month whose pay is already being worked out?

        The one thing that makes a late leave request expensive: pay for that
        period has left draft, so somebody has to redo it.
        """
        self.ensure_one()
        if 'hr.payslip.run' not in self.env:
            return False
        start = self.request_date_from or (
            self.date_from.date() if self.date_from else None)
        if not start:
            return False
        runs = self.env['hr.payslip.run'].sudo().search([
            ('date_start', '<=', start), ('date_end', '>=', start),
        ], limit=5)
        return any(run.state != 'draft' for run in runs)

    def _approval_context(self):
        self.ensure_one()
        employee = self.employee_id.sudo()
        company = self.company_id or self.env.company
        leave_type = self.holiday_status_id
        scopes = []
        Division = self.env.get('pb.division')
        if Division is not None and employee.department_id:
            try:
                division = Division.sudo().division_for(
                    employee.department_id, self.request_date_from)
                if division:
                    scopes.append({'key': 'division:%s' % division.id,
                                   'label': division.name or ''})
            except Exception:   # noqa: BLE001 — a scope must never raise
                _logger.exception('pb_timeoff: the division of a leave failed')
        makers = {self.create_uid.id}
        if employee.user_id:
            makers.add(employee.user_id.id)
        makers.discard(False)
        facts = {
            'days': {'value': self._leave_days(), 'unit': _('days')},
            'leave_type': {'value': leave_type.name or '', 'unit': ''},
            'is_unpaid': {'value': self._leave_unpaid(), 'unit': ''},
            'overlaps_payroll_cutoff': {'value': self._leave_over_cutoff(),
                                        'unit': ''},
            'validation_type': {
                'value': leave_type.leave_validation_type or 'hr', 'unit': ''},
        }
        return {
            'company_id': company.id,
            'title': _("%(what)s · %(who)s",
                       what=leave_type.name or _('Time off'),
                       who=employee.name or ''),
            'scope_keys': [row['key'] for row in scopes] + [''],
            'scope_label': (scopes[0]['label'] if scopes
                            else company.name) or company.name,
            'kind_key': leave_type.leave_validation_type or 'any',
            'facts': facts,
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': employee.user_id.ids,
            'source_revision': self._approval_revision_of({
                'days': self._leave_days(),
                'from': str(self.request_date_from or ''),
                'to': str(self.request_date_to or ''),
                'type': leave_type.id,
            }),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'days': {'type': 'decimal', 'label': _('How many days')},
                'leave_type': {'type': 'char', 'label': _('Kind of time off')},
                'is_unpaid': {'type': 'bool', 'label': _('Unpaid')},
                'overlaps_payroll_cutoff': {
                    'type': 'bool',
                    'label': _('Falls in a month whose pay is already being '
                               'worked out')},
                'validation_type': {
                    'type': 'selection',
                    'label': _('What this kind of time off asks for')},
            },
            'kinds': [
                {'key': 'manager', 'label': _('Approved by the manager')},
                {'key': 'hr', 'label': _('Approved by an officer')},
                {'key': 'both', 'label': _('Approved by both')},
                {'key': 'no_validation', 'label': _('Approved by nobody')},
            ],
            'evidence': [],
            'scope_levels': [_('Division')],
            'manager_mode': True,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        rows = []
        Division = self.env.get('pb.division')
        if Division is not None:
            for division in Division.sudo().search([], limit=200,
                                                   order='name'):
                companies = division.company_ids
                if companies and company not in companies:
                    continue
                rows.append({'scope_key': 'division:%s' % division.id,
                             'scope_keys': ['division:%s' % division.id, ''],
                             'label': division.name or '', 'headcount': 0,
                             'kind_key': 'any', 'facts': {}})
        if not rows:
            rows = [{'scope_key': '', 'scope_keys': [''],
                     'label': company.name, 'headcount': 0,
                     'kind_key': 'any', 'facts': {}}]
        return rows

    def _approval_manager_uids(self):
        """The person hr_holidays already says approves this employee's leave."""
        self.ensure_one()
        employee = self.employee_id.sudo()
        manager = employee.leave_manager_id or employee.parent_id.user_id
        return manager.ids

    def _approval_card_count(self, request):
        self.ensure_one()
        days = self._leave_days()
        if days == 1:
            return _("1 day")
        return _("%s days", '{:g}'.format(days))

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('From'), 'value': str(self.request_date_from or '')},
            {'label': _('To'), 'value': str(self.request_date_to or '')},
            {'label': _('Days'), 'value': '{:g}'.format(self._leave_days())},
        ]
        if self._leave_over_cutoff():
            chips.append({'label': _('Pay for that month'),
                          'value': _('Already being worked out')})
        return {'title': _('The time off'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.name or '')[:240]}

    def _approval_validate(self):
        """The last moment before a request exists."""
        self.ensure_one()
        if self.state != 'confirm':
            raise UserError(_(
                "Only time off that is waiting for approval can be sent in."))
        if self._leave_open_request():
            raise UserError(_("This has already been sent in."))
        return True

    def _approval_apply(self, request):
        """The last approver approves the leave, as themselves."""
        self.ensure_one()
        if self.state in ('validate', 'refuse', 'cancel'):
            return True
        if not (self.env.su or self.env.user.has_group(OFFICER_GROUP)
                or self.env.user._is_admin()):
            raise UserError(_(
                "This time off is approved, but %s is not allowed to record "
                "time off. Ask somebody who looks after approvals to move "
                "this step to a person who is, or give them the Time off "
                "role.", self.env.user.name))
        leave = self.with_context(**{ENGINE_APPLY: True})
        if leave.state == 'confirm':
            leave.action_approve(check_state=False)
        if leave.state == 'validate1':
            leave.action_approve(check_state=True)
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        if self.state not in ('refuse', 'cancel'):
            self.with_context(**{ENGINE_APPLY: True}).sudo().action_refuse()
            if reason:
                self.sudo().message_post(body=reason,
                                         subtype_xmlid='mail.mt_note')
        return True

    def _approval_return(self, request, reason):
        """Sent back: refused with the reason, so the person can ask again.

        hr_holidays has no "back to draft" for a leave under approval — the
        one honest answer it does have is a refusal that says what to change,
        which is what the person reads.
        """
        self.ensure_one()
        if self.state not in ('refuse', 'cancel'):
            self.with_context(**{ENGINE_APPLY: True}).sudo().action_refuse()
            self.sudo().message_post(
                body=_("Sent back: %s", reason or _('no reason given')),
                subtype_xmlid='mail.mt_note')
        return True

    # ==================================================================
    # The doors
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        if self.env.context.get(ENGINE_APPLY) \
                or self.env.context.get('leave_fast_create'):
            return leaves
        for leave in leaves:
            if leave.state != 'confirm':
                continue
            try:
                if not leave._leave_engine_managed():
                    continue
                self.env['biz.approval.engine'].submit(leave)
            except Exception as exc:    # noqa: BLE001
                # A leave that cannot be routed must still exist and still be
                # approvable the old way: the alternative is somebody unable
                # to ask for a day off because a route is half set up.
                _logger.warning('pb_timeoff: leave %s could not be sent for '
                                'approval: %s', leave.id, exc)
        return leaves

    def action_approve(self, check_state=True):
        """One press = one decision on the live route."""
        if self.env.context.get(ENGINE_APPLY):
            return super().action_approve(check_state=check_state)
        routed = self.env['hr.leave']
        for leave in self:
            request = leave._leave_open_request() \
                if leave._leave_engine_managed() else False
            if not request:
                continue
            step = request.step_ids.filtered(
                lambda s: s.status == 'active').sorted('sequence')[:1]
            if not step:
                continue
            self.env['biz.approval.engine'].decide(
                request.id, step.key, 'approve')
            routed |= leave
        rest = self - routed
        if rest:
            return super(HrLeaveApproval, rest).action_approve(
                check_state=check_state)
        return True

    def action_refuse(self):
        if self.env.context.get(ENGINE_APPLY):
            return super().action_refuse()
        routed = self.env['hr.leave']
        for leave in self:
            request = leave._leave_open_request() \
                if leave._leave_engine_managed() else False
            if not request:
                continue
            step = request.step_ids.filtered(
                lambda s: s.status == 'active').sorted('sequence')[:1]
            if not step:
                continue
            self.env['biz.approval.engine'].decide(
                request.id, step.key, 'reject', _("Refused"))
            routed |= leave
        rest = self - routed
        if rest:
            return super(HrLeaveApproval, rest).action_refuse()
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', OFFICER_GROUP)
        return Seed.lay(
            company, LEAVE_PROCESS_KEY, 'Time off',
            route(
                manager_step(
                    _('Their manager'),
                    condition={'fact': 'validation_type', 'op': 'in',
                               'value': ['manager', 'both']}),
                role_step(
                    _('HR lead'), 'hr_lead',
                    condition={'fact': 'validation_type', 'op': 'in',
                               'value': ['hr', 'both']}),
            ),
            binding_note='What each kind of time off already asked for: the '
                         'manager, an officer, or both.',
            model_name='hr.leave',
            role_keys=('hr_lead',),
            reason='Set up when time-off approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['hr.leave']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_timeoff: %s has no time-off route',
                              company.name)
    return done
