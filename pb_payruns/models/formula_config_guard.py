# -*- coding: utf-8 -*-
"""Describe whether pay runs on a scheme can currently be approved.

The Connect step asks this early so it can warn clearly and point to the exact
flow. It deliberately does not gate scheme activation: activation is governed
by the separate ``scheme`` process, while this ``payrun`` process is enforced
when somebody submits a pay run. Keeping those doors separate means choosing
"No approval needed" for Scheme change really does allow the scheme to go live.

WHY IT LIVES IN `pb_payruns`. `hr.formula.config` belongs to the formula
engine, which knows nothing about approvals and must not learn; the approval
engine knows nothing about pay schemes and must not learn either. This module
already depends on both, which is exactly what makes it the right place for a
sentence that involves the two of them.
"""

from odoo import _, models


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
            why = blocking[0].get('msg') or _(
                "The approval route for this scheme is not ready.")
            flow = answer.get('workflow_name') or version.workflow_id.name
            return _(
                "In Approval Matrix, the flow is “%(flow)s”. %(why)s",
                flow=flow, why=why)
        return ''
