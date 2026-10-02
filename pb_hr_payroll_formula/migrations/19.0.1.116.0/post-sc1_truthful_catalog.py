# -*- coding: utf-8 -*-
"""SC-1 — make the field catalogue truthful on databases that predate `origin`.

Three passes, in an order that matters:

  a. CLASSIFY — every pre-existing row got `origin='discovered'` from the
     column default; the ones that are really instantiated shipped paper are
     re-stamped `template` by joining back to the template table they were
     copied from. (This is the only moment the join is trustworthy: after
     this, observation starts promoting rows and the provenance lives on the
     row itself.)

  b. OBSERVE — the store already holds real payloads, so the catalogue can
     learn from them right now instead of waiting for the next pull. This
     stamps real fields `observed` with REAL samples and `last_seen`, which
     on the reference tenant is what turns 39 sample-less discovery rows into
     rows a reader can trust.

  c. PURGE — rows still `template` on a connector whose system can be asked
     and observed (zoho, excel) are fiction that survived both passes:
     never declared by the vendor's metadata, never seen in a payload. They
     are deleted, except paths a drawn mapping still names (those stay, and
     render truthfully amber). This removes the invented Aadhaar/PAN/"Nguyen
     Van An"/"18500000" rows that led payroll to be mapped to `Salary` while
     the payload carried `Base_Salary`.

Idempotent: re-running finds nothing left to classify or purge.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not table_exists(cr, 'hr_integration_endpoint_field'):
        return

    # ---- a. classify -----------------------------------------------------
    cr.execute("""
        UPDATE hr_integration_endpoint_field
           SET origin = 'discovered'
         WHERE origin IS NULL
    """)
    cr.execute("""
        UPDATE hr_integration_endpoint_field f
           SET origin = 'template'
          FROM hr_integration_endpoint e,
               hr_integration_connector c,
               hr_integration_endpoint_field_template t
         WHERE f.endpoint_id = e.id
           AND e.connector_id = c.id
           AND t.connector_type = c.connector_type
           AND t.endpoint_code = e.code
           AND t.path = f.path
           AND f.origin = 'discovered'
    """)
    _logger.info("SC-1: %d catalogue rows classified as shipped paper",
                 cr.rowcount)

    # ---- b. observe, then c. purge, per connector ------------------------
    env = api.Environment(cr, SUPERUSER_ID, {})
    Store = env['hr.api.data.store']
    purged = 0
    for conn in env['hr.integration.connector'].with_context(
            active_test=False).search([]):
        rows = Store.browse()
        for feed_type, in Store._read_group(
                [('connector_id', '=', conn.id)], ['data_type']):
            if not feed_type:
                continue
            rows |= Store.search(
                [('connector_id', '=', conn.id),
                 ('data_type', '=', feed_type)],
                order='pull_date desc, id desc', limit=20)
        if rows:
            conn._observe_endpoint_fields(rows)
        purged += conn._sc1_purge_fictional_rows()
    _logger.info("SC-1: migration complete — %d fictional rows removed",
                 purged)
