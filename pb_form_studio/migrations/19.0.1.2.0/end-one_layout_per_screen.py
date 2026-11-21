# -*- coding: utf-8 -*-
"""R18 (owner, 2026-11-20): one published layout per screen for every company.

Before 19.0.1.2.0 a layout was stored and looked up per company, so a field
placed while working in company A never showed on the employee or contract
panels in company B. The engine now reads ONE layout per screen
(`pb.form.studio._pbfs_layout`). This folds any screen that still has a
layout in several companies into one (`_pbfs_merge_company_layouts`: the
newest published wins, fields placed only in another company's layout are
added to the same section) and re-draws the Full details pages of the record
types it touched.

An `end-` script on purpose: the screens (hosts) are registered by the
bridge modules loaded after this one, and the Full details pages can only
be re-drawn once they are in the registry.

Idempotent: a second run finds at most one layout per screen and writes
nothing. A database with no layout (no custom field ever placed) writes
nothing at all.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT count(*), count(DISTINCT host_key) FROM pb_form_layout")
    rows, screens = cr.fetchone()
    if rows <= screens:
        _logger.info('pb_form_studio R18: %s layout(s) for %s screen(s), one each; '
                     'nothing to fold', rows, screens)
        return
    try:
        with cr.savepoint():
            out = env['pb.form.studio']._pbfs_merge_company_layouts()
    except Exception:       # noqa: BLE001 — an upgrade must not die here
        _logger.exception('pb_form_studio R18: layouts could not be folded; the newest '
                          'published layout of each screen is used meanwhile')
        return
    _logger.info('pb_form_studio R18: folded %(screens)s screen(s) into one layout each; '
                 '%(removed)s per-company layout(s) removed, %(added)s field placement(s) '
                 'carried over', out)
