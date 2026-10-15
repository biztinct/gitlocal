# -*- coding: utf-8 -*-
"""EMPLOYEE OR STAFF — the account type, switched from the People lens.

TIERS T2. Two kinds of login exist in the product:

  * an **Employee** login — a portal (share) account, `base.group_portal` and
    nothing else. It lands on the employee self-service pages, cannot load
    the backend at all
    (stock: share users are bounced out of the web client), holds no backend
    permission and cannot hold a role (`pb.role.assignment._check_safe`);
  * a **Staff** login — a full (internal) account, `base.group_user`, which
    then carries roles from this board.

`set_account_type` moves a person between the two in one press.

DEMOTION IS REFUSED, NEVER FORCED (ledger T-R12, handover D4), while the
person still runs people or decisions: a direct report, an approval seat
waiting on them, administrator rights, the platform recovery login, yourself —
and active roles while the company routes role changes through approvals
(`_roles_route_live`), so a role removal is never smuggled past that route.
Otherwise their roles end through the board's own removal path (the
assignment goes inactive under the private sentinel, access is reconciled,
and a `board_removal` audit row is written per role, exactly as `remove()`
does), running hand-overs to them are taken back through `revoke`, and one
`account_switch` audit row records the type change itself.

Everything is decided BEFORE anything is written, in one transaction. Never
touched: passwords, `login`, `active`, `company_ids`.
"""

import logging

from odoo import _, Command, api, fields, models
from odoo.exceptions import UserError

from .access_common import may_see_recovery, recovery_login
from .role_assignments import INTERNAL

_logger = logging.getLogger(__name__)

KINDS = ('employee', 'staff')


