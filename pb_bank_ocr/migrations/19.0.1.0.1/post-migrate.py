# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""post_init_hook only fires on fresh installs — existing databases get the
finance reviewer groups grafted here instead."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    from odoo.addons.pb_bank_ocr import _add_finance_reviewer_groups
    env = api.Environment(cr, SUPERUSER_ID, {})
    _add_finance_reviewer_groups(env)
