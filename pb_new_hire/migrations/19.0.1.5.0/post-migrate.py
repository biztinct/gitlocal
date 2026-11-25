# -*- coding: utf-8 -*-
"""NEWHIRE P5a — asked items are shown in the READER's language.

Rows made before this version stored only the words of the approver's
language. From now on a row is rendered from its item key and `label_kind`
(models/ask.py). New column `label_kind` defaults to `item`; this step finds
the rows that were asked by another of the item's words — a card whose
number HR typed (`card`) or a card that came across from Hiring (`number`) —
by comparing the stored words with step 5's list in every installed
language. Only those two keys can differ. Nothing else is written; the
stored words stay as the fallback.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MERGED_KEYS = ('id_number', 'tax_number')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Ask = env['pb.new.hire.ask'].sudo()
    rows = Ask.search([('key', 'in', MERGED_KEYS)])
    if not rows:
        return
    langs = [code for code, _name in env['res.lang'].get_installed()]
    Studio = env['pb.new.hire'].sudo().with_context(pb_nh_labels_only=True)
    lists = {}
    moved = 0
    for row in rows:
        code = row.employee_id.payroll_country or ''
        company = row.company_id or row.employee_id.company_id or env.company
        kind = 'item'
        for lang in langs:
            key = (code, company.id, lang)
            if key not in lists:
                try:
                    items = Studio.with_company(company).with_context(lang=lang)._detail_items(code, '') \
                        if code else []
                except Exception:               # noqa: BLE001 — leave the row as it is
                    _logger.warning('pb_new_hire 1.5.0: step 5 list for %s unreadable', code, exc_info=True)
                    items = []
                lists[key] = {i['key']: i for i in items}
            item = lists[key].get(row.key)
            if not item or row.label == item.get('label'):
                continue
            if item.get('upload') and row.label == item['upload'].get('label'):
                kind = 'card'
                break
            if item.get('fields') and row.label == item['fields'][0].get('label'):
                kind = 'number'
                break
        if kind != row.label_kind:
            row.write({'label_kind': kind})
            moved += 1
    _logger.info('pb_new_hire 1.5.0: %s of %s asked rows now read as the card or the number only',
                 moved, len(rows))
