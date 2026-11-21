# -*- coding: utf-8 -*-
"""Approval Matrix P6 — fill the "who this is about" links on old requests.

A request has always carried the people it is about as a frozen Json list. A
Json list cannot be searched and cannot appear in a domain, so a manager's own
queue — "everything waiting about somebody who works for me" — had no way to
be asked for. The list is now mirrored into a real link, and this fills it in
for every request that already exists.

Idempotent: it only writes rows whose link is empty.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    requests = env['biz.approval.request'].sudo().search(
        [('subject_user_ids', '=', False)])
    filled = 0
    for request in requests:
        uids = [int(u) for u in (request.subject_uids or []) if u]
        if not uids:
            continue
        try:
            request.write({'subject_user_ids': [(6, 0, uids)]})
            filled += 1
        except Exception:       # noqa: BLE001 — one bad row stops nothing
            _logger.exception('approval: request %s could not be linked to '
                              'the people it is about', request.id)
    _logger.info('approval: %s requests now say who they are about', filled)
