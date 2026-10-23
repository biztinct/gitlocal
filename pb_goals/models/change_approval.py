# -*- coding: utf-8 -*-
"""A request to change agreed goals travels the route the business published.

THE SAME TWO PEOPLE, ON PURPOSE. The manager and the HR lead agreed the goals
in April; they are the two who agree a change to them in June. A different set
of approvers for a change would make the change easier or harder than the
original, and either way somebody would learn which door to use.

WHAT AN APPROVER IS AGREEING TO is the PROPOSAL and the REASON — so those two
are the revision stamp. R202's lesson applies here as sharply as it did to the
goal sheet itself: nothing an approver is meant to change on the way through
may be in the stamp, and there is nothing on a change request an approver is
meant to change at all. They agree it, send it back, or turn it down.

NO `date_field` (R192). The shim hands the named date to
`responsibility.resolve(..., on_date)`, so naming one asks who held the HR-lead
seat on that date. A change request's dates are the goal year's, which are
months old by construction — and an approval asks who holds the seat NOW,
because now is when the decision is being made.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .goals_common import (
    CHANGE_KIND_LABEL, GROUP_MANAGER, P_ESCALATE_DAYS, P_SLA_DAYS, number,
)

_logger = logging.getLogger(__name__)

CHANGE_PROCESS_KEY = 'goal_change'

#: `reverse_to` NAMES `draft`, unlike the goal sheet's own route. A goal sheet
#: sent back is a thing somebody is expected to rewrite and "sent back" is a
#: row a board has to show; a change request sent back is simply a request
#: still being written, and inventing a sixth status for it would put a word on
#: a screen that means nothing extra.
register_chain(
    'pb.goal.change', CHANGE_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_ok', 'approved'),
    draft_state='draft',
    refuse_state='refused',
    reverse_to=('draft',),
    employee_field='employee_id',
)


def change_route(env=None):
    """The same two rungs and the same two dials as the goal sheet's own."""
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


