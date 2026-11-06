# -*- coding: utf-8 -*-
"""A goal sheet travels the route the business published.

TWO RUNGS, AND THEY ASK DIFFERENT QUESTIONS. The manager is asked *are these
the right goals, and is this what matters most* — which is why the weights are
theirs and why the sheet cannot leave their rung until those add up to a
hundred. The HR lead is asked *is this fair beside everybody else's*, and their
press LOCKS the sheet: the goals stop being editable and the year starts.

WHAT AN APPROVER IS AGREEING TO is the goals and their weights. Change a title
or a weight after a rung has been decided and the approval that was given was
given to a different sheet, so the revision stamp is exactly those two things
(`_chain_revision_values`, AM32) — never `write_date`, and never the progress,
which is true of the work rather than of the plan and moves every week by
design.

NO `date_field` (R192). The shim's `_chain_date()` is handed to
`responsibility.resolve(..., on_date)`, so naming a historical field asks "who
held this seat back then" — and a goal sheet's own dates are its deadline and
its year, both of which are the wrong question. An approval asks who holds the
seat NOW, because now is when the decision is being made.
"""

import logging

from odoo import _, api, fields, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .goals_common import (
    GROUP_MANAGER, P_ESCALATE_DAYS, P_SLA_DAYS, number,
)

_logger = logging.getLogger(__name__)

GOALS_PROCESS_KEY = 'goal_set'

#: `reverse_to` NAMES `returned` AND NOT THE DRAFT. "Sent back" and "never sent"
#: are different rows on a board and the difference is the only useful thing on
#: it — somebody whose goals came back a week ago and has not touched them since
#: is the person HR wants to see, and a sheet that fell back into `draft` is
#: indistinguishable from one nobody ever started.
register_chain(
    'pb.goal.set', GOALS_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_ok', 'locked'),
    draft_state='draft',
    refuse_state='refused',
    reverse_to=('returned',),
    employee_field='employee_id',
)


def goals_route(env=None):
    """Today's ladder, written as a route somebody can read and change.

    THE SLA THE SHEET ASKS FOR IS THE ROUTE'S OWN. `route(due_days=…)` sets
    when a rung falls due and the engine's `escalate_cron` widens the chase
    after `late.escalate_days` — so the two dials are passed in here rather
    than re-implemented as a cron of ours, which would be a second opinion
    about the same date and would sooner or later disagree with the request's
    own trail.
    """
    due = number(env, P_SLA_DAYS, 5) if env is not None else 5
    escalate = number(env, P_ESCALATE_DAYS, 2) if env is not None else 2
    definition = route(
        manager_step(_('Their manager')),
        role_step(_('HR lead'), 'hr_lead', key='hr'),
        due_days=max(int(due or 5), 1),
    )
    definition['safeguards']['late']['escalate_days'] = max(
        int(escalate or 2), 1)
    return definition


