# -*- coding: utf-8 -*-
"""LEARNREV P5a - "Right now" for the Approval Matrix.

What the grid's own attention banner would tell a person, in the order they
should act: routes that reach a part of the business where nobody is named
(requests from there stop until somebody is), then routes still in draft, or
nothing. Read from `get_matrix`, so every count is the screen's own count, and
run as the person asking (the matrix is for people who set approvals up; the
caller handles the AccessError for anybody else).

Declared in `pb_approval_config/learn_manifest.py` as
`pb.approval.matrix.learn_right_now` and called by pb_learn's guide; this
module never imports pb_learn.
"""
from odoo import api, models

NAMED = 3
MATRIX = 'pb_approval_config.action_pb_approval_matrix'


def _names(names, lang):
    shown = ', '.join(names[:NAMED])
    rest = len(names) - NAMED
    if rest > 0:
        shown += (' và %d mục khác' % rest) if lang == 'vi' else (' and %d more' % rest)
    return shown


class PbApprovalMatrixLearn(models.AbstractModel):
    _inherit = 'pb.approval.matrix'

    @api.model
    def _learn_open_matrix(self):
        """An `open` action when the Matrix exists on this database, else None."""
        if not self.env.ref(MATRIX, raise_if_not_found=False):
            return None
        return {'kind': 'open', 'xmlid': MATRIX, 'focus': None, 'context': {}}

    @api.model
    def learn_right_now(self, args=None):
        data = self.get_matrix()
        rows = [row for area in data.get('areas') or () for row in area['rows']]
        items = []

        needs = [r for r in rows if r.get('status') == 'needs']
        if needs:
            n = len(needs)
            names = [r['name'] for r in needs]
            gaps = sum(r.get('needs_people') or 0 for r in needs)
            items.append({
                'key': 'needs_people', 'count': n, 'severity': 'warn',
                'names': names[:NAMED], 'gaps': gaps,
                'text': {
                    'en': ("%s needs people: requests stop there until somebody is "
                           "named." % names[0]) if n == 1 else
                          ("%d routes need people: %s. Requests stop there until "
                           "somebody is named." % (n, _names(names, 'en'))),
                    'vi': ("%s cần bổ sung người: yêu cầu dừng ở đó cho tới khi có "
                           "người được ghi tên." % names[0]) if n == 1 else
                          ("%d lộ trình cần bổ sung người: %s. Yêu cầu dừng ở đó cho "
                           "tới khi có người được ghi tên." % (n, _names(names, 'vi'))),
                },
                'action': self._learn_open_matrix(),
            })

        drafts = [r for r in rows if r.get('status') == 'draft'
                  and r.get('connected') and r.get('version')]
        if drafts:
            n = len(drafts)
            names = [r['name'] for r in drafts]
            items.append({
                'key': 'draft', 'count': n, 'severity': 'info',
                'names': names[:NAMED],
                'text': {
                    'en': ("%s is still a draft. Publish it when it is ready." % names[0])
                          if n == 1 else
                          ("%d routes are still drafts: %s. Publish them when they "
                           "are ready." % (n, _names(names, 'en'))),
                    'vi': ("%s vẫn là bản nháp. Hãy ban hành khi đã sẵn sàng."
                           % names[0]) if n == 1 else
                          ("%d lộ trình vẫn là bản nháp: %s. Hãy ban hành khi đã sẵn "
                           "sàng." % (n, _names(names, 'vi'))),
                },
                'action': self._learn_open_matrix(),
            })

        if not items:
            items.append({
                'key': 'ok', 'count': 0, 'severity': 'ok',
                'text': {'en': "Every route has people named. Nothing here needs you "
                               "right now.",
                         'vi': "Mọi lộ trình đều đã có người được ghi tên. Lúc này "
                               "không có việc gì ở đây cần bạn."},
                'action': None,
            })
        return items
