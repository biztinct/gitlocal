# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What Pay runs tells Workflow Studio about a pay run (WF2 P3b).

Read-only declarations: the run's own statuses in their real order (from
the one status map the board, the kanban and the form already read),
"Rejected" flagged as the end it is, where each approval outcome leaves the
run, and what the pay run itself already does to its payslips at each step
(inventory 1.3; the module sends no message of its own). No operations, no
values a workflow may set, nobody it is "about" (a run is a batch). Nothing
here changes how a pay run behaves; Studio reads it through a duck-typed hook.
"""

from odoo import api, models

from .hr_payslip_run import PB_STAGE_NAME


class HrPayslipRunWorkflowContract(models.Model):
    _inherit = 'hr.payslip.run'

    @api.model
    def _workflow_capabilities(self):
        _ = self.env._
        area = _('Pay runs')
        settings = {'action': 'pb_payruns.action_pb_payruns'}
        return {
            'label': _('Pay run'),
            'area': area,
            'stage_field': 'state',
            'stages': [
                {'key': 'draft', 'name': _(PB_STAGE_NAME['draft']),
                 'enters': _('Someone prepares the pay run, or it comes back to them')},
                {'key': 'approval_pending', 'name': _(PB_STAGE_NAME['approval_pending']),
                 'approval': True, 'enters': _('Someone sends the pay run for approval')},
                {'key': 'done', 'name': _(PB_STAGE_NAME['done']),
                 'enters': _('The last approver says yes')},
                {'key': 'cancel', 'name': _(PB_STAGE_NAME['cancel']), 'exit': True,
                 'enters': _('An approver turns it down')},
            ],
            'approval_outcomes': {'approved': 'done', 'returned': 'draft',
                                  'rejected': 'cancel'},
            'effects': [
                {'stage': 'approval_pending', 'kind': 'change', 'audience': 'other',
                 'owner': area, 'settings': settings,
                 'text': _('Its payslips are checked and held while the run waits '
                           'for approval, so nobody can change or pay them.')},
                {'stage': 'done', 'kind': 'change', 'audience': 'other',
                 'owner': area, 'settings': settings,
                 'text': _('Its payslips are finished, ready for payslips, bank '
                           'files and payment.')},
                {'stage': 'cancel', 'kind': 'change', 'audience': 'other',
                 'owner': area, 'settings': settings,
                 'text': _('Its payslips are cancelled.')},
            ],
            'screen': 'pb_payruns',
        }
