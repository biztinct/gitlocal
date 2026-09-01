# -*- coding: utf-8 -*-
"""The seeded ability catalogue, and the roles built out of it.

WHY A HOOK AND NOT A DATA FILE. Every ability points at a permission group that
belongs to a DIFFERENT module, and a `<record>` with `ref="pb_pip.group_pip_head"`
makes `pb_pip` a hard dependency of this one. A dozen of those would make a
module about vendors and delegation refuse to install unless the whole programme
is present, which is exactly backwards: the catalogue is the part that should
shrink gracefully on a smaller build. R107's rule, reached from the same
direction — ENSURE by name, do not seed a record whose partner may not exist.

So the hook resolves each xmlid and SKIPS the ones this database has never heard
of, saying which in the log. On the main tenant every one of them resolves; on a
payroll-only build about half do, and the board is correspondingly shorter
rather than broken.

TWO LAYERS, SEEDED IN ORDER.

  * **Abilities** — the small units. One sentence, an area, and the one or more
    permissions that sentence really costs. Every role this product ships is
    made of these, and twelve more are seeded that no role uses YET: they are
    the permissions the screens actually gate on that the role catalogue never
    covered, and they are here so that building a role out of them is a job for
    somebody with a mouse rather than for a deploy.
  * **Roles** — the bundles. Same names, same sentences, same areas and
    sequences as before bundles existed. Each one now names its abilities
    instead of a single group.

IT IS IDEMPOTENT BY CONSTRUCTION, not by a stamp. An ability is found by its
`technical_key`, which carries a unique constraint; a role is found by the
ability it is built from, or — on a database seeded before bundles existed — by
the single group it used to carry. Nothing that an administrator has since
reworded is touched, and a second run creates nothing.

R84 — `post_init_hook` fires on INSTALL ONLY and never on `-u`, so
`ensure_catalogue()` is public and every version that adds to the catalogue ships
a migration that calls it. That is not a convenience: without it, an upgrade that
adds abilities adds them to a fresh install and to nothing else, and the
difference is invisible until somebody goes looking for a role that is not there.

R8 — everything created here is COMPANY-LESS. Neither model carries a company,
deliberately: a role means the same thing in every company, and a catalogue that
installed onto whichever company ran the upgrade would be invisible to everybody
else.

THE ABSOLUTE. `base.group_system` and `base.group_erp_manager` are not in this
file and never will be — nor is any group that implies one. Both models refuse
them independently and over the whole implied closure, so a hand edit of this
file cannot get one in.
"""

