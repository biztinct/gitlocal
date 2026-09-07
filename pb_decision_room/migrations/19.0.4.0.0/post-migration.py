# -*- coding: utf-8 -*-
"""Carry every existing row into the world where a plan has a scope.

TWO THINGS HAPPEN HERE AND BOTH ARE ABOUT NOT MOVING A NUMBER.

1. **Every assumptions row and every plan that already exists is a COMPANY
   scope, and now says so.** Before this phase there was nothing else it could
   be. `scope_ref` becomes the company id, so the unique key on
   (scope_kind, scope_ref) has something to be unique about and the room finds
   the row it has always used rather than making a second one.

2. **`use_country_rules` is switched OFF for those rows.** The field's default
   is on, because a company created tomorrow should follow its own country's
   rules without anybody thinking about it. But a row that already exists holds
   numbers somebody looked at, and possibly typed: on the master database the
   employer rate, the ceiling and the tax ladder were reviewed during the
   Decision Room's own build. Switching those rows to "follow the country" on
   the morning of an upgrade could move a picture a board has already seen,
   silently, with nothing on screen to explain it. So they keep exactly what
   they have, and the assumptions card offers the switch in words.

   The shipped Vietnam rules are the very numbers those rows carry, so on a
   Vietnamese company the two answers are identical either way — this is
   belt and braces, and the identity test (T1) leans on it.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE pb_decision_assumptions
           SET scope_kind = 'company',
               scope_ref = company_id::text,
               use_country_rules = FALSE
         WHERE scope_ref IS NULL OR scope_ref = ''
    """)
    rows = cr.rowcount
    cr.execute("""
        INSERT INTO pb_decision_assumptions_company_rel
                    (assumptions_id, company_id)
             SELECT a.id, a.company_id FROM pb_decision_assumptions a
              WHERE NOT EXISTS (
                    SELECT 1 FROM pb_decision_assumptions_company_rel r
                     WHERE r.assumptions_id = a.id
                       AND r.company_id = a.company_id)
    """)

    cr.execute("""
        UPDATE pb_decision_plan
           SET scope_kind = 'company',
               scope_ref = company_id::text
         WHERE scope_ref IS NULL OR scope_ref = ''
    """)
    plans = cr.rowcount
    cr.execute("""
        INSERT INTO pb_decision_plan_company_rel (plan_id, company_id)
             SELECT p.id, p.company_id FROM pb_decision_plan p
              WHERE NOT EXISTS (
                    SELECT 1 FROM pb_decision_plan_company_rel r
                     WHERE r.plan_id = p.id AND r.company_id = p.company_id)
    """)
    cr.execute("""
        UPDATE pb_decision_plan SET status = 'draft' WHERE status IS NULL
    """)
    # The name a reader sees on the chip. Read from the company's partner,
    # which is where a company's name actually lives.
    for table in ('pb_decision_assumptions', 'pb_decision_plan'):
        cr.execute("""
            UPDATE {t} t SET scope_label = p.name
              FROM res_company c JOIN res_partner p ON p.id = c.partner_id
             WHERE c.id = t.company_id
               AND (t.scope_label IS NULL OR t.scope_label = '')
        """.format(t=table))
    _logger.info(
        'pb_decision_room: %s sets of assumptions and %s plans are now '
        'company-scoped, and keep the numbers they had', rows, plans)
