# -*- coding: utf-8 -*-
"""Integrations Cycle 6 — give the connectors that ALREADY exist their fields.

The same shape as Cycle 3's `post-stamp_endpoint_codes.py`, and for the same
reason. `action_sync_endpoint_field_catalog` runs from
`action_sync_endpoint_catalog`, which runs on connector CREATE and from the
cockpit's "Detect feeds" button. That is exactly right for a connector made
after this cycle, and a complete no-op for every connector made before it —
which, on this box, is all of them:

    SELECT count(*) FROM hr_integration_endpoint_field;   -->  0

on both `payobook` and `abm` immediately after the first `-u`, with all 94
template rows loaded. The board would have gone on showing 206 `hr.employee`
columns under "FROM — ZOHO PEOPLE (ABM)" while the catalogue that fixes it sat
in the database unused, and nothing would have errored. W121's second-pass
rule: shipping the data is not the same as landing it.

Two properties, in order of importance:

  1. **It never overwrites.** `action_sync_endpoint_field_catalog` is
     create-only on `(endpoint_id, path)` with `active_test=False`, so a row an
     operator has relabelled, re-sampled or switched off is skipped. This script
     adds nothing to that contract — it only calls it.
  2. **It is idempotent and safe to re-run.** Running it twice creates zero
     rows, which is what makes it safe to leave in the tree.

Per-connector `try/except`: one vendor whose catalogue has a problem must not
abort the upgrade of a database, and a silent skip would be indistinguishable
from a vendor we have no catalogue for (W79), so each one is named in the log.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'hr.integration.endpoint.field' not in env:
        return
    Field = env['hr.integration.endpoint.field']
    if not Field._schema_ready():
        return

    created = skipped = unresolved = 0
    connectors = env['hr.integration.connector'].with_context(
        active_test=False).search([])
    for c in connectors:
        try:
            res = c.action_sync_endpoint_field_catalog()
        except Exception as e:                        # pragma: no cover
            _logger.warning(
                "Cycle 6: could not catalogue fields for connector %s (%s): "
                "%s: %s", c.id, c.connector_type, type(e).__name__, e)
            continue
        created += res.get('created', 0)
        skipped += res.get('skipped', 0)
        unresolved += res.get('unresolved', 0)

    _logger.info(
        "Cycle 6: expected-field catalogue instantiated on %s connectors — "
        "%s created, %s already present, %s templates naming a feed these "
        "connectors have not got.",
        len(connectors), created, skipped, unresolved)
