# -*- coding: utf-8 -*-
"""LEARNREV P5 — "Right now" for the Import screen.

What the screen's own counts say a person should do first, in order: batches
with rows that still need a person matched, batches with error rows, batches
checked and ready to commit — or nothing. Read from `get_import_data`, so every
count is the screen's own count, and run as the asking person, so they see
exactly the batches the screen shows them.

Declared in `pb_import/learn_manifest.py` as `pb.import.learn_right_now` and
called by pb_learn's guide; this module never imports pb_learn.
"""
from odoo import api, models

NAMED = 3
BATCH_MODEL = 'hr.payroll.import.batch'


def _names(names, lang):
    shown = ', '.join(names[:NAMED])
    rest = len(names) - NAMED
    if rest > 0:
        shown += (' và %d đợt khác' % rest) if lang == 'vi' else (' and %d more' % rest)
    return shown


class PbImportLearn(models.AbstractModel):
    _inherit = 'pb.import'

    @api.model
    def _learn_batch(self, batch_id):
        """Open that import batch's own record."""
        return {'kind': 'open_record', 'res_model': BATCH_MODEL, 'res_id': batch_id}

    @api.model
    def learn_right_now(self, args=None):
        batches = self.get_import_data().get('batches') or []
        items = []

        to_match = []
        for b in batches:
            if b.get('state') not in ('loaded', 'matched'):
                continue
            open_rows = (b.get('total_lines') or 0) - (b.get('matched') or 0) \
                - (b.get('new') or 0)
            if open_rows > 0:
                to_match.append((b, open_rows))
        if to_match:
            rows = sum(n for _b, n in to_match)
            names = [b['name'] for b, _n in to_match]
            where_en = names[0] if len(names) == 1 else \
                '%d batches (%s)' % (len(names), _names(names, 'en'))
            where_vi = names[0] if len(names) == 1 else \
                '%d đợt (%s)' % (len(names), _names(names, 'vi'))
            items.append({
                'key': 'needs_match', 'count': rows, 'severity': 'warn',
                'names': names[:NAMED],
                'text': {
                    'en': "%d rows in %s still need a person matched. Match them "
                          "before anything is written." % (rows, where_en),
                    'vi': "%d dòng trong %s vẫn cần khớp với một nhân viên. Hãy khớp "
                          "trước khi ghi bất cứ gì." % (rows, where_vi),
                },
                'action': self._learn_batch(to_match[0][0]['id']),
            })

        with_errors = [b for b in batches
                       if (b.get('errors') or 0) > 0
                       and b.get('state') not in ('done', 'cancelled')]
        if with_errors:
            rows = sum(b['errors'] for b in with_errors)
            names = [b['name'] for b in with_errors]
            items.append({
                'key': 'has_errors', 'count': rows, 'severity': 'warn',
                'names': names[:NAMED],
                'text': {
                    'en': "%d rows have errors (%s). Fix them in the batch before "
                          "you commit." % (rows, _names(names, 'en')),
                    'vi': "%d dòng có lỗi (%s). Hãy sửa trong đợt nhập trước khi "
                          "ghi." % (rows, _names(names, 'vi')),
                },
                'action': {'kind': 'filter', 'value': 'errors'},
            })

        ready = [b for b in batches if b.get('state') == 'validated']
        if ready:
            names = [b['name'] for b in ready]
            items.append({
                'key': 'ready_to_commit', 'count': len(ready), 'severity': 'info',
                'names': names[:NAMED],
                'text': {
                    'en': ("%s is checked and ready to commit." % names[0])
                          if len(ready) == 1 else
                          ("%d batches are checked and ready to commit: %s."
                           % (len(ready), _names(names, 'en'))),
                    'vi': ("Đợt %s đã kiểm tra và sẵn sàng ghi." % names[0])
                          if len(ready) == 1 else
                          ("%d đợt đã kiểm tra và sẵn sàng ghi: %s."
                           % (len(ready), _names(names, 'vi'))),
                },
                'action': self._learn_batch(ready[0]['id']),
            })

        if not items:
            items.append({
                'key': 'ok', 'count': 0, 'severity': 'ok',
                'text': {
                    'en': "Nothing is waiting on a match. Press Load pay data to "
                          "bring in this period's numbers.",
                    'vi': "Không có gì đang chờ khớp. Bấm Tải dữ liệu lương để đưa "
                          "số liệu của kỳ này vào.",
                },
                'action': None,
            })
        return items
