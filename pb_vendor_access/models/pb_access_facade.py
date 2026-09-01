# -*- coding: utf-8 -*-
"""`pb.access` — the Access & delegation panel's facade.

TWO TABS, TWO QUESTIONS.

  **Roles** — who holds what. A profile, the sentence saying what it lets
  somebody do, and the people who hold it. Granting and removing happen here,
  through a dialog that shows the sentence before the button.

  **Hand-overs** — who is covering for whom, until when, and what they were
  given. Anybody internal can lend what they hold; the access team can lend on
  somebody else's behalf and can take any of it back.

WHAT THIS FACADE REFUSES, AND WHY IT REFUSES IT HERE.
The catalogue cannot contain the administrator permission and the model will not
let it (`pb.role.profile._check_group_is_not_the_keys_to_the_building`), so
these checks are the third of three. That is not belt-and-braces for its own
sake: a facade is the only layer that sees a request BEFORE it becomes a write,
and this is the one rule in the module whose failure cannot be undone by anybody
who is still allowed to log in.

R7 IS THE WHOLE ROLES BOARD. `res.users.group_ids` is direct membership only and
misses everybody who holds a group through a ladder — which, on the payroll
ladder, is most of the people who hold it. Every "who holds this" question here
goes through `res.groups.all_user_ids`, which is the transitive set.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .vendor_common import (DELEGATION_ROW_CAP, HOLDER_CAP, PICKER_CAP,
                            area_label, counted, flag, fold,
                            forbidden_group_ids, safe)

_logger = logging.getLogger(__name__)

#: Who may open the board at all. Everybody internal, because the "Delegate my
#: access" half is for everybody by requirement — what each person then SEES is
#: the record rules' business.
BOARD_GROUPS = ('base.group_user',)
#: Who may grant and remove on somebody else's behalf.
MANAGE_GROUPS = (
    'pb_vendor_access.group_access_manager',
    'pb_lifecycle.group_lifecycle_admin',
)


class PbAccess(models.AbstractModel):
    _name = 'pb.access'
    _description = 'Access & delegation board — facade'

    # ================================================================= access
    @api.model
    def _is_admin(self):
        return self.env.user.has_group('base.group_system')

    @api.model
    def _has(self, groups):
        for g in groups:
            try:
                if self.env.user.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _require(self):
        if self._is_admin() or self._has(BOARD_GROUPS):
            return
        raise AccessError(_(
            "This board is for people with a Payobook login. Portal accounts "
            "do not have one."))

    @api.model
    def _require_manage(self):
        if self._is_admin() or self._has(MANAGE_GROUPS):
            return
        raise AccessError(_(
            "Giving somebody a role, or taking one away, is something the "
            "access team does. You can still hand over your own access for a "
            "while — that is the other tab."))

    @api.model
    def can_manage(self):
        return bool(self._is_admin() or self._has(MANAGE_GROUPS))

    # ================================================================ the board
    @api.model
    def get_board(self, area=None, search=None):
        self._require()
        manage = self.can_manage()
        profiles = self._profiles(area, search)
        return {
            'can_manage': manage,
            'me': {'id': self.env.uid, 'name': self.env.user.name or ''},
            'profiles': profiles,
            'areas': self._areas(profiles),
            'mine': self._mine(),
            'delegations': self._delegations(),
            'kpis': self._kpis(profiles),
            'headline': self._headline(profiles),
        }

    def _profiles(self, area=None, search=None):
        """The catalogue, with its holders.

        NO SUDO ON THE PROFILE SEARCH. `visible_group_id` is enforced by a
        record rule, so a growth-plan profile is simply not in the list for
        somebody who is not a head of HR — and this method does not have to
        know that rule exists.
        """
        domain = [('active', '=', True)]
        if area:
            domain.append(('area', '=', area))
        needle = fold(search)
        out = []
        for profile in self.env['pb.role.profile'].search(
                domain, order='area, sequence, name'):
            if needle and needle not in fold(
                    '%s %s' % (profile.name or '', profile.description or '')):
                continue
            holders = profile.holders(cap=HOLDER_CAP)
            total = profile.holder_count
            out.append({
                'id': profile.id,
                'name': profile.name or '',
                'description': profile.description or '',
                'area': profile.area or '',
                'area_label': area_label(profile.area, self.env),
                'group': profile.group_id.display_name or '',
                'holders': [{'id': u.id, 'name': u.name or '',
                             'login': u.login or '',
                             'avatar': '/web/image/res.users/%s/avatar_128'
                                       % u.id}
                            for u in holders],
                'holder_count': total,
                'more': max(0, total - len(holders)),
                'i_hold': profile.group_id.id in set(
                    self.env.user.all_group_ids.ids),
                'restricted': bool(profile.visible_group_id),
            })
        return out

    def _areas(self, profiles):
        counts = {}
        for p in profiles:
            counts[p['area']] = counts.get(p['area'], 0) + 1
        return sorted(
            [{'key': k, 'label': area_label(k, self.env), 'n': n}
             for k, n in counts.items()],
            key=lambda x: -x['n'])

    def _mine(self):
        """What I hold, so the hand-over dialog can be honest about what I have
        to lend before I open it."""
        held = set(self.env.user.all_group_ids.ids)
        return [{'id': p.id, 'name': p.name or '',
                 'description': p.description or '',
                 'area_label': area_label(p.area, self.env)}
                for p in self.env['pb.role.profile'].search(
                    [('active', '=', True)], order='area, sequence, name')
                if p.group_id.id in held]

    def _delegations(self, limit=DELEGATION_ROW_CAP):
        """Hand-overs only — the roles board's grants are audit rows in the
        same table and belong in the audit export, not on this tab.

        The record rule already limits an ordinary person to their own; the
        access team sees everybody's.
        """
        rows = self.env['pb.access.delegation'].search(
            [('origin', '=', 'delegation')], limit=limit or None,
            order='date_start desc, id desc')
        return [self._delegation_row(d) for d in rows]

    def _delegation_row(self, d):
        s = d.sudo()                            # names only (R56)
        return {
            'id': d.id,
            'from': s.delegator_user_id.name or '',
            'from_id': s.delegator_user_id.id or 0,
            'to': s.delegate_user_id.name or '',
            'to_id': s.delegate_user_id.id or 0,
            'profiles': s.profile_ids.mapped('name'),
            'kind': s.kind or '',
            'kind_label': (_("For a while") if s.kind == 'temporary'
                           else _("For good")),
            'date_start': fields.Date.to_string(s.date_start) or '',
            'date_end': fields.Date.to_string(s.date_end) or '',
            'state': s.state or '',
            'state_label': self._state_label(s.state),
            'reason': s.reason or '',
            'applied': len(s.applied_group_ids),
            'ended_note': s.ended_note or '',
            'mine': s.delegator_user_id.id == self.env.uid,
            'to_me': s.delegate_user_id.id == self.env.uid,
            'days_left': ((s.date_end - fields.Date.context_today(self)).days
                          if s.date_end and s.state == 'active' else 0),
        }

    def _state_label(self, state):
        return {
            'draft': _("Not started"),
            'active': _("Running"),
            'expired': _("Ended"),
            'revoked': _("Taken back"),
        }.get(state, state or '')

    def _kpis(self, profiles):
        """Counted over the list the screen shows (R80)."""
        active = safe(
            lambda: self.env['pb.access.delegation'].search_count(
                [('state', '=', 'active'), ('origin', '=', 'delegation')]),
            0, 'the running hand-over count')
        return {
            'profiles': len(profiles),
            'people': len({h['id'] for p in profiles for h in p['holders']}),
            'active': active,
            'mine': len([p for p in profiles if p['i_hold']]),
        }

    def _headline(self, profiles):
        if not profiles:
            return _("No roles have been written down yet.")
        return _("%(p)s described in plain English, and %(m)s of them.",
                 p=counted(len(profiles), _("1 role"), _("%s roles")),
                 m=counted(len([p for p in profiles if p['i_hold']]),
                           _("you hold 1"), _("you hold %s")))

    # ================================================== granting and removing
    @api.model
    def grant(self, profile_id, user_id, reason=None):
        """Put somebody into a profile's group, and write down that it happened.

        The audit row is a `pb.access.delegation` with `origin='board'`, so the
        question "how did this person come to hold that" has ONE place to look
        rather than two.
        """
        self._require_manage()
        profile = self._safe_profile(profile_id)
        user = self._internal_user(user_id)
        if profile.group_id.id in set(user.sudo().all_group_ids.ids):
            raise UserError(_(
                "%(who)s already has \"%(what)s\".",
                who=user.sudo().name or '', what=profile.name))

        target = user.sudo()
        before = set(target.group_ids.ids)
        target.write({'group_ids': [(4, profile.group_id.id)]})
        target.invalidate_recordset(['group_ids'])
        added = sorted(set(target.group_ids.ids) - before)

        self.env['pb.access.delegation'].sudo().create({
            'delegator_user_id': self.env.uid,
            'delegate_user_id': user.id,
            'profile_ids': [(6, 0, [profile.id])],
            'kind': 'permanent',
            'date_start': fields.Date.context_today(self),
            'reason': (reason or '').strip() or _("Given on the roles board."),
            'state': 'active',
            'origin': 'board',
            'applied_group_ids': [(6, 0, added)],
            'applied_on': fields.Datetime.now(),
        })
        return {'ok': True, 'message': _(
            "%(who)s now has \"%(what)s\".",
            who=target.name or '', what=profile.name)}

    @api.model
    def remove(self, profile_id, user_id, reason=None):
        """Take a profile away, and write down that too.

        It removes the profile's OWN group and nothing else. Somebody who holds
        it through a ladder — a payroll manager who implies the officer tier —
        keeps holding it, and the message says so rather than pretending the
        removal worked.
        """
        self._require_manage()
        profile = self._safe_profile(profile_id)
        user = self._internal_user(user_id)
        target = user.sudo()
        if profile.group_id.id not in set(target.group_ids.ids):
            if profile.group_id.id in set(target.all_group_ids.ids):
                raise UserError(_(
                    "%(who)s has \"%(what)s\" because of another role they "
                    "hold, not directly. Take that other role away instead — "
                    "removing this one here would change nothing.",
                    who=target.name or '', what=profile.name))
            raise UserError(_(
                "%(who)s does not have \"%(what)s\".",
                who=target.name or '', what=profile.name))

        target.write({'group_ids': [(3, profile.group_id.id)]})
        self.env['pb.access.delegation'].sudo().create({
            'delegator_user_id': self.env.uid,
            'delegate_user_id': user.id,
            'profile_ids': [(6, 0, [profile.id])],
            'kind': 'permanent',
            'date_start': fields.Date.context_today(self),
            'reason': (reason or '').strip() or _("Taken away on the roles "
                                                  "board."),
            'state': 'revoked',
            'origin': 'board_removal',
            'applied_group_ids': [(6, 0, [profile.group_id.id])],
            'applied_on': fields.Datetime.now(),
            'ended_on': fields.Datetime.now(),
            'ended_note': _("Taken away by %s.", self.env.user.name or ''),
        })
        return {'ok': True, 'message': _(
            "%(who)s no longer has \"%(what)s\".",
            who=target.name or '', what=profile.name)}

    def _safe_profile(self, profile_id):
        """The third refusal (see the module docstring)."""
        profile = self.env['pb.role.profile'].browse(int(profile_id or 0))
        if not profile.exists():
            raise UserError(_("That role is not on this system any more."))
        profile.check_access('read')
        if not profile.group_id:
            raise UserError(_(
                "\"%s\" does not point at a permission, so there is nothing to "
                "hand out.", profile.name or ''))
        if profile.group_id.id in forbidden_group_ids(self.env):
            raise UserError(_(
                "\"%s\" is the administrator permission for the whole system. "
                "It is never given out from this screen — an administrator "
                "changes it on the user record itself, deliberately.",
                profile.name or ''))
        return profile

    def _internal_user(self, user_id):
        user = self.env['res.users'].browse(int(user_id or 0))
        if not user.exists():
            raise UserError(_("That person does not have a login here."))
        if user.sudo().share:
            raise UserError(_(
                "%s has an employee login only. Roles are for people who work "
                "inside Payobook.", user.sudo().name or ''))
        return user

    # ================================================================ hand-over
    @api.model
    def delegate(self, vals):
        """Create AND activate in one action.

        A hand-over that sits in draft is a hand-over that did not happen, and
        a two-step wizard for a two-week absence is a step nobody takes. The
        refusals all live in `_groups_to_hand`, so the record is created and
        then activated — and a failed activation leaves a draft somebody can
        see and fix rather than nothing at all.
        """
        self._require()
        vals = dict(vals or {})
        delegator_id = int(vals.get('delegator_user_id') or self.env.uid)
        delegator = self.env['res.users'].browse(delegator_id)
        self.env['pb.access.delegation']._assert_can_delegate(delegator)

        delegate_user = self._internal_user(vals.get('delegate_user_id'))
        profile_ids = [int(p) for p in (vals.get('profile_ids') or []) if p]
        if not profile_ids:
            raise UserError(_("Choose at least one thing to hand over."))
        for pid in profile_ids:
            self._safe_profile(pid)

        kind = vals.get('kind') or 'temporary'
        date_start = vals.get('date_start') or fields.Date.context_today(self)
        date_end = vals.get('date_end') or False
        if kind == 'temporary' and not date_end:
            raise UserError(_(
                "Say which day it ends. That is what takes the access back "
                "without anybody having to remember."))

        rec = self.env['pb.access.delegation'].sudo().create({
            'delegator_user_id': delegator_id,
            'delegate_user_id': delegate_user.id,
            'profile_ids': [(6, 0, profile_ids)],
            'kind': kind,
            'date_start': date_start,
            'date_end': date_end if kind == 'temporary' else False,
            'reason': (vals.get('reason') or '').strip(),
            'origin': 'delegation',
        })
        rec.action_activate()
        return {'ok': True, 'id': rec.id, 'message': _(
            "%(who)s can now do it on your behalf%(until)s.",
            who=delegate_user.sudo().name or '',
            until=(_(" until %s", date_end) if date_end else ''))}

    @api.model
    def revoke(self, delegation_id, reason=None):
        """Anybody can take back what they lent; the access team can take back
        anything."""
        self._require()
        rec = self.env['pb.access.delegation'].browse(int(delegation_id or 0))
        if not rec.exists():
            raise UserError(_("That hand-over is not on this system."))
        rec.check_access('read')
        if rec.sudo().delegator_user_id.id != self.env.uid and not self.can_manage():
            raise AccessError(_(
                "You can take back what you lent. Taking back somebody else's "
                "hand-over is something the access team does."))
        rec.sudo().action_revoke(
            (reason or '').strip()
            or _("Taken back by %s.", self.env.user.name or ''))
        return {'ok': True, 'message': _("The access has been taken back.")}

    @api.model
    def run_auto_revert(self):
        """"Run the end-of-day check now" — and it does EXACTLY what the night
        does (R53)."""
        self._require_manage()
        res = self.env['pb.access.delegation'].run_auto_revert(limit=None)
        return {'ok': True, 'message': res['message'], 'counters': res}

    # =============================================================== the picker
    @api.model
    def user_options(self, term=None):
        """Folded in Python over `search_read` of two columns (R78/R56)."""
        needle = fold(term)
        rows = self.env['res.users'].sudo().search_read(
            [('active', '=', True), ('share', '=', False)],
            ['name', 'login'], limit=600, order='name')
        out = [{'id': r['id'], 'name': r['name'] or '',
                'login': r['login'] or '',
                'avatar': '/web/image/res.users/%s/avatar_128' % r['id']}
               for r in rows
               if r['id'] != self.env.uid
               and (not needle or needle in fold(r['name'])
                    or needle in fold(r['login']))]
        return out[:PICKER_CAP]

    # ================================================================ exports
    @api.model
    def export_roles(self):
        self._require()
        return self.env['pb.vendor.export'].build_roles()

    @api.model
    def export_delegations(self):
        self._require()
        return self.env['pb.vendor.export'].build_delegations()
