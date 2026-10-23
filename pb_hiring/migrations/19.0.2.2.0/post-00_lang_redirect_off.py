# -*- coding: utf-8 -*-
"""RECRUIT P3 fix (a) — the browser-language redirect goes OFF, once.

Phase 2 added Vietnamese and Indonesian to every website so the apply page
could be read in them. The stock `website.auto_redirect_lang` (default ON)
then sent every visitor whose browser prefers one of those languages to the
`/vi` or `/id` copy of the WHOLE public site, whose marketing pages are not
translated (RC37). Fable's ruling: switch it off on every website.

What stays: the language switcher on the apply page and the apply page's own
pre-select from the role's market (RC38) — that redirect lives inside
`jobs_apply` and does not read this setting.

This module never turns the setting ON anywhere (nothing in pb_hiring writes
it), so running this once on the upgrade that ships it is the whole fix. A
client who wants the redirect back switches it on in the website settings
and no later upgrade touches it again.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('website')")
    if not cr.fetchone()[0]:
        return
    cr.execute("UPDATE website SET auto_redirect_lang = false "
               "WHERE auto_redirect_lang IS DISTINCT FROM false")
    _logger.info('pb_hiring 2.2.0: browser-language redirect switched off '
                 'on %s website(s)', cr.rowcount)