class PbGoalChangeApproval(models.Model):
    _inherit = 'pb.goal.change'

    _approval_process_key = CHANGE_PROCESS_KEY

    # ==================================================================
    #  What the engine is told
    # ==================================================================
    def _chain_title(self):
        self.ensure_one()
        return _("Goal change · %(who)s · %(what)s",
                 who=self.employee_id.sudo().name or '',
                 what=self.summary or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        """Read AS THE SYSTEM (AM40) — the maker is the employee."""
        self.ensure_one()
        record = self.sudo()
        sheet = record.set_id
        return {
            'kind': {'value': CHANGE_KIND_LABEL.get(record.kind, ''),
                     'unit': ''},
            'goals': {'value': int(sheet.goal_count or 0),
                      'unit': _('goals')},
            'weight_total': {'value': float(sheet.weight_total or 0.0),
                             'unit': _('out of 100')},
            'months_left': {'value': record._months_left(),
                            'unit': _('months')},
            'department': {'value': record.department_id.name or '',
                           'unit': ''},
            'changed_before': {'value': int(len(sheet.audit_ids)),
                               'unit': _('changes')},
        }

    def _months_left(self):
        """How much of the year is left to do the changed goal in.

        THE ONE FACT A ROUTE MIGHT ACTUALLY BRANCH ON. Changing a goal in May
        and changing it in February are different requests, and a business
        that wants the second one to need an extra pair of eyes can say so on
        the route without anybody writing code.
        """
        self.ensure_one()
        from odoo import fields as odoo_fields
        from .checkin import months_between
        end = self.sudo().cycle_id.date_end
        if not end:
            return 0
        return max(0, months_between(odoo_fields.Date.today(), end))

    @api.model
    def _chain_fact_specs(self):
        return {
            'kind': {'type': 'char', 'label': _('What kind of change')},
            'goals': {'type': 'int', 'label': _('How many goals')},
            'weight_total': {'type': 'decimal',
                             'label': _('What the weights add up to')},
            'months_left': {'type': 'int',
                            'label': _('Months left in the goal year')},
            'department': {'type': 'char',
                           'label': _('Which part of the business')},
            'changed_before': {'type': 'int',
                               'label': _('Changes already made this year')},
        }

    def _chain_revision_values(self):
        """The proposal and the reason. NEVER `write_date` (AM32).

        And never anything an approver touches on the way through (R202) —
        which on this model is nothing at all, because a change request is a
        proposal somebody says yes or no to rather than a document they edit.
        """
        self.ensure_one()
        record = self.sudo()
        return {
            'kind': record.kind or '',
            'goal': record.goal_id.id or 0,
            'payload': record.payload_json or '',
            'reason': (record.reason or '').strip(),
        }

    def _approval_detail(self, request):
        """What the approver reads without opening anything (AM49)."""
        self.ensure_one()
        record = self.sudo()
        sheet = record.set_id
        chips = [
            {'label': _('Goal year'), 'value': sheet.cycle_id.name or ''},
            {'label': _('What kind'), 'value': record._kind_word()},
            {'label': _('Asked by'),
             'value': record.requested_by_id.name or ''},
        ]
        if record.department_id:
            chips.append({'label': _('Part of the business'),
                          'value': record.department_id.name or ''})
        if sheet.cycle_id.date_end:
            chips.append({'label': _('Year ends'),
                          'value': str(sheet.cycle_id.date_end)})
        payload = record.payload()
        rows = []
        # A DRAWER ROW IS A DICT — `{head, sub, cells}` — AND A LIST IS
        # SILENTLY DISCARDED (`pb_approval_config/models/inbox_facade.py:598`
        # skips anything that is not a dict). The detail is dropped entirely
        # only when there are no chips either, so a consumer that hands it
        # lists gets a drawer with a title, chips and a note and NO TABLE,
        # which reads as "there was nothing to show". Found live on this very
        # request, and B1's goal-sheet drawer had the same shape.
        if record.kind == 'reweight':
            weights = payload.get('weights') or {}
            for goal in sheet._all_goals().sorted(lambda g: (g.sequence,
                                                             g.id)):
                rows.append({
                    'head': goal.title or '',
                    'cells': [
                        '%s%%' % int(round(goal.weight or 0)),
                        '%s%%' % int(round(float(
                            weights.get(str(goal.id), 0)))),
                    ]})
            columns = [_('Goal'), _('Now'), _('Would become')]
        else:
            goal = record.goal_id
            before = record._goal_snapshot(goal) if goal else {}
            for key, label in (('title', _('What it says')),
                               ('description', _('Why it matters')),
                               ('date_end', _('Done by'))):
                was = str(before.get(key) or '')
                now = str(payload.get(key) or was)
                if record.kind == 'drop':
                    now = _('Dropped')
                if was or now:
                    rows.append({'head': label, 'cells': [was, now]})
            columns = [_('What'), _('Now'), _('Would become')]
        return {'title': _('The change being asked for'),
                'columns': columns, 'rows': rows, 'chips': chips,
                'note': record.reason or ''}

    # ==================================================================
    #  The rungs, as they land on the record
    # ==================================================================
    def _chain_engine_write(self, state):
        """R132 — the middle of a route is written AS THE APPROVER.

        The manager deciding this holds no goals group by definition, so the
        record rule refuses their write, the engine swallows it (it must) and
        the request sits one rung behind for ever with one line in the server
        log. This route has TWO intermediate statuses, which is exactly the
        shape R132 says needs it.
        """
        self.ensure_one()
        return super(PbGoalChangeApproval, self.sudo())._chain_engine_write(
            state)

    def _approval_validate(self):
        """The submit-time check — "may this be sent in at all".

        THE RIGHT HOOK FOR THIS ONE, unlike the goal sheet's weights rule
        (R201, which had to grow a new seam because the manager sets the
        weights AFTER the sheet is sent in). Everything a change request has
        to be true about — the goal still exists, the year is still open, the
        weights still add up — is true or false BEFORE anybody is asked, so
        the honest moment to refuse is the moment somebody presses Send.

        `_approval_validate` takes no arguments on this build
        (`chain_shim.py:401`); a signature with a `request` in it is an
        override that never overrides anything.
        """
        self.ensure_one()
        self._check_still_possible()
        return super()._approval_validate()

    def _approval_reject(self, request, reason):
        """Turned down: the reason goes ON THE RECORD, not only on the request.

        THE PERSON WHO HAS TO ACT ON IT READS THEIR OWN GOALS PAGE and not an
        approval inbox. Under a published route the press becomes a decision
        and the engine keeps the reason on the REQUEST; the record's own
        `refuse_note` then stays empty, so `/my/goals` shows "Turned down"
        with nothing beside it and the refusal email has nothing to quote —
        which is the same as not telling anybody.

        Found live on the first refusal: the manager wrote a perfectly good
        sentence and it reached nothing a person would look at. Written here,
        BEFORE `super()`, because `super()` is what fires
        `_after_approval_transition` and that is what sends the email.
        """
        self.ensure_one()
        written = (reason or '').strip()
        if written and not self.sudo().refuse_note:
            self.sudo().write({'refuse_note': written})
        return super()._approval_reject(request, reason)

    # THE CHANGE IS NOT CARRIED OUT HERE, AND THAT IS DELIBERATE (R204).
    # `_approval_apply` is the route's half of the story and is never called
    # on a database where goal-change approvals were not switched on — so a
    # change written here alone would be agreed on the record's own ladder and
    # silently never happen. It hangs off the STATUS, in
    # `pb.goal.change._after_approval_transition`, which both paths call.

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', GROUP_MANAGER)
        return Seed.lay(
            company, CHANGE_PROCESS_KEY, 'Goal change', change_route(self.env),
            binding_note='What happens when somebody asks to change goals '
                         'that have already been agreed. The same two people '
                         'who agreed them in the first place: their own '
                         'manager, then the HR lead. A business that wants '
                         'changes to be harder than the original adds a rung '
                         'here.',
            model_name='pb.goal.change',
            role_keys=('hr_lead',),
            reason='Set up when goal setting was switched on')


def seed_all_changes(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.goal.change']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_goals: %s has no route for goal changes',
                              company.name)
    return done
