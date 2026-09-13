# -*- coding: utf-8 -*-
"""Overtime goes to whoever the business says, not to whoever holds a group.

WHAT WAS TRUE BEFORE. One rung, decided in code: the attendance officer tier,
or the person's own line manager. Nothing else could be asked — not for the
hours that push somebody past the yearly ceiling, not for a second signature
on a long night.

WHAT IS TRUE NOW. The default route is **Their manager**, which is what the
old rung meant in practice, and the facts every route can use are the ones
this module already works out: the hours asked for, whether they go over the
ceiling, and how many overtime hours that person has had this year.

THE SPLIT IS STILL RECOMPUTED AT THE END. `action_approve` recalculates the
approved/bonus split against the allowance as it is AT THE MOMENT OF
APPROVAL, because other requests may have been approved since. Under a route
that moment is the LAST yes, not the first (ledger AM81), so the recompute and
the sealed write happen inside `_approval_apply`.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, route,
)

_logger = logging.getLogger(__name__)

OVERTIME_PROCESS_KEY = 'overtime'

#: Set while the engine carries out the approval.
ENGINE_APPLY = 'pb_ot_engine_apply'

OFFICER_GROUP = 'hr_attendance.group_hr_attendance_officer'

#: Hours compare to two places; anything smaller is float noise.
HOURS_EPS = 0.01


class OvertimeRequestApproval(models.Model):
    _name = 'hr.overtime.request'
    _inherit = ['hr.overtime.request', 'biz.approval.adapter.mixin']

    _approval_process_key = OVERTIME_PROCESS_KEY

    # ------------------------------------------------------------ managed?
    def _ot_engine_managed(self):
        self.ensure_one()
        if 'biz.approval.binding' not in self.env:
            return False
        process = self.env['biz.approval.process']._by_key(
            OVERTIME_PROCESS_KEY)
        if not process:
            return False
        company = self.employee_id.sudo().company_id or self.env.company
        return bool(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id), ('active', '=', True)]))

    def _ot_open_request(self):
        self.ensure_one()
        request = self.approval_request_id
        return request if request and request.state in ('pending', 'blocked') \
            else self.env['biz.approval.request']

    # ------------------------------------------------------------ the facts
    def _ot_year_hours(self):
        """How much overtime this person has already had approved this year."""
        self.ensure_one()
        if not (self.employee_id and self.date):
            return 0.0
        rows = self.sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('date', '>=', self.date.replace(month=1, day=1)),
            ('date', '<=', self.date.replace(month=12, day=31)),
        ])
        return round(sum(rows.mapped('total_hours')), 2)

    def _ot_over_ceiling(self):
        self.ensure_one()
        Ceiling = self.env.get('pb.ot.ceiling')
        if Ceiling is None or not self.employee_id or not self.date:
            return False
        entry = self.actual_hours or self.planned_hours or 0.0
        try:
            approved, bonus = Ceiling.sudo()._split(
                self.employee_id, self.date, entry, exclude_ids=[self.id])
        except Exception:       # noqa: BLE001 — a fact must never raise
            return False
        return bool(bonus)

    def _approval_context(self):
        self.ensure_one()
        employee = self.employee_id.sudo()
        company = employee.company_id or self.env.company
        hours = self.actual_hours or self.planned_hours or 0.0
        scopes = []
        Division = self.env.get('pb.division')
        if Division is not None and employee.department_id:
            try:
                division = Division.sudo().division_for(
                    employee.department_id, self.date)
                if division:
                    scopes.append({'key': 'division:%s' % division.id,
                                   'label': division.name or ''})
            except Exception:   # noqa: BLE001 — a scope must never raise
                _logger.exception('pb_hr_workforce: the division of an '
                                  'overtime request failed')
        makers = {self.create_uid.id}
        if employee.user_id:
            makers.add(employee.user_id.id)
        makers.discard(False)
        return {
            'company_id': company.id,
            'title': _("Overtime · %(who)s · %(day)s",
                       who=employee.name or '', day=self.date or ''),
            'scope_keys': [row['key'] for row in scopes] + [''],
            'scope_label': (scopes[0]['label'] if scopes
                            else company.name) or company.name,
            'kind_key': self.overtime_type or 'any',
            'facts': {
                'hours': {'value': float(hours), 'unit': _('hours')},
                'ot_type': {'value': self.overtime_type or '', 'unit': ''},
                'year_to_date_hours': {'value': self._ot_year_hours(),
                                       'unit': _('hours')},
                'over_ceiling': {'value': self._ot_over_ceiling(), 'unit': ''},
            },
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': employee.user_id.ids,
            'source_revision': self._approval_revision_of({
                'hours': float(hours), 'date': str(self.date or ''),
                'type': self.overtime_type or ''}),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'hours': {'type': 'decimal', 'label': _('Hours asked for')},
                'ot_type': {'type': 'selection', 'label': _('Kind of hours')},
                'year_to_date_hours': {
                    'type': 'decimal',
                    'label': _('Overtime already had this year')},
                'over_ceiling': {'type': 'bool',
                                 'label': _('Past what the law allows')},
            },
            'kinds': [],
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
        self.ensure_one()
        return self.employee_id.sudo().parent_id.user_id.ids

    # ------------------------------------------------- the "nothing to think
    #                                                    about here" verdict
    def _approval_batch_safe(self, request):
        """May this one be swept up by "approve everything easy"?

        Moved here from the Workforce team screen when that screen was
        retired, unchanged in what it promises: three conditions, all of which
        must hold, and any doubt resolves to NO.

        1. **the figures are still the ones the grid entered** — the weekly
           grid writes the same number to planned and actual, so a row where
           they have since diverged was edited by a person, and a person's
           edit is exactly what a batch must not sweep up;
        2. **there is headroom under the ceiling** — the monthly and yearly
           caps, read through the grid's own arithmetic so this can never
           drift from what the ceiling rail shows;
        3. **the day is not locked** — approving overtime onto a closed week
           is refused anyway, and offering it would be a button that can only
           produce an error.

        FAIL CLOSED: if any of the three reads is unavailable, nothing is easy.
        """
        self.ensure_one()
        if self.state != 'submitted':
            return False
        entered = self.actual_hours or 0.0
        planned = self.planned_hours or 0.0
        if entered <= 0 or abs(entered - planned) > HOURS_EPS:
            return False
        try:
            ceilings = self.env['hr.attendance.weekentry'].sudo()._ot_ceilings(
                self.employee_id.ids, fields.Date.context_today(self))
        except Exception:       # noqa: BLE001 — unreadable means not easy
            _logger.debug('pb_hr_workforce: the overtime ceilings could not '
                          'be read, so nothing is easy', exc_info=True)
            return False
        company_id = self.company_id.id if 'company_id' in self._fields \
            and self.company_id else self.employee_id.sudo().company_id.id
        if 'pb.wf.lock' in self.env and self.date:
            try:
                locked = self.env['pb.wf.lock']._locked_pairs(
                    [company_id], [self.date])
            except Exception:   # noqa: BLE001 — unreadable means not easy
                _logger.debug('pb_hr_workforce: the lock state could not be '
                              'read, so nothing is easy', exc_info=True)
                return False
            if (company_id, self.date) in (locked or set()):
                return False
        ceiling = (ceilings or {}).get(self.employee_id.id)
        if not ceiling:
            return False
        if ceiling.get('cap_month') \
                and ceiling['mtd'] > ceiling['cap_month'] + HOURS_EPS:
            return False
        if ceiling.get('cap_year') \
                and ceiling['ytd'] > ceiling['cap_year'] + HOURS_EPS:
            return False
        return True

    def _approval_card_count(self, request):
        self.ensure_one()
        hours = self.actual_hours or self.planned_hours or 0.0
        return _("%s hours", '{:g}'.format(float(hours)))

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Day'), 'value': str(self.date or '')},
            {'label': _('Hours'),
             'value': '{:g}'.format(float(self.actual_hours
                                          or self.planned_hours or 0.0))},
            {'label': _('This year so far'),
             'value': '{:g}'.format(self._ot_year_hours())},
        ]
        if self._ot_over_ceiling():
            chips.append({'label': _('Past the ceiling'), 'value': _('Yes')})
        return {'title': _('The overtime'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.reason or '')[:240]
                if 'reason' in self._fields else ''}

    # ------------------------------------------------------- the transitions
    def _approval_apply(self, request):
        """The split is recomputed and sealed when the whole route says yes."""
        self.ensure_one()
        if self.state == 'approved':
            return True
        if not (self.env.su or self.env.user._is_admin()
                or self._ot_can_decide()):
            raise UserError(_(
                "This overtime is approved, but %s is not allowed to record "
                "overtime. Ask somebody who looks after approvals to move "
                "this step to a person who is.", self.env.user.name))
        self.with_context(**{ENGINE_APPLY: True}).action_approve()
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        if self.state == 'submitted':
            self.sudo().with_context(**{ENGINE_APPLY: True}).action_refuse()
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        if self.state == 'submitted':
            self.sudo().with_context(
                **{ENGINE_APPLY: True})._ot_chain().write({'state': 'draft'})
            self.sudo().message_post(
                body=_("Sent back: %s", reason or _('no reason given')))
        return True

    # ---------------------------------------------------------- the buttons
    def action_submit(self):
        result = super().action_submit()
        if self.env.context.get(ENGINE_APPLY):
            return result
        for rec in self.filtered(lambda r: r.state == 'submitted'):
            try:
                if not rec._ot_engine_managed() or rec._ot_open_request():
                    continue
                self.env['biz.approval.engine'].submit(rec)
            except Exception as exc:    # noqa: BLE001 — the request exists
                _logger.warning('pb_hr_workforce: overtime %s could not be '
                                'sent for approval: %s', rec.id, exc)
        return result

    def action_approve(self):
        if self.env.context.get(ENGINE_APPLY):
            return super().action_approve()
        routed = self.env['hr.overtime.request']
        for rec in self:
            request = rec._ot_open_request() if rec._ot_engine_managed() \
                else False
            if not request:
                continue
            step = request.step_ids.filtered(
                lambda s: s.status == 'active').sorted('sequence')[:1]
            if not step:
                continue
            self.env['biz.approval.engine'].decide(
                request.id, step.key, 'approve')
            routed |= rec
        rest = self - routed
        if rest:
            return super(OvertimeRequestApproval, rest).action_approve()
        return True

    def action_refuse(self):
        if self.env.context.get(ENGINE_APPLY):
            return super().action_refuse()
        routed = self.env['hr.overtime.request']
        for rec in self:
            request = rec._ot_open_request() if rec._ot_engine_managed() \
                else False
            if not request:
                continue
            step = request.step_ids.filtered(
                lambda s: s.status == 'active').sorted('sequence')[:1]
            if not step:
                continue
            self.env['biz.approval.engine'].decide(
                request.id, step.key, 'reject', _("Refused"))
            routed |= rec
        rest = self - routed
        if rest:
            return super(OvertimeRequestApproval, rest).action_refuse()
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        return self.env['biz.approval.seed'].lay(
            company, OVERTIME_PROCESS_KEY, 'Overtime',
            route(manager_step(_('Their manager'))),
            binding_note='The route every overtime request follows unless a '
                         'part of the business is given its own.',
            model_name='hr.overtime.request',
            reason='Set up when overtime approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['hr.overtime.request']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_hr_workforce: %s has no overtime route',
                              company.name)
    return done
