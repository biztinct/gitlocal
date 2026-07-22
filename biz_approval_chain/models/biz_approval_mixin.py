# Part of Payobook. See LICENSE file for full copyright and licensing details.

import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class BizApprovalChainMixin(models.AbstractModel):
    """A small generic multi-tier approval state machine.

    A consumer inherits this mixin, defines a ``state`` Selection field and a
    ``_approval_transitions`` map, then drives the chain with ``_advance_state``
    and ``action_refuse_chain``. Authorization is decided SERVER-SIDE in
    ``_approval_can`` — any ``can_*`` view booleans are cosmetic (safety rail 3).

    ``_approval_transitions`` maps ``(from_state, to_state) -> group_xmlid|None``:
      * a group xmlid → the acting user must ``has_group`` it;
      * ``None``      → open by default (the record owner / any user); a consumer
                        overrides ``_approval_can`` to make a SPECIFIC person
                        (e.g. the employee's own manager) pass without a group.

    No sudo writes anywhere here: the mixin runs as the clicking user so the log
    is truthful (safety rail 5).
    """
    _name = 'biz.approval.chain.mixin'
    _description = 'Approval Chain Mixin'

    # consumer overrides — {(from, to): 'module.group_xmlid' | None}
    _approval_transitions = {}
    # states that are terminal refusals/cancellations (never offered as targets
    # by the auto-computed helpers and excluded from the forward ladder)
    _approval_dead_states = ('refused', 'cancelled')

    # --------------------------------------------------------- authorization
    def _approval_can(self, from_state, to_state):
        """May the current user perform (from_state → to_state) on self?

        Base rule: the transition's group (None = open). Consumers override and
        call super to ALSO admit a specific person (owner/manager) — safety
        rail 4 (a demo must never dead-end because the group-holder is absent).
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        group = self._approval_transitions.get((from_state, to_state))
        if group is None:
            return True
        return self.env.user.has_group(group)

    def _approval_can_refuse(self, from_state):
        """A user who could advance the CURRENT stage may also refuse it."""
        self.ensure_one()
        targets = [to for (frm, to) in self._approval_transitions
                   if frm == from_state and to not in self._approval_dead_states]
        return any(self._approval_can(from_state, to) for to in targets)

    # --------------------------------------------------------- transitions
    def _advance_state(self, to_state, note=False):
        """Validate + perform a forward transition, then log it."""
        self.ensure_one()
        frm = self.state
        if (frm, to_state) not in self._approval_transitions:
            raise UserError(
                _("Illegal approval transition: %s → %s.", frm, to_state))
        if not self._approval_can(frm, to_state):
            raise AccessError(
                _("You are not allowed to perform this approval step."))
        self._before_approval_transition(to_state)
        self.write({'state': to_state})
        self._after_approval_transition(to_state)
        self._log_transition(frm, to_state, note)
        return True

    def action_refuse_chain(self, note=False):
        """Refuse from any mid-state (an approver of the current stage)."""
        for rec in self:
            frm = rec.state
            if frm in rec._approval_dead_states:
                raise UserError(_("This record is already closed."))
            if not rec._approval_can_refuse(frm):
                raise AccessError(_("You are not allowed to refuse this step."))
            rec._before_approval_transition('refused')
            rec.write({'state': 'refused'})
            rec._after_approval_transition('refused')
            rec._log_transition(frm, 'refused', note)
        return True

    # --------------------------------------------------------------- hooks
    def _before_approval_transition(self, to_state):
        """Optional consumer hook — raise to veto, mutate to prepare."""
        return

    def _after_approval_transition(self, to_state):
        """Optional consumer hook — side effects (expenses, notifications)."""
        return

    # ----------------------------------------------------------------- log
    def _log_transition(self, from_state, to_state, note):
        self.ensure_one()
        vals = {
            'res_model': self._name, 'res_id': self.id,
            'from_state': from_state, 'to_state': to_state,
            'note': note or False,
        }
        if 'company_id' in self._fields and self.company_id:
            vals['company_id'] = self.company_id.id
        # NO sudo — the acting user must have create rights so the row is truthful
        self.env['biz.approval.step.log'].create(vals)

    def get_approval_trail(self):
        """Ordered JSON trail for the stepper widget."""
        self.ensure_one()
        logs = self.env['biz.approval.step.log']._for_record(self)
        return [{
            'from_state': l.from_state,
            'to_state': l.to_state,
            'user': l.user_id.name,
            'user_id': l.user_id.id,
            'avatar': '/web/image/res.users/%s/avatar_128' % l.user_id.id,
            'stamp': fields.Datetime.to_string(l.stamp),
            'note': l.note or '',
        } for l in logs]

    def _approval_widget_payload(self, steps):
        """Assemble the JSON a ``biz_approval_stepper`` field renders.

        ``steps`` is the consumer's ordered ladder:
        ``[{'state','label','group_label'?}]``. Returns a JSON string with the
        trail merged in and the current state marked.
        """
        self.ensure_one()
        return json.dumps({
            'steps': steps,
            'trail': self.get_approval_trail(),
            'current': self.state,
            'dead_states': list(self._approval_dead_states),
        })
