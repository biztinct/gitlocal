# -*- coding: utf-8 -*-
"""The Home model and its activation checklist.

`pb.dashboard` is one AbstractModel. Its ONE data call, `get_home_data()`,
lives in `home_data.py` (HOME P1); this file keeps the model itself and the
activation checklist both of them were built around. HOME P3 deleted the old
payload (`get_dashboard_data`, its month strip and its line-table month
figures): every figure on Home now comes from the stored pay run totals.

TWO RULES GOVERN THIS FILE, and both are about honesty.

1. NO FABRICATED NUMBER, EVER. A brand-new tenant sees zeros and a helpful
   empty state; it never sees a company that does not exist. The legacy
   analytics fallback that used to fill these in was a hard-coded sample dict
   and it reached a real customer's screen.

2. NO HARD DEPENDENCY ON ANOTHER COCKPIT. The manifest declares `web`,
   `om_hr_payroll`, `pb_hr_payroll_base` and the icon kit and nothing else.
   The activation checklist below asks questions of the learning module and of
   the import module, and both of those questions are asked through
   `optional()`, which answers "not on this database" instead of raising.
   There is no python import of either module anywhere in here, and there
   must never be one: this dashboard is the first screen of every tenant,
   including the lean ones.
"""
from odoo import api, models

# The two scenarios the activation checklist watches, under the namespace
# `learn.progress` stores them in (pb_learn/models/learn_progress.py
# SCENARIO_PREFIX). Strings, not imports — see rule 2 above.
SCENARIO_PREFIX = 'scenario:'
SC_WELCOME = 'sc_welcome'
SC_PAYRUN = 'sc_payrun'


class PbDashboard(models.AbstractModel):
    _name = 'pb.dashboard'
    _description = 'Payobook Dashboard data provider'

    @api.model
    def _activation(self, employees, contracts, runs, optional):
        """The activation checklist `get_home_data` returns.

        HOME P1 moved this block here unchanged from the old payload (deleted
        in HOME P3). `optional` is the caller's registry guard, passed in so
        every foreign read below still sits inside an `optional()` call
        (test_04).
        """
        env = self.env
        cdom = [('company_id', 'in', env.companies.ids)]
        # ---- Activation checklist (LEARNOS Phase 3) ----
        # FIVE STEPS, FIVE REAL COUNTS. Nothing here is remembered in a flag,
        # inferred from a button press or carried in a browser: every item
        # reports the state of the database, so a step somebody finished in
        # another tab is already ticked when this loads, and a step nobody has
        # done cannot be ticked by pressing its button and coming back.
        #
        # The panel is shown while activation is incomplete and disappears for
        # good once the tenant has a pay run — which is also item 5, so the
        # last tick and the last render are the same event.
        def scenario_state(key):
            """'not_started' | 'in_progress' | 'done', for THIS learner.

            LEARNOS Phase 6 widened this from a boolean. A walkthrough somebody
            STARTED and did not finish used to read here as untouched, so the
            checklist said "Watch the tour" to a person who was four steps into
            it — the one case where the row could tell them something they did
            not already know. One row per learner per key (learn.progress has a
            unique constraint on the pair), so the first row is the answer.
            """
            rows = optional('learn.progress', lambda: env['learn.progress'].search_read(
                [('user_id', '=', env.uid), ('key', '=', SCENARIO_PREFIX + key)],
                ['state'], limit=1))
            return (rows[0]['state'] if rows else None) or 'not_started'

        def scenario_row(item_key, scenario_key):
            state = scenario_state(scenario_key)
            return {'key': item_key, 'done': state == 'done', 'state': state}

        # Is the learning module on this database at all? The same registry
        # probe `optional()` uses, asked once, because it decides whether the
        # two learning steps are OFFERED rather than only whether they can be
        # read. A step whose predicate can never be satisfied is a step that
        # sits unticked forever, which is worse than a shorter list.
        learn_here = 'learn.progress' in env

        # HEADCOUNT > 1, NOT > 0. The golden template ships the admin's
        # `hr.employee` row (id 1, renamed per tenant), and provisioning does
        # not create it — so a tenant that has never added anybody still
        # reports one employee. Contracts carry the "is this tenant empty"
        # question everywhere else in this file for the same reason.
        batches = optional('hr.payroll.import.batch',
                           lambda: env['hr.payroll.import.batch'].search_count(cdom))
        activation_items = []
        if learn_here:
            activation_items.append(scenario_row('meet', SC_WELCOME))
        activation_items.append({'key': 'employee', 'done': employees > 1})
        activation_items.append({'key': 'import', 'done': bool(contracts) or bool(batches)})
        if learn_here:
            activation_items.append(scenario_row('practice', SC_PAYRUN))
        activation_items.append({'key': 'real', 'done': runs > 0})
        return {'show': not runs, 'items': activation_items}