import logging
import re
import unicodedata

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# =============================================================================
# THE ROLES.
#
#   (ability keys, area, sequence, name, what it lets someone do,
#    xmlid of the group that may SEE this row — or None for everybody)
#
# Every `name` is what somebody would say out loud, and every description is
# written to be read by the person about to press "give this to somebody".
# =============================================================================
CATALOGUE = [
    # ------------------------------------------------------------- payroll
    (('payroll-read',), 'payroll', 10,
     'Payroll — can look',
     'Open pay runs and payslips and read them. Changes nothing, approves '
     'nothing, and cannot export bank files.', None),
    (('payroll-officer',), 'payroll', 20,
     'Payroll officer',
     'Prepare a pay run: bring the pay data in, compute it, fix what is wrong '
     'and send it up for approval. Cannot approve their own work.', None),
    (('payroll-manager',), 'payroll', 30,
     'Payroll manager',
     'Everything an officer does, plus approving a run and changing how pay is '
     'calculated. This is the role that decides what people are paid.', None),
    (('payroll-final-approver',), 'payroll', 40,
     'Payroll approver — final',
     'The last signature before money moves. Nobody with this role should also '
     'be the person who prepared the run.', None),
    (('payroll-administrator',), 'payroll', 50,
     'Payroll administrator',
     'Every payroll screen in every country this system runs, including the '
     'ones that change the rules themselves. Give it to very few people.',
     None),
    (('pay-reporting-read',), 'payroll', 60,
     'Pay reporting — can look',
     'Read the pay reports and the cost explorer. Sees totals and trends, '
     'never edits a payslip.', None),

    # ------------------------------------------------------------ lifecycle
    (('lifecycle-read',), 'lifecycle', 10,
     'Joiners and leavers — can look',
     'Follow somebody\'s joining or leaving checklist and see where it has got '
     'to. Cannot start one or close a step somebody else owns.', None),
    (('lifecycle-team',), 'lifecycle', 20,
     'HR lifecycle team',
     'Run joining and leaving: start a checklist, chase the steps, send the '
     'letters, and see every supplier on the vendor register.', None),
    (('lifecycle-admin',), 'lifecycle', 30,
     'HR lifecycle administrator',
     'Everything the lifecycle team does, plus writing the checklists and the '
     'letter templates everybody else then uses.', None),

    # --------------------------------------------------------------- people
    (('equipment-read',), 'people', 10,
     'Company equipment — can look',
     'See what has been given to whom — laptops, phones, accounts, passes. '
     'Cannot hand anything out or take it back.', None),
    (('equipment-team',), 'people', 20,
     'Equipment team',
     'Add equipment to the register, hand it over, take it back, and deal with '
     'requests for it.', None),
    (('packages-and-awards',), 'people', 30,
     'Pay packages and awards',
     'Build somebody\'s pay package, raise a one-off award and enrol people in '
     'benefits. Awards still need a head of pay to approve them.', None),
    (('packages-and-awards-head',), 'people', 40,
     'Head of pay — packages and awards',
     'Everything above, plus approving awards and putting them into a pay run. '
     'This role decides who gets extra money.', None),
    (('recognition',), 'people', 50,
     'Recognition',
     'Praise a colleague and see the recognition wall. Everybody with a login '
     'can be given this one.', None),
    (('recognition-lead',), 'people', 60,
     'Recognition lead',
     'Run the award cycles, decide what the company values are, and manage the '
     'wall.', None),

    # --------------------------------------------------- growth plans (PIP)
    # RESTRICTED. Somebody being coached out of a difficulty is nobody's
    # business but theirs, their manager's and HR's — so these two rows are
    # not even LISTED to anyone outside the heads of HR.
    (('growth-plans-hr',), 'people', 70,
     'Growth plans — HR',
     'Open and run somebody\'s growth plan: the coaching notes, the objectives '
     'and the dates. Highly confidential.',
     'pb_pip.group_pip_head'),
    (('growth-plans-head',), 'people', 80,
     'Growth plans — head of HR',
     'Everything above, plus seeing every growth plan in the company and '
     'making the final decision on one.',
     'pb_pip.group_pip_head'),

    # ------------------------------------------------------- money & budgets
    (('budget-holder',), 'money', 10,
     'Budget holder',
     'See the budget of the team you lead — what it was given, what it has '
     'spent, and whether that is ahead of the calendar.', None),
    (('budget-finance',), 'money', 20,
     'Finance — budgets',
     'See every budget in the companies you work in and export them. Reads '
     'everything; changes nothing.', None),
    (('budget-team',), 'money', 30,
     'Budget team',
     'Everything above, plus uploading a year\'s budget, entering what HR and '
     'the office spent, and re-reading the payroll figures.', None),

    # -------------------------------------------------------------- system
    # "System" here means the administration of THIS product, never the
    # administration of the database. The two groups that do the latter are
    # excluded on purpose and both models refuse them.
    (('vendor-owner',), 'system', 10,
     'Vendor owner',
     'See the suppliers you are named as looking after, and be the one told '
     'when one of their agreements is about to run out.', None),
    (('vendor-team',), 'system', 20,
     'Vendor team',
     'Add and change suppliers, record and renew their agreements, and run the '
     'renewal check whenever you want to.', None),
    (('access-team',), 'system', 30,
     'Access team',
     'Give people roles and take them away, see every hand-over of access in '
     'the company, and take any of them back. It never includes the system '
     'administrator permission.', None),
]