class PbGoalSetApproval(models.Model):
    _inherit = 'pb.goal.set'

    _approval_process_key = GOALS_PROCESS_KEY

    # ==================================================================
    #  What the engine is told
    # ==================================================================
    def _chain_title(self):
        self.ensure_one()
        return _("Goals · %(who)s · %(cycle)s",
                 who=self.employee_id.sudo().name or '',
                 cycle=self.cycle_id.sudo().name or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        """Read AS THE SYSTEM (AM40).

        The maker is the employee, who holds no goals permission at all and
        cannot otherwise read their own sheet's totals — and the facts a route
        is CHOSEN on must be readable by the engine whoever the maker is.
        """
        self.ensure_one()
        record = self.sudo()
        return {
            'goals': {'value': int(record.goal_count or 0),
                      'unit': _('goals')},
            'key_results': {'value': int(record.kr_count or 0),
                            'unit': _('key results')},
            'weight_total': {'value': float(record.weight_total or 0.0),
                             'unit': _('out of 100')},
            'weights_add_up': {
                'value': abs(float(record.weight_total or 0.0) - 100) < 0.01,
                'unit': ''},
            'department': {'value': record.department_id.name or '',
                           'unit': ''},
            'late': {'value': bool(
                record.deadline and record.deadline < fields.Date.today()),
                'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'goals': {'type': 'int', 'label': _('How many goals')},
            'key_results': {'type': 'int', 'label': _('How many key results')},
            'weight_total': {'type': 'decimal',
                             'label': _('What the weights add up to')},
            'weights_add_up': {'type': 'bool',
                               'label': _('The weights add up to 100')},
            'department': {'type': 'char',
                           'label': _('Which part of the business')},
            'late': {'type': 'bool', 'label': _('Sent in after the deadline')},
        }

    def _chain_revision_values(self):
        """WHAT THE EMPLOYEE WROTE, and deliberately not the weights.

        The stamp is frozen when the sheet is SENT IN and compared again when
        the last rung is agreed, so anything an APPROVER is meant to change on
        the way through cannot be in it. The weights are exactly that: setting
        them is the manager's whole job on their own rung, and a stamp over
        them means the route refuses to carry out an approval that everybody
        gave correctly.

        Found live on the first end-to-end run and it is worth writing down
        because it looks like a success: the HR lead pressed Agree, the engine
        recorded the decision and closed the request, and the sheet stayed on
        "Waiting on the HR lead" with the reason only inside the request's own
        `block_reason` — *"This changed after it was sent in, so the approval
        no longer covers it."* An approval that half-happens is worse than one
        that is refused (ledger R193, reached from a new direction).

        So the stamp is the goals themselves: how many there are, what each one
        says, and when it is meant to be done by. Change any of those after the
        sheet went in and the approval that was given was given to a different
        sheet. NEVER `write_date` (AM32), never the progress — a key result
        moving from 30% to 40% is the work happening — and never the weights.
        """
        self.ensure_one()
        return {
            'goals': [
                {'title': (goal.title or '').strip(),
                 'due': str(goal.date_end or '')}
                for goal in self.sudo().goal_ids.sorted(
                    lambda g: (g.sequence, g.id))],
        }

    def _approval_detail(self, request):
        """What the approver reads without opening anything (AM49)."""
        self.ensure_one()
        record = self.sudo()
        chips = [
            {'label': _('Goal year'), 'value': record.cycle_id.name or ''},
            {'label': _('Goals'), 'value': str(record.goal_count or 0)},
            {'label': _('Weights add up to'),
             'value': '%s / 100' % int(round(record.weight_total or 0))},
        ]
        if record.department_id:
            chips.append({'label': _('Part of the business'),
                          'value': record.department_id.name or ''})
        if record.deadline:
            chips.append({'label': _('Was due'), 'value': str(record.deadline)})
        # A DRAWER ROW IS A DICT AND A LIST IS SILENTLY DISCARDED.
        # `pb_approval_config`'s shaper (`inbox_facade.py:598`) skips anything
        # that is not a dict with `head` / `sub` / `cells`, and it drops the
        # detail entirely only when there are no chips either — so a consumer
        # that hands it lists gets a drawer with its chips, its title and its
        # note all present and NO TABLE, which reads as "there was nothing to
        # show" rather than as a mistake. B1 shipped this as lists and the
        # goal-sheet drawer has been drawing no table ever since, with nothing
        # on any screen and nothing in any log to say so. Found live in B2.
        rows = [{'head': goal.title or '',
                 'sub': goal._rating_word(),
                 'cells': ['%s%%' % int(round(goal.weight or 0)),
                           str(goal.date_end or '')]}
                for goal in record.goal_ids.sorted(
                    lambda g: (g.sequence, g.id))]
        note = ''
        if abs(float(record.weight_total or 0.0) - 100) > 0.01:
            note = _("The weights do not add up to 100 yet. Open the sheet, "
                     "set them, and then agree it.")
        return {'title': _('The goals being agreed'),
                'columns': [_('Goal'), _('Weight'), _('Done by')],
                'rows': rows, 'chips': chips, 'note': note}

    # ==================================================================
    #  The rungs, as they land on the record
    # ==================================================================
    def _chain_engine_write(self, state):
        """R132 — THE MIDDLE OF A ROUTE IS WRITTEN AS THE APPROVER.

        `_approval_advance` mirrors each intermediate status onto the record
        while the acting user is the approver — who is, by design, somebody
        who may hold no permission on this model at all: a line manager holds
        no goals group and never will. The rule refuses the write, the engine
        swallows it (it must — a decision a person really made can never be
        undone by a consumer that cannot follow its own route) and the record
        sits one rung behind for ever, with one line in the server log as the
        only trace.

        The trail is unaffected: `_chain_log` still runs as the acting user,
        so the approval log keeps the real name.
        """
        self.ensure_one()
        return super(PbGoalSetApproval, self.sudo())._chain_engine_write(state)

    def _approval_before_approve(self, request, step_key):
        """THE WEIGHTS RULE, at the one moment it can actually refuse.

        The handover named `_approval_validate` for this, and that hook is the
        SUBMIT-time check — "may this be sent in at all" — which runs before
        the manager has seen the sheet, let alone weighted it. There is no
        consumer hook inside `decide()` in the engine as it ships, and the one
        place a consumer is called after a decision (`_approval_advance`) has
        its exceptions deliberately swallowed, so raising there would record
        the approval and leave the sheet behind — R132's exact failure.

        So `pb_goals` adds a generic pre-decision seam to the engine
        (`approval_engine_ext.py`) and answers it here. A sheet waiting on its
        manager whose weights do not add up to a hundred cannot be agreed, and
        the refusal carries the arithmetic.
        """
        self.ensure_one()
        if self.state == 'submitted':
            self._require_weights()
        return True

    # THE LOCK IS NOT HERE, AND THAT IS DELIBERATE. `_approval_apply` is the
    # route's half of the story and is never called on a database where goal
    # approvals were not switched on — so a lock written here alone would mean
    # a sheet that reaches "locked" through the record's own ladder is never
    # actually frozen, silently. The consequence hangs off the STATUS instead,
    # in `pb.goal.set._after_approval_transition`, which both paths call.

    def _approval_return(self, request, reason):
        """Sent back: editable again, with the note the employee reads.

        The shim's own version writes `draft_state`; this one writes
        `returned`, which is a different row on every board (see the
        `reverse_to` note at the top of this file). The note is stored on the
        record as well as on the request, because the person who has to act on
        it reads their own goals page and not an approval inbox.
        """
        self.ensure_one()
        target = 'returned'
        if self.state != target:
            frm = self.state
            self.sudo().write({'return_note': (reason or '').strip()})
            self._chain_engine_write(target)
            self._chain_log(frm, target, reason or '')
            # THE SHIM'S OWN `_approval_return` DOES NOT CALL THIS HOOK
            # (`chain_shim.py:471-482` — every other transition does), so the
            # one place every consequence lives has to be reached by hand from
            # here or a sheet sent back through the route tells nobody.
            self._after_approval_transition(target)
        return True

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        # The HR-lead seat, filled from whoever already holds the goals
        # manager tier — so a company that has not named one explicitly still
        # has somebody to ask, rather than a route that blocks on an empty
        # seat the first time anybody uses it.
        Seed.fill_role_from_group(company, 'hr_lead', GROUP_MANAGER)
        return Seed.lay(
            company, GOALS_PROCESS_KEY, 'Goal sheet', goals_route(self.env),
            binding_note='The route everybody\'s goals follow. Their own '
                         'manager reads them and sets the weights, then the '
                         'HR lead agrees them and the sheet is locked for the '
                         'year. A business that wants a second pair of eyes '
                         'adds a rung here.',
            model_name='pb.goal.set',
            role_keys=('hr_lead',),
            reason='Set up when goal setting was switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.goal.set']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_goals: %s has no route for goal sheets',
                              company.name)
    return done
