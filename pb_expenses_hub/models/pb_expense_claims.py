# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.expense.claims` — Expenses › Claims on the shared filter panel.

FILTER wave 7 (2026-10-31). The Claims tab used to mount the native list of
`pb.expense.claim` with its search view (Waiting approval / Approved /
Refused / Paid, grouped by status or employee). It is now a small Payobook
list on the shared filter panel: counts beside every value, views, search,
sorts, pages of 60. A row still opens the native claim form, in the main
breadcrumb, and decisions are still taken from Approvals — nothing here
approves anything.

Who sees what is unchanged: the tab is offered to expense team approvers
(`CLAIMS_GATE` in `expenses_hub.js`), the rows are read as the reader (the
claim's record rules: company, own claims, a seat on the route, the team
approver's teams, everyone for expense officers and accountants), and the
panel refuses anybody the tab would not be offered to.
"""

from odoo import _, api, models
from odoo.tools.misc import format_date, format_datetime, formatLang

#: The tab's gate (the same group `CLAIMS_GATE` names in the browser).
CLAIMS_GROUP = 'hr_expense.group_hr_expense_team_approver'

#: Rows per page.
PAGE_SIZE = 60

#: Status words and tones, in the claim's own order.
STATUS = [
    ('draft', 'Draft', 'slate'),
    ('submitted', 'Waiting approval', 'amber'),
    ('approved', 'Approved', 'blue'),
    ('refused', 'Refused', 'rose'),
    ('paid', 'Paid', 'green'),
]


class PbExpenseClaims(models.AbstractModel):
    _name = 'pb.expense.claims'
    _inherit = ['pb.filter.mixin']
    _description = 'Expense claims list (filter panel)'

    # ------------------------------------------------------------- the gate
    @api.model
    def _can_read(self):
        user = self.env.user
        if user._is_admin():
            return True
        try:
            return user.has_group(CLAIMS_GROUP)
        except (ValueError, KeyError):
            return False

    @api.model
    def _refusal(self):
        return _("Expense claims are for the people who approve expenses. "
                 "Ask your administrator if you should see them.")

    # ------------------------------------------------------------ the panel
    @api.model
    def _co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    def _pbf_model(self):
        return 'pb.expense.claim'

    def _pbf_screen(self):
        return 'claims'

    def _pbf_base_domain(self):
        return [('company_id', 'in', self._co_ids())]

    def _pbf_search_fields(self):
        return ['name', 'employee_id.name', 'note', 'employee_id.department_id.name']

    def _pbf_sorts(self):
        return [
            {'key': 'sent_new', 'label': _('Newest sent first'),
             'order': 'submitted_on desc nulls last, id desc'},
            {'key': 'sent_old', 'label': _('Waiting longest first'),
             'order': 'submitted_on asc nulls last, id asc'},
            {'key': 'total', 'label': _('Biggest total first'),
             'order': 'total desc, id desc'},
            {'key': 'newest', 'label': _('Newest claim first'),
             'order': 'id desc'},
        ]

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    @api.model
    def _status_words(self):
        return {
            'draft': _('Draft'),
            'submitted': _('Waiting approval'),
            'approved': _('Approved'),
            'refused': _('Refused'),
            'paid': _('Paid'),
        }

    def _pbf_spec(self):
        words = self._status_words()
        return [
            # ---- pinned: where it is, whose, how much
            {'key': 'status', 'label': _('Status'), 'icon': 'listChecks',
             'group': 'other', 'type': 'choice', 'pinned': True,
             'options': [{'value': k, 'label': words[k], 'tone': tone,
                          'domain': [('state', '=', k)]} for k, _w, tone in STATUS]},
            {'key': 'employee', 'label': _('Who sent it'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id',
             'pinned': True, 'label_sudo': True},
            {'key': 'total', 'label': _('Total'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'total', 'unit': 'money',
             'pinned': True},
            # ---- more filters
            {'key': 'department', 'label': _('Their department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'label_sudo': True, 'none_label': _('No department')},
            {'key': 'sent', 'label': _('Sent on'), 'icon': 'send',
             'group': 'dates', 'type': 'date', 'path': 'submitted_on', 'presets': 'past',
             'none_label': _('Not sent yet')},
            {'key': 'decided', 'label': _('Decided on'), 'icon': 'checkCircle',
             'group': 'dates', 'type': 'date', 'path': 'decided_on', 'presets': 'past',
             'none_label': _('Not decided yet')},
            {'key': 'paid', 'label': _('Paid on'), 'icon': 'wallet',
             'group': 'dates', 'type': 'date', 'path': 'paid_on', 'presets': 'past',
             'none_label': _('Not paid yet')},
            {'key': 'receipts', 'label': _('Number of receipts'), 'icon': 'receipt',
             'group': 'other', 'type': 'number', 'path': 'receipt_count'},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'waiting', 'label': _('Waiting approval'), 'icon': 'inbox',
             'filters': {'status': ['submitted']}},
            {'key': 'approved', 'label': _('Approved, not yet paid'), 'icon': 'checkCircle',
             'filters': {'status': ['approved']}},
            {'key': 'paid_month', 'label': _('Paid this month'), 'icon': 'wallet',
             'filters': {'status': ['paid'], 'paid': {'preset': 'this_month'}}},
            {'key': 'refused', 'label': _('Refused'), 'icon': 'xCircle',
             'filters': {'status': ['refused']}},
            {'key': 'sent_month', 'label': _('Sent this month'), 'icon': 'send',
             'filters': {'sent': {'preset': 'this_month'}}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': self._refusal()}
        return super().pbf_layout()

    # ------------------------------------------------------------- the rows
    @api.model
    def _row(self, c, words):
        env = self.env
        emp = c.employee_id
        return {
            'id': c.id,
            'name': c.name or '',
            'employee': emp.name or '',
            'employee_id': emp.id,
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id if emp else '',
            'department': emp.sudo().department_id.name or '' if emp else '',
            'sent': format_datetime(env, c.submitted_on, dt_format='d MMM yyyy') if c.submitted_on else '',
            'decided': format_datetime(env, c.decided_on, dt_format='d MMM yyyy') if c.decided_on else '',
            'paid': format_date(env, c.paid_on) if c.paid_on else '',
            'receipts': c.receipt_count or 0,
            'total': formatLang(env, c.total or 0.0, currency_obj=c.currency_id),
            'state': c.state,
            'state_label': words.get(c.state, c.state),
        }

    @api.model
    def get_claim_page(self, filters=None, search=None, sort=None, offset=0,
                       limit=PAGE_SIZE):
        """One page of claims for the panel's state, read as the reader."""
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'refused': self._refusal()}
        Claim = self.env['pb.expense.claim']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        claims = Claim.search(domain, order=self.pbf_order(sort) or 'id desc',
                              offset=offset, limit=limit)
        words = self._status_words()
        return {
            'rows': [self._row(c, words) for c in claims],
            'total': Claim.search_count(domain),
            'offset': offset,
        }
