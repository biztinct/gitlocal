# -*- coding: utf-8 -*-
"""Link the Decision Room tier to the roles that should already have it.

`hr.group_hr_manager` and `base.group_system` are linked by DATA RECORDS —
both modules are hard dependencies, so the xmlids always resolve.

The Workforce Planning tiers cannot be: `pb_hr_workforce_planning` is a
dependency of `pb_people_hub` today, but a database that ever drops it would
turn a data record naming its group into an install-time failure. So the link
is made HERE, guarded, and only when the group is actually present.

`post_init_hook` fires on INSTALL only (Odoo 19), which is the right moment:
after that, an administrator owns the ladder.
"""
import logging

_logger = logging.getLogger(__name__)

#: Planning tiers that should carry the Decision Room with them.
WFP_TIERS = (
    'pb_hr_workforce_planning.group_wfp_user',
    'pb_hr_workforce_planning.group_wfp_manager',
    'pb_hr_workforce_planning.group_wfp_admin',
)


def post_init_hook(env):
    room_user = env.ref('pb_decision_room.group_decision_user',
                        raise_if_not_found=False)
    if not room_user:
        return
    for xmlid in WFP_TIERS:
        group = env.ref(xmlid, raise_if_not_found=False)
        if not group:
            _logger.info(
                'pb_decision_room: %s is not installed here — nothing to link',
                xmlid)
            continue
        if room_user in group.implied_ids:
            continue
        group.write({'implied_ids': [(4, room_user.id)]})
        _logger.info('pb_decision_room: %s now implies the Decision Room tier',
                     xmlid)
