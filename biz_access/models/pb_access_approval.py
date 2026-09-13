# -*- coding: utf-8 -*-
"""The three doors on the roles board, and the question they now ask first.

`grant`, `remove` and `delegate` are unchanged: the same checks, the same
writes, the same audit row. What is new sits in FRONT of them — where a company
has published a route for role changes, the press writes a request and the
board says who is holding it. When the route says yes, the very same three
methods run, called by the last approver, through this same file.

The re-entry flag is how a route carries out a change without asking about it
again. It is a context key set on the server, by the engine's own apply step;
a browser can put any key on a context and could only ever use this one to
send itself through a door it had already passed.
"""

import json
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .pb_access_request import ENGINE_APPLY, ROLES_PROCESS_KEY

_logger = logging.getLogger(__name__)


class PbAccessApproval(models.AbstractModel):
    _inherit = 'pb.access'

    # ------------------------------------------------------------ managed?
    @api.model
    def _roles_route_live(self):
        """Has this company asked for role changes to be approved?"""
        if 'biz.approval.binding' not in self.env:
            return False
        process = self.env['biz.approval.process']._by_key(ROLES_PROCESS_KEY)
        if not process:
            return False
        company = self.env.company
        return bool(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id), ('active', '=', True)]))

    @api.model
    def _ask_instead(self, kind, vals, instruction):
        """Make the request and send it in. Returns the board's own answer.

        `sudo()` on the create only: the gate the board already applied
        (`_require_manage`) is what decided this person may ask, and the
        request row is the record of their asking. The SUBMIT runs as them, so
        every seat, decision and refusal carries their name.
        """
        record = self.env['pb.access.request'].sudo().create(dict(
            vals, kind=kind, payload=json.dumps(instruction, sort_keys=True,
                                                default=str),
            requested_by=self.env.uid, company_id=self.env.company.id))
        self.env['biz.approval.engine'].submit(record)
        request = record.approval_request_id
        step = request.step_ids.filtered(
            lambda s: s.status == 'active')[:1] if request else None
        waiting = ', '.join(sorted({
            seat.acting_user_id.name or ''
            for seat in step.seat_ids if seat.status == 'open'})) if step \
            else ''
        if record.state == 'applied':
            # a published "No approval needed" route: it happened, and it is
            # still written down as a request
            return {'ok': True, 'message': _("Done, and recorded.")}
        return {
            'ok': True,
            'pending': True,
            'request_id': request.id if request else 0,
            'access_request_id': record.id,
            'message': (_("Sent for approval — %s", waiting) if waiting
                        else _("Sent for approval.")),
        }

    # ================================================================ doors
    @api.model
    def grant(self, profile_id, user_id, reason=None):
        if self.env.context.get(ENGINE_APPLY) or not self._roles_route_live():
            return super().grant(profile_id, user_id, reason)
        self._require_manage()
        profile = self._safe_profile(profile_id)
        user = self._internal_user(user_id)
        # The one check worth making BEFORE a request exists: asking two people
        # to agree to a change that would do nothing is worse than the plain
        # refusal this has always given.
        if set(profile.group_ids.ids) <= set(user.sudo().all_group_ids.ids):
            raise UserError(_(
                "%(who)s already has \"%(what)s\".",
                who=user.sudo().name or '', what=profile.name))
        return self._ask_instead(
            'grant',
            {'profile_ids': [(6, 0, [profile.id])],
             'target_user_id': user.id, 'reason': (reason or '').strip()},
            {'profile_id': profile.id, 'user_id': user.id,
             'reason': (reason or '').strip()})

    @api.model
    def remove(self, profile_id, user_id, reason=None):
        if self.env.context.get(ENGINE_APPLY) or not self._roles_route_live():
            return super().remove(profile_id, user_id, reason)
        self._require_manage()
        profile = self._safe_profile(profile_id)
        user = self._internal_user(user_id)
        return self._ask_instead(
            'remove',
            {'profile_ids': [(6, 0, [profile.id])],
             'target_user_id': user.id, 'reason': (reason or '').strip()},
            {'profile_id': profile.id, 'user_id': user.id,
             'reason': (reason or '').strip()})

    @api.model
    def delegate(self, vals):
        if self.env.context.get(ENGINE_APPLY) or not self._roles_route_live():
            return super().delegate(vals)
        self._require()
        vals = dict(vals or {})
        delegate_user = self._internal_user(vals.get('delegate_user_id'))
        profile_ids = [int(p) for p in (vals.get('profile_ids') or []) if p]
        if not profile_ids:
            raise UserError(_("Choose at least one thing to hand over."))
        for pid in profile_ids:
            self._safe_profile(pid)
        return self._ask_instead(
            'delegate',
            {'profile_ids': [(6, 0, profile_ids)],
             'target_user_id': int(vals.get('delegator_user_id')
                                   or self.env.uid),
             'delegate_user_id': delegate_user.id,
             'date_start': vals.get('date_start') or False,
             'date_end': vals.get('date_end') or False,
             'reason': (vals.get('reason') or '').strip()},
            {'vals': vals})
