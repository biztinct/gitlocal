# -*- coding: utf-8 -*-
"""RECRUIT P3 follow-up — "tell employees when a role opens for referrals"
goes OFF, once.

Phase 3 shipped `pb_hiring.referral_announce` ON, which emailed every employee
with a login whenever a role opened for referrals. Fable's ruling
(2026-10-01): default OFF on install and upgrade. The code default is now
'0' (`hiring_common.DEFAULTS`); this writes '0' explicitly on the upgrade that
ships it, so a database that stored '1' (the set-up switch) is put back too.
The Hiring set-up switch stays, so the talent lead can turn it on again and no
later upgrade touches it.
"""
import logging

_logger = logging.getLogger(__name__)

KEY = 'pb_hiring.referral_announce'


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT id FROM ir_config_parameter WHERE key = %s", (KEY,))
    row = cr.fetchone()
    if row:
        cr.execute("UPDATE ir_config_parameter SET value = '0' WHERE id = %s",
                   (row[0],))
    else:
        cr.execute("INSERT INTO ir_config_parameter (key, value, create_uid, "
                   "write_uid, create_date, write_date) "
                   "VALUES (%s, '0', 1, 1, now() at time zone 'utc', "
                   "now() at time zone 'utc')", (KEY,))
    _logger.info('pb_hiring 2.3.0: referral announcement switched off')
