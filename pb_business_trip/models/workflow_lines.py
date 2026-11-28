# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What Business trips tells Workflow Studio about a trip's lines (WF2 P6a).

A trip has one destination and no legs; its lines are its estimated costs
(`pb.business.trip.line`: date, category, description, amount, receipt).
"Repeat for each…" in Workflow Studio can run a group of steps once per cost
line ("cost 2 of 4 · Hotel · 10 Nov"). Studio never walks a trip's fields
itself: it reads the lines through this door. Same shape as the expense
receipts door (`pb_me_expense/models/workflow_lines.py`).

Trips declare nothing else to Studio (no stages, no actions, nothing a
workflow may set): only the lines are added, so everything else Studio shows
for a trip is discovered exactly as before. Read only: nothing here changes a
trip or a line. Duck-typed, so this module still does not depend on Studio.
Method-only file, loaded by a restart (no version bump, ledger G29).
"""

from odoo import api, fields, models
from odoo.tools.misc import format_date

#: A trip never has more lines than this read back (Studio caps a repeat at
#: 200; reading one more lets it say "more than the limit").
MAX_LINES = 201


class PbBusinessTripWorkflowLines(models.Model):
    _inherit = 'pb.business.trip'

    @api.model
    def _workflow_capabilities(self):
        caps = dict(super()._workflow_capabilities() or {}) if hasattr(super(), '_workflow_capabilities') else {}
        _ = self.env._
        caps['lines'] = [{
            'key': 'costs', 'label': _('Costs'), 'singular': _('cost'),
            'fields': [
                {'key': 'description', 'label': _('Description'), 'type': 'text'},
                {'key': 'date', 'label': _('Date'), 'type': 'date'},
                {'key': 'category', 'label': _('Category'), 'type': 'text'},
                {'key': 'amount', 'label': _('Amount'), 'type': 'number'},
                {'key': 'has_receipt', 'label': _('Has a receipt'), 'type': 'yesno'},
            ],
        }]
        return caps

    def _pb_cost_row(self, line):
        day = format_date(self.env, line.date, date_format='d MMM') if line.date else ''
        name = ' · '.join(x for x in (line.description or line.category_id.name or '', day) if x)
        return {'id': line.id, 'name': name, 'values': {
            'description': line.description or '',
            'date': fields.Date.to_string(line.date) if line.date else None,
            'category': line.category_id.name or '',
            'amount': float(line.amount or 0.0),
            'has_receipt': bool(line.receipt_attachment_id),
        }}

    def _workflow_lines(self, key):
        """[{id, name, values}] — one per cost line, oldest first."""
        self.ensure_one()
        if key != 'costs':
            return []
        lines = self.sudo().line_ids.sorted(lambda l: (l.date or fields.Date.today(), l.id))[:MAX_LINES]
        return [self._pb_cost_row(l) for l in lines]

    def _workflow_line(self, key, line_id):
        """One cost line's row, read again now; None when it was removed."""
        self.ensure_one()
        if key != 'costs':
            return None
        line = self.sudo().line_ids.filtered(lambda l: str(l.id) == str(line_id))
        return self._pb_cost_row(line[:1]) if line else None
