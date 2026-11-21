# -*- coding: utf-8 -*-
"""UPDATES P3a — two OPT-IN seams on the approval engine.

The engine never learns what a bank account is. It learns two questions it
may ask a record — and asks them ONLY when the record's model defines them:

  * `_approval_step_people(step, people, issue, ctx, company)` — after the
    engine has worked out who decides a step, the record may narrow or
    replace that list (`pb.records.apply`: a bank change is never decided by
    the person who proposed it, and a second person is found when the route
    names nobody else);
  * `_approval_may_decide(request, user)` — before an APPROVE is recorded,
    the record may refuse it with a sentence (`pb.records.apply`: the
    proposer of a bank change, whatever seat they hold — a reassignment or a
    hand-over included).

A model that defines neither is untouched: `getattr(..., None)` is None and
the engine's own answer goes out as it always did (test F12). Nothing here
changes `submit`, `cancel`, the independence rule or any other process.

Lives in `pb_records` rather than in `biz_approval_workflow` so that turning
it on is not an upgrade of the approval engine and of every module that
depends on it (the P2c / P2d precedent: extend from the module that needs it).
"""

from odoo import api, models
from odoo.exceptions import UserError


class BizApprovalEngineOptInHooks(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    def _resolve_step_people(self, step, ctx, company, on_date, record=None):
        people, issue = super()._resolve_step_people(
            step, ctx, company, on_date, record=record)
        hook = getattr(record, '_approval_step_people', None) \
            if record is not None else None
        if hook is not None and len(record) == 1:
            people, issue = hook(step, people, issue, ctx, company)
        return people, issue

    @api.model
    def decide(self, request, step_key, action, reason=None, *args, **kwargs):
        if action == 'approve':
            req = self._as_request(request)
            record = req._record() if req.res_model and req.res_id else None
            hook = getattr(record, '_approval_may_decide', None) \
                if record is not None else None
            if hook is not None and record.exists():
                sentence = hook(req, self.env.user)
                if sentence:
                    raise UserError(sentence)
        return super().decide(request, step_key, action, reason,
                              *args, **kwargs)