# =============================================================================
# THE PERMISSIONS EACH SEEDED ROLE USED TO HAND OUT, ONE PER ROLE.
#
# These are the abilities that back the roles above. They are described by the
# ROLE'S own words rather than by a second set: the ability and the role are the
# same thing on this database today, and two sentences for one fact is how they
# come to disagree.
# =============================================================================
ROLE_ABILITY_GROUPS = {
    'payroll-read': ('pb_hr_payroll_base.group_payroll_base_user',),
    'payroll-officer': ('pb_hr_payroll_base.group_payroll_base_officer',),
    'payroll-manager': ('pb_hr_payroll_base.group_payroll_base_manager',),
    'payroll-final-approver': (
        'pb_hr_payroll_base.group_payroll_final_approver',),
    'payroll-administrator': ('pb_hr_payroll_base.group_payroll_super_admin',),
    'pay-reporting-read': (
        'pb_hr_payroll_base.group_payroll_analytics_user',),

    'lifecycle-read': ('pb_lifecycle.group_lifecycle_user',),
    'lifecycle-team': ('pb_lifecycle.group_lifecycle_manager',),
    'lifecycle-admin': ('pb_lifecycle.group_lifecycle_admin',),

    'equipment-read': ('pb_assets.group_assets_user',),
    'equipment-team': ('pb_assets.group_assets_manager',),
    'packages-and-awards': ('pb_comp_ben.group_comp_user',),
    'packages-and-awards-head': ('pb_comp_ben.group_comp_head',),
    'recognition': ('pb_rnr.group_rnr_user',),
    'recognition-lead': ('pb_rnr.group_rnr_manager',),
    'growth-plans-hr': ('pb_pip.group_pip_user',),
    'growth-plans-head': ('pb_pip.group_pip_head',),

    'budget-holder': ('pb_budget.group_budget_viewer',),
    'budget-finance': ('pb_budget.group_budget_finance',),
    'budget-team': ('pb_budget.group_budget_manager',),

    'vendor-owner': ('pb_vendor_access.group_vendor_user',),
    'vendor-team': ('pb_vendor_access.group_vendor_manager',),
    'access-team': ('pb_vendor_access.group_access_manager',),
}

# =============================================================================
# THE ABILITIES NO ROLE USES YET.
#
#   (technical_key, area, sequence, name, the honest sentence, (group xmlids…))
#
# These are the permissions the screens on this product ACTUALLY gate on and
# that the role catalogue never covered — which is why somebody given only roles
# has been seeing a shorter rail than the role they hold implies. Nothing is
# granted by seeding them: an ability that no role names hands nobody anything.
# They are here so that the first person who needs "can read the audit trail" as
# part of a role can tick it instead of waiting for a release.
#
# Each name starts with the verb, because a list of these is read as a list of
# things somebody will be able to DO.
# =============================================================================
NEW_ABILITIES = [
    # ------------------------------------------------------------- payroll
    ('payroll-ops-work', 'payroll', 100,
     'Work the payroll desk',
     'Open pay runs and payslips on the core payroll screens and work through '
     'them day to day. It stops short of approving a run and of changing the '
     'rules that calculate pay.',
     ('om_hr_payroll.group_hr_payroll_user',)),
    ('payroll-ops-manage', 'payroll', 110,
     'Manage the payroll desk',
     'Run the core payroll screens end to end: approve a run, reopen one that '
     'is wrong, and change the rules that calculate pay. It carries nothing '
     'outside pay itself.',
     ('om_hr_payroll.group_hr_payroll_manager',)),
    ('pay-reporting-manage', 'payroll', 120,
     'Manage pay reporting',
     'Build, change and export the pay reports everybody else reads. It reads '
     'payslips; it never edits one and it never approves a run.',
     ('pb_hr_payroll_base.group_payroll_analytics_manager',)),
    ('integrations-run', 'payroll', 130,
     'Run connected-system syncs',
     'Start the syncs that bring people and pay data in from a connected '
     'system, and watch how they went. It moves data; it approves nothing and '
     'pays nobody.',
     ('pb_hr_payroll_base.group_payroll_integration_user',)),
    ('formula-view', 'payroll', 140,
     'Open pay formulas and read them',
     'Open a pay formula and see exactly how a number on a payslip was worked '
     'out. Changes nothing.',
     ('pb_hr_payroll_formula.group_formula_user',)),
    ('formula-build', 'payroll', 150,
     'Build and change pay formulas',
     'Write and change the formulas that calculate pay, and test them against '
     'a real run before anybody is paid by them. It does not approve the run.',
     ('pb_hr_payroll_formula.group_formula_manager',)),
    ('formula-admin', 'payroll', 160,
     'Administer the formula engine',
     'Everything above, plus the settings the formulas themselves run on and '
     'the tools that repair a broken one. Give it to very few people.',
     ('pb_hr_payroll_formula.group_formula_admin',)),

    # --------------------------------------------------------------- people
    ('time-attendance-work', 'people', 100,
     'Work time and attendance',
     'See and correct people\'s clock-in and clock-out records. It cannot '
     'change the working-hours rules those records are judged against.',
     ('hr_attendance.group_hr_attendance_officer',)),
    ('time-attendance-manage', 'people', 110,
     'Manage time and attendance',
     'Everything above, plus setting the working-hours rules and signing the '
     'month off so payroll can use it.',
     ('hr_attendance.group_hr_attendance_manager',)),

    # ------------------------------------------------------- money & budgets
    ('workforce-plan', 'money', 100,
     'See workforce plans',
     'Read the headcount plans and what they would cost. Adds nothing to a '
     'plan and approves nothing.',
     ('pb_hr_payroll_demand.group_pb_workforce_user',)),
    ('workforce-plan-manage', 'money', 110,
     'Plan and approve the workforce',
     'Build the headcount plans, put a request forward and approve one. This '
     'is what decides how many people a team may hire.',
     ('pb_hr_payroll_demand.group_pb_workforce_manager',
      'pb_hr_payroll_demand.group_pb_workforce_admin')),

    # -------------------------------------------------------------- system
    ('audit-read', 'system', 100,
     'Read the audit trail',
     'Read the record of who changed what, and when, across the whole system. '
     'Reads only — the trail itself can never be edited or deleted by anybody.',
     ('biz_audit_trail.group_audit_reader',)),
]


