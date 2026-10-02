# -*- coding: utf-8 -*-
"""`training_day1` — the joining checklist step that assigns the induction.

THE KEY IS THE CONTRACT, not this file. `pb.journey.task._automation_handlers()`
returns a dict and a later module ADDS to it by overriding and calling `super()`
(`pb_onboarding/models/journey_ext.py:70`), which is why nothing in
`pb_onboarding` has to know this module exists. `automation_key` is a plain
Char and deliberately not a Selection, for the same reason.

THE FOUR RULES `pb_onboarding` wrote down, kept here:

  1. **Idempotent.** A person already doing the course is skipped, so a step
     that reaches this code twice assigns once. Nothing is created for a rule
     whose course they are already on.
  2. **A failure does not tick the box.** Anything that goes wrong leaves the
     step open with the reason on it, because a ticked box over an induction
     nobody was put on is worse than a step somebody has to look at.
  3. **One savepoint per person per course** (R131). A try/except is not enough
     when the thing that failed reached the database.
  4. **Off is a real state.** `pb_training.day1_auto` ships OFF, and when it is
     off the step settles with a note saying exactly what it WOULD have
     assigned — never quietly, and never by emailing four thousand people the
     first night after an install (R54).
"""

import logging

from datetime import timedelta

from odoo import _, fields, models

from .training_common import ASSIGN_OPEN, P_DAY1_AUTO, counted, flag

_logger = logging.getLogger(__name__)

DAY1_KEY = 'training_day1'


class PbJourneyTask(models.Model):
    _inherit = 'pb.journey.task'

    def _automation_handlers(self):
        handlers = super()._automation_handlers()
        handlers[DAY1_KEY] = '_auto_training_day1'
        return handlers

    def _auto_training_day1(self):
        """Put the joiner on the day-one courses. Returns a note, or False."""
        self.ensure_one()
        emp = self._employee()
        if not emp:
            return False
        Rule = self.env['pb.training.rule']
        rules = Rule._for_employee(emp)
        if not rules:
            # NOT A FAILURE. A company that has not set up an induction has
            # not got one; saying so and settling the step is the honest
            # outcome, and leaving it open for ever would be a checklist item
            # nobody can ever tick.
            return _("No day-one courses are set up yet, so nothing was "
                     "assigned.")

        courses = rules.mapped('channel_ids')
        if not flag(self.env, P_DAY1_AUTO):
            names = ', '.join(courses.sudo().mapped('name')[:6])
            _logger.info(
                'pb_training: day-one assignment is switched off — %s would '
                'have been put on %s', emp.name, names)
            return _("Day-one courses are switched off, so nothing was "
                     "assigned. With them on, %(who)s would have been put on "
                     "%(what)s.", who=emp.name or '', what=names)

        Assignment = self.env['pb.training.assignment'].sudo()
        today = fields.Date.today()
        made, already = [], []
        for rule in rules:
            due = today + timedelta(days=max(rule.due_days or 14, 1))
            for channel in rule.channel_ids:
                if Assignment.search_count([
                        ('channel_id', '=', channel.id),
                        ('employee_id', '=', emp.id),
                        ('state', 'in', ASSIGN_OPEN)]):
                    already.append(channel.name or '')
                    continue
                try:
                    with self.env.cr.savepoint():
                        Assignment.create({
                            'channel_id': channel.id,
                            'employee_id': emp.id,
                            'reason': 'day_one',
                            'due_date': due,
                            'rule_id': rule.id,
                            'company_id': (emp.company_id
                                           or rule.company_id).id,
                        })
                    made.append(channel.name or '')
                except Exception:       # noqa: BLE001 — rule 3
                    _logger.exception(
                        'pb_training: %s could not be put on course %s on '
                        'their first day', emp.id, channel.id)
                    # RULE 2: the step stays open, with the reason on it.
                    self.sudo().write({'auto_error': _(
                        "%s could not be assigned — try the step again.",
                        channel.name or '')[:250]})
                    return False
        if not made and already:
            return _("Already on %s.", ', '.join(already[:6]))
        if not made:
            return _("Nothing to assign.")
        return _("Put on %(n)s %(word)s: %(what)s.", n=len(made),
                 word=counted(len(made), _('course'), _('courses')),
                 what=', '.join(made[:6]))
