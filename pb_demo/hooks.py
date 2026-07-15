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
]


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
    _ensure_analytics_menu(env)
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


def _ensure_analytics_menu(env):
    """Add a 'Workforce Analytics' item to the Insights sidebar section."""
    Section = env['pb.sidebar.section']
    Item = env['pb.sidebar.item']
    section = Section.search(['|', ('technical_key', '=', 'insights'), ('name', '=', 'Insights')], limit=1)
    if not section:
        return
    if Item.search([('action_tag', '=', 'pb_demo_analytics')], limit=1):
        return
    Item.create({
        'name': 'Workforce Analytics',
        'section_id': section.id,
        'sequence': 50,
        'icon': 'trending-up',
        'action_tag': 'pb_demo_analytics',
        'match_action_tags': 'pb_demo_analytics',
    })

