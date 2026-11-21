# -*- coding: utf-8 -*-
"""IA redesign Cycle 1 — let the data file heal the three audit defects.

The three fixes (A1 retire "Employee/Contract Mapping", A2 renumber the ADMIN
configuration items off pb_audit's sequence 30, A3 stop Import Data claiming
`hr.integration.connector`) are all expressed in
`pb_sidebar/data/pb_sidebar_data.xml`, and that file is `<odoo noupdate="0">`
(W8) — so on a healthy database a plain `-u pb_sidebar` applies every one of
them and this script has nothing to do.

It exists for the databases that are NOT healthy. `ir_model_data.noupdate` is a
PER-RECORD column that Odoo never refreshes (W13.1): if any of these three rows
was ever written by a loader that flagged it — an old file revision, a manual
`ir.model.data` edit, a restore from a database where it was frozen — then the
loader silently skips it forever, `-u` returns EXIT 0, and the repo and the rail
disagree with nothing in the log to say so.

Clearing the flag in a PRE-migrate rather than hand-applying values in a POST
one is W27, learned the expensive way: an upgrade runs
`pre-migrate -> data files load -> post-migrate`, so a post-migrate that clears
the flag is clearing it *after* the loader has already skipped the file, and
only the fields the script itself rewrites actually move. P1b changed two fields
on one record that way and shipped one of them. Here A2 changes a sequence and
A3 changes `match_models` and A1 changes `active` — three different fields on
three different records — so hand-applying them would be three chances to drift
from the XML. Unfreeze, and let the data file be the single source of truth.

Idempotent and narrow: three xmlids, one column, nothing written when the flag
is already clear.
"""
import logging

_logger = logging.getLogger(__name__)

# (module, name) of every record this cycle's data-file edits have to reach.
XMLIDS = [
    ('pb_sidebar', 'item_emp_mapping'),    # A1 — active "False" -> eval False
    ('pb_sidebar', 'item_menu_cfg'),       # A2 — sequence 30 -> 50
    ('pb_sidebar', 'item_section_cfg'),    # A2 — sequence 35 -> 55
    ('pb_sidebar', 'item_import'),         # A3 — match_models loses the connector
]


def migrate(cr, version):
    if not version:
        return

    for module, name in XMLIDS:
        cr.execute("""
            UPDATE ir_model_data
               SET noupdate = false
             WHERE module = %s AND name = %s
               AND model = 'pb.sidebar.item'
               AND noupdate
        """, (module, name))
        if cr.rowcount:
            _logger.info(
                "pb_sidebar: cleared the stored noupdate flag on %s.%s — the "
                "data file's value now applies in this same upgrade (W13.1/W27)",
                module, name)
