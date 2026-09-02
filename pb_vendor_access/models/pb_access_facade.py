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

from .vendor_common import (DELEGATION_ROW_CAP, HOLDER_CAP, PEOPLE_CAP,
                            PICKER_CAP, PROFILE_AREAS, area_label, counted,
                            flag, fold, forbidden_in_closure, implied_closure,
                            safe)

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
            # THE SHAPE OF THIS ROW DOES NOT CHANGE. `group` was one permission
            # name and is now the names of everything the bundle carries — one
            # of them, for every role on this database today, so the board reads
            # exactly as it did.
            bundle = profile.group_ids
            out.append({
                'id': profile.id,
                'name': profile.name or '',
                'description': profile.description or '',
                'area': profile.area or '',
                'area_label': area_label(profile.area, self.env),
                'group': ', '.join(
                    n for n in bundle.mapped('display_name') if n) or '',
                'holders': [{'id': u.id, 'name': u.name or '',
                             'login': u.login or '',
                             'avatar': '/web/image/res.users/%s/avatar_128'
                                       % u.id}
                            for u in holders],
                'holder_count': total,
                'more': max(0, total - len(holders)),
                'i_hold': bool(bundle) and set(bundle.ids) <= set(
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
                if p.group_ids and set(p.group_ids.ids) <= held]

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
            # The fifth number, and the one that turns a list of roles into a
            # picture of the product: how many doors there are to open at all.
            'entries': safe(lambda: len(self._rail_skeleton_items()), 0,
                            'the left-menu entry count'),
        }

    def _headline(self, profiles):
        if not profiles:
            return _("No roles have been written down yet.")
        return _(
            "%(p)s in plain English — who holds them, and what each one opens. "
            "%(m)s.",
            p=counted(len(profiles), _("1 role"), _("%s roles")),
            m=counted(len([p for p in profiles if p['i_hold']]),
                      _("You hold 1"), _("You hold %s")))

    # ================================================== granting and removing
    @api.model
    def grant(self, profile_id, user_id, reason=None):
        """Put somebody into a profile's group, and write down that it happened.

        The audit row is a `pb.access.delegation` with `origin='board'`, so the
        question "how did this person come to hold that" has ONE place to look
        rather than two.

        A ROLE IS A BUNDLE, SO GRANTING IT ADDS ONLY THE MISSING PART. Somebody
        who already reaches two of its three permissions gets the third, and the
        audit row records the one thing that actually changed rather than three
        things, two of which did not.
        """
        self._require_manage()
        profile = self._safe_profile(profile_id)
        user = self._internal_user(user_id)
        bundle = profile.group_ids
        held = set(user.sudo().all_group_ids.ids)
        if set(bundle.ids) <= held:
            raise UserError(_(
                "%(who)s already has \"%(what)s\".",
                who=user.sudo().name or '', what=profile.name))

        target = user.sudo()
        before = set(target.group_ids.ids)
        target.write({'group_ids': [(4, g.id) for g in bundle
                                    if g.id not in held]})
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
        """Take a role away, and write down that too.

        It removes the role's OWN permissions and nothing else. Somebody who
        holds one of them through a ladder — a payroll manager who implies the
        officer tier — keeps holding it, and the message says so rather than
        pretending the removal worked.

        AND IT NEVER TAKES AWAY A PERMISSION ANOTHER ROLE THEY HOLD ALSO NEEDS.
        Two roles could not share a permission before bundles — one row, one
        group, unique — so the question could not arise. Now they can, and
        removing "Budget team" must not quietly break "Finance — budgets" for
        somebody who holds both. A permission that another role of theirs still
        requires is KEPT, and if that leaves nothing to remove the answer says
        so instead of reporting a removal that did not happen.
        """
        self._require_manage()
        profile = self._safe_profile(profile_id)
        user = self._internal_user(user_id)
        target = user.sudo()
        bundle = profile.group_ids
        direct = set(target.group_ids.ids)
        removable = bundle.filtered(lambda g: g.id in direct)
        if not removable:
            if set(bundle.ids) <= set(target.all_group_ids.ids):
                raise UserError(_(
                    "%(who)s has \"%(what)s\" because of another role they "
                    "hold, not directly. Take that other role away instead — "
                    "removing this one here would change nothing.",
                    who=target.name or '', what=profile.name))
            raise UserError(_(
                "%(who)s does not have \"%(what)s\".",
                who=target.name or '', what=profile.name))

        shared = removable.filtered(
            lambda g: g in self._groups_their_other_roles_need(target, profile))
        removable -= shared
        if not removable:
            # THE WAY OUT IS PART OF THE REFUSAL (ledger B7). Two roles made of
            # the same permissions each point at the other, and somebody who is
            # only told "take the other one away instead" has been sent round a
            # circle. So the sentence names the other role AND says the thing
            # that actually ends it.
            others = self._roles_covering(target, profile)
            named = ', '.join('"%s"' % (p.name or '') for p in others[:3])
            raise UserError(_(
                "Every permission in \"%(what)s\" is also part of %(others)s, "
                "which %(who)s holds too — so taking this one away would "
                "change nothing. Take the other one away instead, or, if the "
                "two roles have come to mean the same thing, archive one of "
                "them from its own card.",
                what=profile.name,
                others=named or _("another role"),
                who=target.name or ''))

        target.write({'group_ids': [(3, g.id) for g in removable]})
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
            'applied_group_ids': [(6, 0, removable.ids)],
            'applied_on': fields.Datetime.now(),
            'ended_on': fields.Datetime.now(),
            'ended_note': _("Taken away by %s.", self.env.user.name or ''),
        })
        return {'ok': True, 'message': _(
            "%(who)s no longer has \"%(what)s\".",
            who=target.name or '', what=profile.name)}

    def _roles_covering(self, target, profile):
        """The other roles this person fully holds that between them account for
        every permission in `profile`.

        It is the refusal's evidence: "another role" is a shrug, and the name of
        the role somebody has to deal with is an instruction.
        """
        wanted = set(profile.group_ids.ids)
        held = set(target.sudo().all_group_ids.ids)
        out = self.env['pb.role.profile'].sudo().browse()
        for other in self.env['pb.role.profile'].sudo().search(
                [('active', '=', True), ('id', '!=', profile.id)],
                order='area, sequence, name'):
            if not other.group_ids or not set(other.group_ids.ids) <= held:
                continue
            if set(other.group_ids.ids) & wanted:
                out |= other
        return out

    def _groups_their_other_roles_need(self, target, profile):
        """Everything the OTHER roles this person fully holds are made of.

        "Fully holds" is the same test the board uses everywhere else: all of a
        role's permissions, transitively. A role they only partly hold is not a
        role they hold, so it has no claim on a permission being removed.
        """
        held = set(target.all_group_ids.ids)
        others = self.env['pb.role.profile'].sudo().search(
            [('active', '=', True), ('id', '!=', profile.id)])
        keep = self.env['res.groups'].browse()
        for other in others:
            if other.group_ids and set(other.group_ids.ids) <= held:
                keep |= other.group_ids
        return keep

    def _safe_profile(self, profile_id):
        """The third refusal (see the module docstring).

        It looks at the whole bundle AND at the frozen single group the role
        used to be, because the one route that has ever got past the model's
        constraint is a raw write to that column.
        """
        profile = self.env['pb.role.profile'].browse(int(profile_id or 0))
        if not profile.exists():
            raise UserError(_("That role is not on this system any more."))
        profile.check_access('read')
        if not profile.group_ids:
            raise UserError(_(
                "\"%s\" does not point at a permission, so there is nothing to "
                "hand out.", profile.name or ''))
        if forbidden_in_closure(profile.group_ids | profile.group_id, self.env):
            raise UserError(_(
                "\"%s\" would carry the administrator permission for the whole "
                "system. It is never given out from this screen — an "
                "administrator changes it on the person's own record, "
                "deliberately.", profile.name or ''))
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

    # =========================================================== the left menu
    #
    # "WHICH SCREENS DOES THIS ROLE OPEN" IS NEVER WRITTEN DOWN ON THE ROLE.
    # It is worked out, here, every time it is asked — by matching what the role
    # carries against what each entry on the left menu asks for. A role that
    # stored its own list of screens would be a second copy of the truth, and
    # the second copy is the one that goes stale: the day somebody re-gates an
    # entry, every role that mentions it is quietly lying. Worked out, there is
    # nothing to keep in step.
    #
    # AND IT IS WORKED OUT ON THE SERVER. The rule has to be the SAME rule the
    # left menu itself uses (`pb.sidebar.item.get_sidebar_data`): an entry with
    # no permissions on it is open to everybody, an entry is opened by holding
    # ANY ONE of the permissions named on it, and holding is transitive. A copy
    # of that rule in the browser is a copy that will disagree, and it would
    # disagree by telling somebody they can see a screen they cannot.

    def _rail(self):
        """The left menu as it is written down: (sections, items).

        `(None, None)` on a build that has no left menu of its own — this
        module must stay installable without one, and every reader below treats
        that as "there is nothing to say" rather than as a failure.
        """
        if 'pb.sidebar.item' not in self.env:
            return None, None
        sections = self.env['pb.sidebar.section'].sudo().search(
            [('active', '=', True)], order='sequence, id')
        items = self.env['pb.sidebar.item'].sudo().search(
            [('active', '=', True)], order='section_id, sequence, id')
        return sections, items

    def _rail_skeleton_items(self):
        """The top-level entries only — what "entries on the left menu" counts.

        A sub-screen is part of an entry, not another one, and counting it
        would make the number on the board disagree with the number of things
        a person can point at down the side of their screen.
        """
        _sections, items = self._rail()
        if items is None:
            return []
        return items.filtered(lambda i: not i.parent_id)

    def _any_gated(self):
        """Is ANY entry on the left menu limited at all — by a permission OR by
        a role?

        When nothing is, every "this role opens…" answer is honestly empty, and
        the screens say so in those words instead of showing a blank column.
        The role lane counts here for the same reason it counts everywhere
        else: an entry only the access team opens IS gated, and a screen that
        said "nothing is limited yet" beside it would be wrong.
        """
        _sections, items = self._rail()
        if not items:
            return False
        return bool(any(items.mapped('groups_id'))
                    or any(items.filtered(lambda i: self._gate_roles_raw(i))))

    def _gate_roles(self, item):
        """The roles that open ONE entry, archived ones left out.

        Same answer as the model's own `_gate_roles`, asked from the facade so
        every derivation below reads it the one way.
        """
        if 'role_ids' not in item._fields:
            return self.env['pb.role.profile'].browse()
        # `active_test` does NOT reach into a many-to-many read — it comes off
        # the relation table — so the archived ones are filtered by hand, here
        # and in the model's own `_gate_roles`, which is the rule this mirrors.
        return item.sudo().with_context(
            active_test=False).role_ids.filtered('active')

    def _gate_roles_raw(self, item):
        """Every role written on the entry, archived ones INCLUDED.

        "Is this entry gated at all" is a different question from "who gets
        through it", and answering the first with the active list would make
        archiving the last role on an entry open that entry to everybody — see
        `pb.sidebar.item._gate_roles_raw`, which is the rule this mirrors.
        """
        if 'role_ids' not in item._fields:
            return self.env['pb.role.profile'].browse()
        return item.sudo().with_context(active_test=False).role_ids

    def _held_ids(self, groups):
        """Everything these permissions actually carry, as a set of ids.

        Transitive, through `implied_closure` (ledger A3) — the left menu asks
        `all_group_ids`, so anything less would under-report every ladder.
        """
        if not groups:
            return set()
        return set(implied_closure(groups).ids)

    def _unlocks(self, item, held):
        """The left menu's OWN test, one entry at a time.

        An entry with no permissions and no roles on it is open to everybody
        and is therefore opened by NOBODY IN PARTICULAR — it is not something a
        role can claim credit for. An entry that names permissions is opened by
        holding any one of them; an entry that names ROLES is opened by holding
        one of those roles in full, which is the same test the menu itself now
        applies (`pb.sidebar.item._state_for`).
        """
        if item.groups_id and set(item.groups_id.ids) & held:
            return True
        for role in self._gate_roles(item):
            if role.group_ids and set(role.group_ids.ids) <= held:
                return True
        return False

    def _opens_for(self, groups, rail=None):
        """Which entries on the left menu these permissions unlock.

        `rail` is the answer to `_rail()` when the caller already has it — the
        composer asks this question once per ability, and reading the menu
        thirty-five times to answer thirty-five one-line hints is thirty-four
        reads nobody needed.
        """
        _sections, items = rail if rail is not None else self._rail()
        if items is None:
            return []
        held = self._held_ids(groups)
        if not held:
            return []
        out = []
        for item in items.filtered(lambda i: not i.parent_id):
            kids = items.filtered(lambda c, p=item: c.parent_id == p)
            opened = [k for k in kids if self._unlocks(k, held)]
            if not self._unlocks(item, held) and not opened:
                continue
            out.append({
                'id': item.id,
                'label': item.name or '',
                'icon': item.icon or 'circle',
                'locked': bool(item.restricted),
                'subs': [k.name or '' for k in opened],
            })
        return out

    def _everyone_items(self):
        """The entries everybody with a login already sees.

        The roles lens names them under the column rather than leaving somebody
        to wonder why "Home" is not in the list.
        """
        _sections, items = self._rail()
        if items is None:
            return []
        return [i.name or '' for i in items.filtered(
            lambda i: not i.parent_id and not i.groups_id
            and not self._gate_roles_raw(i))]

    def _opens_hint(self, groups, rail=None):
        """"opens Pay Run and People" — the one-line version, for a tick box."""
        names = [o['label'] for o in self._opens_for(groups, rail=rail)]
        if not names:
            return _("does not open anything new on the left menu")
        if len(names) == 1:
            return _("opens %s", names[0])
        return _("opens %(most)s and %(last)s",
                 most=', '.join(names[:-1]), last=names[-1])

    def _item_state(self, item, held):
        """What one entry looks like to somebody holding `held`.

        Three answers, and the middle one is the reason this is not a boolean:
        an entry marked as a teaser is SHOWN to people who cannot open it, so
        "off" would be a lie about what they see.
        """
        if not item.groups_id and not self._gate_roles_raw(item):
            return 'on', False
        if self._unlocks(item, held):
            return 'on', True
        return ('locked' if item.restricted else 'off'), False

    def _rail_states(self, groups, rail=None):
        """The whole left menu, drawn as somebody holding `groups` would see it.

        `newly_lit` is the entry this selection is what OPENS — never one that
        was already open to everybody, because highlighting those would credit
        a role with something it did not do.
        """
        sections, items = rail if rail is not None else self._rail()
        if sections is None:
            return [], 0
        held = self._held_ids(groups)
        out, lit = [], 0
        for section in sections:
            rows = []
            mine = items.filtered(lambda i, s=section: i.section_id == s)
            for item in mine.filtered(lambda i: not i.parent_id):
                state, gained = self._item_state(item, held)
                lit += 1 if gained else 0
                kids = []
                for kid in mine.filtered(lambda c, p=item: c.parent_id == p):
                    kstate, kgained = self._item_state(kid, held)
                    lit += 1 if kgained else 0
                    kids.append({'id': kid.id, 'label': kid.name or '',
                                 'icon': kid.icon or 'circle',
                                 'state': kstate, 'newly_lit': kgained})
                rows.append({'id': item.id, 'label': item.name or '',
                             'icon': item.icon or 'circle',
                             'state': state, 'newly_lit': gained,
                             'children': kids})
            if rows:
                out.append({'key': section.technical_key or '',
                            'label': section.name or '',
                            'show_label': bool(section.show_label),
                            'items': rows})
        return out, lit

    def _rail_skeleton(self, rail=None):
        """The left menu with nothing held — the shape, before any ticking."""
        sections, _lit = self._rail_states(
            self.env['res.groups'].browse(), rail=rail)
        return sections

    # ============================================================ a role, close
    @api.model
    def role_detail(self, profile_id):
        """One role, opened out: what it opens, what it lets somebody do, and
        who holds it — with, for each holder, whether it is theirs or lent."""
        self._require()
        profile = self.env['pb.role.profile'].browse(int(profile_id or 0))
        if not profile.exists():
            raise UserError(_("That role is not on this system any more."))
        profile.check_access('read')

        lent = self._lent_until(profile)
        holders = profile.holders(cap=HOLDER_CAP)
        total = profile.holder_count
        return {
            'id': profile.id,
            'opens': self._opens_for(profile.group_ids),
            'everyone': self._everyone_items(),
            'any_gated': self._any_gated(),
            'abilities': [{'id': a.id, 'name': a.name or '',
                           'description': a.description or ''}
                          for a in profile.ability_ids],
            'holders': [{'id': u.id, 'name': u.name or '',
                         'login': u.login or '',
                         'avatar': '/web/image/res.users/%s/avatar_128' % u.id,
                         'source': 'lent' if u.id in lent else 'held',
                         'until': lent.get(u.id, {}).get('until', ''),
                         'by': lent.get(u.id, {}).get('by', ''),
                         'delegation_id': lent.get(u.id, {}).get('id', 0)}
                        for u in holders],
            'holder_count': total,
            'more': max(0, total - len(holders)),
        }

    def _lent_until(self, profile):
        """Who is only holding this because somebody lent it, and until when.

        Only a HAND-OVER counts as lent. A grant made on this board is also a
        row in the same table, and it is not a loan — calling it one would put
        an end date on something that has none.
        """
        out = {}
        rows = safe(
            lambda: self.env['pb.access.delegation'].sudo().search(
                [('state', '=', 'active'), ('origin', '=', 'delegation'),
                 ('profile_ids', 'in', profile.id)]),
            None, 'the running hand-overs for a role')
        for row in (rows or []):
            out.setdefault(row.delegate_user_id.id, {
                'id': row.id,
                'until': fields.Date.to_string(row.date_end) or '',
                'by': row.delegator_user_id.name or '',
            })
        return out

    # ============================================================ the composer
    @api.model
    def composer_options(self):
        """Everything the "New role" dialog needs, in one read."""
        self._require_manage()
        abilities = self.env['pb.role.ability'].sudo().search(
            [('active', '=', True)])
        profiles = self.env['pb.role.profile'].search([('active', '=', True)])
        rail = self._rail()
        return {
            'areas': [{'key': key, 'label': area_label(key, self.env)}
                      for key, _label in PROFILE_AREAS],
            'abilities': [{'id': a.id, 'name': a.name or '',
                           'description': a.description or '',
                           'area': a.area or '',
                           'area_label': area_label(a.area, self.env),
                           'opens_hint': self._opens_hint(a.group_ids,
                                                          rail=rail)}
                          for a in abilities],
            'roles': [{'id': p.id, 'name': p.name or '',
                       'description': p.description or '',
                       'area': p.area or '',
                       'ability_ids': p.ability_ids.ids}
                      for p in profiles],
            'rail': self._rail_skeleton(rail=rail),
            'any_gated': self._any_gated(),
        }

    @api.model
    def preview_rail(self, ability_ids):
        """The left menu as a holder of these abilities would see it.

        Same rule, same server, same method as the roles lens — which is the
        whole point: what the dialog promises while somebody is ticking boxes
        is worked out by the code that will answer for it afterwards.
        """
        self._require_manage()
        abilities = self._abilities(ability_ids)
        sections, lit = self._rail_states(abilities.group_ids)
        area = self._dominant_area(abilities) if abilities else ''
        return {
            'sections': sections,
            'lit': lit,
            'abilities': len(abilities),
            'any_gated': self._any_gated(),
            # WHO WOULD ALREADY HOLD IT. A role built out of permissions people
            # already have is held by them the moment it is written down, and a
            # dialog that promised "nobody holds it yet" would be contradicted
            # by its own board one second later.
            'already_held_by': self._already_hold(abilities.group_ids),
            # Where this would land if nobody says otherwise. Worked out here,
            # by the same method that will decide it, so the dialog cannot show
            # one answer and the button do another.
            'area': area,
            'area_label': area_label(area, self.env) if area else '',
        }

    def _abilities(self, ability_ids):
        ids = [int(a) for a in (ability_ids or []) if a]
        return self.env['pb.role.ability'].sudo().browse(ids).exists()

    def _already_hold(self, groups):
        """How many people already hold ALL of these permissions.

        Same arithmetic the board uses for a role's holders — an intersection,
        transitively — because it is the same question asked one moment before
        the role exists rather than one moment after.
        """
        if not groups:
            return 0
        def count():
            users = None
            for group in groups.sudo():
                current = group.all_user_ids.filtered(lambda u: u.active)
                users = current if users is None else (users & current)
                if not users:
                    return 0
            return len(users or [])
        return safe(count, 0, 'who already holds a set of permissions')

    @api.model
    def create_role(self, name, description=None, area=None, ability_ids=None):
        """Write a new role down.

        IT CREATES THE ROLE AND NOTHING ELSE. Nobody is put into anything: a
        new role is held by nobody until somebody is deliberately given it, and
        a builder that quietly enrolled its author would be the one surprise
        this screen cannot afford.

        THE ABSOLUTE, ONE LAST TIME. The abilities refuse a forbidden
        permission, the role refuses it again, and this refuses it before
        either — because the facade is the only layer that sees the request
        before it becomes a write.
        """
        self._require_manage()
        name = (name or '').strip()
        if not name:
            raise UserError(_(
                "Give the role a name somebody could say out loud — it is what "
                "people will ask for by."))

        abilities = self._abilities(ability_ids)
        if not abilities:
            raise UserError(_(
                "Tick at least one thing this role lets somebody do. A role "
                "with nothing in it is a name that hands out nothing."))

        needle = fold(name)
        clash = next((p for p in self.env['pb.role.profile'].sudo().search(
            [('active', '=', True)]) if fold(p.name) == needle), None)
        if clash:
            raise UserError(_(
                "There is already a role called \"%s\". Two roles with one "
                "name is how somebody ends up granting the wrong one — give "
                "this one a different name, or change the one that exists.",
                clash.name or ''))

        bad = forbidden_in_closure(abilities.group_ids, self.env)
        if bad:
            raise UserError(_(
                "That would carry %s — the administrator permission for the "
                "whole system. It is never something a role can hand out.",
                ', '.join('"%s"' % (g.display_name or g.name or '')
                          for g in bad)))

        # TWO ROLES THAT HAND OUT EXACTLY THE SAME THING ARE ONE ROLE WITH TWO
        # NAMES, and they are worse than that: neither can ever be taken away
        # from somebody who holds both, because each is the reason the other's
        # permissions have to stay (ledger A4/B7). The refusal names the role
        # that already exists and offers the honest alternative — start from it
        # — rather than leaving somebody to discover the deadlock months later.
        twin = self._identical_role(abilities.group_ids)
        if twin:
            raise UserError(_(
                "\"%(what)s\" would hand out exactly what \"%(twin)s\" already "
                "hands out, down to the last permission. Two roles that mean "
                "the same thing cannot be told apart afterwards, and neither "
                "can be taken away from somebody who holds both. Give this one "
                "something \"%(twin)s\" does not have — or start from "
                "\"%(twin)s\" and change it.",
                what=name, twin=twin.name or ''))

        area = area or self._dominant_area(abilities)
        last = self.env['pb.role.profile'].sudo().search(
            [('area', '=', area)], order='sequence desc', limit=1)
        profile = self.env['pb.role.profile'].sudo().create({
            'name': name,
            'description': (description or '').strip(),
            'area': area,
            'sequence': (last.sequence or 0) + 10,
            'ability_ids': [(6, 0, abilities.ids)],
        })
        # THE MESSAGE HAS TO MATCH THE BOARD BEHIND IT. A role built out of
        # permissions people already have is held by them from the moment it is
        # written down, and "nobody holds it yet" beside a card saying "held by
        # four people" is the screen contradicting itself.
        held = profile.holder_count
        if not held:
            return {'ok': True, 'id': profile.id, 'message': _(
                "\"%s\" is written down. Nobody holds it yet — give it to "
                "somebody when you are ready.", name)}
        return {'ok': True, 'id': profile.id, 'message': _(
            "\"%(what)s\" is written down. %(who)s already able to do all of "
            "it, so they hold it from the start.",
            what=name,
            who=counted(held, _("1 person is"), _("%s people are")))}

    def _identical_role(self, groups):
        """The active role whose permissions are EXACTLY these, if there is one.

        Exactly, not "overlapping": a role that is a bigger or smaller version
        of another is a different job and a legitimate thing to write down. It
        is the two that are indistinguishable that cause the deadlock.
        """
        wanted = set(groups.ids)
        if not wanted:
            return self.env['pb.role.profile'].browse()
        for other in self.env['pb.role.profile'].sudo().search(
                [('active', '=', True)], order='area, sequence, name'):
            if set(other.group_ids.ids) == wanted:
                return other
        return self.env['pb.role.profile'].browse()

    @api.model
    def archive_role(self, profile_id):
        """Put a role away.

        NOT A DELETE, AND DELIBERATELY NOT. The audit trail points at roles by
        name and by id, and a role that has been given to somebody and taken
        away again is part of what happened here — deleting the row would leave
        the history saying "given X" about nothing at all. Archiving keeps the
        record and takes the name off every screen.

        IT REFUSES WHILE ANYBODY STILL HOLDS IT. Archiving does not remove a
        single permission from a single person — it only stops the board naming
        what they have. A role put away with four holders would leave four
        people carrying access nobody can see or take back, which is the exact
        opposite of what this board is for. So the refusal names them.
        """
        self._require_manage()
        profile = self.env['pb.role.profile'].browse(int(profile_id or 0))
        if not profile.exists():
            raise UserError(_("That role is not on this system any more."))
        profile.check_access('read')

        holders = profile.holders(cap=HOLDER_CAP)
        if holders:
            names = ', '.join(u.name or '' for u in holders[:4])
            more = max(0, profile.holder_count - 4)
            raise UserError(_(
                "%(who)s still %(has)s \"%(what)s\"%(more)s. Take it away from "
                "them first — archiving it would leave them holding access "
                "this board can no longer name.",
                who=names,
                has=_("holds") if profile.holder_count == 1 else _("hold"),
                what=profile.name or '',
                more=(_(" and %s more", more) if more else '')))

        running = safe(
            lambda: self.env['pb.access.delegation'].sudo().search_count(
                [('state', '=', 'active'), ('origin', '=', 'delegation'),
                 ('profile_ids', 'in', profile.id)]),
            0, 'the running hand-overs of a role')
        if running:
            raise UserError(_(
                "\"%s\" is part of a hand-over that is still running. End the "
                "hand-over first — the Hand-overs tab has it.",
                profile.name or ''))

        gated = self._entries_gated_only_by(profile)
        profile.sudo().write({'active': False})
        message = _("\"%s\" has been put away. It is off the board, and "
                    "everything it was ever part of is still in the history.",
                    profile.name or '')
        if gated:
            # NO DEAD END. An entry whose only key has just been put away is an
            # entry nobody but an administrator can reach, and the person who
            # archived the role is the one person who can still fix it.
            message = _(
                "%(said)s One entry on the left menu was opened only by it — "
                "%(where)s — so nobody can reach that entry now. The Screens "
                "lens shows it with a warning.",
                said=message, where=', '.join('"%s"' % n for n in gated))
        return {'ok': True, 'message': message, 'gated': gated}

    def _entries_gated_only_by(self, profile):
        """The left-menu entries this role is the ONLY way into."""
        _sections, items = self._rail()
        if items is None:
            return []
        out = []
        for item in items:
            roles = self._gate_roles(item)
            if not roles or item.groups_id:
                continue
            if set(roles.ids) == {profile.id}:
                out.append(item.name or '')
        return out

    def _dominant_area(self, abilities):
        """Where a new role belongs, if nobody said.

        The area most of its abilities come from, and the catalogue's own order
        breaks a tie — never whichever one the database happened to return
        first, which is how the same ticks land in two different places.
        """
        order = [key for key, _label in PROFILE_AREAS]
        counts = {}
        for ability in abilities:
            if ability.area:
                counts[ability.area] = counts.get(ability.area, 0) + 1
        if not counts:
            return order[0]
        return sorted(counts, key=lambda k: (-counts[k], order.index(k)
                                             if k in order else 99))[0]

    # ================================================================== people
    #
    # THE OTHER WAY ROUND. The roles lens answers "who holds this"; this one
    # answers "what does this person have" — and the second question is the one
    # somebody asks when a colleague says they cannot find a screen. The answer
    # is a PICTURE of that colleague's left menu, not a list of permissions,
    # because the left menu is the thing they are both looking at.
    #
    # AND IT IS THE LEFT MENU'S OWN ANSWER. The states come from
    # `pb.sidebar.item.visibility_for`, which is the SAME code that draws the
    # real menu for the real person. This module does not own that rule and
    # deliberately keeps no copy of it: a copy would drift, and it would drift
    # by showing an administrator a menu their colleague does not have.
    #
    # NOBODY READS SOMEBODY ELSE'S ACCESS UNLESS THEY MAY. The self-only rule
    # for everybody outside the access team is enforced HERE, on the server, in
    # `_person` — not by leaving the picker off the screen. A picker that is
    # absent is a picker somebody can call around.

    def _person(self, user_id):
        """The person being looked at, and the refusal when it is not allowed.

        An empty id means "me", so the lens can open without knowing who it is
        about yet.
        """
        uid = int(user_id or 0) or self.env.uid
        if uid != self.env.uid and not self.can_manage():
            raise AccessError(_(
                "You can look at your own access here. Looking at somebody "
                "else's is something the access team does."))
        return self._internal_user(uid)

    def _job_titles(self, users):
        """What people do, where the system knows — {user id: job title}.

        A name on its own is not enough to pick the right Nguyen out of four,
        and the job title is the thing a person granting access recognises.
        Absent on a build with no employee records, which is why this is a
        `safe()` probe and not a join.
        """
        if not users or 'hr.employee' not in self.env:
            return {}
        def read():
            rows = self.env['hr.employee'].sudo().search_read(
                [('user_id', 'in', users.ids)], ['user_id', 'job_title'])
            out = {}
            for row in rows:
                title = (row.get('job_title') or '').strip()
                if title and row['user_id']:
                    out.setdefault(row['user_id'][0], title)
            return out
        return safe(read, {}, 'the job titles on the people lens') or {}

    def _holders_by_profile(self, profiles):
        """{profile id: the set of people who hold ALL of it}, worked out once.

        Asked per person it would be one intersection per person per role; the
        roles are two dozen and the people are not, so it is asked per ROLE and
        counted afterwards.
        """
        out = {}
        for profile in profiles:
            out[profile.id] = set(safe(
                lambda p=profile: p._holder_users().filtered('active').ids,
                [], 'who holds a role') or [])
        return out

    def _lent_counts(self):
        """{user id: how many roles are on loan to them right now}."""
        rows = safe(
            lambda: self.env['pb.access.delegation'].sudo().search(
                [('state', '=', 'active'), ('origin', '=', 'delegation')]),
            None, 'the running hand-overs')
        out = {}
        for row in (rows or []):
            uid = row.delegate_user_id.id
            out[uid] = out.get(uid, 0) + len(row.profile_ids)
        return out

    @api.model
    def people(self, search=None):
        """Everybody with a login, and how much access each of them carries.

        ME FIRST, THEN ALPHABETICAL. The person opening this screen is the one
        they check first — their own access — and putting them at the top of a
        list of two hundred names saves the one search everybody would
        otherwise type.
        """
        self._require()
        if not self.can_manage():
            # NOT A NARROWER LIST — A LIST OF ONE. Everybody may look at their
            # own access; nobody else's is any of their business, and the lens
            # renders honestly as a single passport rather than an empty search.
            me = self.env.user
            return [self._person_row(
                me, self._holders_by_profile(
                    self.env['pb.role.profile'].visible()),
                self._lent_counts(), self._job_titles(me))]

        needle = fold(search)
        users = self.env['res.users'].sudo().search(
            [('active', '=', True), ('share', '=', False)])
        if needle:
            users = users.filtered(
                lambda u: needle in fold('%s %s' % (u.name or '', u.login or '')))
        profiles = self.env['pb.role.profile'].visible()
        holders = self._holders_by_profile(profiles)
        lent = self._lent_counts()
        titles = self._job_titles(users)

        me = self.env.uid
        users = users.sorted(lambda u: (u.id != me, fold(u.name), u.id))
        return [self._person_row(u, holders, lent, titles)
                for u in users[:PEOPLE_CAP]]

    def _person_row(self, user, holders, lent, titles):
        user = user.sudo()
        return {
            'id': user.id,
            'name': user.name or '',
            'login': user.login or '',
            'title': titles.get(user.id, ''),
            'avatar': '/web/image/res.users/%s/avatar_128' % user.id,
            'role_count': len([1 for ids in holders.values()
                               if user.id in ids]),
            'lent_count': lent.get(user.id, 0),
            'is_me': user.id == self.env.uid,
        }

    # ============================================================ the passport
    def _rail_as_seen_by(self, user, rail=None):
        """The left menu, drawn as THIS PERSON sees it.

        The shape is the mini-rail's, so the passport and the role builder draw
        the same component from the same kind of answer. The word differs by
        one: the left menu calls what somebody cannot see `hidden`, and the
        miniature calls it `off` — the same thing, and this is the one place
        the two vocabularies meet.
        """
        sections, items = rail if rail is not None else self._rail()
        if sections is None:
            return [], 0, 0, 0
        seen = self.env['pb.sidebar.item'].sudo().visibility_for(user)
        states, sec_states = seen['items'], seen['sections']

        def state_of(item):
            raw = states.get(item.id, 'hidden')
            return 'off' if raw == 'hidden' else raw

        out, on, locked, total = [], 0, 0, 0
        for section in sections:
            rows = []
            mine = items.filtered(lambda i, s=section: i.section_id == s)
            for item in mine.filtered(lambda i: not i.parent_id):
                state = state_of(item)
                total += 1
                on += 1 if state == 'on' else 0
                locked += 1 if state == 'locked' else 0
                kids = [{'id': k.id, 'label': k.name or '',
                         'icon': k.icon or 'circle', 'state': state_of(k),
                         'newly_lit': False}
                        for k in mine.filtered(lambda c, p=item: c.parent_id == p)]
                rows.append({'id': item.id, 'label': item.name or '',
                             'icon': item.icon or 'circle', 'state': state,
                             'newly_lit': False, 'children': kids})
            if rows:
                out.append({'key': section.technical_key or '',
                            'label': section.name or '',
                            'show_label': bool(section.show_label),
                            'restricted': sec_states.get(section.id) == 'locked',
                            'items': rows})
        return out, on, total, locked

    def _roles_of(self, user):
        """Every role this person holds, and WHY they hold it.

        Held or lent, and a lent one carries who lent it and until when —
        because "take this away" and "end the hand-over" are different actions
        with different consequences, and a screen that offered the first for a
        loan would leave a hand-over record pointing at access that is gone
        (ledger B3).
        """
        held = set(user.sudo().all_group_ids.ids)
        loans = self._loans_to(user)
        manage = self.can_manage()
        out = []
        for profile in self.env['pb.role.profile'].visible():
            if not profile.group_ids or not set(profile.group_ids.ids) <= held:
                continue
            loan = loans.get(profile.id)
            out.append({
                'profile_id': profile.id,
                'name': profile.name or '',
                'description': profile.description or '',
                'area': profile.area or '',
                'area_label': area_label(profile.area, self.env),
                'source': 'lent' if loan else 'held',
                'lent_by': (loan or {}).get('by', ''),
                'lent_until': (loan or {}).get('until', ''),
                'delegation_id': (loan or {}).get('id', 0),
                'can_take_back': bool(manage and not loan),
            })
        return out

    def _loans_to(self, user):
        """{profile id: the running hand-over that put it there}.

        A grant made on the roles board is a row in the same table and is NOT a
        loan — putting an end date on it would be the screen inventing one.
        """
        out = {}
        rows = safe(
            lambda: self.env['pb.access.delegation'].sudo().search(
                [('state', '=', 'active'), ('origin', '=', 'delegation'),
                 ('delegate_user_id', '=', user.id)]),
            None, 'the running hand-overs for a person')
        for row in (rows or []):
            for profile in row.profile_ids:
                out.setdefault(profile.id, {
                    'id': row.id,
                    'until': fields.Date.to_string(row.date_end) or '',
                    'by': row.delegator_user_id.name or '',
                })
        return out

    @api.model
    def passport(self, user_id=None):
        """One person's access, whole: their menu, their roles, and why."""
        self._require()
        user = self._person(user_id)
        rows, on, total, locked = self._rail_as_seen_by(user)
        roles = self._roles_of(user)
        titles = self._job_titles(user)
        return {
            'header': {
                'id': user.id,
                'name': user.sudo().name or '',
                'login': user.sudo().login or '',
                'title': titles.get(user.id, ''),
                'avatar': '/web/image/res.users/%s/avatar_128' % user.id,
                'sees_x': on,
                'of_y': total,
                'locked_n': locked,
                'role_count': len(roles),
                'lent_count': len([r for r in roles if r['source'] == 'lent']),
                'is_me': user.id == self.env.uid,
                'is_admin': bool(safe(
                    lambda: user.sudo().has_group('base.group_system'), False,
                    'whether somebody is an administrator')),
            },
            'rail': rows,
            'roles': roles,
            'any_gated': self._any_gated(),
            'can_manage': self.can_manage(),
        }

    @api.model
    def as_user(self, user_id=None):
        """The overlay every lens needs to repaint itself as somebody else.

        IT IS A VIEW AND NOTHING ELSE. It returns what a person HOLDS so a
        screen can say so; it changes nothing, it is not passed to any write,
        and no write on this board takes a "who am I looking at" argument —
        granting and lending both name their target outright.
        """
        self._require()
        user = self._person(user_id)
        held = set(user.sudo().all_group_ids.ids)
        return {
            'id': user.id,
            'name': user.sudo().name or '',
            'avatar': '/web/image/res.users/%s/avatar_128' % user.id,
            'is_me': user.id == self.env.uid,
            'profile_ids': [p.id for p in self.env['pb.role.profile'].visible()
                            if p.group_ids and set(p.group_ids.ids) <= held],
        }

    # =============================================================== the picker
    @api.model
    def user_options(self, term=None):
        """Folded in Python over `search_read` of two columns (R78/R56).

        SHAPE FROZEN. Three dialogs read it; the People lens does not — it
        needs the person's roles counted and their own row included, which is a
        different question and gets its own method rather than a flag here.
        """
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

    # =============================================================== the screens
    #
    # THE THIRD QUESTION, AND THE ONE NOBODY COULD ANSWER BEFORE. The roles lens
    # says who holds what; the people lens says what one person has; this one
    # says WHO CAN OPEN THIS SCREEN — and it draws the left menu AS the left
    # menu, because that is the thing everybody is already looking at.
    #
    # IT IS ALSO THE ONLY PLACE A GATE IS EDITED. Before this lens, changing who
    # sees an entry meant a list view of permission-group names, which is how
    # the live menu ended up with no gates at all: the screen that could change
    # them was unreadable, so nobody did. Here a gate is a ROLE — a name and a
    # sentence — and the row shows, while you edit it, who that lets in.
    #
    # NOT A SECOND VISIBILITY RULE. Every state on every row comes from
    # `pb.sidebar.item.visibility_for`, the same method the real menu and the
    # person passport ask. This section decides nothing; it reads, and it writes
    # gates back.

    def _rail_all(self):
        """The left menu INCLUDING what is switched off.

        `_rail()` hands back the live menu, which is right for every other
        reader here and wrong for this one: an editor that hid the entries
        somebody has switched off is an editor with no way to switch one back
        on.
        """
        if 'pb.sidebar.item' not in self.env:
            return None, None
        sections = self.env['pb.sidebar.section'].sudo().with_context(
            active_test=False).search([], order='sequence, id')
        items = self.env['pb.sidebar.item'].sudo().with_context(
            active_test=False).search([], order='section_id, sequence, id')
        return sections, items

    def _screen_roles(self, item):
        """(the roles that open it, the ones that have been put away).

        Archived roles are read back deliberately: an entry whose only key has
        been archived is reachable by nobody, and a lens that simply showed no
        gate would be describing it as open to everybody.
        """
        if 'role_ids' not in item._fields:
            empty = self.env['pb.role.profile'].browse()
            return empty, empty
        every = item.sudo().with_context(active_test=False).role_ids
        return every.filtered('active'), every.filtered(lambda r: not r.active)

    def _role_chip(self, profile, archived=False):
        return {
            'id': profile.id,
            'name': profile.name or '',
            'description': profile.description or '',
            'area': profile.area or '',
            'area_label': area_label(profile.area, self.env),
            'holders': safe(lambda: profile.holder_count, 0,
                            'how many people hold a role'),
            'archived': bool(archived),
        }

    def _roles_by_group(self):
        """{permission id: the roles that carry it}, worked out ONCE.

        Asked per entry it would be one search over the whole catalogue per row
        on the lens, which on a menu of sixty entries is sixty searches to
        answer one question that has the same answer every time.
        """
        out = {}
        for profile in self.env['pb.role.profile'].sudo().search(
                [('active', '=', True)], order='area, sequence, name'):
            for group in profile.group_ids:
                out.setdefault(group.id, []).append(profile.name or '')
        return out

    def _legacy_note(self, item, by_group=None):
        """What the entry's older PERMISSIONS mean, said without naming one.

        Raw permission-group names are exactly what this home exists to stop
        showing people, so a permission that is part of a role is reported as
        THAT ROLE, and one that is part of none is reported as a count. Both are
        honest; neither is a technical name on a screen about plain English.
        """
        groups = item.sudo().groups_id
        if not groups:
            return {'n': 0, 'roles': [], 'loose': 0}
        by_group = self._roles_by_group() if by_group is None else by_group
        names, loose = [], 0
        for group in groups:
            carried = by_group.get(group.id)
            if not carried:
                loose += 1
                continue
            for name in carried:
                if name not in names:
                    names.append(name)
        return {'n': len(groups), 'roles': names, 'loose': loose}

    def _screen_row(self, item, states, seen_by, by_group=None):
        active_roles, archived_roles = self._screen_roles(item)
        legacy = self._legacy_note(item, by_group=by_group)
        gated = bool(active_roles or archived_roles or item.sudo().groups_id)
        chips = ([self._role_chip(r) for r in active_roles]
                 + [self._role_chip(r, archived=True) for r in archived_roles])
        raw = states.get(item.id, 'hidden' if item.active else 'off')
        return {
            'id': item.id,
            'label': item.name or '',
            'icon': item.icon or 'circle',
            'section_id': item.section_id.id,
            'parent_id': item.parent_id.id or 0,
            'sequence': item.sequence or 0,
            'active': bool(item.active),
            'restricted': bool(item.restricted),
            'everyone': not gated,
            'gates': chips,
            'legacy': legacy,
            'state': ('off' if raw == 'hidden' else raw) if item.active else 'off',
            # NOBODY CAN GET IN. Two different kinds of nobody, and they need
            # different sentences: a gate whose roles are all archived is a
            # mistake somebody made, and a gate whose roles are simply unheld is
            # a role waiting to be given to somebody.
            'dead': bool(archived_roles and not active_roles
                         and not item.sudo().groups_id),
            'orphan': bool(active_roles and not item.sudo().groups_id
                           and not any(c['holders'] for c in chips)),
            'seen_by': seen_by.get(item.id, 0),
            'children': [],
        }

    def _seen_by_counts(self, items):
        """{entry id: how many people with a login can open it}.

        Asked the cheap way round: an entry's audience is the union of the
        people who hold each permission on it and the people who hold each of
        its roles, which is a handful of reads — where asking it per PERSON
        would be one closure walk per person per entry.

        AND EACH OF THOSE READS IS MADE ONCE. The same permission gates several
        entries and the same role opens several more, so the two memos below are
        the difference between a handful of queries and a hundred.
        """
        out = {}
        admins = safe(
            lambda: self.env.ref('base.group_system').sudo(
            ).all_user_ids.filtered('active'),
            None, 'who the administrators are')
        admin_ids = set(admins.ids) if admins is not None else set()
        everybody = safe(
            lambda: self.env['res.users'].sudo().search_count(
                [('active', '=', True), ('share', '=', False)]),
            0, 'how many people have a login')
        by_group, by_role = {}, {}
        for item in items:
            active_roles, _archived = self._screen_roles(item)
            groups = item.sudo().groups_id
            if not groups and not active_roles:
                out[item.id] = everybody
                continue
            who = set(admin_ids)
            for group in groups.sudo():
                if group.id not in by_group:
                    by_group[group.id] = set(safe(
                        lambda g=group: g.all_user_ids.filtered('active').ids,
                        [], 'who holds a permission') or [])
                who |= by_group[group.id]
            for profile in active_roles:
                if profile.id not in by_role:
                    by_role[profile.id] = set(safe(
                        lambda p=profile: p._holder_users().filtered(
                            'active').ids, [], 'who holds a role') or [])
                who |= by_role[profile.id]
            out[item.id] = len(who)
        return out

    @api.model
    def screens_board(self, user_id=None):
        """The left menu, drawn as the left menu, with its gates on it."""
        self._require()
        person = self._person(user_id)
        sections, items = self._rail_all()
        if sections is None:
            return {'can_manage': self.can_manage(), 'sections': [],
                    'roles': [], 'any_gated': False,
                    'counts': {'entries': 0, 'gated': 0, 'everyone': 0},
                    'seeing': {'id': person.id, 'name': person.sudo().name or '',
                               'is_me': person.id == self.env.uid},
                    'headline': _("There is no left menu on this system yet.")}

        states = self.env['pb.sidebar.item'].sudo().visibility_for(person)
        seen_by = self._seen_by_counts(items)
        by_group = self._roles_by_group()
        item_states, sec_states = states['items'], states['sections']

        out, gated, everyone = [], 0, 0
        for section in sections:
            mine = items.filtered(lambda i, s=section: i.section_id == s)
            rows = []
            for item in mine.filtered(lambda i: not i.parent_id):
                row = self._screen_row(item, item_states, seen_by, by_group)
                row['children'] = [
                    self._screen_row(kid, item_states, seen_by, by_group)
                    for kid in mine.filtered(
                        lambda c, p=item: c.parent_id == p)]
                rows.append(row)
                if item.active:
                    gated += 0 if row['everyone'] else 1
                    everyone += 1 if row['everyone'] else 0
            if not rows:
                continue
            out.append({
                'id': section.id,
                'key': section.technical_key or '',
                'label': section.name or '',
                'show_label': bool(section.show_label),
                'active': bool(section.active),
                'restricted': sec_states.get(section.id) == 'locked',
                'items': rows,
            })
        return {
            'can_manage': self.can_manage(),
            'sections': out,
            'roles': [{'id': p.id, 'name': p.name or '',
                       'description': p.description or '',
                       'area': p.area or '',
                       'area_label': area_label(p.area, self.env),
                       'holders': p.holder_count}
                      for p in self.env['pb.role.profile'].visible()],
            'any_gated': self._any_gated(),
            'counts': {'entries': gated + everyone, 'gated': gated,
                       'everyone': everyone},
            'seeing': {'id': person.id, 'name': person.sudo().name or '',
                       'is_me': person.id == self.env.uid},
            'headline': self._screens_headline(gated, everyone),
        }

    def _screens_headline(self, gated, everyone):
        """ONE expression per sentence, so the spaces survive (R34)."""
        if not gated:
            return _("Every entry on the left menu is open to everybody with a "
                     "login. Put a role on one and only the people who hold it "
                     "will see it.")
        if not everyone:
            return _("Every entry on the left menu asks for something.")
        return _("%(g)s on the left menu %(v)s limited to a role; %(e)s open to "
                 "everybody with a login.",
                 g=counted(gated, _("1 entry"), _("%s entries")),
                 v=_("is") if gated == 1 else _("are"),
                 e=counted(everyone, _("1 is"), _("%s are")))

    @api.model
    def screen_detail(self, item_id, user_id=None):
        """One entry, opened out: who can reach it, through what, and what is
        inside it."""
        self._require()
        item = self._screen(item_id)
        person = self._person(user_id)
        sections, items = self._rail_all()
        states = self.env['pb.sidebar.item'].sudo().visibility_for(person)
        seen_by = self._seen_by_counts(item | items.filtered(
            lambda i, p=item: i.parent_id == p))

        by_group = self._roles_by_group()
        row = self._screen_row(item, states['items'], seen_by, by_group)
        kids = items.filtered(lambda c, p=item: c.parent_id == p)
        row['children'] = [
            self._screen_row(k, states['items'], seen_by, by_group)
            for k in kids]
        active_roles, archived_roles = self._screen_roles(item)
        held_ids = set(active_roles.ids) | set(archived_roles.ids)
        row.update({
            'section_label': item.section_id.name or '',
            'restriction_reason': item.restriction_reason or '',
            'who': self._who_sees(item, active_roles),
            'options': [{'id': p.id, 'name': p.name or '',
                         'description': p.description or '',
                         'area': p.area or '',
                         'area_label': area_label(p.area, self.env),
                         'holders': p.holder_count}
                        for p in self.env['pb.role.profile'].visible()
                        if p.id not in held_ids],
            'can_manage': self.can_manage(),
        })
        return row

    def _screen(self, item_id):
        item = self.env['pb.sidebar.item'].sudo().with_context(
            active_test=False).browse(int(item_id or 0))
        if not item.exists():
            raise UserError(_("That entry is not on the left menu any more."))
        return item

    def _who_sees(self, item, active_roles):
        """The people who can open this entry, and WHY each of them can.

        Capped, because an entry open to everybody is a fact and not a list —
        and the count beside it already says how many.
        """
        groups = item.sudo().groups_id
        if not groups and not active_roles:
            return {'everyone': True, 'rows': [], 'total': 0, 'more': 0}

        by_role = {}
        for profile in active_roles:
            for uid in safe(
                    lambda p=profile: p._holder_users().filtered('active').ids,
                    [], 'who holds a role') or []:
                by_role.setdefault(uid, []).append(profile.name or '')
        by_group = set()
        for group in groups.sudo():
            by_group |= set(safe(
                lambda g=group: g.all_user_ids.filtered('active').ids, [],
                'who holds a permission') or [])
        admins = set(safe(
            lambda: self.env.ref('base.group_system').sudo(
            ).all_user_ids.filtered('active').ids, [],
            'who the administrators are') or [])

        everybody = set(by_role) | by_group | admins
        users = self.env['res.users'].sudo().browse(
            sorted(everybody)).exists().filtered('active')
        users = users.sorted(lambda u: (not bool(by_role.get(u.id)),
                                        fold(u.name)))
        rows = []
        for user in users[:HOLDER_CAP]:
            roles = by_role.get(user.id) or []
            if roles:
                why = _("Holds %s", ', '.join(roles))
            elif user.id in by_group:
                why = _("An older permission this entry has always asked for")
            else:
                why = _("An administrator — every entry is open to them")
            rows.append({'id': user.id, 'name': user.name or '',
                         'avatar': '/web/image/res.users/%s/avatar_128' % user.id,
                         'why': why,
                         'via_role': bool(roles)})
        return {'everyone': False, 'rows': rows, 'total': len(users),
                'more': max(0, len(users) - len(rows))}

    # -------------------------------------------------------- changing a gate
    @api.model
    def set_screen_roles(self, item_id, role_ids):
        """Say which roles open an entry.

        THE PERMISSION LANE IS NOT TOUCHED. Entries carry older permission
        groups from before roles existed, and this screen deliberately cannot
        remove one: a lens that let somebody drop a permission they cannot see
        the name of would take a door away from people it never showed them.
        Those are edited on the advanced list, by an administrator, on purpose.
        """
        self._require_manage()
        item = self._screen(item_id)
        wanted = self.env['pb.role.profile'].sudo().browse(
            [int(r) for r in (role_ids or []) if r]).exists()
        for profile in wanted:
            self._gateable_profile(profile)
        before = set(self._screen_roles(item)[0].ids)
        item.sudo().write({'role_ids': [(6, 0, wanted.ids)]})
        after = set(wanted.ids)
        return {'ok': True, 'message': self._gate_message(item, before, after)}

    def _gateable_profile(self, profile):
        """May this role be put on a left-menu gate?

        NOT `_safe_profile`, and the difference is deliberate. That one asks
        "may the person in front of me be handed this role", so it checks their
        READ access — which is right for granting and wrong here: a role that is
        only LISTED to the heads of HR (`visible_group_id`) still gates the
        People entry, the lens already draws it on the gate, and refusing to
        write the list back would leave somebody unable to change any OTHER gate
        on that entry. Which roles open a menu entry is a fact about the MENU.

        What is still checked is the absolute, over the whole implied closure —
        a gate is not a way to smuggle the administrator permission onto a
        screen — and that the role hands out anything at all.
        """
        if not profile.sudo().group_ids:
            raise UserError(_(
                "\"%s\" does not hand out anything yet, so putting it on this "
                "entry would gate it on nothing.", profile.sudo().name or ''))
        if forbidden_in_closure(profile.sudo().group_ids, self.env):
            raise UserError(_(
                "\"%s\" would carry the administrator permission for the whole "
                "system. It is never something a role can hand out, and never "
                "something a screen can ask for.", profile.sudo().name or ''))
        return profile

    def _gate_message(self, item, before, after):
        """ONE expression per sentence (R34), and it says what CHANGED."""
        added, dropped = after - before, before - after
        what = item.name or ''
        if added and not dropped:
            return _("%(n)s can now open %(what)s.",
                     n=counted(len(added), _("One more role"),
                               _("%s more roles")), what=what)
        if dropped and not added:
            if not after and not item.sudo().groups_id:
                return _("%s is open to everybody with a login again.", what)
            return _("%(n)s no longer opens %(what)s.",
                     n=counted(len(dropped), _("One role"), _("%s roles")),
                     what=what)
        if added or dropped:
            return _("The roles that open %s have been changed.", what)
        return _("Nothing changed — those are the roles it already asked for.")

    @api.model
    def set_screen_flags(self, item_id, active=None, restricted=None):
        """Switch an entry on or off, and choose what people without it see."""
        self._require_manage()
        item = self._screen(item_id)
        vals = {}
        if active is not None:
            vals['active'] = bool(active)
        if restricted is not None:
            vals['restricted'] = bool(restricted)
        if not vals:
            raise UserError(_("Nothing was asked for."))
        item.sudo().write(vals)

        if 'active' in vals:
            return {'ok': True, 'message': (
                _("\"%s\" is back on the left menu.", item.name or '')
                if vals['active'] else
                _("\"%s\" is off the left menu. Nobody sees it, and nothing "
                  "behind it has changed — switch it back on whenever you "
                  "want.", item.name or ''))}
        return {'ok': True, 'message': (
            _("People who cannot open \"%s\" now see it locked, with a note "
              "saying what it is.", item.name or '')
            if vals['restricted'] else
            _("People who cannot open \"%s\" no longer see it at all.",
              item.name or ''))}

    @api.model
    def reorder_screens(self, section_id, item_ids):
        """Put the entries of one section in the order they were dragged into.

        Numbered in TENS, so the next thing somebody adds by hand has somewhere
        to land between two of them without renumbering the section.
        """
        self._require_manage()
        section = self.env['pb.sidebar.section'].sudo().with_context(
            active_test=False).browse(int(section_id or 0))
        if not section.exists():
            raise UserError(_("That block of the left menu is not here."))
        items = self.env['pb.sidebar.item'].sudo().with_context(
            active_test=False).browse(
                [int(i) for i in (item_ids or []) if i]).exists()
        stray = items.filtered(lambda i: i.section_id != section)
        if stray:
            raise UserError(_(
                "\"%s\" is not in that part of the menu. Entries are reordered "
                "inside their own block.", stray[0].name or ''))
        for index, item in enumerate(items):
            item.write({'sequence': (index + 1) * 10})
        return {'ok': True,
                'message': _("The left menu is in the new order.")}

    # ================================================================ exports
    @api.model
    def export_roles(self):
        self._require()
        return self.env['pb.vendor.export'].build_roles()

    @api.model
    def export_delegations(self):
        self._require()
        return self.env['pb.vendor.export'].build_delegations()