def _role_backed_abilities():
    """One ability per seeded role, in the role's own words."""
    out = []
    for keys, area, sequence, name, description, _visible in CATALOGUE:
        for key in keys:
            groups = ROLE_ABILITY_GROUPS.get(key)
            if groups:
                out.append((key, area, sequence, name, description, groups))
    return out


#: Everything seeded, abilities first. The role-backed ones keep their role's
#: sequence so the two lists read in the same order.
ABILITIES = _role_backed_abilities() + NEW_ABILITIES


def _slug(text, fallback='ability'):
    """A stable key out of a name an administrator typed.

    Accents folded rather than stripped (R28/R78): "Chế độ" must not become
    "ch-", which is a key that collides with the next three roles like it.
    """
    raw = unicodedata.normalize('NFKD', str(text or ''))
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    raw = raw.replace('đ', 'd').replace('Đ', 'D')
    raw = re.sub(r'[^a-zA-Z0-9]+', '-', raw).strip('-').lower()
    return raw or fallback


# =========================================================================
#  seeding
# =========================================================================
def ensure_abilities(env):
    """Create the abilities whose permissions exist here. Safe to run again."""
    Ability = env['pb.role.ability'].sudo().with_context(active_test=False)
    made = skipped = absent = 0
    for key, area, sequence, name, description, group_xmlids in ABILITIES:
        if Ability.search_count([('technical_key', '=', key)]):
            skipped += 1
            continue
        group_ids = []
        missing = []
        for xmlid in group_xmlids:
            group = env.ref(xmlid, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
            else:
                missing.append(xmlid)
        if not group_ids:
            absent += 1
            _logger.info(
                'pb_vendor_access: no permission %s on this database — the '
                '"%s" ability is not offered', ', '.join(group_xmlids), name)
            continue
        if missing:
            # Part of it is here. Seeding what exists is right — the ability is
            # still real — but a shorter ability than the sentence promises is
            # exactly the kind of quiet difference that has to be logged.
            _logger.warning(
                'pb_vendor_access: the "%s" ability is seeded WITHOUT %s, '
                'which is not on this database', name, ', '.join(missing))
        try:
            Ability.create({
                'technical_key': key,
                'name': name,
                'description': description,
                'area': area,
                'sequence': sequence,
                'group_ids': [(6, 0, group_ids)],
            })
            made += 1
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb_vendor_access: could not seed the "%s" ability', name,
                exc_info=True)
    _logger.info(
        'pb_vendor_access: ability catalogue — %s created, %s already there, '
        '%s not offered (their module is not installed)', made, skipped, absent)
    return {'created': made, 'existing': skipped, 'absent': absent}


def _existing_profile(env, ability_keys):
    """The role already standing for these abilities, whichever era it is from.

    Two ways in, because this runs on databases seeded before bundles existed
    and on databases seeded after. Before: the role carries the single group the
    ability wraps, and that column is unique, so it is an exact key. After: the
    role names the ability.
    """
    Profile = env['pb.role.profile'].sudo().with_context(active_test=False)
    legacy_ids = []
    for key in ability_keys:
        for xmlid in ROLE_ABILITY_GROUPS.get(key, ()):
            group = env.ref(xmlid, raise_if_not_found=False)
            if group:
                legacy_ids.append(group.id)
    if legacy_ids:
        found = Profile.search([('group_id', 'in', legacy_ids)], limit=1)
        if found:
            return found
    abilities = env['pb.role.ability'].by_keys(list(ability_keys))
    if abilities:
        found = Profile.search([('ability_ids', 'in', abilities.ids)], limit=1)
        if found:
            return found
    return Profile.browse()


