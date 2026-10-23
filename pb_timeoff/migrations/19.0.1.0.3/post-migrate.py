# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P0 WP-H — unfreeze the Leave sidebar item and move it off its
collision with Timecards.

Why a migration is unavoidable here (W13):

`ir_model_data.noupdate` is stored PER RECORD in the database, and Odoo never
refreshes it on upgrade — `IrModelData._build_update_xmlids_query` writes only
(model, res_id, write_date) on conflict, and `_load_records` skips any record
whose stored flag is set (`if not (update and d_noupdate)`). So flipping
`<odoo noupdate="1">` to `"0"` in the data file changes what a FRESH install
records and nothing else: on every existing database the record stays frozen
forever, and `-u pb_timeoff` silently applies nothing. That is exactly what
happened on the first P0 deploy — the file said 32, the database still said 30.

This clears the stored flag once, so from here on the record tracks the data
file like every other sidebar item, and applies the sequence the data file
already declares.

Idempotent, and deliberately narrow: it touches ONE xmlid and only rewrites the
sequence if it is still sitting on the old colliding value, so an admin who has
since chosen their own ordering is not overruled.
"""
import logging

_logger = logging.getLogger(__name__)

XMLID = ('pb_timeoff', 'item_leave_center')
OLD_SEQUENCE = 30
NEW_SEQUENCE = 32


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT id, res_id, noupdate FROM ir_model_data
         WHERE module = %s AND name = %s AND model = 'pb.sidebar.item'
    """, XMLID)
    row = cr.fetchone()
    if not row:
        _logger.info("pb_timeoff: %s.%s not present, nothing to unfreeze", *XMLID)
        return
    imd_id, res_id, noupdate = row

    if noupdate:
        cr.execute("UPDATE ir_model_data SET noupdate = false WHERE id = %s", (imd_id,))
        _logger.info(
            "pb_timeoff: cleared the noupdate flag on %s.%s — the Leave sidebar "
            "item now follows its data file again (W13)", *XMLID)

    cr.execute("SELECT sequence FROM pb_sidebar_item WHERE id = %s", (res_id,))
    seq = cr.fetchone()
    if seq and seq[0] == OLD_SEQUENCE:
        cr.execute("UPDATE pb_sidebar_item SET sequence = %s WHERE id = %s",
                   (NEW_SEQUENCE, res_id))
        _logger.info("pb_timeoff: Leave sidebar item moved %s -> %s (off the "
                     "Timecards collision)", OLD_SEQUENCE, NEW_SEQUENCE)
