# -*- coding: utf-8 -*-
"""`goals_kickoff` — the joining-checklist step that opens somebody's goals.

THE KEY IS THE CONTRACT, not this file. `pb.journey.task._automation_handlers()`
returns a dict and a later module ADDS to it by overriding and calling `super()`
(`pb_onboarding/models/journey_ext.py:70`), which is why nothing in
`pb_onboarding` has to know this module exists. `automation_key` is a plain
Char and deliberately not a Selection, for exactly the same reason.

THE FOUR RULES `pb_onboarding` wrote down, kept here:

  1. **Idempotent.** A person who already has a sheet in the open cycle is left
     alone, so a step that reaches this code twice opens one sheet. Cases can
     be opened twice (R30) and this one will be.
  2. **A failure does not tick the box.** Anything that goes wrong leaves the
     step open with the reason on it: a ticked box over goals nobody was asked
     for is worse than a step somebody has to look at.
  3. **One savepoint per piece of work** (R131). A try/except is not enough
     when the thing that failed reached the database.
  4. **Off is a real state.** `pb_goals.kickoff_auto` ships ON — it is the one
     automation in this module that ships on, because it only ever touches one
     new joiner at a time — and when it is off the step settles with a note
     saying exactly what it WOULD have done (R54).

NO OPEN CYCLE IS NOT A FAILURE. A company that has not set its goal year up has
not got one; saying so and settling the step is the honest outcome, and leaving
it open for ever would be a checklist item nobody can ever tick.
"""

import logging

from datetime import timedelta

from odoo import _, fields, models

from .goals_common import P_KICKOFF_AUTO, flag

_logger = logging.getLogger(__name__)

GOALS_KICKOFF_KEY = 'goals_kickoff'


class PbJourneyTask(models.Model):
    _inherit = 'pb.journey.task'

    def _automation_handlers(self):
        handlers = super()._automation_handlers()
        handlers[GOALS_KICKOFF_KEY] = '_auto_goals_kickoff'
        return handlers

    def _auto_goals_kickoff(self):
        """Open the joiner's goal sheet. Returns a note, or False."""
        self.ensure_one()
        employee = self._employee()
        if not employee:
            return False
        company = employee.company_id or self.env.company
        Cycle = self.env['pb.goal.cycle']
        cycle = Cycle.open_cycle_for(company.id)
        if not cycle:
            # RULE: not a failure. Settle the step and say so.
            return _("No goal year is open for %s yet, so no goal sheet was "
                     "opened. Open one and the next joiner gets theirs "
                     "automatically.", company.name or '')

        Set = self.env['pb.goal.set'].sudo()
        existing = Set.search([('employee_id', '=', employee.id),
                               ('cycle_id', '=', cycle.id)], limit=1)
        if existing:
            return _("%(who)s already has a goal sheet for %(cycle)s, due "
                     "%(due)s.", who=employee.name or '',
                     cycle=cycle.name or '', due=existing.deadline or '')

        deadline = fields.Date.today() + timedelta(
            days=max(cycle.submission_days or 14, 1))
        if not flag(self.env, P_KICKOFF_AUTO):
            _logger.info('pb_goals: the kick-off is switched off — %s would '
                         'have been given a goal sheet for %s due %s',
                         employee.name, cycle.name, deadline)
            return _("Opening goals automatically is switched off, so nothing "
                     "was opened. With it on, %(who)s would have been given a "
                     "goal sheet for %(cycle)s due %(due)s.",
                     who=employee.name or '', cycle=cycle.name or '',
                     due=deadline)

        try:
            # RULE 3 — the savepoint, not the bare try/except.
            with self.env.cr.savepoint():
                goal_set = Set.create({
                    'employee_id': employee.id,
                    'cycle_id': cycle.id,
                    'deadline': deadline,
                    'company_id': company.id,
                })
        except Exception:                   # noqa: BLE001 — rule 2
            _logger.exception('pb_goals: %s could not be given a goal sheet',
                              employee.id)
            self.sudo().write({'auto_error': _(
                "A goal sheet could not be opened — try the step again."
            )[:250]})
            return False

        # The email and the to-do are PAPERWORK and each has its own guard:
        # a sheet that exists and an email that did not go is a small problem,
        # and a step left open over a sheet that DOES exist is a bigger one
        # (R104 — notification legs never report a success as a failure).
        goal_set._notify_kickoff()
        seed = self.env.get('pb.demo.seed')
        if seed is not None:
            try:
                seed.register(goal_set, 'Goal sheet opened on joining')
            except Exception:               # noqa: BLE001 — a register is not
                _logger.warning('pb_goals: the new goal sheet could not be '
                                'registered as demo data', exc_info=True)
        return _("Goal sheet opened for %(cycle)s. %(who)s has until %(due)s "
                 "to write their goals.", cycle=cycle.name or '',
                 who=employee.name or '', due=deadline)
