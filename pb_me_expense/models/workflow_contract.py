# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What Expenses tells Workflow Studio about an expense claim (WF2 P2).

Read-only declarations: the claim's stages in their real order and what
moves a claim into each, what Expenses itself already does at each stage,
and who a claim is about. Nothing here changes how a claim behaves. Studio
reads this through a duck-typed hook, so this module does not depend on it.
"""

from odoo import api, models


class PbExpenseClaimWorkflowContract(models.Model):
    _inherit = 'pb.expense.claim'

    @api.model
    def _workflow_capabilities(self):
        _ = self.env._
        # The stage names are the claim's own status labels, as every screen
        # shows them (and as they are translated).
        names = dict(self._fields['state']._description_selection(self.env))
        area = _('Expenses')
        settings = {'action': 'pb_expenses_hub.action_pb_expenses_hub'}
        return {
            'label': _('Expense claim'),
            'area': area,
            'stage_field': 'state',
            'stages': [
                {'key': 'draft', 'name': names['draft'],
                 'enters': _('The employee starts a claim, or it comes back to them')},
                {'key': 'submitted', 'name': names['submitted'], 'approval': True,
                 'enters': _('The employee sends the claim')},
                {'key': 'approved', 'name': names['approved'],
                 'enters': _('The last approver says yes')},
                {'key': 'paid', 'name': names['paid'],
                 'enters': _('Every receipt on the claim has been paid')},
                {'key': 'refused', 'name': names['refused'], 'exit': True,
                 'enters': _('An approver says no')},
            ],
            # Where each approval outcome leaves the claim.
            'approval_outcomes': {'approved': 'approved', 'returned': 'draft',
                                  'rejected': 'refused'},
            'effects': [
                {'stage': 'approved', 'kind': 'change', 'audience': 'other',
                 'owner': area, 'settings': settings,
                 'text': _('Every receipt on the claim is marked approved.')},
                {'stage': 'refused', 'kind': 'change', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('Every receipt is marked refused with the approver’s '
                           'reason, which the employee sees on their claim.')},
                {'stage': 'refused', 'kind': 'message', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('The employee home shows the employee a “fix and '
                           'resend” reminder.')},
                {'stage': 'draft', 'kind': 'change', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('When a claim is sent back or taken back, its '
                           'receipts can be changed and sent again.')},
            ],
            'screen': 'pb_expenses_hub',
        }

    def _workflow_subject(self):
        """The employee the claim is for, and their manager by Expenses' own
        rule: the expense approver set on the employee first, else their
        line manager's login (`_approval_manager_uids`)."""
        self.ensure_one()
        employee = self.sudo().employee_id
        return {
            'employee': employee,
            'user': employee.user_id,
            'manager_user': employee.expense_manager_id or employee.parent_id.user_id,
        }
