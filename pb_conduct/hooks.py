# -*- coding: utf-8 -*-
"""Install step: put the two conduct roles on the Talent left-menu entry.

ADDITIVE AND SILENT. Nobody holds either role at install, so nothing anybody
sees changes; it only means that somebody later given ONLY a conduct role (and
no other Talent role) still finds the Talent entry. No group is granted to
anybody, no email, no job, no demo data.
"""
import logging

_logger = logging.getLogger(__name__)

ROLE_XMLIDS = ('pb_conduct.role_conduct_hr', 'pb_conduct.role_conduct_head')


def gate_talent(env):
    item = env.ref('pb_talent_hub.item_talent', raise_if_not_found=False)
    if not item or item._name != 'pb.sidebar.item' or 'role_ids' not in item._fields:
        return
    roles = [env.ref(x, raise_if_not_found=False) for x in ROLE_XMLIDS]
    ids = [r.id for r in roles if r]
    if not ids:
        return
    try:
        item.sudo().write({'role_ids': [(4, rid) for rid in ids]})
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.exception('pb_conduct: the Talent entry could not be gated')


def post_init_hook(env):
    gate_talent(env)
