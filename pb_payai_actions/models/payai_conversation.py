# -*- coding: utf-8 -*-
"""The chat session learns which screens (⌘K rows) its person may open.

THE DOORS COME FROM THE BROWSER, AND THAT IS ACCEPTABLE FOR WHAT THEY DO.
The ⌘K registry lives in the client (37 modules' `*_palette.js`), already
filtered for this person by `hub_palette_service.entries()`. The chat sends
those rows here when it mounts; `open_screen` resolves the person's words
against them and answers with a row id the client then runs through the very
code path ⌘K uses. Opening a screen is navigation: every screen still asks
its own server-side questions. The server re-checks each row's `groups`
anyway (defence in depth, P1_HANDOVER) and never builds anything but a
navigation out of a row.
"""
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MAX_DOORS = 600
_TEXT_CAP = 120


def _clean_str(value, cap=_TEXT_CAP):
    if not isinstance(value, str):
        return ''
    return ' '.join(value.split())[:cap]


class PayrollAIConversation(models.Model):
    _inherit = 'payroll.ai.conversation'

    payai_doors_json = fields.Text(
        string='Screens this person may open',
        help="JSON list of the ⌘K rows the person's browser offered: id, "
             "label, where it lives and the permissions it names.")

    @api.model
    def rpc_register_doors(self, session_id=None, rows=None):
        """Store the person's visible ⌘K rows on their own conversation."""
        session = self.browse(int(session_id)).exists() if session_id else self.browse()
        if not session or session.user_id != self.env.user:
            session = self.get_or_create_session()
        clean = []
        seen = set()
        for row in (rows or [])[:MAX_DOORS]:
            if not isinstance(row, dict):
                continue
            rid = _clean_str(row.get('id'), 80)
            if not rid or rid in seen or rid == 'payai_ask':
                continue
            if row.get('restricted'):
                continue
            seen.add(rid)
            groups = [g for g in (row.get('groups') or [])
                      if isinstance(g, str) and '.' in g][:12]
            clean.append({
                'id': rid,
                'label': _clean_str(row.get('label')),
                'sublabel': _clean_str(row.get('sublabel')),
                'group': _clean_str(row.get('group'), 60),
                'groups': groups,
            })
        blob = json.dumps(clean, ensure_ascii=False)
        if session.payai_doors_json != blob:
            session.write({'payai_doors_json': blob})
        return {'session_id': session.id, 'count': len(clean)}

    def payai_doors(self):
        """The registered rows, or [] on any shape problem."""
        self.ensure_one()
        try:
            rows = json.loads(self.payai_doors_json or '[]')
        except (TypeError, ValueError):
            return []
        return [r for r in rows if isinstance(r, dict) and r.get('id')]
