# -*- coding: utf-8 -*-
"""NEWHIRE P6 — the shipped equipment category names read in Vietnamese and Indonesian.

The records are `noupdate` data: the words already stored are never re-read
from the XML. This writes this module's own `i18n/vi_VN.po` / `id_ID.po`
words onto the SHIPPED rows whose English is still the shipped English, in
the languages active here, where that language holds nothing yet (or only a
copy of the English). Never the English, never a renamed row, never a row a
company made. Idempotent. Helper: pb_lifecycle.models.seed_translations.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.pb_lifecycle.models.seed_translations import apply_seed_translations

TARGETS = {'pb.asset.category': ['name']}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    apply_seed_translations(env, 'pb_assets', TARGETS)
