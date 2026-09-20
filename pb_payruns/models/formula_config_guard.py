# -*- coding: utf-8 -*-
"""A pay scheme cannot go live with nobody to approve its pay runs.

The moment a scheme is activated, somebody can run payroll on it — and the
first thing that happens after they do is that the run asks for its approval.
If the route for that scheme has no binding, or names a responsibility nobody
holds, the run is refused the instant it is submitted, at the worst possible
moment: the numbers are computed, the month is late, and the person holding the
error can do nothing about it themselves.

So the question is asked EARLIER, where it is still cheap: at activation, with
the gap named and the screen that mends it one press away. This is a read only
— it grants nothing and changes nothing about the route.

WHY IT LIVES IN `pb_payruns`. `hr.formula.config` belongs to the formula
engine, which knows nothing about approvals and must not learn; the approval
engine knows nothing about pay schemes and must not learn either. This module
already depends on both, which is exactly what makes it the right place for a
sentence that involves the two of them.
"""

import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    def _pb_approval_gap(self):
        """Why a pay run on this scheme could not be approved today, or ''."""
        self.ensure_one()
        company = self.company_id or self.env.company
        engine = self.env['biz.approval.engine']
        process = self.env['biz.approval.process']._by_key('payrun')
        if not process:
            # Approvals are not set up on this database at all. That is not a
            # gap in THIS scheme, and refusing here would be a door nobody
            # could open.
            return ''
        scope_keys = ['scheme:%s' % self.id, '']
        kind = self.cycle_type or 'any'
        # sudo: this is a GUARD reading the route, not a grant. The person
        # activating a scheme is not necessarily allowed to read the whole
        # approval set-up, and refusing to activate because they cannot look
        # would be the wrong answer to the wrong question (audit-console
        # pattern).
        answer = engine.sudo().resolve_binding(
            company.id, 'payrun', scope_keys, kind)
        if answer.get('error'):
            return answer['error']['message']
        version = self.env['biz.approval.workflow.version'].sudo().browse(
            answer['version_id'])
        result = engine.sudo().preview(version.id, {
            'company_id': company.id,
            'scope_keys': scope_keys,
            'scope_label': self.name or company.name,
            'kind_key': kind,
            'process_key': 'payrun',
            'facts': {},
        })
        blocking = [i for i in (result.get('issues') or [])
                    if i.get('level') == 'block']
        if blocking:
            return blocking[0].get('msg') or _(
                "The approval route for this scheme is not ready.")
        return ''

    def action_activate(self):
        """Activate — once a pay run on this scheme could actually be signed off."""
        for config in self:
            gap = ''
            try:
                gap = config._pb_approval_gap()
            except Exception:   # noqa: BLE001 — never block on a broken read
                _logger.exception(
                    'pb_payruns: the approval check failed on scheme %s',
                    config.id)
            if gap:
                raise UserError(_(
                    "“%(name)s” cannot go live yet: %(why)s\n\nPay runs on this "
                    "scheme would be refused the moment they were sent in. Set "
                    "the approvals for it first — Approvals → Matrix, or the "
                    "Approvals panel on the scheme's own settings.",
                    name=config.name or '', why=gap))
        return super().action_activate()
