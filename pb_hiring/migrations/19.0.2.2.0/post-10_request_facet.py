# -*- coding: utf-8 -*-
"""RECRUIT P3 — the role and its request become two facets (RC-D6).

1. THE STATUS SPLIT. The old status (kept aside by the pre-migration) maps to
   the role's life and the request's facet (handover §2.1):

       draft                   → role being set up,  request being written
       submitted / manager_ok  → set up,             sent in (manager agreed)
       hr_ok                   → set up,             Head of HR agreed
       open                    → open,               agreed
       filled / closed         → kept,               agreed
       refused                 → set up,             not approved

   A role that was open keeps its job, recruiter and referrals untouched.

2. THE ROUTE. Every company's "Hiring request" workflow gets a new published
   revision: one Head of HR step, plus the company's named approver as a
   second step only when one is named. Finance is off the route (an
   over-budget request used to wait for ever on a Finance seat nobody held).
   Safeguards keep what each company chose (rize's independence rule, for
   one). A binding a company pointed at "No approval needed" stays exactly
   as it is — that is the company's choice, and it is never overridden.
   A request still waiting on the old route is withdrawn and sent in again on
   the new one (none existed on the live databases on 2026-10-01).

3. THE ADVERT ROUTE IS RETIRED (G-17): agreed versions become final, the rest
   drafts; an advert waiting in an inbox is withdrawn; the catalogue row's
   bindings are switched off and the row reads "covered by the hiring
   request" rather than "not connected".

4. EVERY HIRING EMAIL comes from the company's hiring sender (`_sender`), not
   from whoever pressed the button — the stored templates are noupdate, so
   `email_from` is rewritten here where it still carries the old default.

5. The budget is read again on every live role (the confirmed figure is new).
"""
import copy
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MAP = {
    'draft': ('setup', 'writing'),
    'submitted': ('setup', 'sent_in'),
    'manager_ok': ('setup', 'sent_in'),
    'hr_ok': ('setup', 'hr_ok'),
    'open': ('open', 'agreed'),
    'filled': ('filled', 'agreed'),
    'closed': ('closed', 'agreed'),
    'refused': ('setup', 'not_approved'),
}

NEW_FROM = '{{ object.company_id.pb_hiring_sender or user.email_formatted }}'
OLD_FROM = ('{{ (user.email_formatted) }}', '{{ user.email_formatted }}')


def _map_states(cr):
    cr.execute("SELECT id, pb_p3_old_state FROM pb_hiring_requisition "
               "WHERE pb_p3_old_state IS NOT NULL")
    rows = cr.fetchall()
    for rid, old in rows:
        state, request_state = MAP.get(old, ('setup', 'writing'))
        cr.execute("""
            UPDATE pb_hiring_requisition
               SET state = %s, request_state = %s,
                   manager_agreed_on = CASE WHEN %s IN ('sent_in', 'hr_ok',
                        'agreed') THEN COALESCE(manager_agreed_on,
                        write_date) ELSE manager_agreed_on END,
                   agreed_on = CASE WHEN %s = 'agreed'
                        THEN COALESCE(agreed_on, opened_on::timestamp,
                        write_date) ELSE agreed_on END
             WHERE id = %s
        """, (state, request_state, request_state, request_state, rid))
    cr.execute("ALTER TABLE pb_hiring_requisition "
               "DROP COLUMN IF EXISTS pb_p3_old_state")
    return len(rows)


def _republish(env):
    """A new published revision of every company's Hiring request route."""
    from odoo.addons.pb_hiring.models.requisition_approval import (
        HIRING_PROCESS_KEY, hiring_steps, seed_all)
    process = env['biz.approval.process']._by_key(HIRING_PROCESS_KEY)
    if not process:
        return 0
    Seed = env['biz.approval.seed']
    done = 0
    workflows = env['biz.approval.workflow'].sudo().with_context(
        active_test=False).search([('process_id', '=', process.id)])
    for wf in workflows:
        published = wf.published_version_id
        definition = copy.deepcopy(published.definition or {}) \
            if published else {}
        steps = definition.get('steps') or []
        # A company's own "No approval needed" lane is its choice: keep it.
        if any(s.get('kind') == 'fast' for s in steps):
            continue
        keys = [s.get('key') for s in steps]
        if keys == ['hr', 'mgr'] and not any(
                (s.get('who') or {}).get('role') == 'finance' for s in steps):
            continue                    # already the new shape
        try:
            with env.cr.savepoint():
                definition['steps'] = hiring_steps()
                draft = wf.draft_version_id or wf.action_new_draft()
                draft.sudo().write({'definition': definition})
                publisher = Seed.publisher_for(wf.company_id)
                engine = env['biz.approval.engine'].with_user(
                    publisher).sudo().with_context(
                        approval_skip_coverage=True)
                checks = engine.validate_for_publish(draft.id)
                if checks['errors']:
                    raise ValueError([e['code'] for e in checks['errors']])
                engine.publish(
                    draft.id, draft.draft_revision, None,
                    'RECRUIT: the hiring request is agreed by the Head of '
                    'HR; the manager sending it in is their agreement. '
                    'Finance is told about over-budget requests instead of '
                    'deciding them.',
                    [w['code'] for w in checks['warnings']])
                done += 1
        except Exception:               # noqa: BLE001 — never fail an upgrade
            _logger.exception('pb_hiring 2.2.0: the hiring route of %s could '
                              'not be re-published', wf.company_id.name)
    seed_all(env)                       # companies that never had one
    return done


