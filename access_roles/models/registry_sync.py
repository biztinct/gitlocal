# -*- coding: utf-8 -*-
"""Gate for the view-scan `_register_hook` syncs (filter/button/tab/groupby).

Those four registries harvest their records by reading and parsing EVERY
ir.ui.view in the database — historically on EVERY registry load, which on a
large database adds minutes to each load and (via their create-or-update
writes) re-signals cache invalidations to the other workers, amplifying any
reload into a storm.

The harvest only ever changes when the view set changes, so each registry now
asks `needs_sync(<its key>)` first: a cheap one-query signature over
ir_ui_view (count | max write_date | max id) compared against the last synced
signature stored in ir.config_parameter. Unchanged views -> the whole scan is
skipped. The stamp is written in the same transaction as the sync itself, so
a failed load rolls both back together. Fail-open: any error in the gate
falls back to syncing, never to silently skipping.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccessRegistrySync(models.AbstractModel):
    _name = 'access.registry.sync'
    _description = 'Access Roles Registry Sync Gate'

    @api.model
    def _views_signature(self):
        self.env.cr.execute(
            "SELECT COUNT(*), COALESCE(MAX(write_date)::text, ''), "
            "COALESCE(MAX(id), 0) FROM ir_ui_view")
        count, max_wd, max_id = self.env.cr.fetchone()
        return '%s|%s|%s' % (count, max_wd, max_id)

    @api.model
    def needs_sync(self, key):
        """True when ir.ui.view changed since the last sync recorded under
        `key` — and stamps the new signature, so a True return MUST be
        followed by the sync in the same transaction."""
        try:
            sig = self._views_signature()
            params = self.env['ir.config_parameter'].sudo()
            if params.get_param(key) == sig:
                return False
            params.set_param(key, sig)
            return True
        except Exception:
            _logger.exception("access.registry.sync: gate failed for %s — "
                              "falling back to a full sync", key)
            return True
