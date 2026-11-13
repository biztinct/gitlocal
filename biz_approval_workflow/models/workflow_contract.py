# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What an "Other request" tells Workflow Studio about itself (WF2 P3b).

Read-only declarations, nothing else: the request's own statuses in their
real order (its end statuses flagged, so a workflow knows the record stops
there), where each approval outcome leaves it, and who it is about. The
request has no effects of its own beyond the approval engine's, which Studio
reads from the engine. Studio reads this through a duck-typed hook, so this
module still depends on nothing (manifest: zero product dependencies).
"""

from odoo import api, models


class BizApprovalGenericRequestWorkflowContract(models.Model):
    _inherit = 'biz.approval.generic.request'

    @api.model
    def _workflow_capabilities(self):
        _ = self.env._
        # The stage names are the request's own status labels, as every
        # screen shows them (and as they are translated).
        names = dict(self._fields['state']._description_selection(self.env))
        return {
            'label': _('Other request'),
            'area': _('Approvals'),
            'stage_field': 'state',
            'stages': [
                {'key': 'draft', 'name': names['draft'],
                 'enters': _('Someone writes down what they are asking for')},
                # Sent back can be changed and sent again, so it is not an
                # end; it sits before "Waiting for approval" and is optional
                # (most requests never go there).
                {'key': 'returned', 'name': names['returned'], 'optional': True,
                 'enters': _('An approver sends it back to be changed')},
                {'key': 'pending', 'name': names['pending'], 'approval': True,
                 'enters': _('Someone sends it for a sign-off')},
                {'key': 'done', 'name': names['done'],
                 'enters': _('The last approver says yes')},
                {'key': 'rejected', 'name': names['rejected'], 'exit': True,
                 'enters': _('An approver says no')},
                {'key': 'cancelled', 'name': names['cancelled'], 'exit': True,
                 'enters': _('The person who asked takes it back')},
            ],
            'approval_outcomes': {'approved': 'done', 'returned': 'returned',
                                  'rejected': 'rejected'},
            'effects': [],
        }

    def _workflow_subject(self):
        """The person who asked, and their manager when they are also an
        employee (looked up only when the people module is installed)."""
        self.ensure_one()
        login = self.sudo().requester_user_id
        employee = None
        if 'hr.employee' in self.env:
            employee = self.env['hr.employee'].sudo().search([
                ('user_id', '=', login.id), ('company_id', '=', self.sudo().company_id.id)],
                limit=1) if login else self.env['hr.employee']
        return {
            'employee': employee,
            'user': login,
            'manager_user': employee.parent_id.user_id if employee else self.env['res.users'],
        }
