# -*- coding: utf-8 -*-
"""NAV P2 — take OPERATE › Ask HR off the left menu, on every database.

Ask HR is a tab of Home now (Home claims the native action and model).

The data file now says `active=False`, but `biz_access` drops writes to
`active` on an entry somebody has customised on the Access home while the
module is loading (install mode), so an entry that was ever edited there would
stay on the menu. The owner's ruling is a menu change, not an access change:
the entry goes off for everybody. Plain SQL, so neither the install-mode guard
nor the "customised" stamp is involved; `access_customized` is cleared so the
next upgrade is free to manage the record again.

The record is kept: the Access home lists it as "off the menu", and the
native action stays for administrators, so no link dead-ends.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    # The data file's writes may still be in the ORM cache; raw SQL must see
    # them (and must not be overwritten by a later flush).
    api.Environment(cr, SUPERUSER_ID, {}).flush_all()
    cr.execute("""
        SELECT res_id FROM ir_model_data
         WHERE module = 'pb_ask_hr' AND name = 'item_ask_hr'
           AND model = 'pb.sidebar.item'
    """)
    row = cr.fetchone()
    if not row:
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'pb_sidebar_item' AND column_name = 'access_customized'
    """)
    sets = "active = false, sequence = 983, match_models = NULL, match_action_xmlids = NULL"
    if cr.fetchone():
        sets += ", access_customized = false"
    cr.execute("UPDATE pb_sidebar_item SET %s WHERE id = %%s" % sets, (row[0],))
    _logger.info('pb_ask_hr NAV P2: the Ask HR entry is off the left menu '
                 '(item %s)', row[0])
