# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What Expenses tells Workflow Studio about a claim's lines (WF2 P5c).

"Repeat for each…" in Workflow Studio can run a group of steps once per
receipt on a claim. Studio never walks a claim's fields itself: it reads the
lines through this door, which says what a receipt is called and which of its
details a workflow may use (conditions, notices, task titles). Read only:
nothing here changes a claim or a receipt, and no value is opened for writing
on a line. Duck-typed, so this module still does not depend on Studio.
Method-only file, loaded by a restart (no version bump, ledger G29).
"""

from odoo import api, fields, models
from odoo.tools.misc import format_date

#: A claim never has more lines than this read back (Studio caps a repeat at
#: 200; reading one more lets it say "more than the limit").
MAX_LINES = 201


class PbExpenseClaimWorkflowLines(models.Model):
    _inherit = 'pb.expense.claim'

    @api.model
    def _workflow_capabilities(self):
        caps = super()._workflow_capabilities()
        _ = self.env._
        caps['lines'] = [{
            'key': 'receipts', 'label': _('Receipts'), 'singular': _('receipt'),
            'fields': [
                {'key': 'description', 'label': _('Description'), 'type': 'text'},
                {'key': 'date', 'label': _('Date'), 'type': 'date'},
                {'key': 'category', 'label': _('Category'), 'type': 'text'},
                {'key': 'amount', 'label': _('Amount'), 'type': 'number'},
            ],
        }]
        return caps

    def _workflow_lines(self, key):
        """[{id, name, values}] — one per receipt, oldest first."""
        self.ensure_one()
        if key != 'receipts':
            return []
        rows = []
        for exp in self.sudo().expense_ids.sorted(lambda e: (e.date or fields.Date.today(), e.id))[:MAX_LINES]:
            day = format_date(self.env, exp.date, date_format='d MMM') if exp.date else ''
            name = ' · '.join(x for x in (exp.name or exp.product_id.name or '', day) if x)
            rows.append({'id': exp.id, 'name': name, 'values': {
                'description': exp.name or '',
                'date': fields.Date.to_string(exp.date) if exp.date else None,
                'category': exp.product_id.name or '',
                'amount': float(exp.total_amount_currency or 0.0),
            }})
        return rows