def _resend_in_flight(env):
    """A request waiting on the old route goes round the new one."""
    Req = env['pb.hiring.requisition'].sudo()
    moved = 0
    for req in Req.search([('request_state', 'in', ('sent_in', 'hr_ok'))]):
        request = req.approval_request_id
        if not request or request.state not in ('pending', 'blocked'):
            continue
        try:
            with env.cr.savepoint():
                env['biz.approval.engine'].sudo().cancel(
                    request.id, 'Moved to the new hiring request route')
                req.invalidate_recordset()
                req._request_write('writing')
                submitter = request.submitter_uid or env.user
                req.with_user(submitter).sudo().action_approval_submit()
                req._log_role('The request went round the new route: the '
                              'Head of HR agrees it now.')
                moved += 1
        except Exception:               # noqa: BLE001
            _logger.exception('pb_hiring 2.2.0: request %s could not be sent '
                              'round the new route', req.id)
    return moved


def _retire_jd_route(env):
    cr = env.cr
    cr.execute("UPDATE pb_hiring_jd SET state = 'final' "
               "WHERE state = 'approved'")
    finals = cr.rowcount
    cr.execute("UPDATE pb_hiring_jd SET state = 'draft' "
               "WHERE state IN ('submitted', 'refused')")
    env['pb.hiring.jd'].invalidate_model()
    process = env['biz.approval.process']._by_key('hiring_jd')
    withdrawn = 0
    if process:
        for request in env['biz.approval.request'].sudo().search([
                ('process_id', '=', process.id),
                ('state', 'in', ('pending', 'blocked'))]):
            try:
                with env.cr.savepoint():
                    env['biz.approval.engine'].sudo().cancel(
                        request.id, 'Job descriptions are shared for input '
                        'now, not signed off.')
                    withdrawn += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_hiring 2.2.0: advert request %s was '
                                  'not withdrawn', request.id)
        env['biz.approval.binding'].sudo().with_context(
            active_test=False).search([('process_id', '=', process.id)]).write(
                {'active': False})
        vals = {'description': 'Retired: a job description is shared with '
                               'the manager for input and made final by the '
                               'recruiter. There is no sign-off.'}
        if 'covered_by_key' in process._fields:
            vals['covered_by_key'] = 'hiring_request'
        process.sudo().write(vals)
    return finals, withdrawn


def _sender_on_templates(env):
    cr = env.cr
    cr.execute("""
        SELECT res_id FROM ir_model_data
         WHERE module = 'pb_hiring' AND model = 'mail.template'
    """)
    ids = [r[0] for r in cr.fetchall()]
    made = 0
    for tpl in env['mail.template'].sudo().browse(ids).exists():
        if (tpl.email_from or '').strip() in OLD_FROM or not tpl.email_from:
            tpl.write({'email_from': NEW_FROM})
            made += 1
    return made


def _noupdate_records(env):
    """Records whose MEANING changed but which live in noupdate blocks: the
    loader skips them on an upgrade whatever ir_model_data says, so they are
    written here from the module's own data file (RC41)."""
    from lxml import etree
    from odoo.modules.module import get_module_path
    root = get_module_path('pb_hiring')
    done = 0
    rule = env.ref('pb_hiring.rule_requisition_own', raise_if_not_found=False)
    if rule:
        tree = etree.parse(root + '/security/pb_hiring_security.xml')
        node = tree.xpath("//record[@id='rule_requisition_own']"
                          "/field[@name='domain_force']")
        if node:
            rule.sudo().write({'domain_force': node[0].text.strip()})
            done += 1
    tree = etree.parse(root + '/data/mail_template_data.xml')
    for xmlid in ('mail_template_requisition_recruiter',
                  'mail_template_requisition_recruiter_manager'):
        tpl = env.ref('pb_hiring.' + xmlid, raise_if_not_found=False)
        rec = tree.xpath("//record[@id='%s']" % xmlid)
        if not tpl or not rec or 'has been agreed' not in (
                (tpl.subject or '') + str(tpl.body_html or '')):
            continue                    # reworded by the company: theirs
        vals = {}
        for field in rec[0].findall('field'):
            name = field.get('name')
            if name in ('name', 'subject', 'email_from', 'email_to'):
                vals[name] = (field.text or '').strip()
            elif name == 'body_html':
                vals[name] = ''.join(etree.tostring(c, encoding='unicode')
                                     for c in field)
        tpl.sudo().write(vals)
        done += 1
    return done


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    mapped = _map_states(cr)
    env['pb.hiring.requisition'].invalidate_model()
    routes = _republish(env)
    moved = _resend_in_flight(env)
    finals, withdrawn = _retire_jd_route(env)
    senders = _sender_on_templates(env)
    rewritten = _noupdate_records(env)
    live = env['pb.hiring.requisition'].sudo().search(
        [('state', 'in', ('setup', 'open'))])
    live._refresh_budget(silent=True)
    _logger.info(
        'pb_hiring 2.2.0: %s requests split into role + request; %s hiring '
        'routes re-published; %s in-flight requests moved; %s adverts final, '
        '%s advert sign-offs withdrawn; %s templates now send from the hiring '
        'sender; %s noupdate records rewritten; budget read again on %s '
        'live roles', mapped, routes, moved, finals, withdrawn, senders,
        rewritten, len(live))