def ensure_catalogue(env):
    """Seed the abilities, then the roles built out of them. Safe to run again.

    It also LINKS: a role seeded before bundles existed has its abilities
    attached here rather than in a one-shot script, so the same call fixes a
    fresh install, an upgrade, and a database somebody restored from a backup
    taken in between.
    """
    abilities = ensure_abilities(env)
    Profile = env['pb.role.profile'].sudo()
    made = skipped = absent = linked = 0
    for keys, area, sequence, name, description, visible_xmlid in CATALOGUE:
        wanted = env['pb.role.ability'].by_keys(list(keys))
        if not wanted:
            absent += 1
            _logger.info(
                'pb_vendor_access: none of the abilities %s are on this '
                'database — the "%s" role is not offered',
                ', '.join(keys), name)
            continue
        existing = _existing_profile(env, keys)
        if existing:
            if not existing.ability_ids:
                try:
                    existing.write({'ability_ids': [(6, 0, wanted.ids)]})
                    linked += 1
                except Exception:               # noqa: BLE001
                    _logger.warning(
                        'pb_vendor_access: could not attach the abilities of '
                        'the "%s" role', name, exc_info=True)
            else:
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
        vals = {
            'name': name,
            'ability_ids': [(6, 0, wanted.ids)],
            'description': description,
            'area': area,
            'sequence': sequence,
            'visible_group_id': visible.id if visible else False,
        }
        # The frozen column, filled in where it can be: a role made of one
        # permission still records which one it was, so a database seeded today
        # and a database migrated today are the same database afterwards. It is
        # written, never read — and never written twice, because it is unique.
        legacy = wanted.group_ids
        if len(legacy) == 1 and not Profile.with_context(
                active_test=False).search_count([('group_id', '=', legacy.id)]):
            vals['group_id'] = legacy.id
        try:
            Profile.create(vals)
            made += 1
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb_vendor_access: could not seed the "%s" role', name,
                exc_info=True)
    linked += ensure_bundles(env)
    _logger.info(
        'pb_vendor_access: role catalogue — %s created, %s already there, '
        '%s given their abilities, %s not offered (their module is not '
        'installed)', made, skipped, linked, absent)
    return {'created': made, 'existing': skipped, 'linked': linked,
            'absent': absent, 'abilities': abilities}


def ensure_bundles(env):
    """Give every remaining role an ability, so nothing is left unbundled.

    The catalogue covers the roles this module seeded. An administrator may have
    added their own before bundles existed — one name, one permission — and that
    role would otherwise have an EMPTY bundle after the upgrade, which the board
    reads as "nobody holds this" for something several people plainly hold. So
    each one gets an ability of its own, wrapping exactly the permission it
    already carried, named after the role because that is the only honest
    sentence available for it.

    It changes nobody's permissions. It writes down, in the new shape, what the
    old shape already said.
    """
    Profile = env['pb.role.profile'].sudo().with_context(active_test=False)
    Ability = env['pb.role.ability'].sudo().with_context(active_test=False)
    orphans = Profile.search(
        [('ability_ids', '=', False), ('group_id', '!=', False)])
    linked = 0
    for profile in orphans:
        key = 'role-%s-%s' % (_slug(profile.name, 'role'), profile.id)
        # Found by its own key and by nothing else. Reusing "an ability that
        # happens to contain this permission" would attach the OTHER
        # permissions in it too, and a migration that widens somebody's access
        # is the one outcome this phase must not have.
        ability = Ability.search([('technical_key', '=', key)], limit=1)
        try:
            if not ability:
                ability = Ability.create({
                    'technical_key': key,
                    'name': profile.name or key,
                    'description': profile.description or '',
                    'area': profile.area or 'people',
                    'sequence': profile.sequence or 10,
                    'group_ids': [(6, 0, [profile.group_id.id])],
                })
            profile.write({'ability_ids': [(6, 0, ability.ids)]})
            linked += 1
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb_vendor_access: the "%s" role could not be given an '
                'ability for the permission it already carried',
                profile.name, exc_info=True)
    if linked:
        _logger.info(
            'pb_vendor_access: %s roles outside the seeded catalogue were '
            'written down as bundles of what they already carried', linked)
    return linked


def post_init_hook(env):
    """Odoo 19 hands the hook an `env`. R84 — this runs on INSTALL only."""
    if not isinstance(env, api.Environment):    # pragma: no cover - old shape
        env = api.Environment(env, SUPERUSER_ID, {})
    ensure_catalogue(env)
