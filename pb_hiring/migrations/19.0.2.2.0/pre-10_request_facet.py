# -*- coding: utf-8 -*-
"""RECRUIT P3 — before the new code loads: keep the old status.

`state` on a hiring request meant the REQUEST's progress (draft → submitted →
manager_ok → hr_ok → open …). From 19.0.2.2.0 it is the ROLE's own life and a
new `request_state` carries the request (RC-D6). The mapping needs the old
value AFTER the new columns exist, so it is copied aside here and read by the
post-migration (`post-10_request_facet.py`), which drops the copy.

(The two reworded "a role is yours to recruit" emails and the confidential
record rule live in noupdate blocks; the post-migration writes them.)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        ALTER TABLE pb_hiring_requisition
        ADD COLUMN IF NOT EXISTS pb_p3_old_state varchar
    """)
    cr.execute("""
        UPDATE pb_hiring_requisition SET pb_p3_old_state = state
        WHERE pb_p3_old_state IS NULL
    """)
    _logger.info('pb_hiring 2.2.0: kept the old status of %s hiring requests',
                 cr.rowcount)
