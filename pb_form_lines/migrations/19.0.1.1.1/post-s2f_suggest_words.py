# -*- coding: utf-8 -*-
"""WDGAP S2-F — the catalogue is noupdate: bring the Indonesian BPJS and
monthly-tax lines' Suggest words to the shipped values on databases that
already have them. Only lines whose words still equal the value shipped
before are touched; idempotent. See `models/suggest_s2f.py`."""
from odoo import SUPERUSER_ID, api

from odoo.addons.pb_form_lines.models import suggest_s2f


def migrate(cr, version):
    if not version:
        return
    suggest_s2f.apply(api.Environment(cr, SUPERUSER_ID, {}))
