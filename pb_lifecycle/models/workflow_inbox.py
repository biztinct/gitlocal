"""WF2 P4a (D1) — workflow tasks in the one Approvals inbox.

Fills the inbox's add-only seam (`pb_approval_config/models/inbox_extra.py`).
A task is never an approval: its card has no route and no decide buttons;
opening it shows Workflow Studio's own task page inside the inbox's drawer.

  * "me"   — tasks waiting on me: mine, or my team's that nobody has taken;
  * "team" — tasks of people who report to me (a read, for logins that may
             already view workflow progress);
  * "org"  — every waiting task in my companies (same gate, plus the inbox's
             own "whole company" gate).
"""
from odoo import api, models


class WorkflowInbox(models.AbstractModel):
    _inherit = 'pb.approval.inbox'

    def _studio(self):
        return self.env['pb.workflow.studio']

    @api.model
    def _extra_items(self, scope='me', search=None):
        items = list(super()._extra_items(scope, search) or [])
        studio = self._studio()
        if scope == 'team':
            items += studio._inbox_tasks('team', search, team_user_ids=self._my_team_user_ids())
        elif scope == 'org':
            items += studio._inbox_tasks('org', search, wide=self._can_org())
        else:
            items += studio._inbox_tasks('me', search)
        return items

    @api.model
    def _extra_counts(self, scope='me'):
        counts = dict(super()._extra_counts(scope) or {})
        mine = self._studio()._inbox_tasks('me')
        counts['mine'] = int(counts.get('mine') or 0) + len(mine)
        counts['late'] = int(counts.get('late') or 0) + sum(1 for c in mine if c['late'])
        return counts
