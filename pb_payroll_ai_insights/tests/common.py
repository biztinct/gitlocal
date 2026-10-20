# -*- coding: utf-8 -*-
"""Who holds PayAI in a test — said by the fixture, never inherited.

Owner ruling 2026-10-20: on payobook.com PayAI is a role (the "AI assistant"
role in Access and delegations). `base.group_user` no longer implies
"PayAI User" there, while the module's own data still makes every internal
user one on a fresh install. A fixture that relied on the implication passed
on one database and failed on the other ("not allowed to create PayAI
Conversation").

So every fixture user who talks to PayAI is GIVEN the group here, and a test
that wants somebody without PayAI takes the implication away inside its own
transaction (`drop_staff_payai`) — both run the same on either shape of
database. Shared by pb_payai_actions' suites (it depends on this module).
"""

PAYAI_USER = 'pb_payroll_ai_insights.group_payai_user'
PAYAI_MANAGER = 'pb_payroll_ai_insights.group_payai_manager'


def payai_group_ids(env, manager=False):
    """The group ids that give a test user PayAI ("PayAI Manager" implies
    "PayAI User", so a manager needs only the one)."""
    return [env.ref(PAYAI_MANAGER if manager else PAYAI_USER).id]


def drop_staff_payai(env):
    """Make this test's database look like payobook: being an internal user
    no longer brings PayAI. Rolled back with the test's transaction (the
    group write clears the group cache; TransactionCase clears every cache on
    cleanup)."""
    payai = env.ref(PAYAI_USER)
    env.ref('base.group_user').sudo().write({'implied_ids': [(3, payai.id)]})
    return payai
