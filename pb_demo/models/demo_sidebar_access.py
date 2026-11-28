# -*- coding: utf-8 -*-
"""Keep the Demo User's sidebar/access wiring alive across upgrades.

`post_init_demo` (the module's post_init_hook) grants the demo group to every
group-gated sidebar item — but a post_init hook runs ONLY on install. A
reverse-dependency cascade (e.g. `-u biz_theme` re-upgrades everything that
depends on it, including pb_sidebar) reloads pb_sidebar's `noupdate="0"` data,
which resets each `pb.sidebar.item.groups_id` with a full-replace `(6,0,[…])` and
drops the demo group. The hook does not re-run, so the demo user silently loses
Formula Engine (and every other gated cockpit).

The `<function>` in `data/pb_demo_sidebar_access.xml` calls `_pb_demo_rewire`
on every module update. pb_demo loads AFTER pb_sidebar in any cascade, so the
grant is re-applied right after the reset — declaratively, no manual UI edits.
"""
from odoo import api, models

from ..hooks import post_init_demo


class PbSidebarItem(models.Model):
    _inherit = 'pb.sidebar.item'

    @api.model
    def _pb_demo_rewire(self):
        """Re-apply the full Demo User wiring (model access + gated-item group
        joins + restricted markers). Idempotent — safe to run on every upgrade."""
        post_init_demo(self.env)
