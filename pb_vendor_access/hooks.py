# -*- coding: utf-8 -*-
"""The seeded role catalogue.

WHY A HOOK AND NOT A DATA FILE. Every profile points at a group that belongs to
a DIFFERENT module, and a `<record>` with `ref="pb_pip.group_pip_head"` makes
`pb_pip` a hard dependency of this one. Six of those would make a module about
vendors and delegation refuse to install unless the whole RIZE programme is
present, which is exactly backwards: the catalogue is the part that should
shrink gracefully on a smaller build. R107's rule, reached from the same
direction — ENSURE by name, do not seed a record whose partner may not exist.

So the hook resolves each xmlid and SKIPS the ones this database has never heard
of, saying which in the log. On this tenant every one of them resolves; on a
payroll-only build about half do, and the board is correspondingly shorter
rather than broken.

IT IS IDEMPOTENT BY CONSTRUCTION, not by a stamp. `pb.role.profile.group_id`
carries a unique constraint, so the hook looks for an existing row on the group
before creating one, and never touches a row an administrator has since
reworded. R84 — `post_init_hook` fires on INSTALL only and never on `-u`, so
`ensure_catalogue()` is public and can be called again by hand or from a later
migration.

R8 — everything created here is COMPANY-LESS. `pb.role.profile` carries no
company at all, deliberately: a role means the same thing in every company, and
a catalogue that installed onto whichever company ran the upgrade would be
invisible to everybody else.

THE ABSOLUTE. `base.group_system` and `base.group_erp_manager` are not in this
list and never will be. The model refuses them independently, so a hand edit of
this file cannot get one in.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# =============================================================================
# THE CATALOGUE.
#
#   (group xmlid, area, sequence, name, what it lets someone do,
#    xmlid of the group that may SEE this row — or None for everybody)
#
# Every `name` is what somebody would say out loud, and every description is
# written to be read by the person about to press "give this to somebody".
# =============================================================================
CATALOGUE = [
    # ------------------------------------------------------------- payroll
    ('pb_hr_payroll_base.group_payroll_base_user', 'payroll', 10,
     'Payroll — can look',
     'Open pay runs and payslips and read them. Changes nothing, approves '
     'nothing, and cannot export bank files.', None),
    ('pb_hr_payroll_base.group_payroll_base_officer', 'payroll', 20,
     'Payroll officer',
     'Prepare a pay run: bring the pay data in, compute it, fix what is wrong '
     'and send it up for approval. Cannot approve their own work.', None),
    ('pb_hr_payroll_base.group_payroll_base_manager', 'payroll', 30,
     'Payroll manager',
     'Everything an officer does, plus approving a run and changing how pay is '
     'calculated. This is the role that decides what people are paid.', None),
    ('pb_hr_payroll_base.group_payroll_final_approver', 'payroll', 40,
     'Payroll approver — final',
     'The last signature before money moves. Nobody with this role should also '
     'be the person who prepared the run.', None),
    ('pb_hr_payroll_base.group_payroll_super_admin', 'payroll', 50,
     'Payroll administrator',
     'Every payroll screen in every country this system runs, including the '
     'ones that change the rules themselves. Give it to very few people.',
     None),
    ('pb_hr_payroll_base.group_payroll_analytics_user', 'payroll', 60,
     'Pay reporting — can look',
     'Read the pay reports and the cost explorer. Sees totals and trends, '
     'never edits a payslip.', None),

    # ------------------------------------------------------------ lifecycle
    ('pb_lifecycle.group_lifecycle_user', 'lifecycle', 10,
     'Joiners and leavers — can look',
     'Follow somebody\'s joining or leaving checklist and see where it has got '
     'to. Cannot start one or close a step somebody else owns.', None),
    ('pb_lifecycle.group_lifecycle_manager', 'lifecycle', 20,
     'HR lifecycle team',
     'Run joining and leaving: start a checklist, chase the steps, send the '
     'letters, and see every supplier on the vendor register.', None),
    ('pb_lifecycle.group_lifecycle_admin', 'lifecycle', 30,
     'HR lifecycle administrator',
     'Everything the lifecycle team does, plus writing the checklists and the '
     'letter templates everybody else then uses.', None),

    # --------------------------------------------------------------- people
    ('pb_assets.group_assets_user', 'people', 10,
     'Company equipment — can look',
     'See what has been given to whom — laptops, phones, accounts, passes. '
     'Cannot hand anything out or take it back.', None),
    ('pb_assets.group_assets_manager', 'people', 20,
     'Equipment team',
     'Add equipment to the register, hand it over, take it back, and deal with '
     'requests for it.', None),
    ('pb_comp_ben.group_comp_user', 'people', 30,
     'Pay packages and awards',
     'Build somebody\'s pay package, raise a one-off award and enrol people in '
     'benefits. Awards still need a head of pay to approve them.', None),
    ('pb_comp_ben.group_comp_head', 'people', 40,
     'Head of pay — packages and awards',
     'Everything above, plus approving awards and putting them into a pay run. '
     'This role decides who gets extra money.', None),
    ('pb_rnr.group_rnr_user', 'people', 50,
     'Recognition',
     'Praise a colleague and see the recognition wall. Everybody with a login '
     'can be given this one.', None),
    ('pb_rnr.group_rnr_manager', 'people', 60,
     'Recognition lead',
     'Run the award cycles, decide what the company values are, and manage the '
     'wall.', None),

    # --------------------------------------------------- growth plans (PIP)
    # RESTRICTED. Somebody being coached out of a difficulty is nobody's
    # business but theirs, their manager's and HR's — so these two rows are
    # not even LISTED to anyone outside the heads of HR.
    ('pb_pip.group_pip_user', 'people', 70,
     'Growth plans — HR',
     'Open and run somebody\'s growth plan: the coaching notes, the objectives '
     'and the dates. Highly confidential.',
     'pb_pip.group_pip_head'),
    ('pb_pip.group_pip_head', 'people', 80,
     'Growth plans — head of HR',
     'Everything above, plus seeing every growth plan in the company and '
     'making the final decision on one.',
     'pb_pip.group_pip_head'),

    # ------------------------------------------------------- money & budgets
    ('pb_budget.group_budget_viewer', 'money', 10,
     'Budget holder',
     'See the budget of the team you lead — what it was given, what it has '
     'spent, and whether that is ahead of the calendar.', None),
    ('pb_budget.group_budget_finance', 'money', 20,
     'Finance — budgets',
     'See every budget in the companies you work in and export them. Reads '
     'everything; changes nothing.', None),
    ('pb_budget.group_budget_manager', 'money', 30,
     'Budget team',
     'Everything above, plus uploading a year\'s budget, entering what HR and '
     'the office spent, and re-reading the payroll figures.', None),

    # -------------------------------------------------------------- system
    # "System" here means the administration of THIS product, never the
    # administration of the database. The two groups that do the latter are
    # excluded on purpose and the model refuses them.
    ('pb_vendor_access.group_vendor_user', 'system', 10,
     'Vendor owner',
     'See the suppliers you are named as looking after, and be the one told '
     'when one of their agreements is about to run out.', None),
    ('pb_vendor_access.group_vendor_manager', 'system', 20,
     'Vendor team',
     'Add and change suppliers, record and renew their agreements, and run the '
     'renewal check whenever you want to.', None),
    ('pb_vendor_access.group_access_manager', 'system', 30,
     'Access team',
     'Give people roles and take them away, see every hand-over of access in '
     'the company, and take any of them back. It never includes the system '
     'administrator permission.', None),
]


def ensure_catalogue(env):
    """Create the profiles whose groups exist here. Safe to run again."""
    Profile = env['pb.role.profile'].sudo()
    made = skipped = absent = 0
    for xmlid, area, sequence, name, description, visible_xmlid in CATALOGUE:
        group = env.ref(xmlid, raise_if_not_found=False)
        if not group:
            absent += 1
            _logger.info(
                'pb_vendor_access: no group %s on this database — the "%s" '
                'role is not offered', xmlid, name)
            continue
        if Profile.search_count([('group_id', '=', group.id)]):
            skipped += 1
            continue
        visible = (env.ref(visible_xmlid, raise_if_not_found=False)
                   if visible_xmlid else None)
        if visible_xmlid and not visible:
            # A restricted row whose gate is missing must NOT fall back to
            # "everybody sees it": that is the one direction this field can
            # fail in that matters.
            absent += 1
            _logger.warning(
                'pb_vendor_access: "%s" is restricted to %s, which is not on '
                'this database — the role is not offered rather than being '
                'shown to everybody', name, visible_xmlid)
            continue
        try:
            Profile.create({
                'name': name,
                'group_id': group.id,
                'description': description,
                'area': area,
                'sequence': sequence,
                'visible_group_id': visible.id if visible else False,
            })
            made += 1
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb_vendor_access: could not seed the "%s" role', name,
                exc_info=True)
    _logger.info(
        'pb_vendor_access: role catalogue — %s created, %s already there, '
        '%s not offered (their module is not installed)', made, skipped, absent)
    return {'created': made, 'existing': skipped, 'absent': absent}


def post_init_hook(env):
    """Odoo 19 hands the hook an `env`. R84 — this runs on INSTALL only."""
    if not isinstance(env, api.Environment):    # pragma: no cover - old shape
        env = api.Environment(env, SUPERUSER_ID, {})
    ensure_catalogue(env)
