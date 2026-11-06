# -*- coding: utf-8 -*-
"""NAV P2 — "Pay Run" is called Payroll; make the Vietnamese say "Lương".

A translation fix is TWO fixes (LOOK programme): the `.po` entry, and the value
already stored in the database. The data file rewrites the English name, but
the Vietnamese key of a stored translated field keeps its old word ("Đợt
lương") unless something writes it. This writes it, for the left-menu entry
and for the hub's action (the browser tab and breadcrumb), on databases where
Vietnamese is installed. Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

RECORDS = (
    ('pb_sidebar_item', 'item_pay_run', 'pb.sidebar.item'),
    ('ir_act_client', 'action_pb_pay_hub', 'ir.actions.client'),
)


def migrate(cr, version):
    if not version:
        return
    # The data file's writes may still be in the ORM cache; raw SQL must see
    # them (and must not be overwritten by a later flush).
    api.Environment(cr, SUPERUSER_ID, {}).flush_all()
    cr.execute("SELECT 1 FROM res_lang WHERE code = 'vi_VN' AND active")
    if not cr.fetchone():
        return
    for table, name, model in RECORDS:
        cr.execute("""
            SELECT res_id FROM ir_model_data
             WHERE module = 'pb_payhub' AND name = %s AND model = %s
        """, (name, model))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute("""
            UPDATE %s
               SET name = jsonb_set(name::jsonb, '{vi_VN}', '"Lương"'::jsonb, true)
             WHERE id = %%s AND name::jsonb ->> 'en_US' = 'Payroll'
        """ % table, (row[0],))
        _logger.info('pb_payhub NAV P2: Vietnamese name of %s set to "Lương" '
                     '(%s row)', name, cr.rowcount)
