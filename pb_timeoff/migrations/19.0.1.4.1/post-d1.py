# -*- coding: utf-8 -*-
"""RIZE W2 D1, on a database that already has this module.

THREE REPAIRS, each of which a fresh install gets for free and an upgrade
does not.

1. **The late block of every published time-off route.** The escalation
   address was `workflow.owner_user_id` — on `payobook` that is uid 2 for all
   four companies, i.e. the owner's own account — so "tell HR when a manager
   has sat on this for two days" reached nobody in HR. The engine now accepts
   `to_role` in the late block (`biz_approval_workflow`), and this writes it
   onto the routes that are already live. A published revision is immutable by
   convention, so this touches ONLY a late block that is still exactly as the
   seed shipped it: a business that has changed its own chasing rules keeps
   them, and is named in the log instead.

2. **Sick leave may be asked for after the fact.** Nobody books being ill in
   advance. Matched on the NAME, because a leave type carries no code on this
   build and the set is different in every country pack.

3. **`seed_all`**, for a company that has no route at all — the same
   idempotent call the install hook makes.

A migration that half-runs is worse than one that does not, so every repair
sits under its own savepoint (R131) and reports what it did.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

#: What the seed has always shipped. Anything else is the business's own.
_AS_SHIPPED = {'remind_days': 1, 'escalate_days': 2, 'reassign': False}

#: The words a sick-leave type is called on this build, in every country pack
#: installed here. Folded to lower case before matching.
_SICK_WORDS = ('sick', 'ốm', 'om dau', 'ốm đau', 'illness', 'nghỉ ốm')


def _fix_routes(env):
    """Put `to_role: hr_lead` on every published time-off route."""
    process = env['biz.approval.process'].sudo().search(
        [('key', '=', 'leave')], limit=1)
    if not process:
        _logger.info('pb_timeoff D1: there is no "leave" row in the approval '
                     'catalogue yet, so no route was touched')
        return 0
    raw = env['ir.config_parameter'].sudo().get_param(
        'pb_timeoff.escalate_days')
    try:
        escalate_days = max(0, int(raw)) if raw not in (None, False, '') else 2
    except (TypeError, ValueError):
        escalate_days = 2

    Version = env['biz.approval.workflow.version'].sudo()
    Seed = env['biz.approval.seed']
    changed = 0
    for workflow in env['biz.approval.workflow'].sudo().search(
            [('process_id', '=', process.id)]):
        version = workflow.published_version_id
        if not version:
            continue
        definition = dict(version.definition or {})
        safeguards = dict(definition.get('safeguards') or {})
        late = dict(safeguards.get('late') or {})
        if late.get('to_role'):
            continue                       # already said, nothing to do
        theirs = {k: late.get(k) for k in _AS_SHIPPED}
        if theirs != _AS_SHIPPED:
            _logger.info(
                'pb_timeoff D1: "%s" has its own chasing rules (%s), so they '
                'were left alone — say who to escalate to on the Approval '
                'Matrix if that is wanted', workflow.name, theirs)
            continue
        late.update({'escalate_days': escalate_days, 'to_role': 'hr_lead'})
        safeguards['late'] = late
        definition['safeguards'] = safeguards

        # A PUBLISHED REVISION IS FROZEN, AND THAT RULE IS RIGHT.
        #
        # The first attempt wrote the definition in place and was refused by
        # the engine's own immutability guard — "requests already under way
        # keep the version they were given". Quite so: a leave somebody sent
        # in yesterday must not silently start being chased by different
        # rules. So the repair does what a business would do on the Approval
        # Matrix — a NEW revision, validated and published, with a reason on
        # it — and every request in flight finishes under the rules it was
        # given.
        publisher = Seed.publisher_for(workflow.company_id)
        draft = Version.create({
            'workflow_id': workflow.id,
            'revision': max(workflow.version_ids.mapped('revision') or [0]) + 1,
            'status': 'draft',
            'definition': definition,
        })
        engine = env['biz.approval.engine'].with_user(publisher).sudo() \
            .with_context(approval_skip_coverage=True)
        checks = engine.validate_for_publish(draft.id)
        if checks['errors']:
            _logger.warning(
                'pb_timeoff D1: "%s" could not be re-published: %s',
                workflow.name, [e['code'] for e in checks['errors']])
            draft.unlink()
            continue
        engine.publish(
            draft.id, draft.draft_revision, None,
            'Time off now goes to the HR lead when a step is late',
            [w['code'] for w in checks['warnings']])
        changed += 1
    _logger.info('pb_timeoff D1: %s time-off route(s) now escalate to the HR '
                 'lead after %s day(s)', changed, escalate_days)
    return changed


def _fix_sick_types(env):
    """Sick leave may be asked for after the day it happened."""
    types = env['hr.leave.type'].sudo().with_context(active_test=False).search(
        [('pb_backdate_ok', '=', False)])
    sick = types.filtered(
        lambda t: any(word in (t.name or '').lower() for word in _SICK_WORDS))
    if sick:
        sick.write({'pb_backdate_ok': True, 'pb_backdate_alert': True})
    _logger.info('pb_timeoff D1: %s kind(s) of time off may now be asked for '
                 'after the fact: %s', len(sick),
                 ', '.join(sorted(t.name or '' for t in sick)) or '—')
    return len(sick)


def _seed_missing(env):
    from odoo.addons.pb_timeoff.models.hr_leave_approval import seed_all
    return seed_all(env)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for name, leg in (('the late blocks', _fix_routes),
                      ('the sick-leave types', _fix_sick_types),
                      ('any missing route', _seed_missing)):
        try:
            with cr.savepoint():
                leg(env)
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_timeoff D1: %s could not be repaired', name)
