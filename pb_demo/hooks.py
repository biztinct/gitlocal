# -*- coding: utf-8 -*-
"""Post-init wiring for the Demo User experience.

Makes the read-only cockpits visible to Demo users (joins the demo group to the
group-gated sidebar items) while marking Administration and Import as *restricted*
so they appear locked with an upsell dialog instead of being hidden.
"""
import logging

_logger = logging.getLogger(__name__)

# Items that should appear LOCKED (upsell) for demo users.
_LOCK_SECTION_KEYS = {'admin'}
_LOCK_ACTION_TAGS = {'pb_import'}
_LOCK_ITEM_NAMES = {'Import Data', 'Roles & Access', 'Companies', 'Menu & Sidebar'}

# (model, read, write, create, unlink) for the Demo User. Read-broad; create only
# on payslip objects so "Run Payroll" works; never write/unlink master data.
_DEMO_ACCESS = [
    ('hr.payslip', 1, 0, 1, 0),
    ('hr.payslip.run', 1, 0, 1, 0),
    ('hr.payslip.line', 1, 0, 1, 0),
    ('hr.payslip.input', 1, 0, 1, 0),
    ('hr.payslip.worked_days', 1, 0, 1, 0),
    ('hr.payroll.structure', 1, 0, 0, 0),
    ('hr.salary.rule', 1, 0, 0, 0),
    ('hr.salary.rule.category', 1, 0, 0, 0),
    ('hr.employee', 1, 0, 0, 0),
    ('hr.contract', 1, 0, 0, 0),
    ('hr.department', 1, 0, 0, 0),
    ('hr.job', 1, 0, 0, 0),
    ('hr.loan', 1, 0, 0, 0),
    ('hr.contribution.register', 1, 0, 0, 0),
    ('hr.integration.connector', 1, 0, 0, 0),
    ('hr.integration.field.mapping', 1, 0, 0, 0),
    ('hr.api.data.store', 1, 0, 0, 0),
    ('hr.api.transformation.rule', 1, 0, 0, 0),
    ('hr.formula.config', 1, 0, 0, 0),
    ('hr.formula.rule', 1, 0, 0, 0),
    # --- Phase D addendum B: the four optional HR domains ---------------
    #
    # PayAI's data queries stopped running under superuser rights (Phase D1),
    # which is right, and made these four questions unanswerable for a demo
    # account — attendance, leave, recruitment and timesheets used to return
    # the whole company only because the escalation ignored the demo user's
    # actual rights. Restoring them through real grants is the same answer
    # arrived at honestly. READ ONLY: a prospect may look at attendance, never
    # write it.
    #
    # Every row is skipped silently when the model is absent (the loop below
    # searches ir.model first), so a database without hr_recruitment or
    # hr_timesheet installed is unaffected.
    ('hr.attendance', 1, 0, 0, 0),
    ('hr.leave', 1, 0, 0, 0),
    ('hr.leave.type', 1, 0, 0, 0),
    ('hr.applicant', 1, 0, 0, 0),
    ('hr.recruitment.stage', 1, 0, 0, 0),
    ('account.analytic.line', 1, 0, 0, 0),
]

# Read-all record rules for the demo group, created only where the demo user
# would OTHERWISE be narrowed by a rule they already match. Rules for one model
# across different groups are OR-combined, so each of these widens.
#
# WHY ONLY TWO. Read off the shipped rules rather than assumed:
#
#   hr.attendance  base.group_user IMPLIES hr_attendance.group_hr_attendance_
#                  own_reader (hr_attendance/security/hr_attendance_security
#                  .xml:14-16), whose rule is [('employee_id.user_id','=',
#                  user.id)] (:82). Every demo user matches it, and a demo
#                  account is not an employee — so the honest result without a
#                  widening rule is an empty attendance report. NEEDS ONE.
#   hr.leave       three rules scoped to base.group_user restrict to own leave
#                  (hr_holidays: hr_leave_rule_employee / _update / _unlink).
#                  Same conclusion. NEEDS ONE.
#   hr.applicant   every narrowing rule is scoped to an hr_recruitment group a
#                  demo user does not hold; what remains is the GLOBAL company
#                  rule, which already gives the whole demo company. A rule
#                  here would be dead configuration — a read path nobody asked
#                  for, which this project has a standing rule against.
#   account.analytic.line  same shape: all four timesheet rules are scoped to
#                  hr_timesheet groups the demo user does not hold.
#
# If either of those two ever gains a demo-scoped group, re-derive this table
# rather than adding to it.
_DEMO_READ_RULES = [
    ('hr.attendance', 'Demo: all attendance (read)'),
    ('hr.leave', 'Demo: all leave (read)'),
]


