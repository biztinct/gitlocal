# -*- coding: utf-8 -*-
"""LEARNING L0 — the product guide is called "Help" (VI "Trợ giúp").

A renamed menu label is TWO fixes (LEARNING ledger LN7, LOOK rule): the
`.po` msgstr AND the stored translated value. `-u pb_learn` rewrites the
English name from the data files (`learn_sidebar_item.xml` is noupdate="0",
`learn_actions.xml` likewise), but an upgrade never overwrites a Vietnamese
value that is already stored, so GROW › Help would still read "Học cùng
Payobook" to a Vietnamese reader.

This updates, IN PLACE, two rows and one field each:

    pb_learn.item_learn_journey   pb.sidebar.item     name
    pb_learn.action_learn_hub     ir.actions.client   name

English is set to "Help". Vietnamese is set to "Trợ giúp" ONLY where the
stored Vietnamese is still one of the old words (or missing), so a name an
administrator retyped on Access › Screens is left alone. Never a
translation reload with overwrite (ledger LN6 / LR29): nothing else in the
database is touched. Idempotent: a second run finds nothing to change.
"""
import json
import logging

from psycopg2.extras import Json

_logger = logging.getLogger(__name__)

NEW_EN = 'Help'
NEW_VI = 'Trợ giúp'
#: Every Vietnamese the guide's name has been stored as.
OLD_VI = {'Học cùng Payobook', 'Học tập', 'Learn', 'Help'}

ROWS = (
    ('item_learn_journey', 'pb_sidebar_item'),
    ('action_learn_hub', 'ir_act_client'),
)


def migrate(cr, version):
    cr.execute("SELECT 1 FROM res_lang WHERE code = 'vi_VN' AND active")
    has_vi = bool(cr.fetchone())
    changed = 0
    for name, table in ROWS:
        cr.execute("SELECT res_id FROM ir_model_data "
                   "WHERE module = 'pb_learn' AND name = %s", (name,))
        hit = cr.fetchone()
        if not hit:
            continue
        cr.execute('SELECT name FROM "%s" WHERE id = %%s' % table, (hit[0],))
        row = cr.fetchone()
        if not row:
            continue
        value = row[0] or {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                value = {'en_US': value}
        new = dict(value)
        new['en_US'] = NEW_EN
        if has_vi and (not value.get('vi_VN') or value.get('vi_VN') in OLD_VI):
            new['vi_VN'] = NEW_VI
        if new != value:
            cr.execute('UPDATE "%s" SET name = %%s WHERE id = %%s' % table,
                       (Json(new), hit[0]))
            changed += 1
    _logger.info('pb_learn: the guide is called Help now — %s name(s) updated '
                 'in place', changed)
