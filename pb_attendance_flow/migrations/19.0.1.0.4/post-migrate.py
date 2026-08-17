# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1a WP-5 — unfreeze the Attendance Control sidebar item and retire it.

Why a migration is unavoidable here (W13.1, proven on the live server during P0):

`ir_model_data.noupdate` is stored PER RECORD in the database, and Odoo never
refreshes it on upgrade — `IrModelData._build_update_xmlids_query` writes only
(model, res_id, write_date) on conflict, and `_load_records` skips any record
whose stored flag is set (`if not (update and d_noupdate)`). So flipping
`<odoo noupdate="1">` to `"0"` in data/pb_sidebar.xml changes what a FRESH
install records and nothing else: on every existing database the record stays
frozen forever, `-u pb_attendance_flow` silently applies nothing, and the log
looks perfectly healthy while the rail still shows the retired item.

This clears the stored flag once — so from here on the record tracks its data
file like every other sidebar item — and applies the deactivation the data file
now declares.

Idempotent and deliberately narrow: ONE xmlid, and `active` is only flipped when
it is still true, so re-running the upgrade cannot overrule an admin who has
since deliberately re-enabled the item.

Precedent cloned: pb_timeoff/migrations/19.0.1.0.3/post-migrate.py.
"""
import logging

_logger = logging.getLogger(__name__)

XMLID = ('pb_attendance_flow', 'item_attendance_control')


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT id, res_id, noupdate FROM ir_model_data
         WHERE module = %s AND name = %s AND model = 'pb.sidebar.item'
    """, XMLID)
    row = cr.fetchone()
    if not row:
        _logger.info("pb_attendance_flow: %s.%s not present, nothing to unfreeze", *XMLID)
        return
    imd_id, res_id, noupdate = row

    if noupdate:
        cr.execute("UPDATE ir_model_data SET noupdate = false WHERE id = %s", (imd_id,))
        _logger.info(
            "pb_attendance_flow: cleared the noupdate flag on %s.%s — the "
            "Attendance Control sidebar item now follows its data file (W13.1)",
            *XMLID)

    cr.execute("SELECT active FROM pb_sidebar_item WHERE id = %s", (res_id,))
    cur = cr.fetchone()
    if cur and cur[0]:
        cr.execute("UPDATE pb_sidebar_item SET active = false WHERE id = %s", (res_id,))
        _logger.info(
            "pb_attendance_flow: Attendance Control retired from the rail — it "
            "is now the Time hub's Exceptions and Import lenses (P1a WP-5)")