def _grant_demo_read_rules(env, demo):
    """Create/refresh the demo group's read-all rules. Idempotent.

    In the hook rather than in ``pb_demo_security.xml`` for the reason
    ``_grant_demo_access`` is: an ``ir.rule`` in XML needs ``model_id`` to
    resolve at load time, so a database without hr_attendance or hr_holidays
    would fail to install pb_demo outright. Here an absent model is a skipped
    row.
    """
    Model, Rule = env['ir.model'], env['ir.rule']
    for name, label in _DEMO_READ_RULES:
        mdl = Model.search([('model', '=', name)], limit=1)
        if not mdl:
            continue
        vals = {
            'name': label,
            'model_id': mdl.id,
            'groups': [(6, 0, [demo.id])],
            'domain_force': "[(1, '=', 1)]",
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
        }
        rec = Rule.search([('name', '=', label)], limit=1)
        rec.write(vals) if rec else Rule.create(vals)
        _logger.info('pb_demo: demo read rule ensured for %s.', name)


def _grant_demo_access(env, demo):
    """Create/refresh the Demo User's model access by model NAME (robust to
    modules whose model external-ids are not resolvable from a CSV)."""
    Model = env['ir.model']
    Access = env['ir.model.access']
    for name, r, w, c, u in _DEMO_ACCESS:
        mdl = Model.search([('model', '=', name)], limit=1)
        if not mdl:
            continue
        key = 'demo_acc_%s' % name.replace('.', '_')
        vals = {'name': key, 'model_id': mdl.id, 'group_id': demo.id,
                'perm_read': r, 'perm_write': w, 'perm_create': c, 'perm_unlink': u}
        rec = Access.search([('name', '=', key), ('group_id', '=', demo.id)], limit=1)
        rec.write(vals) if rec else Access.create(vals)


def post_init_demo(env):
    demo = env.ref('pb_demo.group_payobook_demo', raise_if_not_found=False)
    if not demo:
        return
    _grant_demo_access(env, demo)
    _grant_demo_read_rules(env, demo)
    items = env['pb.sidebar.item'].search([])
    locked = shown = 0
    for it in items:
        sec_key = (it.section_id.technical_key or it.section_id.name or '').lower()
        is_lock = (sec_key in _LOCK_SECTION_KEYS
                   or (it.action_tag or '') in _LOCK_ACTION_TAGS
                   or it.name in _LOCK_ITEM_NAMES)
        if is_lock:
            it.restricted = True
            locked += 1
        elif it.groups_id:
            # Join the demo group to already-gated items so demo users see them;
            # ungated items are visible to everyone already.
            it.groups_id = [(4, demo.id)]
            shown += 1
    _logger.info('pb_demo: demo sidebar wired — %s shown, %s locked.', shown, locked)
    _retire_analytics_menu(env)
    _hide_salary_structures(env)
    _feature_demo_config(env)


# The division config the studio / tutorial should land on by default — a real,
# richly-named config (named components, full VN gross→net story) rather than the
# 250-column scale-test. _pick_config orders by sequence, so a low one wins.
_FEATURED_CONFIG_CODE = 'DEMO_RETAIL_END'


def _feature_demo_config(env):
    """Give the featured demo config the lowest sequence so it is the default
    landing config. Runs on install AND on every upgrade (via the <function> in
    data/pb_demo_sidebar_access.xml), so it takes effect on `-u pb_demo` without a
    full regen. Idempotent."""
    Config = env['hr.formula.config'].sudo().with_context(active_test=False)
    cfg = Config.search([('code', '=', _FEATURED_CONFIG_CODE)], limit=1)
    if cfg and cfg.sequence != 1:
        cfg.sequence = 1
        _logger.info('pb_demo: featured %s as the default studio config.', cfg.code)


def _hide_salary_structures(env):
    """Payroll runs on Formula Configs, not Salary Structures — hide the confusing
    menu (struct_id stays optional/unused so nothing breaks). Reversible."""
    items = env['pb.sidebar.item'].search([
        '|', ('action_tag', '=', 'pb_structures'), ('name', '=', 'Salary Structures')])
    if items:
        items.write({'active': False})
        _logger.info('pb_demo: hid Salary Structures menu (%s item(s)).', len(items))


def _retire_analytics_menu(env):
    """Remove the demo 'Workforce Analytics' sidebar item (Phase O).

    This hook used to CREATE that item, pointing the Insights section at
    ``pb_demo_analytics`` — a demo-module component with no ``groups_id`` (so
    every user saw it) whose every SQL slice was filtered ``is_demo = true``
    (so on a real customer database it rendered completely empty while looking
    like a working feature).

    The slot now belongs to ``pb_workforce_insights``, a gated cockpit on real
    attendance, overtime, leave and payroll-fact data. This removes the old
    item on upgrade; the demo action itself is left installed so the demo
    world keeps its own view, just not a top-level Insights entry.
    """
    items = env['pb.sidebar.item'].search(
        [('action_tag', '=', 'pb_demo_analytics')])
    if items:
        items.unlink()
        _logger.info('pb_demo: retired %s demo analytics sidebar item(s) — '
                     'superseded by pb_workforce_insights.', len(items))

