# -*- coding: utf-8 -*-
"""CLOCK-2: `pb.clock.device.allowed` becomes a mirror of the new `state`.

Seed `state` from the CLOCK-1 Boolean BEFORE the ORM sees the new field, so a
machine somebody switched off stays off (`blocked`) and every other row is
`allowed`. `allowed_at` stays empty: a terminal nobody has let in over the
network waits for Allow the first time it calls (ledger D10).
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE pb_clock_device ADD COLUMN IF NOT EXISTS state varchar;
        UPDATE pb_clock_device
           SET state = CASE WHEN allowed IS FALSE THEN 'blocked' ELSE 'allowed' END
         WHERE state IS NULL;
    """)
