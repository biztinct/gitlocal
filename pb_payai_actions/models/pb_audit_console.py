# -*- coding: utf-8 -*-
"""P3 — the Audit console's PayAI rows say how a decision was confirmed.

A Red request (approve / send back / reject) is confirmed by the person
TYPING its word. Its row in the console carries a "Typed confirmation"
badge (drawn by `static/src/xml/audit_badge.xml`), so a reviewer sees at a
glance that a decision recorded through PayAI was typed, never tapped or
spoken. Read-only: the row is the console's own, one key added.
"""
from odoo import api, models


class PbAuditConsole(models.AbstractModel):
    _inherit = 'pb.audit.console'

    @api.model
    def _fetch_payai(self, filters, limit):
        rows = super()._fetch_payai(filters, limit)
        ids = []
        for row in rows:
            try:
                ids.append(int(str(row.get('key') or '').split('-', 1)[1]))
            except (IndexError, ValueError):
                continue
        if not ids:
            return rows
        typed = set(self.env['payai.task'].sudo().search(
            [('id', 'in', ids), ('confirm_kind', '=', 'typed')]).ids)
        label = self.env._('Typed confirmation')
        for row in rows:
            try:
                rid = int(str(row.get('key') or '').split('-', 1)[1])
            except (IndexError, ValueError):
                continue
            if rid in typed:
                row['badge'] = {'label': label, 'kind': 'typed'}
        return rows
