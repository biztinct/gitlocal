# -*- coding: utf-8 -*-
"""The end of an internal hire: a job change, never a second person.

`pb_hiring`'s "Confirm they joined" makes an employee, a contract, a pay
package, a login and a joining checklist (FACTS §0.4). For somebody who
already works here every one of those is wrong: a second employee record, or
their OLD contract silently reused so the new pay never applies, a second
login, and a welcome checklist for a person who has been here for years.

So for an internal offer (its candidate has `pb_internal`):
  * NONE of those legs runs. The offer is linked to the existing employee.
  * The candidate is marked hired, the role fills, the signed letter is
    filed on the person — the paperwork that is true for a move.
  * CONTRACT C-1: when the system has the Change job flow (model
    `pb.job.change`, probed — Step 8 builds it), the offer opens it,
    prefilled, through `pb_start_for_employee(employee_id, vals)`. When it
    does not, the application carries "Job change to do" and HR is told in
    plain words to change the job on the employee record.

The four `_ensure_*` legs are also guarded one by one, so no other caller
can reach them for an internal candidate either.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_hiring.models.hiring_common import leg

_logger = logging.getLogger(__name__)

#: The model and method of contract C-1 (Step 8, phase S8-B).
JOB_CHANGE_MODEL = 'pb.job.change'
JOB_CHANGE_METHOD = 'pb_start_for_employee'


def job_change_available(env):
    """True when the Change job flow is installed (C-1, probed)."""
    return JOB_CHANGE_MODEL in env and hasattr(env[JOB_CHANGE_MODEL],
                                               JOB_CHANGE_METHOD)


class HiringOfferInternal(models.Model):
    _inherit = 'pb.hiring.offer'

    def _pbhi_internal(self):
        self.ensure_one()
        app = self.sudo().applicant_id
        return bool(app and app.pb_internal and app.employee_id)

    # ------------------------------------------------- the legs, guarded
    def _ensure_employee(self):
        if self._pbhi_internal():
            emp = self.sudo().applicant_id.employee_id
            if self.employee_id != emp:
                self.sudo().write({'employee_id': emp.id})
            return emp
        return super()._ensure_employee()

    def _ensure_contract(self):
        if self._pbhi_internal():
            return False
        return super()._ensure_contract()

    def _ensure_package(self):
        if self._pbhi_internal():
            return False
        return super()._ensure_package()

    def _ensure_benefits(self):
        if self._pbhi_internal():
            return False
        return super()._ensure_benefits()

    def _ensure_login(self):
        if self._pbhi_internal():
            return False
        return super()._ensure_login()

    def _ensure_case(self):
        if self._pbhi_internal():
            return False
        return super()._ensure_case()

    # ------------------------------------------------------- drafting
    @api.model
    def draft_for(self, requisition_id, values=None):
        offer = super().draft_for(requisition_id, values)
        # An offer being drafted IS an offer near (E4), whatever the stage.
        if offer and offer._pbhi_internal():
            offer.applicant_id._pbhi_tell_manager()
        return offer

    # -------------------------------------------------- confirming the move
    def action_confirm_joined(self, joined_on=None):
        if len(self) != 1 or not self._pbhi_internal():
            return super().action_confirm_joined(joined_on=joined_on)
        return self._pbhi_confirm_move(joined_on=joined_on)

    def _pbhi_confirm_move(self, joined_on=None):
        """The internal twin of `action_confirm_joined`. Returns the Change
        job action (C-1) when the system has one, else True."""
        self.ensure_one()
        if self.state == 'joined':
            return self._pbhi_job_change_action() or True
        if self.state != 'signed':
            raise UserError(_(
                "A move can be confirmed once the offer is signed. This one "
                "is “%s” — record the signed copy first.",
                dict(self._fields['state'].selection).get(self.state,
                                                          self.state)))
        when = fields.Date.to_date(joined_on) if joined_on else (
            self.expected_join_date or self.start_date
            or fields.Date.context_today(self))
        app = self.sudo().applicant_id
        emp = app.employee_id
        self.sudo().write({'joined_on': when, 'employee_id': emp.id})
        leg(self.env, 'hiring the internal candidate on offer %s' % self.name,
            self._mark_applicant_hired)
        leg(self.env, 'filing the signed documents on offer %s' % self.name,
            self._file_signed_copy)
        self.sudo().write({'state': 'joined', 'join_status': 'confirmed',
                           'closed_on': fields.Datetime.now()})
        leg(self.env, 'the move date on offer %s' % self.name,
            self._stamp_hire_date)
        app.with_context(pbhi_no_tell=True).write(
            {'pb_job_change_state': 'to_do'})
        self.sudo().message_post(body=_(
            "%(who)s moves to this role from %(when)s. They already work "
            "here, so no new employee record, contract, login or joining "
            "checklist was made. Their job change comes next.",
            who=emp.name or '', when=when))
        leg(self.env, 'filling the role behind offer %s' % self.name,
            lambda: self.requisition_id._on_filled())
        return self._pbhi_job_change_action() or True

    # ------------------------------------------------------ contract C-1
    def _pbhi_job_change_vals(self):
        """The prefill handed to `pb_start_for_employee` (C-1). Keys from the
        S8-B draft's accepted list; anything a later version does not accept
        is ignored there."""
        self.ensure_one()
        offer = self.sudo()
        req = offer.requisition_id
        app = offer.applicant_id
        job = req.job_id or app.job_id
        manager = offer.reporting_manager_id or req.reporting_manager_id
        vals = {
            'job_id': job.id or False,
            'job_title': offer.job_title or req.title or job.name or '',
            'department_id': req.department_id.id or False,
            'parent_id': manager.id or False,
            'company_id': req.company_id.id or False,
            'effective_date': offer.joined_on or offer.expected_join_date
            or offer.start_date or False,
            'reason': _('Moved to %(role)s through an internal application.',
                        role=req.title or job.name or ''),
            'reason_kind': 'transfer',
            'source': 'internal_hire',
            'source_ref': offer.name or '',
        }
        try:
            basic = offer._basic_line()
            if basic and basic[:1].amount:
                vals['wage'] = float(basic[:1].amount)
        except Exception:               # noqa: BLE001 — the prefill is a courtesy
            _logger.info('pb_hiring_internal: no basic pay line on offer %s',
                         offer.id, exc_info=True)
        return {k: v for k, v in vals.items() if v not in (False, None, '')}

    def _pbhi_job_change_target(self):
        """The Change job model (C-1), or None when this system has none."""
        if not job_change_available(self.env):
            return None
        return self.env[JOB_CHANGE_MODEL]

    def _pbhi_job_change_action(self):
        """The Change job action for this move, or False (with the calm note
        on the application) when the system has no such flow or it refused.
        """
        self.ensure_one()
        app = self.sudo().applicant_id
        emp = app.employee_id
        target = self._pbhi_job_change_target()
        if not emp or target is None:
            return False
        try:
            with self.env.cr.savepoint():
                action = getattr(target, JOB_CHANGE_METHOD)(
                    emp.id, self._pbhi_job_change_vals())
        except Exception:               # noqa: BLE001 — never fail the move
            _logger.warning('pb_hiring_internal: the Change job flow refused '
                            'offer %s', self.id, exc_info=True)
            return False
        if not isinstance(action, dict) or not action.get('type'):
            return False
        app.with_context(pbhi_no_tell=True).write(
            {'pb_job_change_state': 'opened'})
        return action
