# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b WP-3 — unfreeze the Business Trips sidebar item and renumber it.

Why a migration is unavoidable here (W13.1, proven on the live server during P0
and again during P1a):

`ir_model_data.noupdate` is stored PER RECORD in the database, and Odoo never
refreshes it on upgrade — `IrModelData._build_update_xmlids_query` writes only
(model, res_id, write_date) on conflict, and `_load_records` skips any record
whose stored flag is set (`if not (update and d_noupdate)`). So flipping
`<odoo noupdate="1">` to `"0"` in data/pb_sidebar.xml changes what a FRESH
install records and nothing else: on every existing database the record stays
frozen forever, `-u pb_business_trip` silently applies nothing, the log looks
perfectly healthy, and the rail still says "Business Trips" at sequence 37.

This clears the stored flag once — so from here on the record tracks its data
file like every other sidebar item — and applies the move the data file now
declares (37 -> 60, the Option-A rail's Trips slot).

Idempotent and deliberately narrow: ONE xmlid, and each value is only written
when it still holds its OLD value, so re-running the upgrade cannot overrule an
admin who has since customised the item. The rename to "Trips" is left to the
data file, which can now reach the record.

Precedent cloned: pb_attendance_flow/migrations/19.0.1.0.4/post-migrate.py.
"""
import logging

_logger = logging.getLogger(__name__)

XMLID = ('pb_business_trip', 'item_wf_trips')
OLD_SEQUENCE = 37
NEW_SEQUENCE = 60


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT id, res_id, noupdate FROM ir_model_data
         WHERE module = %s AND name = %s AND model = 'pb.sidebar.item'
    """, XMLID)
    row = cr.fetchone()
    if not row:
        _logger.info("pb_business_trip: %s.%s not present, nothing to unfreeze", *XMLID)
        return
    imd_id, res_id, noupdate = row

    if noupdate:
        cr.execute("UPDATE ir_model_data SET noupdate = false WHERE id = %s", (imd_id,))
        _logger.info(
            "pb_business_trip: cleared the noupdate flag on %s.%s — the Trips "
            "sidebar item now follows its data file (W13.1)", *XMLID)

    cr.execute("SELECT sequence FROM pb_sidebar_item WHERE id = %s", (res_id,))
    seq = cr.fetchone()
    if seq and seq[0] == OLD_SEQUENCE:
        cr.execute("UPDATE pb_sidebar_item SET sequence = %s WHERE id = %s",
                   (NEW_SEQUENCE, res_id))
        _logger.info(
            "pb_business_trip: Trips moved %s -> %s on the Option-A Workforce "
            "rail (P1b WP-3)", OLD_SEQUENCE, NEW_SEQUENCE)
