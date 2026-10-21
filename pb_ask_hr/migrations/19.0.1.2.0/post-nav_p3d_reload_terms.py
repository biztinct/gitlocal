# -*- coding: utf-8 -*-
"""NAV P3d — the two Vietnamese words the Ask HR board shares with the rest
of the module now read the same everywhere.

"With HR" is "Nhân sự đang xử lý" (it was "Đang ở Nhân sự") and "Nobody has
it yet" is "Chưa ai nhận" (it was "Chưa có ai nhận"), the words the owner gave
for the board and the words Learn already uses. Code words (the board, the
"My requests" list) read the .po directly, but STORED words — the status
choice on the native screens, the portal pill, the search filters — keep their
old value through an ordinary upgrade, because an upgrade never overwrites a
translation that is already there (LOOK ledger: a translation fix is two
fixes). So this one module's terms are re-read with overwrite, once.

Only pb_ask_hr's own terms, from its own .po: nothing else is touched.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env['ir.module.module'].search([('name', '=', 'pb_ask_hr')], limit=1)
    if module:
        module._update_translations(overwrite=True)
        _logger.info('pb_ask_hr: Vietnamese terms re-read with overwrite (NAV P3d)')
