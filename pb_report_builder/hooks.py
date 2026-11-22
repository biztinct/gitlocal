# -*- coding: utf-8 -*-
"""DOCSTUDIO R-b, owner ruling 2026-11-22: everyone who may open "Build a
report" sees Insights on the side menu.

The rail item belongs to `pb_insights_hub` (which stays Python-free with its
fixed lens order); this hook ADDS the report builder's gate groups to it, once,
at install. Only additions ((4, id)): nobody loses the door, and a later
upgrade of `pb_insights_hub` (its own `(4, analytics)`) keeps them.

Why a hook and not a data record: Access Studio (`biz_access`
`pb_sidebar_item_ext.write`) keeps an entry whose access was changed on screen
("Access kept across upgrades", `access_customized`) and silently drops any
data-file write to its groups during an install. On the template databases the
Insights entry is such an entry, so a data record would do nothing. The ruling
is deliberate, so it is written through Access Studio's own internal lane,
which is how its role assignments write the menu.

Inside the hub every other tab keeps its own gate (client groups and probe,
and each facade's `_require` on the server): an HR officer lands on "Build a
report", the only tab they pass.
"""
import logging

_logger = logging.getLogger(__name__)

GATE_XMLIDS = (
    'hr.group_hr_user',
    'base.group_system',
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_analytics_user',
    'pb_hr_payroll_base.group_payroll_super_admin',
)


def open_insights_door(env):
    item = env.ref('pb_insights_hub.item_insights', raise_if_not_found=False)
    if not item:
        return
    groups = [env.ref(x, raise_if_not_found=False) for x in GATE_XMLIDS]
    add = [(4, g.id) for g in groups if g and g not in item.groups_id]
    if not add:
        return
    ctx = {}
    try:
        from odoo.addons.biz_access.models.role_assignments import INTERNAL
        ctx['_pb_access_internal'] = INTERNAL
    except ImportError:  # pragma: no cover — Access Studio absent
        pass
    item.with_context(**ctx).write({'groups_id': add})
    _logger.info('pb_report_builder: Insights side-menu entry opened to %s more group(s)', len(add))


def post_init_hook(env):
    open_insights_door(env)
