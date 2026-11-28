# -*- coding: utf-8 -*-
"""TIDY-E2 — on upgrade, write the stored vi / id name of Country of Work where
it still holds an old wording (deploy report TE-D1; see hooks.py). Runs at the
end of the upgrade, after every module's translations are loaded."""

from odoo import SUPERUSER_ID, api

from odoo.addons.pb_employee_form_tidy.hooks import fix_country_of_work_label


def migrate(cr, version):
    if not version:
        return
    fix_country_of_work_label(api.Environment(cr, SUPERUSER_ID, {}))
