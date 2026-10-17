# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b WP-3 (follow-up) — unfreeze Trips in a PRE-migrate, so the data
file can actually apply itself.

WHY THIS EXISTS, AND WHY 19.0.1.0.5/post-migrate.py was not enough
------------------------------------------------------------------
An upgrade runs in this order:

    pre-migrate scripts  →  DATA FILES ARE LOADED  →  post-migrate scripts

W13.1 says a frozen record needs its stored `ir_model_data.noupdate` flag
cleared before the data file can reach it. Both prior unfreezes in this program
(pb_timeoff 19.0.1.0.3, pb_attendance_flow 19.0.1.0.4) did that in a POST-migrate
and then hand-applied the single field they cared about — which worked, because
each of them was changing exactly one field.

P1b changes TWO fields on this record (sequence 37 → 60 AND the label
"Business Trips" → "Trips"), and the post-migrate approach quietly delivered
only the one it hand-applied. The live database after the first P1b deploy said:

    Business Trips | 60 | active

— the sequence moved because the script wrote it, and the name did not, because
the data file had already been skipped ten milliseconds earlier while the flag
was still set. No error. The flag was left clear, so a SECOND upgrade would have
fixed the name, and that lag is exactly the kind of thing that looks like a
caching bug six months later on a fresh tenant.

Doing the unfreeze in a PRE-migrate removes the whole class of problem: the flag
is clear before the loader reaches the file, so the data file applies EVERY field
it declares, in the same upgrade, with no hand-written UPDATE to keep in sync.
That is the pattern later phases should clone (W27).

Idempotent: clearing an already-clear flag is a no-op, and nothing here writes
business data.
"""
import logging

_logger = logging.getLogger(__name__)

XMLID = ('pb_business_trip', 'item_wf_trips')


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE ir_model_data SET noupdate = false
         WHERE module = %s AND name = %s
           AND model = 'pb.sidebar.item' AND noupdate = true
    """, XMLID)
    if cr.rowcount:
        _logger.info(
            "pb_business_trip: cleared the noupdate flag on %s.%s BEFORE the "
            "data files load, so data/pb_sidebar.xml applies its label and its "
            "sequence in this same upgrade (W13.1/W27)", *XMLID)