class PbAccessAccountType(models.AbstractModel):
    _inherit = 'pb.access'

    # ------------------------------------------------------------ the facts
    def _switch_counts(self, user):
        """{reports, open_seats, roles} for one login — what holds them on a
        full account. Soft reads: approvals are not a dependency of this
        module."""
        user = user.sudo()
        reports = 0
        if 'hr.employee' in self.env:
            reports = self.env['hr.employee'].sudo().search_count(
                [('parent_id.user_id', '=', user.id)])
        seats = 0
        if 'biz.approval.request.seat' in self.env:
            seats = self.env['biz.approval.request.seat'].sudo().search_count(
                ['|', ('acting_user_id', '=', user.id),
                 ('user_id', '=', user.id), ('status', '=', 'open')])
        roles = len(self._switch_sources(user).profile_id)
        return {'reports': reports, 'open_seats': seats, 'roles': roles}

    def _switch_sources(self, user):
        """Every active role source on the person: their own roles and the
        hand-overs running to them."""
        return self.env['pb.role.assignment'].sudo().search(
            [('user_id', '=', user.id), ('active', '=', True)])

    def _switch_refusal(self, user, kind, counts=None):
        """The plain-words reason this switch cannot happen, or ''.

        The ONE list of refusals: the preview shows it under the switch, and
        `set_account_type` raises it — they can never disagree."""
        user = user.sudo()
        name = user.name or ''
        if user.id == self.env.uid:
            return _("You cannot change your own account.")
        if user._is_public():
            return _("That is not a person's login.")
        if (user.login or '').strip().lower() == recovery_login(self.env):
            return _("That person does not have a login here.")
        if (user._is_admin() or user._is_system()
                or user.has_group('base.group_system')):
            return _("%s is an administrator, so their account stays a full "
                     "one.", name)
        if not self._employee_user_ids(user):
            if kind == 'employee':
                return _("%s is not linked to an employee record, so an "
                         "employee login would show them nothing. Link them "
                         "to their employee record first.", name)
            return _("%s is not linked to an employee record, so this screen "
                     "cannot give them a full login.", name)
        if kind == 'employee':
            counts = counts or self._switch_counts(user)
            if counts['reports'] == 1:
                return _("1 person reports to %s. Move them to another "
                         "manager first.", name)
            if counts['reports']:
                return _("%(n)s people report to %(name)s. Move them to "
                         "another manager first.",
                         n=counts['reports'], name=name)
            if counts['open_seats'] == 1:
                return _("1 decision is waiting with %s.", name)
            if counts['open_seats']:
                return _("%(n)s decisions are waiting with %(name)s.",
                         n=counts['open_seats'], name=name)
            if counts['roles'] and self._roles_route_live():
                return _("Remove their roles first.")
        return ''

    def _account_switch_preview(self, user):
        """What the Employee / Staff switch on the passport offers."""
        user = user.sudo()
        to = 'staff' if user.share else 'employee'
        counts = self._switch_counts(user) if not user.share else \
            {'reports': 0, 'open_seats': 0, 'roles': 0}
        why = self._switch_refusal(user, to, counts)
        return {
            'to': to,
            'allowed': bool(self.can_manage() and not why),
            'why': why,
            'roles_ending': counts['roles'] if to == 'employee' else 0,
            'reports': counts['reports'],
            'open_seats': counts['open_seats'],
        }

    # ------------------------------------------------------------ the switch
    @api.model
    def set_account_type(self, user_id, kind, reason=None):
        """Make somebody an Employee (portal login) or Staff (full login)."""
        self._require_manage()
        if kind not in KINDS:
            raise UserError(_("Choose Employee or Staff."))
        user = self.env['res.users'].sudo().browse(int(user_id or 0)).exists()
        if not user or (not may_see_recovery(self.env) and
                        (user.login or '').strip().lower() ==
                        recovery_login(self.env)):
            raise UserError(_("That person does not have a login here."))
        self.env.cr.execute(
            'SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
        user.invalidate_recordset()
        before = 'employee' if user.share else 'staff'
        if kind == before and not user._is_public():
            return {'ok': True, 'kind': kind, 'message': (
                _("%s already has an employee login.", user.name)
                if kind == 'employee' else
                _("%s already has a full login.", user.name))}
        why = self._switch_refusal(user, kind)
        if why:
            raise UserError(why)
        reason = (reason or '').strip()

        ended = self.env['pb.role.profile']
        if kind == 'employee':
            ended = self._end_roles_for_switch(user, reason)
            group = self.env.ref('base.group_portal')
        else:
            group = self.env.ref('base.group_user')
        # ONE user type (`res.users._check_disjoint_groups`): the set replaces
        # every direct group. biz_access's own write keeps its bookkeeping
        # (baseline, sources) in step; the reconcile below is for a person the
        # role service had never initialised.
        user.write({'group_ids': [Command.set(group.ids)]})
        user._pb_reconcile_access()

        now = fields.Datetime.now()
        vals = {
            'delegator_user_id': self.env.uid, 'delegate_user_id': user.id,
            'profile_ids': [Command.set(ended.ids)], 'kind': 'permanent',
            'origin': 'account_switch',
            'reason': reason or (_("Changed to Employee on Access")
                                 if kind == 'employee' else
                                 _("Changed to Staff on Access")),
            'date_start': fields.Date.context_today(self),
        }
        if kind == 'employee':
            vals.update(state='revoked', ended_on=now,
                        ended_note=_("Employee login: self-service pages only."))
        else:
            vals.update(state='active', applied_on=now,
                        applied_group_ids=[Command.set(group.ids)])
        self.env['pb.access.delegation'].sudo().create(vals)
        _logger.info('biz_access: user %s changed the account type of user '
                     '%s from %s to %s (%s roles ended)', self.env.uid,
                     user.id, before, kind, len(ended))

        if kind == 'employee':
            if len(ended) == 1:
                message = _("%s now has an employee login and uses the "
                            "self-service pages only. 1 role ended.",
                            user.name)
            elif ended:
                message = _("%(name)s now has an employee login and uses the "
                            "self-service pages only. %(n)s roles ended.",
                            name=user.name, n=len(ended))
            else:
                message = _("%s now has an employee login and uses the "
                            "self-service pages only.", user.name)
        else:
            message = _("%s now has a full login. Give them a role next.",
                        user.name)
        return {'ok': True, 'kind': kind, 'message': message}

    def _end_roles_for_switch(self, user, reason):
        """End every role source on the person, the board's own way. Returns
        the roles that ended."""
        reason = reason or _("Changed to Employee on Access")
        sources = self._switch_sources(user)
        ended = sources.profile_id
        # 1. Their own roles — `remove()`'s path: inactive under the sentinel,
        #    reconcile, one removal row per role.
        owned = sources.filtered(lambda s: s.source == 'role')
        if owned:
            owned.with_context(_pb_access_internal=INTERNAL).write(
                {'active': False, 'reason': reason})
            user.sudo()._pb_reconcile_access()
            today = fields.Date.context_today(self)
            now = fields.Datetime.now()
            for role in owned.profile_id:
                self.env['pb.access.delegation'].sudo().create({
                    'delegator_user_id': self.env.uid,
                    'delegate_user_id': user.id,
                    'profile_ids': [Command.set(role.ids)],
                    'kind': 'permanent', 'state': 'revoked',
                    'origin': 'board_removal', 'reason': reason,
                    'date_start': today, 'ended_on': now,
                })
        # 2. Hand-overs running TO them — taken back through `revoke`, which
        #    writes the hand-over's own end and tells both people.
        loans = (sources - owned).delegation_id.filtered(
            lambda d: d.state == 'active')
        for loan in loans:
            self.revoke(loan.id, reason)
        # 3. Anything still marked active (a source whose hand-over already
        #    ended) is closed too: an employee login carries no role source.
        rest = self._switch_sources(user)
        if rest:
            rest.with_context(_pb_access_internal=INTERNAL).write(
                {'active': False, 'reason': reason})
            user.sudo()._pb_reconcile_access()
        return ended
