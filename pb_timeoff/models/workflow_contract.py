# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What Time off tells Workflow Studio about a time-off request (WF2 P2).

Read-only declarations: the request's stages in their real order, what
moves a request into each, what Time off (and the standard time-off module
underneath it) already does at each stage, and who a request is about.
Nothing here changes how time off behaves. Studio reads this through a
duck-typed hook, so this module does not depend on it.
"""

from odoo import _, api, models


class HrLeaveWorkflowContract(models.Model):
    _inherit = 'hr.leave'

    @api.model
    def _workflow_capabilities(self):
        # The stage names are the request's own status labels, as every
        # screen shows them (and as they are translated).
        names = dict(self._fields['state']._description_selection(self.env))
        area = _('Time off')
        settings = {'action': 'pb_timeoff.action_pb_timeoff'}
        return {
            'label': _('Time off request'),
            'area': area,
            'stage_field': 'state',
            # A request is sent for approval by itself when the company has
            # an approval route (`create`, hr_leave_approval.py).
            'submits_itself': True,
            'stages': [
                {'key': 'confirm', 'name': names['confirm'], 'approval': True,
                 'enters': _('The employee asks for time off')},
                {'key': 'validate1', 'name': names['validate1'], 'optional': True,
                 'enters': _('The first approver says yes and a second approval is needed')},
                {'key': 'validate', 'name': names['validate'],
                 'enters': _('The last approver says yes, or straight away when this '
                             'kind of time off needs no approval')},
                {'key': 'refuse', 'name': names['refuse'], 'exit': True,
                 'enters': _('An approver says no, or sends it back')},
                {'key': 'cancel', 'name': names['cancel'], 'exit': True,
                 'enters': _('The time off is cancelled')},
            ],
            # A request sent back is refused with the reason (there is no
            # draft for time off under approval).
            'approval_outcomes': {'approved': 'validate', 'returned': 'refuse',
                                  'rejected': 'refuse'},
            'effects': [
                # WF2 P2b (D5): with a live route only the route tells the
                # people it asks; this to-do is for anyone it does not ask.
                {'stage': 'confirm', 'kind': 'todo', 'audience': 'approver',
                 'owner': area, 'settings': settings,
                 'text': _('The person who approves this employee’s time off gets a to-do, '
                           'unless the approval route already asks them.')},
                {'stage': 'confirm', 'kind': 'change', 'audience': 'approver',
                 'owner': area, 'settings': settings,
                 'text': _('A new request is sent for approval by itself when an '
                           'approval route is set up.')},
                {'stage': 'confirm', 'kind': 'message', 'audience': 'other',
                 'owner': area, 'settings': settings,
                 'text': _('When time off is asked for after the days have passed, the HR '
                           'lead gets an email and a to-do. Only for kinds of time off '
                           'with “Tell HR when it is” switched on.')},
                {'stage': 'validate1', 'kind': 'todo', 'audience': 'approver',
                 'owner': area, 'settings': settings,
                 'text': _('When a second approval is needed, the second approver gets a to-do, '
                           'unless the approval route already asks them.')},
                {'stage': 'validate', 'kind': 'message', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('The employee is told their time off is approved.')},
                {'stage': 'validate', 'kind': 'change', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('The days come off the employee’s balance.')},
                {'stage': 'refuse', 'kind': 'message', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('The employee is told their time off was refused.')},
                {'stage': None, 'kind': 'reminder', 'audience': 'requester',
                 'owner': area, 'settings': settings,
                 'text': _('Once a month, as the carry-forward date comes round, people '
                           'holding too many days and their managers get a warning '
                           'email. Only when the warning is switched on.')},
            ],
            'screen': 'pb_timeoff',
        }

    def _workflow_subject(self):
        """The employee the request is for, and their manager by the
        time-off rule: the leave manager first, else their line manager's
        login (`_approval_manager_uids`)."""
        self.ensure_one()
        employee = self.sudo().employee_id
        return {
            'employee': employee,
            'user': employee.user_id,
            'manager_user': employee.leave_manager_id or employee.parent_id.user_id,
        }
